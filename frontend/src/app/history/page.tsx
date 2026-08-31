"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getHistory } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { HistoryBatch, TargetTool } from "@/lib/types";

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  completed: { label: "Completed", className: "status-on" },
  executing: { label: "Executing", className: "status-warn status-live" },
  awaiting_approval: { label: "Awaiting review", className: "status-warn" },
  expired: { label: "Expired", className: "status-off" },
  failed: { label: "Failed", className: "status-err" },
  processing: { label: "Processing", className: "status-warn status-live" },
};

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistoryData = async () => {
    try {
      const data = await getHistory();
      setHistory(data);
    } catch (err) {
      setError(errorMessage(err, "Failed to fetch history"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const initialFetch = setTimeout(fetchHistoryData, 0);
    const interval = setInterval(fetchHistoryData, 4000);
    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
  }, []);

  const statusInfo = (status: string) =>
    STATUS_LABEL[status] || { label: status, className: "status-err" };

  return (
    <div className="container" style={{ maxWidth: "880px" }}>
      {/* Header */}
      <div
        className="rise"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          marginBottom: "30px",
          flexWrap: "wrap",
          gap: "14px",
        }}
      >
        <div>
          <p className="mono-label" style={{ marginBottom: "8px" }}>
            AUDIT TRAIL
          </p>
          <h1 className="h-title" style={{ fontSize: "1.4rem" }}>
            Execution history
          </h1>
          <p className="dim" style={{ fontSize: "0.84rem", marginTop: "4px" }}>
            Processed batches, executed side effects, latency, and object links.
          </p>
        </div>

        <Link href="/" className="btn btn-primary btn-sm">
          New batch
        </Link>
      </div>

      {error && (
        <div className="notice notice-error" style={{ marginBottom: "18px" }}>
          {error}
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton" style={{ height: "96px", borderRadius: "var(--r-lg)" }} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && history.length === 0 && (
        <div className="panel rise" style={{ padding: "56px 32px", textAlign: "center" }}>
          <p className="h-title" style={{ fontSize: "1.05rem", marginBottom: "6px" }}>
            No batches yet
          </p>
          <p className="dim" style={{ fontSize: "0.85rem", marginBottom: "20px" }}>
            Ingest a conversation to see executed actions here.
          </p>
          <Link href="/" className="btn btn-primary btn-sm">
            Ingest conversation
          </Link>
        </div>
      )}

      {/* Batch list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {history.map((b, idx) => {
          const st = statusInfo(b.status);
          return (
            <div
              key={b.batch_id}
              className={`panel panel-hover rise rise-${Math.min(idx + 1, 5)}`}
              style={{ padding: "16px 20px" }}
            >
              {/* Row 1: id + source | status + review link */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "10px",
                  marginBottom: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span className="mono" style={{ fontSize: "0.82rem", color: "var(--text)" }}>
                    {b.batch_id.slice(0, 8)}
                  </span>
                  <span className="mono-label">{b.source_type.replace(/_/g, " ").toUpperCase()}</span>
                  <span className="dim" style={{ fontSize: "0.78rem" }}>
                    {b.created_at ? new Date(b.created_at).toLocaleString() : ""}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span
                    className="tag"
                    style={{ display: "flex", alignItems: "center", gap: "7px" }}
                  >
                    <span className={`status-dot ${st.className}`} />
                    {st.label}
                  </span>
                  {b.status === "awaiting_approval" && (
                    <Link href={`/review/${b.batch_id}`} className="btn btn-primary btn-sm">
                      Review
                    </Link>
                  )}
                </div>
              </div>

              {/* Row 2: stats */}
              <div
                className="mono-label"
                style={{
                  display: "flex",
                  gap: "20px",
                  padding: "7px 12px",
                  background: "var(--bg-input)",
                  borderRadius: "var(--r-sm)",
                  marginBottom: b.logs.length > 0 ? "12px" : 0,
                }}
              >
                <span>{b.total_items} ITEMS</span>
                <span style={{ color: b.executed_items > 0 ? "var(--ok)" : undefined }}>
                  {b.executed_items} EXECUTED
                </span>
                <span style={{ color: b.rejected_items > 0 ? "var(--err)" : undefined }}>
                  {b.rejected_items} DISMISSED
                </span>
                {b.token_count ? <span>{b.token_count} TOKENS</span> : null}
              </div>

              {/* Row 3: execution logs */}
              {b.logs.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {b.logs.map((log) => (
                    <div
                      key={log.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "12px",
                        padding: "8px 12px",
                        background: "var(--bg-input)",
                        border: "1px solid var(--line)",
                        borderRadius: "var(--r-sm)",
                        fontSize: "0.82rem",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          minWidth: 0,
                        }}
                      >
                        <span className={`tag tag-tool tag-${log.tool as TargetTool}`}>
                          {log.tool}
                        </span>
                        <span
                          style={{
                            color: "var(--text-secondary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {log.item_description || "Action item"}
                        </span>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "14px",
                          flexShrink: 0,
                        }}
                      >
                        {log.latency_ms !== undefined && (
                          <span className="mono-label">{log.latency_ms}MS</span>
                        )}
                        <span
                          className="status-dot"
                          style={{ background: log.status === "success" ? "var(--ok)" : "var(--err)" }}
                          title={log.status}
                        />
                        {log.external_url && (
                          <a href={log.external_url} target="_blank" rel="noreferrer" className="link-accent" style={{ fontSize: "0.78rem", flexShrink: 0 }}>
                            Open
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
