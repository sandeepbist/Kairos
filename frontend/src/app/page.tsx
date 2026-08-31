"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ingestBatch } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { SourceType } from "@/lib/types";

const SAMPLE_PRESETS = {
  meeting: {
    label: "Engineering sync",
    type: "meeting_transcript" as SourceType,
    text: `Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.
Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.
John: I will update the technical spec doc in the roadmap wiki and share it with leadership.
Sarah: Let's also make sure someone follows up on the billing invoices discrepancy.`,
  },
  incident: {
    label: "Incident review",
    type: "slack_conversation" as SourceType,
    text: `IncidentLead: Mark, please file an urgent Jira bug on the auth token expiration race condition.
DevOps: I will schedule a post-mortem sync call with the on-call team tomorrow at 10 AM.
Security: Please document the root cause analysis in Notion under the Incident Database.`,
  },
  email: {
    label: "Scope email",
    type: "email_thread" as SourceType,
    text: `From: product-lead@company.com
Subject: Q3 Architecture Deliverables

Hi Team,
1. Alex: Please prepare the RFC document for Model Context Protocol integration.
2. Sarah: Can you schedule a roadmap planning session with the stakeholders next Monday?
3. Task: Clean up all outdated deployment scripts before the freeze.`,
  },
  legal: {
    label: "Vendor notes",
    type: "general_notes" as SourceType,
    text: `Master Services Agreement Excerpt:
1. LegalCounsel: Alex, please file a Jira compliance audit ticket for the SOC2 Type II controls.
2. VendorManager: Sarah, please schedule a quarterly SLA compliance review call with the vendor for next Friday at 3 PM.
3. Operations: Please document the intellectual property assignment schedule in Notion under Corporate Legal Wiki.`,
  },
};

const SOURCE_LABELS: Record<SourceType, string> = {
  meeting_transcript: "Meeting transcript",
  slack_conversation: "Slack conversation",
  email_thread: "Email thread",
  general_notes: "General notes",
};

export default function IngestPage() {
  const router = useRouter();
  const [rawText, setRawText] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("meeting_transcript");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wordCount = rawText.trim() ? rawText.trim().split(/\s+/).length : 0;
  const approxTokens = Math.round(wordCount * 1.33);
  const overLimit = approxTokens > 3000;

  const handleLoadPreset = (key: keyof typeof SAMPLE_PRESETS) => {
    setRawText(SAMPLE_PRESETS[key].text);
    setSourceType(SAMPLE_PRESETS[key].type);
    setError(null);
  };

  const handleIngest = async () => {
    if (!rawText.trim() || rawText.length < 10) {
      setError("Enter at least 10 characters of conversation text.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await ingestBatch(rawText, sourceType);
      router.push(`/review/${response.batch_id}`);
    } catch (err) {
      setError(errorMessage(err, "Failed to submit batch. Verify the backend is reachable."));
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "760px" }}>
      {/* Header */}
      <div className="rise" style={{ marginBottom: "40px" }}>
        <p className="eyebrow" style={{ marginBottom: "14px" }}>
          AMBIENT ACTION ENGINE
        </p>
        <h1 className="h-display" style={{ marginBottom: "14px" }}>
          Conversations in.
          <br />
          Actions out.
        </h1>
        <p className="muted" style={{ fontSize: "0.95rem", maxWidth: "480px" }}>
          Paste a transcript, thread, or note. Kairos extracts the commitments,
          routes each to the right tool, and executes — after your approval.
        </p>
      </div>

      {/* Templates + format */}
      <div
        className="rise rise-1"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          flexWrap: "wrap",
          marginBottom: "14px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span className="mono-label" style={{ marginRight: "2px" }}>
            SAMPLES
          </span>
          {(Object.keys(SAMPLE_PRESETS) as Array<keyof typeof SAMPLE_PRESETS>).map((key) => (
            <button
              key={key}
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => handleLoadPreset(key)}
            >
              {SAMPLE_PRESETS[key].label}
            </button>
          ))}
        </div>

        <select
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value as SourceType)}
          className="select"
          style={{ width: "auto", fontSize: "0.8rem", padding: "6px 10px" }}
          aria-label="Source type"
        >
          {(Object.keys(SOURCE_LABELS) as SourceType[]).map((t) => (
            <option key={t} value={t}>
              {SOURCE_LABELS[t]}
            </option>
          ))}
        </select>
      </div>

      {/* Editor */}
      <div className="panel rise rise-2" style={{ overflow: "hidden" }}>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Paste raw conversation, transcript, or unstructured notes…"
          rows={12}
          spellCheck={false}
          style={{
            width: "100%",
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--text)",
            fontSize: "0.875rem",
            lineHeight: 1.7,
            fontFamily: "var(--font-mono)",
            padding: "18px 20px",
            resize: "vertical",
            minHeight: "240px",
          }}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px 20px",
            borderTop: "1px solid var(--line)",
            background: "var(--bg-raised)",
          }}
        >
          <div
            className="mono-label"
            style={{ display: "flex", gap: "16px" }}
          >
            <span>{wordCount} WORDS</span>
            <span style={{ color: overLimit ? "var(--err)" : undefined }}>
              ~{approxTokens} TOKENS
            </span>
            <span>LIMIT 3000</span>
          </div>

          <button
            type="button"
            onClick={handleIngest}
            disabled={loading || !rawText.trim()}
            className="btn btn-primary"
          >
            {loading ? (
              <>
                <span className="spinner" /> Extracting
              </>
            ) : (
              "Extract actions"
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="notice notice-error rise rise-3" style={{ marginTop: "14px" }}>
          {error}
        </div>
      )}

      {/* How it works — quiet three-step strip */}
      <div
        className="rise rise-4"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "12px",
          marginTop: "44px",
        }}
      >
        {[
          ["01", "Extract", "Structured action items with verbatim source quotes."],
          ["02", "Verify", "Approve, edit, or dismiss each item — nothing runs without you."],
          ["03", "Execute", "Real side effects in Jira, Notion, Calendar, or the ledger."],
        ].map(([n, title, body]) => (
          <div key={n} style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <span className="mono" style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>
              {n}
            </span>
            <span className="h-section">{title}</span>
            <span className="dim" style={{ fontSize: "0.82rem", lineHeight: 1.55 }}>
              {body}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
