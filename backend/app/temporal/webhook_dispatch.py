"""Webhook dispatch workflow: one thin cycle per Schedule tick.

The 5-minute `kairos-webhook-dispatch` Schedule starts this workflow, which
runs one dispatch scan activity — the same Schedule → thin workflow → fat
activity shape as the Gmail and Slack pollers. Durable delivery comes from
the pending-row ledger: every attempt, response code, and retry time lives
in Postgres, so worker restarts never lose a delivery.
"""
import logging
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import dispatch_webhooks_activity

logger = logging.getLogger(__name__)


@workflow.defn
class WebhookDispatchWorkflow:
    """One dispatch scan. A failed scan waits for the next Schedule tick."""

    @workflow.run
    async def run(self) -> dict[str, Any]:
        result = await workflow.execute_activity(
            dispatch_webhooks_activity,
            start_to_close_timeout=workflow.timedelta(seconds=120),
            # A bad cycle (receiver timeouts) waits for the next tick.
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return result
