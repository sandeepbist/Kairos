"use client";

import React, { useState } from "react";
import { ActionItem, TargetTool, ActionItemDecision, ItemStatus } from "@/lib/types";
import { PayloadModal } from "./PayloadModal";

interface ActionCardProps {
  item: ActionItem;
  decision?: ActionItemDecision;
  onDecisionChange: (decision: ActionItemDecision) => void;
  onHoverSnippet: (snippet: string | null) => void;
  isHighlighted?: boolean;
  readOnly?: boolean;
  /** Increment to request opening the payload editor (keyboard shortcut). */
  editSignal?: number;
}

const TOOL_NAMES: Record<TargetTool, string> = {
  jira: "Jira",
  calendar: "Calendar",
  notion: "Notion",
  task_ledger: "Ledger",
  linear: "Linear",
  todoist: "Todoist",
  email_draft: "Email draft",
  github: "GitHub",
  confluence_page: "Confluence",
  google_tasks: "G Tasks",
  asana: "Asana",
  clickup: "ClickUp",
};

const CONFIDENCE_TIER = (c: number): "high" | "mid" | "low" =>
  c >= 0.85 ? "high" : c >= 0.7 ? "mid" : "low";

/** Read-only outcome chip per persisted item status. */
const OUTCOME: Record<ItemStatus, { className: string; label: string }> = {
  executed: { className: "status-on", label: "Executed" },
  failed: { className: "status-err", label: "Failed" },
  rejected: { className: "status-off", label: "Dismissed" },
  approved: { className: "status-warn", label: "Running" },
  modified_approved: { className: "status-warn", label: "Running" },
  pending: { className: "status-warn", label: "Running" },
};

export function ActionCard({
  item,
  decision,
  onDecisionChange,
  onHoverSnippet,
  isHighlighted,
  readOnly,
  editSignal,
}: ActionCardProps) {
  const [selectedTool, setSelectedTool] = useState<TargetTool>(
    decision?.override_tool || item.suggested_tool
  );
  const [modifiedPayload, setModifiedPayload] = useState<Record<string, unknown>>(
    decision?.modified_payload || item.tool_payload || {}
  );
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Re-sync local tool/payload when the parent decision changes (bulk
  // approve / dismiss-all / approve-high-confidence). Render-phase
  // prop-change adjustment, same pattern as editSignal below. Syncs only
  // when the incoming decision actually carries values, so a plain
  // REJECT (no overrides) never wipes local edits — the operator may
  // re-approve the card right after.
  const [prevDecisionTool, setPrevDecisionTool] = useState(decision?.override_tool);
  if (decision?.override_tool !== prevDecisionTool) {
    setPrevDecisionTool(decision?.override_tool);
    if (decision?.override_tool) setSelectedTool(decision.override_tool);
  }
  const [prevDecisionPayload, setPrevDecisionPayload] = useState(decision?.modified_payload);
  if (decision?.modified_payload !== prevDecisionPayload) {
    setPrevDecisionPayload(decision?.modified_payload);
    if (decision?.modified_payload) setModifiedPayload(decision.modified_payload);
  }

  // Keyboard shortcut (editSignal from the review page) opens the payload
  // editor for this card without touching decision state ownership.
  // Render-phase prop-change adjustment (no effect) per the documented
  // "adjust state when a prop changes" pattern.
  const [prevEditSignal, setPrevEditSignal] = useState(editSignal);
  if (editSignal !== prevEditSignal) {
    setPrevEditSignal(editSignal);
    if (editSignal && editSignal > 0) {
      setIsModalOpen(true);
    }
  }

  const currentAction = decision?.action || "APPROVE";
  // In read-only mode the decision state is never seeded — derive the
  // dismissed look from the persisted item status instead.
  const rejected = readOnly ? item.status === "rejected" : currentAction === "REJECT";
  const tier = CONFIDENCE_TIER(item.confidence);
  // Read-only mode shows the resolved tool: the operator's override if any,
  // else the tool execution actually used (final_tool), else the suggestion.
  const resolvedTool: TargetTool = decision?.override_tool || item.final_tool || item.suggested_tool;
  const outcome = OUTCOME[item.status];

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
          {readOnly ? (
            <span className={`tag tag-tool tag-${resolvedTool}`}>
              {TOOL_NAMES[resolvedTool]}
            </span>
          ) : (
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
          )}
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

      {/* Row 3b: execution failure detail (read-only failed items). The
          outcome chip above already carries the generic "Failed" state, so
          this only renders when the backend supplied error text. */}
      {readOnly && item.status === "failed" && item.error && (
        <div className="review-item-error" title={item.error}>
          <span className="mono-label review-error-label">Error</span>
          <span className="review-error-text">{item.error}</span>
        </div>
      )}

      {/* Row 4: actions / outcome */}
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
        {readOnly ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span
                className="tag"
                style={{ display: "inline-flex", alignItems: "center", gap: "7px" }}
              >
                <span className={`status-dot ${outcome.className}`} />
                {outcome.label}
              </span>
              {item.status === "rejected" && item.rejection_reason && (
                <span className="dim" style={{ fontSize: "0.78rem" }}>
                  {item.rejection_reason}
                </span>
              )}
            </div>
            {item.status === "executed" && item.external_url && (
              <a
                href={item.external_url}
                target="_blank"
                rel="noreferrer"
                className="link-accent"
                style={{ fontSize: "0.78rem", flexShrink: 0 }}
              >
                Open
              </a>
            )}
          </>
        ) : (
          <>
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
          </>
        )}
      </div>

      {!readOnly && (
        <PayloadModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          // Pass the card's current payload (including saved edits), not
          // just the extraction original, so reopening shows last-saved values.
          item={{ ...item, tool_payload: modifiedPayload }}
          targetTool={selectedTool}
          onSave={handleSavePayload}
        />
      )}
    </div>
  );
}
