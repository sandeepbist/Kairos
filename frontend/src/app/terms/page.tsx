import React from "react";
import Link from "next/link";

export const metadata = {
  title: "Terms of Service — Kairos",
  description: "Comprehensive Terms of Service and Master Subscription Agreement for Kairos Ambient Action Agent.",
};

export default function TermsPage() {
  return (
    <div className="container" style={{ maxWidth: "920px", paddingTop: "2rem", paddingBottom: "8rem" }}>
      <div style={{ marginBottom: "2.5rem" }}>
        <Link href="/" style={{ color: "var(--text-muted)", fontSize: "0.85rem", textDecoration: "none" }}>
          ← Back to Dashboard
        </Link>
        <h1 className="heading-display" style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>
          Terms of Service
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Effective Date: August 27, 2026 • Master Subscription & License Agreement (Version 2.4)
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
            1. Introduction & Acceptance of Terms
          </h2>
          <p>
            These Terms of Service (&ldquo;Terms&rdquo;, &ldquo;Agreement&rdquo;) constitute a legally binding agreement between you (whether an individual or legal entity, &ldquo;Customer&rdquo;, &ldquo;User&rdquo;, or &ldquo;You&rdquo;) and Kairos Systems Inc. (&ldquo;Kairos&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;, or &ldquo;our&rdquo;), governing your access to and use of the Kairos Ambient Action Agent software, backend orchestration microservices, web dashboards, CLI tools, and Model Context Protocol (MCP) bridges (collectively, the &ldquo;Service&rdquo;).
          </p>
          <p style={{ marginTop: "0.75rem" }}>
            BY INSTALLING, DEPLOYING, ACCESSING, OR CLICKING &ldquo;APPROVE&rdquo;, YOU EXPRESSLY ACKNOWLEDGE AND AGREE TO BE BOUND BY ALL PROVISIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT ACCESS OR USE THE SERVICE.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            2. Architectural Overview & Nature of the Ambient Action Agent
          </h2>
          <p>
            Kairos utilizes advanced Large Language Model (LLM) pipelines, LangGraph state graphs, and Temporal durable workflow orchestration to parse unstructured text inputs (including meeting transcripts, emails, customer tickets, and team chat transcripts), identify prospective action items, calculate routing confidence scores, and format tool-specific payloads.
          </p>
          <p style={{ marginTop: "0.75rem" }}>
            <strong>Autonomous Ingestion vs. Execution:</strong> While extraction, candidate scoring, and routing reasoning are autonomous, side-effect execution against external target systems is strictly contingent upon operator verification in accordance with Section 3 below.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            3. Mandatory Human-in-the-Loop (HITL) Verification & Operator Liability
          </h2>
          <p>
            The Service implements a Human-in-the-Loop review workbench designed to prevent unintended side-effects across connected production environments.
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>
              <strong>Verification Obligation:</strong> You acknowledge that generative AI models may occasionally produce hallucinations, misinterpret multi-speaker nuance, or assign suboptimal parameters. You assume sole operational and legal responsibility for reviewing, modifying, approving, or rejecting every extracted action item.
            </li>
            <li>
              <strong>Execution Authorization:</strong> Clicking &ldquo;Execute&rdquo; or submitting an approval signal constitutes your explicit, irrevocable authorization for the Service to transmit the finalized payload to the designated connector (e.g., Atlassian Jira, Notion, Google Calendar, or Task Ledger).
            </li>
            <li>
              <strong>Waiver of Downstream Claims:</strong> Kairos shall not be liable for any consequences, data corruption, unauthorized issue creation, calendar scheduling conflicts, or operational disruptions arising from approved actions.
            </li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            4. Third-Party Integrations & Model Context Protocol (MCP) Connectors
          </h2>
          <p>
            The Service interfaces with third-party software platforms using official APIs and Model Context Protocol servers. You acknowledge and agree that:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>You must hold valid, active accounts in good standing with each connected third-party service provider.</li>
            <li>Your use of third-party platforms remains subject to Atlassian&rsquo;s, Notion Labs&rsquo;, and Google LLC&rsquo;s independent terms of service and acceptable use policies.</li>
            <li>Kairos does not control, and is not responsible for, rate limiting, service downtime, API deprecations, or modifications imposed by third-party providers.</li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            5. OAuth Credential Vault & Cryptographic Key Management
          </h2>
          <p>
            All access tokens, refresh tokens, and API credentials provided to the Service are stored in an internal PostgreSQL database encrypted at rest using AES-256 Fernet symmetric encryption.
          </p>
          <p style={{ marginTop: "0.75rem" }}>
            <strong>Operator Key Custody:</strong> In self-hosted or dedicated deployments, you are solely responsible for generating, safeguarding, and backing up your master encryption key (<code style={{ color: "#38bdf8" }}>ENCRYPTION_KEY</code>). Loss of the encryption key will render stored OAuth credentials irrecoverable.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            6. Acceptable Use & Prompt Injection Defense
          </h2>
          <p>
            You agree not to use the Service to:
          </p>
          <ul style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "0.75rem" }}>
            <li>Transmit malicious payloads, exploit prompt injection vulnerabilities, or attempt to bypass system security boundaries.</li>
            <li>Process classified, military, or regulated health data without appropriate Business Associate Agreements (BAA) in place.</li>
            <li>Engage in automated harassment, spam generation, or unauthorized scraping.</li>
            <li>Reverse-engineer or decompile proprietary runtime libraries except to the extent permitted by applicable open-source licenses.</li>
          </ul>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            7. Intellectual Property & Customer Data Ownership
          </h2>
          <p>
            <strong>Your Data:</strong> As between you and Kairos, you retain all right, title, and interest in and to all text inputs, transcripts, and custom action configurations (&ldquo;Customer Data&rdquo;). We claim zero ownership over your raw content or extracted deliverables.
          </p>
          <p style={{ marginTop: "0.75rem" }}>
            <strong>Software & Open Source License:</strong> Kairos open-source components are distributed under the MIT License. All rights not expressly granted are reserved.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            8. Disclaimer of Warranties
          </h2>
          <p style={{ textTransform: "uppercase", fontSize: "0.85rem", letterSpacing: "0.02em", color: "var(--text-muted)" }}>
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE SERVICE IS PROVIDED &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo;, WITH ALL FAULTS AND WITHOUT WARRANTY OF ANY KIND. KAIROS DISCLAIMS ALL WARRANTIES, EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING WITHOUT LIMITATION WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            9. Limitation of Liability
          </h2>
          <p style={{ textTransform: "uppercase", fontSize: "0.85rem", letterSpacing: "0.02em", color: "var(--text-muted)" }}>
            IN NO EVENT SHALL KAIROS, ITS OFFICERS, DIRECTORS, EMPLOYEES, OR AFFILIATES BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES (INCLUDING LOSS OF PROFITS, DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES) ARISING OUT OF OR RELATING TO YOUR ACCESS TO OR USE OF THE SERVICE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            10. Indemnification
          </h2>
          <p>
            You agree to defend, indemnify, and hold harmless Kairos and its directors, officers, and employees from and against any third-party claims, liabilities, damages, losses, and expenses (including reasonable attorneys&rsquo; fees) arising out of or related to your Customer Data, your violation of these Terms, or your approved side-effects dispatched to external tools.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            11. Governing Law & Dispute Resolution
          </h2>
          <p>
            These Terms shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of law principles. Any dispute arising out of or in connection with these Terms shall be resolved exclusively through binding arbitration administered by the American Arbitration Association (AAA) under its Commercial Arbitration Rules.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "2rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            12. Modifications to Terms & Service
          </h2>
          <p>
            We reserve the right to modify these Terms at any time by posting an updated version with a revised &ldquo;Effective Date&rdquo;. Continued use of the Service following any update constitutes your acceptance of the amended Terms.
          </p>
        </section>
      </div>
    </div>
  );
}
