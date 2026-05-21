# api/routers/manju/__init__.py
# -*- coding: utf-8 -*-
"""Re-export router so that `from api.routers import manju; manju.router` works."""

from fastapi import APIRouter

from .routes import router as _routes_router
from .history import router as _history_router

router = APIRouter()
router.include_router(_routes_router)
router.include_router(_history_router)
