from __future__ import annotations

from fastapi import APIRouter

from backend.api.routers import (
    convert_from_pdf,
    convert_to_pdf,
    edit_pdf,
    pdf_security,
    quick_tools,
    system,
)

from backend.api.routers.convert_to_pdf import (
    router as convert_to_pdf_router,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(quick_tools.router)
api_router.include_router(edit_pdf.router)
api_router.include_router(convert_to_pdf.router)
api_router.include_router(convert_from_pdf.router)
api_router.include_router(pdf_security.router)
