from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .version import APP_VERSION


def _runtime_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def _manifest_url() -> str:
    override = os.environ.get("PDF_WORKBENCH_UPDATE_MANIFEST_URL", "").strip()
    if override:
        return override
    config_path = _runtime_root() / "update-config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ""
    if not isinstance(config, dict):
        return ""
    return str(config.get("manifest_url", "")).strip()


def _result(status: str, reason: str = "", **values: object) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "current_version": APP_VERSION,
    }
    if reason:
        result["reason"] = reason
    result.update(values)
    return result


def _version_key(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("version must use MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _release_changes(value: object) -> list[str]:
    if isinstance(value, str):
        candidates = value.splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []
    changes: list[str] = []
    for candidate in candidates:
        change = str(candidate).strip()
        if change.startswith(("-", "*", "•")):
            change = change[1:].strip()
        if change and change not in changes:
            changes.append(change)
    return changes


def _localized_release_changes(value: object, fallback: object = None) -> dict[str, list[str]]:
    if isinstance(value, dict):
        localized = {
            "en": _release_changes(value.get("en")),
            "id": _release_changes(value.get("id")),
        }
    else:
        localized = {"en": _release_changes(fallback if fallback is not None else value), "id": []}
    if not localized["en"] and localized["id"]:
        localized["en"] = list(localized["id"])
    if not localized["id"] and localized["en"]:
        localized["id"] = list(localized["en"])
    return localized


def _newer_release_history(
    payload: dict[str, object],
    current_version: str,
    latest_version: str,
) -> list[dict[str, object]]:
    current_key = _version_key(current_version)
    latest_key = _version_key(latest_version)
    history: list[dict[str, object]] = []
    raw_history = payload.get("releases")
    if isinstance(raw_history, list):
        for raw_release in raw_history:
            if not isinstance(raw_release, dict):
                continue
            try:
                version = str(raw_release["version"])
                version_key = _version_key(version)
            except (KeyError, TypeError, ValueError):
                continue
            if not current_key < version_key <= latest_key:
                continue
            changes_i18n = _localized_release_changes(
                raw_release.get("changes_i18n"),
                raw_release.get("changes"),
            )
            changes = changes_i18n["en"]
            if not changes:
                changes = ["Bug fixes and improvements."]
                changes_i18n = {"en": changes, "id": changes}
            history.append({
                "version": version,
                "date": str(raw_release.get("date", "")),
                "changes": changes,
                "changes_i18n": changes_i18n,
            })

    history.sort(key=lambda item: _version_key(str(item["version"])))
    if not history:
        fallback_i18n = _localized_release_changes(
            payload.get("release_notes_i18n"),
            payload.get("release_notes"),
        )
        fallback = fallback_i18n["en"]
        if fallback:
            history.append({
                "version": latest_version,
                "date": "",
                "changes": fallback,
                "changes_i18n": fallback_i18n,
            })
    return history


def check_for_update() -> dict[str, object]:
    """Fetch public release metadata without uploading local documents."""
    manifest_url = _manifest_url()
    if not manifest_url:
        return _result("disabled", "manifest_url_missing")
    if not manifest_url.lower().startswith("https://"):
        return _result("misconfigured", "manifest_url_must_use_https")

    request = Request(
        manifest_url,
        headers={"Accept": "application/json", "User-Agent": "LocalPDFWorkbench"},
    )
    try:
        with urlopen(request, timeout=3.5) as response:
            raw_payload = response.read(256 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError):
        return _result("unavailable", "manifest_request_failed")

    if raw_payload.lstrip().startswith((b"<", b"<!")):
        return _result("misconfigured", "manifest_returned_html")
    try:
        payload = json.loads(raw_payload.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        return _result("misconfigured", "manifest_invalid_json")

    if not isinstance(payload, dict):
        return _result("misconfigured", "manifest_must_be_an_object")
    product = str(payload.get("product", "Local PDF Workbench")).strip()
    if product != "Local PDF Workbench":
        return _result("misconfigured", "manifest_product_mismatch")
    try:
        latest_version = str(payload["version"])
        is_newer = _version_key(latest_version) > _version_key(APP_VERSION)
    except (KeyError, TypeError, ValueError):
        return _result("misconfigured", "manifest_version_invalid")
    if not is_newer:
        return _result("current", latest_version=latest_version)

    release_history = _newer_release_history(payload, APP_VERSION, latest_version)
    installer_url = str(payload.get("installer_url", "")).strip()
    if installer_url and not installer_url.lower().startswith(("https://", "http://")):
        installer_url = urljoin(manifest_url, installer_url)
    if not installer_url:
        return _result("misconfigured", "installer_url_missing", latest_version=latest_version)
    if not installer_url.lower().startswith("https://"):
        return _result(
            "misconfigured",
            "installer_url_must_use_https",
            latest_version=latest_version,
        )
    return _result(
        "available",
        latest_version=latest_version,
        installer_url=installer_url,
        installer_sha256=str(payload.get("installer_sha256", "")).strip().lower(),
        installer_size=payload.get("installer_size", 0),
        release_notes=str(payload.get("release_notes", "")),
        release_history=release_history,
    )
