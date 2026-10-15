"""Skeleton tests: the app boots, the uniform error body holds and every stub
route of the shared contract is wired.

These tests never assert what a stub answers today (its 501 body) — only that
the route exists under the agreed path and verb, which stays true once the
feature tickets fill it in.
"""

import re
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import inspect

from app.database import engine
from app.main import app

# (http method, path, request kwargs). The route must be registered under this
# exact path and verb; whether it answers a stub or the finished feature is
# irrelevant, and a correct 404 for an unknown resource id is not a defect.
ROUTE_PROBES: list[tuple[str, str, dict[str, Any]]] = [
    ("post", "/books", {"json": {}}),
    ("get", "/books", {}),
    ("get", "/books/1", {}),
    ("put", "/books/1", {"json": {}}),
    ("patch", "/books/1", {"json": {}}),
    ("delete", "/books/1", {}),
    ("post", "/members", {"json": {}}),
    ("get", "/members", {}),
    ("get", "/members/1", {}),
    ("put", "/members/1", {"json": {}}),
    ("patch", "/members/1", {"json": {}}),
    ("delete", "/members/1", {}),
    ("post", "/loans", {"json": {}}),
    ("get", "/loans", {}),
    ("get", "/loans/overdue", {}),
    ("get", "/loans/1", {}),
    ("post", "/loans/1/return", {"json": {}}),
]


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_path_uses_uniform_error_body(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "NOT_FOUND"
    assert isinstance(body["error"]["message"], str)
    assert "details" in body["error"]


def test_invalid_query_returns_validation_error(client):
    response = client.get("/books", params={"limit": "abc"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def _is_registered(method: str, path: str) -> bool:
    """Whether the app declares a route for this path template and verb.

    The probe asks the OpenAPI schema, not a live request: once a feature ticket
    fills a by-id route in, ``GET /books/1`` (and its siblings) legitimately
    answers 404 for an unknown id because ``tests/conftest.py`` drops the schema
    per test — that 404 is not a wiring defect and must not fail the suite.
    """
    normalized = re.sub(r"/\d+", "/{id}", path)
    operations = app.openapi().get("paths", {}).get(normalized, {})
    return method.lower() in operations


@pytest.mark.parametrize(("method", "path", "kwargs"), ROUTE_PROBES)
def test_contract_route_is_wired(client, method: str, path: str, kwargs: dict[str, Any]):
    assert _is_registered(method, path), f"{method.upper()} {path} is not wired"
    call: Callable[..., Any] = getattr(client, method)
    response = call(path, **kwargs)
    # A registered route must not answer 405 (method not allowed). A 404 from a
    # by-id route for an unknown id is acceptable and deliberately not rejected.
    assert response.status_code != 405, f"{method.upper()} {path} rejects its method"


def test_startup_creates_all_tables(client):
    client.get("/health")
    tables = set(inspect(engine).get_table_names())
    assert {"books", "members", "loans"} <= tables


def test_configured_key_is_read_from_environment(api_key):
    assert api_key
    assert len(api_key) >= 16
