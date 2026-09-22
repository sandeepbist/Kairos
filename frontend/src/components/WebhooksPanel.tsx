"use client";

import React, { useEffect, useState } from "react";
import {
  armWebhookDispatch,
  createWebhook,
  deleteWebhook,
  listWebhookDeliveries,
  listWebhooks,
  redeliverDelivery,
  rotateWebhookSecret,
  testWebhook,
  updateWebhook,
} from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { WebhookDelivery, WebhookEndpoint } from "@/lib/types";

type Notice = { text: string; type: "success" | "error" | "info" } | null;

const EVENT_TYPES = [
  "action.executed",
  "action.rejected",
  "batch.completed",
  "batch.expired",
  "webhook.test",
];

function toggleEventType(selection: string[], value: string): string[] {
  if (value === "*") return ["*"];
  const withoutAll = selection.filter((v) => v !== "*");
  if (withoutAll.includes(value)) {
    const next = withoutAll.filter((v) => v !== value);
    return next.length > 0 ? next : ["*"];
  }
  return [...withoutAll, value];
}

function relativeTime(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return "";
  const abs = Math.abs(ms);
  let qty: number;
  let unit: string;
  if (abs < 60_000) {
    qty = abs / 1000;
    unit = "s";
  } else if (abs < 3_600_000) {
    qty = abs / 60_000;
    unit = "m";
  } else if (abs < 86_400_000) {
    qty = abs / 3_600_000;
    unit = "h";
  } else {
    qty = abs / 86_400_000;
    unit = "d";
  }
  const rounded = Math.max(1, Math.round(qty));
  return ms >= 0 ? `in ${rounded}${unit}` : `${rounded}${unit} ago`;
}

function EventChip({
  label,
  selected,
  mono,
  onToggle,
}: {
  label: string;
  selected: boolean;
  mono?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className={`tag${mono ? " tag-tool" : ""}`}
      aria-pressed={selected}
      onClick={onToggle}
      style={{
        cursor: "pointer",
        color: selected ? "var(--text)" : "var(--text-secondary)",
        borderColor: selected ? "var(--line-focus)" : "var(--line)",
        background: selected ? "rgba(255, 255, 255, 0.05)" : "var(--bg-raised)",
        transition: "color 140ms, border-color 140ms, background-color 140ms",
      }}
    >
      {label}
    </button>
  );
}

function EventChips({
  selection,
  onToggle,
}: {
  selection: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <>
      <EventChip
        label="All events"
        selected={selection.includes("*")}
        onToggle={() => onToggle("*")}
      />
      {EVENT_TYPES.map((t) => (
        <EventChip
          key={t}
          label={t}
          mono
          selected={selection.includes(t)}
          onToggle={() => onToggle(t)}
        />
      ))}
    </>
  );
}

