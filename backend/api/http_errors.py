from __future__ import annotations

from fastapi import HTTPException


def bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def dependency_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))
