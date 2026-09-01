# Security policy

## Supported versions

The `main` branch receives security fixes. Releases are cut from it; patch
the latest release.

## Reporting a vulnerability

Email `[SECURITY EMAIL]` with details, reproduction steps, and impact. Do
not open a public issue for anything security-sensitive.

You will get an acknowledgment within 72 hours. We will keep you informed
of the fix timeline and credit you in the advisory unless you prefer
otherwise. Please avoid public disclosure until a fix is released.

## Scope

These apply to code in this repository when deployed as documented:

- Authentication bypass, key disclosure, or privilege escalation beyond the
  single-operator model.
- Injection into the extraction pipeline that could alter an approved
  payload between review and execution.
- Credential exposure — vault encryption, log leakage, or proxy header
  handling.
- Idempotency or deduplication weaknesses that could cause duplicate side
  effects on retry.

Out of scope: misconfigured deployments (exposed ports, weak operator
keys, missing TLS at your edge), vulnerabilities in the connected
third-party services themselves, and the single-operator design being
single-operator.

## What the codebase already does

The reference deployment keeps the API on a private Docker network, rate
limits per IP, compares keys in constant time, encrypts credentials with
AES-256, redacts secrets from error text, and validates every extraction
against a schema before execution. `SANDBOX_MODE=true` disables live side
effects entirely for safe testing.

Defense details worth knowing before deploying:

- **Uvicorn and X-Forwarded-For.** Uvicorn (>= 0.46) rewrites
  `request.client` from client-supplied `X-Forwarded-For` when the socket
  peer is loopback, and its default trusted-hosts list includes loopback —
  which once let an attacker mint unlimited rate-limit identities by
  rotating that header. The API is therefore launched with
  `--no-proxy-headers` everywhere (Dockerfile, start.sh), and the limiter
  additionally keys on the raw socket peer unless `TRUST_PROXY=true`, in
  which case only the *last* XFF entry (the one your own proxy appended)
  is used.
- **Request size caps.** Bodies over 1 MB return 413 at the middleware
  edge; `raw_text` is capped at 50,000 characters, approval payloads at
  200 decisions, and saved credentials at 8,192 characters — all enforced
  at schema validation, before storage or workflow dispatch. Ingest
  rejects unknown fields outright (`extra="forbid"`).
- **Signal integrity.** Approval decisions referencing item IDs that are
  not part of the batch's extracted items are skipped by the workflow —
  a forged or stale signal cannot execute anything.
- **SQL injection surface.** All database access goes through
  parameterized SQLAlchemy queries; path parameters are treated as opaque
  IDs (probe strings simply 404).
- **XSS.** Extracted items and source snippets are user-controlled and
  render through React's text escaping — verified with live payloads
  (`<script>`, `onerror`, `svg onload`) which appear as inert text, never
  as elements.
