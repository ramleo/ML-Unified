"""Load an uploaded model file without running code from it (OPEN_ISSUES E18).

`/shap/custom/upload` used to `joblib.load` whatever was uploaded. joblib is
pickle underneath, and a pickle runs arbitrary code the instant it loads, so
one uploaded file was remote code execution on the Space — every API key and
the HF token in its environment. Proven locally with a crafted file.

skops stores an sklearn model as data plus a type manifest and never executes
it. `get_untrusted_types` lists every type the file wants to reconstruct; we
load only when all of them sit under known ML libraries, so a file naming
`posix.system` or `builtins.eval` is refused before anything is built.

The site's own models (export_model, now skops too) load cleanly — a plain
sklearn Pipeline reports no untrusted types at all.
"""
from __future__ import annotations

import skops.io as sio

# Types outside skops's own trusted core are allowed only from these modules.
# sklearn/numpy/scipy cover the pipelines; xgboost/lightgbm the two boosters
# the site trains. No `builtins`, `os`, `posix`, `subprocess`, etc.
_ALLOWED_PREFIXES = ("sklearn.", "numpy.", "scipy.", "xgboost.", "lightgbm.")


class UnsafeModelFile(ValueError):
    pass


def load_model(raw: bytes):
    """Return the model from skops bytes, or raise UnsafeModelFile."""
    try:
        untrusted = sio.get_untrusted_types(data=raw)
    except Exception as exc:  # not a skops file at all (e.g. a .pkl)
        raise UnsafeModelFile(
            "Upload a .skops model file. Plain pickle/joblib files are not "
            "accepted because they can run code when opened."
        ) from exc

    blocked = [t for t in untrusted if not t.startswith(_ALLOWED_PREFIXES)]
    if blocked:
        raise UnsafeModelFile(
            "This model file contains types that are not allowed: "
            + ", ".join(sorted(blocked)[:8])
        )
    try:
        return sio.loads(raw, trusted=untrusted)
    except Exception as exc:
        raise UnsafeModelFile(f"Could not read the model file: {exc}") from exc
