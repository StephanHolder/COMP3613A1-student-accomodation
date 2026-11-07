"""Pagination and security helpers."""

import jwt
import pytest

from app.config import get_settings
from app.utilities.pagination import Pagination
from app.utilities.security import (
    create_access_token,
    encrypt_password,
    verify_password,
)


class TestPagination:
    def test_total_pages_rounds_up(self):
        assert Pagination(total_count=11, current_page=1, limit=5).total_pages == 3

    def test_zero_results_is_a_single_page(self):
        pagination = Pagination(total_count=0, current_page=1, limit=5)
        assert pagination.total_pages == 0
        assert not pagination.has_prev and not pagination.has_next

    def test_first_page_has_next_only(self):
        pagination = Pagination(total_count=12, current_page=1, limit=5)
        assert pagination.has_next and not pagination.has_prev
        assert pagination.next_num == 2

    def test_middle_page_has_both(self):
        pagination = Pagination(total_count=12, current_page=2, limit=5)
        assert pagination.has_prev and pagination.has_next
        assert pagination.prev_num == 1

    def test_last_page_has_prev_only(self):
        pagination = Pagination(total_count=12, current_page=3, limit=5)
        assert pagination.has_prev and not pagination.has_next

    def test_non_positive_limit_does_not_divide_by_zero(self):
        assert Pagination(total_count=10, current_page=1, limit=0).total_pages == 1

    def test_iter_pages_marks_gaps_with_none(self):
        pages = list(Pagination(total_count=200, current_page=10, limit=5).iter_pages())
        assert None in pages
        assert pages[0] == 1


class TestSecurity:
    def test_password_round_trip(self):
        hashed = encrypt_password("s3cret")
        assert hashed != "s3cret"
        assert verify_password("s3cret", hashed)

    def test_wrong_password_is_rejected(self):
        assert not verify_password("wrong", encrypt_password("s3cret"))

    def test_access_token_carries_subject_role_and_expiry(self):
        token = create_access_token({"sub": "4", "role": "landlord"})
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "4"
        assert payload["role"] == "landlord"
        assert "exp" in payload

    def test_token_signed_with_another_key_is_invalid(self):
        token = create_access_token({"sub": "4"})
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "a-different-secret-key-0123456789-abcdef", algorithms=["HS256"])
