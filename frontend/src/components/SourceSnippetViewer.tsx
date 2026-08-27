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
      className="card-panel"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        maxHeight: "calc(100vh - 200px)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "0.85rem 1.25rem",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "rgba(0, 0, 0, 0.4)",
        }}
      >
        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
          Source Transcript
        </span>
        <span
          className="pill"
          style={{ fontSize: "0.7rem", textTransform: "uppercase" }}
        >
          {sourceType.replace("_", " ")}
        </span>
      </div>

      {/* Transcript Content with Synchronized Highlighting */}
      <div
        style={{
          padding: "1rem",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
          fontFamily: "var(--font-mono)",
          fontSize: "0.85rem",
          lineHeight: 1.6,
        }}
      >
        {lines.map((line, idx) => {
          const isHighlighted = Boolean(
            activeSnippet &&
              line.trim() &&
              (line.includes(activeSnippet) || activeSnippet.includes(line.trim()))
          );

          return (
            <div
              key={idx}
              className={`source-line ${isHighlighted ? "highlighted" : ""}`}
              style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
            >
              <span
                style={{
                  color: "var(--text-dim)",
                  fontSize: "0.75rem",
                  marginRight: "0.75rem",
                  userSelect: "none",
                  display: "inline-block",
                  minWidth: "20px",
                }}
              >
                {idx + 1}
              </span>
              {line}
            </div>
          );
        })}
      </div>
    </div>
  );
}
