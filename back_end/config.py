from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    database_url: str = Field(..., alias="DATABASE_URL")
    database_url_common: str = Field(..., alias="DATABASE_URL_COMMON")
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    upload_dir: Path = Field(..., alias="UPLOAD_DIR")
    base_upload_url: str = Field(default="/uploads", alias="BASE_UPLOAD_URL")
    allowed_origins: list[str] = Field(default_factory=list, alias="ALLOWED_ORIGINS")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return [str(origin).strip() for origin in value if str(origin).strip()]

    @field_validator("upload_dir", mode="before")
    @classmethod
    def normalize_upload_dir(cls, value: str | Path) -> Path:
        path = Path(value).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("base_upload_url")
    @classmethod
    def normalize_base_upload_url(cls, value: str) -> str:
        normalized = "/" + str(value or "").strip().strip("/")
        return normalized if normalized != "/" else "/uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
