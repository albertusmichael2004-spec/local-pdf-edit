from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.api.progress_middleware import progress_middleware
from backend.core.config import settings
from backend.core.paths import frontend_root
from backend.core.version import APP_VERSION
from backend.services.workflow_session import workflow_store


FRONTEND_DIR = frontend_root()


@asynccontextmanager
async def lifespan(_: FastAPI):
    workflow_store.cleanup_expired()
    try:
        yield
    finally:
        workflow_store.cleanup_all()


app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.include_router(api_router)
app.middleware("http")(progress_middleware)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "pages" / "main" / "index.html")
