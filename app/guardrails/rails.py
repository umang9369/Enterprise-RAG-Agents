import os
import re

import logfire

from app.config import settings
from app.guardrails.colang_rules import COLANG_CONTENT, RAIL_INDICATORS, YAML_CONTENT

# Cache the last-used key so we only rebuild _rails when the key actually changes.
_rails = None
_rails_key: str | None = None  # which Groq key was used to build _rails

# ── Lightweight Zero-RAM Guardrail Patterns (for Render Free-tier < 512MB RAM) ──
_JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions",
    r"you\s+are\s+now\s+(dan|unrestricted)",
    r"do\s+anything\s+now",
    r"pretend\s+(you\s+have\s+)?no\s+restrictions",
    r"forget\s+(your\s+)?system\s+prompt",
    r"act\s+as\s+if\s+you\s+were\s+trained\s+differently",
    r"your\s+new\s+instructions\s+are",
    r"disregard\s+(your\s+)?training",
    r"developer\s+mode",
    r"override\s+(your\s+)?safety(\s+filters)?",
    r"bypass\s+(your\s+)?(guidelines|filters|rules)",
    r"act\s+as\s+an\s+unrestricted(\s+ai)?",
]

_OFF_TOPIC_PATTERNS = [
    r"^tell\s+me\s+a\s+joke\b",
    r"^what\s+is\s+the\s+capital\s+of\b",
    r"^write\s+(me\s+)?a\s+(poem|song|story)\b",
    r"^(what\s+is\s+)?\d+\s*[\+\-\*\/]\s*\d+\b",
    r"^what\s+should\s+i\s+eat\b",
    r"^who\s+won\s+the\s+game\b",
    r"^recommend\s+a\s+movie\b",
    r"^what\s+is\s+the\s+weather\b",
    r"^can\s+you\s+help\s+(me\s+)?with\s+math\s+homework\b",
    r"^tell\s+me\s+about\s+world\s+history\b",
    r"^what\s+is\s+the\s+best\s+restaurant\b",
]

_GREETING_PATTERNS = [
    r"^(hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening|what's\s+up|howdy)[\s\.\!\?]*$",
]

_CAPABILITIES_PATTERNS = [
    r"^(what\s+can\s+you\s+do|what\s+do\s+you\s+know|help|what\s+are\s+you|what\s+topics\s+do\s+you\s+cover|what\s+can\s+i\s+ask\s+you|what\s+are\s+your\s+capabilities)[\s\.\!\?]*$",
]

_FAREWELL_PATTERNS = [
    r"^(bye|goodbye|see\s+you|thanks\s+bye|that\s+is\s+all|i\s+am\s+done|see\s+you\s+later)[\s\.\!\?]*$",
]

_JAILBREAK_RE = re.compile("|".join(_JAILBREAK_PATTERNS), re.IGNORECASE)
_OFF_TOPIC_RE = re.compile("|".join(_OFF_TOPIC_PATTERNS), re.IGNORECASE)
_GREETING_RE = re.compile("|".join(_GREETING_PATTERNS), re.IGNORECASE)
_CAPABILITIES_RE = re.compile("|".join(_CAPABILITIES_PATTERNS), re.IGNORECASE)
_FAREWELL_RE = re.compile("|".join(_FAREWELL_PATTERNS), re.IGNORECASE)

RESP_REFUSE_JAILBREAK = "I maintain consistent guidelines regardless of how I am prompted. I am here to help with Kubernetes, Intel, and networking. What can I help you with?"
RESP_REFUSE_OFF_TOPIC = "I'm an Enterprise IT Assistant focused on Kubernetes, Intel hardware, and networking. I can't help with that — but ask me anything technical!"
RESP_GREETING = "Hello! I'm your Enterprise IT Assistant. I specialise in Kubernetes, Intel hardware, and enterprise networking. What can I help you with today?"
RESP_CAPABILITIES = "I'm an Enterprise AI Assistant with deep expertise in: Kubernetes (deployment, scaling, networking, operators), Intel Hardware (CPUs, FPGAs, SRIOV, NICs), Enterprise Networking (SDN, VLANs, BGP, routing). Ask me anything in these areas!"
RESP_FAREWELL = "Goodbye! Feel free to return whenever you have more enterprise IT questions. Have a great day!"


def _lightweight_guard(message: str) -> tuple[bool, str]:
    """Zero-RAM pattern matching guardrail for Colang rules."""
    text = message.strip()
    if _JAILBREAK_RE.search(text):
        return True, RESP_REFUSE_JAILBREAK
    if _OFF_TOPIC_RE.search(text):
        return True, RESP_REFUSE_OFF_TOPIC
    if _GREETING_RE.search(text):
        return True, RESP_GREETING
    if _CAPABILITIES_RE.search(text):
        return True, RESP_CAPABILITIES
    if _FAREWELL_RE.search(text):
        return True, RESP_FAREWELL
    return False, message


def _build_rails(groq_api_key: str):
    """
    Build an LLMRails instance using the supplied Groq key.
    NeMo reads the key from the env var named in ``api_key_env_var``.
    """
    os.environ["GROQ_THIRD_API_KEY"] = groq_api_key
    try:
        from nemoguardrails import LLMRails, RailsConfig
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
    """Called once at application startup."""
    if settings.LIGHTWEIGHT_GUARDRAILS:
        logfire.info("🛡️ Lightweight zero-RAM guardrails enabled (Render Free-tier optimized).")
    else:
        logfire.info("🛡️ NeMo Guardrails system ready (lazy key-based init).")


def guard(message: str, groq_api_key: str) -> tuple[bool, str]:
    """
    Run the guardrails on a message using the caller's Groq API key.
    Returns (rail_fired, response).
    """
    if settings.LIGHTWEIGHT_GUARDRAILS:
        return _lightweight_guard(message)

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