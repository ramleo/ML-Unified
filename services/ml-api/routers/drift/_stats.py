"""Statistical functions for drift detection: PSI, KS test, histogram, helpers."""
from __future__ import annotations

import logging
import math
import numpy as np

logger = logging.getLogger(__name__)


def norm_cdf(x: float, mean: float, std: float) -> float:
    return 0.5 * (1.0 + math.erf((x - mean) / (std * math.sqrt(2.0))))


def psi_numeric(vals: list, ref_mean: float, ref_std: float, n_bins: int = 10) -> float:
    if not vals or ref_std <= 0:
        return 0.0
    lo    = ref_mean - 3.0 * ref_std
    hi    = ref_mean + 3.0 * ref_std
    edges = np.linspace(lo, hi, n_bins + 1)

    ref_fracs = np.array([
        norm_cdf(float(edges[i + 1]), ref_mean, ref_std) -
        norm_cdf(float(edges[i]),     ref_mean, ref_std)
        for i in range(n_bins)
    ])
    ref_fracs = np.clip(ref_fracs, 1e-6, None)
    ref_fracs /= ref_fracs.sum()

    clipped = np.clip(vals, lo + 1e-12, hi - 1e-12)
    actual_counts, _ = np.histogram(clipped, bins=edges)
    actual_fracs = actual_counts / max(actual_counts.sum(), 1)
    actual_fracs = np.where(actual_fracs == 0, 1e-6, actual_fracs)
    actual_fracs /= actual_fracs.sum()

    psi = float(np.sum((actual_fracs - ref_fracs) * np.log(actual_fracs / ref_fracs)))
    return max(0.0, round(psi, 6))


def psi_categorical(r_dist: dict, ref_dist: dict, opts: list) -> float:
    psi = 0.0
    for o in opts:
        a = max(r_dist.get(o, 0.0), 1e-6)
        e = max(ref_dist.get(o, 0.0), 1e-6)
        psi += (a - e) * math.log(a / e)
    return max(0.0, round(psi, 6))


def ks_test(vals: list, ref_mean: float, ref_std: float):
    try:
        rng         = np.random.default_rng(42)
        n_ref       = min(2000, max(len(vals) * 10, 500))
        ref_samples = rng.normal(ref_mean, ref_std, size=n_ref)

        s1 = np.sort(vals)
        s2 = np.sort(ref_samples)
        n1, n2 = len(s1), len(s2)

        all_x = np.concatenate([s1, s2])
        all_x.sort()
        cdf1 = np.searchsorted(s1, all_x, side="right") / n1
        cdf2 = np.searchsorted(s2, all_x, side="right") / n2
        ks   = float(np.max(np.abs(cdf1 - cdf2)))

        n_eff  = math.sqrt(n1 * n2 / (n1 + n2))
        t      = (n_eff + 0.12 + 0.11 / n_eff) * ks
        pvalue = float(2.0 * math.exp(-2.0 * t * t))
        pvalue = max(0.0, min(1.0, pvalue))
        return ks, pvalue
    except Exception as exc:
        logger.warning("KS test failed, column will show no p-value: %s", exc)
        return None, None


def histogram(vals: list, ref_mean: float, ref_std: float, n_bins: int = 12) -> list | None:
    if not vals or ref_std <= 0:
        return None
    try:
        lo = min(float(np.min(vals)), ref_mean - 2.5 * ref_std)
        hi = max(float(np.max(vals)), ref_mean + 2.5 * ref_std)
        if lo >= hi:
            return None

        edges = np.linspace(lo, hi, n_bins + 1)
        ref_fracs = np.array([
            norm_cdf(float(edges[i + 1]), ref_mean, ref_std) -
            norm_cdf(float(edges[i]),     ref_mean, ref_std)
            for i in range(n_bins)
        ])
        ref_fracs = np.clip(ref_fracs, 0.0, None)

        actual_counts, _ = np.histogram(vals, bins=edges)
        actual_fracs = actual_counts / max(actual_counts.sum(), 1)

        combined_max = max(ref_fracs.max(), actual_fracs.max(), 1e-9)
        return [
            {
                "lo":       round(float(edges[i]), 4),
                "hi":       round(float(edges[i + 1]), 4),
                "ref_h":    round(float(ref_fracs[i])    / combined_max, 4),
                "actual_h": round(float(actual_fracs[i]) / combined_max, 4),
            }
            for i in range(n_bins)
        ]
    except Exception as exc:
        logger.warning("Histogram computation failed, column will show no chart: %s", exc)
        return None


def is_number(v) -> bool:
    try:
        f = float(v)
        return not math.isnan(f) and not math.isinf(f)
    except (TypeError, ValueError):
        return False


def level(score: float, med: float, high: float) -> str:
    if score >= high:
        return "high"
    if score >= med:
        return "medium"
    return "low"


def psi_level(psi: float) -> str:
    if psi >= 0.25:
        return "high"
    if psi >= 0.10:
        return "medium"
    return "low"
