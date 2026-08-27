"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { getBatch, approveBatch } from "@/lib/api";
import { BatchResponse, ActionItemDecision, ActionItem } from "@/lib/types";
import { ActionCard } from "@/components/ActionCard";
import { SourceSnippetViewer } from "@/components/SourceSnippetViewer";

export default function ReviewPage({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);
  const batchId = resolvedParams.batchId;

  const [batch, setBatch] = useState<BatchResponse | null>(null);
  const [decisions, setDecisions] = useState<Record<string, ActionItemDecision>>({});
  const [hoveredSnippet, setHoveredSnippet] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll batch status until awaiting_approval
  useEffect(() => {
    let interval: NodeJS.Timeout;
    const fetchStatus = async () => {
      try {
        const data = await getBatch(batchId);
        setBatch(data);
        if (data.status === "awaiting_approval" || data.status === "completed") {
          setLoading(false);
          // Initialize default approvals if not yet populated
          setDecisions((prev) => {
            if (Object.keys(prev).length === 0 && data.items.length > 0) {
              const initialMap: Record<string, ActionItemDecision> = {};
              data.items.forEach((item) => {
                initialMap[item.id] = {
                  item_id: item.id,
                  action: "APPROVE",
                  override_tool: item.suggested_tool,
                  modified_payload: item.tool_payload,
                };
              });
              return initialMap;
            }
            return prev;
          });
        }
      } catch (err: any) {
        setError(err.message || "Failed to load batch review");
        setLoading(false);
      }
    };

    fetchStatus();
    interval = setInterval(() => {
      setBatch((curr) => {
        if (!curr || curr.status === "processing" || curr.status === "executing") {
          fetchStatus();
        }
        return curr;
      });
    }, 1500);

    return () => clearInterval(interval);
  }, [batchId]);

  const handleDecisionChange = (decision: ActionItemDecision) => {
    setDecisions((prev) => ({
      ...prev,
      [decision.item_id]: decision,
    }));
  };

  const handleApproveAll = () => {
    if (!batch) return;
    const updated: Record<string, ActionItemDecision> = {};
    batch.items.forEach((item) => {
      updated[item.id] = {
        item_id: item.id,
        action: "APPROVE",
        override_tool: decisions[item.id]?.override_tool || item.suggested_tool,
        modified_payload: decisions[item.id]?.modified_payload || item.tool_payload,
      };
    });
    setDecisions(updated);
  };

  const handleApproveHighConfidence = () => {
    if (!batch) return;
    const updated: Record<string, ActionItemDecision> = {};
    batch.items.forEach((item) => {
      const isHigh = item.confidence >= 0.85;
      updated[item.id] = {
        item_id: item.id,
        action: isHigh ? "APPROVE" : "REJECT",
        rejection_reason: isHigh ? undefined : "Flagged for manual review",
      };
    });
    setDecisions(updated);
  };

  const handleRejectAll = () => {
    if (!batch) return;
    const updated: Record<string, ActionItemDecision> = {};
    batch.items.forEach((item) => {
      updated[item.id] = {
        item_id: item.id,
        action: "REJECT",
        rejection_reason: "Bulk dismissed by user",
      };
    });
    setDecisions(updated);
  };

  const handleSubmitApprovals = async () => {
    if (!batch) return;
    setSubmitting(true);
    setError(null);

    const decisionsList = Object.values(decisions);
    try {
      await approveBatch(batchId, decisionsList);
      router.push("/history");
    } catch (err: any) {
      setError(err.message || "Failed to submit approvals");
      setSubmitting(false);
    }
  };

  if (loading && (!batch || batch.status === "processing")) {
    return (
      <div className="container" style={{ textAlign: "center", padding: "6rem 0" }}>
        <div className="pulse-indicator" style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚡</div>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Extracting & Routing Action Items...</h2>
        <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
          LangGraph is analyzing commitments, provenance snippets, and Mem0 routing memory.
        </p>
      </div>
    );
  }

  if (error && !batch) {
    return (
      <div className="container" style={{ textAlign: "center", padding: "6rem 0" }}>
        <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚠️</div>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#fb7185" }}>Could not load batch</h2>
        <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>{error}</p>
        <button onClick={() => router.push("/")} className="btn btn-secondary" style={{ marginTop: "1.5rem" }}>
          Return to Ingest
        </button>
      </div>
    );
  }

  const approvedCount = Object.values(decisions).filter((d) => d.action !== "REJECT").length;
  const rejectedCount = Object.values(decisions).filter((d) => d.action === "REJECT").length;

  return (
    <div className="container" style={{ maxWidth: "1400px" }}>
      {/* Top Review Header & Bulk Actions Bar */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "1rem",
        marginBottom: "1.5rem",
        paddingBottom: "1.25rem",
        borderBottom: "1px solid var(--border-subtle)",
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Review & Approve Action Items</h1>
            <span className="badge" style={{ background: "rgba(56, 189, 248, 0.15)", color: "#38bdf8" }}>
              Batch: {batchId.slice(0, 8)}
            </span>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
            Verify extracted items against source quotes on the left. Hover any card to highlight its source snippet.
          </p>
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <button onClick={handleApproveHighConfidence} className="btn btn-secondary" style={{ fontSize: "0.8rem", padding: "0.4rem 0.75rem" }}>
            Approve High Confidence (&ge;85%)
          </button>
          <button onClick={handleApproveAll} className="btn btn-secondary" style={{ fontSize: "0.8rem", padding: "0.4rem 0.75rem" }}>
            Approve All ({batch?.items.length || 0})
          </button>
          <button onClick={handleRejectAll} className="btn btn-secondary" style={{ fontSize: "0.8rem", padding: "0.4rem 0.75rem" }}>
            Reject All
          </button>
          <button
            onClick={handleSubmitApprovals}
            disabled={submitting}
            className="btn btn-primary"
            style={{ padding: "0.5rem 1.5rem", fontSize: "0.9rem" }}
          >
            {submitting ? "Dispatching..." : `🚀 Execute (${approvedCount} Approved, ${rejectedCount} Rejected)`}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          padding: "0.75rem 1rem",
          borderRadius: "6px",
          background: "rgba(244, 63, 94, 0.15)",
          border: "1px solid rgba(244, 63, 94, 0.3)",
          color: "#fb7185",
          fontSize: "0.875rem",
          marginBottom: "1.5rem",
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Side-by-Side Review Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1.25fr",
        gap: "1.5rem",
        alignItems: "start",
      }}>
        {/* Left Column: Synchronized Source Viewer */}
        <div>
          <SourceSnippetViewer
            rawText={batch?.raw_text || ""}
            sourceType={batch?.source_type || "meeting_transcript"}
            activeSnippet={hoveredSnippet}
          />
        </div>

        {/* Right Column: Stack of Action Items */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {batch?.items.map((item) => (
            <ActionCard
              key={item.id}
              item={item}
              decision={decisions[item.id]}
              onDecisionChange={handleDecisionChange}
              onHoverSnippet={setHoveredSnippet}
              isHighlighted={hoveredSnippet === item.source_snippet}
            />
          ))}

          {batch?.items.length === 0 && (
            <div className="glass-panel" style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
              No action items detected in this input text.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
