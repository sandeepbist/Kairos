"""Extraction structured-output hardening: method pin, clamps, date normals."""
import pytest

from app.pipelines.extract import ExtractedActionItemSchema


def _base(**overrides):
    payload = {
        "description": "File the checkout bug",
        "suggested_tool": "jira",
        "source_snippet": "file the checkout bug",
    }
    payload.update(overrides)
    return payload


def test_confidence_clamped_out_of_range():
    """Strict-mode schemas drop minimum/maximum, so the model can emit
    1.7 or -0.2; the validator repairs instead of rejecting."""
    assert ExtractedActionItemSchema.model_validate(_base(confidence=1.7)).confidence == 1.0
    assert ExtractedActionItemSchema.model_validate(_base(confidence=-0.3)).confidence == 0.0


def test_confidence_valid_passes_through():
    assert ExtractedActionItemSchema.model_validate(_base(confidence=0.85)).confidence == 0.85


def test_confidence_non_numeric_falls_back():
    assert ExtractedActionItemSchema.model_validate(_base(confidence="high")).confidence == 0.5
    assert ExtractedActionItemSchema.model_validate(_base(confidence=None)).confidence == 0.5


def test_due_date_normalized():
    """Full ISO timestamps truncate to the date; prose dates degrade to
    null rather than failing the item."""
    item = ExtractedActionItemSchema.model_validate(
        _base(suggested_due_date="2026-09-01T17:00:00Z")
    )
    assert item.suggested_due_date == "2026-09-01"
    assert ExtractedActionItemSchema.model_validate(
        _base(suggested_due_date="2026-09-01")
    ).suggested_due_date == "2026-09-01"
    assert ExtractedActionItemSchema.model_validate(
        _base(suggested_due_date="tomorrow")
    ).suggested_due_date is None
    assert ExtractedActionItemSchema.model_validate(
        _base(suggested_due_date="next Friday")
    ).suggested_due_date is None


def test_wire_schema_has_date_hint_no_bounds():
    """The generated JSON schema carries the date format hint (both
    providers accept format where OpenAI strict rejects bounds) and no
    minimum/maximum anywhere — strict-mode compat is structural."""
    schema = ExtractedActionItemSchema.model_json_schema()
    assert schema["properties"]["suggested_due_date"].get("format") == "date"

    def _no_bounds(node):
        if isinstance(node, dict):
            assert "minimum" not in node and "maximum" not in node
            for v in node.values():
                _no_bounds(v)
        elif isinstance(node, list):
            for v in node:
                _no_bounds(v)

    _no_bounds(schema)


def test_method_pinned_in_invoke_path():
    """The production extraction call passes method='json_schema' — a
    dependency bump flipping the default cannot silently degrade to
    the less-reliable function-calling transport."""
    import inspect

    from app.pipelines import extract

    src = inspect.getsource(extract._invoke_extraction_llm)
    assert 'with_structured_output(ExtractedActionItemList, method="json_schema")' in src


@pytest.mark.asyncio
async def test_no_reask_on_clampable_output():
    """A provider response with confidence 1.4 is repaired by the clamp —
    the reask path (attempt 2) is never taken."""
    from app.pipelines.extract import ExtractedActionItemList, _invoke_extraction_llm

    class FakeLLM:
        def with_structured_output(self, _schema, **kwargs):
            return self

        async def ainvoke(self, messages):
            return ExtractedActionItemList(items=[ExtractedActionItemSchema.model_validate(
                _base(confidence=1.4)
            )])

    items, errors = await _invoke_extraction_llm("text", [("gemini", FakeLLM())], "sys")
    assert len(items) == 1
    assert items[0]["confidence"] == 1.0
    assert errors == []


def test_deterministic_output_still_validates():
    """The offline extractor's dicts must survive schema validation after
    the refactor — guards the deterministic path."""
    from app.pipelines.extract import deterministic_fallback_extractor

    items = deterministic_fallback_extractor(
        "Sarah: Alex, please file a ticket for the checkout crash bug.", "meeting_transcript"
    )
    assert items
    for item in items:
        validated = ExtractedActionItemSchema.model_validate(item)
        assert 0.0 <= validated.confidence <= 1.0
