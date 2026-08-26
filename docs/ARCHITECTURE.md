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

The four main product families are explicit folders under `backend/services/`, and each user-facing subfeature owns a focused Python module.

```text
backend/services/
├── edit_pdf/
├── convert_to_pdf/
├── convert_from_pdf/
└── pdf_security/
```

`quick_tools/` keeps Merge and Split separate from those four product families. `shared/` contains mechanics used by multiple features, such as PDF preview rendering, external office/OCR engines, compression internals, and comparison internals.

The Edit PDF family now includes two feature-specific support modules in addition to the eight primary feature files:

- `watermark_fonts.py` resolves popular installed fonts and user-uploaded custom fonts.
- `add_watermark.py` supports multiple staged watermark rules in one final export.

Persistent user data lives under `data/`. Custom watermark font binaries are created at runtime in `data/fonts/` and are ignored by Git.

## API organization

FastAPI concerns stay under `backend/api/`. Edit-PDF routing is further split so page operations, compression, OCR, transforms, and watermark persistence/export do not collapse back into a single long router file.

The PDF preview endpoint returns page thumbnails plus page dimensions. The frontend can therefore render page grids lazily and synchronize visual crop margins with real PDF measurements.

## Frontend organization

The application shell and navigation live in `frontend/pages/main/`. Every feature UI lives in `frontend/feature_views/<family>/<feature>/` with its own `panel.html` and `controller.js`. Panels are lazy-loaded when first opened.

Reusable browser behavior lives in `frontend/assets/js/core/`. Important shared modules include:

- `page_workspace.js`: lazy-loading scrollable page grids, page selection, drag reordering, blank-page insertion, and page-card actions.
- `crop_box.js`: interactive crop rectangle and margin synchronization.
- `dropzones.js`: drag/drop upload behavior and replace/remove controls.
- `previews.js`: local PDF metadata and thumbnail requests.

This prevents Organize, Rotate, Watermark, and Crop from each reimplementing page-grid mechanics.

## Why not more abstraction?

There is deliberately no repository pattern, generic `PDFManager` class, React build pipeline, or database service. Those would add indirection without solving a current problem. The target is small cohesive modules, predictable data flow, and shared helpers only where duplication actually exists.
