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

const TOOL_NAMES: Record<TargetTool, string> = {
  jira: "Jira",
  calendar: "Calendar",
  notion: "Notion",
  task_ledger: "Ledger",
};

const CONFIDENCE_TIER = (c: number): "high" | "mid" | "low" =>
  c >= 0.85 ? "high" : c >= 0.7 ? "mid" : "low";

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
  const rejected = currentAction === "REJECT";
  const tier = CONFIDENCE_TIER(item.confidence);

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

  return (
    <div
      className="panel panel-hover rise"
      onMouseEnter={() => onHoverSnippet(item.source_snippet)}
      onMouseLeave={() => onHoverSnippet(null)}
      style={{
        padding: "18px 20px",
        opacity: rejected ? 0.55 : 1,
        borderColor: isHighlighted
          ? "var(--line-focus)"
          : rejected
            ? "rgba(248, 113, 113, 0.25)"
            : undefined,
        transition:
          "opacity var(--fast) var(--ease), border-color var(--fast) var(--ease), background-color var(--fast) var(--ease)",
      }}
    >
      {/* Row 1: tool + type | confidence meter */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <select
            value={selectedTool}
            onChange={(e) => handleToolChange(e.target.value as TargetTool)}
            className={`tag tag-tool tag-${selectedTool}`}
            style={{ cursor: "pointer", outline: "none" }}
            aria-label="Target tool"
          >
            {(Object.keys(TOOL_NAMES) as TargetTool[]).map((t) => (
              <option key={t} value={t} style={{ color: "var(--text)", background: "var(--bg-surface)" }}>
                {TOOL_NAMES[t]}
              </option>
            ))}
          </select>
          <span className="mono-label">
            {item.actionability_type.replace("_", " ").toUpperCase()}
          </span>
        </div>

        <div className="meter" title={`Extraction confidence: ${Math.round(item.confidence * 100)}%`}>
          <div className="meter-track">
            <div
              className={`meter-fill ${tier}`}
              style={{ width: `${Math.round(item.confidence * 100)}%` }}
            />
          </div>
          <span className="meter-value">{Math.round(item.confidence * 100)}%</span>
        </div>
      </div>

      {/* Row 2: description */}
      <p
        style={{
          fontSize: "0.94rem",
          fontWeight: 480,
          color: "var(--text)",
          lineHeight: 1.5,
          margin: "12px 0 10px",
          textDecoration: rejected ? "line-through" : undefined,
          textDecorationColor: "var(--text-dim)",
        }}
      >
        {item.description}
      </p>

      {/* Row 3: metadata */}
      <div style={{ display: "flex", gap: "7px", flexWrap: "wrap", alignItems: "center" }}>
        {item.speaker && (
          <span className="tag">
            <span className="mono-label" style={{ color: "var(--text-dim)" }}>SPEAKER</span>
            {item.speaker}
          </span>
        )}
        {item.suggested_assignee && (
          <span className="tag">
            <span className="mono-label" style={{ color: "var(--text-dim)" }}>ASSIGNEE</span>
            {item.suggested_assignee}
          </span>
        )}
        <span className="tag">
          <span className="mono-label" style={{ color: "var(--text-dim)" }}>PRIORITY</span>
          <span style={{ textTransform: "capitalize" }}>{item.priority}</span>
        </span>
      </div>

      {/* Row 4: actions */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: "14px",
          paddingTop: "12px",
          borderTop: "1px solid var(--line)",
        }}
      >
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIsModalOpen(true)}>
          Edit payload
        </button>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            type="button"
            onClick={handleReject}
            className={`btn btn-sm ${rejected ? "btn-danger" : "btn-secondary"}`}
          >
            {rejected ? "Dismissed" : "Dismiss"}
          </button>
          <button
            type="button"
            onClick={handleApprove}
            className={`btn btn-sm ${!rejected ? "btn-success" : "btn-secondary"}`}
          >
            {!rejected ? "Approved" : "Approve"}
          </button>
        </div>
      </div>

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
