"""Tests for the members endpoints.

Covers AC-08, AC-09, AC-10, the member half of AC-11, AC-21, AC-22, AC-24 and
AC-26. Everything runs in-process through the FastAPI ``TestClient`` against the
separate test database configured in ``conftest.py`` — no server is started.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.routing import APIRoute

from app.database import SessionLocal
from app.models import Book, Loan
from app.routers import members as members_router
from app.security import require_api_key

API_KEY_HEADER = "X-API-Key"

_WRITE_ROUTES: list[tuple[str, str]] = [
    ("POST", "/members"),
    ("PUT", "/members/{id}"),
    ("PATCH", "/members/{id}"),
    ("DELETE", "/members/{id}"),
]

# The API-key enforcement is delivered by the separate "API key protection"
# ticket (app/security.py). On this branch require_api_key is still a no-op, so
# a write without a key is not (yet) rejected. These tests assert the product
# promise and start passing once that dependency lands.
_AUTH_PENDING_REASON = (
    "require_api_key enforcement is delivered by the 'API key protection' ticket "
    "(app/security.py); it is still a no-op on this branch."
)


def _payload(**overrides: object) -> dict[str, object]:
    """A valid member payload with optional overrides."""
    payload: dict[str, object] = {"name": "Ada Lovelace", "email": "ada@example.com"}
    payload.update(overrides)
    return payload


def _create(client, api_key: str, **overrides: object) -> dict:
    """Create a member with the configured key and return its representation."""
    response = client.post(
        "/members", json=_payload(**overrides), headers={API_KEY_HEADER: api_key}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth(api_key: str) -> dict[str, str]:
    return {API_KEY_HEADER: api_key}


def _assert_error_body(response, code: str) -> None:
    """Assert the uniform error body and status mapped from ``code``."""
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert "details" in body["error"]


# --- AC-08: creation -------------------------------------------------------


def test_create_member_returns_201_and_is_readable(client, api_key):
    created = _create(client, api_key)
    assert isinstance(created["id"], int)
    assert created["name"] == "Ada Lovelace"
    assert created["email"] == "ada@example.com"
    assert "member_since" in created

    fetched = client.get(f"/members/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_member_since_defaults_to_creation_time(client, api_key):
    before = datetime.now(UTC) - timedelta(seconds=1)
    created = _create(client, api_key)
    after = datetime.now(UTC) + timedelta(seconds=1)

    member_since = datetime.fromisoformat(created["member_since"])
    assert member_since.tzinfo is not None
    assert before <= member_since <= after


def test_member_since_is_honoured_when_given(client, api_key):
    given = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
    created = _create(client, api_key, member_since=given.isoformat())
    assert datetime.fromisoformat(created["member_since"]) == given


# --- AC-09: unique email ---------------------------------------------------


def test_duplicate_email_returns_409_and_creates_no_second_member(client, api_key):
    _create(client, api_key, email="dupe@example.com")

    response = client.post(
        "/members",
        json=_payload(name="Grace Hopper", email="dupe@example.com"),
        headers=_auth(api_key),
    )

    assert response.status_code == 409
    _assert_error_body(response, "CONFLICT")
    listing = client.get("/members").json()
    assert listing["total"] == 1
    assert listing["items"][0]["name"] == "Ada Lovelace"


# --- AC-10: listing and lookup ---------------------------------------------


def test_list_members_uses_the_page_envelope(client, api_key):
    for index in range(3):
        _create(client, api_key, email=f"member{index}@example.com")

    response = client.get("/members")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["total"] == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == 3


def test_list_members_honours_limit_and_offset(client, api_key):
    created = [_create(client, api_key, email=f"paged{index}@example.com") for index in range(3)]

    response = client.get("/members", params={"limit": 1, "offset": 1})
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert [item["id"] for item in body["items"]] == [created[1]["id"]]


def test_list_members_rejects_invalid_pagination(client):
    response = client.get("/members", params={"limit": 0})
    assert response.status_code == 422
    _assert_error_body(response, "VALIDATION_ERROR")


def test_get_unknown_member_returns_404(client):
    response = client.get("/members/424242")
    assert response.status_code == 404
    _assert_error_body(response, "NOT_FOUND")


# --- AC-21: reads need no key ----------------------------------------------


def test_read_endpoints_answer_without_key(client, api_key):
    created = _create(client, api_key)
    assert client.get("/members").status_code == 200
    assert client.get(f"/members/{created['id']}").status_code == 200


# --- AC-22: validation errors ----------------------------------------------


def test_invalid_payload_returns_422(client, api_key):
    response = client.post("/members", json={"name": "No Email"}, headers=_auth(api_key))
    assert response.status_code == 422
    _assert_error_body(response, "VALIDATION_ERROR")


# --- AC-11: update and delete with the configured key ----------------------


def test_put_updates_all_fields(client, api_key):
    created = _create(client, api_key, email="put@example.com")
    given = datetime(2021, 5, 6, 7, 8, 9, tzinfo=UTC)

    response = client.put(
        f"/members/{created['id']}",
        json={"name": "Renamed", "email": "put-new@example.com", "member_since": given.isoformat()},
        headers=_auth(api_key),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["email"] == "put-new@example.com"
    assert datetime.fromisoformat(body["member_since"]) == given


def test_patch_updates_only_given_fields(client, api_key):
    created = _create(client, api_key, email="patch@example.com")

    response = client.patch(
        f"/members/{created['id']}", json={"name": "Patched"}, headers=_auth(api_key)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Patched"
    assert body["email"] == "patch@example.com"


@pytest.mark.parametrize("method", ["put", "patch"])
def test_update_unknown_member_returns_404(client, api_key, method):
    response = getattr(client, method)(
        "/members/999999",
        json={"name": "Ghost", "email": "ghost@example.com"},
        headers=_auth(api_key),
    )
    assert response.status_code == 404
    _assert_error_body(response, "NOT_FOUND")


@pytest.mark.parametrize("method", ["put", "patch"])
def test_update_to_email_of_another_member_returns_409(client, api_key, method):
    _create(client, api_key, email="owner@example.com", name="Owner")
    other = _create(client, api_key, email="other@example.com", name="Other")

    payload: dict[str, str] = {"email": "owner@example.com"}
    if method == "put":
        payload["name"] = "Other"

    response = getattr(client, method)(
        f"/members/{other['id']}", json=payload, headers=_auth(api_key)
    )

    assert response.status_code == 409
    _assert_error_body(response, "CONFLICT")
    assert client.get(f"/members/{other['id']}").json()["email"] == "other@example.com"


def test_delete_member_returns_204_and_removes_it(client, api_key):
    created = _create(client, api_key, email="delete@example.com")

    response = client.delete(f"/members/{created['id']}", headers=_auth(api_key))
    assert response.status_code == 204
    assert client.get(f"/members/{created['id']}").status_code == 404


def test_delete_unknown_member_returns_404(client, api_key):
    response = client.delete("/members/999999", headers=_auth(api_key))
    assert response.status_code == 404
    _assert_error_body(response, "NOT_FOUND")


def test_delete_member_with_open_loans_returns_409(client, api_key):
    member = _create(client, api_key, email="borrower@example.com")

    with SessionLocal() as db:
        book = Book(
            title="Structure and Interpretation",
            author="Abelson",
            isbn="isbn-open-loan",
            publication_year=1985,
            total_copies=1,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        db.add(
            Loan(
                book_id=book.id,
                member_id=member["id"],
                due_at=datetime.now(UTC) + timedelta(days=14),
            )
        )
        db.commit()

    response = client.delete(f"/members/{member['id']}", headers=_auth(api_key))
    assert response.status_code == 409
    _assert_error_body(response, "CONFLICT")
    assert client.get(f"/members/{member['id']}").status_code == 200


def test_delete_member_with_closed_loans_returns_204(client, api_key):
    member = _create(client, api_key, email="returned@example.com")

    with SessionLocal() as db:
        book = Book(
            title="Compilers",
            author="Aho",
            isbn="isbn-closed-loan",
            publication_year=1986,
            total_copies=1,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        db.add(
            Loan(
                book_id=book.id,
                member_id=member["id"],
                due_at=datetime.now(UTC) + timedelta(days=14),
                returned_at=datetime.now(UTC),
            )
        )
        db.commit()

    response = client.delete(f"/members/{member['id']}", headers=_auth(api_key))
    assert response.status_code == 204


# --- AC-11: write routes are protected by the API-key dependency -----------


def _member_write_route(method: str, path: str) -> APIRoute:
    for route in members_router.router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"{method} {path} is not registered")


@pytest.mark.parametrize(("method", "path"), _WRITE_ROUTES)
def test_write_routes_declare_the_api_key_dependency(method, path):
    route = _member_write_route(method, path)
    calls = {dependency.call for dependency in route.dependant.dependencies}
    assert require_api_key in calls


@pytest.mark.xfail(reason=_AUTH_PENDING_REASON, strict=False)
@pytest.mark.parametrize(("method", "path"), _WRITE_ROUTES)
def test_write_without_key_is_401(client, method, path):
    url = path.replace("{id}", "1")
    response = getattr(client, method.lower())(url)
    assert response.status_code == 401
    _assert_error_body(response, "UNAUTHORIZED")


@pytest.mark.xfail(reason=_AUTH_PENDING_REASON, strict=False)
def test_write_with_wrong_key_is_401_and_changes_nothing(client):
    response = client.post(
        "/members",
        json=_payload(email="intruder@example.com"),
        headers={API_KEY_HEADER: "definitely-not-the-key"},
    )
    assert response.status_code == 401
    _assert_error_body(response, "UNAUTHORIZED")
    assert client.get("/members").json()["total"] == 0
