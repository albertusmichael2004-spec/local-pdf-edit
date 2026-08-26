# Changelog

## v4.1

- Added scrollable lazy-loaded page workspace for Organize PDF.
- Added visual drag reorder, blank-page insertion, per-page rotation, and deletion to Organize PDF.
- Reworked Rotate PDF to All/Custom selection with page thumbnails and left/right controls.
- Reworked Watermark into staged multi-rule editing with page checkboxes, previews, common fonts, persistent custom font upload, and final export.
- Added interactive visual Crop PDF box with drag handles and synchronized millimeter margins.
- Added page-size metadata to PDF previews.
- Fixed a recursive `run_hidden()` subprocess bug that could break Ghostscript compression, OCR, and LibreOffice operations.
- Hardened compression compatibility for older supported PyMuPDF versions and child-process startup failures.
- Added detailed README.txt architecture documentation.

## v4.0.0 — SOLID/DRY/KISS architecture refactor

- Reorganized the project into explicit `frontend/` and `backend/` roots.
- Split the backend's four main product families into service folders with one Python module per requested subfeature.
- Preserved Merge and Split as `quick_tools` rather than forcing them into an unrelated main family.
- Split large conversion, comparison, compression, and editing internals into cohesive reusable modules.
- Replaced the single large API route file with domain routers and a shared request-workspace abstraction.
- Replaced the single large frontend script with ES modules and lazy-loaded feature panels/controllers.
- Split the monolithic stylesheet into base/layout/component/feature styles.
- Simplified the live-source desktop launcher while keeping FastAPI bound to localhost.
- Reduced root-level setup/build clutter; canonical helper scripts now live under `scripts/`.
- Restored a Windows portable `onedir` distribution workflow under `distribution/windows/`.
- Runtime `requirements.txt` is unchanged from v3, so an existing compatible `.venv` can be reused.
