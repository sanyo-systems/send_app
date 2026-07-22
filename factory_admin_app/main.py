from datetime import datetime
from pathlib import Path

import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from psycopg2.extras import Json, RealDictCursor
from communication.config_loader import WAIT_TIME1_MS
from communication.recorder_client import normalize_recorder_text, send_with_retry
from ui.coment import comment_by_name


BASE_DIR = Path(__file__).resolve().parent
PORTAL_HTML_PATH = BASE_DIR / "portal.html"
INDEX_HTML_PATH = BASE_DIR / "index.html"
ADMIN_HTML_PATH = BASE_DIR / "admin.html"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    database_url_common: str = Field(..., alias="DATABASE_URL_COMMON")
    allowed_origins_raw: str = Field(default="", alias="ALLOWED_ORIGINS")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]


settings = AppSettings()

app = FastAPI(title="Check Record Admin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FactoryCreateRequest(BaseModel):
    factory_name: str = Field(..., min_length=1, max_length=50)
    display_order: int | None = None


class RecorderIpCreateRequest(BaseModel):
    ip_address: str = Field(..., min_length=1, max_length=45)
    port_no: int = 502
    group_no: int | None = None


class FurnaceRecorderMapCreateRequest(BaseModel):
    equipment_id: str
    equipment_group_id: str | None = None
    factory_id: int
    recorder_ip_id: int
    csv_file_name: str | None = Field(default=None, max_length=100)


class CheckRecordCreateRequest(BaseModel):
    equipment_id: str
    equipment_group_id: str | None = None
    factory_id: int
    recorder_ip_id: int | None = None
    check_type: str = Field(..., min_length=2, max_length=10)
    confirmed_by: str = Field(..., min_length=1, max_length=100)
    display_text: str = Field(..., min_length=1)
    raw_value_json: dict | list | None = None


class BatchCheckRecordCreateRequest(BaseModel):
    check_type: str = Field(..., min_length=2, max_length=10)
    confirmed_by: str = Field(..., min_length=1, max_length=100)
    furnace_records: list[dict]


class CommentCreateRequest(BaseModel):
    equipment_id: str
    comment_text: str = Field(..., min_length=1)


def build_sync_database_url() -> str:
    return settings.database_url_common.replace("postgresql+asyncpg://", "postgresql://", 1)


def get_connection():
    return psycopg2.connect(build_sync_database_url())


def build_check_record_date_condition(date_filter: str) -> str:
    if date_filter == "yesterday":
        return "CURRENT_DATE - INTERVAL '1 day'"
    if date_filter == "day_before_yesterday":
        return "CURRENT_DATE - INTERVAL '2 day'"
    return "CURRENT_DATE"


def normalize_check_type(check_type: str) -> str:
    normalized = check_type.strip().upper()
    if normalized not in {"1H", "4H"}:
        raise HTTPException(status_code=400, detail="check_type must be 1H or 4H")
    return normalized


def resolve_confirming_user(cursor, confirmed_by: str) -> dict:
    confirmed_by_value = confirmed_by.strip()
    if not confirmed_by_value:
        raise HTTPException(status_code=400, detail="確認者を入力してください。")

    select_sql = """
    SELECT
        id AS employee_id,
        employee_code,
        name AS employee_name
    FROM users
    WHERE is_active = TRUE
      AND (employee_code = %s OR CAST(id AS TEXT) = %s)
    ORDER BY employee_code ASC, name ASC
    LIMIT 1
    """
    cursor.execute(select_sql, (confirmed_by_value, confirmed_by_value))
    user_row = cursor.fetchone()
    if user_row is None:
        raise HTTPException(status_code=400, detail="入力された確認者は存在しない番号のため登録できません")
    return dict(user_row)


def fetch_single_context(cursor, equipment_id: str) -> dict:
    select_sql = """
    SELECT
        frm.furnace_recorder_map_id,
        frm.equipment_id,
        e.name AS equipment_name,
        frm.equipment_group_id,
        eg.name AS equipment_group_name,
        frm.factory_id,
        f.factory_name,
        frm.recorder_ip_id,
        ri.ip_address,
        ri.group_no,
        CONCAT(ri.ip_address, ' / Group ', ri.group_no) AS recorder_ip_display
    FROM furnace_recorder_map frm
    JOIN equipment e
        ON frm.equipment_id = e.id
    LEFT JOIN equipment_groups eg
        ON frm.equipment_group_id = eg.id
    JOIN factory f
        ON frm.factory_id = f.factory_id
    LEFT JOIN recorder_ip ri
        ON frm.recorder_ip_id = ri.recorder_ip_id
    WHERE frm.is_active = TRUE
      AND frm.equipment_id = %s
    ORDER BY frm.furnace_recorder_map_id ASC
    LIMIT 1
    """
    cursor.execute(select_sql, (equipment_id,))
    context = cursor.fetchone()
    if context is None:
        raise HTTPException(status_code=404, detail="single context not found")
    return dict(context)


@app.get("/", response_class=HTMLResponse)
def get_portal() -> str:
    return PORTAL_HTML_PATH.read_text(encoding="utf-8")


@app.get("/portal", response_class=HTMLResponse)
def get_portal_page() -> str:
    return PORTAL_HTML_PATH.read_text(encoding="utf-8")


@app.get("/portal.html", response_class=HTMLResponse)
def get_portal_html() -> str:
    return PORTAL_HTML_PATH.read_text(encoding="utf-8")


@app.get("/index", response_class=HTMLResponse)
def get_index() -> str:
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/index.html", response_class=HTMLResponse)
def get_index_html() -> str:
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse)
def get_admin() -> str:
    return ADMIN_HTML_PATH.read_text(encoding="utf-8")


