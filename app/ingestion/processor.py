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
            else:
                logfire.warning(f"Skipping unsupported file type: {filename}")
                return

            if not full_text or not full_text.strip():
                logfire.warning(f"No text extracted from {filename} — skipping.")
                return

            # 2. Chunk text
            chunks = chunk_text(full_text)
            if not chunks:
                return

            # 3. Save processed metadata locally
            processed_data = {
                "filename": filename,
                "source_type": source_type,
                "chunks": chunks,
            }
            local_path = save_processed_locally(processed_data, source_type, filename)
            logfire.info(f"Saved processed data → {local_path}")

            # 4. Embed and index in Qdrant
            with logfire.span("Vectorizing & Indexing"):
                embeddings = embed_texts(chunks)
                points = [
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={
                            "text": chunk,
                            "source": filename,
                            "source_type": source_type,
                        },
                    )
                    for chunk, vector in zip(chunks, embeddings)
                ]

                qdrant_client.upsert(
                    collection_name=settings.QDRANT_COLLECTION,
                    points=points,
                )
                logfire.info(f"Indexed {len(points)} points to Qdrant from {filename}.")

        except Exception as e:
            logfire.error(f"Failed to process {filename}: {e}")


