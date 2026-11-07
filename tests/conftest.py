"""Shared pytest setup.

Settings are pinned *before* the app is imported so tests never touch the real
database.db or a Postgres URL. Every integration test gets its own in-memory
SQLite database through a ``get_session`` dependency override.
"""

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # templates and static files are loaded relative to the project root
_IMPORT_DB_DIR = tempfile.mkdtemp(prefix="comp3613-tests-")
os.environ["DATABASE_URI"] = f"sqlite:///{_IMPORT_DB_DIR}/import-engine.db"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256-0123456789"
os.environ["ENV"] = "ci"  # not "production" (secure cookies) and not a verbose-SQL mode

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.application import Application
from app.models.booking import Booking
from app.models.listing import Listing
from app.models.review import Review
from app.models.user import User
from app.utilities.security import create_access_token, encrypt_password

PASSWORD = "testpass"
_PASSWORD_HASH = encrypt_password(PASSWORD)  # hash once; argon2 is slow on purpose


@pytest.fixture()
def engine():
    import app.models  # noqa: F401  (register every table)

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(engine):
    from app.database import get_session
    from app.main import app

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ------------------------------------------------------------------ factories


def _make_user(db: Session, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password=_PASSWORD_HASH,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def users(db):
    """The standard cast: two students, two landlords and an admin."""
    return {
        "bob": _make_user(db, "bob", "regular_user"),
        "fred": _make_user(db, "fred", "regular_user"),
        "landlord": _make_user(db, "landlord", "landlord"),
        "landlord2": _make_user(db, "landlord2", "landlord"),
        "admin": _make_user(db, "admin", "admin"),
    }


@pytest.fixture()
def auth():
    """auth(user) -> Authorization header for that user."""

    def _auth(user: User) -> dict:
        token = create_access_token({"sub": str(user.id), "role": user.role})
        return {"Authorization": f"Bearer {token}"}

    return _auth


@pytest.fixture()
def make_listing(db):
    def _make(
        landlord: User,
        status: str = "Verified",
        available: bool = True,
        address: str = "12 Main Street, San Fernando",
        room_type: str = "Studio",
        amenities: str = "Washing machine, Wi-Fi",
        price: str = "2500",
        security_fee: str = "500",
    ) -> Listing:
        listing = Listing(
            address=address,
            room_type=room_type,
            amenities=amenities,
            price=price,
            security_fee=security_fee,
            photos="[]",
            verification_status=status,
            availability=available,
            landlord_id=landlord.id,
        )
        db.add(listing)
        db.commit()
        db.refresh(listing)
        return listing

    return _make


@pytest.fixture()
def make_application(db):
    def _make(student: User, listing: Listing, status: str = "Applied") -> Application:
        application = Application(
            preferred_start_date=date.today() + timedelta(days=14),
            status=status,
            listing_id=listing.id,
            student_id=student.id,
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        return application

    return _make


@pytest.fixture()
def make_booking(db):
    def _make(application: Application, status: str = "Awaiting Payment") -> Booking:
        booking = Booking(
            application_id=application.id,
            start_date=application.preferred_start_date,
            student_id=application.student_id,
            listing_id=application.listing_id,
            status=status,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking

    return _make


@pytest.fixture()
def make_review(db):
    def _make(booking: Booking, rating: int = 5, comment: str = "Great place") -> Review:
        review = Review(
            booking_id=booking.id,
            student_id=booking.student_id,
            listing_id=booking.listing_id,
            rating=rating,
            comment=comment,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    return _make


def pytest_collection_modifyitems(items):
    """Tag every test by folder so `pytest -m unit` / `-m integration` work."""
    for item in items:
        parts = Path(str(item.fspath)).parts
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in parts:
            item.add_marker(pytest.mark.integration)
