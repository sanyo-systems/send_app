import argparse
import ctypes
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path


def _show_message(message: str, title: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000040)


def _show_error(message: str, title: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000010)


def _wait_for_process_exit(pid: int, timeout_seconds: float = 120.0) -> None:
    end_at = time.time() + timeout_seconds
    while time.time() < end_at:
        handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)
        if not handle:
            return
        ctypes.windll.kernel32.CloseHandle(handle)
        time.sleep(0.5)
    raise TimeoutError(f"PID {pid} did not exit within {timeout_seconds} seconds")


def _log(log_file: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [updater] {message}"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _remove_path_with_retries(path: Path, retries: int = 30, delay: float = 0.2) -> None:
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            if not path.exists():
                return
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
    if last_exc:
        raise last_exc


def _clear_install_dir(install_dir: Path) -> None:
    if not install_dir.exists():
        return
    for item in list(install_dir.iterdir()):
        _remove_path_with_retries(item)


def _normalize_extracted_root(extracted_dir: Path) -> Path:
    items = list(extracted_dir.iterdir())
    if len(items) == 1 and items[0].is_dir():
        return items[0]
    return extracted_dir


def run_update(
    *,
    pid: int,
    install_dir: Path,
    package: Path,
    app_exe: str,
    version_file: str,
    target_version: str,
) -> None:
    install_dir.mkdir(parents=True, exist_ok=True)
    log_file = install_dir / "update.log"

    _log(log_file, f"START pid={pid} install_dir={install_dir} package={package}")
    _wait_for_process_exit(pid)
    _log(log_file, "TARGET_EXITED")

    temp_root = Path(tempfile.mkdtemp(prefix="SendMarkerText_update_"))
    backup_dir = temp_root / "backup"
    extracted_dir = temp_root / "extracted"

    _log(log_file, f"EXTRACT_START temp={temp_root}")
    with zipfile.ZipFile(str(package), "r") as zf:
        zf.extractall(str(extracted_dir))
    extracted_root = _normalize_extracted_root(extracted_dir)
    _log(log_file, f"EXTRACT_DONE root={extracted_root}")

    _copy_tree(install_dir, backup_dir)
    _log(log_file, f"BACKUP_DONE backup={backup_dir}")

    try:
        _log(log_file, "COPY_NEW_START")
        _copy_tree(extracted_root, install_dir)
        _log(log_file, "COPY_NEW_DONE")

        version_path = install_dir / version_file
        version_path.write_text(
            json.dumps({"version": target_version}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _log(log_file, f"VERSION_UPDATED version={target_version} path={version_path}")
    except Exception as exc:
        _log(log_file, f"UPDATE_FAILED restoring_backup error={exc}")
        try:
            _copy_tree(backup_dir, install_dir)
        except Exception as exc2:
            _log(log_file, f"RESTORE_FAILED error={exc2}")
        raise

    app_path = Path(app_exe)
    if not app_path.is_absolute():
        app_path = install_dir / app_exe

    _log(log_file, f"RESTART app={app_path}")
    subprocess.Popen([str(app_path)], cwd=str(install_dir), close_fds=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--app-exe", required=True)
    parser.add_argument("--version-file", required=True)
    parser.add_argument("--target-version", required=True)
    args = parser.parse_args()

    try:
        run_update(
            pid=args.pid,
            install_dir=Path(args.install_dir),
            package=Path(args.package),
            app_exe=args.app_exe,
            version_file=args.version_file,
            target_version=args.target_version,
        )
        _show_message("アップデートが完了しました。アプリを再起動しました。", "SendMarkerText")
        return 0
    except Exception as exc:
        try:
            _log(Path(args.install_dir) / "update.log", f"FATAL {exc}")
        except Exception:
            pass
        _show_error(f"アップデートに失敗しました。\n{exc}", "SendMarkerText")
        return 1


if __name__ == "__main__":
    sys.exit(main())