export function WebhooksPanel() {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [newEventTypes, setNewEventTypes] = useState<string[]>(["*"]);
  const [message, setMessage] = useState<Notice>(null);
  const [secretReveal, setSecretReveal] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<Record<string, WebhookDelivery[]>>({});
  const [openDeliveriesId, setOpenDeliveriesId] = useState<string | null>(null);
  const [redelivering, setRedelivering] = useState<Set<string>>(new Set());
  const [editingEvents, setEditingEvents] = useState<string | null>(null);
  const [editSelection, setEditSelection] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    listWebhooks()
      .then(setEndpoints)
      .catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  // While a deliveries drawer is open, keep it fresh every 10s.
  useEffect(() => {
    if (!openDeliveriesId) return;
    const id = openDeliveriesId;
    const timer = window.setInterval(() => {
      listWebhookDeliveries(id)
        .then((res) => setDeliveries((prev) => ({ ...prev, [id]: res.deliveries })))
        .catch(() => {});
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [openDeliveriesId]);

  const handleCreate = async () => {
    if (!url.trim()) {
      setMessage({ text: "Enter a webhook URL first", type: "error" });
      return;
    }
    try {
      const parsed = new URL(url.trim());
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
        throw new Error("bad scheme");
      }
    } catch {
      setMessage({ text: "Enter a valid http(s) webhook URL", type: "error" });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const res = await createWebhook(url.trim(), description.trim(), newEventTypes);
      setSecretReveal(res.secret);
      setUrl("");
      setDescription("");
      setNewEventTypes(["*"]);
      setMessage({ text: "Endpoint registered — copy the secret now.", type: "success" });
      await armWebhookDispatch().catch(() => {});
      load();
    } catch (err) {
      setMessage({ text: errorMessage(err, "Failed to create webhook"), type: "error" });
    } finally {
      setBusy(false);
    }
  };

  const handleRotate = async (id: string) => {
    setBusy(true);
    try {
      const res = await rotateWebhookSecret(id);
      setSecretReveal(res.secret);
      setMessage({ text: "New secret issued — copy it now. The old one keeps working for 24h.", type: "info" });
      load();
    } catch (err) {
      setMessage({ text: errorMessage(err, "Failed to rotate secret"), type: "error" });
    } finally {
      setBusy(false);
    }
  };

  const handleTest = async (id: string) => {
    setBusy(true);
    try {
      await testWebhook(id);
      setMessage({ text: "Test event queued — refresh deliveries below.", type: "info" });
      const res = await listWebhookDeliveries(id);
      setDeliveries((prev) => ({ ...prev, [id]: res.deliveries }));
      setOpenDeliveriesId(id);
    } catch (err) {
      setMessage({ text: errorMessage(err, "Failed to send test"), type: "error" });
    } finally {
      setBusy(false);
    }
  };

  const toggleEnabled = async (ep: WebhookEndpoint) => {
    await updateWebhook(ep.id, { enabled: !ep.enabled }).catch(() => {});
    load();
  };

  const handleDelete = async (id: string) => {
    await deleteWebhook(id).catch(() => {});
    if (openDeliveriesId === id) setOpenDeliveriesId(null);
    if (editingEvents === id) setEditingEvents(null);
    load();
  };

  const showDeliveries = async (id: string) => {
    if (openDeliveriesId === id) {
      setOpenDeliveriesId(null);
      return;
    }
    const res = await listWebhookDeliveries(id).catch(() => ({ deliveries: [] }));
    setDeliveries((prev) => ({ ...prev, [id]: res.deliveries }));
    setOpenDeliveriesId(id);
  };

  const startEditEvents = (ep: WebhookEndpoint) => {
    if (editingEvents === ep.id) {
      setEditingEvents(null);
      return;
    }
    setEditingEvents(ep.id);
    setEditSelection(ep.event_types.length > 0 ? ep.event_types : ["*"]);
  };

  const saveEvents = async (id: string) => {
    setBusy(true);
    try {
      await updateWebhook(id, { event_types: editSelection });
      setEditingEvents(null);
      setMessage({ text: "Events updated", type: "success" });
      load();
    } catch (err) {
      setMessage({ text: errorMessage(err, "Failed to update events"), type: "error" });
    } finally {
      setBusy(false);
    }
  };

  const handleRedeliver = async (endpointId: string, deliveryId: string) => {
    setRedelivering((prev) => new Set(prev).add(deliveryId));
    try {
      await redeliverDelivery(endpointId, deliveryId);
      setMessage({ text: "Redelivery queued", type: "info" });
      const res = await listWebhookDeliveries(endpointId).catch(() => ({ deliveries: [] }));
      setDeliveries((prev) => ({ ...prev, [endpointId]: res.deliveries }));
    } catch (err) {
      setMessage({ text: errorMessage(err, "Failed to queue redelivery"), type: "error" });
    } finally {
      setRedelivering((prev) => {
        const next = new Set(prev);
        next.delete(deliveryId);
        return next;
      });
    }
  };

  const noticeClass = message
    ? message.type === "success"
      ? "notice notice-ok"
      : message.type === "error"
        ? "notice notice-error"
        : "notice notice-info"
    : "";

  return (
    <div>
      {message && (
        <div className={`${noticeClass} fade-in`} style={{ marginBottom: "12px" }}>
          {message.text}
        </div>
      )}

      {secretReveal && (
        <div className="panel" style={{ padding: "14px 16px", marginBottom: "12px" }}>
          <p className="mono-label" style={{ marginBottom: "6px" }}>
            WEBHOOK SECRET — SHOWN ONCE
          </p>
          <code className="mono" style={{ color: "var(--text-primary)", fontSize: "0.82rem", wordBreak: "break-all" }}>
            {secretReveal}
          </code>
          <p className="dim" style={{ fontSize: "0.75rem", marginTop: "8px" }}>
            Receivers verify with the official library:{" "}
            <code>pip install standardwebhooks</code> →{" "}
            <code>Webhook(&quot;{secretReveal.slice(0, 12)}…&quot;).verify(body, headers)</code>
          </p>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ marginTop: "8px" }}
            onClick={() => setSecretReveal(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="panel" style={{ padding: "16px 20px", marginBottom: "10px" }}>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <input
            className="input mono"
            placeholder="https://your-receiver.example.com/hook"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="Webhook URL"
            style={{ flex: "1 1 220px", minWidth: 0 }}
          />
          <input
            className="input"
            placeholder="Description (n8n, Home Assistant…)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            aria-label="Webhook description"
            style={{ flex: "1 1 160px", minWidth: 0 }}
          />
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleCreate}
            disabled={busy}
            style={{ flexShrink: 0 }}
          >
            Add
          </button>
        </div>
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center", marginTop: "10px" }}>
          <span className="mono-label" style={{ marginRight: "2px" }}>
            EVENTS
          </span>
          <EventChips
            selection={newEventTypes}
            onToggle={(v) => setNewEventTypes(toggleEventType(newEventTypes, v))}
          />
        </div>
      </div>

      {endpoints.map((ep) => (
        <div key={ep.id} className="panel" style={{ padding: "16px 20px", marginBottom: "10px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "9px", minWidth: 0 }}>
              <span className={`status-dot ${ep.enabled ? "status-on" : "status-off"}`} />
              <span className="h-section">{ep.description || "Webhook"}</span>
              <span className="mono dim" style={{ fontSize: "0.72rem", overflow: "hidden", textOverflow: "ellipsis" }}>
                {ep.url}
              </span>
            </div>
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleTest(ep.id)} disabled={busy}>
                Test
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => startEditEvents(ep)}
                aria-expanded={editingEvents === ep.id}
                aria-controls={`events-${ep.id}`}
              >
                Events
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleEnabled(ep)}>
                {ep.enabled ? "Disable" : "Enable"}
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleRotate(ep.id)} disabled={busy}>
                Rotate
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => handleDelete(ep.id)}
                aria-label={`Delete webhook ${ep.description || ep.url}`}
              >
                Delete
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => showDeliveries(ep.id)}
                aria-expanded={openDeliveriesId === ep.id}
                aria-controls={`deliveries-${ep.id}`}
              >
                Deliveries
              </button>
            </div>
          </div>

          {editingEvents === ep.id ? (
            <div
              id={`events-${ep.id}`}
              role="region"
              aria-label={`Event types for ${ep.description || ep.url}`}
              style={{
                marginTop: "12px",
                padding: "10px 12px",
                border: "1px solid var(--line)",
                borderRadius: "var(--r-md)",
                background: "var(--bg-raised)",
              }}
            >
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                <span className="mono-label" style={{ marginRight: "2px" }}>
                  EVENTS
                </span>
                <EventChips
                  selection={editSelection}
                  onToggle={(v) => setEditSelection(toggleEventType(editSelection, v))}
                />
              </div>
              <div style={{ display: "flex", gap: "6px", marginTop: "10px" }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => saveEvents(ep.id)}
                  disabled={busy}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setEditingEvents(null)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center", marginTop: "10px" }}>
              <span className="mono-label" style={{ marginRight: "2px" }}>
                EVENTS
              </span>
              {ep.event_types.length === 0 ? (
                <span className="tag" style={{ color: "var(--text-muted)" }}>
                  No events
                </span>
              ) : ep.event_types.includes("*") ? (
                <span className="tag">All events</span>
              ) : (
                ep.event_types.map((t) => (
                  <span key={t} className="tag tag-tool">
                    {t}
                  </span>
                ))
              )}
            </div>
          )}

          {openDeliveriesId === ep.id && deliveries[ep.id] && (
            <div
              id={`deliveries-${ep.id}`}
              role="region"
              aria-label={`Deliveries for ${ep.description || ep.url}`}
              style={{ marginTop: "12px" }}
            >
              {deliveries[ep.id].length === 0 && (
                <p className="dim" style={{ fontSize: "0.75rem" }}>No deliveries yet.</p>
              )}
              {deliveries[ep.id].map((d) => (
                <div
                  key={d.id}
                  style={{
                    padding: "8px 0",
                    fontSize: "0.75rem",
                    borderTop: "1px solid var(--line)",
                  }}
                >
                  <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                    <span className="mono dim">{d.event_type}</span>
                    <span
                      className="tag"
                      style={{
                        color:
                          d.status === "delivered" ? "var(--ok)" : d.status === "failed" ? "var(--warn)" : "var(--text-muted)",
                        borderColor: "var(--line)",
                      }}
                    >
                      {d.status.toUpperCase()}
                    </span>
                    <span className="dim">attempt {d.attempts}</span>
                    {d.last_response_code !== null && <span className="dim">HTTP {d.last_response_code}</span>}
                    {d.next_retry_at && <span className="dim">retries {relativeTime(d.next_retry_at)}</span>}
                    {(d.status === "failed" || d.status === "delivered") && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ marginLeft: "auto" }}
                        onClick={() => handleRedeliver(ep.id, d.id)}
                        disabled={redelivering.has(d.id)}
                      >
                        Redeliver
                      </button>
                    )}
                  </div>
                  {d.last_error && (
                    <div
                      className="mono"
                      title={d.last_error}
                      style={{
                        color: "var(--err)",
                        fontSize: "0.72rem",
                        marginTop: "4px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {d.last_error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
