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
    )


@workflow.defn
class ProcessBatchWorkflow:
    """Durable workflow managing ingestion, human approval wait, and MCP execution."""

    def __init__(self):
        self._approval_received: bool = False
        self._decisions: list[dict[str, Any]] = []

    @workflow.signal
    def ApprovalReceived(self, decisions: list[dict[str, Any]]) -> None:
        """Signal received when human completes item review."""
        self._decisions = decisions
        self._approval_received = True

    @workflow.run
    async def run(
        self,
        batch_id: str,
        raw_text: str,
        source_type: str = "meeting_transcript",
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

        # 2. Activity: Persist Extracted Candidates to PostgreSQL
        await workflow.execute_activity(
            persist_extracted_items_activity,
            args=[batch_id, routed_items, token_count],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # 3. Durable Wait: Human-in-the-Loop Signal with 7-Day Expiration Timeout
        try:
            await workflow.wait_condition(
                lambda: self._approval_received,
                timeout=timedelta(days=7),
            )
        except TimeoutError:
            workflow.logger.warn(f"Batch {batch_id} timed out waiting for approval. Auto-archiving.")
            await workflow.execute_activity(
                expire_batch_activity,
                args=[batch_id],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return {"batch_id": batch_id, "status": "expired", "reason": "Approval timed out after 7 days"}

        # 4. Process User Decisions (Per-Item Independent Activities with Retry)
        execution_results = []
        for decision in self._decisions:
            item_id = decision["item_id"]
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
                execution_results.append({"item_id": item_id, "status": "rejected"})
            else:
                # APPROVE or MODIFY_AND_APPROVE
                final_tool = decision.get("override_tool") or suggested_tool
                final_payload = decision.get("modified_payload") or original_item.get("tool_payload", {})
                was_overridden = (final_tool != suggested_tool)

                # Execute approved item with exponential backoff retry policy
                exec_res = await workflow.execute_activity(
                    execute_approved_item_activity,
                    args=[batch_id, item_id, final_tool, final_payload, description],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        backoff_coefficient=2.0,
                        maximum_attempts=3,
                    ),
                )

                # Record feedback in Mem0 / DB
                await workflow.execute_activity(
                    update_routing_memory_activity,
                    args=[item_id, batch_id, description, suggested_tool, final_tool, was_overridden],
                    start_to_close_timeout=timedelta(seconds=15),
                )
                execution_results.append({"item_id": item_id, "tool": final_tool, "result": exec_res})

        # 5. Complete Batch Activity
        await workflow.execute_activity(
            complete_batch_activity,
            args=[batch_id],
            start_to_close_timeout=timedelta(seconds=15),
        )

        return {
            "batch_id": batch_id,
            "status": "completed",
            "executions": execution_results,
        }
