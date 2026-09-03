from __future__ import annotations

from pathlib import Path

from backend.core.config import settings
from backend.core.errors import MediaProcessingError
from backend.core.executables import find_ffmpeg
from backend.core.progress import report_progress
from backend.core.subprocesses import run_hidden
from .base import MediaEngine
from ..models import JobOptions, MediaProbeResult


VIDEO_CODECS = {
    "mp4": ("libx264", "aac"), "mov": ("libx264", "aac"), "avi": ("mpeg4", "libmp3lame"),
    "mkv": ("libx264", "aac"), "webm": ("libvpx-vp9", "libopus"), "wmv": ("wmv2", "wmav2"), "flv": ("flv", "aac"),
}
AUDIO_CODECS = {
    "wav": "pcm_s16le", "flac": "flac", "mp3": "libmp3lame", "ogg": "libvorbis", "aac": "aac",
    "wma": "wmav2", "aiff": "pcm_s16be", "m4a": "aac", "mpa": "mp2",
}
VIDEO_CRF = {
    "high": "20", "less": "22", "balanced": "24", "recommended": "28",
    "smallest": "30", "extreme": "36",
}
AUDIO_BITRATE = {
    "high": "256k", "less": "192k", "balanced": "192k", "recommended": "128k",
    "smallest": "96k", "extreme": "48k",
}


def build_ffmpeg_command(executable: str, source: Path, output: Path, probe: MediaProbeResult, options: JobOptions) -> list[str]:
    target = options.target_format
    command = [executable, "-nostdin", "-y", "-i", str(source)]
    if probe.kind == "video":
        if target not in VIDEO_CODECS:
            raise MediaProcessingError(f"Unsupported video target: {target}.")
        video, audio = VIDEO_CODECS[target]
        command += ["-map", "0:v:0", "-map", "0:a?", "-c:v", video, "-c:a", audio]
        command += ["-crf", VIDEO_CRF.get(options.quality, "24")] if video.startswith("libx") else []
        if options.quality == "extreme" and int(probe.details.get("height") or 0) > 720:
            command += ["-vf", "scale=-2:720"]
        if target in {"mp4", "mov", "m4a"}:
            command += ["-movflags", "+faststart"]
    else:
        if target not in AUDIO_CODECS:
            raise MediaProcessingError(f"Unsupported audio target: {target}.")
        command += ["-vn", "-c:a", AUDIO_CODECS[target]]
        if target not in {"wav", "flac", "aiff"}:
            command += ["-b:a", AUDIO_BITRATE.get(options.quality, "192k")]
    if not options.keep_metadata:
        command += ["-map_metadata", "-1"]
    return command + [str(output)]


class FFmpegEngine(MediaEngine):
    def process(self, source: Path, output: Path, probe: MediaProbeResult, options: JobOptions) -> tuple[str, ...]:
        executable = find_ffmpeg()
        if not executable:
            raise MediaProcessingError("FFmpeg is required for video/audio processing. Install it and restart the app.")
        report_progress("FFmpeg is processing media", percent=38, detail=source.name)
        result = run_hidden(
            build_ffmpeg_command(executable, source, output, probe, options),
            capture_output=True, text=True, timeout=settings.media_timeout_seconds, shell=False,
        )
        if result.returncode or not output.exists() or not output.stat().st_size:
            detail = (result.stderr or "FFmpeg created no usable output.")[-1200:]
            raise MediaProcessingError(f"FFmpeg failed for {source.name}: {detail}")
        report_progress("Finalizing media output", percent=90, detail=output.name)
        return ()
