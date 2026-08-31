"use client";

import React from "react";

interface SourceSnippetViewerProps {
  rawText: string;
  sourceType: string;
  activeSnippet: string | null;
}

export function SourceSnippetViewer({
  rawText,
  sourceType,
  activeSnippet,
}: SourceSnippetViewerProps) {
  const lines = rawText.split("\n");

  return (
    <div
      className="panel"
      style={{ display: "flex", flexDirection: "column", height: "100%", maxHeight: "calc(100vh - 220px)" }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 18px",
          borderBottom: "1px solid var(--line)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "var(--bg-raised)",
          borderRadius: "var(--r-lg) var(--r-lg) 0 0",
        }}
      >
        <span className="h-section">Source</span>
        <span className="mono-label">{sourceType.replace(/_/g, " ").toUpperCase()}</span>
      </div>

      {/* Transcript with synchronized highlighting */}
      <div
        style={{
          padding: "12px 8px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
        }}
      >
        {lines.map((line, idx) => {
          const isActive = Boolean(
            activeSnippet &&
              line.trim() &&
              (line.includes(activeSnippet) || activeSnippet.includes(line.trim()))
          );

          return (
            <div key={idx} className={`source-line ${isActive ? "is-active" : ""}`}>
              <span className="source-line-no">{idx + 1}</span>
              <span>{line || " "}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
