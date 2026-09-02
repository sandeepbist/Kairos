"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getConnectorsStatus } from "@/lib/api";
import { ConnectorsStatusResponse, TargetTool } from "@/lib/types";

const TOOL_LABELS: Record<TargetTool, string> = {
  notion: "Notion",
  jira: "Jira",
  calendar: "Calendar",
  task_ledger: "Ledger",
  linear: "Linear",
  todoist: "Todoist",
  email_draft: "Email",
  github: "GitHub",
  confluence_page: "Confluence",
  google_tasks: "G Tasks",
};

const CONNECTOR_TOOLS: TargetTool[] = ["notion", "jira", "calendar", "linear", "todoist", "email_draft", "github", "confluence_page", "google_tasks", "task_ledger"];

export function Navbar() {
  const pathname = usePathname();
  const [status, setStatus] = useState<ConnectorsStatusResponse | null>(null);

  useEffect(() => {
    getConnectorsStatus()
      .then(setStatus)
      .catch(() => {});
  }, []);

  const navLinks = [
    { href: "/", label: "Ingest" },
    { href: "/history", label: "History" },
    { href: "/settings", label: "Settings" },
  ];

  return (
    <header
      style={{
        borderBottom: "1px solid var(--line)",
        background: "rgba(9, 9, 11, 0.78)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      <div
        className="container"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "56px",
        }}
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "28px" }}>
          <Link
            href="/"
            style={{
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: "1px",
            }}
          >
            <span
              style={{
                fontWeight: 620,
                fontSize: "1.02rem",
                letterSpacing: "0.01em",
                color: "var(--text)",
              }}
            >
              Kairos
            </span>
          </Link>

          <nav style={{ display: "flex", gap: "2px" }}>
            {navLinks.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "var(--r-sm)",
                    fontSize: "0.84rem",
                    fontWeight: active ? 550 : 440,
                    color: active ? "var(--text)" : "var(--text-muted)",
                    background: active ? "rgba(255, 255, 255, 0.05)" : "transparent",
                    transition: "color var(--fast) var(--ease), background-color var(--fast) var(--ease)",
                    textDecoration: "none",
                  }}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Connector status — quiet dots */}
        <div
          style={{ display: "flex", alignItems: "center", gap: "14px" }}
          title="Connector availability — manage in Settings"
        >
          {CONNECTOR_TOOLS.map((tool) => {
            const info = status?.connectors?.[tool];
            const connected = Boolean(info?.oauth_connected ?? info?.healthy);
            return (
              <Link
                key={tool}
                href="/settings"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  textDecoration: "none",
                  color: connected ? "var(--text-secondary)" : "var(--text-dim)",
                  fontSize: "0.76rem",
                  transition: "color var(--fast) var(--ease)",
                }}
                title={`${TOOL_LABELS[tool]} ${connected ? "connected" : "not connected"}`}
              >
                <span className={`status-dot ${connected ? "status-on" : "status-off"}`} />
                {TOOL_LABELS[tool]}
              </Link>
            );
          })}

          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "0.72rem",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.03em",
              color: status?.sandbox_mode ? "var(--warn)" : "var(--ok)",
            }}
            title={status?.sandbox_mode ? "Sandbox: tool calls are simulated" : "Live: tool calls hit real APIs"}
          >
            <span
              className={`status-dot ${status?.sandbox_mode ? "status-warn" : "status-on status-live"}`}
            />
            {status?.sandbox_mode ? "SANDBOX" : "LIVE"}
          </span>
        </div>
      </div>
    </header>
  );
}
