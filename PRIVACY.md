# Privacy Policy

**Effective Date**: August 27, 2026 • **Enterprise Data Protection & Security Policy** (Version 2.4)

## 1. Core Privacy Commitment & Zero Data Sale
Kairos is architected with a strict privacy-by-design standard.
**WE NEVER SELL, RENT, MONETIZE, OR SHARE YOUR RAW TRANSCRIPTS, AUDIO, EXTRACTED ACTIONS, OR OAUTH CREDENTIALS WITH DATA BROKERS, THIRD-PARTY ADVERTISERS, OR UNAUTHORIZED COMMERCIAL ENTITIES.**

## 2. Categories of Information Processed
- **Unstructured Source Data**: Text transcripts, email threads, chat logs, or meeting notes submitted via API or frontend.
- **Extracted Action Metadata**: Task descriptions, speaker attributions, suggested assignees, verbatim provenance quotes, tool routing predictions, and confidence scores.
- **Human Decisions & Feedback**: Approval, modification, tool override, and rejection signals used to calibrate local feedback memory.
- **Cryptographic Execution Logs**: Deterministic SHA-256 idempotency hashes, timestamps, tool identifiers, latencies, and returned external URLs.
- **Encrypted Authentication Secrets**: Third-party OAuth 2.1 access and refresh tokens encrypted with AES-256 Fernet symmetric keys.

## 3. AI & Large Language Model (LLM) Processing Hygiene
- **Prompt Injection Guardrails**: All source text is sanitized, length-checked (3,000 token maximum), and encapsulated inside structured XML delimiters (`<untrusted_source_content>`).
- **Transient Structured Inference**: Transcripts are transmitted over encrypted TLS 1.3 tunnels strictly for one-shot structured Pydantic extraction.
- **No Model Training on Customer Data**: Customer text processed via enterprise API endpoints is not used to train or refine public foundation models.

## 4. Cryptographic Token Vault & Data Storage Architecture
- **AES-256 Encryption at Rest**: OAuth tokens for Notion, Jira, and Google Calendar are stored in PostgreSQL using Fernet AES-256 CBC encryption with HMAC authentication.
- **Durable Orchestration**: Batch states and HITL signal queues are maintained securely by Temporal Server workflows.
- **Self-Hosted Isolation**: In self-hosted environments, all database records, vector tables, and logs remain strictly within your infrastructure perimeter.

## 5. Automated Data Lifecycle & Retention Policies
- **7-Day Auto-Archive Lifecycle**: Ingestion batches awaiting human verification that remain untouched for seven (7) consecutive days are automatically timed out and archived by Temporal workflow policies.
- **Operator Deletion Rights**: Operators may delete batches, action items, execution logs, or OAuth tokens at any time via standard API calls.

## 6. Sub-processors & Third-Party Service Providers
- **Atlassian Corporation**: Jira Cloud REST API v3 for ticket creation.
- **Notion Labs, Inc.**: Notion API v1 for workspace database page generation.
- **Google LLC**: Google Calendar API v3 for event scheduling & Google Generative AI for structured LLM inference.
- **OpenAI, L.L.C.**: OpenAI API for alternative structured extraction models.

## 7. Global Compliance: GDPR, UK GDPR, & CCPA/CPRA Rights
Users possess statutory rights regarding access, rectification, portability, and erasure ("Right to be Forgotten") of personal data processed by the Service.
