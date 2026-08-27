"""Batches API Endpoints: Ingestion, Review polling, and Human Approval."""
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.db.models import BatchModel, ActionItemModel
from app.schemas.action_item import (
    BatchIngestRequest,
    BatchStatusResponse,
    ActionItem,
    ActionItemApprovalRequest,
)
from app.temporal.workflows import ProcessBatchWorkflow
from app.temporal.worker import get_temporal_client
from app.core.telemetry import telemetry

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("/ingest", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def ingest_batch(
    request: BatchIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingests unstructured text and triggers the durable Temporal extraction workflow."""
    batch_id = str(uuid.uuid4())
    workflow_id = f"batch-wf-{batch_id}"

    # 1. Create Batch record in PostgreSQL
    batch = BatchModel(
        id=batch_id,
        source_type=request.source_type,
        raw_text=request.raw_text,
        status="processing",
        temporal_workflow_id=workflow_id,
    )
    db.add(batch)
    await db.commit()

    # 2. Trigger Temporal Workflow
    try:
        client = await get_temporal_client()
        await client.start_workflow(
            ProcessBatchWorkflow.run,
            args=[batch_id, request.raw_text, request.source_type],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
    except Exception as e:
        # If Temporal server is unreachable, log warning and set batch to failed
        batch.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not dispatch workflow to Temporal orchestrator: {str(e)}",
        )

    # Log telemetry trace link
    telemetry.log_trace(batch_id=batch_id, name="batch_ingestion", metadata={"source_type": request.source_type})

    return {
        "batch_id": batch_id,
        "status": "processing",
        "temporal_workflow_id": workflow_id,
        "message": "Batch accepted for extraction and routing.",
    }


@router.get("/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves batch status, metadata, and extracted action items for human review."""
    query = select(BatchModel).where(BatchModel.id == batch_id)
    result = await db.execute(query)
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with ID '{batch_id}' not found.",
        )

    # Load associated action items
    items_query = select(ActionItemModel).where(ActionItemModel.batch_id == batch_id).order_by(ActionItemModel.created_at)
    items_res = await db.execute(items_query)
    items = items_res.scalars().all()

    action_items_response = [
        ActionItem(
            id=item.id,
            batch_id=item.batch_id,
            description=item.description,
            suggested_tool=item.suggested_tool,
            final_tool=item.final_tool,
            tool_payload=item.tool_payload or {},
            source_snippet=item.source_snippet,
            speaker=item.speaker,
            suggested_assignee=item.suggested_assignee,
            actionability_type=item.actionability_type,
            priority=item.priority,
            confidence=item.confidence,
            status=item.status,
            external_url=item.external_url,
            rejection_reason=item.rejection_reason,
            executed_at=item.executed_at,
            created_at=item.created_at,
        )
        for item in items
    ]

    return BatchStatusResponse(
        batch_id=batch.id,
        status=batch.status,
        source_type=batch.source_type,
        raw_text=batch.raw_text,
        token_count=batch.token_count,
        items=action_items_response,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        temporal_workflow_id=batch.temporal_workflow_id,
    )


@router.post("/{batch_id}/approve", response_model=dict[str, Any])
async def approve_batch_items(
    batch_id: str,
    request: ActionItemApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sends human approval decisions to the waiting Temporal workflow signal."""
    query = select(BatchModel).where(BatchModel.id == batch_id)
    result = await db.execute(query)
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with ID '{batch_id}' not found.",
        )

    if not batch.temporal_workflow_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch does not have an active Temporal workflow attached.",
        )

    # 1. Send signal to Temporal Workflow
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(batch.temporal_workflow_id)
        decisions_payload = [d.model_dump() for d in request.decisions]
        await handle.signal(ProcessBatchWorkflow.ApprovalReceived, decisions_payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to signal Temporal workflow: {str(e)}",
        )

    # 2. Update Batch Status in DB
    batch.status = "executing"
    await db.commit()

    return {
        "batch_id": batch_id,
        "status": "executing",
        "decisions_received": len(request.decisions),
        "message": "Approval decisions sent to execution engine.",
    }
