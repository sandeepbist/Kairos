"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getHistory } from "@/lib/api";
import { HistoryBatch } from "@/lib/types";

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistoryData = async () => {
    try {
      const data = await getHistory();
      setHistory(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistoryData();
    const interval = setInterval(fetchHistoryData, 4000);
    return () => clearInterval(interval);
  }, []);

  const getStatusPill = (status: string) => {
    if (status === "completed") {
      return (
        <span className="pill" style={{ color: "#34d399" }}>
          <span className="dot dot-green" />
          <span>Completed</span>
        </span>
      );
    }
    if (status === "executing") {
      return (
        <span className="pill" style={{ color: "#38bdf8" }}>
          <span className="dot dot-amber" />
          <span>Executing</span>
        </span>
      );
    }
    if (status === "awaiting_approval") {
      return (
        <span className="pill" style={{ color: "#fbbf24" }}>
          <span className="dot dot-amber" />
          <span>Awaiting Review</span>
        </span>
      );
    }
    if (status === "expired") {
      return (
        <span className="pill" style={{ color: "#a1a1aa" }}>
          <span>Auto-Expired</span>
        </span>
      );
    }
    return (
      <span className="pill" style={{ color: "#fb7185" }}>
        <span className="dot dot-rose" />
        <span style={{ textTransform: "capitalize" }}>{status}</span>
      </span>
    );
  };

  return (
    <div className="container" style={{ maxWidth: "1000px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2.5rem" }}>
        <div>
          <h1 className="heading-title">Execution Audit Trail</h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
            Log of processed batches, executed side-effects, latency metrics, and verified object links.
          </p>
        </div>

        <Link href="/" className="btn btn-primary" style={{ fontSize: "0.85rem", padding: "0.45rem 1rem" }}>
          + New Ingestion
        </Link>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: "6rem 0", color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Loading audit trail...
        </div>
      )}

      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "8px",
            background: "rgba(244, 63, 94, 0.1)",
            border: "1px solid rgba(244, 63, 94, 0.25)",
            color: "#fb7185",
            fontSize: "0.85rem",
            marginBottom: "1.5rem",
          }}
        >
          {error}
        </div>
      )}

      {!loading && history.length === 0 && (
        <div className="card-panel" style={{ padding: "4rem 2rem", textAlign: "center" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#ffffff" }}>No execution history yet</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.4rem" }}>
            Ingest your first conversation transcript to execute actions across your tool ecosystem.
          </p>
          <Link href="/" className="btn btn-primary" style={{ marginTop: "1.25rem", fontSize: "0.85rem" }}>
            Ingest Conversation →
          </Link>
        </div>
      )}

      {/* Batch History List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {history.map((b) => (
          <div key={b.batch_id} className="card-panel" style={{ padding: "1.25rem" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "0.75rem",
                marginBottom: "0.75rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <strong style={{ fontSize: "0.95rem", color: "#ffffff", letterSpacing: "-0.01em" }}>
                      Batch {b.batch_id.slice(0, 8)}
                    </strong>
                    <span className="pill" style={{ fontSize: "0.7rem", textTransform: "capitalize" }}>
                      {b.source_type.replace("_", " ")}
                    </span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {b.created_at ? new Date(b.created_at).toLocaleString() : "Recently"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                {getStatusPill(b.status)}
                {b.status === "awaiting_approval" && (
                  <Link
                    href={`/review/${b.batch_id}`}
                    className="btn btn-primary"
                    style={{ fontSize: "0.75rem", padding: "0.3rem 0.75rem" }}
                  >
                    Review Items →
                  </Link>
                )}
              </div>
            </div>

            {/* Execution Stats Bar */}
            <div
              style={{
                display: "flex",
                gap: "1.5rem",
                background: "rgba(0, 0, 0, 0.4)",
                padding: "0.5rem 0.75rem",
                borderRadius: "6px",
                fontSize: "0.8rem",
                color: "var(--text-secondary)",
                marginBottom: b.logs.length > 0 ? "0.75rem" : "0",
              }}
            >
              <div>
                Total: <strong style={{ color: "#ffffff" }}>{b.total_items}</strong>
              </div>
              <div>
                Executed: <strong style={{ color: "#34d399" }}>{b.executed_items}</strong>
              </div>
              <div>
                Dismissed: <strong style={{ color: "#fb7185" }}>{b.rejected_items}</strong>
              </div>
              {b.token_count && (
                <div>
                  Tokens: <strong style={{ color: "#ffffff" }}>{b.token_count}</strong>
                </div>
              )}
            </div>

            {/* Executed Object Links */}
            {b.logs.length > 0 && (
              <div style={{ marginTop: "0.75rem" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {b.logs.map((log) => (
                    <div
                      key={log.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.45rem 0.75rem",
                        background: "rgba(255, 255, 255, 0.02)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "6px",
                        fontSize: "0.8rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span
                          className={`pill ${
                            log.tool === "notion"
                              ? "pill-notion"
                              : log.tool === "jira"
                              ? "pill-jira"
                              : log.tool === "calendar"
                              ? "pill-calendar"
                              : "pill-task_ledger"
                          }`}
                          style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem" }}
                        >
                          {log.tool}
                        </span>
                        <span style={{ color: "#ffffff", fontWeight: 500 }}>
                          {log.item_description || "Action Item"}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        {log.latency_ms !== undefined && (
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {log.latency_ms}ms
                          </span>
                        )}
                        {log.external_url && (
                          <a
                            href={log.external_url}
                            target="_blank"
                            rel="noreferrer"
                            style={{
                              color: "#06b6d4",
                              fontSize: "0.75rem",
                              fontWeight: 500,
                              textDecoration: "none",
                            }}
                          >
                            Open Link ↗
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
