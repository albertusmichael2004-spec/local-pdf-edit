LOCAL PDF WORKBENCH v4.1
========================

1. PROJECT OVERVIEW
-------------------
Local PDF Workbench is a local-first desktop PDF utility. It is designed to provide common PDF editing, conversion, compression, OCR, security, comparison, and file-management features without sending the user's documents to a cloud conversion service.

The application can run in two modes:

A. Live-source desktop mode
   - Uses the project source files directly.
   - Runs through Python/PyWebView.
   - Best for development and personal use.
   - Source-code changes are picked up the next time the application starts.

B. Portable Windows application mode
   - Built with PyInstaller using distribution/windows/build_portable.ps1.
   - Produces release/LocalPDFWorkbench/.
   - The whole output folder can be copied to another Windows computer.
   - The receiving computer does not need VS Code or Python.

The application binds its local FastAPI server to 127.0.0.1 and processes uploaded files in temporary local workspaces.


2. PROJECT GOALS
----------------
The main goals are:

- Keep document processing local and private.
- Provide a desktop-style user interface instead of requiring a public website.
- Keep the code modular and understandable using SOLID, DRY, and KISS principles.
- Separate frontend, backend, tests, scripts, documentation, and Windows distribution logic.
- Keep each major PDF feature in its own module.
- Make feature updates easy without rebuilding a standalone executable during development.
- Keep portable distribution available for users who do not have Python or VS Code.


2A. COPYRIGHT AND USAGE NOTICE
------------------------------

Copyright © 2026 Albertus Michael. All rights reserved.

This repository and its source code are made publicly available for viewing,
educational reference, and portfolio purposes.

Unless explicitly permitted in writing by the copyright holder, no permission
is granted to copy, reproduce, modify, redistribute, sublicense, sell,
commercially exploit, or incorporate substantial portions of this project's
original source code into another product or service.

Third-party libraries, frameworks, tools, and external software used by this
project remain subject to their respective licenses and terms.

The availability of this source code on a public GitHub repository does not,
by itself, grant a license to reuse or redistribute the project's original
source code.


3. HIGH-LEVEL ARCHITECTURE
--------------------------

Desktop shell (PyWebView)
        |
        v
Frontend HTML/CSS/JavaScript
        |
        | localhost HTTP requests
        v
FastAPI backend routers
        |
        v
Feature service modules
        |
        v
PDF libraries / local executable engines
        |
        v
Temporary local filesystem workspaces

The architecture intentionally avoids unnecessary frameworks, microservices, databases, or dependency-injection containers. The goal is to keep the application maintainable without overengineering it.


4. MAIN PRODUCT FAMILIES
------------------------

A. QUICK TOOLS
   - Merge PDF
   - Split PDF

B. EDIT PDF
   - Remove Pages
   - Extract Pages
   - Organize PDF
   - Compress PDF
   - OCR PDF
   - Rotate PDF
   - Add Watermark
   - Crop PDF

C. CONVERT TO PDF
   - JPG to PDF
   - Word to PDF
   - PowerPoint to PDF
   - Excel to PDF
   - HTML to PDF

D. CONVERT FROM PDF
   - PDF to JPG
   - PDF to Word
   - PDF to PowerPoint
   - PDF to Excel

E. PDF SECURITY
   - Unlock PDF
   - Protect PDF
   - SHA-256 PDF
   - Compare SHA-256
   - Compare PDF


5. IMPORTANT v4.1 EDIT-PDF UI FEATURES
---------------------------------------

ORGANIZE PDF
- A fixed-height scrollable page area prevents a large PDF from expanding the full application page.
- Page thumbnails are lazy-loaded as the user scrolls.
- Pages can be reordered through drag-and-drop.
- The existing text page-order input can still be used.
- Hovering a page shows:
  - Add blank page before.
  - Add blank page after.
  - Rotate page clockwise.
  - Delete page.
- The backend accepts a visual page-editor plan containing source pages, blank pages, and per-page rotation.

ROTATE PDF
- Page selection uses a dropdown:
  - All pages.
  - Custom pages.
- When All pages is selected, the page grid is hidden.
- When Custom pages is selected, a scrollable page grid appears.
- Users click page thumbnails to select them.
- Rotation direction uses Left and Right buttons instead of an angle dropdown.

ADD WATERMARK
- All pages mode shows page 1 as a preview sample.
- Custom pages mode shows a scrollable page grid with a checkbox on every page.
- A watermark can be staged for one set of pages, then another different watermark can be staged for another set of pages.
- The final Export PDF operation applies all staged watermark rules in one output PDF.
- Popular font options include Arial, Calibri, Times New Roman, Segoe UI, Georgia, Verdana, Trebuchet MS, Courier New, Montserrat, and Helvetica.
- Custom .ttf/.otf font files can be uploaded and saved locally.
- Uploaded custom fonts are stored in data/fonts/.
- No font files are bundled by this repository beyond the user's own runtime uploads.

