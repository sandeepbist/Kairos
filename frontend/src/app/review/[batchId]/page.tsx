"use client";

import React, { useEffect, useRef, useState, use } from "react";
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
  const [progress, setProgress] = useState<string | null>(null);

  const fetchStatusRef = useRef<() => void>(() => {});
  const batchStatusRef = useRef<string | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await getBatch(batchId);
      setBatch(data);
      batchStatusRef.current = data.status;
      if (data.status !== "processing") {
        setLoading(false);
      }
      if (data.status === "awaiting_approval") {
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

  // Poll batch status until awaiting_approval (SSE augments this; polling
  // remains the always-available fallback).
  useEffect(() => {
    fetchStatusRef.current = fetchStatus;
    const initialFetch = setTimeout(fetchStatus, 0);
    const interval: ReturnType<typeof setInterval> = setInterval(() => {
      const status = batchStatusRef.current;
      if (!status || status === "processing" || status === "executing") {
        fetchStatusRef.current();
      }
    }, 1500);

    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId]);

  // Live progress via SSE while the batch is processing (falls back to
  // polling silently if the stream is unavailable).
  useEffect(() => {
    if (!batchId) return;
    const source = new EventSource(`/api/batches/${batchId}/events`);
    source.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as { type: string; message: string };
        setProgress(event.message || event.type);
        if (event.type === "awaiting_review") {
          fetchStatusRef.current();
        }
      } catch {
        // malformed event: ignore, polling covers us
      }
    };
    source.onerror = () => source.close();
    return () => source.close();
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
        rejection_reason: isHigh ? undefined : "Below confidence threshold",
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
      <div className="container" style={{ maxWidth: "760px" }}>
        <div style={{ marginBottom: "36px", display: "flex", alignItems: "center", gap: "12px" }}>
          <span className="spinner" />
          <div>
            <p className="h-title">Extracting actions</p>
            <p className="dim" style={{ fontSize: "0.84rem", marginTop: "2px" }}>
              {progress ?? "Identifying commitments, speakers, and routing targets."}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div className="skeleton" style={{ height: "132px", borderRadius: "var(--r-lg)" }} />
          <div className="skeleton" style={{ height: "132px", borderRadius: "var(--r-lg)" }} />
          <div className="skeleton" style={{ height: "132px", borderRadius: "var(--r-lg)" }} />
        </div>
      </div>
    );
  }

  const approvedCount = Object.values(decisions).filter((d) => d.action !== "REJECT").length;
  const rejectedCount = Object.values(decisions).filter((d) => d.action === "REJECT").length;
  const isReviewable = batch?.status === "awaiting_approval";

  // Per-item outcome counts for the read-only banner on terminal batches.
  const items = batch?.items ?? [];
  const executedCount = items.filter((i) => i.status === "executed").length;
  const failedItemCount = items.filter((i) => i.status === "failed").length;
  const ranCount = executedCount + failedItemCount;
  const dismissedCount = items.filter((i) => i.status === "rejected").length;

  const outcomeBanner = !batch || isReviewable ? null : (
    <div
      className={`notice ${batch.status === "failed" ? "notice-error" : batch.status === "completed" ? "notice-ok" : "notice-info"}`}
      style={{ alignItems: "center" }}
    >
      {batch.status === "executing" ? (
        <span className="status-dot status-warn status-live" />
      ) : (
        <span
          className={`status-dot ${
            batch.status === "completed"
              ? "status-on"
              : batch.status === "failed"
                ? "status-err"
                : "status-off"
          }`}
        />
      )}
      <span>
        {batch.status === "completed" && (
          <>
            Executed — {ranCount} {ranCount === 1 ? "action" : "actions"} ran
            {dismissedCount > 0 ? `, ${dismissedCount} dismissed` : ""}
            {failedItemCount > 0 ? `, ${failedItemCount} failed` : ""}.
          </>
        )}
        {batch.status === "expired" && <>Expired — approval timed out after 7 days.</>}
        {batch.status === "failed" && <>Failed — extraction did not complete.</>}
        {batch.status === "executing" && <>Executing — actions are running now.</>}
      </span>
    </div>
  );

  return (
    <div className="container" style={{ maxWidth: "1240px" }}>
      {/* Header */}
      <div
        className="rise"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          marginBottom: "26px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <p className="mono-label" style={{ marginBottom: "8px" }}>
            BATCH {batchId.slice(0, 8)}
          </p>
          <h1 className="h-title" style={{ fontSize: "1.4rem" }}>
            Review extracted actions
          </h1>
          <p className="dim" style={{ fontSize: "0.84rem", marginTop: "4px" }}>
            Hover a card to locate its quote in the source. Nothing executes until you approve.
          </p>
        </div>

        {isReviewable && (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleApproveHighConfidence}>
              Approve high confidence
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleApproveAll}>
              Approve all
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleRejectAll}>
              Dismiss all
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="notice notice-error" style={{ marginBottom: "20px" }}>
          {error}
        </div>
      )}

      {/* Read-only outcome banner for terminal / mid-execution batches */}
      {outcomeBanner && <div className="rise" style={{ marginBottom: "20px" }}>{outcomeBanner}</div>}

      {/* Workbench grid */}
      <div
        className="rise rise-1"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.25fr)",
          gap: "18px",
          alignItems: "start",
        }}
      >
        {/* Left: source */}
        <div style={{ position: "sticky", top: "80px" }}>
          {batch && (
            <SourceSnippetViewer
              rawText={batch.raw_text}
              sourceType={batch.source_type}
              activeSnippet={hoveredSnippet}
            />
          )}
        </div>

        {/* Right: cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {batch?.items.map((item) => (
            <ActionCard
              key={item.id}
              item={item}
              decision={decisions[item.id]}
              readOnly={!isReviewable}
              onDecisionChange={handleDecisionChange}
              onHoverSnippet={setHoveredSnippet}
              isHighlighted={Boolean(
                hoveredSnippet &&
                  item.source_snippet &&
                  (hoveredSnippet === item.source_snippet ||
                    hoveredSnippet.includes(item.source_snippet) ||
                    item.source_snippet.includes(hoveredSnippet))
              )}
            />
          ))}
        </div>
      </div>

      {/* Sticky execution bar */}
      {isReviewable && (
        <div
          className="fade-in"
          style={{
            position: "fixed",
            bottom: "20px",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 40,
            width: "min(560px, calc(100% - 32px))",
            background: "var(--bg-raised)",
            border: "1px solid var(--line-strong)",
            borderRadius: "var(--r-lg)",
            padding: "10px 10px 10px 18px",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            boxShadow: "0 16px 48px -12px rgba(0, 0, 0, 0.8)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "14px",
          }}
        >
          <div style={{ display: "flex", gap: "18px", fontSize: "0.82rem" }} className="muted">
            <span>
              <strong style={{ color: "var(--ok)", fontWeight: 580 }}>{approvedCount}</strong> approved
            </span>
            <span>
              <strong style={{ color: "var(--err)", fontWeight: 580 }}>{rejectedCount}</strong> dismissed
            </span>
          </div>

          <button
            type="button"
            onClick={handleSubmitApprovals}
            disabled={submitting || approvedCount === 0}
            className="btn btn-primary"
          >
            {submitting ? (
              <>
                <span className="spinner" /> Executing
              </>
            ) : (
              `Execute ${approvedCount} ${approvedCount === 1 ? "action" : "actions"}`
            )}
          </button>
        </div>
      )}
    </div>
  );
}
