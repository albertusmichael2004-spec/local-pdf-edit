from __future__ import annotations

import os
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
BUILD_REQUIREMENTS = ROOT / "distribution" / "windows" / "requirements-build.txt"
INSTALLER_BUILDER = ROOT / "distribution" / "windows" / "build_installer.ps1"
INSTALLER_OUTPUT_DIRECTORY = ROOT / "release" / "installer"
VERSION_FILE = ROOT / "VERSION"
PYPROJECT_FILE = ROOT / "pyproject.toml"
VERSION_STATE_FILE = ROOT / ".local" / "installer-version-state.json"
UPDATE_CONFIG_FILE = ROOT / "update-config.json"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
README_FILE = ROOT / "README.md"
README_RELEASE_START = "<!-- BEGIN AUTO RELEASE NOTES -->"
README_RELEASE_END = "<!-- END AUTO RELEASE NOTES -->"
DEFAULT_PUBLIC_INSTALLER_DIRECTORY = Path(
    r"C:\Users\alber\OneDrive\[03] Projects\LocalPDFWorkbench"
)
PUBLIC_LATEST_INSTALLER_NAME = "LocalPDFWorkbench-Setup-x64-latest.exe"
PUBLIC_MANIFEST_NAME = "latest.json"
REPOSITORY_MANIFEST_FILE = ROOT / "update-feed" / PUBLIC_MANIFEST_NAME
PUBLIC_INSTALLER_DIRECTORY = Path(
    os.environ.get(
        "PDF_WORKBENCH_PUBLIC_OUTPUT_DIR",
        str(DEFAULT_PUBLIC_INSTALLER_DIRECTORY),
    )
)


def _run(command: list[str]) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _ensure_pyinstaller() -> None:
    check = subprocess.run(
        [str(VENV_PYTHON), "-c", "import PyInstaller"],
        cwd=ROOT,
        capture_output=True,
    )
    if check.returncode:
        print("PyInstaller is missing; installing the build-only requirements once.")
        _run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(BUILD_REQUIREMENTS)])