CROP PDF
- Includes an interactive crop preview.
- A blue crop rectangle can be resized from edges/corners.
- The crop rectangle can also be moved.
- Left, Top, Right, and Bottom millimeter inputs stay synchronized with the visual crop box.
- All pages or custom selected pages can be cropped.

COMPRESS PDF
- Extreme, Recommended, Less, and Custom target-range modes remain available.
- The structural optimization stage includes backward-compatible PyMuPDF save fallbacks.
- This prevents older but supported existing virtual environments from failing only because a newer PyMuPDF save argument is unavailable.
- Ghostscript remains the primary lossy compression engine.
- The shared hidden-subprocess helper now correctly delegates to subprocess.run; this fixes the recursive child-process failure that could surface as a compressor/server error.


6. ROOT FOLDER STRUCTURE
------------------------

pdf_workbench/
|
|-- backend/
|-- frontend/
|-- data/
|-- distribution/
|-- docs/
|-- scripts/
|-- tests/
|
|-- desktop.py
|-- run.py
|-- requirements.txt
|-- requirements-dev.txt
|-- pyproject.toml
|-- README.md
|-- README.txt
|-- CHANGELOG.md
|-- LICENSE
|-- .gitignore


7. BACKEND FOLDER
-----------------
backend/ contains the Python application logic.

backend/
|-- api/
|-- core/
|-- services/
|-- utils/
|-- main.py

backend/main.py
- Creates the FastAPI application.
- Registers API routers.
- Mounts frontend static files.
- Serves the main desktop page.


7.1 backend/api/
----------------
Responsible for HTTP/API concerns.

backend/api/
|-- router.py
|-- workspace.py
|-- http_errors.py
|-- routers/

router.py
- Combines all feature routers under /api.

workspace.py
- Creates one temporary workspace for each request.
- Saves uploads locally.
- Produces output files.
- Schedules workspace cleanup after a download response.

http_errors.py
- Converts expected application errors into clear HTTP responses.

routers/
- Contains endpoint modules grouped by product family.

routers/edit_pdf/
- pages.py: remove, extract, organize page endpoints.
- compress.py: PDF compression endpoint.
- ocr.py: OCR endpoint.
- transforms.py: rotate and crop endpoints.
- watermark.py: watermark export, font listing, and custom font upload endpoints.


7.2 backend/core/
-----------------
Contains application-wide infrastructure and configuration.

Typical files:
- config.py: runtime settings and limits.
- paths.py: project, frontend, icon, and persistent data paths.
- executables.py: finds Ghostscript, Tesseract, and LibreOffice.
- subprocesses.py: runs external Windows CLI programs without showing console windows.
- errors.py: application exception types.

persistent_data_root() in paths.py creates a writable data directory.
In source mode it is the project's data/ directory.
In portable mode it is beside LocalPDFWorkbench.exe.


7.3 backend/services/
---------------------
Contains actual PDF business logic. Each requested feature owns a dedicated Python file.

backend/services/edit_pdf/
|-- remove_pages.py
|-- extract_pages.py
|-- organize_pdf.py
|-- compress_pdf.py
|-- ocr_pdf.py
|-- rotate_pdf.py
|-- add_watermark.py
|-- watermark_fonts.py
|-- crop_pdf.py

remove_pages.py
- Removes selected pages.

extract_pages.py
- Extracts selected pages to a new PDF.

organize_pdf.py
- Supports simple page ordering.
- Supports visual organization plans with reordered pages, blank pages, and rotations.

compress_pdf.py
- Coordinates compression presets and custom target-size compression.

ocr_pdf.py
- Converts pages to images and builds a searchable OCR PDF.

rotate_pdf.py
- Rotates selected pages.

add_watermark.py
- Applies one or multiple watermark rules.

watermark_fonts.py
- Resolves common installed Windows fonts.
- Resolves built-in PDF font fallbacks.
- Resolves custom uploaded fonts from data/fonts/.

crop_pdf.py
- Applies crop margins to selected pages.


backend/services/convert_to_pdf/
|-- jpg_to_pdf.py
|-- word_to_pdf.py
|-- powerpoint_to_pdf.py
|-- excel_to_pdf.py
|-- html_to_pdf.py

Each file handles only the named conversion direction.


backend/services/convert_from_pdf/
|-- pdf_to_jpg.py
|-- pdf_to_word.py
|-- pdf_to_powerpoint.py
|-- pdf_to_excel.py

