"""Redaction Battle Tests: credentials must never reach logs or history."""
from app.core.redaction import redact_error, redact_secrets


def test_url_query_key_redacted():
    text = "GET https://x.googleapis.com/v1/models/gemini:gen?key=AIzaSyD1234567890abc failed"
    out = redact_secrets(text)
    assert "AIzaSyD1234567890abc" not in out
    assert "key=[REDACTED]" in out


def test_url_api_key_param_redacted():
    text = "https://api.example.com/v1?api_key=sk-proj-1234567890abcdefgh&x=1"
    out = redact_secrets(text)
    assert "sk-proj" not in out


def test_prose_key_value_redacted():
    text = "400 API key not valid. key=AIzaSyBADKEY123456"
    out = redact_secrets(text)
    assert "AIzaSyBADKEY123456" not in out


def test_bearer_token_redacted():
    text = "Authorization: Bearer ya29.a0AfH6SMBx-tokensub denied"
    out = redact_secrets(text)
    assert "ya29" not in out


def test_colon_form_redacted():
    text = "OpenAI Error: api_key: sk-1234567890abcdefgh invalid"
    out = redact_secrets(text)
    assert "sk-1234567890abcdefgh" not in out


def test_ordinary_words_not_redacted():
    text = "the keyboard= mechanical layout and monkey=patch are fine"
    assert "[REDACTED]" not in redact_secrets(text)


def test_redact_error_exception():
    exc = Exception("Request failed: ?key=AIzaSyLEAKME123456789 timeout")
    out = redact_error(exc)
    assert "AIzaSyLEAKME123456789" not in out
    assert "[REDACTED]" in out


def test_empty_and_none_safe():
    assert redact_secrets("") == ""
    assert redact_secrets("no secrets here") == "no secrets here"
