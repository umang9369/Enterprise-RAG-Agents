import time

import logfire
import requests
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from app.config import settings

_JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
_JINA_RERANK_MODEL = "jina-reranker-v3"

_ranker = None

class _JinaReranker:
    """Thin wrapper around the Jina Reranker API."""

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[str]:
        """Score and reorder documents against the query via the Jina API."""
        response = requests.post(
            _JINA_RERANK_URL,
            headers={
                "Authorization": f"Bearer {settings.JINA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": _JINA_RERANK_MODEL,
                "query": query,
                "documents": documents,
                "top_n": top_n,
                "return_documents": True,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()

        results = payload.get("results", [])

        