@app.get("/admin.html", response_class=HTMLResponse)
def get_admin_html() -> str:
    return ADMIN_HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/factories")
def list_factories() -> list[dict]:
    select_sql = """
    SELECT
        factory_id,
        factory_name,
        display_order,
        is_active,
        created_at,
        updated_at
    FROM factory
    ORDER BY display_order ASC NULLS LAST, factory_id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/recorder-ips")
def list_recorder_ips() -> list[dict]:
    select_sql = """
    SELECT
        recorder_ip_id,
        ip_address,
        port_no,
        group_no,
        is_active,
        created_at,
        updated_at
    FROM recorder_ip
    ORDER BY recorder_ip_id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/equipment-options")
def list_equipment_options() -> list[dict]:
    select_sql = """
    SELECT
        id AS equipment_id,
        name
    FROM equipment
    ORDER BY name ASC, id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/equipment-group-options")
def list_equipment_group_options() -> list[dict]:
    select_sql = """
    SELECT
        id AS equipment_group_id,
        name
    FROM equipment_groups
    ORDER BY name ASC, id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/factory-options")
def list_factory_options() -> list[dict]:
    select_sql = """
    SELECT
        factory_id,
        factory_name
    FROM factory
    WHERE is_active = TRUE
    ORDER BY display_order ASC NULLS LAST, factory_id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/recorder-ip-options")
def list_recorder_ip_options() -> list[dict]:
    select_sql = """
    SELECT
        recorder_ip_id,
        ip_address,
        group_no
    FROM recorder_ip
    WHERE is_active = TRUE
    ORDER BY recorder_ip_id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/portal/group-options")
def list_portal_group_options() -> list[dict]:
    select_sql = """
    SELECT DISTINCT
        eg.id AS equipment_group_id,
        eg.name
    FROM furnace_recorder_map frm
    JOIN equipment_groups eg
        ON frm.equipment_group_id = eg.id
    WHERE frm.is_active = TRUE
    ORDER BY eg.name ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/portal/equipment-options")
def list_portal_equipment_options(group_id: str = Query(...)) -> list[dict]:
    select_sql = """
    SELECT
        e.id AS equipment_id,
        e.name,
        COALESCE(e.sort_order, 2147483647) AS sort_order
    FROM furnace_recorder_map frm
    JOIN equipment e
        ON frm.equipment_id = e.id
    WHERE frm.is_active = TRUE
      AND frm.equipment_group_id = %s
    GROUP BY e.id, e.name, e.sort_order
    ORDER BY sort_order ASC, e.name ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql, (group_id,))
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/check-record-context/single")
def get_single_check_record_context(equipment_id: str = Query(...)) -> dict:
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            return fetch_single_context(cursor, equipment_id)


