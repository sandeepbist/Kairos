"""Ingest Node: Text cleaning, length guardrails, and prompt injection defense."""
import re
from typing import Any
from app.config import settings
from .state import AgentState


def clean_text(raw: str) -> str:
    """Normalizes whitespace and standardizes linebreaks."""
    # Normalize Windows CRLF to Unix LF
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def estimate_token_count(text: str) -> int:
    """Calculates approximate token count based on word and character heuristics."""
    words = len(text.split())
    # Standard rule of thumb: 1 token ~= 0.75 words, or 1 word ~= 1.33 tokens
    return max(1, int(words * 1.33))


def ingest_node(state: AgentState) -> dict[str, Any]:
    """
    Ingests and guards untrusted source text.
    Enforces length limits, wraps in safety delimiters, and computes metrics.
    """
    raw_text = state.get("raw_text", "")
    source_type = state.get("source_type", "meeting_transcript")
    warning_flags: list[str] = list(state.get("warning_flags", []))

    cleaned = clean_text(raw_text)
    token_count = estimate_token_count(cleaned)

    # 1. Length Guardrail: hard bound for memory safety. Extraction length
    # policy (single-pass vs chunked) lives downstream in extract_node.
    if len(cleaned) > settings.MAX_INPUT_CHARS:
        warning_flags.append(
            f"Input exceeded {settings.MAX_INPUT_CHARS} characters and was truncated to that bound."
        )
        cleaned = cleaned[: settings.MAX_INPUT_CHARS]
        token_count = estimate_token_count(cleaned)
    elif token_count > settings.SINGLE_PASS_TOKENS:
        warning_flags.append(
            f"Long input ({token_count} estimated tokens) — extracting in "
            f"{settings.CHUNK_TOKENS}-token segments."
        )

    # 2. Prompt Injection XML Delimiting
    # Wrap in strict XML tags with security boundary
    guarded_text = (
        f"<untrusted_source_content source_type='{source_type}'>\n"
        f"{cleaned}\n"
        f"</untrusted_source_content>"
    )

    return {
        "cleaned_text": guarded_text,
        "token_count": token_count,
        "warning_flags": warning_flags,
        "errors": state.get("errors", []),
    }
