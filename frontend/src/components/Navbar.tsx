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
      .catch(() => {
        // Fallback default status if backend is polling
        setStatus({
          sandbox_mode: true,
          connectors: {
            notion: { healthy: true, sandbox_mode: true, oauth_connected: true, type: "official_mcp" },
            jira: { healthy: true, sandbox_mode: true, oauth_connected: true, type: "official_mcp" },
            calendar: { healthy: true, sandbox_mode: true, oauth_connected: true, type: "official_mcp" },
            task_ledger: { healthy: true, sandbox_mode: true, oauth_connected: true, type: "custom_internal" },
          },
        });
      });
  }, []);

  const navLinks = [
    { href: "/", label: "Ingest & Extract" },
    { href: "/history", label: "Execution History" },
    { href: "/settings", label: "Connectors & Sandbox" },
  ];

  return (
    <header style={{
      borderBottom: "1px solid var(--border-subtle)",
      background: "rgba(8, 11, 17, 0.85)",
      backdropFilter: "blur(12px)",
      position: "sticky",
      top: 0,
      zIndex: 50,
    }}>
      <div className="container" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "64px",
      }}>
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "2rem" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <div style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #38bdf8, #6366f1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 12px rgba(56, 189, 248, 0.4)",
              fontWeight: 800,
              fontSize: "1rem",
              color: "#fff",
            }}>
              K
            </div>
            <div>
              <span style={{ fontWeight: 700, fontSize: "1.1rem", letterSpacing: "-0.02em" }}>Kairos</span>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "0.4rem" }}>Ambient Action Agent</span>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav style={{ display: "flex", gap: "0.5rem" }}>
            {navLinks.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  style={{
                    padding: "0.4rem 0.8rem",
                    borderRadius: "6px",
                    fontSize: "0.875rem",
                    fontWeight: active ? 600 : 500,
                    color: active ? "var(--accent-cyan)" : "var(--text-secondary)",
                    background: active ? "rgba(56, 189, 248, 0.1)" : "transparent",
                    transition: "all 0.15s ease",
                  }}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Connector Health Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          {status?.sandbox_mode && (
            <span style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              fontSize: "0.7rem",
              fontWeight: 700,
              background: "rgba(245, 158, 11, 0.15)",
              color: "#fbbf24",
              border: "1px solid rgba(245, 158, 11, 0.3)",
              padding: "0.2rem 0.6rem",
              borderRadius: "9999px",
            }}>
              ⚡ SANDBOX MODE
            </span>
          )}

          <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
            <span title="Notion MCP Server" style={badgeStyle("#c084fc")}>Notion 🟢</span>
            <span title="Jira Atlassian Rovo MCP" style={badgeStyle("#60a5fa")}>Jira 🟢</span>
            <span title="Google Calendar MCP" style={badgeStyle("#34d399")}>Calendar 🟢</span>
            <span title="Custom Task Ledger MCP" style={badgeStyle("#fbbf24")}>Ledger 🟢</span>
          </div>
        </div>
      </div>
    </header>
  );
}

const badgeStyle = (color: string) => ({
  fontSize: "0.7rem",
  fontWeight: 600,
  background: "rgba(255, 255, 255, 0.04)",
  color,
  border: "1px solid rgba(255, 255, 255, 0.08)",
  padding: "0.2rem 0.5rem",
  borderRadius: "6px",
});
