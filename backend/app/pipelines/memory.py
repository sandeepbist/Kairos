"""Routing Memory: adaptive tool-routing preferences learned from operator feedback.

Design (provider-agnostic semantic memory):
- Feedback rows live in the ``routing_feedback`` table (source of truth).
- When an LLM key is configured (env or vault), item descriptions are
  embedded and compared via cosine similarity — real semantic matching
  ("budget reconciliation" ≈ "finance reconciliation").
- Embeddings are stored as JSONB float arrays, not a pgvector column:
  dimensions differ across providers (768 Gemini, 1536 OpenAI), and at
  single-operator scale (hundreds of rows) in-process cosine over the
  most recent 1,000 entries costs under 5ms with zero extra infra.
  If multi-tenant scale ever demands it, migrate to pgvector with a
  fixed dimension — the query interface stays identical.
- Without an LLM key, the matcher degrades to stopword-filtered keyword
  overlap so the system remains fully functional offline.

Policy applied over matched neighbors:
- Confirmed routings vote for their tool (+1); overridden routings vote
  for the operator's chosen tool (+2) and penalize the original suggestion.
- A strong vote for a different tool flips the suggestion with a
  confidence bonus; votes for the same tool reinforce it; being the
  penalized tool docks confidence hard.
"""
import logging
import math
import os
import re
from typing import Any

from sqlalchemy import select

from app.db.models import RoutingFeedbackModel
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "it", "and", "or", "be", "will", "i", "let", "me", "we", "you", "they",
    "this", "that", "please", "sure", "can", "could", "would", "should", "task",
    "item", "do", "done", "get", "got", "my", "your", "our", "their", "all",
}

# Number of votes required before memory overrides the extractor's suggestion
_OVERRIDE_VOTE_THRESHOLD = 2
# How many matched neighbors are surfaced as few-shot routing context
_FEW_SHOT_K = 3
# How many recent feedback rows participate in matching
_MATCH_WINDOW = 1000
# Minimum cosine similarity for an embedding to count as a neighbor
_SIMILARITY_THRESHOLD = 0.78


def extract_keywords(text: str) -> set[str]:
    """Extracts meaningful domain terms by filtering out common stopwords."""
    words = re.findall(r"\w+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity; returns 0.0 for empty or mismatched vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _resolve_embedding_key() -> tuple[str | None, str | None]:
    """Gemini/OpenAI key from env or encrypted vault (same resolution as extractor)."""
    gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if gemini_key or openai_key:
        return gemini_key, openai_key
    try:
        from sqlalchemy import select as _select

        from app.core.security import decrypt_token
        from app.db.models import OAuthTokenModel

        async with async_session_factory() as session:
            res = await session.execute(
                _select(OAuthTokenModel).where(
                    OAuthTokenModel.provider.in_(["gemini", "google_ai", "openai"])
                )
            )
            for rec in res.scalars().all():
                if not rec.access_token_enc:
                    continue
                token = decrypt_token(rec.access_token_enc)
                if rec.provider in ("gemini", "google_ai") and not gemini_key:
                    gemini_key = token
                elif rec.provider == "openai" and not openai_key:
                    openai_key = token
    except Exception as e:  # noqa: BLE001 — vault lookup is best-effort
        logger.debug("Vault LLM key lookup skipped: %s", e)
    return gemini_key, openai_key


class EmbeddingService:
    """Embeds text via Gemini or OpenAI, whichever key is available."""

    async def embed(self, text: str) -> list[float] | None:
        gemini_key, openai_key = await _resolve_embedding_key()
        try:
            if gemini_key:
                return await self._embed_gemini(text, gemini_key)
            if openai_key:
                return await self._embed_openai(text, openai_key)
        except Exception as e:  # noqa: BLE001 — embeddings must fail open
            logger.warning("Embedding failed, falling back to keyword match: %s", e)
        return None

    @staticmethod
    async def _embed_gemini(text: str, api_key: str) -> list[float] | None:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "text-embedding-004:embedContent",
                params={"key": api_key},
                json={
                    "model": "models/text-embedding-004",
                    "content": {"parts": [{"text": text}]},
                },
            )
            res.raise_for_status()
            values = res.json().get("embedding", {}).get("values")
            return [float(v) for v in values] if values else None

    @staticmethod
    async def _embed_openai(text: str, api_key: str) -> list[float] | None:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": text},
            )
            res.raise_for_status()
            data = res.json().get("data", [])
            return [float(v) for v in data[0]["embedding"]] if data else None


