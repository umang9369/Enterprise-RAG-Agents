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

    NeMo Guardrails uses the OpenAI-compatible client internally even when
    `engine: groq` is specified. It resolves the API key from the OPENAI_API_KEY
    env var by default. We temporarily remap GROQ_THIRD_API_KEY → OPENAI_API_KEY
    so that NeMo authenticates against Groq's endpoint correctly.
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

    # NeMo Guardrails resolves the Groq key via OPENAI_API_KEY when using
    # the openai-compatible endpoint. Save and restore the original value.
    _prev_openai_key = os.environ.get("OPENAI_API_KEY")
    if groq_key:
        os.environ["GROQ_THIRD_API_KEY"] = groq_key
        os.environ["OPENAI_API_KEY"] = groq_key  # NeMo picks this up for auth

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
    finally:
        # Always restore the original OPENAI_API_KEY so the rest of the app
        # (Portkey, LangChain, etc.) is not affected.
        if _prev_openai_key is not None:
            os.environ["OPENAI_API_KEY"] = _prev_openai_key
        elif "OPENAI_API_KEY" in os.environ and groq_key:
            # We set it; remove it if it wasn't originally present.
            del os.environ["OPENAI_API_KEY"]


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