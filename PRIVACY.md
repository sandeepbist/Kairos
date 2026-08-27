# Privacy Policy

**Last Updated**: August 27, 2026 • **Version**: 1.0.0

## 1. Zero Data Sale Commitment
Kairos does not sell, rent, monetize, or broker personal data, conversation transcripts, meeting recordings, or action items to third parties or data brokers.

## 2. Categories of Data Processed
- **Unstructured Source Content**: Transcripts, meeting notes, emails, and conversation threads submitted for extraction.
- **Candidate Metadata**: Task descriptions, speaker attributions, assignees, verbatim provenance quotes, and target tool destinations.
- **Execution Audit Logs**: Cryptographic SHA256 hashes, timestamps, external object URLs, and execution latencies.
- **Encrypted Token Vault**: AES-256 Fernet encrypted OAuth access and refresh tokens stored in PostgreSQL.

## 3. AI & LLM Processing Hygiene
- Input text is guarded with prompt injection defense tags (`<untrusted_source_content>`).
- Data sent to Google Gemini or OpenAI LLM inference endpoints is transmitted over TLS and processed transiently for structured output generation.

## 4. Retention & Automated Archiving
- Batches awaiting approval auto-expire after 7 days via Temporal durable workflow policies.
- In self-hosted instances, operators retain full administrative control to purge batches and audit logs at will.

## 5. Compliance & Rights
Users in the EEA, UK, and California maintain rights under GDPR and CCPA regarding access and erasure of personal data within deployed instances.
