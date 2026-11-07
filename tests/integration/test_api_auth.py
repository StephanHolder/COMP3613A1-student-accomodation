"""Authentication and account endpoints (JSON API)."""


def register(client, **overrides):
    body = {"username": "amy", "email": "amy@example.com", "password": "pw12345"}
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


class TestRegister:
    def test_creates_a_student_account(self, client):
        response = register(client)
        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "amy"
        assert body["role"] == "regular_user"
        assert "password" not in body

    def test_duplicate_username_conflicts(self, client):
        register(client)
        response = register(client, email="other@example.com")
        assert response.status_code == 409

    def test_duplicate_email_conflicts(self, client):
        register(client)
        response = register(client, username="amy2")
        assert response.status_code == 409

    def test_invalid_email_is_rejected(self, client):
        assert register(client, email="not-an-email").status_code == 422

    def test_missing_password_is_rejected(self, client):
        response = client.post("/api/auth/register", json={"username": "a", "email": "a@b.co"})
        assert response.status_code == 422


class TestLogin:
    def test_valid_login_returns_a_bearer_token(self, client, users):
        response = client.post("/api/auth/login", json={"username": "bob", "password": "testpass"})
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "regular_user"
        assert body["access_token"]

    def test_wrong_password_is_401(self, client, users):
        response = client.post("/api/auth/login", json={"username": "bob", "password": "nope"})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    def test_unknown_user_is_401(self, client):
        response = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
        assert response.status_code == 401

    def test_empty_body_is_422(self, client):
        assert client.post("/api/auth/login", json={}).status_code == 422

    def test_registered_user_can_log_in(self, client):
        register(client)
        response = client.post("/api/auth/login", json={"username": "amy", "password": "pw12345"})
        assert response.status_code == 200


class TestMe:
    def test_returns_the_current_user(self, client, users, auth):
        response = client.get("/api/auth/me", headers=auth(users["landlord"]))
        assert response.status_code == 200
        assert response.json()["username"] == "landlord"
        assert response.json()["role"] == "landlord"

    def test_requires_a_token(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")

    def test_rejects_a_garbage_token(self, client):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
        assert response.status_code == 401

    def test_rejects_a_non_bearer_scheme(self, client, users, auth):
        token = auth(users["bob"])["Authorization"].split(" ", 1)[1]
        response = client.get("/api/auth/me", headers={"Authorization": f"Basic {token}"})
        assert response.status_code == 401


class TestUserList:
    def test_requires_authentication(self, client):
        assert client.get("/api/users").status_code == 401

    def test_students_are_forbidden(self, client, users, auth):
        assert client.get("/api/users", headers=auth(users["bob"])).status_code == 403

    def test_landlords_are_forbidden(self, client, users, auth):
        assert client.get("/api/users", headers=auth(users["landlord"])).status_code == 403

    def test_admin_sees_everyone_without_passwords(self, client, users, auth):
        response = client.get("/api/users", headers=auth(users["admin"]))
        assert response.status_code == 200
        assert {u["username"] for u in response.json()} == set(users)
        assert all("password" not in u for u in response.json())
