export type SourceType = "meeting_transcript" | "email_thread" | "slack_conversation" | "general_notes";
export type TargetTool = "notion" | "jira" | "calendar" | "task_ledger";
export type ActionabilityType = "task" | "calendar_event" | "decision" | "fyi";
export type PriorityLevel = "low" | "medium" | "high";
export type ItemStatus = "pending" | "approved" | "rejected" | "modified_approved" | "executed" | "failed";
export type BatchStatus = "processing" | "awaiting_approval" | "executing" | "completed" | "failed" | "expired";

export interface ActionItem {
  id: string;
  batch_id: string;
  description: string;
  suggested_tool: TargetTool;
  final_tool?: TargetTool;
  tool_payload: Record<string, unknown>;
  source_snippet: string;
  speaker?: string;
  suggested_assignee?: string;
  actionability_type: ActionabilityType;
  priority: PriorityLevel;
  confidence: number;
  status: ItemStatus;
  external_url?: string;
  rejection_reason?: string;
  executed_at?: string;
  created_at: string;
}

export interface BatchResponse {
  batch_id: string;
  status: BatchStatus;
  source_type: SourceType;
  raw_text: string;
  token_count?: number;
  items: ActionItem[];
  created_at: string;
  updated_at?: string;
  temporal_workflow_id?: string;
}

export interface ActionItemDecision {
  item_id: string;
  action: "APPROVE" | "MODIFY_AND_APPROVE" | "REJECT";
  override_tool?: TargetTool;
  modified_payload?: Record<string, unknown>;
  rejection_reason?: string;
}

export interface ExecutionLog {
  id: string;
  item_id: string;
  tool: TargetTool;
  status: "success" | "failed" | "skipped_duplicate";
  external_url?: string;
  item_description?: string;
  latency_ms?: number;
  executed_at: string;
}

export interface HistoryBatch {
  batch_id: string;
  source_type: SourceType;
  status: BatchStatus;
  created_at: string;
  token_count?: number;
  total_items: number;
  executed_items: number;
  rejected_items: number;
  logs: ExecutionLog[];
}

export interface ConnectorInfo {
  healthy: boolean;
  sandbox_mode: boolean;
  oauth_connected: boolean;
  type: string;
}

export interface ConnectorsStatusResponse {
  sandbox_mode: boolean;
  connectors: Record<TargetTool, ConnectorInfo>;
  llm_providers?: {
    gemini?: { connected: boolean; model: string };
    openai?: { connected: boolean; model: string };
  };
}
