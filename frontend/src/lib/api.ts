import {
  SourceType,
  BatchResponse,
  ActionItemDecision,
  HistoryBatch,
  ConnectorsStatusResponse,
  CreateWebhookResponse,
  WebhookDelivery,
  WebhookEndpoint,
} from "./types";

/**
 * All calls target the same-origin Next.js proxy (`/api/*`), which
 * forwards to the FastAPI backend and injects the operator API key
 * server-side (see src/proxy.ts). The key never ships to the browser.
 */

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string | { msg?: string } };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail?.msg) return body.detail.msg;
  } catch {
    // non-JSON error body
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const message = await parseError(res, `Request failed (${res.status})`);
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as T;
}

export async function ingestBatch(
  raw_text: string,
  source_type: SourceType = "meeting_transcript"
): Promise<{ batch_id: string; status: string }> {
  return request("/api/batches/ingest", {
    method: "POST",
    body: JSON.stringify({ raw_text, source_type }),
  });
}

export async function getBatch(batchId: string): Promise<BatchResponse> {
  return request(`/api/batches/${batchId}`, { cache: "no-store" });
}

export async function approveBatch(
  batchId: string,
  decisions: ActionItemDecision[]
): Promise<{ batch_id: string; status: string }> {
  return request(`/api/batches/${batchId}/approve`, {
    method: "POST",
    body: JSON.stringify({ batch_id: batchId, decisions }),
  });
}

export async function getHistory(): Promise<HistoryBatch[]> {
  return request("/api/history", { cache: "no-store" });
}

export async function getConnectorsStatus(): Promise<ConnectorsStatusResponse> {
  return request("/api/connectors/status", { cache: "no-store" });
}

export async function toggleSandbox(
  sandbox_mode: boolean
): Promise<ConnectorsStatusResponse> {
  return request("/api/connectors/sandbox-toggle", {
    method: "POST",
    body: JSON.stringify({ sandbox_mode }),
  });
}

export async function saveOAuthToken(
  provider: string,
  accessToken: string,
  refreshToken?: string,
  scopes?: string
): Promise<{ status: string; provider: string }> {
  return request("/api/connectors/oauth/save", {
    method: "POST",
    body: JSON.stringify({
      provider,
      access_token: accessToken,
      refresh_token: refreshToken,
      scopes,
    }),
  });
}

export async function deleteOAuthToken(
  provider: string
): Promise<{ status: string; provider: string }> {
  return request(`/api/connectors/oauth/${provider}`, { method: "DELETE" });
}

// ── Outbound webhooks (Standard Webhooks) ────────────────────────────

export async function listWebhooks(): Promise<WebhookEndpoint[]> {
  return request("/api/webhooks");
}

export async function createWebhook(
  url: string,
  description: string,
  eventTypes: string[]
): Promise<CreateWebhookResponse> {
  return request("/api/webhooks", {
    method: "POST",
    body: JSON.stringify({ url, description, event_types: eventTypes }),
  });
}

export async function updateWebhook(
  id: string,
  patch: { enabled?: boolean; description?: string; event_types?: string[] }
): Promise<WebhookEndpoint> {
  return request(`/api/webhooks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function rotateWebhookSecret(id: string): Promise<CreateWebhookResponse> {
  return request(`/api/webhooks/${id}/rotate`, { method: "POST" });
}

export async function deleteWebhook(id: string): Promise<{ status: string }> {
  return request(`/api/webhooks/${id}`, { method: "DELETE" });
}

export async function testWebhook(
  id: string
): Promise<{ status: string; deliveries: number }> {
  return request(`/api/webhooks/${id}/test`, { method: "POST" });
}

export async function listWebhookDeliveries(
  id: string,
  limit = 20
): Promise<{ deliveries: WebhookDelivery[] }> {
  return request(`/api/webhooks/${id}/deliveries?limit=${limit}`);
}

export async function armWebhookDispatch(): Promise<{ status: string }> {
  return request("/api/webhooks/arm", { method: "POST" });
}
