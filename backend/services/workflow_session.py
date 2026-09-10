from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import tempfile
from threading import RLock
from uuid import uuid4

from backend.core.errors import WorkflowError
from backend.services.shared.pdf_reader import get_pdf_page_count


WORKFLOW_PREFIX = "pdf-workflow-"
DEFAULT_TTL_SECONDS = 2 * 60 * 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkflowArtifact:
    artifact_id: str
    path: Path
    media_type: str
    file_name: str
    page_count: int
    bytes: int
    parent_artifact_id: str | None
    source_operation: str
    created_at: datetime
    page_ids: list[str]
    page_sources: list[dict[str, object]]

    def public(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "media_type": self.media_type,
            "file_name": self.file_name,
            "page_count": self.page_count,
            "bytes": self.bytes,
            "parent_artifact_id": self.parent_artifact_id,
            "source_operation": self.source_operation,
            "created_at": self.created_at.isoformat(),
            "page_ids": list(self.page_ids),
            "page_sources": [dict(source) for source in self.page_sources],
        }


@dataclass
class WorkflowSession:
    workflow_id: str
    path: Path
    created_at: datetime
    last_access: datetime
    original_artifact_id: str | None = None
    current_artifact_id: str | None = None
    artifacts: dict[str, WorkflowArtifact] = field(default_factory=dict)
    staged_operation_plan: list[dict[str, object]] = field(default_factory=list)
    return_stack: list[dict[str, str]] = field(default_factory=list)


