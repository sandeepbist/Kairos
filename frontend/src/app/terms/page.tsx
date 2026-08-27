import React from "react";
import Link from "next/link";

export const metadata = {
  title: "Terms of Service — Kairos",
  description: "Terms of Service and Conditions of Use for Kairos Ambient Action Agent.",
};

export default function TermsPage() {
  return (
    <div className="container" style={{ maxWidth: "840px", paddingTop: "2rem", paddingBottom: "6rem" }}>
      <div style={{ marginBottom: "2.5rem" }}>
        <Link href="/" style={{ color: "var(--text-muted)", fontSize: "0.85rem", textDecoration: "none" }}>
          ← Back to Dashboard
        </Link>
        <h1 className="heading-display" style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>
          Terms of Service
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Last Updated: August 27, 2026 • Version 1.0.0
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "2rem", color: "var(--text-secondary)", lineHeight: 1.7, fontSize: "0.95rem" }}>
        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            1. Acceptance of Terms
          </h2>
          <p>
            By accessing, deploying, or utilizing the Kairos Ambient Action Agent software, APIs, or hosted dashboards (collectively, the &ldquo;Service&rdquo;), you agree to be bound by these Terms of Service (&ldquo;Terms&rdquo;). If you are using the Service on behalf of an organization, you represent and warrant that you have full legal authority to bind that entity to these Terms.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            2. Nature of the AI Ambient Agent & Human-in-the-Loop
          </h2>
          <p>
            Kairos is an autonomous action extraction and routing engine that parses unstructured text (e.g., transcripts, messages, emails) and converts candidate commitments into proposed tool side-effects.
          </p>
          <p style={{ marginTop: "0.75rem" }}>
            <strong>Human Verification Responsibility:</strong> Kairos incorporates a mandatory human-in-the-loop review workbench. The user retains ultimate responsibility for inspecting, approving, modifying, or rejecting proposed action items, tool destinations, and generated payloads prior to execution against live third-party systems.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            3. Third-Party Integrations & Model Context Protocol (MCP)
          </h2>
          <p>
            The Service connects to third-party platforms including Atlassian Jira, Notion, and Google Calendar via standard REST APIs and Model Context Protocol (MCP) servers. Your use of such external services is governed by their respective terms of service. You are responsible for ensuring that credentials and OAuth tokens supplied to the Service have appropriate permissions.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            4. Security & Credential Vault
          </h2>
          <p>
            All OAuth tokens and API secrets stored within the Service are encrypted at rest using AES-256 Fernet cryptographic keys. You are responsible for maintaining the confidentiality of your environment keys and preventing unauthorized access to your deployed instances.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            5. Limitation of Liability & Warranty Disclaimer
          </h2>
          <p>
            THE SERVICE IS PROVIDED &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
          </p>
        </section>

        <section className="card-panel" style={{ padding: "1.75rem" }}>
          <h2 style={{ color: "#ffffff", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.75rem" }}>
            6. Open Source License
          </h2>
          <p>
            Core components of Kairos are licensed under the MIT License. You are free to inspect, modify, fork, and self-host the repository in accordance with the license conditions specified in the project repository.
          </p>
        </section>
      </div>
    </div>
  );
}
