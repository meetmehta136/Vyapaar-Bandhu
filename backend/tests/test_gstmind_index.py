"""Unit tests for GSTMindIndex (ChromaDB wrapper)."""
import json, tempfile, pytest
from pathlib import Path


@pytest.fixture
def sample_chunks(tmp_path):
    chunks = [
        {"chunk_id": "cgst_s17_ss5", "citation": "CGST Act, 2017 — Section 17(5)",
         "source_type": "cgst_act", "section": 17, "sub_section": "5",
         "chapter": "Input Tax Credit",
         "text": "Blocked ITC under Section 17(5) of the CGST Act, 2017...",
         "token_count": 120},
        {"chunk_id": "cgst_s16_ss2", "citation": "CGST Act, 2017 — Section 16(2)",
         "source_type": "cgst_act", "section": 16, "sub_section": "2",
         "chapter": "Input Tax Credit",
         "text": "ITC conditions under Section 16(2)...", "token_count": 100},
        {"chunk_id": "cgst_s18_ss1", "citation": "CGST Act, 2017 — Section 18(1)",
         "source_type": "cgst_act", "section": 18, "sub_section": "1",
         "chapter": "Input Tax Credit",
         "text": "ITC reversal under Section 18(1)...", "token_count": 90},
        {"chunk_id": "cbic_circular_123", "citation": "CBIC Circular No. 123",
         "source_type": "cbic_circular", "circular_number": "123",
         "sections_referenced": [16, 17],
         "text": "Clarification on ITC eligibility...", "token_count": 80},
        {"chunk_id": "cgst_s9_ss3", "citation": "CGST Act, 2017 — Section 9(3)",
         "source_type": "cgst_act", "section": 9, "sub_section": "3",
         "chapter": "Levy and Collection of Tax",
         "text": "Reverse charge mechanism under Section 9(3)...", "token_count": 110},
    ]
    path = tmp_path / "test_chunks.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return str(path), chunks


@pytest.fixture
def index(sample_chunks):
    from app.services.gstmind_index import GSTMindIndex

    db_dir = tempfile.mkdtemp()
    idx = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
    idx.build_index(sample_chunks[0])
    yield idx
    idx.close()
    import shutil
    shutil.rmtree(db_dir, ignore_errors=True)


# ── Build Index ───────────────────────────────────────────────────────────────

class TestBuildIndex:
    def test_build_index_creates_collection(self, sample_chunks):
        from app.services.gstmind_index import GSTMindIndex

        chunks_path, _ = sample_chunks
        db_dir = tempfile.mkdtemp()
        index = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
        try:
            index.build_index(chunks_path)
            assert index.count() == 5
        finally:
            index.close()
            import shutil; shutil.rmtree(db_dir, ignore_errors=True)

    def test_build_index_incremental(self, sample_chunks):
        from app.services.gstmind_index import GSTMindIndex

        chunks_path, _ = sample_chunks
        db_dir = tempfile.mkdtemp()
        index = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
        try:
            index.build_index(chunks_path)
            index.build_index(chunks_path)
            assert index.count() == 5
        finally:
            index.close()
            import shutil; shutil.rmtree(db_dir, ignore_errors=True)

    def test_build_index_empty_file(self, tmp_path):
        from app.services.gstmind_index import GSTMindIndex

        empty_path = tmp_path / "empty.jsonl"
        empty_path.write_text("", encoding="utf-8")
        db_dir = tempfile.mkdtemp()
        index = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
        try:
            index.build_index(str(empty_path))
            assert index.count() == 0
        finally:
            index.close()
            import shutil; shutil.rmtree(db_dir, ignore_errors=True)

    def test_reset_clears_index(self, sample_chunks):
        from app.services.gstmind_index import GSTMindIndex

        chunks_path, _ = sample_chunks
        db_dir = tempfile.mkdtemp()
        index = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
        try:
            index.build_index(chunks_path)
            assert index.count() == 5
            # Delete collection via ChromaDB API instead of filesystem
            index.close()
            idx2 = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
            from chromadb.errors import NotFoundError
            try:
                idx2.client.delete_collection("gstmind")
            except NotFoundError:
                pass
            idx2.close()

            idx3 = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
            assert idx3.count() == 0
            idx3.close()
        finally:
            import shutil; shutil.rmtree(db_dir, ignore_errors=True)


# ── Query ─────────────────────────────────────────────────────────────────────

class TestQuery:
    def test_query_returns_results(self, index):
        results = index.query("When is ITC blocked?", top_k=10)
        assert len(results) > 0
        assert len(results) <= 5
        for r in results:
            assert "chunk_id" in r
            assert "score" in r
            assert "text" in r
            assert "citation" in r
            assert "source_type" in r
            assert 0.0 <= r["score"] <= 1.0

    def test_query_empty_string(self, index):
        assert index.query("") == []
        assert index.query("   ") == []

    def test_query_no_match(self, index):
        results = index.query("zzzzzzzzzzzzzzzzzzzz", top_k=10)
        assert isinstance(results, list)

    def test_query_dedup_same_section(self, index):
        results = index.query("ITC credit input tax", top_k=10)
        sections = [r["section"] for r in results if r["section"]]
        assert len(sections) == len(set(sections))


# ── Edge Cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_persist_across_sessions(self, sample_chunks):
        from app.services.gstmind_index import GSTMindIndex

        chunks_path, _ = sample_chunks
        db_dir = tempfile.mkdtemp()
        index = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
        try:
            index.build_index(chunks_path)
            index.close()

            index2 = GSTMindIndex(db_path=db_dir, model_name="all-MiniLM-L6-v2")
            assert index2.count() == 5
            results = index2.query("ITC blocked")
            assert len(results) > 0
            index2.close()
        finally:
            import shutil; shutil.rmtree(db_dir, ignore_errors=True)

    def test_custom_model_name(self):
        from app.services.gstmind_index import GSTMindIndex

        index = GSTMindIndex(db_path=tempfile.mkdtemp(), model_name="all-MiniLM-L6-v2")
        assert index.model_name == "all-MiniLM-L6-v2"
        index.close()
