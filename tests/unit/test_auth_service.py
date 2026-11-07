"""AuthService with a mocked user repository."""

import jwt

from app.config import get_settings
from app.models.user import User
from app.services.auth_service import AuthService
from app.utilities.security import encrypt_password


def _stored_user():
    return User(
        id=3,
        username="bob",
        email="bob@example.com",
        password=encrypt_password("bobpass"),
        role="regular_user",
    )


def test_authenticate_returns_token_for_valid_credentials(user_repo):
    user_repo.get_by_username.return_value = _stored_user()
    token = AuthService(user_repo).authenticate_user("bob", "bobpass")
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "3"
    assert payload["role"] == "regular_user"


def test_authenticate_rejects_wrong_password(user_repo):
    user_repo.get_by_username.return_value = _stored_user()
    assert AuthService(user_repo).authenticate_user("bob", "nope") is None


def test_authenticate_rejects_unknown_user(user_repo):
    user_repo.get_by_username.return_value = None
    assert AuthService(user_repo).authenticate_user("ghost", "x") is None


def test_register_stores_a_hashed_student_account(user_repo):
    user_repo.create.side_effect = lambda data: data
    created = AuthService(user_repo).register_user("amy", "amy@example.com", "pw123")
    assert created.role == "regular_user"
    assert created.password != "pw123"
