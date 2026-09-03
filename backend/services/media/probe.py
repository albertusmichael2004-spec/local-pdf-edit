from __future__ import annotations

import json
from pathlib import Path
import re
import zipfile

from PIL import Image

from backend.core.errors import MediaProcessingError
from backend.core.executables import find_ffmpeg, find_ffprobe
from backend.core.subprocesses import run_hidden
from .models import MediaProbeResult


MIME_BY_KIND = {"image": "image/*", "audio": "audio/*", "video": "video/*", "ebook": "application/epub+zip", "pdf": "application/pdf"}


def _head(path: Path, size: int = 4096) -> bytes:
    with path.open("rb") as stream:
        return stream.read(size)


def _probe_image(path: Path) -> MediaProbeResult | None:
    if b"<svg" in _head(path).lstrip().lower():
        return MediaProbeResult("image", "svg", "image/svg+xml", path.stat().st_size, {"vector": True})
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            details = {"width": image.width, "height": image.height, "frames": getattr(image, "n_frames", 1), "alpha": "A" in image.getbands()}
            return MediaProbeResult("image", (image.format or "").lower(), Image.MIME.get(image.format, "image/*"), path.stat().st_size, details)
    except Exception:
        return None


def _probe_document(path: Path) -> MediaProbeResult | None:
    if _head(path, 5) == b"%PDF-":
        return MediaProbeResult("pdf", "pdf", "application/pdf", path.stat().st_size)
    try:
        with zipfile.ZipFile(path) as archive:
            marker = archive.read("mimetype").decode("ascii", "ignore").strip()
            if marker == "application/epub+zip":
                return MediaProbeResult("ebook", "epub", marker, path.stat().st_size)
    except Exception:
        return None
    return None


def _duration_seconds(value: str) -> float | None:
    match = re.match(r"(\d+):(\d+):(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)


def _probe_with_ffmpeg(path: Path, executable: str) -> MediaProbeResult:
    result = run_hidden(
        [executable, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        shell=False,
    )
    output = result.stderr or result.stdout or ""
    stream_lines = re.findall(r"^\s*Stream #.+$", output, flags=re.MULTILINE)
    video_lines = [line for line in stream_lines if "Video:" in line]
    audio_lines = [line for line in stream_lines if "Audio:" in line]
    if not video_lines and not audio_lines:
        raise MediaProcessingError("The file is not a readable supported image, ebook, video, or audio file.")
    kind = "video" if video_lines else "audio"
    input_match = re.search(r"Input #\d+,\s*([^,\n]+)", output)
    duration_match = re.search(r"Duration:\s*([^,]+)", output)
    dimensions = re.search(r"(\d{2,5})x(\d{2,5})", video_lines[0]) if video_lines else None
    codecs = []
    for line in stream_lines:
        codec = re.search(r"(?:Video|Audio):\s*([^,\s]+)", line)
        if codec:
            codecs.append(codec.group(1))
    details: dict[str, object] = {
        "duration": _duration_seconds(duration_match.group(1).strip()) if duration_match else None,
        "codecs": codecs,
        "streams": len(stream_lines),
        "probe_engine": "ffmpeg",
    }
    if dimensions:
        details.update(width=int(dimensions.group(1)), height=int(dimensions.group(2)))
    return MediaProbeResult(
        kind,
        input_match.group(1).strip().split(",")[0] if input_match else path.suffix.lstrip(".").lower(),
        MIME_BY_KIND[kind],
        path.stat().st_size,
        details,
    )


def _probe_av(path: Path) -> MediaProbeResult:
    executable = find_ffprobe()
    if not executable:
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            return _probe_with_ffmpeg(path, ffmpeg)
        raise MediaProcessingError(
            "The bundled FFmpeg engine is unavailable. Reinstall or rebuild the app with media dependencies."
        )
    command = [executable, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]
    result = run_hidden(command, capture_output=True, text=True, timeout=60, shell=False)
    if result.returncode:
        raise MediaProcessingError("The file is not a readable supported image, ebook, video, or audio file.")
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    kind = "video" if any(item.get("codec_type") == "video" for item in streams) else "audio"
    container = str(payload.get("format", {}).get("format_name", "unknown")).split(",")[0]
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    details = {
        "duration": payload.get("format", {}).get("duration"),
        "codecs": [item.get("codec_name") for item in streams],
        "streams": len(streams),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "probe_engine": "ffprobe",
    }
    return MediaProbeResult(kind, container, MIME_BY_KIND[kind], path.stat().st_size, details)


def probe_media(path: Path) -> MediaProbeResult:
    return _probe_image(path) or _probe_document(path) or _probe_av(path)
