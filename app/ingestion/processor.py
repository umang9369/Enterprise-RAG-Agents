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
from app.ingestion.loaders.office import parse_office
from app.services.retrieval.embeddings import embed_text,get_embedding_dim

# Local folder where parsed + chunked JSON metadata is saved (replaces GCS processed bucket)

PROCESSED_DATA_DIR = "processed_data"

# Initialize Qdrant Client

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)

def save_processed_locally(data: dict, source_type: str, filename: str) -> str:
    """Save parsed chunk metadata as JSON in processed_data/<source_type>/."""
    folder = os.path.join(PROCESSED_DATA_DIR, source_type)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{filename}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return dest


def process_file(file_path: str, filename: str, source_type: str):
    """Parse → chunk → save locally → embed → index in Qdrant."""
    with logfire.span("Processing File", file=filename, source=source_type):
        try:
            # 1. Extract text based on file extension
            ext = filename.lower().rsplit(".", 1)[-1]
            if ext == "pdf":
                full_text = parse_pdf(file_path)
            elif ext in ("html", "htm"):
                full_text = parse_html(file_path)
            elif ext == "txt":
                full_text = parse_text(file_path)
            elif ext in ("docx", "pptx"):
                full_text = parse_office(file_path)