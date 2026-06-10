"""Data drift detection router.

Improvements over v1:
  1. Categorical frequencies — uses actual training frequencies from schema cat_freq
  2. PSI metric — Population Stability Index alongside z-score
  3. KS test — two-sample KS test (upload mode, synthetic ref from training stats)
  4. Distribution histograms — bin data for frontend overlay chart
  5. Persistent buffer — rolling prediction window written to data/drift_buffer.json
  6. Drift trend — timestamped snapshots written to data/drift_history.json
  7. Missing value tracking — null_rate per feature
"""

from __future__ import annotations

from collections import defaultdict, deque

import io
import json
import math
import os
import time

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter(prefix="/drift", tags=["drift"])

# ── Paths ─────────────────────────────────────────────────────────────────────

_DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "data")
_BUFFER_FILE  = os.path.join(_DATA_DIR, "drift_buffer.json")
_HISTORY_FILE = os.path.join(_DATA_DIR, "drift_history.json")
_HISTORY_MAX  = 100   # snapshots kept per model
_TREND_WINDOW = 20    # snapshots embedded in each response

# ── In-memory state ───────────────────────────────────────────────────────────

_recent: dict[str, deque]  = defaultdict(lambda: deque(maxlen=200))
_history: dict[str, list]  = defaultdict(list)
_baseline_cache: dict[str, dict] = {}


# ── Persistence helpers ───────────────────────────────────────────────────────

def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _load_buffer() -> None:
    try:
        with open(_BUFFER_FILE) as f:
            raw = json.load(f)
        for mid, rows in raw.items():
            d: deque = deque(maxlen=200)
            d.extend(rows)
            _recent[mid] = d
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass


def _save_buffer() -> None:
    try:
        _ensure_data_dir()
        with open(_BUFFER_FILE, "w") as f:
            json.dump({mid: list(d) for mid, d in _recent.items()}, f)
    except OSError:
        pass


def _load_history() -> None:
    try:
        with open(_HISTORY_FILE) as f:
            raw = json.load(f)
        for mid, snaps in raw.items():
            _history[mid] = snaps[-_HISTORY_MAX:]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass


def _save_history() -> None:
    try:
        _ensure_data_dir()
        with open(_HISTORY_FILE, "w") as f:
            json.dump(dict(_history), f)
    except OSError:
        pass


def _record_snapshot(model_id: str, result: dict) -> None:
    snap = {
        "ts":            int(time.time()),
        "overall_score": result["overall_score"],
        "overall_level": result["overall_level"],
        "n_recent":      result["n_recent"],
        "source":        result.get("source", "predictions"),
        "features": [
            {
                "name":        f["name"],
                "drift_score": f["drift_score"],
                "drift_level": f["drift_level"],
                "psi":         f.get("psi", 0.0),
            }
            for f in result.get("features", [])
        ],
    }
    _history[model_id].append(snap)
    if len(_history[model_id]) > _HISTORY_MAX:
        _history[model_id] = _history[model_id][-_HISTORY_MAX:]
    _save_history()


# Load persisted data once at import time
_load_buffer()
_load_history()


# ── Public helper (called by app.py /predict) ─────────────────────────────────

def record_input(model_id: str, fields: dict) -> None:
    """Log a raw prediction input for the rolling drift buffer."""
    _recent[model_id].append(fields)
    _save_buffer()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{model_id}")
def get_drift(model_id: str):
    from app import MODELS  # noqa: PLC0415

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m        = MODELS[model_id]
    baseline = _get_baseline(model_id, m)
    rows     = list(_recent[model_id])
    trend    = list(_history.get(model_id, []))[-_TREND_WINDOW:]
    result   = _compute_drift(m["schema"], rows, baseline, mode="predictions")
    result["trend"] = trend
    if rows:
        _record_snapshot(model_id, result)
    return result


@router.post("/{model_id}/upload")
async def upload_drift(model_id: str, file: UploadFile = File(...)):
    from app import MODELS  # noqa: PLC0415

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(400, "CSV is empty")

    m        = MODELS[model_id]
    baseline = _get_baseline(model_id, m)
    rows     = df.to_dict(orient="records")
    trend    = list(_history.get(model_id, []))[-_TREND_WINDOW:]
    result   = _compute_drift(m["schema"], rows, baseline, mode="upload")
    result["source"]   = "upload"
    result["filename"] = file.filename or "dataset.csv"
    result["trend"]    = trend
    _record_snapshot(model_id, result)
    return result