@app.get("/api/check-record-context/batch")
def get_batch_check_record_context(group_id: str = Query(...)) -> dict:
    group_sql = """
    SELECT id AS equipment_group_id, name
    FROM equipment_groups
    WHERE id = %s
    """
    furnace_sql = """
    SELECT
        frm.furnace_recorder_map_id,
        frm.equipment_id,
        e.name AS equipment_name,
        frm.equipment_group_id,
        frm.factory_id,
        f.factory_name,
        frm.recorder_ip_id,
        ri.ip_address,
        ri.group_no,
        CONCAT(ri.ip_address, ' / Group ', ri.group_no) AS recorder_ip_display
    FROM furnace_recorder_map frm
    JOIN equipment e
        ON frm.equipment_id = e.id
    LEFT JOIN factory f
        ON frm.factory_id = f.factory_id
    LEFT JOIN recorder_ip ri
        ON frm.recorder_ip_id = ri.recorder_ip_id
    WHERE frm.is_active = TRUE
      AND frm.equipment_group_id = %s
    ORDER BY
        CASE
            WHEN %s = 'ピット' THEN
                CASE e.name
                    WHEN 'PG-1' THEN 1
                    WHEN 'SQ-1' THEN 2
                    WHEN 'PG-5' THEN 3
                    WHEN 'PG-2' THEN 4
                    WHEN '油槽' THEN 5
                    WHEN 'ピット輸送' THEN 6
                    WHEN 'SQ-2' THEN 7
                    WHEN 'PG-4' THEN 8
                    WHEN 'PG-3' THEN 9
                    WHEN 'SQ-3' THEN 10
                    ELSE 999
                END
            ELSE COALESCE(e.sort_order, 2147483647)
        END ASC,
        e.name ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(group_sql, (group_id,))
            group_row = cursor.fetchone()
            if group_row is None:
                raise HTTPException(status_code=404, detail="batch group not found")
            cursor.execute(furnace_sql, (group_id, group_row["name"]))
            furnaces = [dict(row) for row in cursor.fetchall()]
    return {
        "equipment_group_id": group_row["equipment_group_id"],
        "equipment_group_name": group_row["name"],
        "furnaces": furnaces,
    }


@app.get("/api/furnace-recorder-maps")
def list_furnace_recorder_maps() -> list[dict]:
    select_sql = """
    SELECT
        frm.furnace_recorder_map_id,
        frm.equipment_id,
        e.name AS equipment_name,
        frm.equipment_group_id,
        eg.name AS equipment_group_name,
        frm.factory_id,
        f.factory_name,
        frm.recorder_ip_id,
        ri.ip_address,
        ri.group_no,
        CONCAT(ri.ip_address, ' / Group ', ri.group_no) AS recorder_ip_display,
        frm.csv_file_name,
        frm.is_active,
        frm.created_at,
        frm.updated_at
    FROM furnace_recorder_map frm
    LEFT JOIN equipment e ON frm.equipment_id = e.id
    LEFT JOIN equipment_groups eg ON frm.equipment_group_id = eg.id
    LEFT JOIN factory f ON frm.factory_id = f.factory_id
    LEFT JOIN recorder_ip ri ON frm.recorder_ip_id = ri.recorder_ip_id
    ORDER BY frm.furnace_recorder_map_id ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/check-records/single")
