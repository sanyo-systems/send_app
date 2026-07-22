import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import ctypes
import re

# このファイルは配布版 exe の自己更新判定を担当する。
# 共有フォルダ上の manifest/version/package を見て更新可否を決め、
# 実更新は別プロセスの updater.exe へ委譲する。


DEFAULT_SHARE_DIR = r"\\192.168.203.202\\SendMarkerText"
LEGACY_SHARE_DIR = r"\\192.168.203.202\\Sprint\\SendMarkerText"
DEFAULT_VERSION_FILE_NAME = "version.json"
DEFAULT_MANIFEST_NAME = "manifest.json"
DEFAULT_SETTING_INI_NAME = "Setting.ini"


@dataclass(frozen=True)
class UpdateManifest:
    latest_version: str
    package_type: str
    package_path: str
    force_update: bool = False
    message: str = ""


@dataclass(frozen=True)
class UpdateDecision:
    update_available: bool
    current_version: str
    target_version: str
    manifest: UpdateManifest | None = None
    resolved_package: Path | None = None


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _get_install_dir() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _parse_version(value: str) -> tuple[int, int, int]:
    raw = str(value or "").strip()
    parts = raw.split(".")
    nums: list[int] = []
    for part in parts[:3]:
        try:
            nums.append(int(part))
        except Exception:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _message_box_yes_no(title: str, message: str) -> bool:
    # MB_YESNO=0x00000004, MB_ICONQUESTION=0x00000020, MB_SETFOREGROUND=0x00010000
    result = ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000004 | 0x00000020 | 0x00010000)
    return result == 6  # IDYES


def _normalize_share_dir(raw: str) -> str:
    """
    Normalize UPDATE_SHARE_DIR-like values.

    Some environments accidentally set a UNC path with a single leading backslash
    (e.g. `\\192...` becomes `\192...`). That becomes a drive-rooted path on Windows
    and breaks update checks. If it looks like an IPv4 UNC missing a backslash,
    fix it.
    """
    value = str(raw or "").strip()
    if value.startswith("\\") and not value.startswith("\\\\"):
        head = value.lstrip("\\")
        if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}\\", head):
            return "\\\\" + head
    return value


