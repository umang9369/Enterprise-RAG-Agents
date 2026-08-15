"""Request-context logging helpers."""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

#it gives every request ccoming to our rag a new unique id 
#so that no conflict will take place so that it will increase readibility
#FastAPI me multiple requests simultaneously chal sakti hain
#isliye normal global variable dangerous hota.

def set_request_id(request_id: str | None) -> None:
    """Set the current request id for logging/tracing correlation."""
    _request_id.set(request_id)


def get_request_id() -> str | None:
    """Get the current request id, if any."""
    return _request_id.get()