"""GSTMindResponder — Claude-based generation with retrieved chunk context."""
import json, os, logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are GSTMind, an expert GST consultant for Indian small businesses.

You have access to the following retrieved passages from the CGST Act, 2017 and CBIC circulars.
Answer the user's question based ONLY on the provided context.

Rules:
1. Cite specific sections and circulars when answering. Example format:
   "As per Section 16(2) of the CGST Act, 2017..."
2. If the context does not contain enough information to answer, say so honestly.
   Do NOT make up laws or cite sections not present in the context.
3. Keep answers concise and actionable. Use simple language suitable for small business owners.
4. When answering about ITC, blocked credits, or penalties, be specific about conditions and exceptions.
5. If the user asks in Hindi or Hinglish, you may respond in the same language."""


class GSTMindResponder:
    """Generates answers using Claude Sonnet with retrieved context."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def answer(self, query: str, retrieved_chunks: list[dict],
               max_context_tokens: int = 3000) -> dict:
        """Generate an answer from query + retrieved context.

        Args:
            query: User's question.
            retrieved_chunks: List from GSTMindIndex.query().
            max_context_tokens: Limit context to avoid prompt overflow.

        Returns:
            dict with keys: answer, citations, needs_more_info, error
        """
        if not self.is_available():
            return {
                "answer": "GSTMind is not configured. Set ANTHROPIC_API_KEY in environment.",
                "citations": [],
                "needs_more_info": False,
                "error": "API key not configured",
            }

        if not retrieved_chunks:
            return {
                "answer": "I could not find relevant information in the GST database to answer your question. Please rephrase or ask about a specific section of the CGST Act.",
                "citations": [],
                "needs_more_info": True,
                "error": None,
            }

        context_parts = []
        citations = []
        total_tokens_est = 0

        for chunk in retrieved_chunks:
            text = chunk.get("text", "")
            citation = chunk.get("citation", "")
            score = chunk.get("score", 0)
            # Estimate tokens: ~4 chars per token
            est_tokens = len(text) // 4 + 1
            if total_tokens_est + est_tokens > max_context_tokens:
                break
            context_parts.append(f"[Citation: {citation}]\n{text}\n")
            citations.append({
                "citation": citation,
                "source_type": chunk.get("source_type", ""),
                "section": chunk.get("section", ""),
                "relevance_score": score,
            })
            total_tokens_est += est_tokens

        context = "\n---\n".join(context_parts)

        prompt = f"""Question: {query}

Retrieved Context:
{context}

Answer the question based on the context above. If the context is insufficient, say so."""

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            answer_text = resp.content[0].text
            needs_more = any(phrase in answer_text.lower()
                             for phrase in ["don't know", "cannot answer", "not enough",
                                            "insufficient", "no information", "does not contain"])
            return {
                "answer": answer_text,
                "citations": citations,
                "needs_more_info": needs_more,
                "error": None,
            }
        except Exception as e:
            log.error(f"Claude API error: {e}")
            return {
                "answer": "I encountered an error generating the response. Please try again.",
                "citations": citations,
                "needs_more_info": False,
                "error": str(e),
            }
