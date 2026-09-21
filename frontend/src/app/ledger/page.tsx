"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { completeLedgerTask, deleteLedgerTask, listLedgerTasks } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { relativeTime } from "@/lib/time";
import { LedgerTask } from "@/lib/types";

type LedgerFilter = "open" | "completed" | "all";

const FILTERS: Array<{ value: LedgerFilter; label: string; param: string | undefined }> = [
  { value: "open", label: "Open", param: "open" },
  { value: "completed", label: "Completed", param: "completed" },
  { value: "all", label: "All", param: undefined },
];

const isOpen = (task: LedgerTask) => task.status !== "completed";

const PRIORITY_COLOR: Record<string, string | undefined> = {
  high: "var(--err)",
  medium: "var(--warn)",
  low: undefined,
};

const formatDueDate = (due: string): string => {
  const date = new Date(due);
  if (Number.isNaN(date.getTime())) return due;
  return date.toLocaleDateString();
};

export default function LedgerPage() {
  const [tasks, setTasks] = useState<LedgerTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<LedgerFilter>("open");
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const errorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showError = useCallback((message: string) => {
    setError(message);
    if (errorTimer.current) clearTimeout(errorTimer.current);
    errorTimer.current = setTimeout(() => setError(null), 5000);
  }, []);

  useEffect(() => {
    return () => {
      if (errorTimer.current) clearTimeout(errorTimer.current);
    };
  }, []);

  const fetchTasks = useCallback(async (current: LedgerFilter) => {
    const param = FILTERS.find((f) => f.value === current)?.param;
    try {
      const data = await listLedgerTasks(param);
      setTasks(data);
    } catch (err) {
      showError(errorMessage(err, "Failed to fetch ledger tasks"));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    // Deferred like the history page's initial fetch: setState off the
    // synchronous effect body avoids the cascading-render lint.
    timer = setTimeout(() => {
      if (cancelled) return;
      setLoading(true);
      void fetchTasks(filter);
    }, 0);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [fetchTasks, filter]);

  const handleComplete = async (taskId: string) => {
    setBusyId(taskId);
    try {
      await completeLedgerTask(taskId);
      await fetchTasks(filter);
    } catch (err) {
      showError(errorMessage(err, "Failed to complete task"));
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!window.confirm("Delete this task?")) return;
    setBusyId(taskId);
    try {
      await deleteLedgerTask(taskId);
      await fetchTasks(filter);
    } catch (err) {
      showError(errorMessage(err, "Failed to delete task"));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "880px" }}>
      {/* Header */}
      <div className="rise" style={{ marginBottom: "30px" }}>
        <p className="mono-label" style={{ marginBottom: "8px" }}>
          BUILT-IN SINK
        </p>
        <h1 className="h-display" style={{ fontSize: "2rem" }}>
          Task Ledger
        </h1>
        <p className="muted" style={{ fontSize: "0.9rem", marginTop: "8px", maxWidth: "520px" }}>
          Tasks captured from approved transcripts land here. The always-available
          sink needs no credentials.
        </p>
      </div>

      {/* Filter row */}
      <div
        className="rise rise-1"
        style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}
      >
        {FILTERS.map((f) => {
          const active = filter === f.value;
          return (
            <button
              key={f.value}
              type="button"
              aria-pressed={active}
              className={`btn btn-sm ${active ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          );
        })}
        {!loading && (
          <span className="mono-label dim" style={{ marginLeft: "auto" }}>
            {tasks.length} {tasks.length === 1 ? "TASK" : "TASKS"}
          </span>
        )}
      </div>

      {error && (
        <div className="notice notice-error fade-in" role="alert" style={{ marginBottom: "16px" }}>
          {error}
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: "64px", borderRadius: "var(--r-lg)" }} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && tasks.length === 0 && (
        <div className="panel rise" style={{ padding: "48px 32px", textAlign: "center" }}>
          <p className="dim" style={{ fontSize: "0.85rem" }}>
            No tasks yet — approve a transcript with task_ledger items, or run in
            sandbox mode to try the flow.
          </p>
        </div>
      )}

      {/* Task list */}
      {!loading && tasks.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {tasks.map((task, idx) => {
            const open = isOpen(task);
            const rel = task.created_at ? relativeTime(task.created_at) : null;
            const due = task.due_date ? formatDueDate(task.due_date) : null;
            const busy = busyId === task.id;
            return (
              <div
                key={task.id}
                className={`panel panel-hover rise rise-${Math.min(idx + 1, 5)}`}
                style={{ padding: "16px 20px" }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "14px",
                    flexWrap: "wrap",
                  }}
                >
                  {/* Left: title + notes */}
                  <div style={{ minWidth: 0, flex: "1 1 260px" }}>
                    <p
                      style={{
                        fontSize: "0.92rem",
                        fontWeight: 520,
                        color: "var(--text)",
                        lineHeight: 1.4,
                      }}
                    >
                      {task.title}
                    </p>
                    {task.notes && (
                      <p
                        className="dim"
                        style={{
                          fontSize: "0.79rem",
                          marginTop: "3px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={task.notes}
                      >
                        {task.notes}
                      </p>
                    )}
                  </div>

                  {/* Right: metadata + actions */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      flexShrink: 0,
                      flexWrap: "wrap",
                    }}
                  >
                    <span
                      className={`status-dot ${open ? "status-warn" : "status-on"}`}
                      title={open ? "Open" : "Completed"}
                    />
                    <span className="tag" style={{ textTransform: "capitalize" }}>
                      <span
                        style={{ color: PRIORITY_COLOR[task.priority] ?? undefined }}
                      >
                        {task.priority}
                      </span>
                    </span>
                    {due && (
                      <span className="mono-label" title={`Due ${task.due_date}`}>
                        DUE {due.toUpperCase()}
                      </span>
                    )}
                    {rel && (
                      <span className="mono-label dim" title={rel.title}>
                        {rel.text.toUpperCase()}
                      </span>
                    )}
                    {task.external_url && (
                      <a
                        href={task.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="link-accent"
                        style={{ fontSize: "0.78rem", flexShrink: 0 }}
                      >
                        Open
                      </a>
                    )}
                    {open && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleComplete(task.id)}
                        disabled={busy}
                        aria-label={`Complete task: ${task.title}`}
                      >
                        {busy ? "Working…" : "Complete"}
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ color: "var(--err)" }}
                      onClick={() => handleDelete(task.id)}
                      disabled={busy}
                      aria-label={`Delete task: ${task.title}`}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
