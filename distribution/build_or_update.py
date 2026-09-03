from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SPEC = ROOT / "distribution" / "windows" / "LocalPDFWorkbench.spec"
BUILD_REQUIREMENTS = ROOT / "distribution" / "windows" / "requirements-build.txt"
RELEASE_APP = ROOT / "release" / "LocalPDFWorkbench"


def _run(command: list[str]) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _remove_generated(path: Path) -> None:
    resolved = path.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError(f"Refusing to remove path outside the project: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _ensure_pyinstaller() -> None:
    check = subprocess.run(
        [str(VENV_PYTHON), "-c", "import PyInstaller"],
        cwd=ROOT,
        capture_output=True,
    )
    if check.returncode:
        print("PyInstaller is missing; installing the build-only requirements once.")
        _run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(BUILD_REQUIREMENTS)])


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("This portable builder targets Windows only.")
    if not VENV_PYTHON.is_file():
        raise SystemExit(f"Project virtual environment not found: {VENV_PYTHON}")
    _ensure_pyinstaller()
    action = "Updating" if RELEASE_APP.exists() else "Creating"
    print(f"{action} Local PDF Workbench portable application...")
    for generated in (ROOT / "build", ROOT / "dist", RELEASE_APP):
        _remove_generated(generated)
    _run([str(VENV_PYTHON), "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC)])
    built = ROOT / "dist" / "LocalPDFWorkbench"
    if not (built / "LocalPDFWorkbench.exe").is_file():
        raise RuntimeError("PyInstaller finished without producing LocalPDFWorkbench.exe.")
    RELEASE_APP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built, RELEASE_APP)
    _remove_generated(ROOT / "build")
    _remove_generated(ROOT / "dist")
    print(f"\nDone. Portable app is ready at:\n{RELEASE_APP}")
    print("Share the entire LocalPDFWorkbench folder, not only the EXE.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PermissionError as exc:
        raise SystemExit(f"Close the running portable app and retry. {exc}") from exc
