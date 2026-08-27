"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getConnectorsStatus } from "@/lib/api";
import { ConnectorsStatusResponse } from "@/lib/types";

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

  const isNotionConnected = Boolean(status?.connectors?.notion?.oauth_connected);
  const isJiraConnected = Boolean(status?.connectors?.jira?.oauth_connected);
  const isCalendarConnected = Boolean(status?.connectors?.calendar?.oauth_connected);
  const isTaskLedgerConnected = Boolean(status?.connectors?.task_ledger?.healthy ?? true);

  return (
    <header
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        background: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
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
          height: "60px",
          paddingTop: 0,
          paddingBottom: 0,
        }}
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "2.5rem" }}>
          <Link
            href="/"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
              textDecoration: "none",
            }}
          >
            <div
              style={{
                width: "24px",
                height: "24px",
                borderRadius: "6px",
                background: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: "0.85rem",
                color: "#000000",
              }}
            >
              K
            </div>
            <span
              style={{
                fontWeight: 600,
                fontSize: "0.95rem",
                letterSpacing: "-0.03em",
                color: "#ffffff",
              }}
            >
              Kairos
            </span>
          </Link>

          {/* Navigation Links */}
          <nav style={{ display: "flex", gap: "0.25rem" }}>
            {navLinks.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  style={{
                    padding: "0.35rem 0.75rem",
                    borderRadius: "6px",
                    fontSize: "0.85rem",
                    fontWeight: active ? 600 : 400,
                    color: active ? "#ffffff" : "var(--text-secondary)",
                    background: active ? "rgba(255, 255, 255, 0.08)" : "transparent",
                    transition: "all 0.15s ease",
                    textDecoration: "none",
                  }}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Dynamic Connector Status Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Link
            href="/settings"
            className="pill"
            style={{
              fontSize: "0.75rem",
              textDecoration: "none",
              color: isNotionConnected ? "#d8b4fe" : "var(--text-dim)",
              borderColor: isNotionConnected ? "rgba(168, 85, 247, 0.3)" : "var(--border-subtle)",
            }}
            title={isNotionConnected ? "Notion API Connected" : "Notion Not Connected — Click to add token in Settings"}
          >
            <span className={`dot ${isNotionConnected ? "dot-green" : ""}`} style={{ background: isNotionConnected ? "#10b981" : "#52525b" }} />
            <span>Notion</span>
          </Link>

          <Link
            href="/settings"
            className="pill"
            style={{
              fontSize: "0.75rem",
              textDecoration: "none",
              color: isJiraConnected ? "#93c5fd" : "var(--text-dim)",
              borderColor: isJiraConnected ? "rgba(59, 130, 246, 0.3)" : "var(--border-subtle)",
            }}
            title={isJiraConnected ? "Jira Cloud API Connected" : "Jira Not Connected — Click to add token in Settings"}
          >
            <span className={`dot ${isJiraConnected ? "dot-green" : ""}`} style={{ background: isJiraConnected ? "#10b981" : "#52525b" }} />
            <span>Jira</span>
          </Link>

          <Link
            href="/settings"
            className="pill"
            style={{
              fontSize: "0.75rem",
              textDecoration: "none",
              color: isCalendarConnected ? "#6ee7b7" : "var(--text-dim)",
              borderColor: isCalendarConnected ? "rgba(16, 185, 129, 0.3)" : "var(--border-subtle)",
            }}
            title={isCalendarConnected ? "Google Calendar API Connected" : "Calendar Not Connected — Click to add token in Settings"}
          >
            <span className={`dot ${isCalendarConnected ? "dot-green" : ""}`} style={{ background: isCalendarConnected ? "#10b981" : "#52525b" }} />
            <span>Calendar</span>
          </Link>

          <div
            className="pill"
            style={{
              fontSize: "0.75rem",
              color: isTaskLedgerConnected ? "#fcd34d" : "var(--text-dim)",
              borderColor: "rgba(245, 158, 11, 0.3)",
            }}
            title="Internal Task Ledger MCP Server active on PostgreSQL"
          >
            <span className="dot dot-green" />
            <span>Task Ledger</span>
          </div>

          <Link
            href="/settings"
            className="pill"
            style={{
              fontSize: "0.7rem",
              textDecoration: "none",
              background: status?.sandbox_mode ? "rgba(245, 158, 11, 0.1)" : "rgba(16, 185, 129, 0.1)",
              borderColor: status?.sandbox_mode ? "rgba(245, 158, 11, 0.2)" : "rgba(16, 185, 129, 0.2)",
              color: status?.sandbox_mode ? "#fbbf24" : "#34d399",
            }}
          >
            {status?.sandbox_mode ? "⚡ Sandbox" : "🟢 Live Mode"}
          </Link>
        </div>
      </div>
    </header>
  );
}
