from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from backend.core.errors import MediaProcessingError
from .base import MediaEngine
from ..models import JobOptions, MediaProbeResult


FORMATS = {"jpg": "JPEG", "png": "PNG", "bmp": "BMP", "tiff": "TIFF", "webp": "WEBP", "gif": "GIF", "heic": "HEIF"}
QUALITY = {
    "high": 90,
    "less": 88,
    "balanced": 78,
    "recommended": 72,
    "smallest": 60,
    "extreme": 32,
}


class ImageEngine(MediaEngine):
    def process(self, source: Path, output: Path, probe: MediaProbeResult, options: JobOptions) -> tuple[str, ...]:
        self._register_heif()
        raster_source = self._raster_source(source, probe, output.parent)
        if options.target_format == "svg":
            self._wrap_svg(raster_source, output)
            return ("SVG output embeds the bitmap; it is not true vector tracing.",)
        try:
            with Image.open(raster_source) as image:
                frames = [ImageOps.exif_transpose(frame.copy()) for frame in ImageSequence.Iterator(image)]
                frame_count = len(frames)
                if options.operation == "compressed" and options.quality == "extreme":
                    frames = [self._extreme_resize(frame) for frame in frames]
                self._save(frames, image.info, output, options)
        except MediaProcessingError:
            raise
        except Exception as exc:
            raise MediaProcessingError(f"Image processing failed for {source.name}: {exc}") from exc
        if not output.exists() or not output.stat().st_size:
            raise MediaProcessingError(f"Image engine created no usable output for {source.name}.")
        if options.target_format == "pdf" and frame_count > 1:
            return ("Only the first frame was used so one uploaded image creates one PDF page.",)
        return ()

    def _save(self, frames: list[Image.Image], info: dict, output: Path, options: JobOptions) -> None:
        target = options.target_format
        if target == "pdf":
            frames[0].convert("RGB").save(output, "PDF")
            return
        if target not in FORMATS:
            raise MediaProcessingError(f"Unsupported image target: {target}.")
        prepared = [self._compatible(frame, target) for frame in frames]
        save_options = self._save_options(target, options, info)
        animated = len(prepared) > 1 and target in {"gif", "webp", "tiff"}
        prepared[0].save(output, FORMATS[target], save_all=animated, append_images=prepared[1:] if animated else [], **save_options)

    def _save_options(self, target: str, options: JobOptions, info: dict) -> dict:
        result: dict[str, object] = {}
        if target in {"jpg", "webp", "heic"}:
            result.update(quality=QUALITY.get(options.quality, 78), optimize=True)
        elif target == "png":
            result.update(optimize=True, compress_level={"high": 6, "balanced": 8, "smallest": 9}.get(options.quality, 8))
        if options.keep_metadata:
            for key in ("exif", "icc_profile"):
                if info.get(key):
                    result[key] = info[key]
        return result

    @staticmethod
    def _compatible(image: Image.Image, target: str) -> Image.Image:
        if target in {"jpg", "bmp"} and image.mode not in {"RGB", "L"}:
            background = Image.new("RGB", image.size, "white")
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            return background
        return image

    @staticmethod
    def _extreme_resize(image: Image.Image) -> Image.Image:
        width = max(1, round(image.width * 0.55))
        height = max(1, round(image.height * 0.55))
        if (width, height) == image.size:
            return image
        return image.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def _register_heif() -> None:
        if importlib.util.find_spec("pillow_heif"):
            from pillow_heif import register_heif_opener
            register_heif_opener()

    @staticmethod
    def _raster_source(source: Path, probe: MediaProbeResult, workdir: Path) -> Path:
        if probe.format != "svg":
            return source
        if not importlib.util.find_spec("cairosvg"):
            raise MediaProcessingError("CairoSVG is required to convert SVG input.")
        import cairosvg
        rendered = workdir / f"_{source.stem}_rendered.png"
        cairosvg.svg2png(url=str(source), write_to=str(rendered))
        return rendered

    @staticmethod
    def _wrap_svg(source: Path, output: Path) -> None:
        with Image.open(source) as image:
            width, height = image.size
            from io import BytesIO
            buffer = BytesIO()
            image.save(buffer, "PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        output.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><image width="100%" height="100%" href="data:image/png;base64,{encoded}"/></svg>',
            encoding="utf-8",
        )
