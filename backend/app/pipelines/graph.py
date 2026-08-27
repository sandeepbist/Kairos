"""Compiled LangGraph Pipeline for Kairos Action Extraction."""
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .ingest import ingest_node
from .extract import extract_node
from .route import route_node


def build_extraction_graph():
    """Builds and compiles the stateless LangGraph extraction pipeline."""
    builder = StateGraph(AgentState)

    # Register Nodes
    builder.add_node("ingest", ingest_node)
    builder.add_node("extract", extract_node)
    builder.add_node("route", route_node)

    # Linear Pipeline Flow
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "extract")
    builder.add_edge("extract", "route")
    builder.add_edge("route", END)

    return builder.compile()


# Compiled Singleton Graph
extraction_graph = build_extraction_graph()


async def run_extraction_pipeline(
    batch_id: str,
    raw_text: str,
    source_type: str = "meeting_transcript",
) -> AgentState:
    """Executes the extraction pipeline and returns the resulting state."""
    initial_state: AgentState = {
        "batch_id": batch_id,
        "source_type": source_type,
        "raw_text": raw_text,
        "cleaned_text": "",
        "token_count": 0,
        "warning_flags": [],
        "extracted_items": [],
        "routed_items": [],
        "errors": [],
    }

    result = await extraction_graph.ainvoke(initial_state)
    return result