@router.get("/{model_id}/history")
def get_drift_history(model_id: str):
    from app import MODELS  # noqa: PLC0415

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    return {"history": _history.get(model_id, [])}


# ── Baseline extraction ───────────────────────────────────────────────────────

def _get_baseline(model_id: str, model_entry: dict) -> dict:
    if model_id not in _baseline_cache:
        _baseline_cache[model_id] = _extract_pipeline_stats(
            model_entry["pipeline"], model_entry["schema"]
        )
    return _baseline_cache[model_id]


def _extract_pipeline_stats(pipeline, schema: dict) -> dict:
    """Pull mean/std per numeric field from the fitted sklearn pipeline.

    Priority: StandardScaler.mean_/scale_ > SimpleImputer.statistics_ > schema range.
    """
    stats: dict = {}
    try:
        prep = pipeline.named_steps.get("prep")
        if prep is None:
            return stats

        skip = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))
        field_map = {
            f["name"]: f
            for f in schema.get("fields", [])
            if f["name"] not in skip
        }

        for t_name, transformer, cols in prep.transformers_:
            if t_name != "num":
                continue

            imp    = _step(transformer, "imp")
            scaler = _step(transformer, "scaler")

            for i, col in enumerate(cols):
                if col in skip or col not in field_map:
                    continue
                field = field_map[col]
                fmin  = float(field.get("min", 0))
                fmax  = float(field.get("max", 1))
                schema_std = max((fmax - fmin) / 6, 1e-9)

                if scaler is not None and hasattr(scaler, "mean_") and i < len(scaler.mean_):
                    stats[col] = {
                        "mean":   float(scaler.mean_[i]),
                        "std":    max(float(scaler.scale_[i]), 1e-9),
                        "source": "training",
                    }
                elif imp is not None and hasattr(imp, "statistics_") and i < len(imp.statistics_):
                    stats[col] = {
                        "mean":   float(imp.statistics_[i]),
                        "std":    schema_std,
                        "source": "training",
                    }
    except Exception:
        pass

    return stats


def _step(transformer, name):
    if hasattr(transformer, "named_steps"):
        return transformer.named_steps.get(name)
    return None


# ── Core drift computation ────────────────────────────────────────────────────

def _compute_drift(
    schema: dict,
    rows: list[dict],
    baseline: dict,
    mode: str = "predictions",
) -> dict:
    n_recent = len(rows)
    skip     = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))
    features: list[dict] = []
    used_pipeline_baseline = False

    for field in schema.get("fields", []):
        name  = field["name"]
        ftype = field.get("type")
        if name in skip:
            continue

        if ftype == "number":
            feat = _process_numeric(field, name, rows, n_recent, baseline, mode)
            if feat["name"] in baseline:
                used_pipeline_baseline = True
            features.append(feat)

        elif ftype == "select":
            features.append(_process_categorical(field, name, rows, n_recent))

    overall = max((f["drift_score"] for f in features), default=0.0)
    return {
        "n_recent":      n_recent,
        "overall_score": round(overall, 4),
        "overall_level": _level(overall, 0.35, 0.65),
        "baseline":      "training" if used_pipeline_baseline else "schema",
        "source":        "predictions",
        "features":      features,
    }


# ── Per-field processors ──────────────────────────────────────────────────────

