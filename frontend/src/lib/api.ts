import {
  SourceType,
  BatchResponse,
  ActionItemDecision,
  HistoryBatch,
  ConnectorsStatusResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export async function ingestBatch(
  raw_text: string,
  source_type: SourceType = "meeting_transcript"
): Promise<{ batch_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/batches/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text, source_type }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Ingest failed" }));
    throw new Error(error.detail || `Ingest failed with status ${res.status}`);
  }
  return res.json();
}

export async function getBatch(batchId: string): Promise<BatchResponse> {
  const res = await fetch(`${API_BASE}/batches/${batchId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch batch" }));
    throw new Error(error.detail || `Fetch batch failed with status ${res.status}`);
  }
  return res.json();
}

export async function approveBatch(
  batchId: string,
  decisions: ActionItemDecision[]
): Promise<{ batch_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/batches/${batchId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ batch_id: batchId, decisions }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Approval submission failed" }));
    throw new Error(error.detail || `Approval failed with status ${res.status}`);
  }
  return res.json();
}

export async function getHistory(): Promise<HistoryBatch[]> {
  const res = await fetch(`${API_BASE}/history`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch history (${res.status})`);
  }
  return res.json();
}

export async function getConnectorsStatus(): Promise<ConnectorsStatusResponse> {
  const res = await fetch(`${API_BASE}/connectors/status`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch connectors status (${res.status})`);
  }
  return res.json();
}

export async function toggleSandbox(sandbox_mode: boolean): Promise<any> {
  const res = await fetch(`${API_BASE}/connectors/sandbox-toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sandbox_mode }),
  });
  if (!res.ok) {
    throw new Error("Failed to toggle sandbox mode");
  }
  return res.json();
}
