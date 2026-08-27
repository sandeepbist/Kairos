import React from "react";
import Link from "next/link";

export const metadata = {
  title: "Privacy Policy — Kairos",
  description: "Privacy Policy and Data Protection Practices for Kairos Ambient Action Agent.",
};

export default function PrivacyPage() {
  return (
    <div className="container" style={{ maxWidth: "840px", paddingTop: "2rem", paddingBottom: "6rem" }}>
      <div style={{ marginBottom: "2.5rem" }}>
        <Link href="/" style={{ color: "var(--text-muted)", fontSize: "0.85rem", textDecoration: "none" }}>
          ← Back to Dashboard
        </Link>
        <h1 className="heading-display" style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>
          Privacy Policy
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Last Updated: August 27, 2026 • Version 1.0.0
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "2rem", color: "var(--text-secondary)", lineHeight: 1.7, fontSize: "0.95rem" }}>
        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            1. Core Privacy Philosophy & Zero Data Sale
          </h2>
          <p>
            Kairos is architected with a strict privacy-by-design standard. We do not sell, rent, monetize, or broker your personal data, transcripts, meeting recordings, or action items to any third parties or advertisers under any circumstances.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            2. Data We Process
          </h2>
          <ul style={{ paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <li>
              <strong>Unstructured Input Text:</strong> Text submitted via the ingestion workbench or API (transcripts, emails, conversation threads) processed strictly for action extraction.
            </li>
            <li>
              <strong>Extracted Candidate Metadata:</strong> Action descriptions, speaker attributions, suggested assignees, verbatim provenance snippets, and target tool destinations.
            </li>
            <li>
              <strong>Execution Audit Logs:</strong> Cryptographic idempotency hashes, timestamps, external object URLs, execution latency, and error responses.
            </li>
            <li>
              <strong>Encrypted Credentials:</strong> OAuth 2.1 access and refresh tokens encrypted with AES-256 Fernet keys stored in PostgreSQL.
            </li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            3. AI & LLM Processing Hygiene
          </h2>
          <p>
            When utilizing Google Gemini or OpenAI LLMs for extraction:
          </p>
          <ul style={{ paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.5rem" }}>
            <li>Input transcripts are wrapped in security guardrails (<code style={{ color: "#38bdf8" }}>&lt;untrusted_source_content&gt;</code>) to protect against prompt injection.</li>
            <li>Source text is processed transiently over encrypted TLS connections strictly for structured inference and is not used to train public foundation models when utilizing enterprise API keys.</li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            4. Data Retention & Deletion
          </h2>
          <p>
            Batches awaiting approval are subject to an automated 7-day auto-archive lifecycle managed by Temporal workflows. You maintain complete control over your self-hosted database instance and can purge batches, audit logs, or token vault records at any time.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            5. GDPR & CCPA Compliance
          </h2>
          <p>
            If you are located in the European Economic Area (EEA), the United Kingdom, or California, you have the right to access, rectify, or erase any personal data processed by the Service. In self-hosted deployments, data controller obligations reside with the deploying organization.
          </p>
        </section>
      </div>
    </div>
  );
}
