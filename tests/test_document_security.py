from pathlib import Path
import gzip
import hashlib
import io
import tarfile
import zipfile

import py7zr
import pyzipper
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.core.errors import DocumentSecurityError
from backend.services.document_security.archive_decryption import decrypt_archive
from backend.services.document_security import archive_profiles
from backend.services.document_security.archive_profiles import choose_archive_profile
from backend.services.document_security.archive_security import (
    create_7z_archive,
    create_aes256_7z,
    create_password_protected_zip,
)
from backend.services.document_security.hash_file import create_file_hash, create_path_hash
from backend.services.document_security.archive_extraction import extract_archive_any
from backend.services.document_security import local_operations
from backend.services.document_security.local_operations import secure_local_file
from backend.services.document_security.content_optimization import prepare_balanced_content
from backend.api.routers import document_security as document_security_router
from desktop import DesktopApi


PASSWORD = "correct-horse-battery-staple"


@pytest.mark.parametrize("kind", ["zip", "7z", "tar.gz", "gz"])
def test_extract_archive_common_formats(tmp_path: Path, kind: str):
    payload = b"portable archive extraction content"
    if kind == "zip":
        archive_path = tmp_path / "bundle.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("nested/report.txt", payload)
        expected = Path("nested/report.txt")
    elif kind == "7z":
        source = tmp_path / "report.txt"
        source.write_bytes(payload)
        archive_path = tmp_path / "bundle.7z"
        with py7zr.SevenZipFile(archive_path, "w") as archive:
            archive.write(source, "nested/report.txt")
        expected = Path("nested/report.txt")
    elif kind == "tar.gz":
        archive_path = tmp_path / "bundle.tar.gz"
        info = tarfile.TarInfo("nested/report.txt")
        info.size = len(payload)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.addfile(info, io.BytesIO(payload))
        expected = Path("nested/report.txt")
    else:
        archive_path = tmp_path / "report.txt.gz"
        with gzip.open(archive_path, "wb") as archive:
            archive.write(payload)
        expected = Path("report.txt")

    output = tmp_path / f"output-{kind.replace('.', '-')}"
    result = extract_archive_any(archive_path, output)

    assert result.file_count == 1
    assert result.total_bytes == len(payload)
    assert (output / expected).read_bytes() == payload


def test_extract_archive_rejects_path_traversal_and_removes_partial_output(tmp_path: Path):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", b"must not escape")
    output = tmp_path / "unsafe-output"

    with pytest.raises(DocumentSecurityError, match="unsafe file path"):
        extract_archive_any(archive_path, output)

    assert not output.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_secure_local_file_trashes_original_only_after_validation(tmp_path: Path, monkeypatch):
    source = tmp_path / "contract.docx"
    source.write_bytes(b"confidential document")
    trash_calls: list[Path] = []
    monkeypatch.setattr(local_operations, "send2trash", lambda path: trash_calls.append(Path(path)))

    result = secure_local_file(source, PASSWORD, delete_original=True)

    assert result.original_trashed is True
    assert trash_calls == [source.resolve()]
    with py7zr.SevenZipFile(result.output_path, "r", password=PASSWORD) as archive:
        assert archive.needs_password() is True
        assert archive.getnames() == [source.name]


def test_secure_local_file_does_not_trash_original_when_archive_fails(tmp_path: Path, monkeypatch):
    source = tmp_path / "original.bin"
    source.write_bytes(b"keep me")
    trash_calls: list[Path] = []
    monkeypatch.setattr(local_operations, "send2trash", lambda path: trash_calls.append(Path(path)))

    with pytest.raises(DocumentSecurityError, match="at least 8"):
        secure_local_file(source, "short", delete_original=True)

    assert source.exists()
    assert trash_calls == []
    assert not (tmp_path / "original_secured.7z").exists()


