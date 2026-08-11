```python
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_URL = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_COLLECTION = "enterprise-rag-agents"

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_API_KEY = os.getenv("GROQ_FALLBACK_API_KEY")

    # Logfire is optional for local development.
    LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
    LOGFIRE_BASE_URL = os.getenv("LOGFIRE_BASE_URL")


settings = Settings()
```
