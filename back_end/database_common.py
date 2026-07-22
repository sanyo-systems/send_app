from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base


class CommonDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    database_url_common: str = Field(..., alias="DATABASE_URL_COMMON")


@lru_cache
def get_common_database_settings() -> CommonDatabaseSettings:
    return CommonDatabaseSettings()


common_database_settings = get_common_database_settings()

common_async_engine = create_async_engine(
    common_database_settings.database_url_common,
    pool_pre_ping=True,
)

CommonSessionLocal = async_sessionmaker(
    bind=common_async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()
