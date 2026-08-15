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

import time
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.agents.graph import build_graph
from app.guardrails import guard, initialize_rails
from app.health import router as health_router
from app.logging import set_request_id
from app.services.health.connection_checker import check_all_connections, log_connection_summary

GUARDRAILS_BLOCKS_TOTAL = Counter(
    "guardrails_blocks_total",
    "Number of requests blocked or allowed by guardrails",
    ["blocked"],
)
_security = HTTPBearer(auto_error=False)

def _init_rate_limiter():
    """Initialize rate limiting. Use Redis in production; fall back to in-memory storage locally."""
    from limits.storage import RedisStorage
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.extension import _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address

    try:
        storage = RedisStorage(settings.redis_url)
        # `storage.check()` returns False silently on some failures; ping the
        # underlying Redis client so we only use Redis when it is really reachable.
        if not storage.check() or not storage.storage.ping():
            raise ConnectionError("Redis did not respond to ping")
        app.state.limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
        app.state.rate_limiter_storage = "redis"
        logfire.info("🚦 Rate limiting initialized via Redis.")
    except Exception as e:
        app.state.limiter = Limiter(key_func=get_remote_address)
        app.state.rate_limiter_storage = "memory"
        logfire.warning(f"⚠️ Redis unavailable ({e}); using in-memory rate limiting.")

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    return True

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    """
    Require a valid bearer token when RAG_API_KEY is configured.
    In development, omit RAG_API_KEY to disable authentication.
    """
    if not settings.API_KEY:
        # Development mode: no API key required.
        return None

    if not credentials or credentials.credentials != settings.API_KEY:
        logfire.warning("🔒 Unauthorized /query request: invalid or missing API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

def _get_limiter_rule(times: int, seconds: int) -> str:
    """Convert times/seconds into a slowapi limit string, e.g. '20/minute'."""
    if seconds % 60 == 0:
        return f"{times}/{seconds // 60}minute"
    if seconds % 3600 == 0:
        return f"{times}/{seconds // 3600}hour"
    return f"{times}/{seconds}second"

class _AppLimiter:
    """
    Thin wrapper around the Limiter instance that is initialized at startup.
    Allows routes to be decorated at import time while the real limiter
    (Redis-backed or in-memory) is configured in startup_event.
    """

    def limit(self, rule_or_callable):
        def decorator(func):
            import functools

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                limiter = getattr(app.state, "limiter", None)
                if limiter is None:
                    return func(*args, **kwargs)

                rule = rule_or_callable() if callable(rule_or_callable) else rule_or_callable
                # Build the slowapi wrapper at request time so the limiter
                # instance and storage backend are always current.
                return limiter.limit(rule)(func)(*args, **kwargs)

            return wrapper

        return decorator


app_limiter = _AppLimiter()

#Ye wrapper isliye banaya gaya hai kyunki FastAPI me **routes pehle load/decorate hote hain
#aur actual Redis ya memory-based limiter baad me startup ke time initialize hota hai**. 
#Agar hum directly actual limiter use karein, to route load hote waqt 
#limiter available nahi hoga aur problem aa sakti hai.
#`_AppLimiter` ek **middleman/placeholder** ki tarah kaam karta hai—pehle routes ko register hone deta hai
#aur jab request aati hai tab jo actual limiter startup me bana hai (Redis ya memory), usko use karta hai.
#Isse route code simple rehta hai aur Redis available ho ya na ho
#application properly kaam karti hai.


# Initialize FastAPI
app = FastAPI(title="Enterprise Agentic RAG API")

