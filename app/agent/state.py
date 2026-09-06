import operator
from typing import Annotated, List, Optional, TypedDict


class AgentState(TypedDict):
    # Using Annotated with operator.add ensures that messages
    # are appended to the history rather than replaced.
    messages: Annotated[List[dict], operator.add]
    current_query: str
    documents: List[str]
    plan: List[str]
    status: str
    final_answer: str
    # User-supplied Groq API key forwarded from the HTTP request header.
    # Required — requests without a key are rejected before reaching the graph.
    groq_api_key: str