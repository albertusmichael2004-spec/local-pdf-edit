# Local PDF Workbench v4.1

A local-first PDF desktop workbench built with Python, FastAPI, a Chromium app shell, and a modular HTML/CSS/JavaScript frontend. Documents are processed on the local computer; the application does not require a cloud conversion API.

The working tree may also contain a native Kotlin/Jetpack Compose Android
application under [`apps/android`](apps/android). Platform code stays isolated
so Android dependencies never leak into the Python desktop runtime; `apps/`
and `training/` are development-only and excluded from release commits.

## Copyright and Usage

Copyright © 2026 Albertus Michael. All rights reserved.

This repository is publicly available for viewing, educational reference, and portfolio purposes. Unless explicitly permitted in writing, no permission is granted to copy, modify, redistribute, sublicense, sell, commercially exploit, or incorporate substantial portions of this project's original source code into another product or service.

Third-party libraries, frameworks, and external software used by this project remain subject to their respective licenses and terms.

## Main product families

### Media Tools

- Media Converter: content-based type detection and capability-aware target dropdowns for image, video, audio, PDF, and ebook files
- Media Compressor: image/video/audio quality presets with keep-original or compatible target formats
- Multiple outputs are packaged as ZIP64; one output downloads directly

### Edit PDF

- Remove Pages
- Extract Pages
- Organize PDF
- Compress PDF
- OCR PDF
- Rotate PDF
- Add Watermark
- Crop PDF

### Convert to PDF

- JPG to PDF
- Word to PDF
- PowerPoint to PDF
- Excel to PDF
- HTML to PDF

### Convert from PDF

- PDF to JPG
- PDF to Word
- PDF to PowerPoint
- PDF to Excel

### PDF Security

- Unlock PDF
- Protect PDF
- SHA-256 PDF
- Compare SHA-256
- Compare PDF

### Document Security

- All in One: password + 7z + AES-256 with encrypted headers
- SHA-256 File: generate an integrity fingerprint for any uploaded file type
- Decrypt File / Archive: password-protected ZIP and 7z
- Password Protect File: WinZip AES-256 ZIP
- Create 7z Archive
- AES-256 Encrypt: encrypted 7z

Merge and Split remain available as Quick Tools.

## Processing progress and large files

Every upload-based operation now reports its active stage, elapsed time, estimated remaining time when measurable, and feature-specific progress such as page X of Y, file X of Y, or the current encryption/OCR stage. The existing final status text remains `Done. Output is ready.`

Uploads have no application-defined size cap. File staging and SHA-256 use large streaming chunks, hashing reads directly from FastAPI's upload spool, CPU/blocking engines run outside the API event loop, and downloads for very large inputs stream through the browser instead of buffering the entire output in JavaScript memory. Runtime still depends on storage throughput, page count, codecs, OCR complexity, installed engines, and CPU/GPU performance; a fixed one- or three-minute deadline cannot be guaranteed for every 10 GB workload.


## v4.1 visual edit workflow updates

- Organize PDF now uses a fixed-height lazy-loading page grid with drag reorder, blank-page insertion, per-page rotate, and delete controls.
- Rotate PDF now has All/Custom page modes, visual page selection, and left/right rotation buttons.
- Watermark now supports staged rules, per-page checkbox selection, visual previews, common fonts, persistent custom font upload, and one final export.
- Crop PDF now includes a draggable/resizable visual crop rectangle synchronized with millimeter margins.
- Compression now tolerates older supported PyMuPDF save signatures in an existing venv instead of failing the whole operation.
- See `README.txt` for a detailed file-by-file architecture guide.

## Project structure

