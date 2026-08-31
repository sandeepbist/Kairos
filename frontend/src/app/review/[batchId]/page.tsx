"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { getBatch, approveBatch } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { BatchResponse, ActionItemDecision } from "@/lib/types";
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
    const fetchStatus = async () => {
      try {
        const data = await getBatch(batchId);
        setBatch(data);
        if (data.status === "awaiting_approval" || data.status === "completed") {
          setLoading(false);
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
      } catch (err) {
        setError(errorMessage(err, "Failed to load batch review"));
        setLoading(false);
      }
    };

    fetchStatus();
    const interval: ReturnType<typeof setInterval> = setInterval(() => {
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
    } catch (err) {
      setError(errorMessage(err, "Failed to submit approvals"));
      setSubmitting(false);
    }
  };

  if (loading && (!batch || batch.status === "processing")) {
    return (
      <div className="container" style={{ textAlign: "center", padding: "8rem 0" }}>
        <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>⚡</div>
        <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#ffffff" }}>
          Extracting & Routing Action Items...
        </h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginTop: "0.5rem" }}>
          Analyzing commitments, speakers, verbatim quotes, and tool targets.
        </p>
      </div>
    );
  }

  const approvedCount = Object.values(decisions).filter((d) => d.action !== "REJECT").length;
  const rejectedCount = Object.values(decisions).filter((d) => d.action === "REJECT").length;

  return (
    <div className="container" style={{ maxWidth: "1280px", paddingBottom: "8rem" }}>
      {/* Top Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.75rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <h1 className="heading-title">Human Verification Workbench</h1>
            <span className="pill" style={{ fontSize: "0.75rem" }}>
              Batch {batchId.slice(0, 8)}
            </span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
            Hover over any action item to view its synchronized quote in the original transcript.
          </p>
        </div>

        {/* Quick Bulk Action Buttons */}
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleApproveHighConfidence}
            style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
          >
            Approve High Confidence (&ge;85%)
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleApproveAll}
            style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
          >
            Approve All ({batch?.items.length || 0})
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleRejectAll}
            style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
          >
            Dismiss All
          </button>
        </div>
      </div>

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

      {/* Split Workbench Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.25fr", gap: "1.5rem", alignItems: "start" }}>
        {/* Left Column: Source Transcript Viewer */}
        <div style={{ position: "sticky", top: "80px" }}>
          {batch && (
            <SourceSnippetViewer
              rawText={batch.raw_text}
              sourceType={batch.source_type}
              activeSnippet={hoveredSnippet}
            />
          )}
        </div>

        {/* Right Column: Action Item Candidate Cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
              Extracted Action Items ({batch?.items.length || 0})
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              {approvedCount} selected for execution
            </span>
          </div>

          {batch?.items.map((item) => (
            <ActionCard
              key={item.id}
              item={item}
              decision={decisions[item.id]}
              onDecisionChange={handleDecisionChange}
              onHoverSnippet={setHoveredSnippet}
              isHighlighted={
                Boolean(
                  hoveredSnippet &&
                    item.source_snippet &&
                    (hoveredSnippet === item.source_snippet ||
                      hoveredSnippet.includes(item.source_snippet) ||
                      item.source_snippet.includes(hoveredSnippet))
                )
              }
            />
          ))}
        </div>
      </div>

      {/* Sticky Bottom Execution Bar */}
      <div
        style={{
          position: "fixed",
          bottom: "1.5rem",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 40,
          width: "calc(100% - 3rem)",
          maxWidth: "800px",
          background: "rgba(17, 17, 17, 0.9)",
          border: "1px solid var(--border-medium)",
          borderRadius: "12px",
          padding: "0.75rem 1.25rem",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.8)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.85rem" }}>
          <span>
            Approved: <strong style={{ color: "#34d399" }}>{approvedCount}</strong>
          </span>
          <span>
            Dismissed: <strong style={{ color: "#fb7185" }}>{rejectedCount}</strong>
          </span>
        </div>

        <button
          type="button"
          onClick={handleSubmitApprovals}
          disabled={submitting || approvedCount === 0}
          className="btn btn-primary"
          style={{ padding: "0.55rem 1.25rem", fontSize: "0.875rem" }}
        >
          {submitting
            ? "Executing side-effects..."
            : `Execute ${approvedCount} Approved ${approvedCount === 1 ? "Action" : "Actions"} →`}
        </button>
      </div>
    </div>
  );
}