def list_single_check_records(
    equipment_id: str = Query(...),
    date_filter: str = Query(default="today"),
) -> list[dict]:
    date_condition = build_check_record_date_condition(date_filter)
    select_sql = f"""
    SELECT
        cr.check_record_id,
        cr.check_type,
        cr.check_hour,
        cr.display_text,
        cr.record_time,
        cr.created_at,
        TO_CHAR(cr.record_time, 'MM/DD') AS record_date_label,
        TO_CHAR(cr.created_at, 'HH24:MI:SS') AS input_time_label,
        e.name AS equipment_name,
        eg.name AS equipment_group_name,
        f.factory_name,
        u.name AS employee_name,
        ri.ip_address,
        ri.group_no,
        CONCAT(ri.ip_address, ' / Group ', ri.group_no) AS recorder_ip_display,
        COALESCE(cr.raw_value_json ->> 'temperature_1', '-') AS temperature_1,
        COALESCE(cr.raw_value_json ->> 'temperature_2', '-') AS temperature_2,
        COALESCE(cr.raw_value_json ->> 'conveyor_speed', '-') AS conveyor_speed,
        COALESCE(cr.raw_value_json ->> 'conveyor_speed_ht', '-') AS conveyor_speed_ht,
        COALESCE(NULLIF(cr.raw_value_json ->> 'confirmed_by_name', ''), u.name, '-') AS confirmed_by
    FROM check_record cr
    LEFT JOIN equipment e ON cr.equipment_id = e.id
    LEFT JOIN equipment_groups eg ON cr.equipment_group_id = eg.id
    LEFT JOIN factory f ON cr.factory_id = f.factory_id
    LEFT JOIN users u ON cr.employee_id = u.id
    LEFT JOIN recorder_ip ri ON cr.recorder_ip_id = ri.recorder_ip_id
    WHERE DATE(cr.record_time) = {date_condition}
      AND cr.equipment_id = %s
      AND cr.check_type IN ('1H', '4H')
    ORDER BY cr.record_time DESC, cr.check_record_id DESC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql, (equipment_id,))
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/check-records/batch")
def list_batch_check_records(
    group_id: str = Query(...),
    date_filter: str = Query(default="today"),
) -> list[dict]:
    date_condition = build_check_record_date_condition(date_filter)
    select_sql = f"""
    WITH ranked_records AS (
        SELECT
            cr.check_record_id,
            cr.check_type,
            cr.check_hour,
            cr.display_text,
            cr.record_time,
            cr.created_at,
            TO_CHAR(cr.record_time, 'MM/DD') AS record_date_label,
            TO_CHAR(cr.created_at, 'HH24:MI:SS') AS input_time_label,
            e.id AS equipment_id,
            e.name AS equipment_name,
            eg.id AS equipment_group_id,
            eg.name AS equipment_group_name,
            COALESCE(cr.raw_value_json ->> 'temperature_1', '-') AS temperature_1,
            COALESCE(cr.raw_value_json ->> 'temperature_2', '-') AS temperature_2,
            COALESCE(cr.raw_value_json ->> 'measured_temperature', '-') AS measured_temperature,
            COALESCE(NULLIF(cr.raw_value_json ->> 'confirmed_by_name', ''), '-') AS confirmed_by,
            ROW_NUMBER() OVER (
                PARTITION BY DATE(cr.record_time), cr.equipment_id, cr.check_hour, cr.check_type
                ORDER BY cr.record_time DESC, cr.created_at DESC, cr.check_record_id DESC
            ) AS rn
        FROM check_record cr
        JOIN equipment e
            ON cr.equipment_id = e.id
        LEFT JOIN equipment_groups eg
            ON cr.equipment_group_id = eg.id
        WHERE DATE(cr.record_time) = {date_condition}
          AND cr.equipment_group_id = %s
          AND cr.check_type IN ('1H', '4H')
    )
    SELECT
        check_record_id,
        check_type,
        check_hour,
        display_text,
        record_time,
        created_at,
        record_date_label,
        input_time_label,
        equipment_id,
        equipment_name,
        equipment_group_id,
        equipment_group_name,
        temperature_1,
        temperature_2,
        measured_temperature,
        confirmed_by
    FROM ranked_records
    WHERE rn = 1
    ORDER BY check_type ASC, check_hour DESC, equipment_name ASC
    """
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(select_sql, (group_id,))
            return [dict(row) for row in cursor.fetchall()]


@app.post("/api/factories", status_code=201)
def create_factory(payload: FactoryCreateRequest) -> dict:
    insert_sql = """
    INSERT INTO factory (factory_name, display_order, is_active, created_at, updated_at)
    VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING factory_id, factory_name, display_order, is_active, created_at, updated_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(insert_sql, (payload.factory_name.strip(), payload.display_order))
                created_factory = cursor.fetchone()
            connection.commit()
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "factory created", "factory": dict(created_factory)}


@app.post("/api/recorder-ips", status_code=201)
def create_recorder_ip(payload: RecorderIpCreateRequest) -> dict:
    insert_sql = """
    INSERT INTO recorder_ip (ip_address, port_no, group_no, is_active, created_at, updated_at)
    VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING recorder_ip_id, ip_address, port_no, group_no, is_active, created_at, updated_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(insert_sql, (payload.ip_address.strip(), payload.port_no, payload.group_no))
                created_recorder_ip = cursor.fetchone()
            connection.commit()
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "recorder_ip created", "recorder_ip": dict(created_recorder_ip)}


@app.post("/api/furnace-recorder-maps", status_code=201)
def create_furnace_recorder_map(payload: FurnaceRecorderMapCreateRequest) -> dict:
    insert_sql = """
    INSERT INTO furnace_recorder_map (
        equipment_id, equipment_group_id, factory_id, recorder_ip_id, csv_file_name, is_active, created_at, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING furnace_recorder_map_id, equipment_id, equipment_group_id, factory_id, recorder_ip_id, csv_file_name, is_active, created_at, updated_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    insert_sql,
                    (
                        payload.equipment_id,
                        payload.equipment_group_id,
                        payload.factory_id,
                        payload.recorder_ip_id,
                        payload.csv_file_name.strip() if payload.csv_file_name else None,
                    ),
                )
                created_furnace_recorder_map = cursor.fetchone()
            connection.commit()
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "furnace_recorder_map created", "furnace_recorder_map": dict(created_furnace_recorder_map)}


