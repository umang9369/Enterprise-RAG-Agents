"""Request-context logging helpers."""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Gives every request a unique ID so concurrent requests don't conflict.
# FastAPI handles multiple requests simultaneously, so a normal global
# variable would be dangerous — ContextVar is thread/task-safe.

def set_request_id(request_id: str | None) -> None:
    """Set the current request id for logging/tracing correlation."""
    _request_id.set(request_id)


def get_request_id() -> str | None:
    """Get the current request id, if any."""
    return _request_id.get()