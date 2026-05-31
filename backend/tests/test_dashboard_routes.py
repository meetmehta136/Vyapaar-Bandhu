"""Tests for dashboard routes — auth enforcement."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestDashboardAuth:
    def test_dashboard_requires_auth(self, client):
        resp = client.get("/api/dashboard/stats")
        assert resp.status_code == 401

    def test_clients_requires_auth(self, client):
        resp = client.get("/api/clients")
        assert resp.status_code == 401

    def test_invoices_requires_auth(self, client):
        resp = client.get("/api/invoices")
        assert resp.status_code == 401
