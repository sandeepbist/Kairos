"""State definition for LangGraph extraction pipeline."""
from typing import TypedDict, Any


class AgentState(TypedDict):
    """Scoped state for a single batch extraction run in LangGraph."""
    batch_id: str
    source_type: str
    raw_text: str
    cleaned_text: str
    token_count: int
    warning_flags: list[str]
    extracted_items: list[dict[str, Any]]
    routed_items: list[dict[str, Any]]
    errors: list[str]
