import { useEffect, useMemo, useState } from "react";
import { getProcessed, getStats, getUsers, ingestChunked } from "./api";
import ChatPanel from "./components/ChatPanel";
import Hero from "./components/Hero";
import HowItRoutes from "./components/HowItRoutes";
import InputSection from "./components/InputSection";
import RawTable from "./components/RawTable";
import RealEmailReader from "./components/RealEmailReader";
import Results from "./components/Results";
import ReviewQueue from "./components/ReviewQueue";
import RunHistory from "./components/RunHistory";
import Sidebar, { type PageId } from "./components/Sidebar";
import SkippedLog from "./components/SkippedLog";
import TaskQueue from "./components/TaskQueue";
import { generateSamples } from "./lib/sampleGen";
import type { EmailInput, ProcessedItem, Stats } from "./types";

function parseEmails(text: string): { emails: EmailInput[]; error: string | null } {
  const trimmed = text.trim();
  if (!trimmed) return { emails: [], error: null };
  let data: unknown;
  try {
    data = JSON.parse(trimmed);
  } catch (e) {
    return { emails: [], error: `Invalid JSON: ${(e as Error).message}` };
  }
  if (!Array.isArray(data)) return { emails: [], error: "Expected a JSON array of emails." };
  const bad = (data as EmailInput[]).findIndex((e) => !e || !e.email_id || !e.thread_id);
  if (bad >= 0) return { emails: [], error: `Email at index ${bad} is missing email_id or thread_id.` };
  return { emails: data as EmailInput[], error: null };
}

export default function App() {
  const [page, setPage] = useState<PageId>("inbox");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<EmailInput[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [routing, setRouting] = useState(false);
  const [items, setItems] = useState<ProcessedItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [runId, setRunId] = useState<string | undefined>(undefined);
  const [lastRunSeconds, setLastRunSeconds] = useState<number | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});

  const { count, liveError } = useMemo(() => {
    const { emails, error } = parseEmails(text);
    return { count: emails.length, liveError: error };
  }, [text]);

  async function loadData() {
    try {
      const [proc, st] = await Promise.all([getProcessed(), getStats()]);
      setItems(proc.items);
      setStats(st);
    } catch {
      /* backend not reachable yet — pages show empty states */
    }
  }

  useEffect(() => {
    getUsers().then((u) => setNames(Object.fromEntries(u.team.map((m) => [m.user_id, m.name])))).catch(() => {});
    loadData();
  }, []);

  function navigate(id: PageId) {
    setPage(id);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function scrollToId(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handlePreview() {
    const { emails, error } = parseEmails(text);
    setPreviewError(error);
    if (emails.length > 0) setPreview(emails);
  }

  function handleGenerate() {
    const emails = generateSamples(250);
    setText(JSON.stringify(emails, null, 2));
    setPreview(emails);
    setPreviewError(null);
    navigate("ingest");
  }

  function handleUploadFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      const content = String(reader.result || "");
      setText(content);
      const { emails, error } = parseEmails(content);
      setPreviewError(error);
      if (emails.length > 0) setPreview(emails);
    };
    reader.readAsText(file);
  }

  async function handleRoute() {
    if (preview.length === 0) return;
    setRouting(true);
    const t0 = performance.now();
    try {
      const res = await ingestChunked(preview);
      setLastRunSeconds(Math.max(1, Math.round((performance.now() - t0) / 1000)));
      setRunId(res.run_id);
      await loadData();
      // On the dedicated Ingest page, jump to the Results page. On the Inbox
      // landing, stay put so the inline flow (results + chat below) is reachable.
      if (page === "ingest") navigate("results");
      else setTimeout(() => scrollToId("results"), 80);
    } catch (e) {
      setPreviewError(`Routing failed: ${(e as Error).message}`);
    } finally {
      setRouting(false);
    }
  }

  return (
    <div className="app">
      <Sidebar active={page} onNavigate={navigate} />

      <main className="main">
        {page === "inbox" && (
          <>
            <Hero
              stats={stats}
              lastRunSeconds={lastRunSeconds}
              onPaste={() => scrollToId("input")}
              onGenerate={handleGenerate}
              onSelfTest={() => navigate("history")}
            />
            <HowItRoutes />

            {/* Full numbered flow inline: 1) JSON input  2) raw table  3) ask */}
            <InputSection
              text={text}
              onText={setText}
              detectedCount={count}
              error={previewError ?? liveError}
              onPreview={handlePreview}
              onGenerate={handleGenerate}
              onUploadFile={handleUploadFile}
            />
            {preview.length > 0 && <RawTable emails={preview} onRoute={handleRoute} routing={routing} />}
            {items.length > 0 && <Results items={items} names={names} initialLimit={5} />}
            <ChatPanel runId={runId} />
          </>
        )}

        {page === "ingest" && (
          <>
            <div className="page-head">
              <h2 className="page-title">Inbox Ingest &amp; Triage</h2>
              <p className="page-sub">Paste, upload, or generate a batch, preview the raw emails, then route them through the pipeline.</p>
            </div>
            <InputSection
              text={text}
              onText={setText}
              detectedCount={count}
              error={previewError ?? liveError}
              onPreview={handlePreview}
              onGenerate={handleGenerate}
              onUploadFile={handleUploadFile}
            />
            {preview.length > 0 && <RawTable emails={preview} onRoute={handleRoute} routing={routing} />}
          </>
        )}

        {page === "queue" && <TaskQueue items={items} names={names} />}
        {page === "reader" && <RealEmailReader names={names} onRouted={loadData} />}

        {page === "results" && (
          <>
            <div className="page-head">
              <h2 className="page-title">Results</h2>
              <p className="page-sub">Every processed email with its full decision trace — created, updated, skipped, and triage.</p>
            </div>
            <Results items={items} names={names} />
          </>
        )}

        {page === "skipped" && <SkippedLog items={items} />}

        {page === "decisions" && (
          <>
            <div className="page-head">
              <h2 className="page-title">Decision Center</h2>
              <p className="page-sub">Ask grounded questions about the processed batch — numbers come from stored data, never invented.</p>
            </div>
            <ChatPanel runId={runId} />
          </>
        )}

        {page === "review" && <ReviewQueue items={items} names={names} />}
        {page === "history" && <RunHistory stats={stats} onReset={loadData} />}

        <div className="foot">
          Sales Inbox → Task Router · candidate_id manviitnd0408@gmail.com · every number is grounded in stored data.
        </div>
      </main>
    </div>
  );
}
