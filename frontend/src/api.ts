import type {
  ChatResponse,
  EmailInput,
  IngestResult,
  ProcessedItem,
  Stats,
  TeamMember,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export const CANDIDATE_ID = import.meta.env.VITE_CANDIDATE_ID || "manviitnd0408@gmail.com";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
  }
  return res.json() as Promise<T>;
}

export function ingest(emails: EmailInput[], runId?: string): Promise<IngestResult> {
  return req<IngestResult>("/ingest", {
    method: "POST",
    body: JSON.stringify({ candidate_id: CANDIDATE_ID, emails, run_id: runId }),
  });
}

// Route a batch of any size by chunking into <=100-email /ingest calls that
// share one run_id, then aggregating the counts. Chunks run sequentially so a
// thread's original always lands before a reply in a later chunk.
export async function ingestChunked(emails: EmailInput[]): Promise<IngestResult> {
  const runId = crypto.randomUUID();
  const sorted = [...emails].sort((a, b) =>
    (a.received_at || "").localeCompare(b.received_at || "")
  );
  const agg: IngestResult = { processed: 0, tasks_created: 0, tasks_updated: 0, skipped: 0, errors: [], run_id: runId };
  for (let i = 0; i < sorted.length; i += 100) {
    const res = await ingest(sorted.slice(i, i + 100), runId);
    agg.processed += res.processed;
    agg.tasks_created += res.tasks_created;
    agg.tasks_updated += res.tasks_updated;
    agg.skipped += res.skipped;
    agg.errors.push(...res.errors);
  }
  return agg;
}

export function getProcessed(runId?: string): Promise<{ items: ProcessedItem[]; count: number }> {
  const q = new URLSearchParams({ candidate_id: CANDIDATE_ID });
  if (runId) q.set("run_id", runId);
  return req(`/api/tasks?${q.toString()}`);
}

export function getStats(): Promise<Stats> {
  return req(`/api/stats?candidate_id=${encodeURIComponent(CANDIDATE_ID)}`);
}

export function chat(query: string, runId?: string): Promise<ChatResponse> {
  return req<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ candidate_id: CANDIDATE_ID, query, run_id: runId }),
  });
}

export function getUsers(): Promise<{ team: TeamMember[] }> {
  return req("/users");
}

export function resetDatabase(): Promise<{ ok: boolean; deleted: Record<string, number> }> {
  return req("/api/reset", {
    method: "POST",
    body: JSON.stringify({ candidate_id: CANDIDATE_ID }),
  });
}
