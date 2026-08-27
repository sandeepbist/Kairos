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

  return (
    <header
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        background: "rgba(0, 0, 0, 0.8)",
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

        {/* Live Ecosystem Status */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div className="pill" style={{ fontSize: "0.75rem", padding: "0.2rem 0.55rem" }}>
            <span className="dot dot-green" />
            <span>Notion</span>
          </div>
          <div className="pill" style={{ fontSize: "0.75rem", padding: "0.2rem 0.55rem" }}>
            <span className="dot dot-green" />
            <span>Jira</span>
          </div>
          <div className="pill" style={{ fontSize: "0.75rem", padding: "0.2rem 0.55rem" }}>
            <span className="dot dot-green" />
            <span>Calendar</span>
          </div>
          <div className="pill" style={{ fontSize: "0.75rem", padding: "0.2rem 0.55rem" }}>
            <span className="dot dot-green" />
            <span>Task Ledger</span>
          </div>

          <div
            className="pill"
            style={{
              fontSize: "0.7rem",
              background: status?.sandbox_mode ? "rgba(245, 158, 11, 0.1)" : "rgba(16, 185, 129, 0.1)",
              borderColor: status?.sandbox_mode ? "rgba(245, 158, 11, 0.2)" : "rgba(16, 185, 129, 0.2)",
              color: status?.sandbox_mode ? "#fbbf24" : "#34d399",
            }}
          >
            {status?.sandbox_mode ? "Sandbox" : "Live MCP"}
          </div>
        </div>
      </div>
    </header>
  );
}
