from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import re


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)


def _fail(message: str, *, exit_code: int = 1) -> "None":
    _eprint(message)
    raise SystemExit(exit_code)


def _find_repo_root(start: Path) -> Path:
    current = start
    for candidate in [current, *current.parents]:
        git_path = candidate / ".git"
        if git_path.exists():
            return candidate
    _fail(f"repo root not found from: {start}")


def _find_app_root(repo_root: Path) -> Path:
    ignore_dirs = {
        ".git",
        "__pycache__",
        "build",
        "dist",
        "venv",
        "venv32",
    }

    hits: list[Path] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        if "main.py" in files:
            hits.append(Path(root))

    if not hits:
        _fail(f"main.py not found under repo root: {repo_root}")
    if len(hits) > 1:
        joined = "\n".join(str(p) for p in hits)
        _fail(f"multiple main.py found; cannot decide app root:\n{joined}")
    return hits[0]


def _read_version_from_json(version_json: Path) -> str:
    if not version_json.exists():
        _fail(f"missing required file: {version_json}")
    try:
        data = json.loads(version_json.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(f"failed to read version.json: {version_json} error={exc}")
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        _fail(f"invalid version.json (expected {{\"version\":\"x.y.z\"}}): {version_json}")
    return version.strip()


def _select_spec(repo_root: Path, candidates: list[str]) -> Path:
    for name in candidates:
        spec = repo_root / name
        if spec.exists():
            return spec
    joined = ", ".join(candidates)
    _fail(f"spec file not found (tried: {joined}) under: {repo_root}")


def _run_pyinstaller(repo_root: Path, spec_path: Path, *, python_exe: Path | None = None) -> None:
    python = str((python_exe or Path(sys.executable)).resolve())
    cmd = [python, "-m", "PyInstaller", "--noconfirm", str(spec_path)]
    proc = subprocess.run(cmd, cwd=str(repo_root))
    if proc.returncode != 0:
        _fail(f"PyInstaller failed: spec={spec_path} exit_code={proc.returncode}")


def _default_venv32_python(repo_root: Path) -> Path | None:
    """
    Prefer using a 32-bit Python to build the updater exe.

    Notes:
    - PyInstaller's output architecture follows the Python interpreter used.
    - This project keeps a dedicated `venv32/` for 32-bit builds.
    """
    candidates = [
        repo_root / "venv32" / "Scripts" / "python.exe",
        repo_root / "venv32" / "python.exe",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _infer_dist_exe_from_spec(spec_path: Path) -> str:
    try:
        text = spec_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        _fail(f"failed to read spec file: {spec_path} error={exc}")
    matches = re.findall(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", text)
    if not matches:
        _fail(f"could not infer EXE name from spec (missing name=...): {spec_path}")
    exe_base = matches[-1].strip()
    if not exe_base:
        _fail(f"could not infer EXE name from spec (empty name): {spec_path}")
    return f"{exe_base}.exe"


def _ensure_file(path: Path) -> None:
    if not path.exists():
        _fail(f"missing required file: {path}")
    if not path.is_file():
        _fail(f"required path is not a file: {path}")


def _copy_optional_file(src: Path, dst_dir: Path) -> None:
    if not src.exists():
        return
    if not src.is_file():
        _fail(f"optional path exists but is not a file: {src}")
    shutil.copy2(src, dst_dir / src.name)


def _copy_optional_dir(src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.exists():
        return
    if not src_dir.is_dir():
        _fail(f"optional path exists but is not a directory: {src_dir}")
    shutil.copytree(src_dir, dst_dir / src_dir.name, dirs_exist_ok=True)


def _remove_if_exists(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _create_zip_flat(*, release_dir: Path, zip_path: Path) -> None:
    _remove_if_exists(zip_path)
    with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in release_dir.rglob("*"):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(release_dir).as_posix()
            zf.write(str(file_path), arcname=arcname)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build release folder and ZIP for SendMarkerText.")
    parser.add_argument("--version", help="Override version (default: read from version.json).")
    parser.add_argument("--skip-build", action="store_true", help="Skip PyInstaller build; use existing dist outputs.")
    parser.add_argument(
        "--updater-python",
        help=(
            "Python executable to build updater (default: auto-detect venv32/python.exe; fallback: current Python)."
        ),
    )
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(__file__).resolve().parent)
    app_root = _find_app_root(repo_root)

    version_json = app_root / "version.json"
    version = (args.version or "").strip() or _read_version_from_json(version_json)

    app_spec = _select_spec(repo_root, ["SendMarkerText.spec", "main.spec"])
    updater_spec = _select_spec(repo_root, ["SendMarkerText_updater.spec", "updater.spec"])

    if not args.skip_build:
        _run_pyinstaller(repo_root, app_spec)

        updater_python: Path | None = None
        if (args.updater_python or "").strip():
            updater_python = Path(args.updater_python).expanduser()
            if not updater_python.exists():
                _fail(f"--updater-python not found: {updater_python}")
        else:
            updater_python = _default_venv32_python(repo_root)

        _run_pyinstaller(repo_root, updater_spec, python_exe=updater_python)

    dist_dir = repo_root / "dist"
    app_exe_src = dist_dir / _infer_dist_exe_from_spec(app_spec)
    updater_exe_src = dist_dir / _infer_dist_exe_from_spec(updater_spec)

    _ensure_file(app_exe_src)
    _ensure_file(updater_exe_src)
    _ensure_file(version_json)

    release_dir = dist_dir / f"SendMarkerText_{version}"
    zip_path = dist_dir / f"SendMarkerText_{version}.zip"

    _remove_if_exists(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(app_exe_src, release_dir / app_exe_src.name)
    shutil.copy2(updater_exe_src, release_dir / "SendMarkerText_updater.exe")
    shutil.copy2(version_json, release_dir / "version.json")

    _copy_optional_file(repo_root / ".env", release_dir)
    _copy_optional_dir(repo_root / "resources", release_dir)
    _copy_optional_dir(repo_root / "templates", release_dir)

    _create_zip_flat(release_dir=release_dir, zip_path=zip_path)

    print(f"release_dir={release_dir.resolve()}")
    print(f"zip_path={zip_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
