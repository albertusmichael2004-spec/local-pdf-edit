from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tomllib

from PIL import Image, ImageChops
import pytest

from backend.core import paths
from backend.core import update as update_module
from distribution import build_or_update as installer_launcher


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_sources_match():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["version"] == version
    assert len(version.split(".")) == 3
    assert all(part.isdigit() for part in version.split("."))


def test_installer_has_stable_identity_and_windows_integration():
    script = (ROOT / "distribution" / "windows" / "LocalPDFWorkbench.iss").read_text(
        encoding="utf-8"
    )

    assert '#define MyAppPublisher "Albertus Michael"' in script
    assert '#define MyAppId "E6B92402-5C15-4E50-A8D3-FF805E644E0D"' in script
    assert "DefaultDirName={autopf}\\Local PDF Workbench" in script
    assert "UsePreviousAppDir=yes" in script
    assert "PrivilegesRequired=admin" in script
    assert "PrivilegesRequiredOverridesAllowed=commandline" in script
    assert "WizardImageFile=wizard-logo.bmp" in script
    assert 'ValueName: "InstallPath"; ValueData: "{app}"' in script
    assert 'Filename: "{uninstallexe}"' in script
    assert "Existing installation detected" in script


def test_primary_distribution_entry_point_builds_the_installer():
    entry_point = (ROOT / "distribution" / "build_or_update.py").read_text(
        encoding="utf-8"
    )

    assert 'INSTALLER_BUILDER = ROOT / "distribution" / "windows" / "build_installer.ps1"' in entry_point
    assert "DEFAULT_PUBLIC_INSTALLER_DIRECTORY" in entry_point
    assert '"latest.json"' in entry_point
    assert "Latest installer alias updated" in entry_point
    assert "PORTABLE_BUILDER" not in entry_point


