"""Tests for the books CRUD slice (AC-01..AC-07, AC-11, AC-21..AC-23, AC-26).

The suite runs against the throwaway test database wired by ``conftest.py`` and
never starts a server: every request goes through the FastAPI ``TestClient``.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Loan, Member, utcnow


def _payload(**overrides: object) -> dict[str, object]:
    """A valid ``BookCreate`` payload, with optional field overrides."""
    data: dict[str, object] = {
        "title": "Der Prozess",
        "author": "Franz Kafka",
        "isbn": "978-3-16-148410-0",
        "publication_year": 1925,
        "total_copies": 3,
    }
    data.update(overrides)
    return data


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


def _create(client: TestClient, api_key: str, **overrides: object) -> dict[str, object]:
    response = client.post("/books", json=_payload(**overrides), headers=_headers(api_key))
    assert response.status_code == 201, response.text
    return response.json()


def _insert_loan(book_id: int, *, returned: bool = False) -> None:
    """Insert a member and a loan for ``book_id`` directly in the DB."""
    with SessionLocal() as db:
        member = Member(name="Leser", email="leser@example.com")
        db.add(member)
        db.flush()
        db.add(
            Loan(
                book_id=book_id,
                member_id=member.id,
                due_at=utcnow() + timedelta(days=14),
                returned_at=utcnow() if returned else None,
            )
        )
        db.commit()


def _api_key_is_enforced(client: TestClient) -> bool:
    """True once app/security.py actually rejects a wrong key (ticket #4)."""
    probe = client.post("/books", json=_payload(isbn="probe-isbn"), headers={"X-API-Key": "wrong"})
    return probe.status_code == 401


# --- AC-01 -------------------------------------------------------------------


def test_create_book_returns_201_and_is_readable(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)

    assert created["id"] == 1
    assert created["title"] == "Der Prozess"
    assert created["author"] == "Franz Kafka"
    assert created["isbn"] == "978-3-16-148410-0"
    assert created["publication_year"] == 1925
    assert created["total_copies"] == 3

    fetched = client.get(f"/books/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


# --- AC-02 -------------------------------------------------------------------


def test_duplicate_isbn_returns_409_and_creates_no_second_book(
    client: TestClient, api_key: str
) -> None:
    _create(client, api_key)

    duplicate = client.post(
        "/books", json=_payload(title="Anderer Titel"), headers=_headers(api_key)
    )

    assert duplicate.status_code == 409
    body = duplicate.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "CONFLICT"
    assert isinstance(body["error"]["message"], str)

    assert client.get("/books").json()["total"] == 1


# --- AC-03 -------------------------------------------------------------------


def test_list_uses_default_envelope(client: TestClient, api_key: str) -> None:
    for index in range(3):
        _create(client, api_key, isbn=f"isbn-{index}")

    body = client.get("/books").json()

    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_honours_window_while_total_counts_all(client: TestClient, api_key: str) -> None:
    for index in range(5):
        _create(client, api_key, isbn=f"isbn-{index}")

    body = client.get("/books", params={"limit": 2, "offset": 1}).json()

    assert body["limit"] == 2
    assert body["offset"] == 1
    assert body["total"] == 5
    assert [item["id"] for item in body["items"]] == [2, 3]


def test_list_rejects_limit_above_maximum(client: TestClient) -> None:
    response = client.get("/books", params={"limit": 101})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- AC-04 -------------------------------------------------------------------


def test_search_matches_title_or_author_case_insensitively(
    client: TestClient, api_key: str
) -> None:
    _create(client, api_key, title="Alpha", author="Erste", isbn="isbn-1")
    _create(client, api_key, title="ALPHABET", author="Zweite", isbn="isbn-2")
    _create(client, api_key, title="Beta", author="Alpha Writer", isbn="isbn-3")
    _create(client, api_key, title="Gamma", author="Dritte", isbn="isbn-4")

    body = client.get("/books", params={"q": "alpha"}).json()

    assert body["total"] == 3
    assert {item["isbn"] for item in body["items"]} == {"isbn-1", "isbn-2", "isbn-3"}


def test_search_combines_with_limit_and_offset(client: TestClient, api_key: str) -> None:
    _create(client, api_key, title="Alpha", author="Erste", isbn="isbn-1")
    _create(client, api_key, title="ALPHABET", author="Zweite", isbn="isbn-2")
    _create(client, api_key, title="Beta", author="Alpha Writer", isbn="isbn-3")

    body = client.get("/books", params={"q": "alpha", "limit": 1, "offset": 1}).json()

    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert [item["isbn"] for item in body["items"]] == ["isbn-2"]


# --- AC-05 -------------------------------------------------------------------


def test_get_book_returns_200_and_unknown_id_returns_404(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)

    assert client.get(f"/books/{created['id']}").status_code == 200

    missing = client.get("/books/9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


# --- AC-06 -------------------------------------------------------------------


def test_put_replaces_book(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)

    response = client.put(
        f"/books/{created['id']}",
        json=_payload(title="Neuer Titel", isbn="isbn-neu"),
        headers=_headers(api_key),
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == created["id"]
    assert updated["title"] == "Neuer Titel"
    assert updated["isbn"] == "isbn-neu"
    assert updated["author"] == "Franz Kafka"
    assert client.get(f"/books/{created['id']}").json() == updated


def test_patch_updates_only_given_fields(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)

    response = client.patch(
        f"/books/{created['id']}",
        json={"title": "Nur der Titel"},
        headers=_headers(api_key),
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Nur der Titel"
    assert updated["author"] == created["author"]
    assert updated["isbn"] == created["isbn"]


@pytest.mark.parametrize("method", ["put", "patch"])
def test_update_unknown_id_returns_404(client: TestClient, api_key: str, method: str) -> None:
    response = getattr(client, method)("/books/9999", json=_payload(), headers=_headers(api_key))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("method", ["put", "patch"])
def test_update_with_isbn_of_another_book_returns_409(
    client: TestClient, api_key: str, method: str
) -> None:
    _create(client, api_key, isbn="isbn-a")
    second = _create(client, api_key, isbn="isbn-b")

    response = getattr(client, method)(
        f"/books/{second['id']}", json=_payload(isbn="isbn-a"), headers=_headers(api_key)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert client.get(f"/books/{second['id']}").json()["isbn"] == "isbn-b"


# --- AC-07 -------------------------------------------------------------------


def test_delete_returns_204_and_book_is_gone(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)

    response = client.delete(f"/books/{created['id']}", headers=_headers(api_key))

    assert response.status_code == 204
    assert client.get(f"/books/{created['id']}").status_code == 404


def test_delete_unknown_id_returns_404(client: TestClient, api_key: str) -> None:
    response = client.delete("/books/9999", headers=_headers(api_key))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_delete_with_open_loans_returns_409_and_keeps_book(
    client: TestClient, api_key: str
) -> None:
    created = _create(client, api_key)
    _insert_loan(created["id"])

    response = client.delete(f"/books/{created['id']}", headers=_headers(api_key))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert client.get(f"/books/{created['id']}").status_code == 200


def test_delete_with_only_returned_loans_succeeds(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)
    _insert_loan(created["id"], returned=True)

    response = client.delete(f"/books/{created['id']}", headers=_headers(api_key))

    assert response.status_code == 204
    assert client.get(f"/books/{created['id']}").status_code == 404


# --- AC-23 / AC-22 -----------------------------------------------------------


def _payload_without_title() -> dict[str, object]:
    payload = _payload()
    del payload["title"]
    return payload


@pytest.mark.parametrize(
    "payload",
    [
        _payload_without_title(),
        _payload(publication_year="not-a-number"),
        _payload(total_copies=0),
        _payload(total_copies=-1),
    ],
    ids=["missing-title", "non-integer-year", "zero-copies", "negative-copies"],
)
def test_invalid_payload_returns_422_uniform_body(
    client: TestClient, api_key: str, payload: dict[str, object]
) -> None:
    response = client.post("/books", json=payload, headers=_headers(api_key))

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["error"]["message"], str)
    assert "details" in body["error"]


# --- AC-11 -------------------------------------------------------------------


def test_write_without_key_is_rejected_when_enforcement_is_active(client: TestClient) -> None:
    response = client.post("/books", json=_payload())
    if not _api_key_is_enforced(client):
        pytest.skip("app/security.py enforcement (ticket #4) is not on this branch yet")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert client.get("/books").json()["total"] == 0


def test_write_with_wrong_key_is_rejected_when_enforcement_is_active(client: TestClient) -> None:
    response = client.post("/books", json=_payload(), headers={"X-API-Key": "wrong-key"})
    if not _api_key_is_enforced(client):
        pytest.skip("app/security.py enforcement (ticket #4) is not on this branch yet")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


# --- AC-21 -------------------------------------------------------------------


def test_read_endpoints_answer_without_api_key(client: TestClient, api_key: str) -> None:
    created = _create(client, api_key)

    assert client.get("/books").status_code == 200
    assert client.get(f"/books/{created['id']}").status_code == 200
