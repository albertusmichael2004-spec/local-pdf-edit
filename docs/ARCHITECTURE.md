# Architecture

## Design goals

Local PDF Workbench applies SOLID, DRY, and KISS without introducing a frontend framework, dependency-injection container, database server, or microservice split that a localhost desktop utility does not need.

```text
PyWebView desktop shell
        ↓
Frontend (HTML/CSS/ES modules)
        ↓ localhost
FastAPI routers
        ↓
Feature service modules
        ↓
Shared PDF / executable infrastructure
```

## Backend organization

The main product families are explicit folders under `backend/services/`, and each user-facing subfeature owns a focused Python module.

```text
backend/services/
├── edit_pdf/
├── convert_to_pdf/
├── convert_from_pdf/
├── pdf_security/
├── document_security/
└── media/
```

`media/` is a shared facade for both compression and conversion. `probe.py` detects actual content, `capabilities.py` filters target formats against installed tools, `planner.py` chooses an adapter, `runner.py` bounds concurrency, and `output_manager.py` provides collision-safe names plus ZIP64 packaging. Image, FFmpeg, ebook, and existing-PDF adapters stay isolated under `media/engines/`.

`quick_tools/` keeps Merge and Split separate from those product families. `shared/` contains mechanics used by multiple features, such as PDF preview rendering, external office/OCR engines, compression internals, and comparison internals.

`document_security/archive_security.py` owns the reusable archive operations for arbitrary files. The API exposes focused endpoints for password-protected ZIP, plain 7z, and AES-256 encrypted 7z; the All in One route reuses the same encrypted-7z operation instead of duplicating cryptographic code. `archive_decryption.py` safely opens password-protected ZIP/7z containers with entry-count, expanded-size, special-file, and path-traversal guards.

`document_security/hash_file.py` exposes SHA-256 hashing for arbitrary file types. Both PDF Security and Document Security reuse the streaming primitive in `shared/file_hash.py`, so hashing behavior stays identical without coupling the generic feature to PDF validation.

The Edit PDF family includes focused support modules in addition to the primary feature files:

- `watermark_fonts.py` resolves popular installed fonts and user-uploaded custom fonts.
- `add_watermark.py` supports multiple staged watermark rules in one final export.
- `redact_pdf.py` resolves normalized visible-page rectangles, applies native PDF redactions, inserts optional secure appearance rasters, and verifies the sanitized output.

Persistent user data lives under `data/`. Custom watermark font binaries are created at runtime in `data/fonts/` and are ignored by Git.

## API organization

FastAPI concerns stay under `backend/api/`. Edit-PDF routing is further split so page operations, compression, OCR, transforms, and watermark persistence/export do not collapse back into a single long router file.

Media endpoints are split into probe/capability and job routers under `backend/api/routers/media/`. Uploads stream to a request workspace without a media-specific application size cap; physical disk, RAM, codec, timeout, and filesystem limits still apply.

The shared upload spooler applies no application-level size cap to any feature. Archive extraction retains a separately named expanded-output guard to limit zip-bomb impact; that guard does not restrict the uploaded archive size.

The PDF preview endpoint returns page thumbnails plus page dimensions. The frontend can therefore render page grids lazily and synchronize visual crop margins with real PDF measurements.

### Integrated Organize workflow

Organize PDF is the first feature backed by a short-lived `WorkflowSession`. Its uploaded source, merged source pool, organized derivatives, and optional compressed/protected derivatives are registered as `WorkflowArtifact` records in a private operating-system temp directory. The browser receives opaque workflow/artifact IDs; filesystem paths are never exposed.

The canonical Organize plan is `merge -> organize -> compress -> protect -> sha256`. The primary Organize dropzone accepts one or more PDFs; merge is inferred automatically when more than one source is present. Adding, removing, or reordering the source list reconciles the workflow source pool and rebuilds the page arrangement immediately. Unchanged source PDFs are retained by artifact ID instead of being uploaded again.

Merge is materialized before page arrangement so the visual editor can work against the definitive page pool. Every source page carries a stable page identity plus its original source-artifact, filename, and source-page lineage. Every output page carries a separate instance identity, so reorder, duplication, deletion, and blank-page insertion do not rely on drifting page numbers. The frontend maps that lineage to stable per-file colors; blank pages deliberately have no source color.

After execution, Redact, Split, Extract, Watermark, Crop, OCR, and Compare PDF can accept workflow artifacts without uploading the PDF again. A transferred artifact is used directly by the backend. Preview requests use the same reference, while a lightweight browser `File` placeholder keeps existing feature controllers and file metadata UI compatible.

### Integrated Redact workflow

Redact PDF reuses the workflow artifact store and multi-PDF source arrangement. Merge is inferred from the uploaded PDF list, while page-level reorder, rotate, remove, and blank-page insertion are optional and materialized before final marks are drawn. Marks are stored against stable page-instance IDs using normalized visible-page coordinates so browser zoom never changes the protected region.

The secure engine uses native PyMuPDF redaction annotations to remove intersecting text, image pixels, and vector graphics before applying black, white, blur, or pixelate appearance. Output is written as a full non-incremental save with garbage collection, then reopened to verify that no text-character center remains in a protected rectangle. OCR may run before redaction; compression, AES-256 protection, and SHA-256 run afterward. If an optional post-step fails, the last successful sanitized artifact remains downloadable and transferable.

Redact results can transfer to Watermark, Split, Extract, Crop, OCR, or Compare PDF. Compare receives both the pre-redaction artifact and sanitized artifact by opaque ID, so Original versus Redacted opens with both inputs detected automatically.

Workflow directories are deleted explicitly by Finish or workspace reset and expire after a two-hour inactivity TTL. Per-request workspaces retain their existing download-response cleanup lifecycle.

## Frontend organization

The application shell and navigation live in `frontend/pages/main/`. Every feature UI lives in `frontend/feature_views/<family>/<feature>/` with its own `panel.html` and `controller.js`. Panels are lazy-loaded when first opened.

Reusable browser behavior lives in `frontend/assets/js/core/`. Important shared modules include:

- `page_workspace.js`: lazy-loading scrollable page grids, page selection, drag reordering, blank-page insertion, and page-card actions.
- `drag_reorder.js`: pointer-based lifted-card drag behavior with live insertion markers and FLIP movement animation, shared by PDF pages, image pages, Merge/JPG lists, and media batches.
- `media_tool.js`: shared probe/dropdown/job behavior for the converter and compressor panels.
- `crop_box.js`: interactive crop rectangle and margin synchronization.
- `dropzones.js`: drag/drop upload behavior and replace/remove controls.
- `previews.js`: local PDF metadata and thumbnail requests.

This prevents Organize, Rotate, Watermark, and Crop from each reimplementing page-grid mechanics.

## Why not more abstraction?

There is deliberately no repository pattern, generic `PDFManager` class, React build pipeline, or database service. Those would add indirection without solving a current problem. The target is small cohesive modules, predictable data flow, and shared helpers only where duplication actually exists.
