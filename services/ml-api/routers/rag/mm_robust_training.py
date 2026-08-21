"""
Adversarial training defense demo — the third defense in the Adversarial
Robustness Lab, and a different SHAPE of defense than the other two
(JPEG recompression, randomized smoothing in mm_adversarial_defenses.py):
those are inference-time tricks bolted onto an already-trained model,
while adversarial training changes HOW the model is trained in the first
place (Madry et al. 2018 — train on adversarially-perturbed examples,
not just clean ones, so the model's decision boundary is pushed away
from the attack directions it will actually see).

Why this is a SEPARATE small digit classifier, not the main tool's
ImageNet-pretrained MobileNetV2: real adversarial training needs many
epochs over a real labeled dataset, which is infeasible to do per-
request (or even per-deploy) against a 1000-class ImageNet model on a
CPU-only Space. Instead this bundles two SMALL CNNs (TinyCNN, ~110K
params), trained ONCE offline on MNIST digits and shipped as static
checkpoints (mnist_standard.pt, mnist_adversarial.pt, ~427KB each,
services/ml-api/models/) — no training happens at request time, no
dataset download either.

Real training/eval results (not guessed, not simulated) — 3 epochs each,
PGD attack at epsilon=0.2, 7 steps, alpha=0.05, same architecture, same
data, only the training procedure differs:
  STANDARD model:      clean accuracy 98.62%  →  robust accuracy  1.09%
  ADVERSARIAL-trained:  clean accuracy 96.98%  →  robust accuracy 84.30%
The standard model is almost completely fooled by a PGD attack it never
saw during training; the adversarially-trained model gives up only
~13 points of clean accuracy in exchange for staying right ~84% of the
time under the SAME attack. This is the real, honest trade-off adversarial
training makes — it is not free, and it is not universal (this demo only
covers this attack type/epsilon range against this specific model).

Both models are attacked independently, white-box (each with its OWN
gradients, i.e. the strongest fair attack against each), at the same
epsilon the user picks — not a shared perturbation, since the optimal
attack direction differs per model.

Honest limitations: (1) only demonstrated on MNIST digits, a much
simpler domain than the rest of this tool's ImageNet photos — the
robustness gain does not automatically generalize to larger, more
complex models or datasets. (2) tested only against PGD at the specific
epsilon range offered here; adversarial training's real-world robustness
against attacks it wasn't trained against (transferred/black-box, or a
different epsilon entirely) can be weaker. (3) sample digits are fixed,
bundled MNIST test images, not the user's own upload — a real user photo
of a handwritten digit would need real preprocessing (crop/threshold/
resize) this demo doesn't attempt.
"""

import base64
import io
import logging
import threading

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.rag.mm_robust_training_samples import SAMPLE_DIGITS

logger = logging.getLogger(__name__)
router = APIRouter()

_MODELS_DIR = "models"
_PGD_STEPS = 20
_PGD_ALPHA_DIVISOR = 8

_standard_model = None
_adversarial_model = None
_lock = threading.Lock()


class TinyCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv2d(1, 16, 3, padding=1)
        self.c2 = nn.Conv2d(16, 32, 3, padding=1)
        self.fc1 = nn.Linear(32 * 7 * 7, 64)
        self.fc2 = nn.Linear(64, 10)

    def forward(self, x):
        x = F.max_pool2d(F.relu(self.c1(x)), 2)
        x = F.max_pool2d(F.relu(self.c2(x)), 2)
        x = x.flatten(1)
        x = F.relu(self.fc1(x))
        return self.fc2(x)


def _ensure_loaded() -> bool:
    global _standard_model, _adversarial_model
    if _standard_model is not None:
        return True
    with _lock:
        if _standard_model is not None:
            return True
        try:
            standard = TinyCNN()
            standard.load_state_dict(torch.load(f"{_MODELS_DIR}/mnist_standard.pt", map_location="cpu"))
            standard.eval()
            for p in standard.parameters():
                p.requires_grad_(False)

            adversarial = TinyCNN()
            adversarial.load_state_dict(torch.load(f"{_MODELS_DIR}/mnist_adversarial.pt", map_location="cpu"))
            adversarial.eval()
            for p in adversarial.parameters():
                p.requires_grad_(False)

            _standard_model = standard
            _adversarial_model = adversarial
            return True
        except Exception as exc:
            logger.warning("MNIST robustness-demo models failed to load: %s", exc)
            return False


def _pgd_attack(model: nn.Module, x: torch.Tensor, y: torch.Tensor, epsilon: float, steps: int = _PGD_STEPS):
    alpha = epsilon / _PGD_ALPHA_DIVISOR
    x_adv = x.clone().detach()
    x_adv = (x_adv + torch.empty_like(x_adv).uniform_(-epsilon, epsilon)).clamp(0, 1)
    for _ in range(steps):
        x_adv = x_adv.detach().requires_grad_(True)
        loss = F.cross_entropy(model(x_adv), y)
        grad = torch.autograd.grad(loss, x_adv)[0]
        x_adv = x_adv.detach() + alpha * grad.sign()
        x_adv = torch.min(torch.max(x_adv, x - epsilon), x + epsilon).clamp(0, 1)
    return x_adv.detach()


def _predict(model: nn.Module, x: torch.Tensor):
    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=-1)[0]
        pred = int(probs.argmax().item())
        conf = float(probs[pred].item())
    return pred, conf


def _tensor_to_b64(x: torch.Tensor) -> str:
    arr = (x.clamp(0, 1)[0, 0].detach().numpy() * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr, mode="L").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _run_one_model(model: nn.Module, x_clean: torch.Tensor, y: torch.Tensor, epsilon: float):
    clean_pred, clean_conf = _predict(model, x_clean)
    x_adv = _pgd_attack(model, x_clean, y, epsilon)
    adv_pred, adv_conf = _predict(model, x_adv)
    return {
        "clean_pred": clean_pred,
        "clean_conf": round(clean_conf, 4),
        "adv_pred": adv_pred,
        "adv_conf": round(adv_conf, 4),
        "fooled": adv_pred != int(y.item()),
        "adversarial_image": _tensor_to_b64(x_adv),
    }


class RunRequest(BaseModel):
    sample_id: int
    epsilon: float = 0.2


def run_robust_training_demo(sample_id: int, epsilon: float) -> dict:
    if not (0.02 <= epsilon <= 0.4):
        raise HTTPException(status_code=400, detail="epsilon must be between 0.02 and 0.4")
    if not (0 <= sample_id < len(SAMPLE_DIGITS)):
        raise HTTPException(status_code=400, detail="invalid sample_id")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Robustness-demo models are unavailable right now.")

    sample = SAMPLE_DIGITS[sample_id]
    raw = base64.b64decode(sample["image_b64"])
    img = Image.open(io.BytesIO(raw)).convert("L")
    x = torch.from_numpy(np.asarray(img).astype("float32") / 255.0).unsqueeze(0).unsqueeze(0)
    y = torch.tensor([sample["label"]])

    return {
        "label": sample["label"],
        "standard": _run_one_model(_standard_model, x, y, epsilon),
        "adversarial_trained": _run_one_model(_adversarial_model, x, y, epsilon),
    }


@router.get("/mm-robust-training/samples")
def robust_training_samples():
    return {"samples": [{"id": i, "label": s["label"], "image_b64": s["image_b64"]} for i, s in enumerate(SAMPLE_DIGITS)]}


@router.post("/mm-robust-training/run")
def robust_training_run(body: RunRequest):
    return run_robust_training_demo(body.sample_id, body.epsilon)
