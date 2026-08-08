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