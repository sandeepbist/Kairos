"""Slack Socket Mode bot: forward-channel ingestion for an operator's Slack.

Slack's Socket Mode connects over a WebSocket — no public URL, no
ingress, no webhook verification — which fits Kairos's bridge-network
deployment. The bot listens in channels it's invited to; when a message
thread carries action-shaped text, the operator can forward it with an
app-mention or reaction, and the thread becomes a standard batch.

No-credential no-op: like the Gmail poller, the bot only runs when
SLACK_BOT_TOKEN and SLACK_APP_TOKEN are configured; without them the
workflow is a clean skip. (The zero-auth path for everyone else is the
existing slack_export ingestion.)

Tokens:
  SLACK_APP_TOKEN  xapp-...  (Socket Mode connection token)
  SLACK_BOT_TOKEN  xoxb-...  (bot OAuth token)
"""
import logging
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import slack_socket_poll_activity


logger = logging.getLogger(__name__)


@workflow.defn
class SlackIngestWorkflow:
    """One Socket Mode listening cycle. The activity owns the entire
    connection (WebSocket + auth + thread collection) because every
    non-deterministic concern lives in activities, never in workflows.
    Runs on a Temporal Schedule, like the Gmail poller."""

    @workflow.run
    async def run(self) -> dict[str, Any]:
        result = await workflow.execute_activity(
            slack_socket_poll_activity,
            start_to_close_timeout=workflow.timedelta(seconds=600),
            retry_policy=RetryPolicy(maximum_attempts=1),  # a failed listen cycle waits for the next Schedule tick
        )
        return result
