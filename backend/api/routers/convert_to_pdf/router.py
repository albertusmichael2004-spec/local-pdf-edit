from __future__ import annotations

from fastapi import APIRouter

from .html import router as html_router
from .image import router as image_router
from .image_ocr import router as image_ocr_router
from .office import router as office_router


router = APIRouter(
    prefix="/convert",
    tags=["convert-to-pdf"],
)

router.include_router(image_router)
router.include_router(image_ocr_router)
router.include_router(office_router)
router.include_router(html_router)
