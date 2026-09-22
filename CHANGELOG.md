# Changelog

All notable changes to Kairos are documented here.

The format follows [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.1/),
and versions follow [Semantic Versioning](https://semver.org/).

Releases are cut with `scripts/release.sh` — it moves `[Unreleased]`
entries under a dated version heading and opens a fresh `[Unreleased]`.

## [Unreleased]

Tracked in commit history; curated here at release time.

## [0.1.0] — 2026-09-10

First tagged release. Single-operator ambient action engine: transcripts
in, schema-validated action items out, nothing executes without an
explicit human approval.

### Added

- Transcript ingestion (paste, notetaker exports — Meetily/Granola/Otter,
  Slack workspace exports) with front matter, timestamp, and summary
  chrome normalization.
- LLM extraction via LangGraph with Google Gemini or OpenAI; a
  deterministic offline parser keeps the full flow working with zero
  credentials configured.
- Long-document handling: single-pass under 50k tokens, speaker-turn-aware
  map-reduce above it, cross-chunk deduplication, no truncation.
- Human-in-the-loop review workbench: per-item verbatim source quote,
  suggested destination tool, confidence score, edit/approve/dismiss.
- Twelve execution destinations: Jira, Notion, Google Calendar, Linear,
  Todoist, GitHub issues, Confluence, Google Tasks, Asana, ClickUp, email
  drafts (operator-reviewed before send), and the built-in Task Ledger.
- Durable execution on Temporal: per-item retry, crash-resume via
  workflow replay, 7-day approval expiry.
- SHA-256 idempotency keys on every execution — retries and replays
  never double-create anything.
- Embedding-backed routing memory (Gemini/OpenAI vectors, cosine
  similarity) with keyword matching as the no-key fallback; suggestions
  adjust from confirms, overrides, and rejections.
- MCP 2.x task ledger server runnable standalone over stdio
  (`python -m app.mcp.servers.kairos`) exposing submit_transcript,
  list_pending_items, approve_items; Kairos can also be driven as a
  tool from Claude Desktop or Cursor.
- Notion and Jira dispatch over real MCP transport to the vendors' GA
  remote servers, REST for static keys, automatic REST fallback on
  transport failure.
- Gmail poller: 15-minute Temporal Schedule pulls new threads.
- Slack Socket Mode bot: live threads and DMs become batches without a
  public URL.
- Outbound webhooks (Standard Webhooks spec): HMAC-SHA256 over
  `{msg_id}.{timestamp}.{payload}`, timestamp inside the signature
  (replay defense), secrets shown once and encrypted in the vault,
  durable retry ladder with jitter, 410 auto-disable, SSRF guards
  including private-URL opt-in with link-local stays blocked.
- Settings UI: sandbox/live toggle, encrypted credential vault for
  connector and LLM keys, tool-target defaults per destination.
- Version reporting: `GET /api/health` returns the version from
  `backend/VERSION` (single source of truth for releases).
- Backup tooling (`scripts/backup.sh`): compressed `pg_dump` plus a
  paired `0600` key file; dump and key are worthless apart.
- Zero-downtime Fernet key rotation
  (`scripts/rotate_fernet_key.py`): pre-flight decrypt of every row,
  abort before any write on the first failure, one-transaction
  re-encrypt, `ENCRYPTION_KEY_PREVIOUS` bridge.

### Security

- AES-256 (Fernet) encryption at rest for all vault credentials;
  decryption only in memory during approved executions; credential-shaped
  strings stripped from error text and logs.
- Operator API key (≥16 chars) guarding every route; production startup
  refuses to boot with a missing API key, the dev encryption key, or
  `DEBUG=true`.
- Exact-origin CORS, `nosniff`/`DENY`/HSTS headers, JSON logs without
  stack traces, `/docs` disabled in production.
- Untrusted-input handling: bodies over 1 MB rejected with 413,
  `raw_text` capped at 50k characters, approval payloads capped at 200
  decisions, transcript content wrapped in explicit delimiters and
  parsed as data (prompt-injection defense), never sent in webhook
  payloads.
- Per-IP rate limits (60 reads/min, 10 writes/min) hardened against
  `X-Forwarded-For` spoofing at both the uvicorn and limiter layers;
  `TRUST_PROXY` opt-in only behind a trusted proxy.
- `DELETE /api/history/batches/{id}` erases a batch and its records; a
  batch still mid-workflow returns 409 instead of corrupting state.

### Infrastructure

- FastAPI backend, Next.js dashboard with a server-side API proxy —
  browsers never hold the operator API key.
- Alembic versioned migrations; the app refuses to boot on an
  unmigrated database.
- `docker-compose.dev.yml` (local infrastructure) and
  `docker-compose.prod.yml` (full stack: postgres 17-alpine, Temporal
  1.8.2 with volume init, one-shot migrate gate, API, worker, frontend
  on an internal bridge network; only the frontend is published).
- Multi-stage non-root Docker images with healthchecks for both backend
  and frontend.
- GitHub Actions CI (`.github/workflows/ci.yml`): 237-test backend suite
  against live PostgreSQL + Temporal, extraction eval gate at a 90%
  floor over a 25-case golden set, frontend lint/typecheck/build.
- Security scanning workflow (`.github/workflows/security.yml`):
  gitleaks secret scan over full history, pip-audit dependency audit,
  CodeQL for Python and JavaScript/TypeScript, weekly schedule.
- GHCR publishing (`.github/workflows/publish.yml`): edge channel from
  main (`edge` + `sha-<short>` tags), stable channel from `v*` tags
  (`vX.Y.Z`, `stable`, `latest`), with provenance and SBOM attestations.
- Tag-driven GitHub Releases (`.github/workflows/release.yml`) verified
  against `backend/VERSION`; `scripts/release.sh` cuts versions;
  Dependabot covers pip, npm, GitHub Actions, and Docker Compose.

[Unreleased]: https://github.com/sandeepbist/Kairos/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeepbist/Kairos/releases/tag/v0.1.0
