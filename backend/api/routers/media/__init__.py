from __future__ import annotations

from fastapi import APIRouter

from .jobs import router as jobs_router
from .probe import router as probe_router


router = APIRouter(tags=["media-compressor-converter"])
router.include_router(probe_router)
router.include_router(jobs_router)
