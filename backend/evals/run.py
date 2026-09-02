"""Extraction eval harness.

Two modes:

- ``KAIROS_EVAL_LLM=1 python -m evals.run`` — runs the golden set through
  the real LLM provider chain (requires keys; optionally configured
  Langfuse records the run as trace metadata).
- ``python -m evals.run`` — deterministic extractor baseline: scores the
  offline path and acts as the regression floor in CI.

Usage:
    cd backend && PYTHONPATH=. python -m evals.run [--threshold 0.9]

Exits non-zero when the pass rate falls below --threshold, so CI can gate
on it. Set KAIROS_EVAL_BREAKDOWN=1 to print per-case detail.
"""
import argparse
import asyncio
import os
import sys

from app.pipelines.extract import deterministic_fallback_extractor
from app.pipelines.graph import run_extraction_pipeline

from .golden_cases import GOLDEN_CASES
from .scorer import run_eval


def _extract_deterministic(raw_text: str, source_type: str) -> list[dict]:
    return deterministic_fallback_extractor(raw_text, source_type)


async def _extract_llm(raw_text: str, source_type: str) -> list[dict]:
    state = await run_extraction_pipeline(
        batch_id="eval-run",
        raw_text=raw_text,
        source_type=source_type,
    )
    return state["extracted_items"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Kairos extraction eval harness")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="minimum pass rate required (0-1); default 0.9",
    )
    args = parser.parse_args()

    use_llm = os.environ.get("KAIROS_EVAL_LLM") == "1"
    breakdown = os.environ.get("KAIROS_EVAL_BREAKDOWN") == "1"

    if use_llm:
        print(f"Running {len(GOLDEN_CASES)} golden cases through the LLM provider chain...")
        results = run_eval(lambda t, s: asyncio.run(_extract_llm(t, s)))
        mode = "llm"
    else:
        print(f"Running {len(GOLDEN_CASES)} golden cases through the deterministic extractor...")
        results = run_eval(_extract_deterministic)
        mode = "deterministic"

    if breakdown:
        for case in results["cases"]:
            status = "PASS" if case["passed"] else "FAIL"
            line = f"  [{status}] {case['case_id']}: {case['matched']}/{case['expected']} matched"
            if not case["passed"]:
                line += f" — unmatched: {case['unmatched']}"
            print(line)

    print(
        f"\nMode: {mode} | Pass rate: {results['passed']}/{results['total']} "
        f"({results['pass_rate']:.0%}) | threshold: {args.threshold:.0%}"
    )

    if results["pass_rate"] < args.threshold:
        print("EVAL FAILED: below threshold", file=sys.stderr)
        return 1
    print("EVAL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