def test_desktop_extract_uses_selected_folder_when_same_folder_is_unchecked(tmp_path: Path):
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("inside.txt", b"extracted")
    chosen_root = tmp_path / "chosen-output"
    chosen_root.mkdir()

    class FakeWindow:
        def create_file_dialog(self, *_args, **_kwargs):
            return (str(chosen_root),)

    api = DesktopApi()
    api.window = FakeWindow()
    result = api.extract_archive(str(archive_path), same_folder=False)

    assert result is not None
    assert Path(result["path"]).parent == chosen_root.resolve()
    assert (Path(result["path"]) / "inside.txt").read_bytes() == b"extracted"


def _write_large_jpeg(path: Path) -> None:
    image = Image.effect_noise((640, 480), 90).convert("RGB")
    image.save(path, "JPEG", quality=98, subsampling=0)


def test_balanced_security_optimization_reduces_jpeg_without_resizing(tmp_path: Path):
    source = tmp_path / "photo.jpg"
    _write_large_jpeg(source)

    result = prepare_balanced_content(source, tmp_path / "balanced", source.name)

    assert result.applied is True
    assert result.output_bytes < result.original_bytes
    with Image.open(result.path) as optimized:
        assert optimized.size == (640, 480)
        optimized.verify()


def test_all_in_one_balanced_option_encrypts_reduced_content(tmp_path: Path):
    source = tmp_path / "photo.jpg"
    _write_large_jpeg(source)

    result = secure_local_file(source, PASSWORD, reduce_size=True)
    extracted = tmp_path / "reduced-content"
    with py7zr.SevenZipFile(result.output_path, "r", password=PASSWORD) as archive:
        archive.extractall(path=extracted)

    protected_content = extracted / source.name
    assert protected_content.stat().st_size < source.stat().st_size
    assert "Balanced image optimization" in result.note
    with Image.open(protected_content) as image:
        assert image.size == (640, 480)
        image.verify()


def test_all_in_one_encrypts_complete_folder_tree(tmp_path: Path):
    source = tmp_path / "project-folder"
    (source / "nested").mkdir(parents=True)
    (source / "readme.txt").write_bytes(b"root content")
    (source / "nested" / "data.bin").write_bytes(b"nested content")

    result = secure_local_file(source, PASSWORD)

    assert result.output_path == tmp_path / "project-folder_secured.7z"
    with py7zr.SevenZipFile(result.output_path, "r", password=PASSWORD) as archive:
        assert archive.needs_password() is True
        assert "project-folder/readme.txt" in archive.getnames()
        assert "project-folder/nested/data.bin" in archive.getnames()
        archive.extractall(path=tmp_path / "folder-roundtrip")
    assert (tmp_path / "folder-roundtrip" / "project-folder" / "readme.txt").read_bytes() == b"root content"
    assert (tmp_path / "folder-roundtrip" / "project-folder" / "nested" / "data.bin").read_bytes() == b"nested content"


def test_all_in_one_folder_moves_source_only_after_validation(tmp_path: Path, monkeypatch):
    source = tmp_path / "source-folder"
    source.mkdir()
    (source / "file.txt").write_bytes(b"keep safe")
    trashed: list[Path] = []
    monkeypatch.setattr(local_operations, "send2trash", lambda path: trashed.append(Path(path)))

    result = secure_local_file(source, PASSWORD, delete_original=True)

    assert result.original_trashed is True
    assert trashed == [source.resolve()]


def test_balanced_option_keeps_unsupported_file_unchanged(tmp_path: Path):
    source = tmp_path / "database.bin"
    source.write_bytes(b"arbitrary binary payload")

    result = prepare_balanced_content(source, tmp_path / "balanced", source.name)

    assert result.applied is False
    assert result.path == source.resolve()
    assert "encrypted the original unchanged" in result.note


def test_all_in_one_api_accepts_balanced_reduction_checkbox(tmp_path: Path):
    source = tmp_path / "upload.jpg"
    _write_large_jpeg(source)
    original = source.read_bytes()
    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/all-in-one",
            files={"file": (source.name, original, "image/jpeg")},
            data={"password": PASSWORD, "reduce_size": "true"},
        )

    assert response.status_code == 200
    assert "Balanced image optimization" in response.headers["x-archive-note"]
    archive_path = tmp_path / "balanced-secured.7z"
    archive_path.write_bytes(response.content)
    output = tmp_path / "api-balanced"
    with py7zr.SevenZipFile(archive_path, "r", password=PASSWORD) as archive:
        archive.extractall(path=output)
    assert (output / source.name).stat().st_size < len(original)


