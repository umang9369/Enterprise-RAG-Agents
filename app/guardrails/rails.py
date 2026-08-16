import os

import logfire
from nemoguardrails import LLMRails, RailsConfig

from app.config import settings
from app.guardrails.colang_rules import COLANG_CONTENT, RAIL_INDICATORS, YAML_CONTENT

_rails: LLMRails | None = None


def initialize_rails():
    """
    Initialize the guardrails system from the Colang/YAML config.
    This function is called once at application startup.
    """
    global _rails
    if _rails:
        return

    # Set the API key for the guardrails LLM (Groq) in the environment
    # so nemoguardrails can pick it up automatically based on the YAML config.
    if settings.GROQ_THIRD_API_KEY:
        # NeMo Guardrails expands environment variables in the YAML config.
        os.environ["GROQ_THIRD_API_KEY"] = settings.GROQ_THIRD_API_KEY
    else:
        logfire.warning("⚠️ GROQ_THIRD_API_KEY is not set, guardrails may not function.")

    # Initialize rails without an explicit LLM.
    # It will now use the `engine: groq` configuration from YAML_CONTENT.
    _rails = LLMRails(
        config=RailsConfig.from_content(
            colang_content=COLANG_CONTENT,
            yaml_content=YAML_CONTENT,
        )
    )


def guard(message: str) -> tuple[bool, str]:
    """
    Run the guardrails on a message. Returns (rail_fired, response).
    If the guardrails system fails for any reason, it "fails open" and
    allows the request to proceed.
    """
    if not _rails:
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