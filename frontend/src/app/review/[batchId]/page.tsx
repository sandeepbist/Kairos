"use client";

import React, { useEffect, useMemo, useRef, useState, use } from "react";
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
  // Keyboard focus index into `items` (review mode only), plus a per-item
  // counter used to ask a card to open its payload editor.
  const [focusedIdx, setFocusedIdx] = useState<number | null>(null);
  const [editSignals, setEditSignals] = useState<Record<string, number>>({});

  const fetchStatusRef = useRef<() => void>(() => {});
  const batchStatusRef = useRef<string | null>(null);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Hoisted above the effects: the keyboard effect (below) and the outcome
  // counts (below the loading gate) share them. Memoized so the keyboard
  // effect's deps stay referentially stable.
  const items = useMemo(() => batch?.items ?? [], [batch]);
  const isReviewable = batch?.status === "awaiting_approval";

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

  // Live progress via SSE while the batch is processing. The server
  // deliberately closes idle/terminal streams, so a dropped connection is
  // normal: reconnect with capped backoff and stop once the batch is
  // terminal. Polling remains the silent safety net; no UI is shown for
  // connection state.
  useEffect(() => {
    if (!batchId) return;

    const TERMINAL_STATUSES = ["completed", "failed", "expired"];
    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let backoffMs = 1000;
    const MAX_BACKOFF_MS = 10000;

    const stop = () => {
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      source?.close();
      source = null;
    };

    const connect = () => {
      if (TERMINAL_STATUSES.includes(batchStatusRef.current ?? "")) return;
      source = new EventSource(`/api/batches/${batchId}/events`);
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
        // A delivered message proves the stream is healthy.
        backoffMs = 1000;
      };
      source.onerror = () => {
        // Schedule a fresh EventSource (the old one is dead after error).
        source?.close();
        source = null;
        if (retryTimer !== null) clearTimeout(retryTimer);
        retryTimer = setTimeout(() => {
          retryTimer = null;
          if (TERMINAL_STATUSES.includes(batchStatusRef.current ?? "")) return;
          backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
          connect();
        }, backoffMs);
      };
    };

    connect();

    return stop;
  }, [batchId]);

  // Keyboard shortcuts, review mode only: j/k move focus between cards,
  // Enter/a approve the focused card, x/d dismiss it, e opens its payload
  // editor. Guards: no shortcuts while a dialog is open, while typing in a
  // form control, on held-repeat, or with modifier keys.
  useEffect(() => {
    if (!isReviewable) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.isContentEditable ||
          ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        return;
      }
      // PayloadModal (and any future dialog) renders role="dialog"; while a
      // dialog owns the keyboard, page shortcuts stand down. (Native
      // window.confirm blocks keydown entirely, so it needs no guard.)
      if (document.querySelector('[role="dialog"]')) return;
      if (items.length === 0) return;

      const key = e.key.toLowerCase();

      if (key === "j" || key === "k") {
        e.preventDefault();
        const current = focusedIdx ?? -1;
        // First press lands on the first card; further presses clamp at the
        // ends rather than wrapping.
        const next =
          current === -1 ? 0 : Math.min(items.length - 1, Math.max(0, current + (key === "j" ? 1 : -1)));
        setFocusedIdx(next);
        // Ride the existing hover pipeline so the source pane follows.
        setHoveredSnippet(items[next].source_snippet);
        cardRefs.current[items[next].id]?.scrollIntoView({ block: "nearest" });
        return;
      }

      if (focusedIdx === null) return;
      const item = items[focusedIdx];
      if (!item) return;

      if (key === "enter" || key === "a") {
        // Enter on a focused button is a native click — don't hijack it.
        if (key === "enter" && target?.tagName === "BUTTON") return;
        e.preventDefault();
        setDecisions((prev) => ({
          ...prev,
          [item.id]: {
            item_id: item.id,
            action: "APPROVE",
            override_tool: prev[item.id]?.override_tool || item.suggested_tool,
            modified_payload: prev[item.id]?.modified_payload || item.tool_payload,
          },
        }));
      } else if (key === "x" || key === "d") {
        e.preventDefault();
        setDecisions((prev) => ({
          ...prev,
          [item.id]: {
            item_id: item.id,
            action: "REJECT",
            rejection_reason: "Dismissed by user during review",
            // Preserved so a later re-approve restores the edits.
            override_tool: prev[item.id]?.override_tool,
            modified_payload: prev[item.id]?.modified_payload,
          },
        }));
      } else if (key === "e") {
        e.preventDefault();
        setEditSignals((prev) => ({ ...prev, [item.id]: (prev[item.id] ?? 0) + 1 }));
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isReviewable, items, focusedIdx]);

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
      updated[item.id] = isHigh
        ? {
            item_id: item.id,
            action: "APPROVE",
            // Preserve any operator tool override / payload edits so the
            // bulk action never silently wipes per-card adjustments.
            override_tool: decisions[item.id]?.override_tool || item.suggested_tool,
            modified_payload: decisions[item.id]?.modified_payload || item.tool_payload,
          }
        : {
            item_id: item.id,
            action: "REJECT",
            rejection_reason: "Below confidence threshold",
            // Kept so a later re-approve restores the operator's
            // override instead of falling back to the suggestion. The
            // workflow's reject path ignores these fields.
            override_tool: decisions[item.id]?.override_tool,
            modified_payload: decisions[item.id]?.modified_payload,
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
        // Preserved (not sent down the reject path) so a later
        // re-approve restores the operator's override/payload edits.
        override_tool: decisions[item.id]?.override_tool,
        modified_payload: decisions[item.id]?.modified_payload,
      };
    });
    setDecisions(updated);
  };

  const handleSubmitApprovals = async () => {
    if (!batch) return;
    setSubmitting(true);
    setError(null);

    const decisionsList = Object.values(decisions).filter(
      // Prune decisions for items no longer in the batch (stale tabs):
      // the workflow validator rejects the whole payload on any unknown id.
      (d) => batch.items.some((i) => i.id === d.item_id)
    );
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

  // Per-item outcome counts for the read-only banner on terminal batches.
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
            {failedItemCount > 0 ? (
              <>
                {", "}
                <strong style={{ color: "var(--err)", fontWeight: 580 }}>
                  {failedItemCount} failed
                </strong>
                .
              </>
            ) : (
              "."
            )}
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
          {isReviewable && (
            <p className="mono-label dim hide-narrow" style={{ marginTop: "10px" }}>
              J/K move · A approve · X dismiss · E edit
            </p>
          )}
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
      <div className="rise rise-1 review-grid">
        {/* Left: source */}
        <div className="review-source">
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
            <div
              key={item.id}
              ref={(el) => {
                cardRefs.current[item.id] = el;
              }}
            >
              <ActionCard
                item={item}
                decision={decisions[item.id]}
                readOnly={!isReviewable}
                onDecisionChange={handleDecisionChange}
                onHoverSnippet={setHoveredSnippet}
                editSignal={editSignals[item.id]}
                isHighlighted={Boolean(
                  hoveredSnippet &&
                    item.source_snippet &&
                    (hoveredSnippet === item.source_snippet ||
                      hoveredSnippet.includes(item.source_snippet) ||
                      item.source_snippet.includes(hoveredSnippet))
                )}
              />
            </div>
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
            disabled={submitting || Object.keys(decisions).length === 0}
            className="btn btn-primary"
          >
            {submitting ? (
              <>
                <span className="spinner" /> Executing
              </>
            ) : approvedCount === 0 ? (
              `Dismiss ${rejectedCount} ${rejectedCount === 1 ? "action" : "actions"}`
            ) : (
              `Execute ${approvedCount} ${approvedCount === 1 ? "action" : "actions"}`
            )}
          </button>
        </div>
      )}
    </div>
  );
}
