"""Invisible watermark embed/verify (backlog item — "embedding" half of
deepfake detection; detection half is mm_tampering.py/mm_noise_forensics.py).

Pure local image processing, no external API and no budget cost, unlike
mm_ai_fill.py/mm_text_to_image.py — this never calls out to a paid model.

A short fixed-size payload (1-byte length + 24-byte label + 2-byte checksum,
always 216 bits) is embedded into the Y (luma) channel via 8x8-block DCT
quantization-index-modulation (QIM): one mid-frequency coefficient per block
is nudged to the nearest even/odd multiple of `_STEP` depending on the bit
being encoded, then the block is inverse-DCT'd back. Each payload bit is
redundantly repeated across many blocks (however many `total_blocks // 216`
allows, capped at `_MAX_REDUNDANCY`) and recovered by majority vote, which
is what gives this some tolerance to mild recompression/resizing noise —
though a resize that changes pixel dimensions will misalign the block grid
entirely and break extraction; this only survives being re-saved at the same
dimensions (e.g. PNG round-trip), not arbitrary transforms.

The payload is fixed-size specifically so embed and verify can compute the
same redundancy factor independently from image dimensions alone, with no
chicken-and-egg dependency on decoding the label before knowing how many
blocks per bit to read.
"""
from __future__ import annotations

import base64
import io
import logging
import struct
import zlib

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_STEP = 24.0  # QIM quantization step for the embedded DCT coefficient
_COEF_POS = (3, 2)  # mid-frequency AC coefficient — imperceptible, survives mild resave
_MAX_LABEL_LEN = 24
_DEFAULT_LABEL = "MLU-VERIFIED"
_FRAME_BYTES = 1 + _MAX_LABEL_LEN + 2  # length byte + padded label + 16-bit checksum
_FRAME_BITS = _FRAME_BYTES * 8  # = 216, always — see module docstring
_MAX_REDUNDANCY = 40  # cap so embedding stays fast on large images


