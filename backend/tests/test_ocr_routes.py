"""Tests for OCR routes — auth enforcement and file validation."""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _signup_and_login(client, email, password="Test@1234"):
    resp = client.post("/auth/signup", json={
        "name": "Test User",
        "email": email,
        "password": password,
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestOCRAuth:
    def test_ocr_upload_requires_auth(self, client):
        resp = client.post("/ocr/upload", files={"file": ("test.jpg", b"fake-image-data", "image/jpeg")})
        assert resp.status_code == 401

    def test_ocr_upload_rejects_text_file(self, client):
        token = _signup_and_login(client, "ocr@ca.com")

        resp = client.post(
            "/ocr/upload",
            files={"file": ("test.txt", b"not an image", "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 422)

    def test_ocr_upload_rejects_large_file(self, client):
        token = _signup_and_login(client, "ocr2@ca.com")

        large_data = b"x" * (11 * 1024 * 1024)
        resp = client.post(
            "/ocr/upload",
            files={"file": ("large.jpg", large_data, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 422)
