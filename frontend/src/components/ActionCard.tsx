"use client";

import React, { useState } from "react";
import { ActionItem, TargetTool, ActionItemDecision } from "@/lib/types";
import { PayloadModal } from "./PayloadModal";

interface ActionCardProps {
  item: ActionItem;
  decision?: ActionItemDecision;
  onDecisionChange: (decision: ActionItemDecision) => void;
  onHoverSnippet: (snippet: string | null) => void;
  isHighlighted?: boolean;
}

export function ActionCard({
  item,
  decision,
  onDecisionChange,
  onHoverSnippet,
  isHighlighted,
}: ActionCardProps) {
  const [selectedTool, setSelectedTool] = useState<TargetTool>(
    decision?.override_tool || item.suggested_tool
  );
  const [modifiedPayload, setModifiedPayload] = useState<Record<string, any>>(
    decision?.modified_payload || item.tool_payload || {}
  );
  const [isModalOpen, setIsModalOpen] = useState(false);

  const currentAction = decision?.action || "APPROVE";

  const handleToolChange = (newTool: TargetTool) => {
    setSelectedTool(newTool);
    onDecisionChange({
      item_id: item.id,
      action: newTool !== item.suggested_tool ? "MODIFY_AND_APPROVE" : "APPROVE",
      override_tool: newTool,
      modified_payload: modifiedPayload,
    });
  };

  const handleApprove = () => {
    onDecisionChange({
      item_id: item.id,
      action: selectedTool !== item.suggested_tool ? "MODIFY_AND_APPROVE" : "APPROVE",
      override_tool: selectedTool,
      modified_payload: modifiedPayload,
    });
  };

  const handleReject = () => {
    onDecisionChange({
      item_id: item.id,
      action: "REJECT",
      rejection_reason: "Dismissed by user during review",
    });
  };

  const handleSavePayload = (newPayload: Record<string, any>) => {
    setModifiedPayload(newPayload);
    onDecisionChange({
      item_id: item.id,
      action: "MODIFY_AND_APPROVE",
      override_tool: selectedTool,
      modified_payload: newPayload,
    });
  };

  const getConfidenceBadge = (score: number) => {
    const pct = Math.round(score * 100);
    if (score >= 0.85) return <span className="badge badge-confidence-high">🟢 {pct}% Confidence</span>;
    if (score >= 0.70) return <span className="badge badge-confidence-medium">🟡 {pct}% Confidence</span>;
    return <span className="badge badge-confidence-low">🔴 {pct}% Confidence</span>;
  };

  return (
    <div
      className="glass-panel"
      onMouseEnter={() => onHoverSnippet(item.source_snippet)}
      onMouseLeave={() => onHoverSnippet(null)}
      style={{
        padding: "1.25rem",
        border: isHighlighted
          ? "1px solid var(--accent-cyan)"
          : currentAction === "REJECT"
          ? "1px solid rgba(244, 63, 94, 0.4)"
          : "1px solid var(--border-subtle)",
        background: currentAction === "REJECT"
          ? "rgba(244, 63, 94, 0.04)"
          : isHighlighted
          ? "var(--bg-card-hover)"
          : "var(--bg-card)",
        transition: "all 0.2s ease",
        display: "flex",
        flexDirection: "column",
        gap: "0.85rem",
      }}
    >
      {/* Top Header Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          {/* Target Tool Selector */}
          <select
            value={selectedTool}
            onChange={(e) => handleToolChange(e.target.value as TargetTool)}
            style={{
              padding: "0.25rem 0.6rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 700,
              background: "rgba(0, 0, 0, 0.4)",
              color: selectedTool === "jira" ? "#60a5fa" : selectedTool === "calendar" ? "#34d399" : selectedTool === "notion" ? "#c084fc" : "#fbbf24",
              border: "1px solid var(--border-subtle)",
              cursor: "pointer",
            }}
          >
            <option value="jira">Jira Issue</option>
            <option value="calendar">Google Calendar</option>
            <option value="notion">Notion Page</option>
            <option value="task_ledger">Task Ledger</option>
          </select>

          {/* Actionability Badge */}
          <span style={{
            fontSize: "0.7rem",
            color: "var(--text-muted)",
            textTransform: "uppercase",
            fontWeight: 600,
            background: "rgba(255, 255, 255, 0.05)",
            padding: "0.2rem 0.5rem",
            borderRadius: "4px",
          }}>
            {item.actionability_type}
          </span>
        </div>

        {/* Confidence Badge */}
        {getConfidenceBadge(item.confidence)}
      </div>

      {/* Description */}
      <p style={{ fontSize: "0.95rem", fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.4 }}>
        {item.description}
      </p>

      {/* Metadata Chips: Speaker, Assignee, Priority */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center", fontSize: "0.75rem" }}>
        {item.speaker && (
          <span style={{ color: "var(--text-secondary)", background: "rgba(255, 255, 255, 0.04)", padding: "0.15rem 0.5rem", borderRadius: "4px" }}>
            🗣️ Speaker: <strong style={{ color: "var(--text-primary)" }}>{item.speaker}</strong>
          </span>
        )}
        {item.suggested_assignee && (
          <span style={{ color: "var(--text-secondary)", background: "rgba(56, 189, 248, 0.08)", padding: "0.15rem 0.5rem", borderRadius: "4px" }}>
            👤 Assignee: <strong style={{ color: "var(--accent-cyan)" }}>{item.suggested_assignee}</strong>
          </span>
        )}
        <span style={{
          color: item.priority === "high" ? "#fb7185" : "var(--text-muted)",
          background: "rgba(255, 255, 255, 0.04)",
          padding: "0.15rem 0.5rem",
          borderRadius: "4px",
          textTransform: "capitalize",
        }}>
          Priority: <strong>{item.priority}</strong>
        </span>
      </div>

      {/* Source Provenance Snippet Preview */}
      <div style={{
        background: "rgba(0, 0, 0, 0.35)",
        borderLeft: "2px solid var(--accent-cyan)",
        padding: "0.5rem 0.75rem",
        borderRadius: "0 6px 6px 0",
        fontSize: "0.8rem",
        color: "var(--text-secondary)",
        fontFamily: "var(--font-mono)",
      }}>
        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", display: "block", marginBottom: "0.2rem" }}>
          SOURCE QUOTE:
        </span>
        &quot;{item.source_snippet}&quot;
      </div>

      {/* Card Action Controls */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginTop: "0.25rem",
        paddingTop: "0.75rem",
        borderTop: "1px solid var(--border-subtle)",
      }}>
        <button
          onClick={() => setIsModalOpen(true)}
          style={{
            background: "transparent",
            border: "1px solid var(--border-subtle)",
            color: "var(--text-secondary)",
            fontSize: "0.75rem",
            padding: "0.3rem 0.6rem",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          ⚙️ Customize Payload
        </button>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={handleReject}
            className={`btn ${currentAction === "REJECT" ? "btn-danger" : "btn-secondary"}`}
            style={{ padding: "0.35rem 0.8rem", fontSize: "0.75rem" }}
          >
            {currentAction === "REJECT" ? "✗ Rejected" : "Reject"}
          </button>
          <button
            onClick={handleApprove}
            className={`btn ${currentAction !== "REJECT" ? "btn-success" : "btn-secondary"}`}
            style={{ padding: "0.35rem 0.8rem", fontSize: "0.75rem" }}
          >
            {currentAction !== "REJECT" ? "✓ Approved" : "Approve"}
          </button>
        </div>
      </div>

      {/* Payload Modal */}
      <PayloadModal
        item={item}
        targetTool={selectedTool}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSavePayload}
      />
    </div>
  );
}
