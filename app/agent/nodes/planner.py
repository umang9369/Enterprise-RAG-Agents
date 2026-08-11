import logfire

from app.agents.state import AgentState
from app.gateway import get_langchain_llm

# Portkey-backed LLM: fallback + cache + retry — same .invoke() interface as ChatOpenAI
llm = get_langchain_llm(feature="planner")
