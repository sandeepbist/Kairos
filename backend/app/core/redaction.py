"""Secret redaction for logs and persisted error strings.

LLM SDK and HTTP client exceptions sometimes echo request URLs with
embedded credentials (e.g. Gemini's ``?key=API_KEY``) or raw key
assignments (``API key not valid. key=AI...``). Any error text that may
flow into workflow history or logs passes through here first.
"""
import re

# Secret-bearing query/matrix params in URLs: ?key=... / &api_key=...
_URL_SECRET = re.compile(
    r"([?&](?:api[_-]?key|key|token|access[_-]?token|client[_-]?secret|password|secret)=)[^\s&'\"]+",
    re.IGNORECASE,
)
# Key-value form anywhere in prose: key=VALUE (word boundary before, so
# 'monkey=x' doesn't match), value = non-space run.
_KV_SECRET = re.compile(
    r"\b((?:api[_-]?key|key|token|access[_-]?token|client[_-]?secret|password|secret)\s*[=:])\s*[^\s&'\"]+",
    re.IGNORECASE,
)
# Bearer/Basic authorization values
_AUTH_HEADER = re.compile(r"(Bearer\s+|Basic\s+)[A-Za-z0-9\-_.~+/]+=*", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Replaces credential-shaped substrings with a placeholder."""
    if not text:
        return text
    text = _URL_SECRET.sub(r"\1[REDACTED]", text)
    text = _KV_SECRET.sub(r"\1[REDACTED]", text)
    text = _AUTH_HEADER.sub(r"\1[REDACTED]", text)
    return text


def redact_error(exc: Exception) -> str:
    """str(exc) with secrets stripped; safe for logs and history."""
    return redact_secrets(str(exc))
