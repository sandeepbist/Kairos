"""Routing Memory: Learns user preferences, positive confirmations, and negative constraints."""
import re
from typing import Any
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import RoutingFeedbackModel

STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "it", "and", "or", "be", "will", "i", "let", "me", "we", "you", "they",
    "this", "that", "please", "sure", "can", "could", "would", "should", "task",
    "item", "do", "done", "get", "got", "my", "your", "our", "their", "all"
}


def extract_keywords(text: str) -> set[str]:
    """Extracts meaningful domain terms by filtering out common stopwords."""
    words = re.findall(r"\w+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


class RoutingMemory:
    """Manages adaptive routing memory with positive reinforcement and negative constraint penalization."""

    def __init__(self):
        self._memory_cache: list[dict[str, Any]] = []

    async def record_feedback(
        self,
        item_id: str,
        batch_id: str,
        item_description: str,
        suggested_tool: str,
        final_tool: str,
        was_overridden: bool,
    ) -> None:
        """Stores routing feedback in PostgreSQL and fast memory cache."""
        feedback_entry = {
            "item_id": item_id,
            "batch_id": batch_id,
            "item_description": item_description,
            "suggested_tool": suggested_tool.lower(),
            "final_tool": final_tool.lower(),
            "was_overridden": was_overridden,
        }
        self._memory_cache.append(feedback_entry)

        async with async_session_factory() as session:
            db_record = RoutingFeedbackModel(
                item_id=item_id,
                batch_id=batch_id,
                item_description=item_description,
                suggested_tool=suggested_tool.lower(),
                final_tool=final_tool.lower(),
                was_overridden=was_overridden,
            )
            session.add(db_record)
            await session.commit()

    async def get_all_feedback(self) -> list[dict[str, Any]]:
        """Retrieves all feedback records from DB if cache is empty."""
        if not self._memory_cache:
            async with async_session_factory() as session:
                query = select(RoutingFeedbackModel).order_by(RoutingFeedbackModel.created_at.desc())
                result = await session.execute(query)
                records = result.scalars().all()
                self._memory_cache = [
                    {
                        "item_id": r.item_id,
                        "batch_id": r.batch_id,
                        "item_description": r.item_description,
                        "suggested_tool": r.suggested_tool,
                        "final_tool": r.final_tool,
                        "was_overridden": r.was_overridden,
                    }
                    for r in records
                ]
        return self._memory_cache

    async def query_routing_preference(
        self,
        description: str,
        initial_tool: str,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluates past feedback to apply positive reinforcement or negative constraint overrides.
        Requires genuine domain keyword overlap (>= 2 key domain terms).
        """
        feedback_list = await self.get_all_feedback()
        desc_keywords = extract_keywords(description)

        tool_votes: dict[str, int] = {}
        penalized_tools: set[str] = set()

        for entry in feedback_list:
            past_keywords = extract_keywords(entry["item_description"])
            overlap = len(desc_keywords.intersection(past_keywords))

            # Only consider genuine domain keyword matches (>= 2 domain words)
            if overlap >= 2:
                if entry["was_overridden"]:
                    penalized_tools.add(entry["suggested_tool"])
                    if entry["final_tool"] != "rejected":
                        tool_votes[entry["final_tool"]] = tool_votes.get(entry["final_tool"], 0) + 2
                else:
                    tool_votes[entry["final_tool"]] = tool_votes.get(entry["final_tool"], 0) + 1

        if tool_votes:
            best_tool = max(tool_votes, key=tool_votes.get)
            if best_tool != initial_tool.lower():
                return {
                    "suggested_tool": best_tool,
                    "confidence_adjustment": 0.15,
                    "reason": f"Learned preference: past similar items were routed to {best_tool}",
                }
            else:
                return {
                    "suggested_tool": initial_tool,
                    "confidence_adjustment": 0.1,
                    "reason": "Reinforced: user consistently confirms this routing",
                }
        elif initial_tool.lower() in penalized_tools:
            return {
                "suggested_tool": initial_tool,
                "confidence_adjustment": -0.25,
                "reason": "Penalized: user previously rejected this tool for similar tasks",
            }

        return {
            "suggested_tool": initial_tool,
            "confidence_adjustment": 0.0,
            "reason": None,
        }


# Global memory manager
routing_memory = RoutingMemory()