def _read_setting_ini_overrides(install_dir: Path) -> dict[str, str]:
    """
    Read share-dir overrides from Setting.ini.

    This project uses `configparser` for most settings, but for these overrides we
    allow simple `KEY=VALUE` lines anywhere in the file (even outside sections),
    because users may paste them without INI sections.

    Supported keys:
    - DEFAULT_SHARE_DIR
    - LEGACY_SHARE_DIR
    """
    path = install_dir / DEFAULT_SETTING_INI_NAME
    if not path.exists() or not path.is_file():
        return {}

    try:
        text = path.read_text(encoding="shift_jis", errors="replace")
    except Exception:
        return {}

    overrides: dict[str, str] = {}
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith(("#", ";")):
            continue
        if raw.startswith("[") and raw.endswith("]"):
            continue

        m = re.match(r"^(DEFAULT_SHARE_DIR|LEGACY_SHARE_DIR)\s*=\s*(.+?)\s*$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        value = str(value).strip().strip('"').strip("'")
        if value:
            overrides[key] = value

    return overrides


class UpdateService:
    def __init__(self) -> None:
        # 環境変数を最優先しつつ、現場配布版では Setting.ini の上書きも許容する。
        self.install_dir = Path(os.environ.get("INSTALL_DIR") or _get_install_dir()).resolve()
        raw_share_dir = os.environ.get("UPDATE_SHARE_DIR")
        self._share_dir_configured = bool(raw_share_dir)
        ini_overrides = _read_setting_ini_overrides(self.install_dir)

        default_share_dir = ini_overrides.get("DEFAULT_SHARE_DIR") or DEFAULT_SHARE_DIR
        self.legacy_share_dir = Path(_normalize_share_dir(ini_overrides.get("LEGACY_SHARE_DIR") or LEGACY_SHARE_DIR))

        self.share_dir = Path(_normalize_share_dir(raw_share_dir or default_share_dir))
        self.version_file_name = os.environ.get("VERSION_FILE_NAME") or DEFAULT_VERSION_FILE_NAME
        self.manifest_name = os.environ.get("MANIFEST_NAME") or DEFAULT_MANIFEST_NAME

    def _auto_fallback_share_dir(self, share_dir: Path, manifest_name: str) -> Path | None:
        # UNC 直指定が失敗しても、net use 済みドライブから manifest を探し直す。
        try:
            if share_dir.exists():
                manifest = share_dir / manifest_name
                return share_dir if manifest.exists() else None
        except Exception:
            return None

        raw = str(share_dir)
        if not raw.startswith("\\\\"):
            return None

        try:
            proc = subprocess.run(
                ["net", "use"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return None

        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        unc = raw.rstrip("\\")
        share_leaf = share_dir.name

        mapped_drives: list[str] = []
        for line in text.splitlines():
            drive = None
            for token in line.split():
                if len(token) == 2 and token[1] == ":" and token[0].isalpha():
                    drive = token.upper()
                    break
            if drive and drive not in mapped_drives:
                mapped_drives.append(drive)

        # Prefer a mapping whose remote UNC contains the target UNC.
        for line in text.splitlines():
            if unc.lower() not in line.lower():
                continue
            drive = None
            for token in line.split():
                if len(token) == 2 and token[1] == ":" and token[0].isalpha():
                    drive = token.upper()
                    break
            if not drive:
                continue
            base = Path(drive + "\\")
            for candidate in [base, base / share_leaf]:
                try:
                    if (candidate / manifest_name).exists():
                        return candidate
                except Exception:
                    continue

        # Otherwise, try common layouts on any mapped drive.
        for drive in mapped_drives:
            base = Path(drive + "\\")
            for candidate in [base / share_leaf]:
                try:
                    if (candidate / manifest_name).exists():
                        return candidate
                except Exception:
                    continue

        return None

    def is_enabled(self) -> bool:
        if _is_frozen():
            return True
        return os.environ.get("ENABLE_UPDATE_CHECK") == "1"

    def _version_file_path(self) -> Path:
        return self.install_dir / self.version_file_name

    def load_local_version(self) -> str:
        path = self._version_file_path()
        if not path.exists():
            return "0.0.0"
        try:
            data = _read_json(path)
            if isinstance(data, dict) and "version" in data:
                return str(data["version"]).strip() or "0.0.0"
        except Exception:
            pass
        return "0.0.0"

    def load_manifest(self) -> UpdateManifest:
        # 共有パスは現場差分が大きいため、既定 -> 旧既定 -> マップドドライブ救済の順で探索する。
        manifest_path = self.share_dir / self.manifest_name
        if not manifest_path.exists():
            tried: list[Path] = [self.share_dir]

            # If UPDATE_SHARE_DIR is not explicitly configured, try legacy defaults.
            if not self._share_dir_configured:
                for candidate in [self.legacy_share_dir]:
                    if candidate in tried:
                        continue
                    tried.append(candidate)
                    candidate_manifest = candidate / self.manifest_name
                    if candidate_manifest.exists():
                        self.share_dir = candidate
                        manifest_path = candidate_manifest
                        break

        if not manifest_path.exists():
            fallback_dir = self._auto_fallback_share_dir(self.share_dir, self.manifest_name)
            if fallback_dir:
                self.share_dir = fallback_dir
                manifest_path = self.share_dir / self.manifest_name

        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {manifest_path}")
        data = _read_json(manifest_path)
        return UpdateManifest(
            latest_version=str(data.get("latest_version") or "").strip(),
            package_type=str(data.get("package_type") or "").strip(),
            package_path=str(data.get("package_path") or "").strip(),
            force_update=bool(data.get("force_update") or False),
            message=str(data.get("message") or "").strip(),
        )

    def resolve_package_path(self, package_path: str) -> Path:
        # manifest の package_path は share_dir 直下/ packages 配下の両方を許容する。
        raw = str(package_path or "").strip()
        if not raw:
            raise ValueError("package_path is empty")

        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate

        first = self.share_dir / raw
        if first.exists():
            return first

        second = self.share_dir / "packages" / raw
        if second.exists():
            return second

        # fallback for callers that want an explicit missing-file error
        return first

    def check_for_update(self) -> UpdateDecision:
        current_version = self.load_local_version()
        manifest = self.load_manifest()

        if not manifest.latest_version:
            return UpdateDecision(False, current_version, current_version, manifest=manifest)

        if manifest.package_type.lower() != "zip":
            raise ValueError(f"unsupported package_type: {manifest.package_type}")

        if not _is_newer(manifest.latest_version, current_version):
            return UpdateDecision(False, current_version, current_version, manifest=manifest)

        package = self.resolve_package_path(manifest.package_path)
        if not package.exists():
            raise FileNotFoundError(f"package not found: {package}")

        return UpdateDecision(
            True,
            current_version=current_version,
            target_version=manifest.latest_version,
            manifest=manifest,
            resolved_package=package,
        )

    def confirm_update(self, decision: UpdateDecision) -> bool:
        manifest = decision.manifest
        if not manifest:
            return False

        lines = [
            f"更新があります: {decision.current_version} -> {decision.target_version}",
        ]
        if manifest.message:
            lines.append("")
            lines.append(str(manifest.message))
        if manifest.force_update:
            lines.append("")
            lines.append("この更新は必須です。拒否するとアプリを終了します。")

        return _message_box_yes_no("SendMarkerText 更新", "\n".join(lines))

    def _detect_app_exe_name(self) -> str:
        if _is_frozen():
            return Path(sys.executable).name
        return os.environ.get("APP_EXE_NAME") or "main.exe"

    def _detect_updater_name(self) -> str:
        configured = os.environ.get("UPDATER_EXE_NAME")
        if configured:
            return configured

        preferred = "SendMarkerText_updater.exe"
        if (self.install_dir / preferred).exists():
            return preferred

        if (self.install_dir / "updater.exe").exists():
            return "updater.exe"

        return preferred

    def build_updater_command(self, decision: UpdateDecision) -> list[str]:
        if not decision.update_available or not decision.resolved_package:
            raise ValueError("no update to launch")

        updater_name = self._detect_updater_name()
        updater_path = (self.install_dir / updater_name).resolve()
        if not updater_path.exists():
            raise FileNotFoundError(f"updater not found: {updater_path}")

        # updater 自身が更新対象に含まれても実行継続できるよう、一時コピーを起動する。
        temp_dir = Path(tempfile.mkdtemp(prefix="SendMarkerText_updater_"))
        temp_updater = temp_dir / updater_path.name
        temp_updater.write_bytes(updater_path.read_bytes())

        app_exe = self._detect_app_exe_name()
        version_file = self.version_file_name

        return [
            str(temp_updater),
            "--pid",
            str(os.getpid()),
            "--install-dir",
            str(self.install_dir),
            "--package",
            str(decision.resolved_package),
            "--app-exe",
            app_exe,
            "--version-file",
            version_file,
            "--target-version",
            decision.target_version,
        ]

    def launch_updater(self, decision: UpdateDecision) -> None:
        # 親プロセスはこの後終了するため、待機せず別プロセスで起動する。
        cmd = self.build_updater_command(decision)
        logging.info(f"UPDATE_LAUNCH_UPDATER cmd={cmd!r}")
        subprocess.Popen(cmd, close_fds=True)
