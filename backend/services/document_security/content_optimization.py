from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.config import settings
from backend.core.errors import MediaProcessingError, PDFWorkbenchError


@dataclass(frozen=True)
class ContentOptimizationResult:
    path: Path
    applied: bool
    original_bytes: int
    output_bytes: int
    note: str


def prepare_balanced_content(
    source_path: Path,
    workdir: Path,
    display_name: str | None = None,
) -> ContentOptimizationResult:
    """Create a moderate-quality, same-format candidate when that is meaningful."""
    source = Path(source_path).resolve()
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    original_bytes = source.stat().st_size
    name = Path(display_name or source.name).name
    suffix = Path(name).suffix.lower()
    candidate = workdir / f"balanced_content{suffix or '.bin'}"

    try:
        if _is_pdf(source):
            from backend.services.edit_pdf.compress_pdf import compress_preset

            compress_preset(
                source,
                candidate.with_suffix(".pdf"),
                "recommended",
                settings.ghostscript_timeout_seconds,
            )
            candidate = candidate.with_suffix(".pdf")
            method = "Balanced PDF optimization (150 DPI image floor, JPEG quality 74)"
        else:
            candidate, method = _prepare_media(source, candidate)
    except (PDFWorkbenchError, OSError, ValueError) as exc:
        candidate.unlink(missing_ok=True)
        return ContentOptimizationResult(
            source,
            False,
            original_bytes,
            original_bytes,
            f"Balanced reduction was unavailable for this file; encrypted the original unchanged. {exc}",
        )

    if not candidate.is_file() or candidate.stat().st_size <= 0:
        candidate.unlink(missing_ok=True)
        return ContentOptimizationResult(
            source,
            False,
            original_bytes,
            original_bytes,
            "Balanced reduction produced no usable output; encrypted the original unchanged.",
        )

    output_bytes = candidate.stat().st_size
    if output_bytes >= original_bytes:
        candidate.unlink(missing_ok=True)
        return ContentOptimizationResult(
            source,
            False,
            original_bytes,
            original_bytes,
            "Balanced reduction would not make this file smaller; encrypted the original unchanged.",
        )

    reduction = (1 - output_bytes / original_bytes) * 100 if original_bytes else 0.0
    return ContentOptimizationResult(
        candidate,
        True,
        original_bytes,
        output_bytes,
        f"{method} reduced the protected content by {reduction:.1f}% before encryption.",
    )


def _is_pdf(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(5) == b"%PDF-"


def _prepare_media(source: Path, candidate: Path) -> tuple[Path, str]:
    from backend.services.media.capabilities import targets_for
    from backend.services.media.models import JobOptions
    from backend.services.media.planner import JobPlanner
    from backend.services.media.probe import probe_media

    probe = probe_media(source)
    if probe.kind not in {"image", "video", "audio"}:
        raise MediaProcessingError(
            "Balanced quality reduction is available for PDF, image, video, and audio files."
        )
    if probe.format == "svg":
        raise MediaProcessingError("Vector SVG files are kept unchanged to preserve their structure.")

    planner = JobPlanner()
    options = planner.normalize(
        source,
        probe,
        JobOptions("compressed", "keep", "balanced", False),
    )
    supported = {str(item["format"]) for item in targets_for(probe)}
    if options.target_format not in supported:
        raise MediaProcessingError(
            f"Balanced same-format compression is unavailable for {options.target_format.upper()}."
        )
    output = candidate.with_suffix(f".{options.target_format}")
    planner.engine_for(probe).process(source, output, probe, options)
    labels = {
        "image": "Balanced image optimization (quality 78)",
        "video": "Balanced video optimization (CRF 24 where supported)",
        "audio": "Balanced audio optimization (192 kbps where supported)",
    }
    return output, labels[probe.kind]
