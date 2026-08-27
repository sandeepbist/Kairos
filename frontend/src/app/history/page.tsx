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
      return <span className="badge badge-confidence-high">✓ Completed</span>;
    }
    if (status === "executing") {
      return <span className="badge" style={{ background: "rgba(56, 189, 248, 0.15)", color: "#38bdf8" }}>⚡ Executing</span>;
    }
    if (status === "awaiting_approval") {
      return <span className="badge badge-confidence-medium">⏸ Awaiting Review</span>;
    }
    if (status === "expired") {
      return <span className="badge" style={{ background: "rgba(255, 255, 255, 0.1)", color: "#94a3b8" }}>⏰ Auto-Expired</span>;
    }
    return <span className="badge badge-confidence-low">✗ {status}</span>;
  };

  return (
    <div className="container" style={{ maxWidth: "1100px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
        <div>
          <h1 style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
            Execution History & Side-Effects
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginTop: "0.25rem" }}>
            Audit log of all processed batches, real object URLs, and execution metrics.
          </p>
        </div>

        <Link href="/" className="btn btn-primary" style={{ padding: "0.5rem 1.25rem", fontSize: "0.875rem" }}>
          + New Ingestion Batch
        </Link>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: "4rem 0", color: "var(--text-muted)" }}>
          Loading execution history...
        </div>
      )}

      {error && (
        <div style={{
          padding: "1rem",
          borderRadius: "8px",
          background: "rgba(244, 63, 94, 0.15)",
          border: "1px solid rgba(244, 63, 94, 0.3)",
          color: "#fb7185",
          marginBottom: "1.5rem",
        }}>
          ⚠️ {error}
        </div>
      )}

      {!loading && history.length === 0 && (
        <div className="glass-panel" style={{ padding: "4rem", textAlign: "center" }}>
          <span style={{ fontSize: "2.5rem", display: "block", marginBottom: "0.75rem" }}>📭</span>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>No execution history yet</h3>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.4rem" }}>
            Ingest your first meeting transcript or email thread to execute real side-effects.
          </p>
          <Link href="/" className="btn btn-primary" style={{ marginTop: "1.25rem" }}>
            Ingest Conversation
          </Link>
        </div>
      )}

      {/* Batch History Cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {history.map((b) => (
          <div key={b.batch_id} className="glass-panel" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem", marginBottom: "1rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ fontSize: "1.2rem" }}>📦</span>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <strong style={{ fontSize: "1rem" }}>Batch {b.batch_id.slice(0, 8)}</strong>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                      ({b.source_type.replace("_", " ")})
                    </span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {b.created_at ? new Date(b.created_at).toLocaleString() : "Recently"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                {getStatusPill(b.status)}
                {b.status === "awaiting_approval" && (
                  <Link href={`/review/${b.batch_id}`} className="btn btn-primary" style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}>
                    Review Items &rarr;
                  </Link>
                )}
              </div>
            </div>

            {/* Execution Stats */}
            <div style={{
              display: "flex",
              gap: "1.5rem",
              background: "rgba(0, 0, 0, 0.25)",
              padding: "0.75rem 1rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              marginBottom: b.logs.length > 0 ? "1rem" : "0",
            }}>
              <div>Total Actions: <strong style={{ color: "var(--text-primary)" }}>{b.total_items}</strong></div>
              <div>Executed: <strong style={{ color: "#34d399" }}>{b.executed_items}</strong></div>
              <div>Rejected: <strong style={{ color: "#fb7185" }}>{b.rejected_items}</strong></div>
              {b.token_count && <div>Tokens: <strong style={{ color: "var(--text-primary)" }}>{b.token_count}</strong></div>}
            </div>

            {/* Executed Object Links */}
            {b.logs.length > 0 && (
              <div style={{ marginTop: "1rem" }}>
                <h4 style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                  Created External Objects & Links:
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {b.logs.map((log) => (
                    <div
                      key={log.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.5rem 0.75rem",
                        background: "rgba(255, 255, 255, 0.02)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "6px",
                        fontSize: "0.85rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                        <span className={`badge badge-tool-${log.tool}`}>
                          {log.tool}
                        </span>
                        <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                          {log.item_description || "Action Item"}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        {log.latency_ms !== undefined && (
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            ⏱️ {log.latency_ms}ms
                          </span>
                        )}
                        {log.external_url && (
                          <a
                            href={log.external_url.startsWith("http") ? log.external_url : "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              color: "var(--accent-cyan)",
                              fontSize: "0.8rem",
                              fontWeight: 600,
                              textDecoration: "underline",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "0.25rem",
                            }}
                          >
                            Open Live Object ↗
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
