"""DB 연결. 기본은 SQLite 파일(개발·테스트·데모), 배포는 DATABASE_URL로 PostgreSQL.

PostGIS 없이 동작하게 설계했다: 위치는 lat/lon + geohash 접두 인덱스로 후보를 좁히고,
정확한 거리는 파이썬에서 하버사인으로 잰다. 무료 호스팅에서 확장을 못 켜는 경우 대비.
"""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

def normalize_db_url(url: str) -> str:
    """접속 주소를 psycopg(3) 드라이버로 맞춘다.

    Neon·Supabase는 `postgresql://...`, Render·Heroku 옛 형식은 `postgres://...`로 준다.
    그냥 두면 SQLAlchemy가 psycopg2를 찾다가 실패한다(이 프로젝트는 psycopg3만 설치한다).
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_db_url(os.environ.get("DATABASE_URL", "sqlite:///./data/crack_watch.db"))

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):  # noqa: ANN001
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401 — 테이블 등록

    if DATABASE_URL.startswith("sqlite:///./"):
        os.makedirs(os.path.dirname(DATABASE_URL.removeprefix("sqlite:///")) or ".", exist_ok=True)
    Base.metadata.create_all(engine)
