from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from threading import RLock
import time


@dataclass
class ProgressState:
    job_id: str
    operation: str
    stage: str
    percent: float | None
    detail: str
    completed: int | None
    total: int | None
    started_at: float
    updated_at: float
    status: str = "running"


class ProgressRegistry:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._items: dict[str, ProgressState] = {}
        self._lock = RLock()
        self._ttl = ttl_seconds

    def start(self, job_id: str, operation: str) -> ProgressState:
        now = time.time()
        state = ProgressState(job_id, operation, "Receiving request", 1, "", None, None, now, now)
        with self._lock:
            self._purge(now)
            self._items[job_id] = state
        return state

    def update(self, job_id: str, **changes) -> None:
        with self._lock:
            state = self._items.get(job_id)
            if not state:
                return
            for key, value in changes.items():
                if value is not None and hasattr(state, key):
                    setattr(state, key, value)
            state.updated_at = time.time()

    def snapshot(self, job_id: str) -> dict | None:
        with self._lock:
            state = self._items.get(job_id)
            if not state:
                return None
            data = asdict(state)
        data["elapsed_seconds"] = max(0, time.time() - state.started_at)
        return data

    def _purge(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if now - item.updated_at > self._ttl]
        for key in expired:
            self._items.pop(key, None)


registry = ProgressRegistry()
_current_job: ContextVar[str | None] = ContextVar("pdf_workbench_progress", default=None)


def bind_progress(job_id: str) -> Token:
    return _current_job.set(job_id)


def reset_progress(token: Token) -> None:
    _current_job.reset(token)


def report_progress(
    stage: str,
    *,
    percent: float | None = None,
    completed: int | None = None,
    total: int | None = None,
    detail: str = "",
    status: str = "running",
) -> None:
    job_id = _current_job.get()
    if not job_id:
        return
    if percent is not None:
        percent = min(100.0, max(0.0, float(percent)))
    registry.update(
        job_id,
        stage=stage,
        percent=percent,
        completed=completed,
        total=total,
        detail=detail,
        status=status,
    )


def report_fraction(stage: str, completed: int, total: int, start: float, end: float) -> None:
    ratio = completed / total if total else 0
    report_progress(
        stage,
        percent=start + ((end - start) * ratio),
        completed=completed,
        total=total,
        detail=f"{completed:,} of {total:,}",
    )
