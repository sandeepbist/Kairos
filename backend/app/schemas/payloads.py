"""Tool-specific payload schemas for target execution destinations."""
from datetime import date
from typing import Literal, Union, Any
from pydantic import BaseModel, Field


class JiraPayload(BaseModel):
    """Payload specifically validated for Atlassian Jira issue creation."""
    project_key: str = Field(default="PROJ", description="Jira project key (e.g. ENG, FIN, OPS)")
    issue_type: Literal["Task", "Story", "Bug"] = Field(default="Task", description="Jira issue type")
    summary: str = Field(..., description="Short summary/title of the Jira issue")
    description: str = Field(..., description="Detailed description and context")
    priority: Literal["Low", "Medium", "High", "Critical"] = Field(default="Medium", description="Jira priority level")
    due_date: date | None = Field(default=None, description="Optional due date")


class CalendarPayload(BaseModel):
    """Payload specifically validated for Google Calendar event creation."""
    title: str = Field(..., description="Calendar event title / summary")
    start_time: str = Field(..., description="ISO 8601 formatted start datetime (e.g. 2026-09-01T10:00:00Z)")
    end_time: str = Field(..., description="ISO 8601 formatted end datetime (e.g. 2026-09-01T10:30:00Z)")
    attendees: list[str] = Field(default_factory=list, description="List of attendee email addresses")
    location: str | None = Field(default=None, description="Location or virtual meeting link")
    reminder_minutes_before: int = Field(default=30, description="Reminder notification in minutes prior to event")


class NotionPayload(BaseModel):
    """Payload specifically validated for Notion database page creation."""
    database_id: str | None = Field(default=None, description="Target Notion Database ID")
    title: str = Field(..., description="Page title")
    details: str = Field(default="", description="Main page content / description blocks")
    due_date: str | None = Field(default=None, description="Due date string or ISO date")
    properties: dict[str, Any] = Field(default_factory=dict, description="Custom Notion database properties")


class TaskLedgerPayload(BaseModel):
    """Payload for custom internal Task Ledger fallback MCP server."""
    title: str = Field(..., description="Task title")
    notes: str = Field(default="", description="Task context and details")
    priority: Literal["low", "medium", "high"] = Field(default="medium", description="Priority level")
    due_date: str | None = Field(default=None, description="Optional target completion date")


ToolPayloadUnion = Union[JiraPayload, CalendarPayload, NotionPayload, TaskLedgerPayload]
