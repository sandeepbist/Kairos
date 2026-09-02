"""Golden-set extraction scorer.

Scores a set of extracted items against an expected floor: every
expected item must be matched by some extracted item (field-for-field on
the checkable attributes); extra extracted items are not penalized.
Returns per-case and aggregate results. Pure functions — no network, no
LLM calls — so the same scorer runs in pytest, CI, and against live
LLM output captured elsewhere.
"""
from typing import Any

from .golden_cases import GOLDEN_CASES


def _description_matches(extracted_desc: str, fragments: list[str]) -> bool:
    low = extracted_desc.lower()
    return all(f.lower() in low for f in fragments)


def _item_matches(expected: dict[str, Any], extracted: dict[str, Any]) -> bool:
    """True when `extracted` satisfies every constraint in `expected`."""
    if expected.get("suggested_tool") and extracted.get("suggested_tool") != expected["suggested_tool"]:
        return False
    if "suggested_assignee" in expected and extracted.get("suggested_assignee") != expected["suggested_assignee"]:
        return False
    if "speaker" in expected and extracted.get("speaker") != expected["speaker"]:
        return False
    if expected.get("priority") and extracted.get("priority") != expected["priority"]:
        return False
    fragments = expected.get("description_contains") or []
    if fragments and not _description_matches(extracted.get("description", ""), fragments):
        return False
    return True


def score_case(
    case: dict[str, Any],
    extracted_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Scores one golden case against the items extracted from it."""
    expected = case.get("expected_items", [])
    unmatched: list[dict[str, Any]] = []
    matched_expected_indexes: set[int] = set()

    for ei, exp in enumerate(expected):
        hit = next(
            (ix for ix, item in enumerate(extracted_items) if _item_matches(exp, item)),
            None,
        )
        if hit is None:
            unmatched.append(exp)
        else:
            matched_expected_indexes.add(ei)

    precision_denom = len(extracted_items)
    precision = (len(matched_expected_indexes)) / precision_denom if precision_denom else 1.0
    recall = len(matched_expected_indexes) / len(expected) if expected else 1.0

    return {
        "case_id": case["id"],
        "expected": len(expected),
        "extracted": len(extracted_items),
        "matched": len(matched_expected_indexes),
        "unmatched": unmatched,
        "precision_floor": round(precision, 3),
        "recall": round(recall, 3),
        "passed": recall == 1.0,
    }


def run_eval(extract_fn) -> dict[str, Any]:
    """Runs the full golden set through an extraction function.

    ``extract_fn(raw_text, source_type) -> list[dict]`` may be the
    deterministic extractor, a live LLM pipeline, or a recorded capture.
    """
    results = [score_case(case, extract_fn(case["raw_text"], case["source_type"]))
               for case in GOLDEN_CASES]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    return {
        "cases": results,
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 3) if total else 1.0,
        "all_passed": passed == total,
    }
