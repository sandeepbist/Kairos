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

    export_format: str = "markdown"  # markdown | otter | fireflies | plain
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
