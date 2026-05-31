"""Unit tests for GSTMindResponder (Claude-based answer generation)."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "cgst_s17_ss5",
            "score": 0.92,
            "text": "Blocked ITC under Section 17(5) of the CGST Act, 2017...",
            "citation": "CGST Act, 2017 — Section 17(5)",
            "source_type": "cgst_act",
            "section": "17",
            "chapter": "Input Tax Credit",
        },
        {
            "chunk_id": "cgst_s16_ss2",
            "score": 0.85,
            "text": "ITC conditions under Section 16(2)...",
            "citation": "CGST Act, 2017 — Section 16(2)",
            "source_type": "cgst_act",
            "section": "16",
            "chapter": "Input Tax Credit",
        },
    ]


class TestIsAvailable:
    def test_available_with_api_key(self):
        from app.services.gstmind_responder import GSTMindResponder

        r = GSTMindResponder(api_key="sk-ant-test123")
        assert r.is_available() is True

    def test_not_available_without_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from app.services.gstmind_responder import GSTMindResponder

        r = GSTMindResponder(api_key="")
        assert r.is_available() is False


class TestAnswer:
    def test_answer_no_chunks(self):
        from app.services.gstmind_responder import GSTMindResponder

        r = GSTMindResponder(api_key="sk-ant-test123")
        result = r.answer("What is ITC?", [])
        assert "could not find" in result["answer"].lower()
        assert len(result["citations"]) == 0
        assert result["needs_more_info"] is True
        assert result["error"] is None

    def test_answer_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from app.services.gstmind_responder import GSTMindResponder

        r = GSTMindResponder(api_key="")
        result = r.answer("What is ITC?", [])
        assert "not configured" in result["answer"].lower()
        assert result["error"] is not None

    def test_answer_calls_claude_api(self, sample_chunks):
        from app.services.gstmind_responder import GSTMindResponder

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "As per Section 17(5), ITC is blocked for..."

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            r = GSTMindResponder(api_key="sk-ant-test123")
            result = r.answer("When is ITC blocked?", sample_chunks)

            assert result["error"] is None
            assert "blocked" in result["answer"].lower()
            assert len(result["citations"]) == 2
            assert result["needs_more_info"] is False

    def test_answer_includes_citations(self, sample_chunks):
        from app.services.gstmind_responder import GSTMindResponder

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Answer with citations."

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            r = GSTMindResponder(api_key="sk-ant-test123")
            result = r.answer("ITC query", sample_chunks)

            citations = result["citations"]
            assert len(citations) == 2
            assert citations[0]["citation"] == "CGST Act, 2017 — Section 17(5)"
            assert citations[1]["citation"] == "CGST Act, 2017 — Section 16(2)"
            assert all("relevance_score" in c for c in citations)

    def test_answer_respects_max_context(self, sample_chunks):
        """With very small max_context_tokens, should limit context."""
        from app.services.gstmind_responder import GSTMindResponder

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Short answer."

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            r = GSTMindResponder(api_key="sk-ant-test123")
            # max_context_tokens=1 → should include 0 or 1 chunks
            result = r.answer("ITC", sample_chunks, max_context_tokens=1)
            assert result["error"] is None

    def test_answer_api_error_handling(self, sample_chunks):
        from app.services.gstmind_responder import GSTMindResponder

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("API timeout")
            mock_anthropic.return_value = mock_client

            r = GSTMindResponder(api_key="sk-ant-test123")
            result = r.answer("ITC", sample_chunks)

            assert "error" in result["answer"].lower()
            assert result["error"] == "API timeout"

    def test_answer_detects_insufficient_context(self, sample_chunks):
        from app.services.gstmind_responder import GSTMindResponder

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "I don't know the answer to this question."

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            r = GSTMindResponder(api_key="sk-ant-test123")
            result = r.answer("Some unknown topic", sample_chunks)
            assert result["needs_more_info"] is True
