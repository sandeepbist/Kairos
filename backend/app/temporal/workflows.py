"""Temporal Workflows: Durable batch processing and human-in-the-loop signal wait."""
from datetime import timedelta
from typing import Any
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity definitions for type-safe invocation
with workflow.unsafe.imports_passed_through():
    from .activities import (
        extract_and_route_activity,
        persist_extracted_items_activity,
        execute_approved_item_activity,
        reject_item_activity,
        update_routing_memory_activity,
        complete_batch_activity,
        expire_batch_activity,
        emit_webhook_event_activity,
    )


async def _emit(event_type: str, data: dict[str, Any]) -> None:
    """Fire-and-forget webhook fan-out; never blocks the pipeline."""
    try:
        await workflow.execute_activity(
            emit_webhook_event_activity,
            args=[event_type, data],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except Exception:  # noqa: BLE001 — webhooks must never fail the batch
        workflow.logger.warning("Webhook emit %s failed; pipeline continues.", event_type)


@workflow.defn
class ProcessBatchWorkflow:
    """Durable workflow managing ingestion, human approval wait, and MCP execution."""

    def __init__(self):
        self._approval_received: bool = False
        self._decisions: list[dict[str, Any]] = []
        self._extracted_item_ids: set[str] = set()
        self._already_accepted: bool = False

    @workflow.update
    def ApprovalReceived(self, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        """Update received when the operator completes item review.

        An update (rather than a raw signal) gives the caller synchronous
        acceptance or rejection: the validator below runs BEFORE the
        decision enters workflow history, so a stale or forged approval
        is refused by the platform, not merely skipped in workflow code.
        """
        self._decisions = decisions
        self._approval_received = True
        return {"accepted": True, "decisions": len(decisions)}

    @ApprovalReceived.validator
    def ApprovalReceivedValidator(self, decisions: list[dict[str, Any]]) -> None:
        """Rejects approval payloads referencing items outside the batch.

        Runs before ApprovalReceived is recorded in history. Duplicate
        submissions are also rejected — an approval is a one-shot,
        guarded by workflow determinism.
        """
        if self._already_accepted:
            raise ValueError("Approval already accepted for this batch")
        unknown = [
            d.get("item_id") for d in decisions
            if d.get("item_id") not in self._extracted_item_ids
        ]
        if unknown:
            raise ValueError(
                f"Decision payload rejected: {len(unknown)} item id(s) "
                "do not belong to this batch."
            )

    @workflow.run
    async def run(
        self,
        batch_id: str,
        raw_text: str,
        source_type: str = "meeting_transcript",
        sandbox_mode: bool = False,
    ) -> dict[str, Any]:
        workflow.logger.info(f"Starting ProcessBatchWorkflow for batch {batch_id}")

        # 1. Activity: Extract & Route via LangGraph (stateless activity invocation)
        extraction_result = await workflow.execute_activity(
            extract_and_route_activity,
            args=[batch_id, raw_text, source_type],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        routed_items = extraction_result.get("routed_items", [])
        token_count = extraction_result.get("token_count", 0)
        # Known item ids gate approval updates (see ApprovalReceived validator)
        self._extracted_item_ids = {i.get("id") for i in routed_items}

        # 2. Activity: Persist Extracted Candidates to PostgreSQL
        await workflow.execute_activity(
            persist_extracted_items_activity,
            args=[batch_id, routed_items, token_count],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # 3. Durable Wait: Human-in-the-Loop Update with 7-Day Expiry.
        # Approval arrives via ApprovalReceived (an update with a
        # validator); unknown-item payloads are rejected before history.
        try:
            await workflow.wait_condition(
                lambda: self._approval_received,
                timeout=timedelta(days=7),
            )
            self._already_accepted = True
        except TimeoutError:
            workflow.logger.warning(f"Batch {batch_id} timed out waiting for approval. Auto-archiving.")
            await workflow.execute_activity(
                expire_batch_activity,
                args=[batch_id],
                start_to_close_timeout=timedelta(seconds=15),
            )
            await _emit("batch.expired", {
                "batch_id": batch_id,
                "reason": "Approval timed out after 7 days",
            })
            return {"batch_id": batch_id, "status": "expired", "reason": "Approval timed out after 7 days"}

        # 4. Process User Decisions (Per-Item Independent Activities with Retry)
        # Reject decisions whose item_id is not part of this batch's extracted
        # items — a stale or forged signal must never trigger execution.
        known_item_ids = {i.get("id") for i in routed_items}
        execution_results = []
        for decision in self._decisions:
            item_id = decision["item_id"]
            if item_id not in known_item_ids:
                workflow.logger.warning(
                    f"Skipping decision for unknown item {item_id} in batch {batch_id}"
                )
                execution_results.append(
                    {"item_id": item_id, "status": "skipped_unknown_item"}
                )
                continue

            action = decision.get("action") or decision.get("decision") or "APPROVE"
            rejection_reason = decision.get("rejection_reason")

            # Find matching item in routed_items
            original_item = next((i for i in routed_items if i.get("id") == item_id), {})
            suggested_tool = original_item.get("suggested_tool", "task_ledger")
            description = original_item.get("description", "")

            if action == "REJECT":
                # Reject item activity
                await workflow.execute_activity(
                    reject_item_activity,
                    args=[batch_id, item_id, rejection_reason],
                    start_to_close_timeout=timedelta(seconds=15),
                )
                # Update memory with rejection negative constraint
                await workflow.execute_activity(
                    update_routing_memory_activity,
                    args=[item_id, batch_id, description, suggested_tool, "rejected", True],
                    start_to_close_timeout=timedelta(seconds=15),
                )
                await _emit("action.rejected", {
                    "batch_id": batch_id,
                    "item_id": item_id,
                    "tool": suggested_tool,
                    "description": description,
                    "rejection_reason": rejection_reason,
                })
                execution_results.append({"item_id": item_id, "status": "rejected"})
            else:
                # APPROVE or MODIFY_AND_APPROVE
                final_tool = decision.get("override_tool") or suggested_tool
                final_payload = decision.get("modified_payload") or original_item.get("tool_payload", {})
                was_overridden = (final_tool != suggested_tool)

                # Execute approved item with exponential backoff retry policy.
                # sandbox_mode is captured at ingest time and threaded through
                # workflow args so the worker's own env/settings never diverge
                # from what the operator approved.
                exec_res = await workflow.execute_activity(
                    execute_approved_item_activity,
                    args=[batch_id, item_id, final_tool, final_payload, description, sandbox_mode],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        backoff_coefficient=2.0,
                        maximum_attempts=3,
                    ),
                )

                # Record feedback in routing memory
                await workflow.execute_activity(
                    update_routing_memory_activity,
                    args=[item_id, batch_id, description, suggested_tool, final_tool, was_overridden],
                    start_to_close_timeout=timedelta(seconds=15),
                )
                await _emit("action.executed", {
                    "batch_id": batch_id,
                    "item_id": item_id,
                    "tool": final_tool,
                    "status": exec_res.get("status"),
                    "description": description,
                    "external_url": exec_res.get("external_url"),
                    "latency_ms": exec_res.get("latency_ms"),
                })
                execution_results.append({"item_id": item_id, "tool": final_tool, "result": exec_res})

        # 5. Complete Batch Activity
        await workflow.execute_activity(
            complete_batch_activity,
            args=[batch_id],
            start_to_close_timeout=timedelta(seconds=15),
        )
        await _emit("batch.completed", {
            "batch_id": batch_id,
            "items": len(self._decisions),
            "executed": sum(1 for r in execution_results if r.get("status") != "rejected" and r.get("status") != "skipped_unknown_item"),
            "rejected": sum(1 for r in execution_results if r.get("status") == "rejected"),
            "skipped": sum(1 for r in execution_results if r.get("status") == "skipped_unknown_item"),
        })

        return {
            "batch_id": batch_id,
            "status": "completed",
            "executions": execution_results,
        }
