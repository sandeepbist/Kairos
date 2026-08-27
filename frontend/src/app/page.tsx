"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ingestBatch } from "@/lib/api";
import { SourceType } from "@/lib/types";

const SAMPLE_PRESETS = {
  meeting: {
    label: "🎙️ Engineering Sync Meeting",
    type: "meeting_transcript" as SourceType,
    text: `Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.
Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.
John: I will update the technical spec doc in the roadmap wiki and share it with leadership.
Sarah: Let's also make sure someone follows up on the billing invoices discrepancy.`,
  },
  incident: {
    label: "🚨 Incident Post-Mortem",
    type: "slack_conversation" as SourceType,
    text: `IncidentLead: Mark, please file an urgent Jira bug on the auth token expiration race condition.
DevOps: I will schedule a post-mortem sync call with the on-call team tomorrow at 10 AM.
Security: Please document the root cause analysis in Notion under the Incident Database.`,
  },
  email: {
    label: "✉️ Project Scope Email",
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
      setError("Please enter at least 10 characters of unstructured text.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await ingestBatch(rawText, sourceType);
      // Navigate to review screen
      router.push(`/review/${response.batch_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to submit batch. Make sure backend is running on localhost:8000.");
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "960px" }}>
      {/* Header Banner */}
      <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
        <h1 style={{
          fontSize: "2.5rem",
          fontWeight: 800,
          letterSpacing: "-0.03em",
          background: "linear-gradient(135deg, #f8fafc 40%, #94a3b8)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          marginBottom: "0.75rem",
        }}>
          Ambient Action Extraction & Execution
        </h1>
        <p style={{
          fontSize: "1.05rem",
          color: "var(--text-secondary)",
          maxWidth: "680px",
          margin: "0 auto",
        }}>
          Paste meeting transcripts, raw emails, or Slack conversations.
          Kairos reasons over the text, routes each item to Notion, Jira, Calendar, or Task Ledger, and awaits your 1-click approval.
        </p>
      </div>

      {/* Preset Quick Loader Buttons */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: "1rem",
        flexWrap: "wrap",
        gap: "0.75rem",
      }}>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", alignSelf: "center", marginRight: "0.25rem" }}>
            Sample Presets:
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleLoadPreset("meeting")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            {SAMPLE_PRESETS.meeting.label}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleLoadPreset("incident")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            {SAMPLE_PRESETS.incident.label}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleLoadPreset("email")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            {SAMPLE_PRESETS.email.label}
          </button>
        </div>

        {/* Source Type Selector */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 600 }}>
            Source Format:
          </label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as SourceType)}
            style={{
              padding: "0.4rem 0.75rem",
              borderRadius: "6px",
              background: "rgba(18, 26, 43, 0.9)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
              cursor: "pointer",
            }}
          >
            <option value="meeting_transcript">Meeting Transcript</option>
            <option value="slack_conversation">Slack Conversation</option>
            <option value="email_thread">Email Thread</option>
            <option value="general_notes">General Notes</option>
          </select>
        </div>
      </div>

      {/* Ingestion Panel */}
      <div className="glass-panel" style={{ padding: "1.5rem", position: "relative" }}>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Paste raw conversation or transcript here..."
          rows={12}
          style={{
            width: "100%",
            background: "rgba(0, 0, 0, 0.4)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "8px",
            padding: "1rem",
            color: "var(--text-primary)",
            fontSize: "0.95rem",
            lineHeight: 1.6,
            fontFamily: "var(--font-mono)",
            resize: "vertical",
            outline: "none",
          }}
        />

        {/* Character & Token Counts */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: "0.75rem",
          fontSize: "0.8rem",
          color: "var(--text-muted)",
        }}>
          <div>
            <span>{wordCount} words</span>
            <span style={{ margin: "0 0.5rem" }}>•</span>
            <span style={{ color: approxTokens > 3000 ? "var(--accent-rose)" : "var(--text-muted)" }}>
              ~{approxTokens} tokens {approxTokens > 3000 && "(Will be safely guarded)"}
            </span>
          </div>

          <button
            onClick={handleIngest}
            disabled={loading}
            className="btn btn-primary"
            style={{
              padding: "0.7rem 1.75rem",
              fontSize: "0.95rem",
              opacity: loading ? 0.7 : 1,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? (
              <>
                <span className="pulse-indicator">⚡</span> Extracting with LangGraph...
              </>
            ) : (
              <>
                🚀 Extract & Route Action Items
              </>
            )}
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div style={{
            marginTop: "1rem",
            padding: "0.75rem 1rem",
            borderRadius: "6px",
            background: "rgba(244, 63, 94, 0.15)",
            border: "1px solid rgba(244, 63, 94, 0.3)",
            color: "#fb7185",
            fontSize: "0.875rem",
          }}>
            ⚠️ {error}
          </div>
        )}
      </div>
    </div>
  );
}
