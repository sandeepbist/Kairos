"use client";

import React, { useState } from "react";
import { ActionItem, TargetTool } from "@/lib/types";

interface PayloadModalProps {
  item: ActionItem;
  targetTool: TargetTool;
  isOpen: boolean;
  onClose: () => void;
  onSave: (modifiedPayload: Record<string, any>) => void;
}

export function PayloadModal({
  item,
  targetTool,
  isOpen,
  onClose,
  onSave,
}: PayloadModalProps) {
  const [payload, setPayload] = useState<Record<string, any>>({ ...item.tool_payload });

  if (!isOpen) return null;

  const handleChange = (field: string, value: any) => {
    setPayload((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    onSave(payload);
    onClose();
  };

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      background: "rgba(0, 0, 0, 0.75)",
      backdropFilter: "blur(8px)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 100,
      padding: "1rem",
    }}>
      <div className="glass-panel" style={{
        width: "100%",
        maxWidth: "560px",
        padding: "1.75rem",
        border: "1px solid var(--border-active)",
        boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <div>
            <h3 style={{ fontSize: "1.15rem", fontWeight: 700 }}>
              Edit {targetTool.toUpperCase()} Payload
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              Customize tool parameters before dispatching execution.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: "1.2rem",
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem", maxHeight: "60vh", overflowY: "auto" }}>
          {/* JIRA FIELDS */}
          {targetTool === "jira" && (
            <>
              <div>
                <label style={labelStyle}>Project Key</label>
                <input
                  type="text"
                  value={payload.project_key || "ENG"}
                  onChange={(e) => handleChange("project_key", e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Issue Type</label>
                <select
                  value={payload.issue_type || "Task"}
                  onChange={(e) => handleChange("issue_type", e.target.value)}
                  style={inputStyle}
                >
                  <option value="Task">Task</option>
                  <option value="Bug">Bug</option>
                  <option value="Story">Story</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Summary / Title</label>
                <input
                  type="text"
                  value={payload.summary || ""}
                  onChange={(e) => handleChange("summary", e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Priority</label>
                <select
                  value={payload.priority || "Medium"}
                  onChange={(e) => handleChange("priority", e.target.value)}
                  style={inputStyle}
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </div>
            </>
          )}

          {/* CALENDAR FIELDS */}
          {targetTool === "calendar" && (
            <>
              <div>
                <label style={labelStyle}>Event Title</label>
                <input
                  type="text"
                  value={payload.title || ""}
                  onChange={(e) => handleChange("title", e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Start Time (ISO 8601)</label>
                <input
                  type="text"
                  value={payload.start_time || ""}
                  onChange={(e) => handleChange("start_time", e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>End Time (ISO 8601)</label>
                <input
                  type="text"
                  value={payload.end_time || ""}
                  onChange={(e) => handleChange("end_time", e.target.value)}
                  style={inputStyle}
                />
              </div>
            </>
          )}

          {/* NOTION FIELDS */}
          {targetTool === "notion" && (
            <>
              <div>
                <label style={labelStyle}>Database ID</label>
                <input
                  type="text"
                  value={payload.database_id || "roadmap_db"}
                  onChange={(e) => handleChange("database_id", e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Page Title</label>
                <input
                  type="text"
                  value={payload.title || ""}
                  onChange={(e) => handleChange("title", e.target.value)}
                  style={inputStyle}
                />
              </div>
            </>
          )}

          {/* TASK LEDGER FIELDS */}
          {targetTool === "task_ledger" && (
            <>
              <div>
                <label style={labelStyle}>Task Title</label>
                <input
                  type="text"
                  value={payload.title || ""}
                  onChange={(e) => handleChange("title", e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Priority</label>
                <select
                  value={payload.priority || "medium"}
                  onChange={(e) => handleChange("priority", e.target.value)}
                  style={inputStyle}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            Save Payload Changes
          </button>
        </div>
      </div>
    </div>
  );
}

const labelStyle = {
  display: "block",
  fontSize: "0.75rem",
  fontWeight: 600,
  color: "var(--text-secondary)",
  marginBottom: "0.35rem",
  textTransform: "uppercase" as const,
  letterSpacing: "0.04em",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem 0.8rem",
  background: "rgba(0, 0, 0, 0.4)",
  border: "1px solid var(--border-subtle)",
  borderRadius: "6px",
  color: "var(--text-primary)",
  fontSize: "0.875rem",
  fontFamily: "inherit",
};
