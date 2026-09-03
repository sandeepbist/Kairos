"use client";

import React, { useEffect, useState } from "react";
import { getConnectorsStatus, toggleSandbox, saveOAuthToken, deleteOAuthToken } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { ConnectorsStatusResponse, TargetTool } from "@/lib/types";

type Notice = { text: string; type: "success" | "error" | "info" } | null;

interface CredentialConfig {
  provider: string;
  label: string;
  hint: string;
  linkLabel?: string;
  linkUrl?: string;
  placeholder: string;
  connectedKey: (s: ConnectorsStatusResponse) => boolean;
}

const TOOL_CARDS: Array<{
  tool: TargetTool;
  name: string;
  detail: string;
  protocol: string;
}> = [
  { tool: "notion", name: "Notion", detail: "Creates database pages via Notion API v1.", protocol: "api.notion.so" },
  { tool: "jira", name: "Jira", detail: "Files issues via Jira Cloud REST v3.", protocol: "atlassian.net" },
  { tool: "calendar", name: "Google Calendar", detail: "Creates events with reminders via Calendar API v3.", protocol: "googleapis.com" },
  { tool: "linear", name: "Linear", detail: "Files issues via the Linear GraphQL API.", protocol: "linear.app" },
  { tool: "todoist", name: "Todoist", detail: "Creates tasks via the Todoist REST v2 API.", protocol: "todoist.com" },
  { tool: "email_draft", name: "Email draft", detail: "Prepares a Gmail draft you review and send. Uses the Gmail credential.", protocol: "gmail drafts api" },
  { tool: "github", name: "GitHub", detail: "Opens issues on a repository you name, via the REST API.", protocol: "api.github.com" },
  { tool: "confluence_page", name: "Confluence", detail: "Creates pages through Atlassian's remote MCP server. Uses the Jira credential.", protocol: "mcp.atlassian.com" },
  { tool: "google_tasks", name: "Google Tasks", detail: "Adds tasks to your task list via the Tasks API.", protocol: "tasks.googleapis.com" },
  { tool: "asana", name: "Asana", detail: "Creates tasks in your first workspace via the Asana API v1.", protocol: "app.asana.com" },
  { tool: "clickup", name: "ClickUp", detail: "Creates tasks on a list you name, via the ClickUp API v2.", protocol: "api.clickup.com" },
  { tool: "task_ledger", name: "Task Ledger", detail: "Built-in MCP server, backed by Postgres. Always available.", protocol: "mcp · internal" },
];

