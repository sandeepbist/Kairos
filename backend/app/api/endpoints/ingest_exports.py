"""Notetaker-export ingestion: the layer after your meeting notetaker.

Accepts exported transcripts/notes from Meetily, Hyprnote, Granola,
Otter, Fireflies, and plain markdown/DOCX exports, normalizes their
front-matter and speaker formatting into Kairos source text, and starts
the standard extraction workflow. This endpoint is what lets Kairos be
the execution layer for notetakers that stop at the summary.
"""
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints.batches import ingest_batch  # reuse the ingest core
from app.db.session import get_db
from app.schemas.action_item import BatchIngestRequest

router = APIRouter(prefix="/ingest", tags=["ingest"])


class ExportIngestRequest(BatchIngestRequest):
    """A notetaker export: markdown or plain text with optional YAML-ish
    front matter (title, date, attendees)."""

    # markdown | otter | fireflies | slack_export | plain
    export_format: str = "markdown"
    title: str | None = None


# --- Normalization ----------------------------------------------------------

_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LINE_LABEL = re.compile(r"^(?:\d{1,2}:\d{2}(?::\d{2})?\s+)?([A-Z][\w .'-]{0,40})\s+\d{1,2}:\d{2}")


def strip_front_matter(text: str) -> tuple[str, dict[str, str]]:
    """Removes YAML front matter, returning (body, meta)."""
    m = _FRONT_MATTER.match(text)
    if not m:
        return text, {}
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()
    return text[m.end():], meta


def normalize_slack_export(raw: str) -> str:
    """Normalizes Slack export JSON (messages array or channel history)
    and copied thread text into 'Name: content' speaker turns.

    Slack exports carry timestamps as unix epochs and messages as
    {user/user_profile/name, text}; copied threads look like
    'Name  12:34 PM  message'. Both become plain speaker lines.
    """
    import json as _json

    # JSON form: a bare list, or a {"messages": [...]} / channel-history dict
    stripped = raw.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            data = _json.loads(stripped)
            messages = data if isinstance(data, list) else data.get("messages", [])
            lines = []
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                who = (
                    msg.get("user_profile", {}).get("display_name")
                    or msg.get("user")
                    or msg.get("name")
                    or "Someone"
                )
                text = (msg.get("text") or "").strip()
                if text:
                    lines.append(f"{who}: {text}")
            if lines:
                return "\n".join(lines)
        except ValueError:
            pass  # not JSON after all — fall through to text handling

    # Copied-thread text: 'Name  12:34 PM  content' (Slack copy layout)
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^([A-Za-z][\w .'-]{0,40}?)\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\s+(.+)$", s)
        if m:
            lines.append(f"{m.group(1)}: {m.group(2)}")
        else:
            lines.append(s)
    return "\n".join(lines)


def normalize_export(raw: str, export_format: str) -> str:
    """Cleans common notetaker artifacts so the extractor sees plain
    conversation text.

    - Otter/Fireflies CSV-ish exports: 'Name 12:34  Speaker text' lines
      become 'Name: text'
    - Meetily/Granola markdown: headers and bullet summary sections are
      dropped; speaker lines are kept
    - Everything: control characters and zero-width chars removed
    """
    text = raw.replace("\u200b", "").replace("\ufeff", "")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        # Timestamped speaker label: "Sarah 12:04 file the report"
        labeled = _LINE_LABEL.match(stripped)
        if labeled and export_format in ("otter", "fireflies", "markdown"):
            rest = stripped[labeled.end():].strip()
            lines.append(f"{labeled.group(1).strip()}: {rest}")
            continue
        # Markdown chrome that carries no conversation. Headers, summary
        # bullets, and bold-labeled filler sections — with or without a
        # leading list dash — are dropped.
        if export_format == "markdown":
            bare = stripped[2:].strip() if stripped.startswith("- ") else stripped
            if stripped.startswith("#"):
                continue
            if bare.startswith(("**Summary", "**Key", "**Action", "**Decision", "**Note")):
                continue
        lines.append(stripped)
    cleaned = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


# --- Endpoint ----------------------------------------------------------------

@router.post("/export", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def ingest_export(
    request: ExportIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingests a notetaker export and starts the standard extraction
    workflow — Kairos as the layer after Meetily/Granola/Otter/Hyprnote.

    The export is normalized (front matter parsed, timestamp labels
    converted to speaker turns, summary chrome dropped) before it hits
    the same extraction pipeline a manual paste uses.
    """
    body, meta = strip_front_matter(request.raw_text)
    if request.export_format == "slack_export":
        normalized = normalize_slack_export(body)
    else:
        normalized = normalize_export(body, request.export_format)
    if len(normalized) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Export contained no usable conversation text after normalization.",
        )

    title = request.title or meta.get("title") or meta.get("meeting")
    source_text = f"[{title}]\n\n{normalized}" if title else normalized

    inner = BatchIngestRequest(
        raw_text=source_text,
        source_type=request.source_type,
    )
    return await ingest_batch(inner, db)
