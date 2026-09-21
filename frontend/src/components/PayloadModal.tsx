"use client";

import React, { useEffect, useRef, useState } from "react";
import { ActionItem, TargetTool } from "@/lib/types";

interface PayloadModalProps {
  item: ActionItem;
  targetTool: TargetTool;
  isOpen: boolean;
  onClose: () => void;
  onSave: (modifiedPayload: Record<string, unknown>) => void;
}

/**
 * Supported field renderings.
 * "single-email" renders one email text input whose payload value is an
 * array (first element shown, `[value]` or `[]` written back).
 */
type FieldKind =
  | "text"
  | "textarea"
  | "select"
  | "date"
  | "datetime-local"
  | "single-email";

interface FieldConfig {
  /** Payload property the field displays and writes back to. */
  key: string;
  label: string;
  kind: FieldKind;
  /** Options for kind: "select". */
  options?: { value: string; label: string }[];
  /** Display default for kind: "select" when the payload lacks the key (never written back). */
  defaultValue?: string;
  /** Secondary payload key whose value is displayed while this key is empty (display-only). */
  fallback?: "description" | "title";
  placeholder?: string;
  /** Render the input with the "mono" modifier class. */
  mono?: boolean;
  /** Rows for kind: "textarea" (default 3). */
  rows?: number;
  /** Explanatory copy rendered directly below this field. */
  note?: string;
}

/** Shared option set for the lowercase low/medium/high priority selects (linear, task_ledger). */
const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

/**
 * Per-tool form layout. Keys, order and kinds mirror the payload each tool
 * consumes — adding a field to a tool is a config edit, not new JSX.
 */
const TOOL_FIELDS: Record<TargetTool, FieldConfig[]> = {
  jira: [
    { key: "project_key", label: "Project key", kind: "text", mono: true, placeholder: "from Settings · Tool targets" },
    {
      key: "issue_type", label: "Issue type", kind: "select", defaultValue: "Task",
      options: [
        { value: "Task", label: "Task" },
        { value: "Bug", label: "Bug" },
        { value: "Story", label: "Story" },
      ],
    },
    { key: "summary", label: "Summary", kind: "text" },
    {
      key: "priority", label: "Priority", kind: "select", defaultValue: "Medium",
      options: [
        { value: "Low", label: "Low" },
        { value: "Medium", label: "Medium" },
        { value: "High", label: "High" },
        { value: "Critical", label: "Critical" },
      ],
    },
  ],
  calendar: [
    { key: "title", label: "Event title", kind: "text" },
    { key: "start_time", label: "Start time", kind: "datetime-local", mono: true },
    {
      key: "end_time", label: "End time", kind: "datetime-local", mono: true,
      note: "Required before execution — Kairos never invents a meeting slot. The source quote is shown on the left.",
    },
    { key: "attendees", label: "Attendee email", kind: "single-email", mono: true, placeholder: "name@company.com" },
  ],
  notion: [
    { key: "database_id", label: "Database ID", kind: "text", mono: true, placeholder: "from Settings · Tool targets (empty = search)" },
    { key: "title", label: "Page title", kind: "text" },
    { key: "details", label: "Details", kind: "textarea", fallback: "description" },
  ],
  linear: [
    { key: "title", label: "Issue title", kind: "text" },
    { key: "description", label: "Description", kind: "textarea" },
    { key: "priority", label: "Priority", kind: "select", defaultValue: "medium", options: PRIORITY_OPTIONS },
  ],
  todoist: [
    { key: "content", label: "Task content", kind: "text", fallback: "title" },
    { key: "description", label: "Description", kind: "textarea" },
    { key: "due_date", label: "Due date (natural language ok)", kind: "text", mono: true, placeholder: "next Friday" },
  ],
  email_draft: [
    { key: "to", label: "To (optional)", kind: "text", mono: true, placeholder: "name@company.com" },
    { key: "subject", label: "Subject", kind: "text" },
    { key: "body", label: "Body", kind: "textarea", rows: 4 },
  ],
  github: [
    { key: "repo", label: "Repository (owner/name)", kind: "text", mono: true, placeholder: "acme/planning" },
    { key: "title", label: "Issue title", kind: "text" },
    { key: "description", label: "Description", kind: "textarea" },
    { key: "labels", label: "Labels (comma separated)", kind: "text", mono: true, placeholder: "kairos, bug" },
  ],
  confluence_page: [
    { key: "space_key", label: "Space key", kind: "text", mono: true, placeholder: "TEAM" },
    { key: "title", label: "Page title", kind: "text" },
    { key: "content", label: "Content", kind: "textarea", rows: 4 },
  ],
  google_tasks: [
    { key: "title", label: "Task title", kind: "text" },
    { key: "notes", label: "Notes", kind: "textarea" },
    { key: "due_date", label: "Due date", kind: "date", mono: true },
  ],
  asana: [
    { key: "name", label: "Task name", kind: "text", fallback: "title" },
    { key: "notes", label: "Notes", kind: "textarea" },
    { key: "due_date", label: "Due date", kind: "date", mono: true },
  ],
  clickup: [
    { key: "list_id", label: "List ID", kind: "text", mono: true, placeholder: "from the list URL in ClickUp" },
    { key: "name", label: "Task name", kind: "text", fallback: "title" },
    { key: "description", label: "Description", kind: "textarea" },
  ],
  task_ledger: [
    { key: "title", label: "Task title", kind: "text" },
    { key: "notes", label: "Notes", kind: "textarea" },
    { key: "priority", label: "Priority", kind: "select", defaultValue: "medium", options: PRIORITY_OPTIONS },
  ],
};

