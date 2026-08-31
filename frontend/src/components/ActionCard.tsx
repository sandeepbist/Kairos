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
  const [modifiedPayload, setModifiedPayload] = useState<Record<string, unknown>>(
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

  const handleSavePayload = (newPayload: Record<string, unknown>) => {
    setModifiedPayload(newPayload);
    onDecisionChange({
      item_id: item.id,
      action: "MODIFY_AND_APPROVE",
      override_tool: selectedTool,
      modified_payload: newPayload,
    });
  };

  const getToolPillClass = (tool: string) => {
    if (tool === "notion") return "pill pill-notion";
    if (tool === "jira") return "pill pill-jira";
    if (tool === "calendar") return "pill pill-calendar";
    return "pill pill-task_ledger";
  };

  return (
    <div
      className="card-panel"
      onMouseEnter={() => onHoverSnippet(item.source_snippet)}
      onMouseLeave={() => onHoverSnippet(null)}
      style={{
        padding: "1.25rem",
        border: isHighlighted
          ? "1px solid #06b6d4"
          : currentAction === "REJECT"
          ? "1px solid rgba(244, 63, 94, 0.3)"
          : "1px solid var(--border-subtle)",
        background: currentAction === "REJECT"
          ? "rgba(244, 63, 94, 0.03)"
          : isHighlighted
          ? "var(--bg-surface-hover)"
          : "var(--bg-surface)",
        transition: "all 0.15s ease",
        display: "flex",
        flexDirection: "column",
        gap: "0.85rem",
      }}
    >
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {/* Tool Selector */}
          <select
            value={selectedTool}
            onChange={(e) => handleToolChange(e.target.value as TargetTool)}
            className={getToolPillClass(selectedTool)}
            style={{
              padding: "0.2rem 0.5rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              outline: "none",
            }}
          >
            <option value="jira">Jira Issue</option>
            <option value="calendar">Google Calendar</option>
            <option value="notion">Notion Page</option>
            <option value="task_ledger">Task Ledger</option>
          </select>

          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "capitalize" }}>
            {item.actionability_type.replace("_", " ")}
          </span>
        </div>

        {/* Confidence Pill */}
        <div className="pill" style={{ fontSize: "0.7rem", color: item.confidence >= 0.85 ? "#34d399" : item.confidence >= 0.7 ? "#fbbf24" : "#fb7185" }}>
          <span className={`dot ${item.confidence >= 0.85 ? "dot-green" : item.confidence >= 0.7 ? "dot-amber" : "dot-rose"}`} />
          <span>{Math.round(item.confidence * 100)}% Confidence</span>
        </div>
      </div>

      {/* Task Description */}
      <p style={{ fontSize: "0.925rem", fontWeight: 500, color: "#ffffff", lineHeight: 1.45 }}>
        {item.description}
      </p>

      {/* Metadata Tags */}
      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center", fontSize: "0.75rem" }}>
        {item.speaker && (
          <span className="pill" style={{ fontSize: "0.7rem" }}>
            Speaker: <strong style={{ color: "#ffffff", marginLeft: "0.2rem" }}>{item.speaker}</strong>
          </span>
        )}
        {item.suggested_assignee && (
          <span className="pill" style={{ fontSize: "0.7rem" }}>
            Assignee: <strong style={{ color: "#ffffff", marginLeft: "0.2rem" }}>{item.suggested_assignee}</strong>
          </span>
        )}
        <span className="pill" style={{ fontSize: "0.7rem", textTransform: "capitalize" }}>
          Priority: {item.priority}
        </span>
      </div>

      {/* Action Decision Controls */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: "0.75rem",
          borderTop: "1px solid var(--border-subtle)",
          marginTop: "0.25rem",
        }}
      >
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setIsModalOpen(true)}
          style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
        >
          Customize Payload →
        </button>

        <div style={{ display: "flex", gap: "0.4rem" }}>
          <button
            type="button"
            onClick={handleReject}
            className={`btn ${currentAction === "REJECT" ? "btn-danger" : "btn-secondary"}`}
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.75rem" }}
          >
            {currentAction === "REJECT" ? "Dismissed" : "Dismiss"}
          </button>
          <button
            type="button"
            onClick={handleApprove}
            className={`btn ${currentAction !== "REJECT" ? "btn-success" : "btn-secondary"}`}
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.75rem" }}
          >
            {currentAction !== "REJECT" ? "✓ Approved" : "Approve"}
          </button>
        </div>
      </div>

      {/* Payload Modal */}
      <PayloadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        item={item}
        targetTool={selectedTool}
        onSave={handleSavePayload}
      />
    </div>
  );
}
