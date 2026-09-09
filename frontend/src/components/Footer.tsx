"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth } from "@/lib/api";

// Public links are opt-in via env; absent in prod builds by default.
const API_DOCS_URL = process.env.NEXT_PUBLIC_API_DOCS_URL || "";
const TEMPORAL_UI_URL = process.env.NEXT_PUBLIC_TEMPORAL_UI_URL || "";

export function Footer() {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    // One quiet fetch on mount — the version line is decorative, so a
    // failure renders nothing (no empty chrome, no separator dot).
    getHealth()
      .then((health) => {
        if (!cancelled && health.version) setVersion(health.version);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <footer
      style={{
        borderTop: "1px solid var(--line)",
        padding: "28px 0 32px",
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
          gap: "16px",
        }}
      >
        <span className="mono-label">
          © {new Date().getFullYear()} KAIROS — AMBIENT ACTION ENGINE
          {version && (
            <span className="dim" style={{ marginLeft: "6px" }}>
              · v{version}
            </span>
          )}
        </span>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "22px", fontSize: "0.8rem" }}>
          <Link href="/terms" className="link-quiet">
            Terms
          </Link>
          <Link href="/privacy" className="link-quiet">
            Privacy
          </Link>
          {API_DOCS_URL ? (
            <a href={API_DOCS_URL} target="_blank" rel="noreferrer" className="link-quiet">
              API
            </a>
          ) : null}
          {TEMPORAL_UI_URL ? (
            <a href={TEMPORAL_UI_URL} target="_blank" rel="noreferrer" className="link-quiet">
              Temporal
            </a>
          ) : null}
        </div>
      </div>
    </footer>
  );
}
