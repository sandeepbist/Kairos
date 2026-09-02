"""Temporal Worker: Listens on task queue and executes workflows & activities."""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.config import settings
from .workflows import ProcessBatchWorkflow
from .gmail_poll import GmailPollWorkflow
from .slack_ingest import SlackIngestWorkflow
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
        workflows=[ProcessBatchWorkflow, GmailPollWorkflow, SlackIngestWorkflow],
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
        ],
    )


async def run_worker():
    """Main worker event loop."""
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Connecting Temporal worker to {settings.TEMPORAL_HOST}...")
    client = await get_temporal_client()
    worker = create_worker(client)
    logger.info(f"Temporal Worker running on queue: {settings.TEMPORAL_TASK_QUEUE}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