@app.post("/api/check-records", status_code=201)
def create_check_record(payload: CheckRecordCreateRequest) -> dict:
    now = datetime.now()
    record_time = now.replace(minute=0, second=0, microsecond=0)
    check_hour = record_time.hour
    check_type = normalize_check_type(payload.check_type)
    insert_sql = """
    INSERT INTO check_record (
        equipment_id, equipment_group_id, factory_id, employee_id, recorder_ip_id,
        record_time, check_hour, check_type, display_text, raw_value_json, created_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    RETURNING check_record_id, equipment_id, equipment_group_id, factory_id, employee_id, recorder_ip_id,
              record_time, check_hour, check_type, display_text, raw_value_json, created_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                user_row = resolve_confirming_user(cursor, payload.confirmed_by)
                raw_value = dict(payload.raw_value_json) if isinstance(payload.raw_value_json, dict) else {}
                raw_value["confirmed_by_code"] = user_row["employee_code"]
                raw_value["confirmed_by_name"] = user_row["employee_name"]
                cursor.execute(
                    insert_sql,
                    (
                        payload.equipment_id,
                        payload.equipment_group_id,
                        payload.factory_id,
                        user_row["employee_id"],
                        payload.recorder_ip_id,
                        record_time,
                        check_hour,
                        check_type,
                        payload.display_text,
                        Json(raw_value),
                    ),
                )
                created_check_record = cursor.fetchone()
            connection.commit()
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "check_record created", "check_record": dict(created_check_record)}


@app.post("/api/check-records/batch", status_code=201)
def create_batch_check_records(payload: BatchCheckRecordCreateRequest) -> dict:
    now = datetime.now()
    record_time = now.replace(minute=0, second=0, microsecond=0)
    check_hour = record_time.hour
    check_type = normalize_check_type(payload.check_type)
    insert_sql = """
    INSERT INTO check_record (
        equipment_id, equipment_group_id, factory_id, employee_id, recorder_ip_id,
        record_time, check_hour, check_type, display_text, raw_value_json, created_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    RETURNING check_record_id
    """
    created_ids: list[int] = []
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                user_row = resolve_confirming_user(cursor, payload.confirmed_by)
                for furnace_record in payload.furnace_records:
                    if not furnace_record.get("is_checked"):
                        continue
                    measured_temperature = str(furnace_record.get("measured_temperature") or "").strip()
                    cursor.execute(
                        insert_sql,
                        (
                            furnace_record["equipment_id"],
                            furnace_record.get("equipment_group_id"),
                            furnace_record["factory_id"],
                            user_row["employee_id"],
                            furnace_record.get("recorder_ip_id"),
                            record_time,
                            check_hour,
                            check_type,
                            f"{check_type}チェック / {furnace_record.get('equipment_name', '')}",
                            Json(
                                {
                                    "measured_temperature": measured_temperature,
                                    "confirmed_by_code": user_row["employee_code"],
                                    "confirmed_by_name": user_row["employee_name"],
                                }
                            ),
                        ),
                    )
                    created_ids.append(cursor.fetchone()["check_record_id"])
            connection.commit()
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc

    if not created_ids:
        raise HTTPException(status_code=400, detail="送信対象の炉が選択されていません。")
    return {"message": "batch check_records created", "check_record_ids": created_ids}


@app.post("/api/comments", status_code=201)
def create_comment_record(payload: CommentCreateRequest) -> dict:
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    normalized_comment_text = normalize_recorder_text(payload.comment_text.strip())
    if not normalized_comment_text:
        raise HTTPException(status_code=400, detail="コメントを入力してください")

    select_sql = """
    SELECT
        frm.equipment_id,
        e.name AS equipment_name,
        frm.equipment_group_id,
        eg.name AS equipment_group_name,
        frm.factory_id,
        frm.recorder_ip_id,
        ri.ip_address,
        ri.port_no,
        ri.group_no
    FROM furnace_recorder_map frm
    JOIN equipment e
        ON frm.equipment_id = e.id
    LEFT JOIN equipment_groups eg
        ON frm.equipment_group_id = eg.id
    LEFT JOIN recorder_ip ri
        ON frm.recorder_ip_id = ri.recorder_ip_id
    WHERE frm.is_active = TRUE
      AND frm.equipment_id = %s
    ORDER BY frm.furnace_recorder_map_id ASC
    LIMIT 1
    """
    insert_sql = """
    INSERT INTO comment_record (
        equipment_id,
        equipment_group_id,
        factory_id,
        comment_text,
        created_at
    )
    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
    RETURNING comment_record_id
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(select_sql, (payload.equipment_id,))
                target_row = cursor.fetchone()
                if target_row is None:
                    raise HTTPException(status_code=404, detail="comment target not found")

                target_data = dict(target_row)
                if not target_data.get("ip_address") or target_data.get("group_no") is None:
                    raise HTTPException(status_code=400, detail="comment recorder target is not configured")

                send_success = send_with_retry(
                    str(target_data["ip_address"]).strip(),
                    int(target_data.get("port_no") or 502),
                    normalized_comment_text,
                    int(target_data["group_no"]),
                    WAIT_TIME1_MS,
                )
                if not send_success:
                    raise HTTPException(status_code=400, detail="記録計へのコメント送信に失敗しました")

                cursor.execute(
                    insert_sql,
                    (
                        target_data["equipment_id"],
                        target_data["equipment_group_id"],
                        target_data["factory_id"],
                        normalized_comment_text,
                    ),
                )
                created_comment = cursor.fetchone()
            connection.commit()
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc

    comment_by_name(now_str, normalized_comment_text, target_data["equipment_name"])
    return {
        "message": "comment created",
        "comment_record_id": created_comment["comment_record_id"],
        "target": target_data,
    }


@app.patch("/api/factories/{factory_id}/toggle")
def toggle_factory_status(factory_id: int) -> dict:
    select_sql = "SELECT factory_id, is_active FROM factory WHERE factory_id = %s"
    update_sql = """
    UPDATE factory
    SET is_active = %s, updated_at = CURRENT_TIMESTAMP
    WHERE factory_id = %s
    RETURNING factory_id, factory_name, display_order, is_active, created_at, updated_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(select_sql, (factory_id,))
                current_factory = cursor.fetchone()
                if current_factory is None:
                    raise HTTPException(status_code=404, detail="factory not found")
                cursor.execute(update_sql, (not bool(current_factory["is_active"]), factory_id))
                updated_factory = cursor.fetchone()
            connection.commit()
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "factory updated", "factory": dict(updated_factory)}


@app.patch("/api/recorder-ips/{recorder_ip_id}/toggle")
def toggle_recorder_ip_status(recorder_ip_id: int) -> dict:
    select_sql = "SELECT recorder_ip_id, is_active FROM recorder_ip WHERE recorder_ip_id = %s"
    update_sql = """
    UPDATE recorder_ip
    SET is_active = %s, updated_at = CURRENT_TIMESTAMP
    WHERE recorder_ip_id = %s
    RETURNING recorder_ip_id, ip_address, port_no, group_no, is_active, created_at, updated_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(select_sql, (recorder_ip_id,))
                current_recorder_ip = cursor.fetchone()
                if current_recorder_ip is None:
                    raise HTTPException(status_code=404, detail="recorder_ip not found")
                cursor.execute(update_sql, (not bool(current_recorder_ip["is_active"]), recorder_ip_id))
                updated_recorder_ip = cursor.fetchone()
            connection.commit()
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "recorder_ip updated", "recorder_ip": dict(updated_recorder_ip)}


@app.patch("/api/furnace-recorder-maps/{furnace_recorder_map_id}/toggle")
def toggle_furnace_recorder_map_status(furnace_recorder_map_id: int) -> dict:
    select_sql = "SELECT furnace_recorder_map_id, is_active FROM furnace_recorder_map WHERE furnace_recorder_map_id = %s"
    update_sql = """
    UPDATE furnace_recorder_map
    SET is_active = %s, updated_at = CURRENT_TIMESTAMP
    WHERE furnace_recorder_map_id = %s
    RETURNING furnace_recorder_map_id, equipment_id, equipment_group_id, factory_id, recorder_ip_id, csv_file_name, is_active, created_at, updated_at
    """
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(select_sql, (furnace_recorder_map_id,))
                current_map = cursor.fetchone()
                if current_map is None:
                    raise HTTPException(status_code=404, detail="furnace_recorder_map not found")
                cursor.execute(update_sql, (not bool(current_map["is_active"]), furnace_recorder_map_id))
                updated_map = cursor.fetchone()
            connection.commit()
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip()) from exc
    return {"message": "furnace_recorder_map updated", "furnace_recorder_map": dict(updated_map)}
