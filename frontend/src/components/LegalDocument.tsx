import React from "react";

/**
 * Minimal markdown renderer for the embedded legal documents.
 * Supports the subset used by PRIVACY.md / TERMS.md: headings, paragraphs,
 * ordered/bulleted lists, blockquotes, bold/italic/inline-code, tables,
 * and horizontal rules. Deliberately no HTML passthrough — legal text is
 * rendered as structured React nodes, never dangerouslySetInnerHTML.
 */

// --- inline formatting -------------------------------------------------------

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Split on **bold**, *italic*, `code`, [link](url)
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    const key = `${keyPrefix}-i${i++}`;
    if (tok.startsWith("**")) {
      nodes.push(<strong key={key}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      nodes.push(<code key={key}>{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("[")) {
      const lm = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok);
      nodes.push(
        <a key={key} href={lm?.[2]} target="_blank" rel="noreferrer" className="link-accent">
          {lm?.[1]}
        </a>
      );
    } else {
      nodes.push(<em key={key}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// --- block parsing -----------------------------------------------------------

type Block =
  | { kind: "h1"; text: string }
  | { kind: "h2"; text: string }
  | { kind: "h3"; text: string }
  | { kind: "p"; text: string }
  | { kind: "quote"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "hr" };

function parseBlocks(md: string): Block[] {
  const lines = md.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  const isTableSep = (l: string) =>
    /^\|?[\s:|-]+$/ .test(l) && l.includes("-") && l.includes("|");
  const splitRow = (l: string) =>
    l.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push({ kind: "h3", text: line.slice(4) });
      i++;
    } else if (line.startsWith("## ")) {
      blocks.push({ kind: "h2", text: line.slice(3) });
      i++;
    } else if (line.startsWith("# ")) {
      blocks.push({ kind: "h1", text: line.slice(2) });
      i++;
    } else if (line.trim() === "---" || line.trim() === "***") {
      blocks.push({ kind: "hr" });
      i++;
    } else if (line.startsWith(">")) {
      const qLines: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        qLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({ kind: "quote", lines: qLines });
    } else if (line.startsWith("|") && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const header = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      blocks.push({ kind: "table", header, rows });
    } else if (/^\d+\.\s/.test(line) || /^\s{4,}\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && (/^\d+\.\s/.test(lines[i]) || /^\s{4,}\d+\.\s/.test(lines[i]) || (/^\s{4,}\S/.test(lines[i]) && items.length))) {
        items.push(lines[i]);
        i++;
      }
      blocks.push({ kind: "ol", items });
    } else if (/^\s*[-*]\s/.test(line) || /^\s{4,}[-*]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && (/^\s*[-*]\s/.test(lines[i]) || /^\s{4,}[-*]\s/.test(lines[i]) || (/^\s{4,}\S/.test(lines[i]) && items.length))) {
        items.push(lines[i]);
        i++;
      }
      blocks.push({ kind: "ul", items });
    } else {
      const para: string[] = [];
      while (i < lines.length && lines[i].trim() && !/^(#|>|\||\d+\.\s|\s*[-*]\s|---)/.test(lines[i])) {
        para.push(lines[i]);
        i++;
      }
      if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
      else i++; // malformed line, skip
    }
  }
  return blocks;
}

// --- component ----------------------------------------------------------------

export interface LegalDocProps {
  title: string;
  subtitle?: string;
  /** Raw markdown of the legal document (PRIVACY.md / TERMS.md content). */
  document: string;
}

export function LegalDocument({ title, subtitle, document }: LegalDocProps) {
  // Strip the first H1 (we render our own header) and any index/TOC section
  const md = document.replace(/^#\s+.*\n/, "");
  const blocks = parseBlocks(md);

  return (
    <div className="container" style={{ maxWidth: "820px", paddingTop: "8px", paddingBottom: "48px" }}>
      <div style={{ marginBottom: "40px" }}>
        <h1 className="h-display" style={{ fontSize: "2rem", marginBottom: "10px" }}>
          {title}
        </h1>
        {subtitle ? <p className="dim" style={{ fontSize: "0.9rem" }}>{subtitle}</p> : null}
      </div>

      <div className="prose-legal" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {blocks.map((b, idx) => {
          const key = `b${idx}`;
          switch (b.kind) {
            case "h1":
              return (
                <h2 key={key} className="h-title" style={{ fontSize: "1.15rem", marginTop: idx > 0 ? "20px" : 0, marginBottom: "10px" }}>
                  {renderInline(b.text, key)}
                </h2>
              );
            case "h2":
              return (
                <h3 key={key} className="h-section" style={{ marginTop: "16px", marginBottom: "8px" }}>
                  {renderInline(b.text, key)}
                </h3>
              );
            case "h3":
              return (
                <h4 key={key} style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)", margin: "12px 0 6px" }}>
                  {renderInline(b.text, key)}
                </h4>
              );
            case "p":
              return <p key={key}>{renderInline(b.text, key)}</p>;
            case "quote":
              return (
                <blockquote key={key} style={{ borderLeft: "2px solid var(--line-strong)", paddingLeft: "14px", color: "var(--text-muted)", fontSize: "0.86rem" }}>
                  {b.lines.map((l, li) => (
                    <p key={`${key}-q${li}`}>{renderInline(l, `${key}-q${li}`)}</p>
                  ))}
                </blockquote>
              );
            case "ul":
              return (
                <ul key={key}>
                  {b.items.map((item, li) => (
                    <li key={`${key}-l${li}`}>{renderInline(item.replace(/^\s*[-*]\s?/, ""), `${key}-l${li}`)}</li>
                  ))}
                </ul>
              );
            case "ol":
              return (
                <ol key={key} style={{ listStyle: "decimal", paddingLeft: "22px", display: "flex", flexDirection: "column", gap: "9px" }}>
                  {b.items.map((item, li) => {
                    const isNested = /^\s{4,}/.test(item);
                    const inner = item.replace(/^\s*(\d+\.)?\s*/, "");
                    return isNested ? (
                      <li key={`${key}-l${li}`} style={{ marginLeft: "0", listStyle: "none" }}>
                        <span style={{ color: "var(--text-muted)" }}>{renderInline(inner, `${key}-l${li}`)}</span>
                      </li>
                    ) : (
                      <li key={`${key}-l${li}`}>{renderInline(inner, `${key}-l${li}`)}</li>
                    );
                  })}
                </ol>
              );
            case "table":
              return (
                <div key={key} style={{ overflowX: "auto", margin: "12px 0" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                    <thead>
                      <tr>
                        {b.header.map((h, hi) => (
                          <th
                            key={`${key}-th${hi}`}
                            style={{ textAlign: "left", padding: "8px 12px", borderBottom: "1px solid var(--line-strong)", color: "var(--text)", fontWeight: 600, whiteSpace: "nowrap" }}
                          >
                            {renderInline(h, `${key}-th${hi}`)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {b.rows.map((row, ri) => (
                        <tr key={`${key}-r${ri}`}>
                          {row.map((cell, ci) => (
                            <td
                              key={`${key}-r${ri}c${ci}`}
                              style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)", color: "var(--text-secondary)", verticalAlign: "top" }}
                            >
                              {renderInline(cell, `${key}-r${ri}c${ci}`)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            case "hr":
              return <hr key={key} style={{ border: "none", borderTop: "1px solid var(--line)", margin: "24px 0" }} />;
            default:
              return null;
          }
        })}
      </div>
    </div>
  );
}