Each file handles only the named export format.


backend/services/pdf_security/
|-- unlock_pdf.py
|-- protect_pdf.py
|-- sha256_pdf.py
|-- compare_sha256.py
|-- compare_pdf.py

unlock_pdf.py
- Removes PDF password protection when the correct password is supplied.

protect_pdf.py
- Creates a password-protected PDF.

sha256_pdf.py
- Generates SHA-256 hashes.

compare_sha256.py
- Compares two SHA-256 values/files.

compare_pdf.py
- Coordinates deeper PDF comparison.


backend/services/quick_tools/
|-- merge_pdf.py
|-- split_pdf.py

These are separated from the four main product families because Merge and Split are cross-cutting quick tools.


backend/services/shared/
Contains reusable internal mechanics used by multiple features.

Important areas include:
- pdf_reader.py: shared safe PDF reader.
- preview.py: PDF thumbnail rendering and page-size metadata.
- office.py: LibreOffice integration.
- tesseract.py: Tesseract OCR integration.
- compression/: Ghostscript and compression internals.
- comparison/: text/visual comparison internals.
- renderers/: fallback document renderers.

Shared code belongs here only when more than one feature benefits from it.


7.4 backend/utils/
------------------
Small stateless utilities.

Examples:
- file_uploads.py: safe file naming and upload streaming.
- page_ranges.py: parse page selections and ranges.


8. FRONTEND FOLDER
------------------
frontend/ contains all HTML, CSS, JavaScript, and app image assets.

frontend/
|-- pages/
|-- feature_views/
|-- assets/


8.1 frontend/pages/main/
------------------------
Contains the main application shell.

- index.html: sidebar, navigation, workspace shell, and feature host.
- app_shell.js: initializes navigation, drag/drop protection, health checks, and initial feature loading.

The main shell does not contain all feature HTML. Features are lazy-loaded when opened.


8.2 frontend/feature_views/
---------------------------
Contains one UI folder per feature.

Example:
frontend/feature_views/edit_pdf/organize-pdf/
|-- panel.html
|-- controller.js

panel.html
- Contains only that feature's UI markup.

controller.js
- Contains only that feature's browser behavior and API calls.

Families include:
- edit_pdf/
- convert_to_pdf/
- convert_from_pdf/
- pdf_security/
- quick_tools/


8.3 frontend/assets/
--------------------
frontend/assets/css/
- base.css: variables and global base rules.
- layout.css: sidebar, workspace, main layout.
- components.css: buttons, forms, dropzones, upload controls, reusable components.
- features.css: feature-specific components such as page editors, comparison results, watermark previews, and crop editor.

frontend/assets/js/core/
Reusable browser modules.

Important modules:
- api.js: HTTP calls and response errors.
- downloads.js: download workflows.
- file_store.js: in-memory uploaded-file state.
- dropzones.js: drag-and-drop upload behavior and single-file controls.
- previews.js: PDF information and preview API calls.
- page_workspace.js: reusable lazy-loading scrollable PDF page grid, page selection, page reordering, blank-page insertion, and page-card actions.
- crop_box.js: interactive visual crop rectangle logic.
- feature_loader.js: lazy-loads feature panels/controllers.
- features.js: maps navigation feature IDs to view/controller files.
- health.js: displays local engine status.

frontend/assets/images/
- Application logo and icon files.


9. DATA FOLDER
--------------
data/ stores persistent runtime data that belongs to the user rather than temporary request files.

data/fonts/
- Stores user-uploaded custom .ttf/.otf watermark fonts.
- The repository ships without custom font binaries.
- User fonts persist between app restarts.

This folder is different from temporary PDF workspaces. Temporary PDF processing files are deleted after each request whenever processing completes normally.


10. DISTRIBUTION FOLDER
-----------------------
distribution/windows/ contains Windows portable-build files.

Important files:
- LocalPDFWorkbench.spec: PyInstaller configuration.
- build_portable.ps1: builds the Windows onedir application.
- Build Portable App.bat: convenient launcher for the build script.
- requirements-build.txt: build-only Python dependency list.
- README_PORTABLE.md: portable-build notes.

Build result:
release/LocalPDFWorkbench/
|-- LocalPDFWorkbench.exe
|-- _internal/

Share the whole LocalPDFWorkbench folder. Do not share only the EXE because _internal contains the Python runtime and bundled dependencies.


11. SCRIPTS FOLDER
------------------
scripts/ contains helper utilities for setup and development.

- setup_windows.ps1: creates/checks the local virtual environment and optionally installs requirements.
- check_system.py: checks local external engines.
- create_desktop_shortcut.ps1: creates a live-source desktop shortcut.


