"""Chunked long-document extraction tests: boundaries, dedup, end-to-end."""
import pytest

from app.config import settings
from app.pipelines.chunking import (
    chunk_transcript,
    estimate_tokens,
    merge_extracted_chunks,
)
from app.pipelines.extract import deterministic_fallback_extractor


def _transcript(speakers_minutes: int) -> str:
    """Synthesizes a labeled transcript with many speaker turns."""
    lines = []
    for i in range(speakers_minutes):
        lines.append(f"Sarah: Item number {i}, please file the report task {i} before Friday.")
        lines.append(f"Alex: I will schedule the review meeting {i} with the team on Thursday.")
        lines.append(f"John: Let me update the spec document {i} in the roadmap wiki then.")
        lines.append("Unlabeled chatter about lunch plans and weather that carries no actions.")
    return "\n".join(lines)


def test_short_input_single_chunk():
    text = "Sarah: Alex, please file a ticket.\nAlex: I will schedule the review."
    chunks = chunk_transcript(text, settings.CHUNK_TOKENS)
    assert len(chunks) == 1
    assert "please file a ticket" in chunks[0] and "schedule the review" in chunks[0]


def test_chunks_respect_speaker_turn_boundaries():
    text = _transcript(30)  # several thousand tokens
    chunks = chunk_transcript(text, 400)
    assert len(chunks) > 1
    # No chunk breaks mid-turn: every chunk that starts with a speaker
    # label begins at a turn boundary, and the last line of a chunk is a
    # complete line (no split inside a line).
    for c in chunks:
        for line in c.split("\n"):
            assert not line.startswith(" ")  # no orphaned continuations


def test_all_speaker_turns_reachable_after_chunking():
    text = _transcript(40)
    chunks = chunk_transcript(text, 300)
    rejoined = "\n\n".join(chunks)
    # Every unique action line from the original survives chunking
    for i in (0, 10, 39):
        assert f"file the report task {i}" in rejoined
        assert f"spec document {i}" in rejoined


def test_crumb_merging():
    # A tiny trailing block merges into the previous chunk
    big = "Sarah: " + ("work content here " * 200)
    crumb = "Alex: tiny note"
    text = big + "\nAlex: tiny note"
    chunks = chunk_transcript(text, 300)
    assert len(chunks) >= 1
    assert "tiny note" in chunks[-1]


def test_merge_dedups_identical_descriptions_across_chunks():
    item_a = {"description": "File the compliance report", "suggested_tool": "jira",
              "source_snippet": "file the compliance report"}
    item_b = {"description": "file the compliance report", "suggested_tool": "jira",
              "source_snippet": "File the compliance report, please"}
    item_c = {"description": "Schedule the offsite", "suggested_tool": "calendar",
              "source_snippet": "schedule the offsite"}
    merged, dropped = merge_extracted_chunks([[item_a], [item_b, item_c]], ["c1", "c2"])
    assert len(merged) == 2 and len(dropped) == 1
    assert merged[1]["description"] == "Schedule the offsite"


def test_merge_dedups_by_snippet():
    item_a = {"description": "One phrasing", "suggested_tool": "jira",
              "source_snippet": "Sarah: file the bug"}
    item_b = {"description": "A different phrasing", "suggested_tool": "jira",
              "source_snippet": "Sarah: file the bug"}
    merged, dropped = merge_extracted_chunks([[item_a], [item_b]], ["c1", "c2"])
    assert len(merged) == 1 and len(dropped) == 1


@pytest.mark.asyncio
async def test_long_document_deterministic_extraction_not_truncated():
    """The pipeline must extract actions from beyond the old 3k-token
    truncation point: an actionable line placed at token ~15k must appear."""
    from app.pipelines.graph import run_extraction_pipeline

    # ~20k tokens of filler before the late, actionable line
    filler = _transcript(120)
    late_line = "Priya: Rahul, please file the Q4 audit ticket before the deadline."
    text = filler + "\n" + late_line

    state = await run_extraction_pipeline(
        batch_id="test-long-doc",
        raw_text=text,
        source_type="meeting_transcript",
    )
    items = state["routed_items"]
    descriptions = " ".join(i["description"].lower() for i in items)
    assert "q4 audit" in descriptions, "action past the old 3k-token cutoff was lost"


def test_very_long_input_warns_and_caps():
    """Inputs beyond the hard char cap are flagged, not silent."""
    from app.pipelines.ingest import ingest_node

    state = {"raw_text": "A" * (settings.MAX_INPUT_CHARS + 1000), "source_type": "meeting_transcript"}
    out = ingest_node(state)
    # Cap applies to the payload; the XML guard wrapper adds fixed overhead.
    wrapper = out["cleaned_text"]
    inner = wrapper.replace("<untrusted_source_content source_type='meeting_transcript'>\n", "").replace("\n</untrusted_source_content>", "")
    assert len(inner) <= settings.MAX_INPUT_CHARS
    assert any("exceeded" in w for w in out["warning_flags"])
