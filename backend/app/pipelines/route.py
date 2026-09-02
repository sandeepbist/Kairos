"""Route Node: Adaptive routing calibration via positive/negative routing-memory feedback."""
from typing import Any
from .state import AgentState
from .memory import routing_memory


async def route_node(state: AgentState) -> dict[str, Any]:
    """
    Adjusts tool destinations and confidence scores by querying historical feedback memory.
    Applies positive reinforcements and negative constraint penalizations.
    """
    extracted_items = state.get("extracted_items", [])
    source_type = state.get("source_type", "meeting_transcript")
    routed_items: list[dict[str, Any]] = []

    for item in extracted_items:
        initial_tool = item.get("suggested_tool", "task_ledger")
        description = item.get("description", "")
        base_confidence = float(item.get("confidence", 0.8))

        # Query adaptive memory
        mem_decision = await routing_memory.query_routing_preference(
            description=description,
            initial_tool=initial_tool,
            source_type=source_type,
        )

        final_tool = mem_decision["suggested_tool"]
        confidence_delta = mem_decision["confidence_adjustment"]
        calibrated_confidence = max(0.1, min(0.99, base_confidence + confidence_delta))

        # Update item with calibrated routing
        updated_item = dict(item)
        updated_item["suggested_tool"] = final_tool
        updated_item["confidence"] = round(calibrated_confidence, 2)
        if mem_decision.get("reason"):
            updated_item["routing_reason"] = mem_decision["reason"]
        # Matched precedent (few-shot context). Kept on the item so later
        # stages — prompts, UI tooltips, or the routing-memory evals — can
        # show *why* a suggestion was calibrated, not just that it was.
        neighbors = mem_decision.get("neighbors") or []
        if neighbors:
            updated_item["routing_precedent"] = [
                {
                    "description": nb["description"][:80],
                    "suggested_tool": nb["suggested_tool"],
                    "final_tool": nb["final_tool"],
                    "was_overridden": nb["was_overridden"],
                    "similarity": nb["similarity"],
                    "matched_by": nb["matched_by"],
                }
                for nb in neighbors
            ]

        routed_items.append(updated_item)

    return {"routed_items": routed_items}