export default function SettingsPage() {
  const [status, setStatus] = useState<ConnectorsStatusResponse | null>(null);
  const [sandboxEnabled, setSandboxEnabled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<Notice>(null);

  const [tokenValues, setTokenValues] = useState<Record<string, string>>({
    gemini: "",
    openai: "",
    notion: "",
    jira: "",
    google_calendar: "",
  });
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
        text: res.sandbox_mode
          ? "Sandbox enabled — tool calls are simulated for new batches."
          : "Live mode — new batches execute against real APIs.",
        type: "info",
      });
      loadStatus();
    } catch {
      setMessage({ text: "Failed to update execution mode", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveToken = async (provider: string) => {
    const value = tokenValues[provider] || "";
    if (!value.trim()) {
      setMessage({ text: `Enter a valid token for ${provider}`, type: "error" });
      return;
    }
    setSavingProvider(provider);
    setMessage(null);
    try {
      await saveOAuthToken(provider, value.trim());
      setMessage({ text: `${provider} credential encrypted into the vault.`, type: "success" });
      setTokenValues((prev) => ({ ...prev, [provider]: "" }));
      loadStatus();
    } catch (err) {
      setMessage({ text: errorMessage(err, `Failed to save ${provider} token`), type: "error" });
    } finally {
      setSavingProvider(null);
    }
  };

  const handleDeleteToken = async (provider: string) => {
    setSavingProvider(provider);
    setMessage(null);
    try {
      await deleteOAuthToken(provider);
      setMessage({ text: `${provider} credential removed from the vault.`, type: "info" });
      loadStatus();
    } catch (err) {
      setMessage({ text: errorMessage(err, `Failed to disconnect ${provider}`), type: "error" });
    } finally {
      setSavingProvider(null);
    }
  };

  const isGeminiConnected = Boolean(status?.llm_providers?.gemini?.connected);
  const isOpenAIConnected = Boolean(status?.llm_providers?.openai?.connected);
  const isNotionConnected = Boolean(status?.connectors?.notion?.oauth_connected);
  const isJiraConnected = Boolean(status?.connectors?.jira?.oauth_connected);
  const isCalendarConnected = Boolean(status?.connectors?.calendar?.oauth_connected);
  const isGmailConnected = Boolean(status?.connectors?.email_draft?.oauth_connected);
  const isLinearConnected = Boolean(status?.connectors?.linear?.oauth_connected);
  const isTodoistConnected = Boolean(status?.connectors?.todoist?.oauth_connected);
  const isGithubConnected = Boolean(status?.connectors?.github?.oauth_connected);
  const isConfluenceConnected = Boolean(status?.connectors?.confluence_page?.oauth_connected);
  const isGoogleTasksConnected = Boolean(status?.connectors?.google_tasks?.oauth_connected);
  const isAsanaConnected = Boolean(status?.connectors?.asana?.oauth_connected);
  const isClickUpConnected = Boolean(status?.connectors?.clickup?.oauth_connected);

  const credentialCards: CredentialConfig[] = [
    {
      provider: "gemini",
      label: "Google Gemini",
      hint: "Free key from aistudio.google.com. Powers structured extraction.",
      linkLabel: "aistudio.google.com",
      linkUrl: "https://aistudio.google.com",
      placeholder: "Gemini API key",
      connectedKey: () => isGeminiConnected,
    },
    {
      provider: "openai",
      label: "OpenAI",
      hint: "Key from platform.openai.com. Alternative extraction model.",
      linkLabel: "platform.openai.com",
      linkUrl: "https://platform.openai.com/api-keys",
      placeholder: "sk-…",
      connectedKey: () => isOpenAIConnected,
    },
    {
      provider: "notion",
      label: "Notion",
      hint: "Internal integration secret. Grant the integration access to your target database in Notion first.",
      linkLabel: "notion.so/my-integrations",
      linkUrl: "https://www.notion.so/my-integrations",
      placeholder: "secret_…",
      connectedKey: () => isNotionConnected,
    },
    {
      provider: "jira",
      label: "Jira",
      hint: "Atlassian API token, paired with your account email.",
      linkLabel: "Atlassian security settings",
      linkUrl: "https://id.atlassian.com/manage-profile/security/api-tokens",
      placeholder: "Atlassian API token",
      connectedKey: () => isJiraConnected,
    },
    {
      provider: "google_calendar",
      label: "Google Calendar",
      hint: "OAuth access token with calendar.events scope.",
      placeholder: "OAuth access token",
      connectedKey: () => isCalendarConnected,
    },
    {
      provider: "gmail",
      label: "Gmail",
      hint: "OAuth token with gmail.readonly + compose scopes. Powers the Gmail poller and email-draft actions.",
      placeholder: "OAuth access token",
      connectedKey: () => isGmailConnected,
    },
    {
      provider: "linear",
      label: "Linear",
      hint: "API key from Linear settings (Security & access).",
      linkLabel: "linear.app/settings",
      linkUrl: "https://linear.app/settings",
      placeholder: "Linear API key",
      connectedKey: () => isLinearConnected,
    },
    {
      provider: "todoist",
      label: "Todoist",
      hint: "API token from Todoist settings (Integrations).",
      linkLabel: "todoist.com/psettings/integrations",
      linkUrl: "https://todoist.com/psettings/integrations",
      placeholder: "Todoist API token",
      connectedKey: () => isTodoistConnected,
    },
    {
      provider: "github",
      label: "GitHub",
      hint: "Fine-grained PAT with Issues: write on your target repo. Default repo set via GITHUB_TARGET_REPO, or per action.",
      linkLabel: "github.com/settings/personal-access-tokens",
      linkUrl: "https://github.com/settings/personal-access-tokens/new",
      placeholder: "GitHub PAT (github_pat_…)",
      connectedKey: () => isGithubConnected,
    },
    {
      provider: "confluence",
      label: "Confluence",
      hint: "Pages go through Atlassian's remote MCP server. Uses the Jira credential — connect Jira above and this activates.",
      placeholder: "Atlassian token (optional override)",
      connectedKey: () => isConfluenceConnected,
    },
    {
      provider: "google_tasks",
      label: "Google Tasks",
      hint: "OAuth token with the tasks scope. A Google Calendar token with a bundled grant also works.",
      placeholder: "OAuth access token (tasks scope)",
      connectedKey: () => isGoogleTasksConnected,
    },
    {
      provider: "asana",
      label: "Asana",
      hint: "Personal access token from the Asana developer console. Tasks land in your first workspace by default.",
      linkLabel: "app.asana.com/0/my-apps",
      linkUrl: "https://app.asana.com/0/my-apps",
      placeholder: "Asana PAT",
      connectedKey: () => isAsanaConnected,
    },
    {
      provider: "clickup",
      label: "ClickUp",
      hint: "Personal token from ClickUp settings (Apps). Default target list via CLICKUP_TARGET_LIST, or per action.",
      linkLabel: "ClickUp settings — Apps",
      linkUrl: "https://app.clickup.com/settings/apps",
      placeholder: "ClickUp token (pk_…)",
      connectedKey: () => isClickUpConnected,
    },
  ];

  const noticeClass = message
    ? message.type === "success"
      ? "notice notice-ok"
      : message.type === "error"
        ? "notice notice-error"
        : "notice notice-info"
    : "";

  return (
    <div className="container" style={{ maxWidth: "760px" }}>
      {/* Header */}
      <div className="rise" style={{ marginBottom: "34px" }}>
        <p className="mono-label" style={{ marginBottom: "8px" }}>
          CONFIGURATION
        </p>
        <h1 className="h-title" style={{ fontSize: "1.4rem" }}>
          Settings
        </h1>
        <p className="dim" style={{ fontSize: "0.84rem", marginTop: "4px" }}>
          Execution mode, extraction models, and connected tool credentials.
        </p>
      </div>

      {message && (
        <div className={`${noticeClass} fade-in`} style={{ marginBottom: "20px" }}>
          {message.text}
        </div>
      )}

      {/* Execution mode */}
      <section className="panel rise rise-1" style={{ padding: "18px 22px", marginBottom: "28px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "18px", flexWrap: "wrap" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <span className="h-section">Execution mode</span>
              <span
                className="tag"
                style={{
                  color: sandboxEnabled ? "var(--warn)" : "var(--ok)",
                  borderColor: sandboxEnabled ? "rgba(234, 179, 8, 0.3)" : "rgba(74, 222, 128, 0.3)",
                }}
              >
                {sandboxEnabled ? "SANDBOX" : "LIVE"}
              </span>
            </div>
            <p className="dim" style={{ fontSize: "0.82rem", maxWidth: "420px" }}>
              {sandboxEnabled
                ? "Tool calls return simulated results — no external requests, no side effects."
                : "Approved actions execute real calls to Jira, Notion, and Calendar using the vault credentials below."}
            </p>
          </div>

          <button
            type="button"
            className="switch"
            data-on={sandboxEnabled}
            onClick={handleToggleSandbox}
            disabled={saving}
            aria-label="Toggle sandbox mode"
            role="switch"
            aria-checked={sandboxEnabled}
          >
            <span className="switch-thumb" />
          </button>
        </div>
      </section>

      {/* Credentials */}
      <p className="mono-label rise rise-2" style={{ marginBottom: "14px" }}>
        CREDENTIAL VAULT — AES-256 ENCRYPTED AT REST
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "36px" }}>
        {credentialCards.map((card, idx) => {
          const connected = card.connectedKey(status as ConnectorsStatusResponse);
          return (
            <div
              key={card.provider}
              className={`panel rise rise-${Math.min(idx + 1, 5)}`}
              style={{ padding: "16px 20px" }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "10px",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "9px" }}>
                  <span
                    className={`status-dot ${connected ? "status-on" : "status-off"}`}
                  />
                  <span className="h-section">{card.label}</span>
                </div>
                {connected && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDeleteToken(card.provider)}
                    disabled={savingProvider === card.provider}
                  >
                    Disconnect
                  </button>
                )}
              </div>

              <p className="dim" style={{ fontSize: "0.79rem", marginBottom: "12px", lineHeight: 1.5 }}>
                {card.hint}{" "}
                {card.linkUrl && (
                  <a href={card.linkUrl} target="_blank" rel="noreferrer" className="link-accent">
                    {card.linkLabel}
                  </a>
                )}
              </p>

              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="password"
                  className="input mono"
                  placeholder={card.placeholder}
                  value={tokenValues[card.provider] || ""}
                  onChange={(e) =>
                    setTokenValues((prev) => ({ ...prev, [card.provider]: e.target.value }))
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSaveToken(card.provider);
                  }}
                  aria-label={`${card.label} credential`}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => handleSaveToken(card.provider)}
                  disabled={savingProvider === card.provider}
                  style={{ flexShrink: 0 }}
                >
                  {savingProvider === card.provider ? "Saving…" : connected ? "Update" : "Save"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Tool ecosystem */}
      <p className="mono-label" style={{ marginBottom: "14px" }}>
        TOOL ECOSYSTEM
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: "10px",
        }}
      >
        {TOOL_CARDS.map((t) => {
          const info = status?.connectors?.[t.tool];
          const connected = t.tool === "task_ledger" ? true : Boolean(info?.oauth_connected);
          return (
            <div key={t.tool} className="panel" style={{ padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span className={`tag tag-tool tag-${t.tool}`}>{t.name}</span>
                <span className={`status-dot ${connected ? "status-on" : "status-off"}`} />
              </div>
              <p className="dim" style={{ fontSize: "0.78rem", lineHeight: 1.5, marginBottom: "8px" }}>
                {t.detail}
              </p>
              <span className="mono-label">{t.protocol.toUpperCase()}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
