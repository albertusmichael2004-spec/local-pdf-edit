from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.core.config import settings
from backend.core.paths import frontend_root


FRONTEND_DIR = frontend_root()

app = FastAPI(
    title=settings.app_name,
    version="4.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)
app.include_router(api_router)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "pages" / "main" / "index.html")
