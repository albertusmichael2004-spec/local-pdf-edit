from __future__ import annotations

import json
from pathlib import Path

from .paths import persistent_data_root


SUPPORTED_LOCALES = {"en", "id"}
DEFAULT_LOCALE = "en"
PREFERENCES_FILE_NAME = "preferences.json"


def _preferences_path() -> Path:
    return persistent_data_root() / PREFERENCES_FILE_NAME


def read_locale() -> str:
    try:
        payload = json.loads(_preferences_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return DEFAULT_LOCALE
    if not isinstance(payload, dict):
        return DEFAULT_LOCALE
    locale = str(payload.get("language", DEFAULT_LOCALE)).strip().lower()
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


def write_locale(locale: str) -> str:
    normalized = str(locale).strip().lower()
    if normalized not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported language: {locale}")
    path = _preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"language": normalized}, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
