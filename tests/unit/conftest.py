"""Fixtures for unit tests: plain model objects and mocked repositories (no database)."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.models.application import Application
from app.models.booking import Booking
from app.models.listing import Listing
from app.models.user import User
from app.repositories.application import ApplicationRepository
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository


def make_user(user_id: int, role: str) -> User:
    return User(
        id=user_id,
        username=f"user{user_id}",
        email=f"user{user_id}@example.com",
        password="hashed",
        role=role,
    )


@pytest.fixture()
def student():
    return make_user(1, "regular_user")


@pytest.fixture()
def other_student():
    return make_user(2, "regular_user")


@pytest.fixture()
def landlord():
    return make_user(10, "landlord")


@pytest.fixture()
def other_landlord():
    return make_user(11, "landlord")


@pytest.fixture()
def admin():
    return make_user(99, "admin")


@pytest.fixture()
def listing():
    return Listing(
        id=1,
        address="12 Main Street",
        price=Decimal("2500"),
        security_fee=Decimal("500"),
        room_type="Studio",
        amenities="Wi-Fi",
        photos="[]",
        verification_status="Verified",
        availability=True,
        landlord_id=10,
    )


@pytest.fixture()
def application():
    return Application(
        id=7,
        listing_id=1,
        student_id=1,
        status="Applied",
        preferred_start_date=date(2027, 1, 10),
    )


@pytest.fixture()
def booking():
    return Booking(
        id=5,
        application_id=7,
        listing_id=1,
        student_id=1,
        start_date=date(2027, 1, 10),
        status="Confirmed",
    )


@pytest.fixture()
def listing_repo():
    repo = MagicMock(spec=ListingRepository)
    repo.create.side_effect = lambda item: item
    repo.update.side_effect = lambda item: item
    return repo


@pytest.fixture()
def application_repo():
    repo = MagicMock(spec=ApplicationRepository)
    repo.create.side_effect = lambda item: item
    repo.update.side_effect = lambda item: item
    return repo


@pytest.fixture()
def booking_repo():
    repo = MagicMock(spec=BookingRepository)
    repo.create_for_application.side_effect = lambda app, book: book
    repo.save_status_change.side_effect = lambda book, *rest: book
    repo.confirm_payment.side_effect = lambda book, lst, pay: pay
    return repo


@pytest.fixture()
def review_repo():
    repo = MagicMock(spec=ReviewRepository)
    repo.create.side_effect = lambda item: item
    return repo


@pytest.fixture()
def user_repo():
    return MagicMock(spec=UserRepository)
