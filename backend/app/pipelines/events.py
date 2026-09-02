"""Batch progress events: append + tail for SSE streaming.

The pipeline records milestone events; the API streams them to the
review UI. Written for the single-operator scale — seq is computed
per batch under a small advisory lock to stay monotonic without a
global counter.
"""
import uuid
from typing import Any, AsyncGenerator

from sqlalchemy import func, select

from app.db.models import BatchEventModel
from app.db.session import async_session_factory


async def record_event(batch_id: str, event_type: str, message: str = "") -> None:
    """Appends one progress event for a batch (best-effort: progress
    events must never fail the pipeline)."""
    try:
        async with async_session_factory() as session:
            next_seq = (
                await session.execute(
                    select(func.coalesce(func.max(BatchEventModel.seq), -1)).where(
                        BatchEventModel.batch_id == batch_id
                    )
                )
            ).scalar_one() + 1
            session.add(
                BatchEventModel(
                    id=str(uuid.uuid4()),
                    batch_id=batch_id,
                    event_type=event_type,
                    message=message,
                    seq=next_seq,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — progress events are non-critical
        pass


async def stream_events(
    batch_id: str,
    poll_seconds: float = 0.4,
    idle_limit: int = 25,  # ~10s of silence before closing the stream
) -> AsyncGenerator[dict[str, Any], None]:
    """Yields events in seq order, polling until the batch reaches a
    terminal state or the client disconnects. The generator is the SSE
    body; FastAPI closes it on client disconnect, ending the loop."""
    from app.db.models import BatchModel

    last_seq = -1
    idle = 0
    import asyncio

    while True:
        async with async_session_factory() as session:
            events = (
                await session.execute(
                    select(BatchEventModel)
                    .where(BatchEventModel.batch_id == batch_id, BatchEventModel.seq > last_seq)
                    .order_by(BatchEventModel.seq)
                )
            ).scalars().all()
            terminal = (
                await session.execute(
                    select(BatchModel.status).where(BatchModel.id == batch_id)
                )
            ).scalar_one_or_none()

        for e in events:
            last_seq = max(last_seq, e.seq)
            idle = 0
            yield {
                "seq": e.seq,
                "type": e.event_type,
                "message": e.message,
                "at": e.created_at.isoformat() if e.created_at else None,
            }

        if terminal in ("completed", "failed", "expired", "executing"):
            # final state seen and events drained: one last look, then stop
            if not events:
                break
        if events:
            continue
        idle += 1
        if idle >= idle_limit:
            break
        await asyncio.sleep(poll_seconds)
