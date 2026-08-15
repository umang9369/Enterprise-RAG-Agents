import logfire
from langchain_openai import ChatOpenAI
from nemoguardrails import LLMRails, RailsConfig

from app.config import settings
from app.guardrails.colang_rules import COLANG_CONTENT, RAIL_INDICATORS, YAML_CONTENT

_rails: LLMRails | None = None

def initialize_rails() -> None:
    """
    Build the NeMo LLMRails singleton at app startup.
    Uses OpenAI gpt-5-mini for fast intent classification at the gate.
    """
    global _rails

    guard_llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY, model="gpt-5-mini")

    config = RailsConfig.from_content(colang_content=COLANG_CONTENT, yaml_content=YAML_CONTENT)

    _rails = LLMRails(config, llm=guard_llm)
    logfire.info("🛡️ NeMo Guardrails initialised (gpt-5-mini).")
