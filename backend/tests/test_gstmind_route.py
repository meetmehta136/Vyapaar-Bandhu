"""Tests for GSTMind RAG route (POST /api/gstmind/ask, GET /api/gstmind/status)."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_index():
    """Patch the global _index in app.routes.gstmind."""
    with patch("app.routes.gstmind.get_index") as mock:
        idx = MagicMock()
        idx.count.return_value = 994
        idx.query.return_value = [
            {
                "chunk_id": "cgst_s17_ss5",
                "score": 0.92,
                "text": "Blocked ITC under Section 17(5)...",
                "citation": "CGST Act, 2017 — Section 17(5)",
                "source_type": "cgst_act",
                "section": "17",
                "chapter": "Input Tax Credit",
            }
        ]
        mock.return_value = idx
        yield mock


@pytest.fixture
def mock_empty_index():
    with patch("app.routes.gstmind.get_index") as mock:
        idx = MagicMock()
        idx.count.return_value = 0
        mock.return_value = idx
        yield mock


@pytest.fixture
def mock_responder():
    with patch("app.routes.gstmind.get_responder") as mock:
        resp = MagicMock()
        resp.answer.return_value = {
            "answer": "As per Section 17(5) of the CGST Act, ITC is blocked for...",
            "citations": [{"citation": "CGST Act, 2017 — Section 17(5)", "relevance_score": 0.92}],
            "needs_more_info": False,
            "error": None,
        }
        resp.is_available.return_value = True
        mock.return_value = resp
        yield mock


@pytest.fixture
def mock_unconfigured_responder():
    with patch("app.routes.gstmind.get_responder") as mock:
        resp = MagicMock()
        resp.is_available.return_value = False
        resp.answer.return_value = {
            "answer": "GSTMind is not configured. Set ANTHROPIC_API_KEY in environment.",
            "citations": [],
            "needs_more_info": False,
            "error": "API key not configured",
        }
        mock.return_value = resp
        yield mock


# ── GET /api/gstmind/status ───────────────────────────────────────────────────

class TestGSTMindStatus:
    def test_status_returns_index_count(self, mock_index, mock_responder):
        resp = client.get("/api/gstmind/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["index_documents"] == 994
        assert data["responder_configured"] is True

    def test_status_empty_index(self, mock_empty_index, mock_responder):
        resp = client.get("/api/gstmind/status")
        assert resp.status_code == 200
        assert resp.json()["index_documents"] == 0


# ── POST /api/gstmind/ask ─────────────────────────────────────────────────────

class TestGSTMindAsk:
    def test_ask_returns_answer(self, mock_index, mock_responder):
        resp = client.post("/api/gstmind/ask", json={"query": "When is ITC blocked?"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["answer"]) > 0
        assert len(data["citations"]) > 0
        assert data["needs_more_info"] is False
        assert data["error"] is None

    def test_ask_empty_index(self, mock_empty_index, mock_responder):
        resp = client.post("/api/gstmind/ask", json={"query": "What is ITC?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "empty" in data["answer"].lower() or "build" in data["answer"].lower()

    def test_ask_no_api_key(self, mock_index, mock_unconfigured_responder):
        resp = client.post("/api/gstmind/ask", json={"query": "What is ITC?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "not configured" in data["answer"].lower()

    def test_ask_empty_query(self, mock_index, mock_responder):
        resp = client.post("/api/gstmind/ask", json={"query": ""})
        assert resp.status_code == 422  # Validation error

    def test_ask_very_long_query(self, mock_index, mock_responder):
        long_q = "x" * 2500
        resp = client.post("/api/gstmind/ask", json={"query": long_q})
        assert resp.status_code == 422

    def test_ask_top_k_out_of_range(self, mock_index, mock_responder):
        resp = client.post("/api/gstmind/ask", json={"query": "ITC", "top_k": 50})
        assert resp.status_code == 422

    def test_ask_citations_structure(self, mock_index, mock_responder):
        resp = client.post("/api/gstmind/ask", json={"query": "Section 17"})
        assert resp.status_code == 200
        data = resp.json()
        for c in data["citations"]:
            assert "citation" in c
            assert "relevance_score" in c

    def test_ask_invalid_json(self, mock_index, mock_responder):
        resp = client.post("/api/gstmind/ask", json={"not_query": "test"})
        assert resp.status_code == 422  # Missing required 'query' field

    def test_ask_index_error(self, mock_index, mock_responder):
        mock_index.return_value.query.side_effect = RuntimeError("ChromaDB error")
        with pytest.raises(RuntimeError):
            client.post("/api/gstmind/ask", json={"query": "ITC"})