def test_extract_archive_upload_fallback_writes_to_downloads_and_opens_explorer(
    tmp_path: Path,
    monkeypatch,
):
    archive_path = tmp_path / "dragged.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("folder/result.txt", b"drag-and-drop works")
    downloads = tmp_path / "Downloads"
    opened: list[Path] = []
    monkeypatch.setattr(document_security_router, "_downloads_root", lambda: downloads)
    monkeypatch.setattr(document_security_router.os, "startfile", lambda path: opened.append(Path(path)))

    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/extract-upload",
            files={"file": (archive_path.name, archive_path.read_bytes(), "application/zip")},
            data={"password": ""},
        )

    assert response.status_code == 200
    payload = response.json()
    destination = Path(payload["path"])
    assert destination.parent == downloads.resolve()
    assert (destination / "folder" / "result.txt").read_bytes() == b"drag-and-drop works"
    assert opened == [destination]
    assert payload["explorer_opened"] is True


def test_sha256_accepts_any_file_type(tmp_path: Path):
    source = tmp_path / "sample-video.mp4"
    payload = b"not a real video, but arbitrary binary file content"
    source.write_bytes(payload)

    result = create_file_hash(source, source.name)

    assert result.name == "sample-video.mp4"
    assert result.bytes == len(payload)
    assert result.sha256 == hashlib.sha256(payload).hexdigest()


def test_sha256_folder_is_deterministic_and_tracks_progress(tmp_path: Path):
    source = tmp_path / "folder"
    (source / "nested").mkdir(parents=True)
    (source / "alpha.txt").write_bytes(b"alpha")
    (source / "nested" / "beta.bin").write_bytes(b"beta payload")
    progress = []

    first = create_path_hash(source, lambda *state: progress.append(state))
    second = create_path_hash(source)

    assert first == second
    assert first.kind == "folder"
    assert first.files == 2
    assert first.bytes == len(b"alpha") + len(b"beta payload")
    assert progress[-1][:4] == (first.bytes, first.bytes, 2, 2)

    (source / "nested" / "beta.bin").write_bytes(b"changed")
    assert create_path_hash(source).sha256 != first.sha256


def test_desktop_sha256_path_returns_folder_metadata(tmp_path: Path):
    source = tmp_path / "folder"
    source.mkdir()
    (source / "document.txt").write_bytes(b"desktop hash")

    result = DesktopApi().hash_security_path(str(source))

    assert result["name"] == "folder"
    assert result["kind"] == "folder"
    assert result["files"] == 1
    assert result["bytes"] == len(b"desktop hash")


