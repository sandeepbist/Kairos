"""Routing Memory: Learns user preferences, positive confirmations, and negative constraints."""
from typing import Any
import re
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import RoutingFeedbackModel


class RoutingMemory:
    """Manages adaptive routing memory with positive reinforcement and negative constraint penalization."""

    def __init__(self):
        # In-memory fast cache for quick lookup
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
        Returns:
            - suggested_tool: str
            - confidence_adjustment: float (+0.1 to +0.2 if confirmed, -0.2 to -0.4 if historically overridden)
            - reason: str | None
        """
        feedback_list = await self.get_all_feedback()
        desc_words = set(re.findall(r"\w+", description.lower()))

        # Check for matching patterns in past feedback
        tool_votes: dict[str, int] = {}
        penalized_tools: set[str] = set()

        for entry in feedback_list:
            past_words = set(re.findall(r"\w+", entry["item_description"].lower()))
            overlap = len(desc_words.intersection(past_words))

            # If semantic/keyword overlap is significant (e.g. >= 2 key terms)
            if overlap >= 2:
                if entry["was_overridden"]:
                    # Negative constraint: penalize the suggested tool that was rejected
                    penalized_tools.add(entry["suggested_tool"])
                    # Positive vote for the tool the user actually chose
                    tool_votes[entry["final_tool"]] = tool_votes.get(entry["final_tool"], 0) + 2
                else:
                    # Positive reinforcement for confirmed tool
                    tool_votes[entry["final_tool"]] = tool_votes.get(entry["final_tool"], 0) + 1

        # Determine if we should override or adjust confidence
        if tool_votes:
            best_tool = max(tool_votes, key=tool_votes.get)
            if best_tool != initial_tool.lower():
                # Learned override
                return {
                    "suggested_tool": best_tool,
                    "confidence_adjustment": 0.15,
                    "reason": f"Learned preference: past similar items were routed to {best_tool}",
                }
            else:
                # Reinforced confirmation
                return {
                    "suggested_tool": initial_tool,
                    "confidence_adjustment": 0.1,
                    "reason": "Reinforced: user consistently confirms this routing",
                }
        elif initial_tool.lower() in penalized_tools:
            # Penalized without clear winner
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
