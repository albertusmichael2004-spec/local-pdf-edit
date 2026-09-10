# Windows Installer Build

This is the primary distribution path for Local PDF Workbench. It freezes the
Python application as a folder-based runtime, wraps that payload in an Inno
Setup installer, and writes a SHA-256 checksum beside the installer.

## Installed layout

- Application binaries: `C:\Program Files\Local PDF Workbench` by default.
- User-selected installation folders are supported and remembered by the
  stable Inno Setup AppId and an explicit registry `InstallPath` value.
- User-writable state: `%LOCALAPPDATA%\LocalPDFWorkbench`.
- Start Menu shortcuts: application and uninstaller.
- Desktop shortcut: optional checkbox on the final installer page.
- Launch application: optional checkbox on the final installer page.
- Windows uninstall entry: **Settings > Apps > Installed apps**.

Running a newer setup over an older installed version shows **Update** and
**Uninstall** choices. Updates compare SHA-256 hashes per payload file, copy
only new or changed files, and remove obsolete files listed by the prior
payload manifest. The application is not uninstalled first, and user state in
`%LOCALAPPDATA%` is preserved.

## One-time build prerequisites

1. Keep the existing project `.venv` and install the PyInstaller build
   requirement if needed:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r .\distribution\windows\requirements-build.txt
   ```

2. Install Inno Setup 6 so `ISCC.exe` is available in PATH or in its standard
   Program Files/Local AppData location.

## Build

Double-click `Build Installer.bat`, or run:

```powershell
.\distribution\windows\build_installer.ps1
```

The default outputs are:

```text
release\installer\LocalPDFWorkbench-Setup-x64-vX.Y.Z.exe
release\installer\LocalPDFWorkbench-X.Y.Z-SHA256.txt
```

The Python launcher additionally copies the versioned installer executable, a
stable `LocalPDFWorkbench-Setup-x64-latest.exe` alias, and `latest.json` to
`C:\Users\alber\OneDrive\[03] Projects\LocalPDFWorkbench` for sharing. The
checksum text file is kept only in `release\installer\`. Configure the public
manifest and installer URLs once in the root `update-config.json`, or override
them with `PDF_WORKBENCH_UPDATE_MANIFEST_URL` and
`PDF_WORKBENCH_PUBLIC_INSTALLER_URL`.

The publisher overwrites the contents of the two stable `latest` files in
place. Do not delete and recreate either shared item manually; deleting it can
invalidate its OneDrive item link. Versioned installer copies may be added or
removed independently because the updater never links to those filenames.

The same manifest is also written to `update-feed\latest.json` in the Git
repository. Commit and push that generated file after a release so installed
builds can read it through the configured raw GitHub HTTPS URL.

Example `update-config.json` values:

```json
{
  "manifest_url": "https://your-public-link/latest.json",
  "installer_url": "https://your-public-link/LocalPDFWorkbench-Setup-x64-latest.exe",
  "release_notes": {
    "en": [
      "Describe the feature or fix included in this release."
    ],
    "id": [
      "Jelaskan fitur atau perbaikan yang masuk dalam release ini."
    ]
  }
}
```

On every successful build, the launcher adds the generated version and its
bullets to the root `CHANGELOG.md`, refreshes the generated release-history
section in `README.md`, and includes the full release list in `latest.json`.
The app filters that list against the installed version, so a user upgrading
from 4.1.1 directly to 4.1.5 sees the notes for every intervening release but
downloads only the 4.1.5 installer. The notification chooses the `en` or `id`
notes according to the language saved in the installed app.

The selected language is stored in `%LOCALAPPDATA%\LocalPDFWorkbench\preferences.json`
and survives closing and reopening the desktop app.

The application checks the public manifest through its local API when it starts.
The request contains only version metadata; PDF files are never uploaded. If
the network is unavailable, startup continues without an update warning.

`build_or_update.py` now stops before changing the version or building when
either public URL is empty or is not HTTPS. This prevents an installer from
shipping with an updater that is silently disabled. The manifest URL must be a
direct response containing the raw JSON object. A OneDrive folder/file preview
page returns HTML and is rejected by the app. The generated manifest also
contains the installer SHA-256 and byte size as release-integrity metadata.

The manifest URL is bootstrap information embedded inside each installed app.
An already distributed build with an empty URL cannot discover a newly created
`latest.json` on its own. Users of such a build need to install one corrected
installer manually. Every build after that can discover later versions through
the stable manifest URL.

The Python launcher automatically advances the patch version when the source
fingerprint changes and records the last state in `.local\installer-version-state.json`.
Repeated builds of the same source reuse the same version. Change `VERSION`
manually only when changing the major or minor release line.

The app version lives in both `VERSION` and `pyproject.toml`; the build stops if
they differ. For a rebuild that reuses an existing `dist\LocalPDFWorkbench`
payload, pass `-SkipAppBuild`. Tests run by default and can be skipped for a
local packaging experiment with `-SkipTests`.

## Trusted public releases

`AppPublisher=Albertus Michael` controls installer metadata and the Windows
Installed Apps entry. It does not create a trusted Windows digital signature.
Before public distribution, install a trusted code-signing certificate in the
Windows certificate store and provide its thumbprint:

```powershell
$env:PDF_WORKBENCH_CERT_THUMBPRINT = "YOUR_CERTIFICATE_THUMBPRINT"
.\distribution\windows\build_installer.ps1
```

The build signs `LocalPDFWorkbench.exe` before it is packed, signs the final
installer, and timestamps both signatures. Never store signing keys or
passwords in this repository.
