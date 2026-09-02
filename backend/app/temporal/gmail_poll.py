"""Gmail ingestion workflow: poll for new mail and turn threads into batches.

The workflow is deliberately thin and sandbox-clean: no httpx, DB, or
crypto imports at module level — everything non-deterministic lives in
the activity. Runs on a Temporal Schedule created by the API when the
operator connects Gmail.
"""
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import ingest_gmail_history_activity


@workflow.defn
class GmailPollWorkflow:
    """One poll cycle: the activity handles token refresh, incremental
    history sync (messages added since the last watermark), per-thread
    batch creation via the shared ingest core, and watermark advance."""

    @workflow.run
    async def run(self) -> dict[str, Any]:
        result = await workflow.execute_activity(
            ingest_gmail_history_activity,
            start_to_close_timeout=workflow.timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        return result
