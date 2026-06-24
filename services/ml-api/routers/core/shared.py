"""Shared globals, constants, and helper functions (no endpoints)."""
import json
import os
import re
from typing import Any, Dict

import joblib
import pandas as pd

from routers.core.fe_transformer import FeatureEngineeringTransformer

# app root is two levels up from routers/core/shared.py
HERE       = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_DIR = os.path.join(HERE, "schemas")
MODEL_DIR  = os.path.join(HERE, "models")
os.makedirs(SCHEMA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
FRONTEND   = os.path.join(HERE, "frontend", "index.html")

MODELS: Dict[str, Any] = {}

_BUILTIN_IDS: frozenset = frozenset({"titanic", "iris", "diabetes", "insurance"})

ACCENT_PALETTE = [
    "#818cf8", "#38bdf8", "#34d399", "#fbbf24",
    "#f87171", "#fb923c", "#a78bfa", "#4ade80",
]

_HF_SPACE_ID = "wram1708/ml-unified"
_HF_PKL_FILES = [
    "models/diabetes_pipeline.pkl",
    "models/diabetes_labels.pkl",
    "models/iris_pipeline.pkl",
    "models/iris_labels.pkl",
    "models/titanic_pipeline.pkl",
    "models/titanic_labels.pkl",
    "models/insurance_pipeline.pkl",
]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _detect_gpu() -> dict:
    try:
        import torch
        if torch.cuda.is_available():
            return {"available": True, "name": torch.cuda.get_device_name(0)}
    except Exception:
        pass
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            return {"available": True, "name": r.stdout.strip().split("\n")[0]}
    except Exception:
        pass
    return {"available": False, "name": None}


def _fetch_hf_models():
    """Download missing model files from HF Space XET storage."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        return
    try:
        from huggingface_hub import hf_hub_download
        import shutil
    except ImportError:
        print("huggingface_hub not available — skipping model download", flush=True)
        return
    os.makedirs(MODEL_DIR, exist_ok=True)
    all_fpaths = list(_HF_PKL_FILES)
    if os.path.isdir(SCHEMA_DIR):
        for _sf in os.listdir(SCHEMA_DIR):
            if _sf.endswith(".json"):
                _mid = _sf[:-5]
                if _mid in _BUILTIN_IDS:
                    continue
                for _suffix in ("_fe.pkl", "_actuals.json"):
                    _extra = f"models/{_mid}{_suffix}"
                    if _extra not in all_fpaths:
                        all_fpaths.append(_extra)
    for fpath in all_fpaths:
        local = os.path.join(HERE, fpath)
        if os.path.exists(local):
            continue
        try:
            print(f"HF: downloading {fpath} ...", flush=True)
            cached = hf_hub_download(
                repo_id=_HF_SPACE_ID,
                repo_type="space",
                filename=fpath,
                token=token,
            )
            shutil.copy2(cached, local)
            print(f"HF: {fpath} ready", flush=True)
        except Exception as exc:
            print(f"HF: could not download {fpath}: {exc}", flush=True)


def _upload_model_to_hf(model_id: str) -> None:
    """Upload newly trained model files to HF Space XET storage."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF: HF_TOKEN not set — trained model will not persist across restarts", flush=True)
        return
    try:
        from huggingface_hub import HfApi as _HfApi  # noqa: PLC0415
        _api = _HfApi()
        _files = [
            (os.path.join(MODEL_DIR, f"{model_id}_pipeline.pkl"), f"models/{model_id}_pipeline.pkl"),
            (os.path.join(MODEL_DIR, f"{model_id}_fe.pkl"),       f"models/{model_id}_fe.pkl"),
            (os.path.join(SCHEMA_DIR, f"{model_id}.json"),        f"schemas/{model_id}.json"),
        ]
        if os.path.exists(os.path.join(MODEL_DIR, f"{model_id}_labels.pkl")):
            _files.append((
                os.path.join(MODEL_DIR, f"{model_id}_labels.pkl"),
                f"models/{model_id}_labels.pkl",
            ))
        if os.path.exists(os.path.join(MODEL_DIR, f"{model_id}_actuals.json")):
            _files.append((
                os.path.join(MODEL_DIR, f"{model_id}_actuals.json"),
                f"models/{model_id}_actuals.json",
            ))
        for _local, _repo_path in _files:
            if not os.path.exists(_local):
                continue
            _api.upload_file(
                path_or_fileobj=_local,
                path_in_repo=_repo_path,
                repo_id=_HF_SPACE_ID,
                repo_type="space",
                token=token,
            )
            print(f"HF: uploaded {_repo_path}", flush=True)
    except Exception as _exc:
        print(f"HF: upload after train failed (non-fatal): {_exc}", flush=True)


def _delete_model_from_hf(model_id: str) -> None:
    if not os.environ.get("SPACE_ID"):
        return
    token = os.environ.get("HF_TOKEN")
    if not token:
        return
    try:
        from huggingface_hub import HfApi as _HfApi
        _api = _HfApi()
        _candidates = [
            f"models/{model_id}_pipeline.pkl",
            f"models/{model_id}_fe.pkl",
            f"models/{model_id}_labels.pkl",
            f"models/{model_id}_actuals.json",
            f"schemas/{model_id}.json",
        ]
        for _rpath in _candidates:
            try:
                _api.delete_file(
                    path_in_repo=_rpath,
                    repo_id=_HF_SPACE_ID,
                    repo_type="space",
                    token=token,
                )
            except Exception:
                pass
    except Exception as _exc:
        print(f"HF: delete failed (non-fatal): {_exc}", flush=True)


def _load():
    for fname in sorted(os.listdir(SCHEMA_DIR)):
        if not fname.endswith(".json"):
            continue
        mid    = fname[:-5]
        schema = json.load(open(os.path.join(SCHEMA_DIR, fname)))
        pkl_path = os.path.join(MODEL_DIR, f"{mid}_pipeline.pkl")
        if not os.path.exists(pkl_path):
            continue
        pipeline = joblib.load(pkl_path)
        le_path  = os.path.join(MODEL_DIR, f"{mid}_labels.pkl")
        le       = joblib.load(le_path) if os.path.exists(le_path) else None
        _fe_pkl  = os.path.join(MODEL_DIR, f"{mid}_fe.pkl")
        _fe_loaded = joblib.load(_fe_pkl) if os.path.exists(_fe_pkl) else FeatureEngineeringTransformer({})
        _act_pkl = os.path.join(MODEL_DIR, f"{mid}_actuals.json")
        _actuals_loaded = json.load(open(_act_pkl)) if os.path.exists(_act_pkl) else None
        MODELS[mid] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
            "fe":       _fe_loaded,
            "actuals":  _actuals_loaded,
        }
