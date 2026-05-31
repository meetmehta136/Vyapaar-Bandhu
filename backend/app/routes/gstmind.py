"""GSTMind RAG route — query the CGST Act + CBIC circular knowledge base."""
import os, logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gstmind", tags=["gstmind"])

DB_PATH = os.getenv("GSTMIND_DB_PATH", "data/chromadb")
MODEL_NAME = os.getenv("GSTMIND_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

_index: Optional[object] = None
_responder: Optional[object] = None


def get_index():
    global _index
    if _index is None:
        from app.services.gstmind_index import GSTMindIndex
        _index = GSTMindIndex(db_path=DB_PATH, model_name=MODEL_NAME)
    return _index


def get_responder():
    global _responder
    if _responder is None:
        from app.services.gstmind_responder import GSTMindResponder
        _responder = GSTMindResponder()
    return _responder


class GSTMindQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class GSTMindResponse(BaseModel):
    answer: str
    citations: list[dict]
    needs_more_info: bool
    error: str | None = None


@router.post("/ask", response_model=GSTMindResponse)
def ask_gstmind(body: GSTMindQuery):
    """Ask GSTMind a question about GST compliance, ITC, or CGST Act provisions."""
    index = get_index()
    responder = get_responder()

    if index.count() == 0:
        return GSTMindResponse(
            answer="The GSTMind knowledge base is empty. Please build the index first by running the build script.",
            citations=[],
            needs_more_info=False,
            error="Index not built",
        )

    log.info(f"Query: {body.query[:100]}...")
    retrieved = index.query(body.query, top_k=body.top_k)
    log.info(f"Retrieved {len(retrieved)} chunks")

    result = responder.answer(body.query, retrieved)
    return GSTMindResponse(**result)


@router.get("/status")
def gstmind_status():
    """Check GSTMind index and responder status."""
    index = get_index()
    responder = get_responder()
    return {
        "index_documents": index.count(),
        "index_path": str(Path(DB_PATH).resolve()),
        "responder_configured": responder.is_available(),
        "model": MODEL_NAME,
    }
