from __future__ import annotations

import uvicorn

from backend.core.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=False,
    )
