import configparser
import os
import sys

# このファイルは Setting.ini の読み込み窓口。
# 他モジュールはここで正規化済みの設定値を参照する。

def normalize_config_path(raw_path):
    path = str(raw_path).strip().strip('"').strip("'")
    if not path:
        return path

    # 現場設定で UNC が短く書かれている場合の救済。
    if path.startswith("\\\\"):
        parts = path[2:].split("\\")
        if len(parts) == 2 and parts[1].lower().endswith((".accdb", ".mdb")):
            candidate = f"\\\\{parts[0]}\\Sprint\\{parts[1]}"
            if os.path.exists(candidate):
                return candidate

    return path


def get_base_dir():
    # exe 配布時は exe 配置場所、ソース実行時はリポジトリ直下を基準にする。
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()

DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "Setting.ini")

_bootstrap_config = configparser.ConfigParser()
_bootstrap_config.read(DEFAULT_CONFIG_PATH, encoding="shift_jis")

def _get_ui_rec_type_value(config_obj):
    if config_obj.has_option("SECTION_1", "UI_REC_TYPE"):
        return config_obj.get("SECTION_1", "UI_REC_TYPE", fallback="PIT")
    return config_obj.get("SECTION_1", "UI_REC_TYP", fallback="PIT")


UI_REC_TYPE_RAW = _get_ui_rec_type_value(_bootstrap_config)


def _normalize_recorder_type(value):
    raw = str(value or "").strip()
    if not raw:
        return "PIT"
    if raw in ("焼準", "焼入焼戻", "SA"):
        return raw
    upper = raw.upper()
    if upper == "HNR":
        return "\u713c\u6e96"
    if upper == "HQ":
        return "\u713c\u5165\u713c\u623b"
    if upper in ("BATCH_G", "BATCH_GIFU"):
        return "BATCH"
    return upper


UI_REC_TYPE = _normalize_recorder_type(UI_REC_TYPE_RAW)

CONFIG_PATH = DEFAULT_CONFIG_PATH

config = configparser.ConfigParser()
config.read(CONFIG_PATH, encoding="shift_jis")


def _get_config(section: str, key: str, fallback: str = "") -> str:
    if config.has_option(section, key):
        return config.get(section, key, fallback=fallback)
    return fallback


def _get_config_bool(section: str, key: str, fallback: bool = True) -> bool:
    raw = _get_config(section, key, fallback="1" if fallback else "0")
    normalized = str(raw or "").strip().lower()
    if normalized in ("1", "true", "on", "yes"):
        return True
    if normalized in ("0", "false", "off", "no"):
        return False
    return fallback


CSV_FOLDER = _get_config("SECTION_1", "CSV_FOLDER1", fallback="") or _get_config("SECTION_1", "CSV_FOLDER", fallback="")
CSV_FOLDER2 = _get_config("SECTION_1", "CSV_FOLDER2", fallback="")
DEFAULT_SHARE_DIR = _get_config("SECTION_1", "DEFAULT_SHARE_DIR", fallback="")
SENT_RIGHT = _get_config_bool("SECTION_1", "SENT_RIGHT", fallback=True)
PLC_MODE = (_get_config("SECTION_1", "PLC_MODE", fallback="REAL") or "REAL").strip().upper()
try:
    WAIT_TIME1_MS = int(_get_config("SECTION_1", "WAIT_TIME1", fallback="500") or "500")
except ValueError:
    WAIT_TIME1_MS = 500

try:
    PLC_LOGICAL_STATION_NUMBER = int(
        _get_config("SECTION_1", "ACT_LOGICAL_STATION_NUMBER", fallback="1") or "1"
    )
except ValueError:
    PLC_LOGICAL_STATION_NUMBER = 1

ACCESS_FILE = normalize_config_path(_get_config("SECTION_1", "ACCESS_FILE", fallback=""))
ACCESS_FILE_2 = normalize_config_path(_get_config("SECTION_1", "ACCESS_FILE_2", fallback=""))


RECORDER_CONFIG = []

last_ip = None
current_group_no = 0

# 焼入焼戻は単一設備前提の設定形式を優先して構成する。
if UI_REC_TYPE == "焼入焼戻":
    ip = _get_config("SECTION_1", "RECORDER_IP_ADRESS", fallback=None) or _get_config("SECTION_1", "RECORDER_IP_ADRESS1", fallback=None)
    port_raw = _get_config("SECTION_1", "RECORDER_PORT", fallback="502") or _get_config("SECTION_1", "RECORDER_PORT1", fallback="502")
    file = _get_config("SECTION_1", "CSV_FILE", fallback=None) or _get_config("SECTION_1", "CSV_FILE1", fallback=None)
    try:
        port = int(port_raw)
    except Exception:
        port = 502

    if ip and file:
        RECORDER_CONFIG.append({
            "no": 1,
            "file": file,
            "ip": ip,
            "port": port,
            "group_no": 1,
            "type": UI_REC_TYPE,
            "group_name": "",
        })
else:
    # PIT/BATCH 系は連番設定を走査し、同一IPごとに group_no を振り直す。
    i = 1
    while True:
        ip = config.get("SECTION_1", f"RECORDER_IP_ADRESS{i}", fallback=None)

        if ip is None:
            break

        port = config.getint("SECTION_1", f"RECORDER_PORT{i}", fallback=502)
        file = config.get("SECTION_1", f"CSV_FILE{i}", fallback=None)
        rec_type = _normalize_recorder_type(config.get("SECTION_1", f"RECORDER_TYPE{i}", fallback="PIT"))

        if rec_type != UI_REC_TYPE:
            i += 1
            continue

        if ip != last_ip:
            current_group_no = 1
        else:
            current_group_no += 1

        RECORDER_CONFIG.append({
            "no": i,
            "file": file,
            "ip": ip,
            "port": port,
            "group_no": current_group_no,
            "type": rec_type,
            "group_name": config.get("SECTION_1", f"RECORDER_GROUP_NAME{i}", fallback="")
        })

        last_ip = ip
        i += 1
