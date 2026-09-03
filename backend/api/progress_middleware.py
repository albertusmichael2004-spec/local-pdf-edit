from __future__ import annotations

from starlette.requests import Request

from backend.core.progress import bind_progress, registry, reset_progress


OPERATION_NAMES = {
    "merge": "Merging PDF files", "split": "Splitting PDF", "compress": "Compressing PDF",
    "ocr": "Running OCR", "remove-pages": "Removing pages", "extract-pages": "Extracting pages",
    "organize": "Organizing pages", "rotate": "Rotating pages", "crop": "Cropping pages",
    "watermark": "Applying watermarks", "jpg-to-pdf": "Building PDF from images",
    "image-ocr-export": "Recognizing image text", "pdf-to-jpg": "Rendering PDF pages",
    "pdf-to-word": "Converting PDF to Word", "pdf-to-powerpoint": "Building PowerPoint slides",
    "pdf-to-excel": "Extracting PDF tables", "word-to-pdf": "Converting Word to PDF",
    "powerpoint-to-pdf": "Converting PowerPoint to PDF", "excel-to-pdf": "Converting Excel to PDF",
    "html-to-pdf": "Rendering HTML to PDF", "sha256": "Calculating SHA-256",
    "sha256-compare": "Comparing SHA-256", "compare-pdf-summary": "Comparing PDF pages",
    "compare-pdf": "Building PDF comparison", "unlock": "Unlocking PDF",
    "protect": "Protecting PDF", "all-in-one": "Securing file with AES-256",
    "password-protect": "Creating protected ZIP", "create-7z": "Creating 7z archive",
    "aes256": "Encrypting with AES-256", "decrypt": "Decrypting archive",
    "media": "Processing media", "images": "Processing images", "video": "Converting video",
    "audio": "Converting audio", "ebook": "Converting ebook",
}


def operation_name(path: str) -> str:
    key = path.rstrip("/").rsplit("/", 1)[-1]
    return OPERATION_NAMES.get(key, "Processing file")


async def progress_middleware(request: Request, call_next):
    job_id = request.headers.get("x-progress-id") or request.query_params.get("progress_id")
    if not job_id or request.method not in {"POST", "PUT"}:
        return await call_next(request)
    registry.start(job_id, operation_name(request.url.path))
    token = bind_progress(job_id)
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            registry.update(job_id, stage="Processing failed", status="error")
        else:
            registry.update(job_id, stage="Output ready", percent=100, status="complete")
        response.headers["X-Progress-ID"] = job_id
        return response
    except Exception as exc:
        registry.update(job_id, stage="Processing failed", detail=str(exc), status="error")
        raise
    finally:
        reset_progress(token)