def _process_numeric(
    field: dict,
    name: str,
    rows: list[dict],
    n_recent: int,
    baseline: dict,
    mode: str,
) -> dict:
    # Reference stats
    if name in baseline:
        ref_mean = baseline[name]["mean"]
        ref_std  = baseline[name]["std"]
    else:
        fmin     = float(field.get("min", 0))
        fmax     = float(field.get("max", 1))
        ref_mean = (fmin + fmax) / 2
        ref_std  = max((fmax - fmin) / 6, 1e-9)

    # Actual values + null tracking
    vals = [
        float(r[name])
        for r in rows
        if name in r and r[name] is not None and _is_number(r[name])
    ]
    null_count = n_recent - len(vals)
    null_rate  = round(null_count / n_recent, 4) if n_recent else 0.0

    if vals:
        r_mean = float(np.mean(vals))
        r_std  = float(np.std(vals)) if len(vals) > 1 else 0.0
        z            = abs(r_mean - ref_mean) / ref_std
        drift_score  = round(min(1.0, z / 3), 4)
        psi_val      = _psi_numeric(vals, ref_mean, ref_std)
        histogram    = _histogram(vals, ref_mean, ref_std)
        ks_stat = ks_pval = None
        if mode == "upload" and len(vals) >= 5:
            ks_stat, ks_pval = _ks_test(vals, ref_mean, ref_std)
    else:
        r_mean = r_std = None
        drift_score = psi_val = 0.0
        histogram   = None
        ks_stat = ks_pval = None

    feat: dict = {
        "name":        name,
        "label":       field.get("label", name),
        "type":        "numeric",
        "ref_mean":    round(ref_mean, 4),
        "ref_std":     round(ref_std, 4),
        "recent_mean": round(r_mean, 4) if r_mean is not None else None,
        "recent_std":  round(r_std, 4)  if r_std  is not None else None,
        "drift_score": drift_score,
        "drift_level": _level(drift_score, 0.35, 0.65),
        "psi":         round(psi_val, 4),
        "psi_level":   _psi_level(psi_val),
        "null_rate":   null_rate,
        "n_recent":    len(vals),
    }
    if ks_stat is not None:
        feat["ks_stat"]   = round(float(ks_stat), 4)
        feat["ks_pvalue"] = round(float(ks_pval), 4)
    if histogram:
        feat["histogram"] = histogram
    return feat


def _process_categorical(
    field: dict,
    name: str,
    rows: list[dict],
    n_recent: int,
) -> dict:
    opts   = [str(o["value"]) for o in field.get("options", [])]
    n_opts = len(opts)
    if not opts:
        return {}

    # Reference distribution — actual training frequencies preferred
    cat_freq = field.get("cat_freq")
    if cat_freq:
        raw   = {str(k): float(v) for k, v in cat_freq.items()}
        total = sum(raw.get(o, 0.0) for o in opts) or 1.0
        ref_dist = {o: raw.get(o, 0.0) / total for o in opts}
        cat_baseline = "training"
    else:
        ref_p    = 1.0 / n_opts
        ref_dist = {o: ref_p for o in opts}
        cat_baseline = "uniform"

    # Actual distribution + null tracking
    vals = [
        str(r[name]) for r in rows
        if name in r and r[name] is not None and str(r[name]).strip()
    ]
    null_count = n_recent - len(vals)
    null_rate  = round(null_count / n_recent, 4) if n_recent else 0.0

    if vals:
        n_vals  = len(vals)
        r_dist  = {o: vals.count(o) / n_vals for o in opts}
        drift_score = round(
            sum(abs(r_dist[o] - ref_dist[o]) for o in opts) / n_opts, 4
        )
        psi_val = _psi_categorical(r_dist, ref_dist, opts)
    else:
        r_dist      = {o: 0.0 for o in opts}
        drift_score = 0.0
        psi_val     = 0.0

    return {
        "name":         name,
        "label":        field.get("label", name),
        "type":         "categorical",
        "options":      opts,
        "ref_dist":     {o: round(ref_dist[o], 4) for o in opts},
        "recent_dist":  {o: round(r_dist.get(o, 0.0), 4) for o in opts},
        "drift_score":  drift_score,
        "drift_level":  _level(drift_score, 0.15, 0.30),
        "psi":          round(psi_val, 4),
        "psi_level":    _psi_level(psi_val),
        "null_rate":    null_rate,
        "n_recent":     len(vals),
        "cat_baseline": cat_baseline,
    }


# ── Statistical functions ─────────────────────────────────────────────────────

def _norm_cdf(x: float, mean: float, std: float) -> float:
    """Standard normal CDF using math.erf (no scipy required for this)."""
    return 0.5 * (1.0 + math.erf((x - mean) / (std * math.sqrt(2.0))))


