import json
import os
import sys
import re
def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()

# コメントを送るパスリスト
BASE_DIR = os.path.join(get_base_dir(), "comment")
os.makedirs(BASE_DIR, exist_ok=True)

PATHS = [
    os.path.join(BASE_DIR, "PG-1.json"),
    os.path.join(BASE_DIR, "PG-2.json"),
    os.path.join(BASE_DIR, "PG-3.json"),
    os.path.join(BASE_DIR, "PG-4.json"),
    os.path.join(BASE_DIR, "PG-5.json"),
    os.path.join(BASE_DIR, "SQ-1.json"),
    os.path.join(BASE_DIR, "SQ-2.json"),
    os.path.join(BASE_DIR, "SQ-3.json"),
    os.path.join(BASE_DIR, "油槽.json")
]


def _sanitize_filename(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        return "unknown"
    # Windowsで使えない文字を避ける
    value = re.sub(r'[\\\\/:*?"<>|]+', "_", value)
    value = re.sub(r"\\s+", " ", value).strip()
    return value or "unknown"


def get_comment_path_by_name(furnace_name: str) -> str:
    safe = _sanitize_filename(furnace_name)
    return os.path.join(BASE_DIR, f"{safe}.json")

# ==========================================================
# コメント履歴読み込み
#
# 各炉ごとに保存されているコメント履歴(JSON)を読み込む。
# PATHS[index] に炉ごとの履歴ファイルが保存されている。
#
# ファイルが存在しない場合は空リストを返す。
#
# 戻り値
# [
#   {"time": "...", "comment": "..."},
#   ...
# ]
# ==========================================================
# 履歴保存用にload可能にする
def load_comment(index):

    path = PATHS[index]

    if not os.path.exists(path):
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return []
    

# ==========================================================
# コメント履歴保存
#
# 炉ごとのコメント履歴に新しいコメントを追加する。
#
# 保存形式(JSON)
# {
#     "time": 記録時刻
#     "comment": コメント内容
# }
#
# 処理手順
# 1. 既存履歴を読み込み
# 2. 新コメントを追加
# 3. JSONファイルへ保存
#
# ro_no
#   炉番号（PATHS配列のインデックス）
# ==========================================================
def comment(now_str, text, ro_no):
    data = {
            "time": now_str,
            "comment": text
        }
    # 既存のコメント履歴の読み込み
    tuiki = load_comment(ro_no)
    # 新しいコメントを追加
    tuiki.append(data)
    # リストからro_noで指定して上書き
    with open(PATHS[ro_no], "w", encoding="utf-8") as f:
        json.dump(tuiki, f, ensure_ascii=False, indent=2)


def load_comment_by_name(furnace_name: str):
    path = get_comment_path_by_name(furnace_name)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def comment_by_name(now_str: str, text: str, furnace_name: str):
    data = {"time": now_str, "comment": text}
    rows = load_comment_by_name(furnace_name)
    rows.append(data)
    path = get_comment_path_by_name(furnace_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