class WorkflowStore:
    """Own short-lived, localhost-only artifacts used across feature requests."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._sessions: dict[str, WorkflowSession] = {}
        self._lock = RLock()

    def create(self) -> WorkflowSession:
        self.cleanup_expired()
        workflow_id = f"w_{uuid4().hex}"
        path = Path(tempfile.mkdtemp(prefix=WORKFLOW_PREFIX))
        now = _utcnow()
        session = WorkflowSession(workflow_id, path, now, now)
        with self._lock:
            self._sessions[workflow_id] = session
        return session

    def get(self, workflow_id: str) -> WorkflowSession:
        self.cleanup_expired()
        with self._lock:
            session = self._sessions.get(workflow_id)
            if session is None:
                raise WorkflowError("This temporary workflow has expired or no longer exists.")
            session.last_access = _utcnow()
            return session

    def artifact(self, workflow_id: str, artifact_id: str) -> WorkflowArtifact:
        session = self.get(workflow_id)
        artifact = session.artifacts.get(artifact_id)
        if artifact is None or not artifact.path.is_file():
            raise WorkflowError("This temporary PDF artifact has expired or no longer exists.")
        return artifact

    def reserve_path(self, workflow_id: str, file_name: str) -> Path:
        session = self.get(workflow_id)
        suffix = Path(file_name).suffix or ".pdf"
        return session.path / f"pending_{uuid4().hex}{suffix}"

    def register_pdf(
        self,
        workflow_id: str,
        path: Path,
        file_name: str,
        source_operation: str,
        *,
        parent_artifact_id: str | None = None,
        page_ids: list[str] | None = None,
        page_sources: list[dict[str, object]] | None = None,
        page_count: int | None = None,
        make_original: bool = False,
    ) -> WorkflowArtifact:
        session = self.get(workflow_id)
        resolved_path = path.resolve()
        try:
            resolved_path.relative_to(session.path.resolve())
        except ValueError as exc:
            raise WorkflowError("Workflow artifacts must remain inside the local workflow directory.") from exc
        if not resolved_path.is_file():
            raise WorkflowError("The workflow output file was not created.")

        verified_page_count = int(page_count) if page_count is not None else get_pdf_page_count(resolved_path)
        artifact_id = f"a_{uuid4().hex}"
        stable_ids = list(page_ids or [])
        if not stable_ids:
            stable_ids = [f"p_{artifact_id}_{index + 1}" for index in range(verified_page_count)]
        if len(stable_ids) != verified_page_count or len(set(stable_ids)) != verified_page_count:
            raise WorkflowError("The PDF page identity map is invalid.")
        stable_sources = [dict(source) for source in (page_sources or [])]
        if not stable_sources:
            stable_sources = [
                {
                    "source_artifact_id": artifact_id,
                    "file_name": file_name,
                    "source_page": index + 1,
                }
                for index in range(verified_page_count)
            ]
        if len(stable_sources) != verified_page_count:
            raise WorkflowError("The PDF page source map is invalid.")

        artifact = WorkflowArtifact(
            artifact_id=artifact_id,
            path=resolved_path,
            media_type="application/pdf",
            file_name=file_name,
            page_count=verified_page_count,
            bytes=resolved_path.stat().st_size,
            parent_artifact_id=parent_artifact_id,
            source_operation=source_operation,
            created_at=_utcnow(),
            page_ids=stable_ids,
            page_sources=stable_sources,
        )
        with self._lock:
            session.artifacts[artifact_id] = artifact
            session.current_artifact_id = artifact_id
            session.last_access = _utcnow()
            if make_original or session.original_artifact_id is None:
                session.original_artifact_id = artifact_id
        return artifact

    def set_current(self, workflow_id: str, artifact_id: str) -> None:
        session = self.get(workflow_id)
        if artifact_id not in session.artifacts:
            raise WorkflowError("This temporary PDF artifact has expired or no longer exists.")
        with self._lock:
            session.current_artifact_id = artifact_id
            session.last_access = _utcnow()

    def set_operation_plan(
        self,
        workflow_id: str,
        operations: list[dict[str, object]],
    ) -> None:
        session = self.get(workflow_id)
        with self._lock:
            session.staged_operation_plan = list(operations)
            session.last_access = _utcnow()

    def push_return(self, workflow_id: str, feature_id: str, artifact_id: str) -> None:
        session = self.get(workflow_id)
        with self._lock:
            session.return_stack.append({"feature_id": feature_id, "artifact_id": artifact_id})
            session.last_access = _utcnow()

    def summary(self, workflow_id: str) -> dict[str, object]:
        session = self.get(workflow_id)
        return {
            "workflow_id": session.workflow_id,
            "created_at": session.created_at.isoformat(),
            "last_access": session.last_access.isoformat(),
            "expires_at": (session.last_access + timedelta(seconds=self.ttl_seconds)).isoformat(),
            "original_artifact_id": session.original_artifact_id,
            "current_artifact_id": session.current_artifact_id,
            "artifact_ids": list(session.artifacts),
            "staged_operation_plan": list(session.staged_operation_plan),
            "return_stack": list(session.return_stack),
        }

    def delete(self, workflow_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(workflow_id, None)
        if session is None:
            return False
        shutil.rmtree(session.path, ignore_errors=True)
        return not session.path.exists()

    def cleanup_expired(self) -> int:
        threshold = _utcnow() - timedelta(seconds=self.ttl_seconds)
        with self._lock:
            expired_ids = [
                workflow_id
                for workflow_id, session in self._sessions.items()
                if session.last_access < threshold
            ]
        removed = sum(1 for workflow_id in expired_ids if self.delete(workflow_id))

        # A previous app process may have exited before it could clear its in-memory index.
        temp_root = Path(tempfile.gettempdir())
        threshold_timestamp = threshold.timestamp()
        for path in temp_root.glob(f"{WORKFLOW_PREFIX}*"):
            if not path.is_dir():
                continue
            with self._lock:
                if any(session.path == path for session in self._sessions.values()):
                    continue
            try:
                if path.stat().st_mtime >= threshold_timestamp:
                    continue
            except OSError:
                continue
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                removed += 1
        return removed

    def cleanup_all(self) -> int:
        with self._lock:
            workflow_ids = list(self._sessions)
        return sum(1 for workflow_id in workflow_ids if self.delete(workflow_id))


workflow_store = WorkflowStore()
