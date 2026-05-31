"""Tests for auth routes — signup, login, refresh, me."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestSignup:
    def test_signup_success(self, client):
        resp = client.post("/auth/signup", json={
            "name": "Test CA",
            "email": "test@ca.com",
            "password": "Test@1234",
            "phone": "+919876543210",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["email"] == "test@ca.com"
        assert data["name"] == "Test CA"

    def test_signup_duplicate_email(self, client):
        resp = client.post("/auth/signup", json={
            "name": "Another CA",
            "email": "test@ca.com",
            "password": "Pass@1234",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()


class TestLogin:
    def test_login_success(self, client):
        resp = client.post("/auth/login", json={
            "email": "test@ca.com",
            "password": "Test@1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["email"] == "test@ca.com"

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={
            "email": "test@ca.com",
            "password": "WrongPassword123!",
        })
        assert resp.status_code == 401

    def test_login_wrong_email(self, client):
        resp = client.post("/auth/login", json={
            "email": "nonexistent@ca.com",
            "password": "Test@1234",
        })
        assert resp.status_code == 401


class TestGetMe:
    def test_get_me_with_valid_token(self, client):
        login_resp = client.post("/auth/login", json={
            "email": "test@ca.com",
            "password": "Test@1234",
        })
        token = login_resp.json()["access_token"]
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@ca.com"

    def test_get_me_without_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_token(self, client):
        login_resp = client.post("/auth/login", json={
            "email": "test@ca.com",
            "password": "Test@1234",
        })
        old_refresh_token = login_resp.json()["refresh_token"]

        # Use refresh token → get new tokens
        resp = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Old refresh token must fail (rotation)
        resp2 = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
        assert resp2.status_code == 401
