from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from litmonitor.config import get_settings


def _sqlite_path(database_url: str) -> Path | None:
    if database_url.startswith("sqlite:///./"):
        return Path(database_url.removeprefix("sqlite:///"))
    return None


def get_engine():
    settings = get_settings()
    path = _sqlite_path(settings.database_url)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


engine = get_engine()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
