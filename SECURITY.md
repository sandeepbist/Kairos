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
