"""
Testwright — the QA Automation platform, mounted at /qa.

Self-contained package: everything QA lives under routers/qa/, and the only
reach into the rest of ML-Unified is routers/qa/deps.py. Adding a stage (run,
discover, heal) = a new sub-module + one include_router line below.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/qa")


def _mount() -> None:
    # Imported inside the function so `import routers.qa.config` (used by
    # models.py at import time) resolves before the sub-routers load.
    from routers.qa import author, run, discover, heal
    router.include_router(author.router)
    router.include_router(run.router)
    router.include_router(discover.router)
    router.include_router(heal.router)


_mount()