def test_sha256_api_accepts_non_pdf_file():
    payload = b"arbitrary image bytes"
    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/sha256",
            files={"file": ("photo.webp", payload, "image/webp")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "name": "photo.webp",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_sha256_compare_api_accepts_any_file_types():
    left = b"arbitrary video-like bytes\x00\x01"
    right = b"arbitrary video-like bytes\x00\x02"
    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/sha256-compare",
            files={
                "left": ("clip.mov", left, "video/quicktime"),
                "right": ("archive.bin", right, "application/octet-stream"),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["identical"] is False
    assert payload["left"]["bytes"] == len(left)
    assert payload["right"]["bytes"] == len(right)
    assert payload["left"]["sha256"] == hashlib.sha256(left).hexdigest()
    assert payload["right"]["sha256"] == hashlib.sha256(right).hexdigest()


def test_password_protected_zip_uses_aes256(tmp_path: Path):
    source = tmp_path / "photo.png"
    source.write_bytes(b"private image bytes")
    output = tmp_path / "protected.zip"

    create_password_protected_zip(source, output, PASSWORD)

    with pyzipper.AESZipFile(output) as archive:
        archive.setpassword(PASSWORD.encode())
        info = archive.getinfo("photo.png")
        assert info.wz_aes_strength == 3  # WinZip AES strength 3 means AES-256.
        assert archive.read("photo.png") == source.read_bytes()

    with pyzipper.AESZipFile(output) as archive:
        archive.setpassword(b"incorrect-password")
        with pytest.raises(RuntimeError):
            archive.read("photo.png")


def test_precompressed_inputs_use_fast_store_mode(tmp_path: Path):
    source = tmp_path / "existing.zip"
    source.write_bytes(b"PK\x03\x04already-compressed-content")
    output = tmp_path / "protected.zip"

    result = create_password_protected_zip(source, output, PASSWORD)

    assert choose_archive_profile(source).mode == "store"
    assert result.mode == "store"
    with pyzipper.AESZipFile(output) as archive:
        archive.setpassword(PASSWORD.encode())
        info = archive.getinfo(source.name)
        assert info.compress_type == pyzipper.ZIP_STORED
        assert archive.read(source.name) == source.read_bytes()


def test_large_uncompressed_inputs_use_fast_deflate(tmp_path: Path, monkeypatch):
    source = tmp_path / "large-data.bin"
    source.write_bytes(b"uncompressed data")
    monkeypatch.setattr(archive_profiles, "FAST_THRESHOLD_BYTES", 1)
    encrypted = tmp_path / "large-data.7z"

    assert choose_archive_profile(source).mode == "fast-deflate"
    result = create_aes256_7z(source, encrypted, PASSWORD)
    assert result.mode == "fast-deflate"
    with py7zr.SevenZipFile(encrypted, mode="r", password=PASSWORD) as archive:
        archive.extractall(path=tmp_path / "fast-roundtrip")
    assert (tmp_path / "fast-roundtrip" / source.name).read_bytes() == source.read_bytes()


def test_all_in_one_api_reports_fast_mode_for_zip(tmp_path: Path):
    payload = b"PK\x03\x04existing archive payload"
    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/all-in-one",
            files={"file": ("bundle.zip", payload, "application/zip")},
            data={"password": PASSWORD},
        )

    assert response.status_code == 200
    assert response.headers["x-archive-mode"] == "store"
    encrypted = tmp_path / "bundle_secured.7z"
    encrypted.write_bytes(response.content)
    with py7zr.SevenZipFile(encrypted, mode="r", password=PASSWORD) as archive:
        archive.extractall(path=tmp_path / "roundtrip")
    assert (tmp_path / "roundtrip" / "bundle.zip").read_bytes() == payload


def test_plain_and_aes256_7z_archives(tmp_path: Path):
    source = tmp_path / "document.txt"
    source.write_text("private document", encoding="utf-8")
    plain = tmp_path / "document.7z"
    encrypted = tmp_path / "document_aes256.7z"

    create_7z_archive(source, plain)
    create_aes256_7z(source, encrypted, PASSWORD)

    with py7zr.SevenZipFile(plain, mode="r") as archive:
        assert archive.needs_password() is False
        assert archive.getnames() == ["document.txt"]
    with py7zr.SevenZipFile(encrypted, mode="r", password=PASSWORD) as archive:
        assert archive.needs_password() is True
        assert archive.getnames() == ["document.txt"]
        archive.extractall(path=tmp_path / "decrypted")
    assert (tmp_path / "decrypted" / "document.txt").read_text(encoding="utf-8") == "private document"


def test_short_password_and_stored_paths_are_rejected_or_sanitized(tmp_path: Path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"content")

    with pytest.raises(DocumentSecurityError, match="at least 8"):
        create_aes256_7z(source, tmp_path / "bad.7z", "short")

    output = tmp_path / "safe.7z"
    create_7z_archive(source, output, stored_name="../../safe-name.bin")
    with py7zr.SevenZipFile(output, mode="r") as archive:
        assert archive.getnames() == ["safe-name.bin"]


@pytest.mark.parametrize("kind", ["zip", "7z"])
def test_decrypt_returns_original_single_file(tmp_path: Path, kind: str):
    source = tmp_path / "report.txt"
    source.write_text("confidential report", encoding="utf-8")
    encrypted = tmp_path / f"encrypted.{kind}"
    if kind == "zip":
        create_password_protected_zip(source, encrypted, PASSWORD)
    else:
        create_aes256_7z(source, encrypted, PASSWORD)

    result = decrypt_archive(
        encrypted,
        tmp_path / "output",
        PASSWORD,
        archive_stem="encrypted",
        max_output_bytes=1024 * 1024,
    )

    assert result.download_name == "report.txt"
    assert result.file_count == 1
    assert result.path.read_text(encoding="utf-8") == "confidential report"


def test_decrypt_multiple_files_returns_plain_zip(tmp_path: Path):
    encrypted = tmp_path / "bundle.zip"
    with pyzipper.AESZipFile(
        encrypted,
        mode="w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as archive:
        archive.setpassword(PASSWORD.encode())
        archive.setencryption(pyzipper.WZ_AES, nbits=256)
        archive.writestr("first.txt", b"first")
        archive.writestr("nested/second.txt", b"second")

    result = decrypt_archive(
        encrypted,
        tmp_path / "output",
        PASSWORD,
        archive_stem="bundle",
        max_output_bytes=1024 * 1024,
    )

    assert result.file_count == 2
    assert result.download_name == "bundle_decrypted.zip"
    with zipfile.ZipFile(result.path) as archive:
        assert archive.read("first.txt") == b"first"
        assert archive.read("nested/second.txt") == b"second"


def test_decrypt_rejects_wrong_password_unsafe_paths_and_oversized_output(tmp_path: Path):
    encrypted = tmp_path / "unsafe.zip"
    with pyzipper.AESZipFile(
        encrypted,
        mode="w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as archive:
        archive.setpassword(PASSWORD.encode())
        archive.setencryption(pyzipper.WZ_AES, nbits=256)
        archive.writestr("../outside.txt", b"blocked")

    with pytest.raises(DocumentSecurityError, match="unsafe file path"):
        decrypt_archive(
            encrypted,
            tmp_path / "unsafe_output",
            PASSWORD,
            archive_stem="unsafe",
            max_output_bytes=1024,
        )

    safe = tmp_path / "safe.zip"
    source = tmp_path / "source.bin"
    source.write_bytes(b"more than one byte")
    create_password_protected_zip(source, safe, PASSWORD)
    with pytest.raises(DocumentSecurityError, match="exceeds"):
        decrypt_archive(
            safe,
            tmp_path / "large_output",
            PASSWORD,
            archive_stem="safe",
            max_output_bytes=1,
        )
    with pytest.raises(DocumentSecurityError, match="password may be incorrect"):
        decrypt_archive(
            safe,
            tmp_path / "wrong_password_output",
            "wrong-password",
            archive_stem="safe",
            max_output_bytes=1024,
        )


def test_decrypt_api_downloads_original_file(tmp_path: Path):
    source = tmp_path / "original.txt"
    source.write_bytes(b"api round trip")
    encrypted = tmp_path / "original_secured.7z"
    create_aes256_7z(source, encrypted, PASSWORD)

    with TestClient(app) as client:
        response = client.post(
            "/api/document-security/decrypt",
            files={
                "file": (
                    encrypted.name,
                    encrypted.read_bytes(),
                    "application/x-7z-compressed",
                )
            },
            data={"password": PASSWORD},
        )

    assert response.status_code == 200
    assert response.headers["x-decrypted-files"] == "1"
    assert "original.txt" in response.headers["content-disposition"]
    assert response.content == b"api round trip"


def test_decrypt_has_no_default_output_size_cap(tmp_path: Path):
    source = tmp_path / "large.bin"
    source.write_bytes(b"large local payload" * 100_000)
    encrypted = tmp_path / "large_secured.7z"
    create_aes256_7z(source, encrypted, PASSWORD)

    result = decrypt_archive(
        encrypted,
        tmp_path / "unlimited_output",
        PASSWORD,
        archive_stem="large",
    )

    assert result.file_count == 1
    assert result.path.stat().st_size == source.stat().st_size
    assert result.path.read_bytes() == source.read_bytes()
