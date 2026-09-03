"use client";

import React, { useEffect, useState } from "react";
import {
  armWebhookDispatch,
  createWebhook,
  deleteWebhook,
  listWebhookDeliveries,
  listWebhooks,
  rotateWebhookSecret,
  testWebhook,
  updateWebhook,
} from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { WebhookDelivery, WebhookEndpoint } from "@/lib/types";

type Notice = { text: string; type: "success" | "error" | "info" } | null;

export function WebhooksPanel() {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState<Notice>(null);
  const [secretReveal, setSecretReveal] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<Record<string, WebhookDelivery[]>>({});
  const [busy, setBusy] = useState(false);

  const load = () => {
    listWebhooks()
      .then(setEndpoints)
      .catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!url.trim()) {
      setMessage({ text: "Enter a webhook URL first", type: "error" });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const res = await createWebhook(url.trim(), description.trim(), ["*"]);
      setSecretReveal(res.secret);
      setUrl("");
      setDescription("");
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
    load();
  };

  const showDeliveries = async (id: string) => {
    const res = await listWebhookDeliveries(id).catch(() => ({ deliveries: [] }));
    setDeliveries((prev) => ({ ...prev, [id]: res.deliveries }));
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
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            className="input mono"
            placeholder="https://your-receiver.example.com/hook"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="Webhook URL"
          />
          <input
            className="input"
            placeholder="Description (n8n, Home Assistant…)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            aria-label="Webhook description"
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
              <button className="btn btn-ghost btn-sm" onClick={() => handleTest(ep.id)} disabled={busy}>
                Test
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => toggleEnabled(ep)}>
                {ep.enabled ? "Disable" : "Enable"}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => handleRotate(ep.id)} disabled={busy}>
                Rotate
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(ep.id)}>
                Delete
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => showDeliveries(ep.id)}>
                Deliveries
              </button>
            </div>
          </div>

          {deliveries[ep.id] && (
            <div style={{ marginTop: "12px" }}>
              {deliveries[ep.id].length === 0 && (
                <p className="dim" style={{ fontSize: "0.75rem" }}>No deliveries yet.</p>
              )}
              {deliveries[ep.id].map((d) => (
                <div
                  key={d.id}
                  style={{
                    display: "flex",
                    gap: "10px",
                    alignItems: "center",
                    fontSize: "0.75rem",
                    padding: "6px 0",
                    borderTop: "1px solid var(--line)",
                  }}
                >
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
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
