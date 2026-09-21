import os
import tempfile

# 앱을 import하기 전에 임시 DB를 가리킨다(db.py가 import 시점에 엔진을 만든다).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ADMIN_TOKEN"] = "test-admin"

import pytest  # noqa: E402

from api.app.db import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    yield
    Base.metadata.drop_all(engine)
