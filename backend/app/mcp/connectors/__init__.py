"""MCP connectors package."""
from .base import BaseConnector, ExecutionResult
from .task_ledger_connector import TaskLedgerConnector
from .notion_connector import NotionConnector
from .jira_connector import JiraConnector
from .calendar_connector import CalendarConnector
from .linear_connector import LinearConnector
from .todoist_connector import TodoistConnector
from .email_draft_connector import EmailDraftConnector
from .github_connector import GitHubConnector
from .confluence_connector import ConfluenceConnector
from .google_tasks_connector import GoogleTasksConnector
from .asana_connector import AsanaConnector
from .clickup_connector import ClickUpConnector

__all__ = [
    "BaseConnector",
    "ExecutionResult",
    "TaskLedgerConnector",
    "NotionConnector",
    "JiraConnector",
    "CalendarConnector",
    "LinearConnector",
    "TodoistConnector",
    "EmailDraftConnector",
    "GitHubConnector",
    "ConfluenceConnector",
    "GoogleTasksConnector",
    "AsanaConnector",
    "ClickUpConnector",
]
