"""Speaker-turn-aware chunking for long-document extraction.

Inputs longer than the single-pass ceiling are split on speaker-turn
boundaries into segment-sized chunks, extracted independently (map), and
merged with near-duplicate elimination (reduce). Splitting on speaker
turns rather than raw character counts keeps each item's verbatim source
quote within one chunk, so extracted snippets remain truthful.

Chunk sizing: a segment targets a token budget derived from the
configured single-pass ceiling — the map prompt must leave room for the
preamble and the output schema.
"""
import re
from typing import Any

# Never produce chunks smaller than this many tokens; trailing crumbs are
# merged into the previous chunk instead of becoming a costly LLM call
# with almost no content.
_MIN_CHUNK_TOKENS = 200

_SPEAKER_LINE = re.compile(r"^([A-Z][\w .'-]{0,40}):\s", re.MULTILINE)


def estimate_tokens(text: str) -> int:
    """Same heuristic the ingest guard uses, shared for consistency."""
    words = len(text.split())
    return max(1, int(words * 1.33))


def _line_count_to_tokens(lines: list[str]) -> int:
    return estimate_tokens("\n".join(lines))


def chunk_transcript(
    text: str,
    max_chunk_tokens: int,
) -> list[str]:
    """Splits text into chunks of roughly max_chunk_tokens, breaking only
    at speaker-turn boundaries (or paragraph boundaries for unlabeled
    text). Returns [] for empty input; a single chunk when it fits.
    """
    if not text.strip():
        return []

    # Split into speaker-turn blocks: a new block starts at each
    # "Name:" line. Unlabeled text falls back to paragraph blocks.
    starts = [m.start() for m in _SPEAKER_LINE.finditer(text)]
    blocks: list[str] = []
    if len(starts) >= 2:
        bounds = starts + [len(text)]
        for i in range(len(bounds) - 1):
            blocks.append(text[bounds[i]:bounds[i + 1]].strip("\n"))
        head = text[:bounds[0]].strip("\n")
        if head.strip():
            blocks.insert(0, head)
    else:
        blocks = [p.strip("\n") for p in text.split("\n\n") if p.strip()]

    # A single block over budget (monologue with no blank lines, one
    # giant speaker turn) would otherwise pass through whole and defeat
    # the ceiling. Force-split such blocks by lines, preserving order.
    # Word counts (not per-line estimate floors) drive the budget so the
    # joined piece measures at or under budget exactly.
    split_blocks: list[str] = []
    for block in blocks:
        while True:
            if not block.strip() or int(len(block.split()) * 1.33) <= max_chunk_tokens:
                break
            lines = block.splitlines()
            piece: list[str] = []
            piece_words = 0
            while lines:
                line_words = len(lines[0].split())
                if piece and int((piece_words + line_words) * 1.33) > max_chunk_tokens:
                    break
                piece.append(lines.pop(0))
                piece_words += line_words
            if not piece:  # one pathological line exceeds budget alone
                piece.append(lines.pop(0))
            split_blocks.append("\n".join(piece))
            block = "\n".join(lines)
        if block.strip():
            split_blocks.append(block)
    blocks = split_blocks

    # Greedily pack blocks into chunks under the token budget.
    chunks: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for block in blocks:
        block_tokens = estimate_tokens(block)
        if current and current_tokens + block_tokens > max_chunk_tokens:
            chunks.append(current)
            current, current_tokens = [], 0
        current.append(block)
        current_tokens += block_tokens
    if current:
        chunks.append(current)

    # Merge trailing crumbs into the previous chunk — but never past
    # the budget (the merge must not reintroduce the overrun the
    # splitter just eliminated). An unmergeable crumb stays its own
    # chunk: one extra LLM call beats an over-context call.
    packed: list[str] = ["\n\n".join(parts) for parts in chunks]
    while len(packed) >= 2 and estimate_tokens(packed[-1]) < _MIN_CHUNK_TOKENS:
        tail = packed.pop()
        if estimate_tokens(packed[-1]) + estimate_tokens(tail) <= max_chunk_tokens:
            packed[-1] = packed[-1] + "\n\n" + tail
        else:
            packed.append(tail)
            break
    return packed


def _snippet_in(snippet: str, text: str) -> bool:
    """True when the verbatim snippet (or its first line) occurs in text."""
    if not snippet:
        return False
    if snippet in text:
        return True
    first_line = snippet.split("\n", 1)[0].strip()
    return bool(first_line) and first_line in text


def merge_extracted_chunks(
    chunk_results: list[list[dict[str, Any]]],
    chunk_texts: list[str],
    dedup_embedding=None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reduces per-chunk extraction results into one item list.

    Near-duplicate elimination, in order of strength:
    1. identical normalized description + same tool
    2. same verbatim source snippet
    3. embedding cosine above 0.92 (when an embedder is provided)

    Dropped duplicates are returned as a report list for the pipeline's
    error/info channel. Original chunk ordering is preserved.
    """
    merged: list[dict[str, Any]] = []
    seen_descriptions: set[tuple[str, str]] = set()
    seen_snippets: set[str] = set()
    dropped: list[str] = []

    for items in chunk_results:
        for item in items:
            desc_key = (
                " ".join(item.get("description", "").lower().split()),
                item.get("suggested_tool", ""),
            )
            snippet_key = " ".join((item.get("source_snippet") or "").lower().split())
            is_dup = desc_key in seen_descriptions or (
                snippet_key and snippet_key in seen_snippets
            )
            if not is_dup and dedup_embedding is not None:
                item_vec = dedup_embedding(item.get("description", ""))
                for kept in merged:
                    kept_vec = dedup_embedding(kept.get("description", ""))
                    from app.pipelines.memory import cosine_similarity

                    if item_vec and kept_vec and cosine_similarity(item_vec, kept_vec) > 0.92:
                        is_dup = True
                        break
            if is_dup:
                dropped.append(item.get("description", "")[:80])
                continue
            seen_descriptions.add(desc_key)
            if snippet_key:
                seen_snippets.add(snippet_key)
            merged.append(item)

    return merged, dropped