def _bits_from_bytes(data: bytes) -> list[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bytes_from_bits(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        b = 0
        for j in range(8):
            b = (b << 1) | bits[i + j]
        out.append(b)
    return bytes(out)


def _encode_payload(label: str) -> bytes:
    label_bytes = label.encode("utf-8")[:_MAX_LABEL_LEN]
    padded = label_bytes.ljust(_MAX_LABEL_LEN, b"\x00")
    header = bytes([len(label_bytes)])
    checksum = zlib.crc32(header + padded) & 0xFFFF
    return header + padded + struct.pack(">H", checksum)


def _decode_payload(data: bytes) -> tuple[str, bool]:
    if len(data) < _FRAME_BYTES:
        return "", False
    header, padded, crc_stored = data[0], data[1:1 + _MAX_LABEL_LEN], struct.unpack(">H", data[-2:])[0]
    crc_calc = zlib.crc32(bytes([header]) + padded) & 0xFFFF
    if crc_calc != crc_stored:
        return "", False
    length = min(header, _MAX_LABEL_LEN)
    return padded[:length].decode("utf-8", errors="replace"), True


def _qim_embed(coef: float, bit: int, step: float) -> float:
    q = round(coef / step)
    if (q % 2) != bit:
        q += 1
    return q * step


def _qim_extract(coef: float, step: float) -> int:
    return int(round(coef / step)) % 2


def _redundancy_for(total_blocks: int) -> int:
    return min(_MAX_REDUNDANCY, total_blocks // _FRAME_BITS)


def embed_watermark(b64: str, label: str = _DEFAULT_LABEL) -> dict:
    """Returns {"ok": True, "image": <b64 PNG>} on success, or
    {"ok": False, "error": <str>} if the image is too small to hold the
    fixed-size payload with at least 1x redundancy per bit."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        w, h = img.size
        ycc = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2YCrCb).astype(np.float32)
        y = ycc[:, :, 0]

        h_blocks, w_blocks = h // 8, w // 8
        total_blocks = h_blocks * w_blocks
        redundancy = _redundancy_for(total_blocks)
        if redundancy < 1:
            return {"ok": False, "error": "image too small to embed a watermark"}

        bits = _bits_from_bytes(_encode_payload(label))
        r, c = _COEF_POS
        block_idx = 0
        for bit in bits:
            for _ in range(redundancy):
                by, bx = divmod(block_idx, w_blocks)
                block_idx += 1
                y0, x0 = by * 8, bx * 8
                coeffs = cv2.dct(y[y0:y0 + 8, x0:x0 + 8])
                coeffs[r, c] = _qim_embed(coeffs[r, c], bit, _STEP)
                y[y0:y0 + 8, x0:x0 + 8] = cv2.idct(coeffs)

        ycc[:, :, 0] = np.clip(y, 0, 255)
        rgb = cv2.cvtColor(ycc.astype(np.uint8), cv2.COLOR_YCrCb2RGB)
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format="PNG")
        return {"ok": True, "image": base64.b64encode(buf.getvalue()).decode()}
    except Exception as exc:
        logger.warning("Watermark embed failed: %s", exc)
        return {"ok": False, "error": "embed failed"}


def verify_watermark(b64: str) -> dict:
    """Returns {"present": bool, "label": str|None, "confidence": float}.
    `present` is only True when the recovered checksum matches — a random/
    unwatermarked image will decode garbage bits that almost never pass the
    16-bit checksum by chance. `confidence` is the average per-bit majority
    agreement across all redundant copies (1.0 = every copy of every bit
    agreed), scaled down when the checksum failed since that's the stronger
    signal it isn't actually watermarked (or was too badly damaged)."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        w, h = img.size
        ycc = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2YCrCb).astype(np.float32)
        y = ycc[:, :, 0]

        h_blocks, w_blocks = h // 8, w // 8
        total_blocks = h_blocks * w_blocks
        redundancy = _redundancy_for(total_blocks)
        if redundancy < 1:
            return {"present": False, "label": None, "confidence": 0.0}

        r, c = _COEF_POS
        block_idx = 0
        bits, agreements = [], []
        for _ in range(_FRAME_BITS):
            ones = 0
            for _ in range(redundancy):
                by, bx = divmod(block_idx, w_blocks)
                block_idx += 1
                y0, x0 = by * 8, bx * 8
                coeffs = cv2.dct(y[y0:y0 + 8, x0:x0 + 8])
                ones += _qim_extract(coeffs[r, c], _STEP)
            bit = 1 if ones * 2 >= redundancy else 0
            bits.append(bit)
            agreements.append(max(ones, redundancy - ones) / redundancy)

        label, ok = _decode_payload(_bytes_from_bits(bits))
        avg_agreement = sum(agreements) / len(agreements)
        return {
            "present": ok,
            "label": label if ok else None,
            "confidence": round(avg_agreement, 3) if ok else round(avg_agreement * 0.3, 3),
        }
    except Exception as exc:
        logger.warning("Watermark verify failed: %s", exc)
        return {"present": False, "label": None, "confidence": 0.0}


class WatermarkEmbedRequest(BaseModel):
    image: str  # b64 image, any common format
    label: str = _DEFAULT_LABEL


class WatermarkVerifyRequest(BaseModel):
    image: str


@router.post("/mm-watermark/embed")
def watermark_embed_endpoint(body: WatermarkEmbedRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    label = body.label.strip() or _DEFAULT_LABEL
    if len(label) > _MAX_LABEL_LEN:
        raise HTTPException(status_code=400, detail=f"label must be {_MAX_LABEL_LEN} characters or fewer")
    result = embed_watermark(body.image, label)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("error", "embed failed"))
    return {"image": result["image"]}


@router.post("/mm-watermark/verify")
def watermark_verify_endpoint(body: WatermarkVerifyRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    return verify_watermark(body.image)