12. TESTS FOLDER
----------------
tests/ contains automated regression tests.

Tests cover key operations such as:
- Page-range parsing.
- Merge and split.
- PDF editing.
- Conversion.
- Security.
- Visual edit workflow backend operations.

Run:

    .\.venv\Scripts\python.exe -m pytest

Tests are not required to run the application, but they are important when changing source code because they help detect regressions.


13. IMPORTANT PYTHON PACKAGES
-----------------------------

FastAPI
- Local HTTP/API framework.

Uvicorn
- Local ASGI server used by FastAPI.

python-multipart
- Handles file/form uploads.

PyMuPDF (fitz)
- PDF rendering, previews, page editing, watermarking, cropping, and many low-level PDF operations.

pypdf
- PDF reading/writing, page manipulation, encryption/decryption, and related operations.

cryptography
- Security-related support.

pdf2docx
- PDF to Word conversion.

python-docx
- Word document generation/fallback handling.

Pillow
- Image processing.

pytesseract
- OCR-related Python integration where applicable.

python-pptx
- PowerPoint generation.

openpyxl
- Excel generation.

pdfplumber
- PDF text/table extraction for spreadsheet conversion and related analysis.

WeasyPrint
- HTML to PDF rendering when its native dependencies are available.

ReportLab
- PDF/document fallback rendering.

BeautifulSoup4
- HTML parsing and fallback handling.

PyWebView
- Desktop window shell that displays the local HTML frontend without requiring the user to manually open a browser.


14. EXTERNAL WINDOWS ENGINES
----------------------------
Some features require separately installed local programs.

Ghostscript
- Used for strong PDF compression.

Tesseract OCR
- Used for OCR PDF.

LibreOffice
- Used for higher-fidelity Office-to-PDF conversion.
- Required for legacy .doc, .ppt, and .xls files.

Check them with:

    .\.venv\Scripts\python.exe .\scripts\check_system.py


15. RUNNING IN LIVE-SOURCE DESKTOP MODE
---------------------------------------
From the project folder:

    & ".\.venv\Scripts\pythonw.exe" ".\desktop.py"

This mode does not need VS Code to remain open.

A desktop shortcut can be created with:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\create_desktop_shortcut.ps1

When source code is changed:
1. Save the source file.
2. Close the running Local PDF Workbench.
3. Open it again from the desktop shortcut.
4. The newest source is loaded automatically.


16. RUNNING IN BROWSER DEVELOPMENT MODE
---------------------------------------

    .\.venv\Scripts\python.exe .\run.py

Then open:

    http://127.0.0.1:8000


17. BUILDING THE PORTABLE WINDOWS APPLICATION
---------------------------------------------
If PyInstaller is not already installed:

    .\.venv\Scripts\python.exe -m pip install -r .\distribution\windows\requirements-build.txt

Allow the PowerShell script for the current terminal only:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Build:

    .\distribution\windows\build_portable.ps1

Output:

    release\LocalPDFWorkbench\

The portable build contains the Python runtime and Python packages, but Ghostscript and Tesseract remain separate external engines unless a future distribution strategy explicitly bundles them.


18. PRIVACY AND FILE STORAGE
----------------------------
Normal PDF uploads are processed inside temporary local folders created for each API request.

Typical flow:

Browser/PyWebView UI
    -> localhost FastAPI
    -> local temporary workspace
    -> local PDF engine
    -> output download
    -> temporary workspace cleanup

The application does not require a cloud PDF API.

Persistent user data is currently limited to intended application data such as custom watermark fonts stored in data/fonts/.


19. DESIGN PRINCIPLES
---------------------

SOLID
- Each feature has a focused module.
- HTTP routing is separated from service logic.
- Shared code is kept behind small reusable modules.

DRY
- Page-grid behavior is centralized in page_workspace.js.
- Crop interaction is centralized in crop_box.js.
- Upload/download handling uses shared frontend helpers.
- External-process handling uses shared backend helpers.

KISS
- Vanilla HTML/CSS/JavaScript is kept instead of adding a frontend framework.
- FastAPI remains a single local application rather than being split into microservices.
- No database server is required.
- Persistent font storage uses a simple local data folder.


20. SOURCE VS RELEASE
---------------------
Source project:
- Used for development.
- Uses .venv.
- Can be edited directly.
- Desktop shortcut points to desktop.py.

release/LocalPDFWorkbench/:
- Generated portable application.
- Used for sharing with another Windows user/computer.
- Does not update automatically when source code changes.
- Must be rebuilt after source changes if the portable release must contain those changes.

END OF README
