import React from "react";
import Link from "next/link";

export const metadata = {
  title: "Privacy Policy — Kairos",
  description: "Comprehensive Privacy Policy, Data Governance, and Security Standards for Kairos Ambient Action Agent.",
};

export default function PrivacyPage() {
  return (
    <div className="container" style={{ maxWidth: "920px", paddingTop: "2rem", paddingBottom: "8rem" }}>
      <div style={{ marginBottom: "2.5rem" }}>
        <Link href="/" style={{ color: "var(--text-muted)", fontSize: "0.85rem", textDecoration: "none" }}>
          ← Back to Dashboard
        </Link>
        <h1 className="heading-display" style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>
          Privacy Policy
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Effective Date: August 27, 2026 • Enterprise Data Protection & Security Policy (Version 2.4)
        </p>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "2.25rem",
          color: "var(--text-secondary)",
          lineHeight: 1.75,
          fontSize: "0.95rem",
        }}
      >
        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            1. Core Privacy Commitment & Zero Data Sale
          </h2>
          <p>
            At Kairos (&ldquo;we&rdquo;, &ldquo;us&rdquo;, or &ldquo;our&rdquo;), we believe that enterprise productivity software must adhere to the highest standards of data confidentiality and privacy-by-design.
          </p>
          <p style={{ marginTop: "0.75rem" }}>
            <strong>WE NEVER SELL, RENT, MONETIZE, OR SHARE YOUR RAW TRANSCRIPTS, AUDIO, EXTRACTED ACTIONS, OR OAUTH CREDENTIALS WITH DATA BROKERS, THIRD-PARTY ADVERTISERS, OR UNAUTHORIZED COMMERCIAL ENTITIES.</strong>
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            2. Scope & Categories of Information Processed
          </h2>
          <p>
            The Service processes information strictly necessary to fulfill action extraction, human verification, and tool dispatch workflows:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>
              <strong>Unstructured Source Data:</strong> Text transcripts, email threads, chat logs, or meeting notes submitted via the API or frontend for reasoning and parsing.
            </li>
            <li>
              <strong>Extracted Action Metadata:</strong> Task descriptions, identified speaker attributions, suggested assignees, verbatim provenance quotes, tool routing predictions, and confidence scores.
            </li>
            <li>
              <strong>Human Decisions & Feedback:</strong> Approval, modification, tool override, and rejection signals used to calibrate the local Mem0 feedback memory loop.
            </li>
            <li>
              <strong>Cryptographic Execution Logs:</strong> Deterministic SHA-256 idempotency hashes, timestamps, tool identifiers, execution latencies in milliseconds, and returned external object URLs.
            </li>
            <li>
              <strong>Encrypted Authentication Secrets:</strong> Third-party OAuth 2.1 access and refresh tokens encrypted with AES-256 Fernet symmetric keys.
            </li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            3. AI & Large Language Model (LLM) Processing Hygiene
          </h2>
          <p>
            When processing source content through foundation models (including Google Gemini and OpenAI):
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>
              <strong>Prompt Injection Guardrails:</strong> All source text is sanitized, length-checked (3,000 token maximum), and encapsulated inside structured XML delimiters (<code style={{ color: "#38bdf8" }}>&lt;untrusted_source_content&gt;</code>) to prevent prompt injection or instruction hijacking.
            </li>
            <li>
              <strong>Transient Structured Inference:</strong> Transcripts are transmitted over encrypted TLS 1.3 tunnels strictly for one-shot structured Pydantic extraction.
            </li>
            <li>
              <strong>No Model Training on Customer Data:</strong> Customer text processed via standard enterprise API endpoints is not used to train or refine public foundation models.
            </li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            4. Cryptographic Token Vault & Data Storage Architecture
          </h2>
          <p>
            All persistent data is managed within isolated database layers:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>
              <strong>AES-256 Encryption at Rest:</strong> OAuth tokens for Notion, Jira, and Google Calendar are stored in PostgreSQL using Fernet AES-256 CBC encryption with HMAC authentication.
            </li>
            <li>
              <strong>Durable Orchestration:</strong> Batch states and HITL signal queues are maintained securely by Temporal Server workflows.
            </li>
            <li>
              <strong>Self-Hosted Isolation:</strong> In self-hosted environments, all database records, vector tables, and logs remain strictly within your infrastructure perimeter.
            </li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            5. Automated Data Lifecycle & Retention Policies
          </h2>
          <p>
            To prevent stale data accumulation:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>
              <strong>7-Day Auto-Archive Lifecycle:</strong> Ingestion batches awaiting human verification that remain untouched for seven (7) consecutive days are automatically timed out and archived by Temporal workflow policies.
            </li>
            <li>
              <strong>Operator Deletion Rights:</strong> Operators and administrative users may delete batches, action items, execution logs, or OAuth tokens at any time via standard API calls or direct database management.
            </li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            6. Sub-processors & Third-Party Service Providers
          </h2>
          <p>
            Depending on your deployment mode and configured credentials, the Service may transmit data to the following service providers:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li><strong>Atlassian Corporation:</strong> Jira Cloud REST API v3 for ticket creation.</li>
            <li><strong>Notion Labs, Inc.:</strong> Notion API v1 for workspace database page generation.</li>
            <li><strong>Google LLC:</strong> Google Calendar API v3 for event scheduling & Google Generative AI for structured LLM inference.</li>
            <li><strong>OpenAI, L.L.C.:</strong> OpenAI API for alternative structured extraction models.</li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            7. Global Compliance: GDPR, UK GDPR, & CCPA/CPRA Rights
          </h2>
          <p>
            If you reside in the European Economic Area (EEA), United Kingdom, or California, you possess statutory rights regarding your personal data, including:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li><strong>Right to Access & Portability:</strong> The right to request copies of your stored data and execution logs.</li>
            <li><strong>Right to Rectification:</strong> The right to correct inaccurate or incomplete metadata.</li>
            <li><strong>Right to Erasure (&ldquo;Right to be Forgotten&rdquo;):</strong> The right to request full purging of your batches and cryptographic audit trails.</li>
            <li><strong>Right to Restrict Processing:</strong> The right to toggle Sandbox Mode to prevent live external network transmissions.</li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            8. Security Measures & Incident Notification
          </h2>
          <p>
            We implement comprehensive technical and organizational safeguards including encrypted data transmission (TLS 1.3), database field encryption, strict CORS controls, and isolated Docker container networks. In the event of a security breach affecting stored customer credentials, affected operators will be notified in accordance with applicable legal requirements.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            9. Changes to this Privacy Policy
          </h2>
          <p>
            We may periodically revise this Privacy Policy to reflect architectural updates or legal developments. Changes become effective upon posting with the updated &ldquo;Effective Date&rdquo; at the top of this document.
          </p>
        </section>
      </div>
    </div>
  );
}
