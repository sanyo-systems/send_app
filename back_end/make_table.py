from functools import lru_cache
from pathlib import Path
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine

if __package__ in (None, ""):
    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

try:
    from back_end.database_common import Base
    from back_end.models.common_models import (  # noqa: F401
        CheckRecord,
        CommentRecord,
        CsvSendRecord,
        Factory,
        FurnaceRecorderMap,
        RecorderIp,
    )
except ModuleNotFoundError:
    from database_common import Base
    from models.common_models import (  # noqa: F401
        CheckRecord,
        CommentRecord,
        CsvSendRecord,
        Factory,
        FurnaceRecorderMap,
        RecorderIp,
    )


class CommonMigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    alembic_database_url_common: str = Field(..., alias="ALEMBIC_DATABASE_URL_COMMON")


@lru_cache
def get_common_migration_settings() -> CommonMigrationSettings:
    return CommonMigrationSettings()


def build_common_sync_engine():
    migration_settings = get_common_migration_settings()
    return create_engine(
        migration_settings.alembic_database_url_common,
        pool_pre_ping=True,
    )


def create_common_tables() -> None:
    engine = build_common_sync_engine()
    Base.metadata.create_all(
        bind=engine,
        checkfirst=True,
    )


if __name__ == "__main__":
    create_common_tables()
