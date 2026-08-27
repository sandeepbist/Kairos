"use client";

import React, { useEffect, useState } from "react";
import { getConnectorsStatus, toggleSandbox } from "@/lib/api";
import { ConnectorsStatusResponse } from "@/lib/types";

export default function SettingsPage() {
  const [status, setStatus] = useState<ConnectorsStatusResponse | null>(null);
  const [sandboxEnabled, setSandboxEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getConnectorsStatus()
      .then((data) => {
        setStatus(data);
        setSandboxEnabled(data.sandbox_mode);
      })
      .catch(() => {});
  }, []);

  const handleToggleSandbox = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const next = !sandboxEnabled;
      const res = await toggleSandbox(next);
      setSandboxEnabled(res.sandbox_mode);
      setMessage(`Sandbox Mode is now ${res.sandbox_mode ? "ENABLED (Offline Mock Emulation)" : "DISABLED (Live MCP Servers)"}`);
    } catch (err: any) {
      setMessage("Failed to update sandbox mode");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "960px" }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
          Connectors & Sandbox Settings
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginTop: "0.25rem" }}>
          Configure Model Context Protocol (MCP) server endpoints, OAuth credentials, and demo modes.
        </p>
      </div>

      {message && (
        <div style={{
          padding: "0.75rem 1rem",
          borderRadius: "8px",
          background: "rgba(56, 189, 248, 0.15)",
          border: "1px solid rgba(56, 189, 248, 0.3)",
          color: "#38bdf8",
          fontSize: "0.875rem",
          marginBottom: "1.5rem",
        }}>
          ℹ️ {message}
        </div>
      )}

      {/* Sandbox Mode Toggle Card */}
      <div className="glass-panel" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Sandbox / Mock Mode</h3>
              <span className="badge" style={{ background: sandboxEnabled ? "rgba(245, 158, 11, 0.2)" : "rgba(16, 185, 129, 0.2)", color: sandboxEnabled ? "#fbbf24" : "#34d399" }}>
                {sandboxEnabled ? "Active" : "Disabled"}
              </span>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.35rem", maxWidth: "600px" }}>
              When enabled, MCP tool calls return high-fidelity mock IDs and simulated URLs with realistic latency.
              Allows zero-friction offline demos without requiring live Notion or Jira OAuth credentials.
            </p>
          </div>

          <button
            onClick={handleToggleSandbox}
            disabled={saving}
            className={`btn ${sandboxEnabled ? "btn-secondary" : "btn-primary"}`}
            style={{ padding: "0.6rem 1.25rem", fontSize: "0.875rem" }}
          >
            {saving ? "Updating..." : sandboxEnabled ? "Switch to Live MCP Mode" : "Switch to Sandbox Mode"}
          </button>
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
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#c084fc" }}>Notion MCP Server</span>
            <span className="badge badge-confidence-high">🟢 Connected</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Official Notion Model Context Protocol Server with OAuth 2.1 authentication. Creates database pages with properties.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>mcp-notion/v1</code> • Transport: <code>SSE / HTTP</code>
          </div>
        </div>

        {/* Jira */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#60a5fa" }}>Atlassian Rovo Jira MCP</span>
            <span className="badge badge-confidence-high">🟢 Connected</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Official Atlassian Rovo MCP Server with OAuth 2.1. Files Bugs, Stories, and Tasks with assigned project keys.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>mcp-atlassian-rovo</code> • Transport: <code>SSE</code>
          </div>
        </div>

        {/* Google Calendar */}
        <div className="glass-panel" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#34d399" }}>Google Calendar MCP</span>
            <span className="badge badge-confidence-high">🟢 Connected</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Official Google Calendar MCP Server (April 2026). Schedules events with attendees, timezones, and reminders.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>google-calendar-mcp</code> • Transport: <code>Streamable HTTP</code>
          </div>
        </div>

        {/* Task Ledger */}
        <div className="glass-panel" style={{ padding: "1.25rem", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", color: "#fbbf24" }}>Task Ledger (Custom Server)</span>
            <span className="badge" style={{ background: "rgba(245, 158, 11, 0.2)", color: "#fbbf24" }}>⭐ Custom MCP</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Authored FastMCP server backed by PostgreSQL. Provides standalone fallback task management when external tools are unmapped.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Protocol: <code>FastMCP 2.x</code> • Transport: <code>Native Async FastMCP</code>
          </div>
        </div>
      </div>
    </div>
  );
}
