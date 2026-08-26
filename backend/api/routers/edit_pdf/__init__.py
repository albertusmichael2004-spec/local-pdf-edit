from __future__ import annotations

from fastapi import APIRouter

from . import compress, ocr, pages, transforms, watermark


router = APIRouter(prefix="/edit")
router.include_router(pages.router)
router.include_router(compress.router)
router.include_router(ocr.router)
router.include_router(transforms.router)
router.include_router(watermark.router)