def test_public_installer_publish_copies_only_the_versioned_exe(tmp_path, monkeypatch):
    source = tmp_path / "release" / "installer"
    destination = tmp_path / "OneDrive" / "LocalPDFWorkbench"
    source.mkdir(parents=True)
    version_file = tmp_path / "VERSION"
    version_file.write_text("4.1.1\n", encoding="utf-8")
    installer = source / "LocalPDFWorkbench-Setup-x64-v4.1.1.exe"
    installer.write_bytes(b"installer")
    (source / "LocalPDFWorkbench-4.1.1-SHA256.txt").write_text(
        "checksum", encoding="utf-8"
    )

    monkeypatch.setattr(installer_launcher, "VERSION_FILE", version_file)
    monkeypatch.setattr(installer_launcher, "INSTALLER_OUTPUT_DIRECTORY", source)
    monkeypatch.setattr(installer_launcher, "PUBLIC_INSTALLER_DIRECTORY", destination)
    repository_manifest = tmp_path / "repository" / "update-feed" / "latest.json"
    monkeypatch.setattr(installer_launcher, "REPOSITORY_MANIFEST_FILE", repository_manifest)
    monkeypatch.setattr(
        installer_launcher,
        "_read_update_config",
        lambda: {
            "manifest_url": "https://downloads.example.test/latest.json",
            "installer_url": "https://downloads.example.test/LocalPDFWorkbench-Setup-x64-latest.exe",
        },
    )

    published = installer_launcher._publish_public_installer()

    assert published == destination / installer.name
    assert published.read_bytes() == b"installer"
    assert (destination / installer_launcher.PUBLIC_LATEST_INSTALLER_NAME).read_bytes() == b"installer"
    manifest = json.loads((destination / "latest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "4.1.1"
    assert manifest["installer_filename"] == installer_launcher.PUBLIC_LATEST_INSTALLER_NAME
    assert manifest["installer_sha256"] == hashlib.sha256(b"installer").hexdigest()
    assert manifest["installer_size"] == len(b"installer")
    assert json.loads(repository_manifest.read_text(encoding="utf-8")) == manifest
    assert not list(destination.glob("*SHA256*.txt"))


def test_public_update_config_rejects_a_silent_disabled_channel():
    with pytest.raises(SystemExit, match="manifest_url is empty"):
        installer_launcher._validate_public_update_config({
            "manifest_url": "",
            "installer_url": "",
        })


def test_public_update_config_rejects_onedrive_preview_as_manifest():
    with pytest.raises(SystemExit, match="OneDrive preview link"):
        installer_launcher._validate_public_update_config({
            "manifest_url": "https://1drv.ms/u/c/example/item",
            "installer_url": "https://1drv.ms/u/c/example/installer",
        })


def test_powershell_builder_preserves_nested_update_configuration():
    builder = (ROOT / "distribution" / "windows" / "build_installer.ps1").read_text(
        encoding="utf-8"
    )

    assert "$updateConfig[$property.Name] = $property.Value" in builder
    assert "$updateConfig[$property.Name] = [string]$property.Value" not in builder


def test_automatic_version_reuses_same_source_version_and_advances_on_change(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    project_file = tmp_path / "pyproject.toml"
    state_file = tmp_path / "state.json"
    version_file.write_text("4.1.1\n", encoding="utf-8")
    project_file.write_text('[project]\nversion = "4.1.1"\n', encoding="utf-8")

    monkeypatch.setattr(installer_launcher, "VERSION_FILE", version_file)
    monkeypatch.setattr(installer_launcher, "PYPROJECT_FILE", project_file)
    monkeypatch.setattr(installer_launcher, "VERSION_STATE_FILE", state_file)
    fingerprint = {"value": "source-a"}
    monkeypatch.setattr(
        installer_launcher,
        "_project_fingerprint",
        lambda: fingerprint["value"],
    )

    assert installer_launcher._prepare_build_version() == "4.1.2"
    assert installer_launcher._prepare_build_version() == "4.1.2"
    fingerprint["value"] = "source-b"
    assert installer_launcher._prepare_build_version() == "4.1.3"


def test_release_record_updates_changelog_and_readme(tmp_path, monkeypatch):
    changelog = tmp_path / "CHANGELOG.md"
    readme = tmp_path / "README.md"
    changelog.write_text("# Changelog\n\n", encoding="utf-8")
    readme.write_text(
        "# App\n\n<!-- BEGIN AUTO RELEASE NOTES -->\nold\n<!-- END AUTO RELEASE NOTES -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(installer_launcher, "CHANGELOG_FILE", changelog)
    monkeypatch.setattr(installer_launcher, "README_FILE", readme)
    monkeypatch.setattr(
        installer_launcher,
        "_read_update_config",
        lambda: {"release_notes": ["Added batch export", "Fixed startup crash"]},
    )

    history = installer_launcher._record_release("4.1.2")

    assert history[0]["version"] == "4.1.2"
    assert history[0]["changes"] == ["Added batch export", "Fixed startup crash"]
    assert "## [4.1.2]" in changelog.read_text(encoding="utf-8")
    generated_readme = readme.read_text(encoding="utf-8")
    assert "### v4.1.2" in generated_readme
    assert "Added batch export" in generated_readme


def test_release_record_preserves_bilingual_notes(tmp_path, monkeypatch):
    changelog = tmp_path / "CHANGELOG.md"
    readme = tmp_path / "README.md"
    changelog.write_text("# Changelog\n\n", encoding="utf-8")
    readme.write_text("# App\n", encoding="utf-8")
    monkeypatch.setattr(installer_launcher, "CHANGELOG_FILE", changelog)
    monkeypatch.setattr(installer_launcher, "README_FILE", readme)
    monkeypatch.setattr(
        installer_launcher,
        "_read_update_config",
        lambda: {"release_notes": {"en": ["Added export"], "id": ["Menambahkan ekspor"]}},
    )

    history = installer_launcher._record_release("4.1.2")

    assert history[0]["changes_i18n"] == {
        "en": ["Added export"],
        "id": ["Menambahkan ekspor"],
    }
    changelog_text = changelog.read_text(encoding="utf-8")
    assert "### en" in changelog_text
    assert "### id" in changelog_text


def test_update_manifest_accumulates_intervening_release_history(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps({
                "version": "4.1.5",
                "installer_url": "https://example.test/installer.exe",
                "releases": [
                    {"version": "4.1.2", "changes": ["Added A"]},
                    {"version": "4.1.3", "changes": ["Fixed B"]},
                    {"version": "4.1.4", "changes": ["Improved C"]},
                    {"version": "4.1.5", "changes": ["Added D"]},
                ],
            }).encode("utf-8")

    monkeypatch.setenv("PDF_WORKBENCH_UPDATE_MANIFEST_URL", "https://example.test/latest.json")
    monkeypatch.setattr(update_module, "APP_VERSION", "4.1.1")
    monkeypatch.setattr(update_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    result = update_module.check_for_update()

    assert result["latest_version"] == "4.1.5"
    assert [item["version"] for item in result["release_history"]] == [
        "4.1.2", "4.1.3", "4.1.4", "4.1.5"
    ]


def test_update_manifest_keeps_localized_release_notes(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps({
                "version": "4.1.2",
                "installer_url": "https://example.test/installer.exe",
                "releases": [{
                    "version": "4.1.2",
                    "changes_i18n": {
                        "en": ["Added export"],
                        "id": ["Menambahkan ekspor"],
                    },
                }],
            }).encode("utf-8")

    monkeypatch.setenv("PDF_WORKBENCH_UPDATE_MANIFEST_URL", "https://example.test/latest.json")
    monkeypatch.setattr(update_module, "APP_VERSION", "4.1.1")
    monkeypatch.setattr(update_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    result = update_module.check_for_update()

    assert result["release_history"][0]["changes_i18n"]["id"] == ["Menambahkan ekspor"]


def test_update_manifest_reports_newer_version(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps({
                "version": "4.1.2",
                "installer_url": "https://example.test/installer.exe",
                "release_notes": "Bug fixes",
            }).encode("utf-8")

    monkeypatch.setenv("PDF_WORKBENCH_UPDATE_MANIFEST_URL", "https://example.test/latest.json")
    monkeypatch.setattr(update_module, "APP_VERSION", "4.1.1")
    monkeypatch.setattr(update_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    result = update_module.check_for_update()

    assert result["status"] == "available"
    assert result["latest_version"] == "4.1.2"
    assert result["installer_url"] == "https://example.test/installer.exe"


def test_update_manifest_explains_when_the_embedded_url_is_missing(monkeypatch):
    monkeypatch.delenv("PDF_WORKBENCH_UPDATE_MANIFEST_URL", raising=False)
    monkeypatch.setattr(update_module, "_manifest_url", lambda: "")

    result = update_module.check_for_update()

    assert result == {
        "status": "disabled",
        "current_version": update_module.APP_VERSION,
        "reason": "manifest_url_missing",
    }


def test_update_manifest_rejects_a_onedrive_preview_page(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b"<!doctype html><title>OneDrive</title>"

    monkeypatch.setenv("PDF_WORKBENCH_UPDATE_MANIFEST_URL", "https://example.test/latest.json")
    monkeypatch.setattr(update_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    result = update_module.check_for_update()

    assert result["status"] == "misconfigured"
    assert result["reason"] == "manifest_returned_html"


def test_installer_update_is_hash_and_manifest_driven():
    script = (ROOT / "distribution" / "windows" / "LocalPDFWorkbench.iss").read_text(
        encoding="utf-8"
    )
    builder = (ROOT / "distribution" / "windows" / "build_installer.ps1").read_text(
        encoding="utf-8"
    )

    assert "PayloadFileNeedsUpdate" in script
    assert "GetSHA256OfFile" in script
    assert "RemoveObsoletePayloadFiles" in script
    assert "payload-manifest.txt" in script
    assert "Get-FileHash -Algorithm SHA256" in builder
    assert "[InstallDelete]" not in script


def test_installer_finish_page_offers_shortcut_and_launch():
    script = (ROOT / "distribution" / "windows" / "LocalPDFWorkbench.iss").read_text(
        encoding="utf-8"
    )

    assert "Create a desktop shortcut" in script
    assert "Launch Local PDF Workbench" in script
    assert "ScaleY(28)" in script
    assert "CreateShellLink(" in script
    assert "ExecAsOriginalUser(" in script


def test_windows_icon_contains_all_shell_sizes_and_is_the_runtime_favicon():
    icon_path = ROOT / "frontend" / "assets" / "images" / "app.ico"
    original_logo = Image.open(
        ROOT / "frontend" / "assets" / "images" / "app-logo-256.png"
    ).convert("RGBA")
    with Image.open(icon_path) as icon:
        assert {(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)} <= icon.ico.sizes()
        taskbar_icon = icon.ico.getimage((32, 32))
        assert taskbar_icon.mode == "RGBA"
        assert ImageChops.difference(icon.ico.getimage((256, 256)), original_logo).getbbox() is None

    index = (ROOT / "frontend" / "pages" / "main" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'app.ico?v=5" rel="icon" type="image/x-icon"' in index
    assert "app-favicon.svg" not in index


def test_frozen_app_writes_persistent_data_to_local_app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    data_root = paths.persistent_data_root()

    assert data_root == tmp_path / "LocalPDFWorkbench"
    assert data_root.is_dir()
