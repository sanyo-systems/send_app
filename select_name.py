from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import MetaData, Table, create_engine, select


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


def load_users_table() -> Table:
    metadata = MetaData()
    engine = build_common_sync_engine()
    return Table(
        "users",
        metadata,
        autoload_with=engine,
    )


def find_user_name_by_employee_code(employee_code: str) -> str | None:
    normalized_employee_code = str(employee_code or "").strip()
    if not normalized_employee_code:
        return None

    users_table = load_users_table()
    stmt = (
        select(users_table.c.name)
        .where(users_table.c.employee_code == normalized_employee_code)
        .limit(1)
    )

    engine = build_common_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(stmt).first()

    if row is None:
        return None

    return str(row[0])


def main() -> None:
    employee_code = input("employee_codeを入力してください: ").strip()
    user_name = find_user_name_by_employee_code(employee_code)

    if user_name is None:
        print("該当するユーザーは見つかりませんでした。")
        return

    print(f"name: {user_name}")


if __name__ == "__main__":
    main()
