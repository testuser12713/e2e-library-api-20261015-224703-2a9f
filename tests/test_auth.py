"""Tests for the API key protection of every write endpoint.

The key is never a literal here: it comes from the generated ``api_key`` fixture
(see ``tests/conftest.py``). Only the behaviour the ticket owns is asserted —
that an unauthorized request is rejected with ``401 UNAUTHORIZED`` and changes
nothing, and that a correctly keyed request is not rejected with 401. What a
keyed request actually answers is owned by the feature tickets whose routes are
still stubs on this branch, so it is never pinned.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Book, Loan, Member

_BOOK_PAYLOAD: dict[str, Any] = {
    "title": "Der Prozess",
    "author": "Franz Kafka",
    "isbn": "978-3-15-009018-7",
    "publication_year": 1925,
    "total_copies": 3,
}

_MEMBER_PAYLOAD: dict[str, Any] = {
    "name": "Ada Lovelace",
    "email": "ada.lovelace@example.org",
}

_LOAN_PAYLOAD: dict[str, Any] = {"book_id": 1, "member_id": 1}

# (method, path, body, model whose table the request could write to)
_WRITE_ROUTES: list[tuple[str, str, dict[str, Any] | None, type | None]] = [
    ("POST", "/books", _BOOK_PAYLOAD, Book),
    ("PUT", "/books/1", _BOOK_PAYLOAD, None),
    ("PATCH", "/books/1", {"title": "Das Schloss"}, None),
    ("DELETE", "/books/1", None, None),
    ("POST", "/members", _MEMBER_PAYLOAD, Member),
    ("PUT", "/members/1", _MEMBER_PAYLOAD, None),
    ("PATCH", "/members/1", {"name": "Grace Hopper"}, None),
    ("DELETE", "/members/1", None, None),
    ("POST", "/loans", _LOAN_PAYLOAD, Loan),
    ("POST", "/loans/1/return", None, None),
]

_ROUTE_IDS = [f"{method} {path}" for method, path, _, _ in _WRITE_ROUTES]


def _call(client: TestClient, method: str, path: str, body: dict[str, Any] | None) -> Any:
    return client.request(method, path, json=body)


def _count(model: type) -> int:
    """Count rows of ``model`` in the test database."""
    db: Session = SessionLocal()
    try:
        return db.execute(select(func.count()).select_from(model)).scalar_one()
    finally:
        db.close()


def _assert_uniform_401(response: Any) -> None:
    assert response.status_code == 401
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == "UNAUTHORIZED"
    assert isinstance(error["message"], str) and error["message"]


@pytest.mark.parametrize(("method", "path", "body", "_model"), _WRITE_ROUTES, ids=_ROUTE_IDS)
def test_write_without_key_is_401(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    _model: type | None,
) -> None:
    response = _call(client, method, path, body)
    _assert_uniform_401(response)


@pytest.mark.parametrize(("method", "path", "body", "_model"), _WRITE_ROUTES, ids=_ROUTE_IDS)
def test_write_with_wrong_key_is_401(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    _model: type | None,
) -> None:
    response = client.request(method, path, json=body, headers={"X-API-Key": "not-the-key"})
    _assert_uniform_401(response)


@pytest.mark.parametrize(("method", "path", "body", "_model"), _WRITE_ROUTES, ids=_ROUTE_IDS)
def test_write_with_configured_key_is_not_rejected(
    client: TestClient,
    api_key: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    _model: type | None,
) -> None:
    response = client.request(method, path, json=body, headers={"X-API-Key": api_key})
    # The status the route answers is owned by a feature ticket; only the key
    # check itself is asserted here.
    assert response.status_code != 401


@pytest.mark.parametrize(
    ("method", "path", "body", "model"),
    [route for route in _WRITE_ROUTES if route[3] is not None],
    ids=[rid for rid, route in zip(_ROUTE_IDS, _WRITE_ROUTES, strict=True) if route[3] is not None],
)
def test_unauthorized_write_creates_nothing(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    model: type,
) -> None:
    assert _count(model) == 0
    response = _call(client, method, path, body)
    _assert_uniform_401(response)
    assert _count(model) == 0


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/books"),
        ("PUT", "/books/1"),
        ("POST", "/members"),
        ("PUT", "/members/1"),
        ("POST", "/loans"),
    ],
)
def test_missing_key_wins_over_invalid_payload(client: TestClient, method: str, path: str) -> None:
    # An empty body would be a 422 under validation, but the key check runs
    # first, so a missing key must surface as 401.
    response = client.request(method, path, json={})
    _assert_uniform_401(response)


@pytest.mark.parametrize("path", ["/books", "/members", "/loans", "/loans/overdue"])
def test_read_routes_do_not_require_a_key(client: TestClient, path: str) -> None:
    response = client.get(path)
    # GET routes carry no API-key dependency; whatever they answer (a stub
    # answers 501) it must never be the authentication rejection.
    assert response.status_code != 401
