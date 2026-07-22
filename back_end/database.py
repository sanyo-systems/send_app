from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from back_end.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

common_engine = create_engine(
    settings.database_url_common,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

SessionLocalCommon = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=common_engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_common_db() -> Generator[Session, None, None]:
    db = SessionLocalCommon()
    try:
        yield db
    finally:
        db.close()
