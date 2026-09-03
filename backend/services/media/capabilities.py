from __future__ import annotations

from functools import lru_cache
import importlib.util

from PIL import features

from backend.core.executables import find_ebook_convert, find_ffmpeg, find_ffprobe
from backend.core.subprocesses import run_hidden
from .models import MediaProbeResult


VIDEO_TARGETS = ("mp4", "mov", "avi", "mkv", "webm", "wmv", "flv")
AUDIO_TARGETS = ("wav", "flac", "mp3", "ogg", "aac", "wma", "aiff", "m4a", "mpa")
IMAGE_TARGETS = ("jpg", "png", "bmp", "tiff", "webp", "gif", "pdf", "heic", "svg")
VIDEO_ENCODERS = {"mp4": ("libx264", "aac"), "mov": ("libx264", "aac"), "avi": ("mpeg4", "libmp3lame"), "mkv": ("libx264", "aac"), "webm": ("libvpx-vp9", "libopus"), "wmv": ("wmv2", "wmav2"), "flv": ("flv", "aac")}
AUDIO_ENCODERS = {"wav": ("pcm_s16le",), "flac": ("flac",), "mp3": ("libmp3lame",), "ogg": ("libvorbis",), "aac": ("aac",), "wma": ("wmav2",), "aiff": ("pcm_s16be",), "m4a": ("aac",), "mpa": ("mp2",)}


@lru_cache(maxsize=1)
def installed_tools() -> dict[str, bool]:
    return {
        "ffmpeg": bool(find_ffmpeg()),
        "ffprobe": bool(find_ffprobe() or find_ffmpeg()),
        "calibre": bool(find_ebook_convert()),
        "pillow_heif": bool(importlib.util.find_spec("pillow_heif")),
        "cairosvg": bool(importlib.util.find_spec("cairosvg")),
    }


def targets_for(probe: MediaProbeResult) -> list[dict[str, object]]:
    tools = installed_tools()
    if probe.kind == "video" and tools["ffmpeg"]:
        return _rank(ffmpeg_targets("video"), "mp4")
    if probe.kind == "audio" and tools["ffmpeg"]:
        return _rank(ffmpeg_targets("audio"), "mp3")
    if probe.kind == "image":
        targets = [target for target in IMAGE_TARGETS if _image_target_available(target, tools)]
        recommended = "png" if probe.details.get("alpha") else "jpg"
        return _rank(targets, recommended)
    if probe.kind == "ebook" and tools["calibre"]:
        return _rank(("pdf", "epub"), "pdf" if probe.kind == "ebook" else "epub")
    if probe.kind == "pdf":
        targets = ["docx", "pptx", "xlsx"] + (["epub"] if tools["calibre"] else [])
        return _rank(targets, "docx")
    return []


def _image_target_available(target: str, tools: dict[str, bool]) -> bool:
    if target == "heic":
        return tools["pillow_heif"]
    if target == "webp":
        return features.check("webp")
    return True


def _rank(targets, recommended: str) -> list[dict[str, object]]:
    return [{"format": item, "recommended": item == recommended} for item in targets]


@lru_cache(maxsize=2)
def ffmpeg_targets(kind: str) -> tuple[str, ...]:
    executable = find_ffmpeg()
    if not executable:
        return ()
    result = run_hidden([executable, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30, shell=False)
    if result.returncode:
        return ()
    listing = result.stdout or ""
    matrix = VIDEO_ENCODERS if kind == "video" else AUDIO_ENCODERS
    return tuple(target for target, encoders in matrix.items() if all(encoder in listing for encoder in encoders))


def capability_payload() -> dict[str, object]:
    tools = installed_tools()
    return {
        "tools": tools,
        "targets": {
            "video": list(ffmpeg_targets("video")) if tools["ffprobe"] else [],
            "audio": list(ffmpeg_targets("audio")) if tools["ffprobe"] else [],
            "image": [item for item in IMAGE_TARGETS if _image_target_available(item, tools)],
            "ebook": ["pdf", "epub"] if tools["calibre"] else [],
            "pdf": ["docx", "pptx", "xlsx"] + (["epub"] if tools["calibre"] else []),
        },
        "constraints": "No app-imposed total-size limit; processing depends on disk space, system resources, and installed codecs/tools.",
    }
