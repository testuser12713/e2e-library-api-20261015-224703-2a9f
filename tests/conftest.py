"""Shared pytest fixtures: a dedicated test database and the TestClient.

The environment is configured BEFORE ``app.config`` is imported so the whole app
boots against a throwaway SQLite file and a key generated at runtime — no key
value appears anywhere in the repository.
"""

import os
import secrets
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_TMP_DIR = tempfile.mkdtemp(prefix="library-api-tests-")
os.environ.setdefault("LIBRARY_API_KEY", secrets.token_urlsafe(32))
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP_DIR, "test.db")

from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _schema() -> Iterator[None]:
    """Create the schema before each test and drop it afterwards."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A TestClient whose session dependency points at the test database."""

    def override_get_db() -> Iterator[Session]:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def api_key() -> str:
    """The configured API key, generated at runtime."""
    return os.environ["LIBRARY_API_KEY"]
