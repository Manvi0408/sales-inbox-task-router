import { useState } from "react";
import { getProcessed, ingest } from "../api";
import type { EmailInput, ProcessedItem } from "../types";
import fixture from "../lib/workedExamples.json";

interface Expected {
  decision: string;
  assignee_id?: string;
  category?: string;
  priority?: string;
  due_date?: string | null;
  deal_value_inr?: number | null;
  company_name?: string | null;
  skip_reason?: string;
  confidence_below?: number;
}
interface Example extends EmailInput { expected: Expected }

interface RowResult {
  id: string;
  pass: boolean;
  expected: string;
  actual: string;
}

// em_ex01 gets mutated by the em_ex10 reply, so only its stable routing fields
// (decision/assignee/category) are asserted — value fields are checked on ex10.
const MUTATED_LATER = new Set(["em_ex01"]);

function compare(ex: Example, item: ProcessedItem | undefined): RowResult {
  const exp = ex.expected;
  const parts: string[] = [];
  const act: string[] = [];
  let pass = true;

  const eq = (label: string, e: unknown, a: unknown) => {
    parts.push(`${label}=${e ?? "null"}`);
    act.push(`${label}=${a ?? "null"}`);
    if (e !== a) pass = false;
  };

  if (!item) {
    return { id: ex.email_id, pass: false, expected: JSON.stringify(exp), actual: "no record found" };
  }

  eq("decision", exp.decision, item.decision);

  if (exp.decision === "skipped") {
    eq("skip", exp.skip_reason, item.skip_reason);
  } else {
    eq("assignee", exp.assignee_id, item.assignee_id || item.task?.assignee_id);
    eq("category", exp.category, item.category);
    if (!MUTATED_LATER.has(ex.email_id)) {
      if (exp.priority) eq("priority", exp.priority, item.task?.priority);
      if ("due_date" in exp) eq("due", exp.due_date, item.task?.due_date ?? null);
      if ("deal_value_inr" in exp) eq("deal", exp.deal_value_inr, item.task?.deal_value_inr ?? null);
    }
    if (exp.confidence_below != null) {
      const c = item.confidence ?? 1;
      parts.push(`conf<${exp.confidence_below}`);
      act.push(`conf=${c.toFixed(2)}`);
      if (!(c < exp.confidence_below)) pass = false;
    }
  }

  return { id: ex.email_id, pass, expected: parts.join(" "), actual: act.join(" ") };
}

export default function SelfTest() {
  const [rows, setRows] = useState<RowResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setErr(null);
    setRows([]);
    try {
      const examples = fixture.emails as Example[];
      const emails: EmailInput[] = examples.map(({ expected, ...e }) => { void expected; return e; });
      const res = await ingest(emails);
      const processed = await getProcessed(res.run_id);
      const byId = new Map(processed.items.map((it) => [it.email_id, it]));
      setRows(examples.map((ex) => compare(ex, byId.get(ex.email_id))));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const passed = rows.filter((r) => r.pass).length;

  return (
    <section className="card section" id="selftest">
      <div className="section-head">
        <span className="section-title">Self-test · 12 worked examples</span>
        <button className="btn btn-outline btn-sm" onClick={run} disabled={busy}>
          {busy ? "Running…" : "Run self-test"}
        </button>
      </div>
      {err && <div className="inline-error">⚠ {err}</div>}
      {rows.length > 0 && (
        <>
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            {passed}/{rows.length} passed
          </div>
          {rows.map((r) => (
            <div key={r.id} className="selftest-row">
              <span className={r.pass ? "st-pass" : "st-fail"}>{r.pass ? "✓" : "✗"}</span>
              <span className="st-cell mono">{r.expected}</span>
              <span className="st-cell mono">{r.actual}</span>
              <span className="mono">{r.id}</span>
            </div>
          ))}
        </>
      )}
      {rows.length === 0 && !busy && !err && (
        <div className="loading">
          Posts the twelve §6 worked examples to the live backend and checks expected vs actual.
        </div>
      )}
    </section>
  );
}
