"""접속 주소 형식 변환 — Neon·Supabase·Render가 주는 주소를 그대로 넣어도 붙어야 한다."""

import pytest

from api.app.db import normalize_db_url


@pytest.mark.parametrize(
    "given,expected",
    [
        # Neon·Supabase
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
        # Render·Heroku 옛 형식
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        # 이미 드라이버가 붙어 있으면 그대로
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        # 개발용 SQLite는 건드리지 않는다
        ("sqlite:///./data/crack_watch.db", "sqlite:///./data/crack_watch.db"),
    ],
)
def test_url_is_normalised_to_psycopg3(given, expected):
    assert normalize_db_url(given) == expected