def _parse_version(version: str) -> tuple[int, int, int]:
    parts = version.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise SystemExit(f"Version must use MAJOR.MINOR.PATCH format: {version!r}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _project_fingerprint() -> str:
    """Hash source files while ignoring generated version and build output."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("Automatic versioning requires a Git checkout.") from exc

    digest = hashlib.sha256()
    paths = sorted(
        Path(raw.decode("utf-8", errors="surrogateescape"))
        for raw in result.stdout.split(b"\0")
        if raw
    )
    for relative_path in paths:
        if relative_path.as_posix() in {
            "VERSION",
            "update-config.json",
            "CHANGELOG.md",
            "README.md",
            "update-feed/latest.json",
        }:
            continue
        absolute_path = ROOT / relative_path
        if not absolute_path.is_file():
            continue
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        if relative_path.as_posix() == "pyproject.toml":
            contents = absolute_path.read_text(encoding="utf-8")
            contents = re.sub(
                r'(?m)^version\s*=\s*"[^"\r\n]+"',
                'version = "<auto>"',
                contents,
                count=1,
            )
            digest.update(contents.encode("utf-8"))
        else:
            digest.update(absolute_path.read_bytes())
        digest.update(b"\0")
    # The effective public channel ships with the application even when its
    # values are supplied through environment variables instead of the file.
    digest.update(b"effective-update-config\0")
    digest.update(
        json.dumps(
            _read_update_config(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _read_update_config() -> dict[str, object]:
    config: dict[str, object] = {}
    if UPDATE_CONFIG_FILE.is_file():
        try:
            raw_config = json.loads(UPDATE_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw_config, dict):
                config = {str(key): value for key, value in raw_config.items() if value is not None}
        except (OSError, ValueError, TypeError):
            print(f"Warning: could not read update configuration: {UPDATE_CONFIG_FILE}")
    for key, environment_name in (
        ("manifest_url", "PDF_WORKBENCH_UPDATE_MANIFEST_URL"),
        ("installer_url", "PDF_WORKBENCH_PUBLIC_INSTALLER_URL"),
        ("release_notes", "PDF_WORKBENCH_RELEASE_NOTES"),
    ):
        override = os.environ.get(environment_name, "").strip()
        if override:
            config[key] = override
    return config


def _validate_public_update_config(
    config: dict[str, object] | None = None,
) -> dict[str, object]:
    """Reject a public release that installed builds cannot discover or download."""
    config = dict(config if config is not None else _read_update_config())
    errors: list[str] = []
    for key in ("manifest_url", "installer_url"):
        value = str(config.get(key, "")).strip()
        parsed = urlsplit(value)
        if not value:
            errors.append(f"{key} is empty")
        elif parsed.scheme.lower() != "https" or not parsed.netloc:
            errors.append(f"{key} must be a complete HTTPS URL")
        elif "your-public-link" in parsed.netloc.lower():
            errors.append(f"{key} still contains the example host")
        elif key == "manifest_url" and parsed.netloc.lower() == "1drv.ms":
            errors.append(
                "manifest_url is a OneDrive preview link; use a URL that returns raw JSON"
            )
        config[key] = value

    if errors:
        detail = "; ".join(errors)
        raise SystemExit(
            "Public update-channel preflight failed: "
            f"{detail}. Set the stable public URLs in update-config.json or "
            "PDF_WORKBENCH_UPDATE_MANIFEST_URL and "
            "PDF_WORKBENCH_PUBLIC_INSTALLER_URL. The manifest URL must return "
            "the raw latest.json content rather than a OneDrive preview page."
        )
    return config


def _normalize_release_notes(value: object) -> list[str]:
    """Convert configured release notes into unique, display-ready bullets."""
    if isinstance(value, str):
        candidates: list[object] = value.splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    notes: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        note = re.sub(r"^\s*[-*•]\s*", "", str(candidate).strip())
        if note and note not in seen:
            notes.append(note)
            seen.add(note)
    return notes


def _normalize_localized_release_notes(value: object) -> dict[str, list[str]]:
    """Normalize release notes to the locales supported by the app."""
    if isinstance(value, dict):
        localized = {
            locale: _normalize_release_notes(value.get(locale))
            for locale in ("en", "id")
        }
    else:
        localized = {"en": _normalize_release_notes(value), "id": []}
    if not localized["en"] and localized["id"]:
        localized["en"] = list(localized["id"])
    if not localized["id"] and localized["en"]:
        localized["id"] = list(localized["en"])
    return localized


def _automatic_release_notes() -> list[str]:
    """Create a useful fallback summary when no manual notes were supplied."""
    changed: set[str] = set()
    for command in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        changed.update(
            path.strip().replace("\\", "/")
            for path in result.stdout.splitlines()
            if path.strip()
        )

    # Generated release metadata and local configuration should not become notes.
    changed.difference_update({"VERSION", "CHANGELOG.md", "README.md", "update-config.json"})
    notes: list[str] = []
    if any(path.startswith("backend/") for path in changed):
        notes.append("Backend reliability and workflow improvements.")
    if any(path.startswith("frontend/") for path in changed):
        notes.append("User interface and document workflow improvements.")
    if any(path.startswith("distribution/") for path in changed):
        notes.append("Installer, update, and distribution improvements.")
    if any(path.startswith("tests/") for path in changed):
        notes.append("Regression coverage and validation updates.")
    if any(path.startswith("docs/") for path in changed):
        notes.append("Documentation and project guidance updates.")
    return notes or ["Bug fixes, maintenance, and performance improvements."]


def _automatic_localized_release_notes() -> dict[str, list[str]]:
    english = _automatic_release_notes()
    indonesian = {
        "Backend reliability and workflow improvements.": "Peningkatan keandalan backend dan alur kerja.",
        "User interface and document workflow improvements.": "Peningkatan antarmuka dan alur kerja dokumen.",
        "Installer, update, and distribution improvements.": "Peningkatan installer, pembaruan, dan distribusi.",
        "Regression coverage and validation updates.": "Peningkatan pengujian regresi dan validasi.",
        "Documentation and project guidance updates.": "Pembaruan dokumentasi dan panduan proyek.",
        "Bug fixes, maintenance, and performance improvements.": "Perbaikan bug, pemeliharaan, dan peningkatan kinerja.",
    }
    return {"en": english, "id": [indonesian.get(note, note) for note in english]}


def _localized_changes_from_section(section: str) -> dict[str, list[str]]:
    localized = {"en": [], "id": []}
    headings = list(re.finditer(r"(?mi)^###\s+(en|id|english|bahasa indonesia)\s*$", section))
    if not headings:
        localized["en"] = _normalize_release_notes(
            [line.strip() for line in section.splitlines() if line.strip().startswith(("-", "*", "•"))]
        )
    else:
        prefix = section[:headings[0].start()]
        localized["en"] = _normalize_release_notes(
            [line.strip() for line in prefix.splitlines() if line.strip().startswith(("-", "*", "•"))]
        )
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(section)
            language = heading.group(1).lower()
            language = "en" if language == "english" else "id" if language == "bahasa indonesia" else language
            localized[language] = _normalize_release_notes(
                [line.strip() for line in section[heading.end() : end].splitlines() if line.strip().startswith(("-", "*", "•"))]
            )
    if not localized["en"] and localized["id"]:
        localized["en"] = list(localized["id"])
    if not localized["id"] and localized["en"]:
        localized["id"] = list(localized["en"])
    return localized


def _read_release_history() -> list[dict[str, object]]:
    if not CHANGELOG_FILE.is_file():
        return []
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    headings = list(
        re.finditer(
            r"(?m)^##\s+\[([0-9]+\.[0-9]+\.[0-9]+)\](?:\s+-\s+([^\r\n]+))?\s*$",
            text,
        )
    )
    history: list[dict[str, object]] = []
    for heading in headings:
        next_heading = re.search(r"(?m)^##\s+", text[heading.end() :])
        section_end = (
            heading.end() + next_heading.start()
            if next_heading
            else len(text)
        )
        section = text[heading.end() : section_end]
        changes_i18n = _localized_changes_from_section(section)
        history.append({
            "version": heading.group(1),
            "date": (heading.group(2) or "").strip(),
            "changes": changes_i18n["en"] or ["Bug fixes and improvements."],
            "changes_i18n": changes_i18n,
        })
    history.sort(key=lambda item: _parse_version(str(item["version"])), reverse=True)
    return history


def _format_changelog_entry(
    version: str,
    date: str,
    changes_i18n: dict[str, list[str]],
) -> str:
    lines = [f"## [{version}] - {date}", ""]
    for locale in ("en", "id"):
        lines.append(f"### {locale}")
        lines.extend(f"- {note}" for note in changes_i18n.get(locale, []))
        lines.append("")
    return "\n".join(lines)


def _render_readme_release_block(history: list[dict[str, object]]) -> str:
    lines = [
        README_RELEASE_START,
        "## Recent release history",
        "",
        "This section is generated by `distribution/build_or_update.py` from `CHANGELOG.md`.",
        "",
    ]
    for release in history:
        version = str(release["version"])
        date = str(release.get("date", "")).strip()
        suffix = f" — {date}" if date else ""
        lines.extend([f"### v{version}{suffix}", ""])
        changes_i18n = release.get("changes_i18n", {})
        if not isinstance(changes_i18n, dict):
            changes_i18n = {"en": release.get("changes", [])}
        for change in changes_i18n.get("en", release.get("changes", [])):
            lines.append(f"- {change}")
        english = list(changes_i18n.get("en", []))
        indonesian = list(changes_i18n.get("id", []))
        if indonesian and indonesian != english:
            lines.extend(["", "**Bahasa Indonesia**", ""])
            lines.extend(f"- {change}" for change in indonesian)
        lines.append("")
    lines.append(README_RELEASE_END)
    return "\n".join(lines)


def _sync_readme_release_history(history: list[dict[str, object]]) -> None:
    if not README_FILE.is_file():
        return
    readme = README_FILE.read_text(encoding="utf-8")
    block = _render_readme_release_block(history)
    pattern = re.compile(
        re.escape(README_RELEASE_START) + r".*?" + re.escape(README_RELEASE_END),
        re.DOTALL,
    )
    if pattern.search(readme):
        updated = pattern.sub(block, readme, count=1)
    else:
        updated = readme.rstrip() + "\n\n" + block + "\n"
    if updated != readme:
        README_FILE.write_text(updated, encoding="utf-8")


def _record_release(version: str) -> list[dict[str, object]]:
    """Add a release entry once, then regenerate the README release section."""
    history = _read_release_history()
    configured_notes = _normalize_localized_release_notes(
        _read_update_config().get("release_notes")
    )
    has_configured_notes = any(configured_notes.values())
    existing = next(
        (item for item in history if str(item.get("version")) == version),
        None,
    )
    if existing and has_configured_notes:
        changelog = CHANGELOG_FILE.read_text(encoding="utf-8")
        section_pattern = re.compile(
            rf"(?ms)^##\s+\[{re.escape(version)}\].*?(?=^##\s+|\Z)"
        )
        replacement = (
            _format_changelog_entry(
                version,
                str(existing.get("date") or datetime.now(timezone.utc).date().isoformat()),
                configured_notes,
            )
        )
        updated_changelog, replacements = section_pattern.subn(
            replacement,
            changelog,
            count=1,
        )
        if replacements:
            CHANGELOG_FILE.write_text(updated_changelog, encoding="utf-8")
            history = _read_release_history()
    elif not existing:
        notes = configured_notes if has_configured_notes else _automatic_localized_release_notes()
        entry = _format_changelog_entry(
            version,
            datetime.now(timezone.utc).date().isoformat(),
            notes,
        )
        if CHANGELOG_FILE.is_file():
            changelog = CHANGELOG_FILE.read_text(encoding="utf-8")
        else:
            changelog = "# Changelog\n\n"
        header_match = re.match(r"(?s)(\s*# Changelog[^\r\n]*\r?\n(?:\r?\n)?)", changelog)
        if header_match:
            insert_at = header_match.end()
            changelog = changelog[:insert_at] + entry + changelog[insert_at:]
        else:
            changelog = "# Changelog\n\n" + entry + changelog
        CHANGELOG_FILE.write_text(changelog, encoding="utf-8")
        history = _read_release_history()
    _sync_readme_release_history(history)
    return history


def _write_version_sources(version: str) -> None:
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")
    project_text = PYPROJECT_FILE.read_text(encoding="utf-8")
    updated_text, replacements = re.subn(
        r'(?m)^version\s*=\s*"[^"\r\n]+"',
        f'version = "{version}"',
        project_text,
        count=1,
    )
    if replacements != 1:
        raise SystemExit(f"Could not update the project version in {PYPROJECT_FILE}")
    PYPROJECT_FILE.write_text(updated_text, encoding="utf-8")


def _prepare_build_version() -> str:
    """Return a stable version for this source state and persist the counter."""
    current_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    current_major, current_minor, current_patch = _parse_version(current_version)
    fingerprint = _project_fingerprint()
    state: dict[str, object] = {}
    if VERSION_STATE_FILE.is_file():
        try:
            loaded = json.loads(VERSION_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except (OSError, ValueError, TypeError):
            state = {}

    state_version = str(state.get("version", ""))
    state_fingerprint = str(state.get("fingerprint", ""))
    if state_fingerprint == fingerprint and state_version:
        _parse_version(state_version)
        version = state_version
    elif state_version:
        state_major, state_minor, state_patch = _parse_version(state_version)
        if (state_major, state_minor) == (current_major, current_minor):
            version = f"{current_major}.{current_minor}.{max(current_patch, state_patch) + 1}"
        else:
            # A deliberate major/minor change in VERSION starts a new release line.
            version = current_version
    else:
        version = f"{current_major}.{current_minor}.{current_patch + 1}"

    _write_version_sources(version)
    VERSION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_STATE_FILE.write_text(
        json.dumps({"fingerprint": fingerprint, "version": version}, indent=2) + "\n",
        encoding="utf-8",
    )
    return version


def _copy_atomically(source: Path, destination: Path) -> None:
    partial = destination.with_name(destination.name + ".partial")
    try:
        shutil.copy2(source, partial)
        partial.replace(destination)
    finally:
        if partial.exists():
            partial.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _publish_public_installer(config: dict[str, object] | None = None) -> Path:
    """Copy the installer and update manifest to the user-facing OneDrive folder."""
    config = _validate_public_update_config(config)
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    installer = INSTALLER_OUTPUT_DIRECTORY / f"LocalPDFWorkbench-Setup-x64-v{version}.exe"
    if not installer.is_file():
        raise SystemExit(f"Built installer was not found: {installer}")

    PUBLIC_INSTALLER_DIRECTORY.mkdir(parents=True, exist_ok=True)
    destination = PUBLIC_INSTALLER_DIRECTORY / installer.name
    latest_destination = PUBLIC_INSTALLER_DIRECTORY / PUBLIC_LATEST_INSTALLER_NAME
    _copy_atomically(installer, destination)
    # Keep the stable OneDrive item in place so its shared link can remain
    # valid across releases. The versioned file above is safe to replace.
    shutil.copy2(installer, latest_destination)

    history = _read_release_history()
    latest_release = next(
        (item for item in history if str(item.get("version")) == version),
        None,
    )
    release_notes_source = (
        latest_release.get("changes_i18n", latest_release.get("changes", []))
        if latest_release
        else config.get("release_notes")
    )
    release_notes_i18n = _normalize_localized_release_notes(release_notes_source)
    release_notes = release_notes_i18n["en"]
    manifest = {
        "product": "Local PDF Workbench",
        "version": version,
        "installer_filename": PUBLIC_LATEST_INSTALLER_NAME,
        "installer_url": config["installer_url"],
        "installer_sha256": _sha256_file(installer),
        "installer_size": installer.stat().st_size,
        "release_notes": "\n".join(f"- {note}" for note in release_notes),
        "release_notes_i18n": release_notes_i18n,
        "releases": history,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_destination = PUBLIC_INSTALLER_DIRECTORY / PUBLIC_MANIFEST_NAME
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    # Write in place for the same stable-link reason as the latest installer.
    manifest_destination.write_text(manifest_text, encoding="utf-8")
    # Keep a Git-tracked copy for a stable raw HTTPS manifest. The installer
    # remains on OneDrive; this file contains only release metadata and links.
    REPOSITORY_MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPOSITORY_MANIFEST_FILE.write_text(manifest_text, encoding="utf-8")

    print(f"Public installer copied: {destination}")
    print(f"Latest installer alias updated: {latest_destination}")
    print(f"Update metadata written: {manifest_destination}")
    print(f"Repository update metadata written: {REPOSITORY_MANIFEST_FILE}")
    return destination


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("This installer builder targets Windows only.")
    if not VENV_PYTHON.is_file():
        raise SystemExit(f"Project virtual environment not found: {VENV_PYTHON}")
    if not INSTALLER_BUILDER.is_file():
        raise SystemExit(f"Installer builder not found: {INSTALLER_BUILDER}")

    update_config = _validate_public_update_config()
    version = _prepare_build_version()
    print(f"Building automatic release version {version}...")
    _ensure_pyinstaller()
    _run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER_BUILDER),
        ]
    )
    _record_release(version)
    _publish_public_installer(update_config)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PermissionError as exc:
        raise SystemExit(f"Close the running app and retry the installer build. {exc}") from exc
