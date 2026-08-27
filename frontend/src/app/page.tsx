"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ingestBatch } from "@/lib/api";
import { SourceType } from "@/lib/types";

const SAMPLE_PRESETS = {
  meeting: {
    label: "Engineering Sync",
    type: "meeting_transcript" as SourceType,
    text: `Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.
Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.
John: I will update the technical spec doc in the roadmap wiki and share it with leadership.
Sarah: Let's also make sure someone follows up on the billing invoices discrepancy.`,
  },
  incident: {
    label: "Incident Post-Mortem",
    type: "slack_conversation" as SourceType,
    text: `IncidentLead: Mark, please file an urgent Jira bug on the auth token expiration race condition.
DevOps: I will schedule a post-mortem sync call with the on-call team tomorrow at 10 AM.
Security: Please document the root cause analysis in Notion under the Incident Database.`,
  },
  email: {
    label: "Scope Email",
    type: "email_thread" as SourceType,
    text: `From: product-lead@company.com
Subject: Q3 Architecture Deliverables

Hi Team,
1. Alex: Please prepare the RFC document for Model Context Protocol integration.
2. Sarah: Can you schedule a roadmap planning session with the stakeholders next Monday?
3. Task: Clean up all outdated deployment scripts before the freeze.`,
  },
};

export default function IngestPage() {
  const router = useRouter();
  const [rawText, setRawText] = useState(SAMPLE_PRESETS.meeting.text);
  const [sourceType, setSourceType] = useState<SourceType>("meeting_transcript");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wordCount = rawText.trim() ? rawText.trim().split(/\s+/).length : 0;
  const approxTokens = Math.round(wordCount * 1.33);

  const handleLoadPreset = (key: keyof typeof SAMPLE_PRESETS) => {
    setRawText(SAMPLE_PRESETS[key].text);
    setSourceType(SAMPLE_PRESETS[key].type);
    setError(null);
  };

  const handleIngest = async () => {
    if (!rawText.trim() || rawText.length < 10) {
      setError("Please enter at least 10 characters of conversation text.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await ingestBatch(rawText, sourceType);
      router.push(`/review/${response.batch_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to submit batch. Verify backend is running on localhost:8000.");
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "880px", paddingTop: "4rem", paddingBottom: "6rem" }}>
      {/* Hero Header */}
      <div style={{ marginBottom: "3rem" }}>
        <div className="pill" style={{ marginBottom: "1rem" }}>
          <span className="dot dot-green" />
          <span>Ambient Action Agent</span>
        </div>
        <h1 className="heading-display" style={{ marginBottom: "1rem" }}>
          Turn conversations into executed actions.
        </h1>
        <p className="text-subhead" style={{ maxWidth: "620px" }}>
          Paste meeting transcripts, emails, or incident logs. Kairos reasons over the text, matches target MCP tools, and routes side-effects for 1-click human verification.
        </p>
      </div>

      {/* Preset Selector & Format Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "1rem",
          flexWrap: "wrap",
          gap: "0.75rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginRight: "0.25rem" }}>
            Templates:
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleLoadPreset("meeting")}
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem", borderRadius: "6px" }}
          >
            {SAMPLE_PRESETS.meeting.label}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleLoadPreset("incident")}
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem", borderRadius: "6px" }}
          >
            {SAMPLE_PRESETS.incident.label}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleLoadPreset("email")}
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem", borderRadius: "6px" }}
          >
            {SAMPLE_PRESETS.email.label}
          </button>
        </div>

        {/* Source Format Selector */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Format:</label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as SourceType)}
            style={{
              padding: "0.3rem 0.6rem",
              borderRadius: "6px",
              background: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
              fontSize: "0.8rem",
              cursor: "pointer",
              outline: "none",
            }}
          >
            <option value="meeting_transcript">Meeting Transcript</option>
            <option value="slack_conversation">Slack Conversation</option>
            <option value="email_thread">Email Thread</option>
            <option value="general_notes">General Notes</option>
          </select>
        </div>
      </div>

      {/* Editor Panel */}
      <div className="card-panel" style={{ padding: "1.25rem", marginBottom: "1.5rem" }}>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Paste raw conversation, transcript, or unstructured notes here..."
          rows={11}
          style={{
            width: "100%",
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--text-primary)",
            fontSize: "0.9rem",
            lineHeight: 1.6,
            fontFamily: "var(--font-mono)",
            resize: "vertical",
          }}
        />

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingTop: "1rem",
            borderTop: "1px solid var(--border-subtle)",
            marginTop: "0.75rem",
          }}
        >
          <div style={{ display: "flex", gap: "1rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            <span>{wordCount} words</span>
            <span>~{approxTokens} tokens</span>
            <span>Max: 3,000</span>
          </div>

          <button
            type="button"
            onClick={handleIngest}
            disabled={loading}
            className="btn btn-primary"
            style={{ padding: "0.55rem 1.25rem", fontSize: "0.875rem" }}
          >
            {loading ? "Extracting..." : "Extract & Route Actions →"}
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "8px",
            background: "rgba(244, 63, 94, 0.1)",
            border: "1px solid rgba(244, 63, 94, 0.25)",
            color: "#fb7185",
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