const FOCUSABLE_SELECTOR =
  'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])';

export function PayloadModal({
  item,
  targetTool,
  isOpen,
  onClose,
  onSave,
}: PayloadModalProps) {
  const [payload, setPayload] = useState<Record<string, unknown>>({ ...item.tool_payload });

  // Re-sync the editable copy whenever the dialog is (re)opened for a
  // different item or target tool — otherwise stale values from a
  // previous edit session leak into the new one. Render-phase prop-change
  // adjustment (no effect): keyed on ids, not object identity, so
  // background refetches replacing `item` while the dialog is open do not
  // wipe in-progress edits. Closing resets the key so reopening resyncs.
  const modalSyncKey = isOpen ? `${item.id}:${targetTool}` : null;
  const [prevModalSyncKey, setPrevModalSyncKey] = useState<string | null>(null);
  if (modalSyncKey !== prevModalSyncKey) {
    setPrevModalSyncKey(modalSyncKey);
    if (modalSyncKey) setPayload({ ...item.tool_payload });
  }

  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;

      // Focus trap: keep Tab cycling inside the dialog
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((el) => el.offsetParent !== null || el === document.activeElement);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (e.shiftKey) {
        if (active === first || !dialog.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !dialog.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) return;

    // Remember what had focus before the dialog opened…
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;

    // …and move focus to the first focusable element inside the dialog
    const dialog = dialogRef.current;
    if (dialog) {
      const first = dialog.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (first ?? dialog).focus();
    }

    // On close/unmount, hand focus back to the trigger element
    return () => {
      const el = previouslyFocusedRef.current;
      if (el && document.contains(el)) el.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleChange = (field: string, value: unknown) => {
    setPayload((prev) => ({ ...prev, [field]: value }));
  };

  /** Coerces a possibly-unknown payload value into an input-friendly string. */
  const str = (field: string, fallback = ""): string => {
    const v = payload[field];
    return typeof v === "string" ? v : v == null ? fallback : String(v);
  };

  /** Display value for a field, honoring display-only select defaults and fallbacks. */
  const fieldValue = (field: FieldConfig): string => {
    const own = str(field.key, field.defaultValue ?? "");
    return own || (field.fallback ? str(field.fallback) : "");
  };

  /** Display value for "single-email" fields: first element of the attendees array. */
  const attendeeValue = (field: FieldConfig): string => {
    const v = payload[field.key];
    return Array.isArray(v) ? String(v[0] ?? "") : "";
  };

  const handleSave = () => {
    onSave(payload);
    onClose();
  };

  const fields = TOOL_FIELDS[targetTool];

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
        ref={dialogRef}
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
          {fields.map((field) => (
            <React.Fragment key={field.key}>
              <div>
                <label className="field-label">{field.label}</label>
                {field.kind === "textarea" ? (
                  <textarea
                    className="input"
                    style={{ resize: "vertical" }}
                    rows={field.rows ?? 3}
                    value={fieldValue(field)}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                  />
                ) : field.kind === "select" ? (
                  <select
                    className="select"
                    value={fieldValue(field)}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                  >
                    {field.options?.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className={field.mono ? "input mono" : "input"}
                    type={
                      field.kind === "date" || field.kind === "datetime-local"
                        ? field.kind
                        : undefined
                    }
                    value={
                      field.kind === "single-email"
                        ? attendeeValue(field)
                        : fieldValue(field)
                    }
                    placeholder={field.placeholder}
                    onChange={(e) =>
                      field.kind === "single-email"
                        ? handleChange(field.key, e.target.value ? [e.target.value] : [])
                        : handleChange(field.key, e.target.value)
                    }
                  />
                )}
              </div>
              {field.note ? (
                <p className="dim" style={{ fontSize: "0.72rem", lineHeight: 1.45 }}>
                  {field.note}
                </p>
              ) : null}
            </React.Fragment>
          ))}
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
