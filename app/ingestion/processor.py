import json
import os
import sys
import uuid


# logfire must be configured before app module imports so spans from
# chunking/loaders/embedding are captured from the start.

import logfire
from app.config import settings

_logfire_base_url=settings.LOGFIRE_BASE_URL
if not _logfire_base_url and settings.LOGFIRE_TOKEN:
    if settings.LOGFIRE_TOKEN.startwith("pylf_v2_eu_"):
        _logfire_base_url="https://logfire-eu.pydantic.dev"

if settings.LOGFIRE_TOKEN :
    logfire.configure(
        token=settings.LOGFIRE_TOKEN,
        service_name="enterprise-ingestion-service",
        advanced=logfire.AdvancedOptions(base_url=_logfire_base_url) if _logfire_base_url else None
    )


from qdrant_client import QdrantClient
from qdrant_client.http import models 
from app.ingestion.chunking.splitter import chunk_text
from app.ingestion.loaders.html import parse_html
from app.ingestion.loaders.pdf import parse_pdf
from app.ingestion.loaders.text import parse_text
from app.services.retrieval.embeddings import embed_text,get_embedding_dim

