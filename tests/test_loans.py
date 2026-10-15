"""Tests for the loans router: lending rules, returns, listing and overdue.

These tests build their own books and members directly through the session, so
they do not depend on the books or members routers of other tickets.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Book, Loan, Member, utcnow
from app.routers import loans as loans_router
from app.security import require_api_key


@pytest.fixture()
def db() -> Iterator[Session]:
    """A direct session against the test database."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def auth(api_key: str) -> dict[str, str]:
    """The header carrying the configured API key."""
    return {"X-API-Key": api_key}


def _add_book(db: Session, *, isbn: str, total_copies: int = 1) -> Book:
    book = Book(
        title="Titel",
        author="Autor",
        isbn=isbn,
        publication_year=2000,
        total_copies=total_copies,
    )
    db.add(book)
    db.commit()
    return book


def _add_member(db: Session, *, email: str) -> Member:
    member = Member(name="Mitglied", email=email)
    db.add(member)
    db.commit()
    return member


def _loan_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Loan)) or 0


def _parse(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None, f"{ts} is not timezone-aware"
    return parsed


def test_create_loan_sets_due_date_14_days_after_loaned_at(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac12")
    member = _add_member(db, email="ac12@example.com")

    response = client.post(
        "/loans", json={"book_id": book.id, "member_id": member.id}, headers=auth
    )

    assert response.status_code == 201
    body = response.json()
    assert body["book_id"] == book.id
    assert body["member_id"] == member.id
    assert body["returned_at"] is None

    loaned_at = _parse(body["loaned_at"])
    due_at = _parse(body["due_at"])
    assert due_at - loaned_at == timedelta(days=14)


def test_create_loan_rejects_member_with_three_open_loans(db: Session, client: TestClient, auth):
    member = _add_member(db, email="ac13@example.com")
    books = [_add_book(db, isbn=f"isbn-ac13-{i}") for i in range(4)]

    for book in books[:3]:
        response = client.post(
            "/loans", json={"book_id": book.id, "member_id": member.id}, headers=auth
        )
        assert response.status_code == 201

    before = _loan_count(db)
    response = client.post(
        "/loans", json={"book_id": books[3].id, "member_id": member.id}, headers=auth
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert _loan_count(db) == before == 3


def test_create_loan_rejects_book_without_free_copy(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac14", total_copies=1)
    first = _add_member(db, email="ac14-first@example.com")
    second = _add_member(db, email="ac14-second@example.com")

    assert (
        client.post(
            "/loans", json={"book_id": book.id, "member_id": first.id}, headers=auth
        ).status_code
        == 201
    )

    before = _loan_count(db)
    response = client.post(
        "/loans", json={"book_id": book.id, "member_id": second.id}, headers=auth
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert _loan_count(db) == before == 1


def test_create_loan_allows_book_with_free_copy(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac14b", total_copies=2)
    first = _add_member(db, email="ac14b-first@example.com")
    second = _add_member(db, email="ac14b-second@example.com")

    assert (
        client.post(
            "/loans", json={"book_id": book.id, "member_id": first.id}, headers=auth
        ).status_code
        == 201
    )
    response = client.post(
        "/loans", json={"book_id": book.id, "member_id": second.id}, headers=auth
    )
    assert response.status_code == 201


def test_create_loan_unknown_book_or_member_returns_404(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac15")
    member = _add_member(db, email="ac15@example.com")

    before = _loan_count(db)
    response = client.post("/loans", json={"book_id": 999999, "member_id": member.id}, headers=auth)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

    response = client.post("/loans", json={"book_id": book.id, "member_id": 999999}, headers=auth)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

    assert _loan_count(db) == before == 0


def test_return_loan_frees_the_copy(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac16", total_copies=1)
    first = _add_member(db, email="ac16-first@example.com")
    second = _add_member(db, email="ac16-second@example.com")

    created = client.post(
        "/loans", json={"book_id": book.id, "member_id": first.id}, headers=auth
    ).json()

    response = client.post(f"/loans/{created['id']}/return", headers=auth)
    assert response.status_code == 200
    assert response.json()["returned_at"] is not None

    assert (
        client.post(
            "/loans", json={"book_id": book.id, "member_id": second.id}, headers=auth
        ).status_code
        == 201
    )


def test_return_loan_twice_conflicts_and_unknown_returns_404(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac17")
    member = _add_member(db, email="ac17@example.com")
    created = client.post(
        "/loans", json={"book_id": book.id, "member_id": member.id}, headers=auth
    ).json()

    assert client.post(f"/loans/{created['id']}/return", headers=auth).status_code == 200

    response = client.post(f"/loans/{created['id']}/return", headers=auth)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"

    response = client.post("/loans/999999/return", headers=auth)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_overdue_returns_only_open_loans_past_due(db: Session, client: TestClient, auth):
    book_a = _add_book(db, isbn="isbn-ac18-a")
    book_b = _add_book(db, isbn="isbn-ac18-b")
    overdue_member = _add_member(db, email="ac18-overdue@example.com")
    future_member = _add_member(db, email="ac18-future@example.com")

    overdue = client.post(
        "/loans", json={"book_id": book_a.id, "member_id": overdue_member.id}, headers=auth
    ).json()
    client.post("/loans", json={"book_id": book_b.id, "member_id": future_member.id}, headers=auth)

    overdue_loan = db.get(Loan, overdue["id"])
    assert overdue_loan is not None
    overdue_loan.due_at = utcnow() - timedelta(days=1)
    db.commit()

    response = client.get("/loans/overdue")
    assert response.status_code == 200
    body = response.json()
    assert [loan["id"] for loan in body] == [overdue["id"]]


def test_overdue_excludes_returned_loans(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac18-returned")
    member = _add_member(db, email="ac18-returned@example.com")
    created = client.post(
        "/loans", json={"book_id": book.id, "member_id": member.id}, headers=auth
    ).json()

    loan = db.get(Loan, created["id"])
    assert loan is not None
    loan.due_at = utcnow() - timedelta(days=1)
    db.commit()

    client.post(f"/loans/{created['id']}/return", headers=auth)

    response = client.get("/loans/overdue")
    assert response.status_code == 200
    assert response.json() == []


def test_list_loans_filters_and_pagination(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-ac19", total_copies=5)
    member_one = _add_member(db, email="ac19-one@example.com")
    member_two = _add_member(db, email="ac19-two@example.com")

    first = client.post(
        "/loans", json={"book_id": book.id, "member_id": member_one.id}, headers=auth
    ).json()
    second = client.post(
        "/loans", json={"book_id": book.id, "member_id": member_two.id}, headers=auth
    ).json()
    client.post(f"/loans/{second['id']}/return", headers=auth)

    listed = client.get("/loans").json()
    assert set(listed) == {"items", "total", "limit", "offset"}
    assert listed["total"] == 2
    assert listed["limit"] == 20
    assert listed["offset"] == 0

    by_member = client.get("/loans", params={"member_id": member_one.id}).json()
    assert by_member["total"] == 1
    assert by_member["items"][0]["id"] == first["id"]

    by_book = client.get("/loans", params={"book_id": book.id}).json()
    assert by_book["total"] == 2

    active = client.get("/loans", params={"active": "true"}).json()
    assert active["total"] == 1
    assert active["items"][0]["id"] == first["id"]

    returned = client.get("/loans", params={"active": "false"}).json()
    assert returned["total"] == 1
    assert returned["items"][0]["id"] == second["id"]

    window = client.get("/loans", params={"limit": 1, "offset": 1}).json()
    assert len(window["items"]) == 1
    assert window["total"] == 2


def test_get_loan_returns_it_or_404(db: Session, client: TestClient, auth):
    book = _add_book(db, isbn="isbn-getloan")
    member = _add_member(db, email="getloan@example.com")
    created = client.post(
        "/loans", json={"book_id": book.id, "member_id": member.id}, headers=auth
    ).json()

    response = client.get(f"/loans/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]

    missing = client.get("/loans/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


def test_write_routes_carry_the_api_key_dependency():
    guarded = {
        (route.path, method)
        for route in loans_router.router.routes
        for method in route.methods
        if any(dep.dependency is require_api_key for dep in route.dependencies)
    }
    assert ("/loans", "POST") in guarded
    assert ("/loans/{id}/return", "POST") in guarded


def test_validation_error_has_uniform_body(client: TestClient, auth):
    response = client.post("/loans", json={}, headers=auth)
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]


def test_read_endpoints_answer_without_api_key(db: Session, client: TestClient):
    assert client.get("/loans").status_code == 200
    assert client.get("/loans/overdue").status_code == 200
    assert client.get("/loans/999999").status_code == 404
