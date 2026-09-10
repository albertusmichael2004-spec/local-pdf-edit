# Portable Windows Build

This folder contains the portable build tooling. After PyInstaller reports a
successful build, the script asks where to copy the generated deliverable.

## Goal

Create an `onedir` portable application:

```text
<selected-output-folder>/
├── LocalPDFWorkbench.exe
└── _internal/...
```

Copy/share the **whole `LocalPDFWorkbench` folder**. The destination PC does not need VS Code or a Python installation.
Double-click `LocalPDFWorkbench.exe`; the app opens with normal user permissions.

## Build on the Windows development PC

The build reuses the project's existing `.venv`.

1. Install the optional build dependency once, only if PyInstaller is not already installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\distribution\windows\requirements-build.txt
```

2. Double-click `Build Portable App.bat`, or run:

```powershell
.\distribution\windows\build_portable.ps1
```

3. Share:

```text
<selected-output-folder>/
```

Choose option 1 for an external folder (saved destination or Windows folder
picker), or option 2 for `release\LocalPDFWorkbench\` under the project. The
selected output is saved in `.local\portable_output_dir.txt`; `.local\` is
ignored by Git.

Do **not** share only the `.exe`; this is intentionally an onedir build for reliability and easier troubleshooting.

## External local engines

PyInstaller bundles Python and the Python packages, but it does not bundle third-party desktop programs:

- Ghostscript: required by **Compress PDF**.
- Tesseract OCR: required by **OCR PDF**.
- LibreOffice: optional for higher-fidelity Office-to-PDF conversion and required for legacy `.doc`, `.ppt`, and `.xls` formats.

Other features that use bundled Python libraries can run without VS Code/Python on the destination PC.
