# Changelog

## [4.1.3] - 2026-09-09

### en
- Backend reliability and workflow improvements.
- User interface and document workflow improvements.
- Installer, update, and distribution improvements.
- Regression coverage and validation updates.
- Documentation and project guidance updates.

### id
- Peningkatan keandalan backend dan alur kerja.
- Peningkatan antarmuka dan alur kerja dokumen.
- Peningkatan installer, pembaruan, dan distribusi.
- Peningkatan pengujian regresi dan validasi.
- Pembaruan dokumentasi dan panduan proyek.
## [4.1.2] - 2026-09-09

### en
- Backend reliability and workflow improvements.
- User interface and document workflow improvements.
- Installer, update, and distribution improvements.
- Regression coverage and validation updates.
- Documentation and project guidance updates.

### id
- Peningkatan keandalan backend dan alur kerja.
- Peningkatan antarmuka dan alur kerja dokumen.
- Peningkatan installer, pembaruan, dan distribusi.
- Peningkatan pengujian regresi dan validasi.
- Pembaruan dokumentasi dan panduan proyek.
## [4.1.1] - 2026-09-09
### en
- Organize PDF now uses a fixed-height lazy-loading page grid with drag reorder, blank-page insertion, per-page rotate, and delete controls.
- Rotate PDF now has All/Custom page modes, visual page selection, and left/right rotation buttons.
- Watermark now supports staged rules, per-page checkbox selection, visual previews, common fonts, persistent custom font upload, and one final export.
- Crop PDF now includes a draggable/resizable visual crop rectangle synchronized with millimeter margins.
- Compression now tolerates older supported PyMuPDF save signatures in an existing virtual environment.
- Added the Windows installer, incremental update flow, and startup update check.

### id
- Atur PDF kini menggunakan kisi halaman lazy-loading dengan tinggi tetap, drag reorder, penyisipan halaman kosong, rotasi per halaman, dan kontrol hapus.
- Putar PDF kini memiliki mode Semua/Khusus, pemilihan halaman visual, dan tombol rotasi kiri/kanan.
- Watermark kini mendukung aturan bertahap, pilihan checkbox per halaman, preview visual, font umum, upload font khusus persisten, dan satu ekspor final.
- Potong PDF kini memiliki kotak crop visual yang dapat digeser/diubah ukurannya dan tersinkron dengan margin milimeter.
- Kompresi kini tetap kompatibel dengan signature PyMuPDF lama yang didukung pada virtual environment yang sudah ada.
- Menambahkan installer Windows, alur update inkremental, dan pemeriksaan update saat startup.

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
