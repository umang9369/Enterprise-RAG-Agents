from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders

from app.config import settings

# Portkey routing strategy:
#   - Primary/fallback logic lives in a Portkey saved config (required when
#     block_inline_config is enabled on the workspace).
#   - We reference that config via the x-portkey-config-id header.
#   - The inline config dict approach is disabled for this account, so all
#     retry/fallback/cache behavior must be configured inside the Portkey UI.



def _make_headers(feature: str = "rag") -> dict:
    """Build Portkey headers that reference the primary saved config by ID."""
    if not settings.PORTKEY_PRIMARY_CONFIG_ID:
        raise ValueError(
            "PORTKEY_PRIMARY_CONFIG_ID is not set in .env. "
            "Get the real pc-... ID from the Portkey dashboard or "
            "run: PYTHONPATH=. python scripts/list_portkey_configs.py"
        )
    return createHeaders(
        api_key=settings.PORTKEY_API_KEY,
        config_id=settings.PORTKEY_PRIMARY_CONFIG_ID,
        metadata={
            "feature": feature,
            "_user": "rag-system",
            "environment": "production",
        },
    )

# OpenAI-compatible client routed through Portkey.
# We use the OpenAI SDK directly because the native Portkey SDK does not
# surface a first-class config_id constructor parameter; the header-based
# approach works reliably with block_inline_config enabled.
portkey_client = OpenAI(
    api_key=settings.PORTKEY_API_KEY,
    base_url=PORTKEY_GATEWAY_URL,
    default_headers=_make_headers(),
)