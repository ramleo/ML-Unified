"""Exploratory data analysis — profile, clean, and suggest.

Folded in from the standalone services/ml-eda on 2026-09-12. That service
was deployed and healthy and had never been called by anything on the site;
its /eda endpoint returned 500 for a large class of ordinary CSVs. Its own
35 tests passed throughout, because none of them covered the shape that
broke it.
"""
from .router import router
from ._suggest import router as suggest_router

__all__ = ["router", "suggest_router"]
