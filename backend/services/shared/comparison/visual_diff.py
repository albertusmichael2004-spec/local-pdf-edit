from __future__ import annotations

from io import BytesIO

import fitz
from PIL import Image, ImageChops, ImageEnhance

def pad_to_same_size(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    width = max(a.width, b.width)
    height = max(a.height, b.height)

    def pad(image: Image.Image) -> Image.Image:
        if image.size == (width, height):
            return image
        canvas = Image.new("RGB", (width, height), "white")
        canvas.paste(image, (0, 0))
        return canvas

    return pad(a), pad(b)

def render_diff(lp, rp, scale: float) -> tuple[float, bool, bytes | None]:
    limg = Image.open(BytesIO(lp.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png"))).convert("RGB")
    rimg = Image.open(BytesIO(rp.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png"))).convert("RGB")
    limg, rimg = pad_to_same_size(limg, rimg)
    diff = ImageChops.difference(limg, rimg).convert("L")
    histogram = diff.histogram()
    total_pixels = limg.width * limg.height
    changed = total_pixels - histogram[0]
    pixel_difference = changed / max(1, total_pixels)
    visually_identical = pixel_difference < 0.00005
    payload = None
    if not visually_identical:
        enhanced = ImageEnhance.Contrast(diff).enhance(4.0).convert("RGB")
        buf = BytesIO()
        enhanced.save(buf, format="PNG", optimize=True)
        payload = buf.getvalue()
    limg.close(); rimg.close(); diff.close()
    return round(pixel_difference, 7), visually_identical, payload
