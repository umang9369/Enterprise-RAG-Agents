import logfire
import requests
from tenacity import retry,before_sleep_log,stop_after_attempt,wait_exponential
from app.config import settings



# Constants for embedding model selection and configuration


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



def _init():
    """Initialise embedding provider once per process. Called lazily on first use."""
    global _active_model,model_type
    if _active_model is not None or _model_type is not None:
        return

    if _probe_jina_api():
        _active_model = None  # Jina API is stateless; no local model to keep
        _model_type = "jina"

    else:
        _active_model = _load_fallback()
        _model_type = "fallback"


#         _init()
#           ↓
#     Already initialized?
#       /          \
#    YES           NO
#     ↓             ↓
#   return      Test Jina
#                 ↓
#          ┌────┴────┐
#          Works      Failed
#             ↓           ↓
#          Use Jina   Load mxbai
#            ↓           ↓
#       model_type    model_type
#        = "jina"    = "fallback"


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_embedding_model():
    """Return the active embedding model and its type."""
    _init()
    return _EMBEDDING_DIM


# ── Jina API embedding ─

@retry(
    stop=stop_after_prompt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
    before_sleep=before_sleep_log(logfire,"warning")
)
def _embed_jina_batch(texts:list[str],task:str)->list[list[float]]:
    """Call the Jina Embeddings API for a single batch."""
    response = request.post(
        _JINA_EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": _JINA_MODEL,
            "task": task,
            "normalized": True,
            "input": texts,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    results=payload.get("data",[])
    # Sort by index because the API may not preserve order in rare cases
    results_sorted=sorted(results,key=lambda x:x.get("index",0))
    return [item["embedding"] for item in results_sorted]
