"use client";

import React, { useEffect, useState } from "react";
import { ActionItem, TargetTool } from "@/lib/types";

interface PayloadModalProps {
  item: ActionItem;
  targetTool: TargetTool;
  isOpen: boolean;
  onClose: () => void;
  onSave: (modifiedPayload: Record<string, unknown>) => void;
}

export function PayloadModal({
  item,
  targetTool,
  isOpen,
  onClose,
  onSave,
}: PayloadModalProps) {
  const [payload, setPayload] = useState<Record<string, unknown>>({ ...item.tool_payload });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleChange = (field: string, value: unknown) => {
    setPayload((prev) => ({ ...prev, [field]: value }));
  };

  /** Coerces a possibly-unknown payload value into an input-friendly string. */
  const str = (field: string, fallback = ""): string => {
    const v = payload[field];
    return typeof v === "string" ? v : v == null ? fallback : String(v);
  };

  const handleSave = () => {
    onSave(payload);
    onClose();
  };

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--bg-overlay)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: "24px",
      }}
    >
      <div
        className="panel-elevated fade-in"
        style={{ width: "100%", maxWidth: "480px", padding: "22px 24px" }}
        role="dialog"
        aria-modal="true"
        aria-label={`Configure ${targetTool} payload`}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "18px",
          }}
        >
          <div>
            <h3 className="h-title" style={{ fontSize: "1.05rem" }}>
              {targetTool === "task_ledger" ? "Task Ledger" : targetTool} payload
            </h3>
            <p className="dim" style={{ fontSize: "0.8rem", marginTop: "3px" }}>
              Adjust parameters before dispatch.
            </p>
          </div>
          <button
            onClick={onClose}
            className="btn btn-ghost btn-sm"
            style={{ fontSize: "0.9rem", padding: "4px 10px" }}
            aria-label="Close"
          >
            Esc
          </button>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            maxHeight: "58vh",
            overflowY: "auto",
            paddingRight: "4px",
          }}
        >
          {/* JIRA */}
          {targetTool === "jira" && (
            <>
              <div>
                <label className="field-label">Project key</label>
                <input
                  className="input mono"
                  value={str("project_key", "ENG")}
                  onChange={(e) => handleChange("project_key", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Issue type</label>
                <select
                  className="select"
                  value={str("issue_type", "Task")}
                  onChange={(e) => handleChange("issue_type", e.target.value)}
                >
                  <option value="Task">Task</option>
                  <option value="Bug">Bug</option>
                  <option value="Story">Story</option>
                </select>
              </div>
              <div>
                <label className="field-label">Summary</label>
                <input
                  className="input"
                  value={str("summary")}
                  onChange={(e) => handleChange("summary", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Priority</label>
                <select
                  className="select"
                  value={str("priority", "Medium")}
                  onChange={(e) => handleChange("priority", e.target.value)}
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </div>
            </>
          )}

          {/* CALENDAR */}
          {targetTool === "calendar" && (
            <>
              <div>
                <label className="field-label">Event title</label>
                <input
                  className="input"
                  value={str("title")}
                  onChange={(e) => handleChange("title", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Start time (ISO 8601)</label>
                <input
                  className="input mono"
                  value={str("start_time")}
                  onChange={(e) => handleChange("start_time", e.target.value)}
                  placeholder="2026-09-10T14:00:00Z"
                />
              </div>
              <div>
                <label className="field-label">End time (ISO 8601)</label>
                <input
                  className="input mono"
                  value={str("end_time")}
                  onChange={(e) => handleChange("end_time", e.target.value)}
                  placeholder="2026-09-10T15:00:00Z"
                />
              </div>
              <div>
                <label className="field-label">Attendee email</label>
                <input
                  className="input mono"
                  value={Array.isArray(payload.attendees) ? String(payload.attendees[0] ?? "") : ""}
                  onChange={(e) =>
                    handleChange("attendees", e.target.value ? [e.target.value] : [])
                  }
                  placeholder="name@company.com"
                />
              </div>
            </>
          )}

          {/* NOTION */}
          {targetTool === "notion" && (
            <>
              <div>
                <label className="field-label">Database ID</label>
                <input
                  className="input mono"
                  value={str("database_id", "roadmap_db")}
                  onChange={(e) => handleChange("database_id", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Page title</label>
                <input
                  className="input"
                  value={str("title")}
                  onChange={(e) => handleChange("title", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Details</label>
                <textarea
                  className="input"
                  style={{ resize: "vertical" }}
                  rows={3}
                  value={str("details") || str("description")}
                  onChange={(e) => handleChange("details", e.target.value)}
                />
              </div>
            </>
          )}

          {/* LINEAR */}
          {targetTool === "linear" && (
            <>
              <div>
                <label className="field-label">Issue title</label>
                <input
                  className="input"
                  value={str("title")}
                  onChange={(e) => handleChange("title", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Description</label>
                <textarea
                  className="input"
                  style={{ resize: "vertical" }}
                  rows={3}
                  value={str("description")}
                  onChange={(e) => handleChange("description", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Priority</label>
                <select
                  className="select"
                  value={str("priority", "medium")}
                  onChange={(e) => handleChange("priority", e.target.value)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </>
          )}

          {/* TODOIST */}
          {targetTool === "todoist" && (
            <>
              <div>
                <label className="field-label">Task content</label>
                <input
                  className="input"
                  value={str("content") || str("title")}
                  onChange={(e) => handleChange("content", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Description</label>
                <textarea
                  className="input"
                  style={{ resize: "vertical" }}
                  rows={3}
                  value={str("description")}
                  onChange={(e) => handleChange("description", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Due date (natural language ok)</label>
                <input
                  className="input mono"
                  value={str("due_date")}
                  onChange={(e) => handleChange("due_date", e.target.value)}
                  placeholder="next Friday"
                />
              </div>
            </>
          )}

          {/* EMAIL DRAFT */}
          {targetTool === "email_draft" && (
            <>
              <div>
                <label className="field-label">To (optional)</label>
                <input
                  className="input mono"
                  value={str("to")}
                  onChange={(e) => handleChange("to", e.target.value)}
                  placeholder="name@company.com"
                />
              </div>
              <div>
                <label className="field-label">Subject</label>
                <input
                  className="input"
                  value={str("subject")}
                  onChange={(e) => handleChange("subject", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Body</label>
                <textarea
                  className="input"
                  style={{ resize: "vertical" }}
                  rows={4}
                  value={str("body")}
                  onChange={(e) => handleChange("body", e.target.value)}
                />
              </div>
            </>
          )}

          {/* TASK LEDGER */}
          {targetTool === "task_ledger" && (
            <>
              <div>
                <label className="field-label">Task title</label>
                <input
                  className="input"
                  value={str("title")}
                  onChange={(e) => handleChange("title", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Notes</label>
                <textarea
                  className="input"
                  style={{ resize: "vertical" }}
                  rows={3}
                  value={str("notes")}
                  onChange={(e) => handleChange("notes", e.target.value)}
                />
              </div>
              <div>
                <label className="field-label">Priority</label>
                <select
                  className="select"
                  value={str("priority", "medium")}
                  onChange={(e) => handleChange("priority", e.target.value)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "10px",
            marginTop: "20px",
            paddingTop: "16px",
            borderTop: "1px solid var(--line)",
          }}
        >
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={handleSave}>
            Save changes
          </button>
        </div>
      </div>
    </div>
  );
}
