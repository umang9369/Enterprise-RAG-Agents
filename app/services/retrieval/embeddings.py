import logfire
import requests
from tenacity import retry,before_sleep_log,stop_after_attempt,wait_exponential
from app.config import settings

BTACH_SIZE = 64
_EMBEDDING_DIM = 1024
_JINA_EMBEDDING_URL = "https://api.jina.ai/v1/embeddings"
_JINA_MODEL = "jina-embeddings-v3"
_FALLBACK_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
_active_model = None
_model_type: str | None = None  # "jina" or "fallback"

#Model initialisation

def _load_fallback():
    """Load the local mxbai fallback model."""
    from sentence_transformers import SentenceTransformer
    logfire.info(f"loading fallback model ({_FALLBACK_MODEL},{_EMBEDDING_DIM}-dim).")
    return SentenceTransformer(_FALLBACK_MODEL)

def _probe_jina_api()->bool:
    """Verify the Jina Embeddings API is reachable with the configured key."""

    if not settings.JINA_API_KEY:
        logfire.info("JINA_API_KEY not set — will use local fallback embeddings.")
        return False

    try:
        response = requests.get(
            _JINA_EMBEDDING_URL,
            headers={
                "Authorization": f"Bearer {settings.JINA_API_KEY}",
                "Content-Type": "application/json",
                },
                json={
                    "model": _JINDA_MODEL,
                    "task": "retrieval.query",
                    "normalized": True,
                    "input": ["probe"],
                },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if not payload.get("data"):
            raise RuntimeError("jina api returned  empty data")
        logfire.info("Jina Embeddings API is reachable and working.")   
        return true

    except Exception as e:
        logfire.warning(f"Jina Embeddings API probe failed: {e}")
        return False   