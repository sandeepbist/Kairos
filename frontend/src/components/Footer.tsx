import React from "react";
import Link from "next/link";

export function Footer() {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--border-subtle)",
        background: "rgba(0, 0, 0, 0.9)",
        padding: "3rem 1.5rem 4rem",
        marginTop: "auto",
      }}
    >
      <div
        className="container"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1.5rem",
          padding: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              width: "20px",
              height: "20px",
              borderRadius: "4px",
              background: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: "0.75rem",
              color: "#000000",
            }}
          >
            K
          </div>
          <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            © {new Date().getFullYear()} Kairos Ambient Action Agent. Production-Grade OSS.
          </span>
        </div>

        <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.85rem" }}>
          <Link
            href="/terms"
            style={{ color: "var(--text-secondary)", textDecoration: "none", transition: "color 0.15s ease" }}
          >
            Terms of Service
          </Link>
          <Link
            href="/privacy"
            style={{ color: "var(--text-secondary)", textDecoration: "none", transition: "color 0.15s ease" }}
          >
            Privacy Policy
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            style={{ color: "var(--text-secondary)", textDecoration: "none" }}
          >
            API Docs
          </a>
          <a
            href="http://localhost:8234"
            target="_blank"
            rel="noreferrer"
            style={{ color: "var(--text-secondary)", textDecoration: "none" }}
          >
            Temporal UI
          </a>
        </div>
      </div>
    </footer>
  );
}
