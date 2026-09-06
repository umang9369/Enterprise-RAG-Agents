import os

import logfire
from nemoguardrails import LLMRails, RailsConfig

from app.guardrails.colang_rules import COLANG_CONTENT, RAIL_INDICATORS, YAML_CONTENT

# Cache the last-used key so we only rebuild _rails when the key actually changes.
_rails: LLMRails | None = None
_rails_key: str | None = None  # which Groq key was used to build _rails


def _build_rails(groq_api_key: str) -> LLMRails | None:
    """
    Build an LLMRails instance using the supplied Groq key.
    NeMo reads the key from the env var named in ``api_key_env_var``.
    """
    os.environ["GROQ_THIRD_API_KEY"] = groq_api_key
    try:
        rails = LLMRails(
            config=RailsConfig.from_content(
                colang_content=COLANG_CONTENT,
                yaml_content=YAML_CONTENT,
            )
        )
        logfire.info("✅ NeMo Guardrails initialized successfully.")
        return rails
    except Exception as exc:
        logfire.error(f"❌ Failed to initialize NeMo Guardrails: {exc}")
        return None


def initialize_rails() -> None:
    """
    Called once at application startup to warm up the NeMo runtime
    (downloads Colang, sets up the async loop, etc.) without needing a real key yet.
    The first real /query call will trigger _build_rails() with the user's key.
    """
    # Nothing to do — rails are built lazily on the first guard() call.
    logfire.info("🛡️ Guardrails system ready (lazy key-based init).")


def guard(message: str, groq_api_key: str) -> tuple[bool, str]:
    """
    Run the guardrails on a message using the caller's Groq API key.

    Re-uses the cached LLMRails instance if the key hasn't changed.
    Rebuilds it when a new key is supplied.

    Returns (rail_fired, response).
    Fails open on any error so a guardrails outage never blocks legitimate queries.
    """
    global _rails, _rails_key

    # Rebuild rails whenever a different key is presented.
    if _rails is None or _rails_key != groq_api_key:
        _rails = _build_rails(groq_api_key)
        _rails_key = groq_api_key

    if not _rails:
        # Guardrails init failed — fail open.
        return False, message

    try:
        result = _rails.generate(
            messages=[{"role": "user", "content": message}]
        )
        response = (
            result.get("content", "")
            if isinstance(result, dict)
            else str(result)
        )
        return any(indicator in response for indicator in RAIL_INDICATORS), response
    except Exception as e:
        logfire.error(f"🛡️ Guardrails failed: {e}")
        return False, message