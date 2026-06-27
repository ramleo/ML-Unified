"""Pipeline Builder router package."""
from fastapi import APIRouter

from .stages import router as _stages_router
from .automl_stage import router as _automl_router
from .export import router as _export_router
from .comparison import router as _comparison_router

router = APIRouter(prefix="/pipeline-builder", tags=["pipeline-builder"])
router.include_router(_stages_router)
router.include_router(_automl_router)
router.include_router(_export_router)
router.include_router(_comparison_router)
