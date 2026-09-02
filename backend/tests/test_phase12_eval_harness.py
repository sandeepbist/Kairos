"""Golden-set eval gate: extraction quality regression tests.

Runs the same eval as `python -m evals.run` (deterministic mode) inside
pytest so extraction regressions fail the suite directly. The LLM mode
(KAIROS_EVAL_LLM=1) is exercised manually or in CI with provider keys.
"""
from evals.golden_cases import GOLDEN_CASES
from evals.scorer import run_eval, score_case


def test_golden_set_size():
    """The golden set holds at least 20 cases across all source types."""
    assert len(GOLDEN_CASES) >= 20
    types = {c["source_type"] for c in GOLDEN_CASES}
    assert types >= {"meeting_transcript", "email_thread", "slack_conversation", "general_notes"}


def test_deterministic_extractor_passes_golden_set():
    """The offline extractor (every fresh clone's default) must clear the
    90% floor — it currently passes 100%."""
    from app.pipelines.extract import deterministic_fallback_extractor

    results = run_eval(deterministic_fallback_extractor)
    assert results["pass_rate"] >= 0.9, (
        f"Extraction eval regressed: {results['passed']}/{results['total']}; "
        f"failing cases: "
        f"{[c['case_id'] for c in results['cases'] if not c['passed']]}"
    )


def test_scorer_floor_semantics():
    """Expected items are a floor: extras are allowed, misses are not."""
    case = {"id": "x", "raw_text": "", "source_type": "meeting_transcript",
            "expected_items": [{"suggested_tool": "jira",
                                "description_contains": ["bug"]}]}
    ok = score_case(case, [{"suggested_tool": "jira",
                            "description": "Fix the login bug"},
                           {"suggested_tool": "notion",
                            "description": "extra item"}])
    assert ok["passed"] and ok["recall"] == 1.0
    assert ok["precision_floor"] == 0.5  # 1 expected matched of 2 extracted

    miss = score_case(case, [{"suggested_tool": "notion",
                              "description": "unrelated"}])
    assert not miss["passed"] and miss["recall"] == 0.0