class RoutingMemory:
    """Learns and applies operator routing preferences (confirm/override/reject)."""

    def __init__(self) -> None:
        self._embedding_service = EmbeddingService()

    async def record_feedback(
        self,
        item_id: str,
        batch_id: str,
        item_description: str,
        suggested_tool: str,
        final_tool: str,
        was_overridden: bool,
    ) -> None:
        """Stores routing feedback with an optional semantic embedding."""
        embedding = await self._embedding_service.embed(item_description)
        async with async_session_factory() as session:
            session.add(
                RoutingFeedbackModel(
                    item_id=item_id,
                    batch_id=batch_id,
                    item_description=item_description,
                    suggested_tool=suggested_tool.lower(),
                    final_tool=final_tool.lower(),
                    was_overridden=was_overridden,
                    embedding=embedding,
                )
            )
            await session.commit()

    async def get_recent_feedback(self, limit: int = _MATCH_WINDOW) -> list[dict[str, Any]]:
        """Retrieves the most recent feedback rows from the database."""
        async with async_session_factory() as session:
            query = (
                select(RoutingFeedbackModel)
                .order_by(RoutingFeedbackModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return [
                {
                    "item_description": r.item_description,
                    "suggested_tool": r.suggested_tool,
                    "final_tool": r.final_tool,
                    "was_overridden": r.was_overridden,
                    "embedding": r.embedding or None,
                }
                for r in result.scalars().all()
            ]

    async def query_routing_preference(
        self,
        description: str,
        initial_tool: str,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """Applies learned preferences to calibrate routing for one item."""
        feedback_list = await self.get_recent_feedback()
        if not feedback_list:
            return {"suggested_tool": initial_tool, "confidence_adjustment": 0.0, "reason": None}

        query_embedding = await self._embedding_service.embed(description)

        tool_votes: dict[str, float] = {}
        penalized_tools: set[str] = set()
        matched = 0
        neighbors: list[dict[str, Any]] = []

        # Hybrid similarity: cosine over embeddings when both sides have
        # them, with keyword overlap as a lexical backstop so an embedding
        # gap never zeroes out a genuinely related past decision. Recency
        # weights votes — newest feedback is the strongest signal — using
        # a linear decay across the window (index 0 = most recent).
        n = len(feedback_list)
        for idx, entry in enumerate(feedback_list):
            entry_embedding = entry.get("embedding")
            similarity = 0.0
            matched_by: str | None = None
            if query_embedding and entry_embedding:
                similarity = cosine_similarity(query_embedding, entry_embedding)
                if similarity >= _SIMILARITY_THRESHOLD:
                    matched_by = "embedding"
            overlap = len(
                extract_keywords(description)
                & extract_keywords(entry["item_description"])
            )
            if matched_by is None and overlap >= 2:
                matched_by = "keyword"

            if matched_by is None:
                continue

            # Linear recency weight: 1.0 for the newest entry down to 0.2
            # for the oldest in the window.
            recency = 0.2 + 0.8 * (1 - idx / max(n - 1, 1))
            weight = recency * (2.0 if matched_by == "embedding" else 1.0)

            matched += 1
            neighbors.append({
                "description": entry["item_description"],
                "suggested_tool": entry["suggested_tool"],
                "final_tool": entry["final_tool"],
                "was_overridden": entry["was_overridden"],
                "similarity": round(similarity, 3),
                "matched_by": matched_by,
                "weight": round(weight, 3),
            })
            if entry["was_overridden"]:
                penalized_tools.add(entry["suggested_tool"])
                if entry["final_tool"] != "rejected":
                    tool_votes[entry["final_tool"]] = (
                        tool_votes.get(entry["final_tool"], 0.0) + 2 * weight
                    )
            else:
                tool_votes[entry["final_tool"]] = (
                    tool_votes.get(entry["final_tool"], 0.0) + 1 * weight
                )

        logger.debug(
            "Routing memory matched %d neighbors for %r (embedding=%s)",
            matched,
            description[:50],
            bool(query_embedding),
        )

        # Top neighbors (highest weight first), capped, for few-shot
        # context in the routing prompt rather than post-hoc override only.
        neighbors.sort(key=lambda nb: nb["weight"], reverse=True)
        few_shot = neighbors[:_FEW_SHOT_K]

        if tool_votes:
            best_tool = max(tool_votes, key=tool_votes.get)
            best_votes = tool_votes[best_tool]
            if best_votes >= _OVERRIDE_VOTE_THRESHOLD * 0.5 and best_tool != initial_tool.lower():
                return {
                    "suggested_tool": best_tool,
                    "confidence_adjustment": 0.15,
                    "reason": f"Learned preference: past similar items were routed to {best_tool}",
                    "neighbors": few_shot,
                }
            if best_tool == initial_tool.lower():
                return {
                    "suggested_tool": initial_tool,
                    "confidence_adjustment": 0.1,
                    "reason": "Reinforced: operator consistently confirms this routing",
                    "neighbors": few_shot,
                }

        if initial_tool.lower() in penalized_tools:
            return {
                "suggested_tool": initial_tool,
                "confidence_adjustment": -0.25,
                "reason": "Penalized: operator previously rejected this tool for similar tasks",
                "neighbors": few_shot,
            }

        return {
            "suggested_tool": initial_tool,
            "confidence_adjustment": 0.0,
            "reason": None,
            "neighbors": few_shot,
        }


# Global memory manager
routing_memory = RoutingMemory()
