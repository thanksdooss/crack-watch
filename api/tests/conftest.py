import os
import tempfile

# 앱을 import하기 전에 임시 DB를 가리킨다(db.py가 import 시점에 엔진을 만든다).
_tmp = tempfile.mkdtemp()
# TEST_DATABASE_URL을 주면 그 DB(예: 일회용 PostgreSQL)로 돈다. 기본은 임시 SQLite.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["ADMIN_TOKEN"] = "test-admin"

import pytest  # noqa: E402

from api.app.db import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    yield
    Base.metadata.drop_all(engine)
