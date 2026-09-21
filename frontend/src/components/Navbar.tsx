"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getBatchesSummary, getConnectorsStatus } from "@/lib/api";
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
  asana: "Asana",
  clickup: "ClickUp",
};

const CONNECTOR_TOOLS: TargetTool[] = ["notion", "jira", "calendar", "linear", "todoist", "email_draft", "github", "confluence_page", "google_tasks", "asana", "clickup", "task_ledger"];

/** oauth_connected wins when present; falls back to the healthy flag. */
const isConnected = (
  status: ConnectorsStatusResponse | null,
  tool: TargetTool
): boolean => {
  const info = status?.connectors?.[tool];
  return Boolean(info?.oauth_connected ?? info?.healthy);
};

export function Navbar() {
  const pathname = usePathname();
  const [status, setStatus] = useState<ConnectorsStatusResponse | null>(null);
  const [awaiting, setAwaiting] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = () => {
      // One combined refresh: connector status plus the pending-approvals
      // count for the badge. Failures stay silent — both are decorative.
      getConnectorsStatus()
        .then((s) => {
          if (!cancelled) setStatus(s);
        })
        .catch(() => {}); // status is decorative — failures stay silent
      getBatchesSummary()
        .then((summary) => {
          if (!cancelled) setAwaiting(summary.awaiting_approval);
        })
        .catch(() => {});
    };

    // (a) on mount and on every route change (covers navigating to /settings,
    //     where a saved credential must be reflected immediately)
    fetchStatus();

    // (b) refetch when the tab becomes visible again
    const handleVisibility = () => {
      if (document.visibilityState === "visible") fetchStatus();
    };
    document.addEventListener("visibilitychange", handleVisibility);

    // (c) poll while the tab is visible
    const poll = window.setInterval(() => {
      if (document.visibilityState === "visible") fetchStatus();
    }, 30_000);

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", handleVisibility);
      window.clearInterval(poll);
    };
  }, [pathname]);

  const connectedTools = CONNECTOR_TOOLS.filter((tool) =>
    isConnected(status, tool)
  );
  const connectedCount = connectedTools.length;
  const connectedTitle =
    connectedCount > 0
      ? `Connected (${connectedCount}/${CONNECTOR_TOOLS.length}): ${connectedTools
          .map((tool) => TOOL_LABELS[tool])
          .join(" · ")} — manage in Settings`
      : "No connectors connected — manage in Settings";

  const navLinks = [
    { href: "/", label: "Ingest" },
    { href: "/history", label: "History" },
    { href: "/ledger", label: "Ledger" },
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
        className="container nav-row"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        {/* Brand */}
        <div className="nav-left" style={{ display: "flex", alignItems: "center" }}>
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

        {/* Connector status — compact summary */}
        <div
          style={{ display: "flex", alignItems: "center", gap: "14px" }}
          title="Connector availability — manage in Settings"
        >
          <Link
            href="/settings"
            className="mono-label nav-summary"
            data-zero={connectedCount === 0 ? "true" : "false"}
            aria-label="Connected tools"
            title={connectedTitle}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              textDecoration: "none",
              whiteSpace: "nowrap",
            }}
          >
            <span
              className={`status-dot hide-narrow ${
                connectedCount > 0 ? "status-on" : "status-off"
              }`}
            />
            {connectedCount}/12 CONNECTED
          </Link>

          {awaiting > 0 && (
            <Link
              href="/history"
              className="mono-label"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                textDecoration: "none",
                whiteSpace: "nowrap",
                color: "var(--warn)",
              }}
              title={`${awaiting} batch${awaiting === 1 ? "" : "es"} awaiting approval — review in History`}
            >
              <span className="status-dot status-warn" />
              {awaiting} AWAITING
            </Link>
          )}

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
