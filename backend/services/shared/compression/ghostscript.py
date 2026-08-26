from __future__ import annotations

from pathlib import Path
import subprocess

from backend.core.errors import CompressionError
from backend.core.executables import find_ghostscript
from backend.core.subprocesses import run_hidden
from backend.services.shared.compression.models import CompressionProfile


def profile_from_strength(strength: float) -> CompressionProfile:
    """Map 0.0 (high quality) to 1.0 (strong compression)."""
    strength = min(1.0, max(0.0, strength))
    dpi = round(300 - (240 * strength))
    jpeg_quality = round(92 - (57 * strength))
    mono_dpi = max(150, round(dpi * 2))
    return CompressionProfile(dpi=dpi, jpeg_quality=jpeg_quality, mono_dpi=mono_dpi)


def run_ghostscript(
    input_path: Path,
    output_path: Path,
    profile: CompressionProfile,
    timeout_seconds: int,
) -> None:
    executable = find_ghostscript()
    if not executable:
        raise CompressionError(
            "Ghostscript was not found. Install Ghostscript and restart the app, "
            "or set GHOSTSCRIPT_PATH to the executable."
        )

    command = [
        executable,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dSAFER",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dEmbedAllFonts=true",
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        f"-dColorImageResolution={profile.dpi}",
        "-dColorImageDownsampleThreshold=1.0",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        f"-dGrayImageResolution={profile.dpi}",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dAutoFilterGrayImages=false",
        "-dGrayImageFilter=/DCTEncode",
        "-dDownsampleMonoImages=true",
        "-dMonoImageDownsampleType=/Subsample",
        f"-dMonoImageResolution={profile.mono_dpi}",
        f"-dJPEGQ={profile.jpeg_quality}",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]
    try:
        completed = run_hidden(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CompressionError(
            f"Ghostscript exceeded the {timeout_seconds}s processing timeout."
        ) from exc
    except OSError as exc:
        raise CompressionError(f"Ghostscript could not be started: {exc}") from exc

    if completed.returncode != 0 or not output_path.exists():
        stderr = (completed.stderr or completed.stdout or "Unknown Ghostscript error").strip()
        raise CompressionError(f"Ghostscript compression failed: {stderr[-1200:]}")
