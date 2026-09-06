import logfire
from app.config import settings

_logfire_base_url = settings.LOGFIRE_BASE_URL
if not _logfire_base_url and settings.LOGFIRE_TOKEN:
    if settings.LOGFIRE_TOKEN.startswith("pylf_v2_eu_"):
        _logfire_base_url = "https://logfire-eu.pydantic.dev"

logfire.configure(
    token=settings.LOGFIRE_TOKEN,
    advanced=logfire.AdvancedOptions(base_url=_logfire_base_url) if _logfire_base_url else None,
)

import hmac
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import Counter
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agent.graph import build_graph
from app.guardrails.rails import guard, initialize_rails
from app.health import router as health_router
from app.logging import set_request_id
from app.services.health.connection_checker import check_all_connections, log_connection_summary

GUARDRAILS_BLOCKS_TOTAL = Counter(
    "guardrails_blocks_total",
    "Number of requests blocked or allowed by guardrails",
    ["blocked"],
)
_security = HTTPBearer(auto_error=False)


def _build_limiter() -> tuple[Limiter, str]:
    """Build the rate limiter, preferring Redis when credentials are available."""
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            return Limiter(key_func=get_remote_address, storage_uri=settings.redis_url), "redis"
        except Exception:
            pass
    return Limiter(key_func=get_remote_address), "memory"


limiter, _rate_limiter_storage = _build_limiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events.
    Replaces the deprecated @app.on_event("startup") pattern.
    """
    # Startup
    initialize_rails()

    # Build the agent graph with the production checkpointer (Postgres by default).
    app.state.rag_agent = build_graph()

    app.state.rate_limiter_storage = _rate_limiter_storage
    app.state.rate_limiter_enabled = _rate_limiter_storage == "redis"
    logfire.info("🚦 Rate limiting initialized", storage=_rate_limiter_storage)

    # Verify all external dependencies are reachable.
    connection_results = check_all_connections()
    all_healthy = log_connection_summary(connection_results)
    if settings.STRICT_STARTUP and not all_healthy:
        failed = [name for name, r in connection_results.items() if not r.healthy]
        raise RuntimeError(f"STRICT_STARTUP enabled; failing services: {', '.join(failed)}")

    if not settings.API_KEY:
        logfire.warning("🔓 RAG_API_KEY is not set — /query is open to anyone. Set it in production.")

    logfire.info("✅ Enterprise RAG API startup complete.")

    yield  # Application runs here

    # Shutdown (optional cleanup)
    logfire.info("🛑 Enterprise RAG API shutting down.")


# Single authoritative FastAPI app instance
app = FastAPI(
    title="Enterprise Agentic RAG API",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(health_router)


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    """
    Require a valid bearer token when RAG_API_KEY is configured.
    In development, omit RAG_API_KEY to disable authentication.
    """
    if not settings.API_KEY:
        # Development mode: no API key required.
        return None

    if not credentials or not hmac.compare_digest(credentials.credentials, settings.API_KEY):
        logfire.warning("🔒 Unauthorized /query request: invalid or missing API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


class QueryRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=10_000)
    thread_id: str | None = "default_user"


@app.get("/")
def home():
    return {"message": "Enterprise LangGraph RAG API is live."}


@app.get("/graph")
def get_graph_image(_api_key: str = Depends(verify_api_key)):
    """
    Returns the Mermaid image of the agent's workflow.
    """
    try:
        png_bytes = app.state.rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logfire.error("Could not generate graph image", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Could not generate graph image."},
        )


@app.post("/query")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
def query(
    request: Request,
    body: QueryRequest,
    _api_key: str = Depends(verify_api_key),
):
    """
    Runs the LangGraph RAG pipeline synchronously.
    Returns the final answer, thought process, status, and sources.
    """
    q = body.q
    thread_id = body.thread_id
    request_id = str(uuid.uuid4())
    set_request_id(request_id)

    start = time.perf_counter()
    with logfire.span("🔍 /query", request_id=request_id, thread_id=thread_id):
        # Gate: run guardrails synchronously so blocked requests never run the graph.
        rail_fired, rail_response = guard(q)
        if rail_fired:
            GUARDRAILS_BLOCKS_TOTAL.labels(blocked="true").inc()
            elapsed = time.perf_counter() - start
            logfire.info(
                "🛡️ Request blocked by guardrails",
                request_id=request_id,
                thread_id=thread_id,
                elapsed_seconds=round(elapsed, 3),
            )
            return {
                "question": q,
                "answer": rail_response,
                "thought_process": ["Intent: Guardrails Fired", "Retrieval: Skipped"],
                "status": "Blocked by guardrails.",
                "sources": [],
                "request_id": request_id,
            }

        GUARDRAILS_BLOCKS_TOTAL.labels(blocked="false").inc()

        try:
            rag_agent = app.state.rag_agent
            initial_state = {
                "messages": [{"role": "user", "content": q}],
                "current_query": q,
                "documents": [],
                "plan": ["Start"],
                "status": "Initializing Graph...",
            }
            config = {"configurable": {"thread_id": thread_id}}
            final_output = rag_agent.invoke(initial_state, config=config)

            elapsed = time.perf_counter() - start
            logfire.info(
                "✅ RAG pipeline completed",
                request_id=request_id,
                thread_id=thread_id,
                elapsed_seconds=round(elapsed, 3),
            )
            return {
                "question": q,
                "answer": final_output.get("final_answer"),
                "thought_process": final_output.get("plan"),
                "status": final_output.get("status"),
                "sources": final_output.get("documents", []),
                "request_id": request_id,
            }
        except Exception as e:
            elapsed = time.perf_counter() - start
            logfire.error(
                "❌ RAG pipeline failed",
                request_id=request_id,
                thread_id=thread_id,
                error=str(e),
                elapsed_seconds=round(elapsed, 3),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "question": q,
                    "answer": None,
                    "thought_process": None,
                    "status": "error",
                    "sources": [],
                    "request_id": request_id,
                    "message": "Failed to process request. Please try again later.",
                },
            )