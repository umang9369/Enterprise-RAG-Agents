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

    NeMo resolves the API key via the ``api_key_env_var`` field in the YAML
    config — it reads the named environment variable at call time, so we just
    need to ensure GROQ_THIRD_API_KEY is set before initializing.
    """
    global _rails
    if _rails:
        return

    groq_key = settings.GROQ_THIRD_API_KEY or settings.GROQ_API_KEY
    if not groq_key:
        logfire.warning(
            "⚠️ No Groq API key found (GROQ_THIRD_API_KEY / GROQ_API_KEY). "
            "Guardrails will run in rule-only mode (no LLM intent detection)."
        )
    else:
        # Ensure the env var NeMo reads (api_key_env_var: GROQ_THIRD_API_KEY)
        # is populated. pydantic-settings loads it into Settings but may not
        # write it back to os.environ.
        os.environ["GROQ_THIRD_API_KEY"] = groq_key

    try:
        _rails = LLMRails(
            config=RailsConfig.from_content(
                colang_content=COLANG_CONTENT,
                yaml_content=YAML_CONTENT,
            )
        )
        logfire.info("✅ NeMo Guardrails initialized successfully.")
    except Exception as exc:
        logfire.error(f"❌ Failed to initialize NeMo Guardrails: {exc}")
        _rails = None


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