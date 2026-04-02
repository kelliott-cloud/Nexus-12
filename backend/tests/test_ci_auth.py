"""test_auth.py — Authentication flow regression tests."""
import requests
import pytest


class TestAuthFlow:
    """Test login, register, session management."""

    def test_login_success(self, api_url, admin_credentials):
        resp = requests.post(f"{api_url}/api/auth/login", json=admin_credentials)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_token" in data
        assert data.get("email") == admin_credentials["email"]

    def test_login_wrong_password(self, api_url):
        resp = requests.post(f"{api_url}/api/auth/login", json={"email": "kelliott@urtech.org", "password": "wrong"})
        assert resp.status_code in (401, 403)

    def test_login_nonexistent_user(self, api_url):
        resp = requests.post(f"{api_url}/api/auth/login", json={"email": "nobody@nowhere.com", "password": "test"})
        assert resp.status_code in (401, 404)

    def test_login_missing_fields(self, api_url):
        resp = requests.post(f"{api_url}/api/auth/login", json={"email": "test@test.com"})
        assert resp.status_code == 422

    def test_session_list(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/user/sessions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_logout(self, api_url, admin_credentials):
        login = requests.post(f"{api_url}/api/auth/login", json=admin_credentials)
        token = login.json().get("session_token")
        resp = requests.post(f"{api_url}/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestRegistration:
    """Test user registration validation."""

    def test_register_missing_fields(self, api_url):
        resp = requests.post(f"{api_url}/api/auth/register", json={"email": "test@test.com"})
        assert resp.status_code in (422, 429)  # 429 = rate limited on auth endpoints

    def test_register_duplicate_email(self, api_url):
        resp = requests.post(f"{api_url}/api/auth/register", json={
            "email": "kelliott@urtech.org", "password": "test123", "name": "Duplicate"
        })
        assert resp.status_code in (400, 409, 429)  # 429 = rate limited on auth endpoints
