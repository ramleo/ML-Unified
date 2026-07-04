"""In-memory rolling buffers, history snapshots, and persistence helpers."""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque

_DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_BUFFER_FILE  = os.path.join(_DATA_DIR, "drift_buffer.json")
_HISTORY_FILE = os.path.join(_DATA_DIR, "drift_history.json")
_HISTORY_MAX  = 100
_TREND_WINDOW = 20

_recent:          dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
_history:         dict[str, list]  = defaultdict(list)


def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def load_all() -> None:
    try:
        with open(_BUFFER_FILE) as f:
            raw = json.load(f)
        for mid, rows in raw.items():
            d: deque = deque(maxlen=200)
            d.extend(rows)
            _recent[mid] = d
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    try:
        with open(_HISTORY_FILE) as f:
            raw = json.load(f)
        for mid, snaps in raw.items():
            _history[mid] = snaps[-_HISTORY_MAX:]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass


def save_buffer() -> None:
    try:
        _ensure_data_dir()
        with open(_BUFFER_FILE, "w") as f:
            json.dump({mid: list(d) for mid, d in _recent.items()}, f)
    except OSError:
        pass


def save_history() -> None:
    try:
        _ensure_data_dir()
        with open(_HISTORY_FILE, "w") as f:
            json.dump(dict(_history), f)
    except OSError:
        pass


def record_input(model_id: str, fields: dict) -> None:
    """Log a raw prediction input for the rolling drift buffer."""
    _recent[model_id].append(fields)
    save_buffer()


def record_snapshot(model_id: str, result: dict, label: str | None = None) -> None:
    snap: dict = {
        "ts":            int(time.time()),
        "overall_score": result["overall_score"],
        "overall_level": result["overall_level"],
        "n_recent":      result["n_recent"],
        "source":        result.get("source", "predictions"),
        "features": [
            {
                "name":        f["name"],
                "label":       f.get("label", f["name"]),
                "drift_score": f["drift_score"],
                "drift_level": f["drift_level"],
                "psi":         f.get("psi", 0.0),
            }
            for f in result.get("features", [])
        ],
    }
    if label:
        snap["label"] = label
    _history[model_id].append(snap)
    if len(_history[model_id]) > _HISTORY_MAX:
        _history[model_id] = _history[model_id][-_HISTORY_MAX:]
    save_history()


def get_recent(model_id: str) -> list:
    return list(_recent[model_id])


def get_trend(model_id: str) -> list:
    return list(_history.get(model_id, []))[-_TREND_WINDOW:]


def get_history(model_id: str) -> list:
    return list(_history.get(model_id, []))


# Load persisted state once at import time
load_all()
