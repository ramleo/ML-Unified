"""
The four attack implementations for the Adversarial Robustness Lab: FGSM,
PGD, the adversarial patch, and the query-only black-box attack. Split out
of mm_adversarial_models.py purely to keep files under this codebase's
~400-line convention. See mm_adversarial.py's module docstring for the
attack narrative and real test findings; see mm_adversarial_models.py's
docstring for why `_model`/`_normalize`/`_categories` must be accessed via
`models.` rather than imported by value.
"""

from . import mm_adversarial_models as models


def _fgsm(x, label_idx: int, epsilon: float, targeted: bool = False):
    """Untargeted: ascend the loss w.r.t. the TRUE label (push away from it).
    Targeted: descend the loss w.r.t. the TARGET label (push toward it) —
    same gradient, opposite sign."""
    import torch
    import torch.nn.functional as F

    x_adv = x.clone().requires_grad_(True)
    logits = models._model(models._normalize(x_adv))
    loss = F.cross_entropy(logits, torch.tensor([label_idx]))
    grad = torch.autograd.grad(loss, x_adv)[0]
    step = -epsilon * grad.sign() if targeted else epsilon * grad.sign()
    x_adv = (x_adv + step).clamp(0, 1)
    return x_adv.detach()


def _pgd(x, label_idx: int, epsilon: float, steps: int = 10, targeted: bool = False):
    import torch
    import torch.nn.functional as F

    alpha = epsilon / 4
    x_adv = x.clone()
    for _ in range(steps):
        x_adv = x_adv.detach().requires_grad_(True)
        logits = models._model(models._normalize(x_adv))
        loss = F.cross_entropy(logits, torch.tensor([label_idx]))
        grad = torch.autograd.grad(loss, x_adv)[0]
        step = -alpha * grad.sign() if targeted else alpha * grad.sign()
        x_adv = x_adv.detach() + step
        x_adv = torch.min(torch.max(x_adv, x - epsilon), x + epsilon)  # project to epsilon ball
        x_adv = x_adv.clamp(0, 1)
    return x_adv.detach()


_PATCH_MAX_STEPS = 150
_PATCH_LR = 0.08


def _adversarial_patch(x, label_idx: int, targeted: bool, patch_frac: float, max_steps: int = _PATCH_MAX_STEPS, lr: float = _PATCH_LR):
    """A DIFFERENT attack family from FGSM/PGD: instead of a tiny,
    imperceptible epsilon-bounded perturbation over the WHOLE image, this
    optimizes a single square region (unconstrained within [0,1], no
    epsilon ball) — a visible "sticker" patch, the kind that could in
    principle be printed and physically placed in a scene. This is the
    single-image, single-placement version (patch optimized for THIS exact
    photo and THIS exact center position) — not the original Brown et al.
    2017 paper's UNIVERSAL patch (trained across many images/positions/
    rotations via expectation-over-transformation to work anywhere, on
    any photo). Real testing found the two attack goals behave very
    differently here: UNTARGETED patches fool the classifier almost
    instantly (often within 1-2 gradient steps, sometimes before real
    optimization even helps — a patch this size is already a large, blunt
    perturbation on its own). TARGETED patches (forcing one exact chosen
    label) are genuinely harder and slower — a small patch (10% of the
    image) failed to reach the target at all within the step budget in
    real testing, while a larger patch (25%) reached it in a handful of
    steps. Early-stops the moment the goal is met (fooled for untargeted,
    exact target for targeted) rather than always running the full step
    budget, so `patch_steps` in the response is a real, honest measure of
    how much optimization this specific run actually needed."""
    import torch
    import torch.nn.functional as F

    size = x.shape[-1]
    p = max(4, int(round(patch_frac * size)))
    top = (size - p) // 2
    mask = torch.zeros_like(x)
    mask[:, :, top:top + p, top:top + p] = 1.0
    patch = torch.rand_like(x)

    for step in range(max_steps):
        patch = patch.detach().requires_grad_(True)
        x_patched = x * (1 - mask) + patch * mask
        logits = models._model(models._normalize(x_patched))
        pred_idx = int(logits.argmax(dim=1)[0])
        if (not targeted and pred_idx != label_idx) or (targeted and pred_idx == label_idx):
            return x_patched.clamp(0, 1).detach(), step
        loss = F.cross_entropy(logits, torch.tensor([label_idx]))
        grad = torch.autograd.grad(loss, patch)[0]
        with torch.no_grad():
            step_dir = -lr * grad.sign() if targeted else lr * grad.sign()
            patch = (patch + step_dir).clamp(0, 1)

    x_patched = (x * (1 - mask) + patch * mask).clamp(0, 1)
    return x_patched.detach(), max_steps


