"use client";

import React, { useEffect, useState } from "react";
import { getConnectorsStatus, toggleSandbox, saveOAuthToken } from "@/lib/api";
import { ConnectorsStatusResponse } from "@/lib/types";

export default function SettingsPage() {
  const [status, setStatus] = useState<ConnectorsStatusResponse | null>(null);
  const [sandboxEnabled, setSandboxEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // Live Token State
  const [jiraToken, setJiraToken] = useState("");
  const [notionToken, setNotionToken] = useState("");
  const [calendarToken, setCalendarToken] = useState("");
  const [savingProvider, setSavingProvider] = useState<string | null>(null);

  const loadStatus = () => {
    getConnectorsStatus()
      .then((data) => {
        setStatus(data);
        setSandboxEnabled(data.sandbox_mode);
      })
      .catch(() => {});
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleToggleSandbox = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const next = !sandboxEnabled;
      const res = await toggleSandbox(next);
      setSandboxEnabled(res.sandbox_mode);
      setMessage({
        text: `Sandbox Mode is now ${res.sandbox_mode ? "ENABLED (Offline Mock Emulation)" : "DISABLED (Live Production APIs & MCP Servers)"}`,
        type: "info",
      });
      loadStatus();
    } catch (err: any) {
      setMessage({ text: "Failed to update sandbox mode", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveToken = async (provider: string, tokenValue: string) => {
    if (!tokenValue.trim()) {
      setMessage({ text: `Please enter a valid token for ${provider}`, type: "error" });
      return;
    }
    setSavingProvider(provider);
    setMessage(null);
    try {
      await saveOAuthToken(provider, tokenValue.trim());
      setMessage({
        text: `Successfully encrypted and saved ${provider.toUpperCase()} credentials into PostgreSQL Vault!`,
        type: "success",
      });
      if (provider === "jira") setJiraToken("");
      if (provider === "notion") setNotionToken("");
      if (provider === "google_calendar") setCalendarToken("");
      loadStatus();
    } catch (err: any) {
      setMessage({ text: err.message || `Failed to save ${provider} token`, type: "error" });
    } finally {
      setSavingProvider(null);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "980px" }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
          Connectors, OAuth Vault & Live Mode Settings
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginTop: "0.25rem" }}>
          Configure live Model Context Protocol (MCP) servers, encrypted OAuth 2.1 credentials, and demo sandboxing.
        </p>
      </div>

      {message && (
        <div style={{
          padding: "0.75rem 1rem",
          borderRadius: "8px",
          background: message.type === "success" ? "rgba(16, 185, 129, 0.15)" : message.type === "error" ? "rgba(244, 63, 94, 0.15)" : "rgba(56, 189, 248, 0.15)",
          border: `1px solid ${message.type === "success" ? "rgba(16, 185, 129, 0.3)" : message.type === "error" ? "rgba(244, 63, 94, 0.3)" : "rgba(56, 189, 248, 0.3)"}`,
          color: message.type === "success" ? "#34d399" : message.type === "error" ? "#fb7185" : "#38bdf8",
          fontSize: "0.875rem",
          marginBottom: "1.5rem",
        }}>
          {message.type === "success" ? "✓" : message.type === "error" ? "⚠️" : "ℹ️"} {message.text}
        </div>
      )}

      {/* Sandbox Mode Toggle Card */}
      <div className="glass-panel" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Execution Mode</h3>
              <span className="badge" style={{ background: sandboxEnabled ? "rgba(245, 158, 11, 0.2)" : "rgba(16, 185, 129, 0.2)", color: sandboxEnabled ? "#fbbf24" : "#34d399" }}>
                {sandboxEnabled ? "Sandbox (Offline Emulation)" : "Live Production APIs"}
              </span>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.35rem", maxWidth: "600px" }}>
              {sandboxEnabled
                ? "Sandbox Mode allows offline demos without requiring live Notion, Jira, or Google Calendar API keys. All responses simulate real schemas and latency."
                : "Live Mode executes real HTTP REST calls and MCP requests to Atlassian Jira, Notion API v1, and Google Calendar API v3 using credentials from the OAuth Vault below."}
            </p>
          </div>

          <button
            onClick={handleToggleSandbox}
            disabled={saving}
            className={`btn ${sandboxEnabled ? "btn-secondary" : "btn-primary"}`}
            style={{ padding: "0.6rem 1.25rem", fontSize: "0.875rem" }}
          >
            {saving ? "Updating..." : sandboxEnabled ? "Switch to Live Production Mode" : "Switch to Sandbox Mode"}
          </button>
        </div>
      </div>

      {/* Live OAuth Credentials Vault */}
      <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "1rem" }}>
        🔐 Encrypted OAuth Vault & Production Credentials
      </h3>
      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1.25rem" }}>
        Tokens entered here are encrypted via AES-256 Fernet before storage in PostgreSQL and used for live API calls when Sandbox Mode is disabled.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.25rem", marginBottom: "2.5rem" }}>
        {/* Notion Token Form */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <span style={{ fontWeight: 700, color: "#c084fc", fontSize: "0.95rem" }}>Notion Integration Token (secret_...)</span>
            {status?.connectors?.notion?.oauth_connected && (
              <span className="badge badge-confidence-high">✓ Connected in Vault</span>
            )}
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
            Create an internal integration at <a href="https://www.notion.so/my-integrations" target="_blank" rel="noreferrer" style={{ color: "#c084fc", textDecoration: "underline" }}>notion.so/my-integrations</a> and paste the internal secret.
          </p>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="password"
              placeholder="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              value={notionToken}
              onChange={(e) => setNotionToken(e.target.value)}
              style={{
                flex: 1,
                padding: "0.5rem 0.75rem",
                borderRadius: "6px",
                background: "rgba(0, 0, 0, 0.4)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-primary)",
                fontSize: "0.85rem",
              }}
            />
            <button
              onClick={() => handleSaveToken("notion", notionToken)}
              disabled={savingProvider === "notion"}
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem", padding: "0.5rem 1rem" }}
            >
              {savingProvider === "notion" ? "Saving..." : "Save Notion Token"}
            </button>
          </div>
        </div>

        {/* Jira Token Form */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <span style={{ fontWeight: 700, color: "#60a5fa", fontSize: "0.95rem" }}>Atlassian Jira API Token / Bearer Token</span>
            {status?.connectors?.jira?.oauth_connected && (
              <span className="badge badge-confidence-high">✓ Connected in Vault</span>
            )}
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
            Generate an API token from <a href="https://id.atlassian.com/manage-profile/security/api-tokens" target="_blank" rel="noreferrer" style={{ color: "#60a5fa", textDecoration: "underline" }}>Atlassian Security Settings</a>.
          </p>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="password"
              placeholder="ATATT3xFfGF0xxxxxxxxxxxxxxxxxxxxxxxx"
              value={jiraToken}
              onChange={(e) => setJiraToken(e.target.value)}
              style={{
                flex: 1,
                padding: "0.5rem 0.75rem",
                borderRadius: "6px",
                background: "rgba(0, 0, 0, 0.4)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-primary)",
                fontSize: "0.85rem",
              }}
            />
            <button
              onClick={() => handleSaveToken("jira", jiraToken)}
              disabled={savingProvider === "jira"}
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem", padding: "0.5rem 1rem" }}
            >
              {savingProvider === "jira" ? "Saving..." : "Save Jira Token"}
            </button>
          </div>
        </div>

        {/* Google Calendar Token Form */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <span style={{ fontWeight: 700, color: "#34d399", fontSize: "0.95rem" }}>Google Calendar OAuth Access Token</span>
            {status?.connectors?.calendar?.oauth_connected && (
              <span className="badge badge-confidence-high">✓ Connected in Vault</span>
            )}
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
            Google Calendar v3 OAuth Bearer access token with <code>https://www.googleapis.com/auth/calendar.events</code> scope.
          </p>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="password"
              placeholder="ya29.a0AfH6SMxxxxxxxxxxxxxxxxxxxxxxxx"
              value={calendarToken}
              onChange={(e) => setCalendarToken(e.target.value)}
              style={{
                flex: 1,
                padding: "0.5rem 0.75rem",
                borderRadius: "6px",
                background: "rgba(0, 0, 0, 0.4)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-primary)",
                fontSize: "0.85rem",
              }}
            />
            <button
              onClick={() => handleSaveToken("google_calendar", calendarToken)}
              disabled={savingProvider === "google_calendar"}
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem", padding: "0.5rem 1rem" }}
            >
              {savingProvider === "google_calendar" ? "Saving..." : "Save Calendar Token"}
            </button>
          </div>
        </div>
      </div>

      {/* Connected MCP Servers Grid */}
      <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "1rem" }}>
        Connected MCP Tool Ecosystem
      </h3>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
        {/* Notion */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#c084fc" }}>Notion API / MCP</span>
            <span className="badge badge-confidence-high">🟢 Active</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Official Notion API v1 & Model Context Protocol. Creates database pages with rich text blocks and returns real URLs.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>Notion API v1 / SSE</code> • Target: <code>api.notion.so</code>
          </div>
        </div>

        {/* Jira */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#60a5fa" }}>Atlassian Jira REST API v3</span>
            <span className="badge badge-confidence-high">🟢 Active</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Atlassian Jira Cloud REST API v3 & Rovo MCP. Creates Bug, Story, and Task issues with Atlassian Document Format.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>Jira REST v3 / ADF</code> • Target: <code>atlassian.net</code>
          </div>
        </div>

        {/* Google Calendar */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#34d399" }}>Google Calendar API v3</span>
            <span className="badge badge-confidence-high">🟢 Active</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Google Calendar API v3 with attendee invitations, pop-up notifications, and timezone synchronization.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>Google Calendar v3</code> • Target: <code>googleapis.com</code>
          </div>
        </div>

        {/* Task Ledger */}
        <div className="glass-panel" style={{ padding: "1.25rem", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#fbbf24" }}>Task Ledger (Custom Server)</span>
            <span className="badge" style={{ background: "rgba(245, 158, 11, 0.2)", color: "#fbbf24" }}>⭐ Custom MCP</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Native FastMCP 2.x server backed by PostgreSQL. Provides standalone fallback task management when external tools are unmapped.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>FastMCP 2.x</code> • Transport: <code>Native Async FastMCP</code>
          </div>
        </div>
      </div>
    </div>
  );
}
