"""Build and manage ChromaDB index for GSTMind RAG.
Indexes CGST Act sections + CBIC circulars for dense retrieval."""
import json, os, logging, shutil
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_CHUNKS_PATH = "ml/data/processed/all_chunks.jsonl"
DEFAULT_DB_PATH = "data/chromadb"


def _prefix_query(text: str) -> str:
    """E5 models require 'query: ' prefix for queries."""
    return f"query: {text}"


def _prefix_doc(text: str) -> str:
    """E5 models require 'passage: ' prefix for documents."""
    return f"passage: {text}"


class GSTMindIndex:
    """ChromaDB index for CGST Act + CBIC circular chunks."""

    def __init__(self, db_path: str | Path, model_name: str = DEFAULT_MODEL):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._model = None
        self._collection = None
        self._client = None

    # ── Model ────────────────────────────────────────────────────────────────

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            log.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(
                self.model_name,
                trust_remote_code=True,
            )
            log.info(f"Model ready — dim={self._model.get_sentence_embedding_dimension()}")
        return self._model

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        model = self._load_model()
        prefixed = [_prefix_query(t) if is_query else _prefix_doc(t) for t in texts]
        return model.encode(
            prefixed,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()

    # ── Client / Collection ──────────────────────────────────────────────────

    @property
    def client(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            self._client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            from chromadb.errors import NotFoundError
            name = "gstmind"
            try:
                self._collection = self.client.get_collection(name)
                log.info(f"Loaded existing collection '{name}' ({self._collection.count()} docs)")
            except (ValueError, NotFoundError):
                self._collection = self.client.create_collection(
                    name,
                    metadata={"hnsw:space": "cosine"},
                )
                log.info(f"Created new collection '{name}'")
        return self._collection

    # ── Build ─────────────────────────────────────────────────────────────────

    def build_index(self, chunks_path: str | Path):
        """Build index from all_chunks.jsonl."""
        chunks = []
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))

        log.info(f"Building index from {len(chunks)} chunks")

        ids = []
        texts = []
        metadatas = []
        for c in chunks:
            ids.append(c["chunk_id"])
            texts.append(c["text"])
            metadatas.append({
                "citation": c.get("citation", ""),
                "source_type": c.get("source_type", ""),
                "section": str(c.get("section", "")),
                "sub_section": str(c.get("sub_section", "")),
                "chapter": str(c.get("chapter", "")),
                "circular_number": str(c.get("circular_number", "")),
            })

        log.info("Embedding documents...")
        embeddings = self.embed(texts)

        log.info("Adding to ChromaDB...")
        # Add in batches of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.add(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=texts[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )
            log.info(f"  Added {min(i+batch_size, len(ids))}/{len(ids)}")

        log.info(f"Index built — {self.collection.count()} documents")

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(self, query_text: str, top_k: int = 15) -> list[dict]:
        """Multi-stage retrieval.

        Stage 1: ChromaDB dense search (top-15).
        Stage 2: Deduplicate by section.
        Stage 3: Return top-5 with metadata.
        """
        if not query_text or not query_text.strip():
            return []

        query_emb = self.embed([query_text], is_query=True)[0]
        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        deduped = []
        seen_sections = set()
        for i, cid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            section = meta.get("section", "")
            # Convert cosine distance to similarity score [0, 1]
            raw_dist = float(results["distances"][0][i]) if results.get("distances") else 0.0
            similarity = 1.0 - (raw_dist / 2.0)  # Cosine dist range [0,2]
            if section and section != "0":
                if section in seen_sections:
                    continue
                seen_sections.add(section)
            deduped.append({
                "chunk_id": cid,
                "score": round(similarity, 4),
                "text": results["documents"][0][i],
                "citation": meta.get("citation", ""),
                "source_type": meta.get("source_type", ""),
                "section": section,
                "chapter": meta.get("chapter", ""),
            })
            if len(deduped) >= 5:
                break

        return deduped

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def reset(self):
        log.warning("Resetting index...")
        self.close()
        if self.db_path.exists():
            shutil.rmtree(self.db_path, ignore_errors=True)
        self.db_path.mkdir(parents=True, exist_ok=True)
        # Reset state so next access creates fresh client + collection
        self._client = None
        self._collection = None
        log.info("Index reset")

    def close(self):
        """Close ChromaDB client and release file locks."""
        if self._client is not None:
            try:
                del self._client
            except Exception:
                pass
            self._client = None
        self._collection = None

    def count(self) -> int:
        return self.collection.count()