def _psi_numeric(vals: list, ref_mean: float, ref_std: float, n_bins: int = 10) -> float:
    """PSI for numeric fields: bin actual data vs N(mean,std) reference."""
    if not vals or ref_std <= 0:
        return 0.0
    lo    = ref_mean - 3.0 * ref_std
    hi    = ref_mean + 3.0 * ref_std
    edges = np.linspace(lo, hi, n_bins + 1)

    # Reference fractions from N(mean, std)
    ref_fracs = np.array([
        _norm_cdf(float(edges[i + 1]), ref_mean, ref_std) -
        _norm_cdf(float(edges[i]),     ref_mean, ref_std)
        for i in range(n_bins)
    ])
    ref_fracs = np.clip(ref_fracs, 1e-6, None)
    ref_fracs /= ref_fracs.sum()

    # Actual fractions — values outside [lo, hi] go into edge bins
    clipped = np.clip(vals, lo + 1e-12, hi - 1e-12)
    actual_counts, _ = np.histogram(clipped, bins=edges)
    actual_fracs = actual_counts / max(actual_counts.sum(), 1)
    actual_fracs = np.where(actual_fracs == 0, 1e-6, actual_fracs)
    actual_fracs /= actual_fracs.sum()

    psi = float(np.sum((actual_fracs - ref_fracs) * np.log(actual_fracs / ref_fracs)))
    return max(0.0, round(psi, 6))


def _psi_categorical(r_dist: dict, ref_dist: dict, opts: list) -> float:
    """PSI for categorical fields."""
    psi = 0.0
    for o in opts:
        a = max(r_dist.get(o, 0.0), 1e-6)
        e = max(ref_dist.get(o, 0.0), 1e-6)
        psi += (a - e) * math.log(a / e)
    return max(0.0, round(psi, 6))


def _ks_test(vals: list, ref_mean: float, ref_std: float):
    """Two-sample KS test: actual vals vs synthetic N(mean,std) reference.

    Generates a synthetic reference sample and uses the asymptotic KS statistic.
    Returns (ks_stat, approx_p_value).
    """
    try:
        rng         = np.random.default_rng(42)
        n_ref       = min(2000, max(len(vals) * 10, 500))
        ref_samples = rng.normal(ref_mean, ref_std, size=n_ref)

        s1 = np.sort(vals)
        s2 = np.sort(ref_samples)
        n1, n2 = len(s1), len(s2)

        # Two-sample KS statistic via merged CDF comparison
        all_x = np.concatenate([s1, s2])
        all_x.sort()
        cdf1 = np.searchsorted(s1, all_x, side="right") / n1
        cdf2 = np.searchsorted(s2, all_x, side="right") / n2
        ks   = float(np.max(np.abs(cdf1 - cdf2)))

        # Asymptotic p-value approximation
        n_eff  = math.sqrt(n1 * n2 / (n1 + n2))
        t      = (n_eff + 0.12 + 0.11 / n_eff) * ks
        pvalue = float(2.0 * math.exp(-2.0 * t * t))
        pvalue = max(0.0, min(1.0, pvalue))

        return ks, pvalue
    except Exception:
        return None, None


def _histogram(
    vals: list,
    ref_mean: float,
    ref_std: float,
    n_bins: int = 12,
) -> list | None:
    """Histogram bin data for frontend overlay chart.

    Returns list of {lo, hi, ref_h, actual_h} with heights normalised to [0, 1].
    ref_h uses N(mean, std); actual_h uses empirical distribution of vals.
    """
    if not vals or ref_std <= 0:
        return None
    try:
        lo = min(float(np.min(vals)), ref_mean - 2.5 * ref_std)
        hi = max(float(np.max(vals)), ref_mean + 2.5 * ref_std)
        if lo >= hi:
            return None

        edges = np.linspace(lo, hi, n_bins + 1)

        ref_fracs = np.array([
            _norm_cdf(float(edges[i + 1]), ref_mean, ref_std) -
            _norm_cdf(float(edges[i]),     ref_mean, ref_std)
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
    except Exception:
        return None


# ── Small helpers ─────────────────────────────────────────────────────────────

def _is_number(v) -> bool:
    try:
        f = float(v)
        return not math.isnan(f) and not math.isinf(f)
    except (TypeError, ValueError):
        return False


def _level(score: float, med: float, high: float) -> str:
    if score >= high:
        return "high"
    if score >= med:
        return "medium"
    return "low"


def _psi_level(psi: float) -> str:
    if psi >= 0.25:
        return "high"
    if psi >= 0.10:
        return "medium"
    return "low"
