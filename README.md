# Local PDF Workbench v4.1

A local-first PDF desktop workbench built with Python, FastAPI, PyWebView, and a modular HTML/CSS/JavaScript frontend. Documents are processed on the local computer; the application does not require a cloud conversion API.

## Copyright and Usage

Copyright © 2026 Albertus Michael. All rights reserved.

This repository is publicly available for viewing, educational reference, and portfolio purposes. Unless explicitly permitted in writing, no permission is granted to copy, modify, redistribute, sublicense, sell, commercially exploit, or incorporate substantial portions of this project's original source code into another product or service.

Third-party libraries, frameworks, and external software used by this project remain subject to their respective licenses and terms.

## Main product families

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

Merge and Split remain available as Quick Tools.


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
├── desktop.py
├── run.py
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

See `docs/ARCHITECTURE.md` for the design rationale.

## Replacing the old project while keeping the existing `.venv`

Target project folder:

```text
C:\Users\<username>\Projects\pdf_workbench
```

This source package intentionally **does not contain `.venv`** and the runtime `requirements.txt` has not been changed from the supplied v3 codebase.

Recommended migration:

1. Close Local PDF Workbench and VS Code terminals that are running it.
2. Back up the current project folder once.
3. Keep this folder untouched:

```text
.venv\
```

4. Remove obsolete old-source/build items such as the old `app\`, `build\`, `dist\`, old root build BAT files, and old PyInstaller spec if they are still present.
5. Copy the contents of this `pdf_workbench` folder into the permanent project folder.
6. Verify the existing environment:

```powershell
cd "C:\Users\<username>\Projects\pdf_workbench"
.\.venv\Scripts\python.exe .\scripts\check_system.py
```

7. Run the live-source desktop app:

```powershell
& ".\.venv\Scripts\pythonw.exe" ".\desktop.py"
```

Or recreate the Desktop shortcut:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\create_desktop_shortcut.ps1
```

The shortcut points back to `desktop.py`; saved source changes are picked up the next time the app starts. No PyInstaller rebuild is required for this development workflow.

## Existing `.venv` and package installation

Because runtime requirements are unchanged, a healthy old `.venv` should be reusable as-is.

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
.\distribution\windows\build_portable.ps1
```

The result is:

```text
release\LocalPDFWorkbench\
├── LocalPDFWorkbench.exe
└── _internal\...
```

Share the **whole folder**, not only the EXE. The receiving computer does not need Python or VS Code. Ghostscript/Tesseract remain external requirements for Compression/OCR respectively.

## Privacy

The FastAPI server binds to `127.0.0.1`. Uploaded documents are processed locally in temporary workspaces and scheduled for cleanup after responses are delivered. No cloud API is required by this project.