```text
pdf_workbench/
├── backend/
│   ├── api/
│   ├── core/
│   ├── services/
│   │   ├── edit_pdf/
│   │   ├── convert_to_pdf/
│   │   ├── convert_from_pdf/
│   │   ├── pdf_security/
│   │   ├── document_security/
│   │   ├── media/
│   │   ├── quick_tools/
│   │   └── shared/
│   └── utils/
├── frontend/
│   ├── pages/main/
│   ├── feature_views/
│   └── assets/
├── scripts/
├── tests/
├── docs/
├── distribution/windows/
├── apps/                 # development-only Android project; ignored by Git
├── training/             # development-only OCR training; ignored by Git
├── Start Local PDF Workbench.cmd
├── desktop.py
├── run.py
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

See `docs/ARCHITECTURE.md` for the design rationale.

## Windows source setup and runtime layout

Target project folder:

```text
C:\Users\<username>\Projects\pdf_workbench
```

The working checkout keeps one local `.venv` for development. It is ignored by
Git and is never required by the portable release. The `apps/` Android project
and `training/` OCR experiments are also development-only folders and are
intentionally excluded from release commits.

Recommended migration:

1. Close Local PDF Workbench and VS Code terminals that are running it.
2. Back up the current project folder once.
3. Keep this folder untouched:

```text
.venv\
```

4. Keep generated folders (`build\`, `dist\`, `release\`, `tmp\`) out of Git. If an old checkout contains duplicate environments, retain only one usable `.venv`.
5. Copy the contents of this `pdf_workbench` folder into the permanent project folder.
6. Verify the existing environment:

```powershell
cd "C:\Users\<username>\Projects\pdf_workbench"
.\.venv\Scripts\python.exe .\scripts\check_system.py
```

7. Install/refresh the desktop launcher (this is also safe for an existing `.venv`):

```powershell
.\scripts\setup_windows.ps1
```

8. Double-click `Start Local PDF Workbench.cmd`, or run the source launcher from PowerShell:

```powershell
Start-Process ".\.venv\Scripts\pythonw.exe" -ArgumentList "-I","-m","desktop" -WorkingDirectory (Get-Location)
```

The launcher opens a dedicated Chromium app window with normal user
permissions. This avoids WebView2 data-directory failures and .NET
message-pump hangs that can mark `pythonw.exe` as “Not responding”. The local
API and native file operations remain on `127.0.0.1`; no document is uploaded
to the internet.

Or recreate the Desktop shortcut:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\create_desktop_shortcut.ps1
```

The launcher is installed in editable mode and points back to this source tree,
so saved source changes are picked up the next time the app starts. It first
validates the source environment and falls back to
`release\LocalPDFWorkbench\LocalPDFWorkbench.exe` when the source runtime is
unavailable. No PyInstaller rebuild is required for source development.

The desktop shell requires an installed Google Chrome or Microsoft Edge. File
and folder pickers use native Windows PowerShell/.NET dialogs, so they do not
depend on Tcl/Tk being present in the Python or PyInstaller runtime.

## Existing `.venv` and package installation

The media pipeline adds `pillow-heif`, `CairoSVG`, `mutagen`, `psutil`, and
`EbookLib`. A healthy existing `.venv` can be reused. The setup script checks
it before installation and warns if it uses a managed runtime; the portable
build remains self-contained.

To reuse it without reinstalling packages:

```powershell
.\scripts\setup_windows.ps1
```

The setup script only installs requirements automatically when `.venv` does not exist. To intentionally refresh dependencies:

```powershell
.\scripts\setup_windows.ps1 -InstallDependencies
```

## External local engines

Some features depend on Windows applications rather than Python packages:

- **Ghostscript** → Compress PDF
- **Tesseract OCR** → OCR PDF
- **LibreOffice** → optional higher-fidelity Office-to-PDF conversion; required for legacy `.doc`, `.ppt`, `.xls`
- **FFmpeg + ffprobe** → video/audio detection, conversion, and compression
- **Calibre ebook-convert** → EPUB/PDF ebook conversion

The UI only offers formats supported by the engines currently installed. MIDI synthesis and true bitmap-to-vector tracing remain optional, separate pipelines and are not advertised as normal audio/image conversions.

Check status with:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_system.py
```

## Browser/development server mode

```powershell
.\.venv\Scripts\python.exe .\run.py
```

Then open `http://127.0.0.1:8000`.

## Tests

Install dev requirements only if `pytest` is not already present:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Portable application for another Windows computer

A separate **portable onedir build** is supported under `distribution/windows/`. This is for sharing the application with a computer that does not have VS Code or Python.

If PyInstaller is not already installed in the development `.venv`, install the build-only dependency once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\distribution\windows\requirements-build.txt
```

Build:

```powershell
.\.venv\Scripts\python.exe .\distribution\build_or_update.py
```

This single launcher installs missing build-only packages when needed, detects whether it is creating or updating the portable app, rebuilds it, and refreshes `release\LocalPDFWorkbench`. The lower-level `distribution\windows\build_portable.ps1` remains available for manual builds.

The result is:

```text
release\LocalPDFWorkbench\
├── LocalPDFWorkbench.exe
└── _internal\...
```

Share the **whole folder**, not only the EXE. The receiving computer does not
need Python or VS Code. Ghostscript and Tesseract remain external requirements
for Compression/OCR; FFprobe, Calibre, and LibreOffice are optional engines
for their respective features.

## OCR training (development-only)

The `training/` tree is intentionally ignored by Git and is not included in
the desktop release. After preparing both training and validation datasets,
run:

```powershell
.\.venv\Scripts\python.exe .\training\run_training.py
```

The launcher resumes the newest unfinished checkpoint. If no unfinished checkpoint exists, it starts a new training run.

## Privacy

The FastAPI server binds to `127.0.0.1`. Uploaded files have no application-imposed size limit and stream to local temporary workspaces; practical capacity still depends on disk space, memory, filesystem, and processing-engine limits. Temporary workspaces are scheduled for cleanup after responses are delivered. No cloud API is required by this project.