_BLACKBOX_DEFAULT_QUERIES = 1500
_BLACKBOX_MAX_QUERIES = 3000


def _black_box_attack(x, label_idx: int, targeted: bool, epsilon: float, max_queries: int = _BLACKBOX_DEFAULT_QUERIES):
    """A FOURTH, fundamentally different attack: FGSM/PGD/the patch attack
    all use real gradients (a backward pass through the model) — this one
    does NOT. It only calls the model forward and reads back a softmax
    score, exactly like querying someone else's deployed API with no
    access to weights or gradients — the actual "black-box" threat model.
    Implements a simplified SimBA (Guo et al. 2019, score-based): visit
    random, never-repeated (pixel, channel) coordinates; at each one, try
    nudging that single value by +epsilon then -epsilon, keep whichever
    nudge moves the target score (down for untargeted on the true label,
    up for targeted on the chosen label), otherwise leave it unchanged.
    Since each coordinate is touched at most once, the maximum possible
    per-pixel change is bounded by epsilon even with no explicit epsilon-
    ball projection step. Assumes SCORE-based query access (a softmax
    probability, not just a top-1 label) — a real, common API shape (many
    hosted classifiers return confidence), but an easier setting than a
    true label-only black-box, which needs even more queries.

    Real testing found the query cost this predicts is real, not just a
    theoretical estimate: UNTARGETED converged reliably and fast (348
    queries, ~5.5s on a real photo). TARGETED did NOT converge at all in
    real testing — 3000 queries (~46s) failed, and even pushing to 6000
    queries at a larger step size (~94s, already past what one HTTP
    request should reasonably take) still failed to reach the chosen
    label. This is the actual point of shipping this attack: query-only
    black-box attacks are dramatically more expensive than white-box
    ones, and a REQUEST-SIZED query budget is often not enough for a
    targeted goal — a genuine, expected limitation of the threat model,
    not a bug in this implementation."""
    import random

    import torch
    import torch.nn.functional as F

    x_adv = x.clone()
    _, C, H, W = x.shape
    coords = [(c, h, w) for c in range(C) for h in range(H) for w in range(W)]
    random.shuffle(coords)

    with torch.no_grad():
        probs = F.softmax(models._model(models._normalize(x_adv)), dim=1)[0]
    queries = 1

    for (c, h, w) in coords:
        if queries >= max_queries:
            break
        cur_score = probs[label_idx].item()
        for sign in (1, -1):
            trial = x_adv.clone()
            trial[0, c, h, w] = (trial[0, c, h, w] + sign * epsilon).clamp(0, 1)
            with torch.no_grad():
                trial_probs = F.softmax(models._model(models._normalize(trial)), dim=1)[0]
            queries += 1
            new_score = trial_probs[label_idx].item()
            if (new_score > cur_score) if targeted else (new_score < cur_score):
                x_adv, probs = trial, trial_probs
                break
        pred_idx = int(probs.argmax())
        if (not targeted and pred_idx != label_idx) or (targeted and pred_idx == label_idx):
            return x_adv.detach(), queries, True
        if queries >= max_queries:
            break

    return x_adv.detach(), queries, False
