"""Temporal Worker: Listens on task queue and executes workflows & activities."""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.config import settings
from .workflows import ProcessBatchWorkflow
from .gmail_poll import GmailPollWorkflow
from .slack_ingest import SlackIngestWorkflow
from .webhook_dispatch import WebhookDispatchWorkflow
from .activities import (
    extract_and_route_activity,
    persist_extracted_items_activity,
    execute_approved_item_activity,
    reject_item_activity,
    update_routing_memory_activity,
    complete_batch_activity,
    expire_batch_activity,
    ingest_gmail_history_activity,
    slack_socket_poll_activity,
    emit_webhook_event_activity,
    dispatch_webhooks_activity,
)

logger = logging.getLogger(__name__)


async def get_temporal_client() -> Client:
    """Connects to the Temporal server."""
    return await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
    )


def create_worker(client: Client) -> Worker:
    """Instantiates a Temporal Worker with all workflows and activities."""
    return Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        # Align activity concurrency with the DB pool (10 + 20 overflow):
        # temporalio's default 100 would oversubscribe Postgres during a
        # multi-batch burst, leaving activities to timeout on pool_timeout
        # and retry — doubling load exactly when the system is busiest.
        max_concurrent_activities=settings.TEMPORAL_MAX_CONCURRENT_ACTIVITIES,
        workflows=[ProcessBatchWorkflow, GmailPollWorkflow, SlackIngestWorkflow, WebhookDispatchWorkflow],
        activities=[
            extract_and_route_activity,
            persist_extracted_items_activity,
            execute_approved_item_activity,
            reject_item_activity,
            update_routing_memory_activity,
            complete_batch_activity,
            expire_batch_activity,
            ingest_gmail_history_activity,
            slack_socket_poll_activity,
            emit_webhook_event_activity,
            dispatch_webhooks_activity,
        ],
    )


async def run_worker():
    """Main worker event loop."""
    # Force a plain StreamHandler on the root logger: some dependency
    # (mcp/langsmith chain) installs a RichHandler at import time, and
    # rich's handler re-enters rich imports while emitting. Inside
    # Temporal's workflow sandbox that re-entrancy is fatal — rich 15+
    # calls os.getcwd() at module import, which the sandbox restricts,
    # so every workflow activation dies with a circular ImportError and
    # batches stall in "processing" forever. Plain logging keeps the
    # sandbox replay import-clean regardless of rich's version.
    logging.basicConfig(level=logging.INFO, force=True)
    logger.info(f"Connecting Temporal worker to {settings.TEMPORAL_HOST}...")
    client = await get_temporal_client()
    worker = create_worker(client)
    logger.info(f"Temporal Worker running on queue: {settings.TEMPORAL_TASK_QUEUE}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
