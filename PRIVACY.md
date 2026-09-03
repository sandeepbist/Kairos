# Privacy Policy

**Version 1.0 &middot; Effective date:** `[EFFECTIVE DATE]`

> **How to use this document.** Kairos is open-source, self-hosted software.
> When you deploy it, **you** become the data controller for the data it
> processes, and this policy becomes yours to publish. Replace every
> `[bracketed placeholder]` with your information before publishing, and
> remove any bracketed text that does not apply to your deployment. This
> document is adapted from the
> [General Legal](https://github.com/General-Legal/legal-templates) template
> library (CC0) and describes the data handling implemented in the Kairos
> codebase as of version 1.0. It is a template, not legal advice.

`[OPERATOR LEGAL NAME]` ("[SHORT NAME]", "**we**", "**us**", "**our**")
operates the Kairos dashboard and API located at `[DOMAIN]` (the
"**Service**"). The Service is a deployment of the Kairos Ambient Action
Engine: open-source software that converts unstructured conversations into
executed actions across connected tools.

This policy covers the people whose text and credentials are processed
through a Kairos deployment — typically the operator and any individuals
they invite to use it. Kairos is a single-operator system by design: one
shared API key, one set of connected tool credentials, and one shared batch
history. If you expose your deployment to other people, you are the
controller for their data, and this policy governs your handling of it.

## Index

- [Personal information we collect](#personal-information-we-collect)
- [How we use your personal information](#how-we-use-your-personal-information)
- [AI and LLM processing](#ai-and-llm-processing)
- [Cookies and tracking technologies](#cookies-and-tracking-technologies)
- [How we share your personal information](#how-we-share-your-personal-information)
- [Retention and deletion](#retention-and-deletion)
- [Security](#security)
- [International data transfer](#international-data-transfer)
- [Children](#children)
- [Your choices](#your-choices)
- [State privacy rights notice](#state-privacy-rights-notice)
- [Notice to European users](#notice-to-european-users)
- [Changes to this Privacy Policy](#changes-to-this-privacy-policy)
- [How to contact us](#how-to-contact-us)

---

# Personal information we collect

## Information you provide to us

The Service is built around text you deliberately submit, plus credentials
you deliberately connect. Depending on how the operator configures the
deployment, this includes:

1. **Source content.** The raw, unstructured text you paste or submit
   through the ingest screen or `POST /api/batches/ingest` — meeting
   transcripts, email threads, chat logs, or notes. Source content is stored
   verbatim in the `batches` table alongside the declared source type.
2. **Extracted action data.** When the extraction pipeline runs, it derives
   structured items from your source content and stores them in the
   `action_items` table: a task description, a suggested destination tool, a
   tool-specific payload, the verbatim source snippet each item was derived
   from, detected speaker labels and assignees, priority, due dates, and a
   confidence score.
3. **Decision and feedback data.** Every review decision you make — approve,
   modify-and-approve (including edited payloads and tool overrides),
   reject, and any rejection reason you type — is recorded. Approved and
   overridden routings are also written to the `routing_feedback` table with
   a numeric embedding vector of the item description, which the Service
   uses to learn routing preferences.
4. **Connector credentials.** OAuth tokens or API keys you save through
   the Settings screen for any connected destination — Notion; Jira and
   Confluence (Atlassian); Google Calendar, Gmail, and Google Tasks
   (Google); Linear; Todoist; GitHub; Asana; ClickUp; and Slack — and
   for LLM providers (Google Gemini, OpenAI). These are encrypted with
   AES-256 (Fernet, including HMAC integrity) before they are written to
   the `oauth_tokens` table, and are decrypted only in memory when an
   approved action executes.
5. **Contact data.** Any contact details you provide when communicating with
   the operator about the Service (for example, support email).

## Automatically collected information

The Service keeps a short technical record of requests to operate and
secure itself. No advertising or analytics identifiers are created or read:

1. **Request metadata.** The API applies per-IP rate limits (60 read and 10
   write requests per minute) using the client IP address. These are held
   only in process memory and are never persisted.
2. **Authentication events.** Requests presenting an invalid API key are
   logged with the request method and path — never the key itself.
3. **Execution telemetry.** Each executed action writes an `execution_logs`
   row: the target tool, outcome status, a deterministic SHA-256 idempotency
   hash derived from the batch ID, item ID, tool, and canonical payload,
   the external URL of the created object, latency in milliseconds, and any
   error text (with credential-shaped strings redacted before storage).
4. **Workflow history.** The Temporal orchestration server persists
   workflow execution history — which activities ran, their inputs and
   outputs, and the approval signal with your decisions — for the lifetime
   of its data store. Self-hosted deployments keep this in the operator's
   own database volume.

## Information about other people

Source content you paste may contain other people's personal information —
names, email addresses, statements they made in meetings. It is processed
as part of your content, extracted into action items (for example, as an
assignee), and, if you approve an action, transmitted to the connected
tool you chose. Do not paste content containing other people's personal
information unless you have a lawful basis to process and, where relevant,
to share it with the destination tool.

# How we use your personal information

We use personal information to:

**Operate the Service.** Store your submitted content, run extraction and
routing, hold batches for your review, execute the actions you approve, and
maintain the audit trail the history screen shows.

**Learn your routing preferences.** Confirmations, overrides, and
rejections feed the routing memory so suggested destinations and confidence
scores improve over your use. This learning stays inside your deployment's
database.

**Secure the Service.** Enforce authentication, apply rate limits, reject
invalid credentials, and keep the execution and error records needed to
diagnose failures.

**Comply with law.** Respond to lawful requests and meet legal,
accounting, or reporting requirements where they apply to the operator.

We do not use personal information for advertising, profiling, or
behavioral tracking. The Service contains no analytics, no advertising
integrations, and no third-party scripts on its pages.

# AI and LLM processing

When the operator configures an LLM provider key (Google Gemini or OpenAI),
submitted source content is transmitted to that provider's API over TLS for
one-shot structured extraction: the text is length-limited, wrapped in
explicit untrusted-content delimiters, and sent as data to be parsed —
never as instructions to the service. The provider's API terms govern
their processing; Google and OpenAI enterprise API terms state submitted
content is not used to train public models. When no LLM key is configured,
extraction runs entirely inside the deployment using a deterministic local
parser, and no text leaves the server.

The routing memory's embedding vectors are produced by the configured
provider's embedding endpoint and stored locally. They are numeric and are
never transmitted back to the provider.

# Cookies and tracking technologies

**The Service sets no cookies.** There are no login sessions, no analytics
cookies, no advertising cookies, no pixels, no web beacons, and no session
replay. Authentication uses an API key passed as a request header through
the dashboard's server-side proxy; nothing is stored in your browser. The
dashboard loads its fonts from the deployment itself and makes no requests
to third-party font or script CDNs. "Do Not Track" browser signals are moot
for this reason; the Service does not otherwise respond to them.

# How we share your personal information

We do not sell, rent, or share personal information with data brokers,
advertisers, or analytics vendors. The Service shares data only in these
ways:

1. **Tool connectors you approve.** When you approve an action, the Service
   transmits that item's payload to the destination you chose: a Jira issue
   to Atlassian, a page to Notion, an event to Google Calendar, or a task to
   the internal Task Ledger (which stays inside your database). Only the
   approved item is transmitted — never the whole transcript.
2. **LLM providers, when configured.** Source content sent for extraction,
   as described in the AI and LLM processing section.
3. **Langfuse, when configured.** If the operator sets Langfuse keys, trace
   metadata (batch ID, event names, latencies, token counts) is sent to the
   configured Langfuse host. Submitted source text is not included.
4. **Professional advisors and authorities.** Where the operator is required
   to share information with lawyers, auditors, regulators, or law
   enforcement, or to protect rights, safety, and property.
5. **Business transfers.** In connection with a merger, acquisition, or
   sale of the operator's assets, information may be transferred as a
   business asset, subject to this policy.

# Retention and deletion

- **Submitted batches and their items** persist until deleted. Batches that
  reach `awaiting_approval` and receive no decision are automatically
  expired after 7 days by the Temporal workflow and retained in an archived
  state.
- **Deletion is available at any time.** `DELETE /api/history/batches/{id}`
  erases a batch and its action items and execution logs. Connector
  credentials can be removed from Settings via the Disconnect control.
  Routing feedback rows contain no source text and are retained for the
  learning loop; operators who want them removed can truncate the
  `routing_feedback` table directly.
- **Credential removal.** Disconnecting a provider deletes the encrypted
  token row. Rotating the deployment's Fernet key without preserving the
  old key renders any remaining tokens unreadable.
- Backups are the operator's responsibility; deletion propagates to backups
  per the operator's backup schedule.

# Security

The Service implements the following safeguards, and the operator is
responsible for the infrastructure around them:

- OAuth and LLM credentials are encrypted at rest with AES-256 (Fernet) and
  decrypted only in memory during approved executions.
- Every API route except the health probe requires an operator API key,
  compared in constant time. In the reference production deployment the
  backend is unreachable from outside the private container network; the
  frontend proxy injects the key server-side so browsers never hold it.
- Error text is scrubbed of credential-shaped strings before logging.
- Rate limiting, strict CORS, security headers, and JSON structured logging
  are enabled by default. Production mode refuses to start without a real
  API key and a fresh encryption key, and disables the public API docs.
- The operator must keep their `ENCRYPTION_KEY` and `API_KEY` secret, apply
  OS and container updates, and secure the host.

Security risk is inherent in all internet and information technologies, and
no system can be guaranteed secure.

# International data transfer

The Service runs entirely on infrastructure the operator chooses, in the
region the operator chooses. Cross-border transfer occurs only through the
sub-processors the operator configures — for example, Google, OpenAI,
Atlassian, Notion, Linear, Todoist, GitHub, Asana, ClickUp, Slack, or
Langfuse endpoints — and those providers' locations
and transfer mechanisms apply. See the
[Notice to European users](#notice-to-european-users) for GDPR transfer
details.

# Children

The Service is not directed at children and is not intended for use by
anyone under 18. The operator should not knowingly collect personal
information from children through the Service.

# Your choices

- **Review before execution.** Nothing executes without an explicit human
  approval; the review screen shows the verbatim source behind every
  proposed action.
- **Delete batches.** Call `DELETE /api/history/batches/{id}` or ask the
  operator to.
- **Disconnect tools.** The Disconnect control removes a stored credential
  immediately.
- **Run sandbox mode.** The operator can set `SANDBOX_MODE=true`, which
  simulates all tool executions: no external requests, no side effects.
- **Run keyless.** With no LLM keys configured, text never leaves the
  deployment.
- **Declining to provide information.** The Service cannot extract actions
  from text you do not submit; connector credentials are optional per tool.

# State privacy rights notice

This section applies to residents of U.S. states with comprehensive privacy
laws (collectively, the "**State Privacy Laws**") — as of early 2026,
California (CCPA/CPRA), Colorado, Connecticut, Virginia, Texas, Oregon,
Montana, Utah, Iowa, Indiana, Tennessee, and others. Where the operator is
the controller, these rights are exercised against the operator.

Depending on the State Privacy Law that applies to you, you may have some
or all of the following rights. These rights are not absolute; we may
decline requests as permitted by law, and we may need reasonable
information to verify your identity and request.

- **Information.** The categories of personal information collected, the
  sources, the business purposes, and the categories of third parties with
  which it is shared.
- **Access.** A copy of the personal information collected about you.
- **Correction.** Correction of inaccurate personal information.
- **Deletion.** Deletion of personal information collected from you.
- **Opt-out of targeted advertising, sale, or profiling.** We do not sell
  personal information, do not share it for targeted advertising, and do not
  engage in profiling or automated decision-making that produces legal or
  similarly significant effects. There is nothing to opt out of.
- **Nondiscrimination.** Exercising these rights must not result in
  discrimination against you.

**Categories we collect and disclose.** During the 12 months preceding this
policy's effective date, a typical deployment collected:

| Category (Kairos term) | Example fields | Purpose | Disclosed to |
| --- | --- | --- | --- |
| Source content | raw pasted text, source type | extraction, review, audit | LLM provider (if configured); destination tool (only the approved item) |
| Extracted action data | description, tool, payload, snippet, speaker, assignee, priority, confidence | routing, execution | destination tool (only the approved item) |
| Decision and feedback data | decisions, rejection reasons, embeddings | routing-memory learning | no one outside the deployment |
| Connector credentials | provider tokens | executing approved actions | the provider itself, when its token is used |
| Execution telemetry | tool, status, SHA-256 hash, URL, latency | audit trail, deduplication | no one outside the deployment |
| Request metadata | IP address (memory only), path | rate limiting, security | no one |

We do not sell any category, and we do not disclose categories for targeted
advertising.

**California residents.** Under the CCPA (as amended by the CPRA), California
residents may also request the information described above and may bring
complaints to the Complaint Assistance Unit of the California Department of
Consumer Affairs. California's "Shine the Light" law requests may be sent
to `[PRIVACY EMAIL]` with "Shine the Light Request" in the subject, the
requester's name and mailing address, and certification of California
residency.

**Nevada residents.** Nevada law grants a right to opt out of sales of
personal information for monetary consideration. We do not make such sales;
if that ever changes, opt-out requests may be sent to `[PRIVACY EMAIL]`.

**Verification and authorized agents.** To process a request we may need to
verify identity (matching the request to the deployment's records), confirm
state residency, and, where an authorized agent submits on your behalf,
verify the agent's authority. We will respond within the timeframes State
Privacy Laws require.

# Notice to European users

This section applies to individuals in the European Economic Area and the
United Kingdom ("Europe"). "Personal information" in this policy includes
"personal data" as defined in the GDPR and UK GDPR.

## Controller

For a self-hosted deployment, the operator — `[OPERATOR LEGAL NAME,
ADDRESS]` — is the controller of personal data processed by the Service.
Contact: `[PRIVACY EMAIL]`.

## Legal bases for processing

| Purpose | Categories involved | Legal basis |
| --- | --- | --- |
| Providing the Service (storage, extraction, review, execution, audit) | Source content, extracted action data, decision data, execution telemetry | Performance of a contract with you, or your consent where no contract exists |
| Learning routing preferences | Decision and feedback data, embeddings | Legitimate interests in providing a service that improves with use; the data stays in your deployment |
| Security, abuse prevention, rate limiting | Request metadata, authentication events, execution telemetry | Legitimate interests in securing the Service; compliance with law |
| Transmitting approved items to connected tools | Extracted action data (the approved item) | Performance of the contract; your explicit instruction when you approve the action |
| LLM extraction when a provider key is configured | Source content | Your consent, revocable by running keyless |
| Connector credential storage | Credentials | Necessary for performance of the contract at your instruction; encrypted at rest |
| Compliance and legal requests | Any, as lawfully required | Compliance with a legal obligation |
| Langfuse tracing when configured | Trace metadata | Legitimate interests in operating and debugging the Service |

**No automated decision-making with legal effect.** The Service only
proposes actions; a human approves or rejects every one. It does not profile
users.

**Special category data.** Please do not submit special category data
(health, biometrics, race or ethnic origin, political opinions, religion,
trade union membership, criminal history) through the Service. If you do,
you consent to its processing as described, but the Service has no features
designed for its safe handling.

## Your GDPR rights

If you are located in Europe, you may ask us to:

1. **Access** — provide information about our processing and a copy of your
   personal data.
2. **Rectify** — correct inaccurate personal data.
3. **Erase** — delete your personal data; batch deletion via the API
   implements this directly.
4. **Restrict** — restrict processing while accuracy or basis is contested.
5. **Portability** — receive a machine-readable copy of your data; the
   batch and history API endpoints return it as JSON.
6. **Object** — object to processing based on legitimate interests,
   including the routing-memory learning; the operator can disable memory
   embeddings or truncate the feedback table.
7. **Withdraw consent** — for consent-based processing (LLM extraction),
   withdraw at any time; running keyless stops it.

Submit requests to `[PRIVACY EMAIL]`. We may request specific information
to confirm identity. If we reject a request, we will explain the grounds,
subject to legal restrictions. You also have the right to lodge a complaint
with your national data protection authority (the EDPB website lists them;
in the UK, the Information Commissioner's Office).

## Transfers outside Europe

Personal data is processed where the operator hosts the deployment. Where
configured sub-processors (Google, OpenAI, Atlassian, Notion, Linear,
Todoist, GitHub, Asana, ClickUp, Slack, Langfuse) are
located outside Europe or make transfers to it, the operator relies on the
provider's transfer mechanisms — adequacy decisions or Standard Contractual
Clauses — and can supply details on request. The GDPR does not consider
the United States adequate by default, so U.S.-based providers require
such safeguards.

# Changes to this Privacy Policy

We may modify this policy from time to time. Material changes will be
signaled by updating the effective date and posting the revised policy on
the Service. Continued use after the effective date acknowledges the
revised policy. Prior versions are available in the project's source
repository.

# How to contact us

- **Email:** `[PRIVACY EMAIL]`
- **Mail:** `[OPERATOR POSTAL ADDRESS]`
- **Repository issues (non-sensitive matters):** `[REPO URL]`

Do not send credentials or sensitive personal information through these
channels.
