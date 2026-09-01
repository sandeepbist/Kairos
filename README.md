# Kairos

Kairos turns meeting transcripts, email threads, and chat logs into actions
that actually run. An extraction pipeline proposes the actions, a human
approves each one, and the system executes them in whatever tools the
operator has connected — keeping an audit trail and learning routing
preferences along the way.

It is self-hosted, single-operator software. You run the whole stack; your
transcripts and credentials stay on your infrastructure.

**What it is not:** a multi-user SaaS. One operator key, one set of connected
tool accounts, one shared history. See [Deployment scope](#deployment-scope)
before going live.

## How it works

```
you paste text ─┐
                ▼
        FastAPI API ── auth, rate limit
                │ starts a workflow
                ▼
        Temporal worker ── owns the whole batch lifecycle
                │
                ├─ extract: LangGraph + LLM (or offline parser)
                │   └─ schema-validated items with verbatim source quotes
                ├─ route: semantic memory adjusts tool + confidence
                │   └─ learns from every approve / override / reject
                ├─ wait: human review, 7-day expiry
                │   └─ operator edits payloads, approves, or dismisses
                └─ execute: one activity per approved item
                    ├─ SHA-256 idempotency check → no duplicates on retry
                    ├─ Jira / Notion / Calendar / Task Ledger MCP
                    └─ execution log with URL, latency, status
```

Each stage survives crashes: Temporal replays the workflow instead of losing
it, the idempotency hash prevents a replayed execution from filing the same
ticket twice, and an approval wait that never gets a decision expires
after seven days instead of piling up.

| Choice | Where | Why |
|---|---|---|
| Temporal | orchestration | Durable workflows; per-item retry; the 7-day approval wait lives here, not in a process |
| LangGraph | extraction | Stateless pipeline invoked from one activity; schema-validated output before anything executes |
| MCP 2.x | Task Ledger | The ledger is a real MCP server — tools dispatch through `call_tool`, and it can run standalone over stdio |
| Alembic | schema | Versioned migrations; the app refuses to boot on an unmigrated database |
| Embeddings | routing memory | Gemini or OpenAI vectors, cosine similarity over your decision history; keyword matching when no key is set |

The extractor uses Google Gemini or OpenAI when a key is configured and a
deterministic local parser otherwise, so the full flow works on a fresh
clone with zero credentials — in that mode no text ever leaves the machine.

## Quick start

Requirements: Docker, Python 3.11+, Node 18+.

```bash
git clone <this repo> && cd kairos
./scripts/start.sh
```

The script starts PostgreSQL (5435), Temporal (7234, UI on 8234), applies
migrations, then launches the worker, the API on
[localhost:8000](http://localhost:8000) (docs at `/docs`), and the dashboard
on [localhost:3000](http://localhost:3000).

Open the dashboard, click a sample, press **Extract actions**, and approve
the items to watch them execute. With no tool credentials saved, enable
**Sandbox** in Settings first — otherwise the connectors correctly refuse
to make live calls.

To stop everything: the script traps Ctrl-C and tears down its processes;
`docker compose -f docker-compose.dev.yml down` stops the infrastructure.

## Configuration

Local settings live in `.env` (copy from `.env.example`). Anything saved in
the Settings UI is encrypted into PostgreSQL instead.

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | prod | Database password — never the dev default |
| `API_KEY` | prod | Operator key (≥16 chars) guarding every API route |
| `ENCRYPTION_KEY` | prod | 44-char Fernet key for the credential vault |
| `CORS_ORIGINS` | prod | Exact allowed origins for the published frontend |
| `TRUST_PROXY` | optional | `true` only behind a proxy that overwrites X-Forwarded-For (rate limiter then trusts its last entry) |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` | optional | Enables LLM extraction and semantic memory |
| `NOTION_API_KEY`, `JIRA_*`, `GOOGLE_CALENDAR_ACCESS_TOKEN` | optional | Live tool execution |
| `SANDBOX_MODE` | optional | `true` simulates all executions, no side effects |
| `LANGFUSE_*` | optional | Tracing to a Langfuse host |

Generate the two secrets:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
openssl rand -base64 24
```

In production the config rejects a missing API key, a reused dev encryption
key, or `DEBUG=true` at startup — the process refuses to boot rather than
run wide open.

## Testing

```bash
./scripts/test.sh
```

54 tests run against live PostgreSQL and Temporal: schema and payload
validation, MCP tool dispatch, idempotency deduplication, extraction and
prompt-injection defense, the routing-memory learning loop, workflow
lifecycle (approval signal, rejections, stale-signal protection, expiry),
the API surface, end-to-end integration, auth/rate-limit/CORS, connector
retry, secret redaction, and the batch-deletion guards. CI runs the same
suite plus frontend lint, typecheck, and build on every push.

## Production deployment

```bash
cp .env.example .env   # fill in the required secrets
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

The stack runs the API, worker, PostgreSQL, and Temporal on an internal
bridge network — only the frontend is published. A one-shot migrate
container applies `alembic upgrade head` and gates startup on success.
Missing required variables fail at compose interpolation, before anything
boots half-configured.

Both images are multi-stage, run as non-root users, and have healthchecks.
The frontend is a Next.js standalone build whose edge proxy injects the API
key server-side: browsers never hold it, and the backend is unreachable
from outside the Docker network.

## Deployment scope

Kairos is built for one operator. Confirm this matches your use before
going live:

- **One shared key.** Anyone who can reach the dashboard holds full rights:
  every batch, verdict, and side effect is visible to everyone, and the
  linked provider accounts are pooled.
- **One credential per provider.** The vault stores a single Notion, Jira,
  Calendar, and LLM connection. Individual visitors cannot attach their own.
- **One memory.** Suggestion quality is learned for the deployment as a
  whole, not per person.

Giving real users isolated sign-ins and per-user OAuth is a product change —
per-person flows, a `user_id` column through every table, per-person memory —
not a settings toggle. If that is the goal, plan it as a follow-on effort
built on this codebase rather than expecting configuration to get there.

## Repository layout

```
backend/
  app/api/        REST endpoints (batches, history, connectors)
  app/core/       auth, vault, rate limiting, logging, telemetry, redaction
  app/db/         models, sessions, pool policy
  app/mcp/        connectors, retry transport, Task Ledger MCP server
  app/pipelines/  LangGraph ingest/extract/route, routing memory
  app/temporal/   workflow, activities, worker
  alembic/        migrations
  tests/          the battle suite
frontend/         Next.js dashboard + server-side API proxy
scripts/          start.sh, test.sh
docker-compose.dev.yml    local infrastructure
docker-compose.prod.yml   production stack
.github/workflows/ci.yml  CI
```

## Security notes

- Connector and LLM credentials are AES-256-encrypted at rest; decryption
  happens in memory during approved executions only, and credential-shaped
  strings are stripped from error text before anything is logged.
- Submitted text is untrusted input: length-limited, wrapped in explicit
  delimiters, and parsed as data. An injected line in a transcript can at
  worst produce a suspicious-looking card for the operator to dismiss.
- Per-IP rate limits: 60 reads/min, 10 writes/min; health probes exempt.
- Exact-origin CORS, nosniff/DENY/HSTS headers, JSON logs, no stack traces
  in responses; `/docs` disabled in production.
- `DELETE /api/history/batches/{id}` erases a batch and its records;
  deleting a batch still mid-workflow returns 409 instead of corrupting
  state.

Found something sensitive? See [SECURITY.md](SECURITY.md) for how to report
it responsibly.

## Contributing

Bug reports and pull requests are welcome. The bar to clear: accompany
behavior changes with tests, write conventional commit messages, and argue
the case for any new dependency. Run `./scripts/test.sh` plus the frontend
checks locally; CI will run them again either way.

## License

MIT — [LICENSE](LICENSE). `PRIVACY.md` and `TERMS.md` adapt documents from
the [General Legal](https://github.com/General-Legal/legal-templates) library
(CC0); per that library's notice they are drafting starting points, not
counsel.
