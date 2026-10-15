"""Skeleton tests: the app boots, the uniform error body holds and every stub
route of the shared contract is wired.

These tests never assert what a stub answers today (its 501 body) — only that
the route exists under the agreed path and verb, which stays true once the
feature tickets fill it in.
"""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import inspect

from app.database import engine

# (http method, path, request kwargs). A declared route answers anything but
# 404 (unknown path) or 405 (wrong method); the exact stub answer is irrelevant.
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


@pytest.mark.parametrize(("method", "path", "kwargs"), ROUTE_PROBES)
def test_contract_route_is_wired(client, method: str, path: str, kwargs: dict[str, Any]):
    call: Callable[..., Any] = getattr(client, method)
    response = call(path, **kwargs)
    assert response.status_code not in (404, 405), (
        f"{method.upper()} {path} is not wired (status {response.status_code})"
    )


def test_startup_creates_all_tables(client):
    client.get("/health")
    tables = set(inspect(engine).get_table_names())
    assert {"books", "members", "loans"} <= tables


def test_configured_key_is_read_from_environment(api_key):
    assert api_key
    assert len(api_key) >= 16
