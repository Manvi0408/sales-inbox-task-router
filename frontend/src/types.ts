export interface EmailInput {
  email_id: string;
  thread_id: string;
  message_index?: number;
  from_name?: string;
  from_email?: string;
  to?: string;
  cc?: string[];
  subject?: string;
  body?: string;
  received_at?: string;
  attachments?: string[];
  is_reply?: boolean;
}

export interface IngestResult {
  processed: number;
  tasks_created: number;
  tasks_updated: number;
  skipped: number;
  errors: { email_id: string; error: string }[];
  run_id: string;
}

export interface TaskSpec {
  task_id: string;
  candidate_id: string;
  source_email_id: string;
  thread_id: string;
  title: string;
  description: string | null;
  assignee_id: string;
  category: string;
  priority: string;
  due_date: string | null;
  deal_value_inr: number | null;
  company_name: string | null;
  confidence: number;
  created_at: string;
  updated_at: string;
}

export interface Revision {
  revision_index: number;
  source_email_id: string;
  changed_fields: Record<string, { from: unknown; to: unknown }>;
  created_at: string;
}

export interface ProcessedItem {
  email_id: string;
  thread_id: string;
  message_index: number | null;
  from_name: string | null;
  from_email: string | null;
  subject: string | null;
  received_at: string | null;
  is_reply: boolean;
  decision: "created" | "updated" | "skipped" | "error";
  skip_reason: string | null;
  category: string | null;
  assignee_id: string | null;
  confidence: number | null;
  reasoning: string | null;
  direction_of_intent: string | null;
  rules_fired: string[];
  llm_proposed_assignee: string | null;
  override_applied: boolean;
  is_spurious: boolean;
  task_id: string | null;
  run_id: string | null;
  latency_ms: number | null;
  token_count: number | null;
  task: TaskSpec | null;
  revisions: Revision[];
  revision_count: number;
}

export interface Stats {
  candidate_id: string;
  processed: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  spurious: number;
  spurious_rate: number;
  by_category: Record<string, number>;
  by_assignee: Record<string, number>;
  by_skip_reason: Record<string, number>;
  by_run: Record<string, { processed: number; created: number; updated: number; skipped: number }>;
  avg_latency_ms: number;
  total_tokens: number;
  run_count: number;
}

export interface ChatResponse {
  answer: string;
  supporting_data: Record<string, unknown>;
  query: { intent: string; filters: Record<string, unknown>; scope: string; run_id: string | null };
}

export interface TeamMember {
  user_id: string;
  name: string;
  department: string;
  scope: string;
}
