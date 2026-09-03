from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.http_errors import bad_request
from backend.api.workspace import RequestWorkspace
from backend.core.errors import PDFWorkbenchError
from backend.services.quick_tools.merge_pdf import merge_pdfs
from backend.services.quick_tools.split_pdf import (
    groups_by_approx_size,
    split_pdf_to_zip,
    write_groups_as_one_pdf,
)
from backend.services.shared.pdf_reader import get_pdf_page_count
from backend.utils.page_ranges import groups_every_n_pages, parse_group_expression


router = APIRouter()


@router.post("/merge")
async def merge(files: Annotated[list[UploadFile], File(...)]) -> FileResponse:
    if len(files) < 2:
        raise bad_request(ValueError("Upload at least two PDFs to merge."))
    workspace = RequestWorkspace()
    try:
        input_paths: list[Path] = []
        for index, upload in enumerate(files, start=1):
            input_path, _, _ = await workspace.save_pdf(
                upload,
                fallback=f"document_{index}.pdf",
                prefix=f"{index:03d}_",
            )
            input_paths.append(input_path)
        output = workspace.output("merged.pdf")
        total_pages = await run_in_threadpool(merge_pdfs, input_paths, output)
        return workspace.download(
            output,
            "application/pdf",
            "merged.pdf",
            {"X-PDF-Pages": str(total_pages)},
        )
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise


@router.post("/split")
async def split(
    file: Annotated[UploadFile, File(...)],
    mode: Annotated[str, Form()] = "range",
    ranges: Annotated[str, Form()] = "1",
    every_n: Annotated[int, Form()] = 1,
    max_size_mb: Annotated[float, Form()] = 5.0,
    merge_ranges: Annotated[bool, Form()] = False,
) -> FileResponse:
    workspace = RequestWorkspace()
    try:
        input_path, filename, _ = await workspace.save_pdf(file)
        total_pages = get_pdf_page_count(input_path)
        oversized: list[int] = []

        if mode in {"range", "ranges"}:
            groups = parse_group_expression(ranges, total_pages)
            if merge_ranges:
                output = workspace.output(f"{Path(filename).stem}_extracted_ranges.pdf")
                count = await run_in_threadpool(write_groups_as_one_pdf, input_path, groups, output)
                return workspace.download(
                    output,
                    "application/pdf",
                    output.name,
                    {"X-Output-Pages": str(count), "X-Original-Pages": str(total_pages)},
                )
        elif mode in {"pages", "every_n", "individual"}:
            groups = groups_every_n_pages(total_pages, 1 if mode == "individual" else every_n)
        elif mode == "size":
            if max_size_mb <= 0:
                raise ValueError("Maximum part size must be greater than zero.")
            groups, oversized = await run_in_threadpool(
                groups_by_approx_size,
                input_path, int(max_size_mb * 1024 * 1024)
            )
        else:
            raise ValueError("Unknown split mode.")

        output_zip = workspace.output("split-pdf.zip")
        base_name = Path(filename).stem
        count = await run_in_threadpool(split_pdf_to_zip, input_path, groups, output_zip, base_name)
        headers = {
            "X-Split-Files": str(count),
            "X-Original-Pages": str(total_pages),
        }
        if oversized:
            headers["X-Oversized-Parts"] = ",".join(map(str, oversized))
        return workspace.download(
            output_zip,
            "application/zip",
            f"{base_name}_split.zip",
            headers,
        )
    except (ValueError, PDFWorkbenchError) as exc:
        workspace.cleanup_on_error()
        raise bad_request(exc) from exc
    except Exception:
        workspace.cleanup_on_error()
        raise
