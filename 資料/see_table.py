from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.exc import NoSuchTableError


class CommonSelectSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    alembic_database_url_common: str = Field(..., alias="ALEMBIC_DATABASE_URL_COMMON")


@lru_cache
def get_common_select_settings() -> CommonSelectSettings:
    return CommonSelectSettings()


def build_common_sync_engine():
    settings = get_common_select_settings()
    return create_engine(
        settings.alembic_database_url_common,
        pool_pre_ping=True,
    )


def load_table_definition(table_name: str) -> Table:
    metadata = MetaData()
    engine = build_common_sync_engine()
    return Table(
        table_name,
        metadata,
        autoload_with=engine,
    )


def find_table_columns(table_name: str) -> list[dict]:
    normalized_table_name = str(table_name or "").strip()
    if not normalized_table_name:
        return []

    table = load_table_definition(normalized_table_name)
    return [
        {
            "column_name": column.name,
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key,
        }
        for column in table.columns
    ]


def main() -> None:
    table_name = input("テーブル名を入力してください: ").strip()
    if not table_name:
        print("テーブル名が未入力です。")
        return

    try:
        columns = find_table_columns(table_name)
    except NoSuchTableError:
        print("指定したテーブルは見つかりませんでした。")
        return

    if not columns:
        print("カラム情報を取得できませんでした。")
        return

    for index, column in enumerate(columns, start=1):
        print(f"[{index}] {column}")


if __name__ == "__main__":
    main()
