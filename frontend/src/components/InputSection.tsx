import { useRef, useState } from "react";
import { CANDIDATE_ID } from "../api";

interface Props {
  text: string;
  onText: (v: string) => void;
  detectedCount: number;
  error: string | null;
  onPreview: () => void;
  onGenerate: () => void;
  onUploadFile: (file: File) => void;
}

export default function InputSection({
  text, onText, detectedCount, error, onPreview, onGenerate, onUploadFile,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onUploadFile(f);
  }

  return (
    <section className="card section" id="input">
      <div className="section-head">
        <span className="section-title">1 · paste, upload, or drop inbox JSON</span>
        <span className="section-sub">candidate_id: {CANDIDATE_ID}</span>
      </div>

      <textarea
        className={`batch-input${dragging ? " dragover" : ""}`}
        placeholder='Paste a JSON array of emails — or drag a .json file here. e.g. [ { "email_id": "em_00142", "thread_id": "th_0091", "subject": "...", "body": "...", "received_at": "2026-08-01T09:14:22+05:30" } ]'
        value={text}
        onChange={(e) => onText(e.target.value)}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      />

      <div className="input-controls">
        <button className="btn btn-primary btn-sm" onClick={onPreview} disabled={detectedCount === 0}>
          Preview batch
        </button>
        <button className="btn btn-outline btn-sm" onClick={() => fileRef.current?.click()}>
          Upload JSON
        </button>
        <button className="btn btn-outline btn-sm" onClick={onGenerate}>
          Generate 250 samples
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden-file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUploadFile(f);
            e.target.value = "";
          }}
        />
        <span className="count-badge">{detectedCount} email{detectedCount === 1 ? "" : "s"} detected</span>
      </div>

      {error && <div className="inline-error">⚠ {error}</div>}
    </section>
  );
}
