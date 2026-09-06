import logfire
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from app.agent.state import AgentState
from app.config import settings
from app.gateway import extract_cache_status, make_portkey_client_for_key


def generate_node(state: AgentState):
    """
    Synthesizes a response using both Documentation Context AND Conversation History.
    Uses the native Portkey client (not LangChain) so we can read the
    x-portkey-cache-status response header and surface Cache: Hit in the UI.
    The user's own Groq API key is forwarded via Portkey's Authorization override.
    """
    query = state["current_query"]
    groq_api_key = state["groq_api_key"]

    # Cap history to the last 6 messages (3 exchanges) to prevent the prompt
    # from growing unboundedly and triggering Groq 413 "request too large" errors.
    MAX_HISTORY_TURNS = 6
    recent_messages = state["messages"][:-1][-MAX_HISTORY_TURNS:]
    history_str = ""
    for msg in recent_messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")
        prompt = f"""
        You are a friendly and helpful Enterprise AI Assistant.
        Answer the user's latest message using the CONVERSATION HISTORY below.

        CONVERSATION HISTORY:
        {history_str}

        LATEST MESSAGE:
        "{user_msg}"
        """

    else:
        logfire.info("Generating technical RAG response.")
        # Keep context within ~18k chars to stay safely under Groq's per-request
        # token limit even after adding system prompt + history overhead.
        max_context_chars = 18000
        full_context = ""

        for doc in state["documents"]:
            if len(full_context) + len(doc) < max_context_chars:
                full_context += doc + "\n\n"
            else:
                logfire.warning("Context truncated to fit Groq TPM limits.")
                break

        prompt = f"""
        You are a Senior Technical Architect.
        Answer the question using the TECHNICAL CONTEXT provided.

        TECHNICAL CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ LLM Synthesis"):
        try:
            response = _generate_response(prompt, groq_api_key)
            content = response.choices[0].message.content
            cache_status = extract_cache_status(response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:
                logfire.info("⚡ Gateway Cache Hit — response served from Portkey cache.")
                plan_update = state["plan"] + ["Cache: Hit ⚡"]
                status = "Cache hit — instant response."
            else:
                logfire.info("✅ Response synthesised via LLM.")
                plan_update = state["plan"]
                status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [{"role": "assistant", "content": content}],
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed after retries: {e}")
            raise e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
    before_sleep=before_sleep_log(logfire, "warning"),
)
def _generate_response(prompt: str, groq_api_key: str):
    """Call the LLM gateway with retry logic. Uses the user's Groq key via Portkey."""
    client = make_portkey_client_for_key(groq_api_key)
    return client.chat.completions.create(
        model=f"@{settings.PORTKEY_PRIMARY_SLUG}/{settings.PORTKEY_MODEL}",
        messages=[{"role": "user", "content": prompt}],
    )
