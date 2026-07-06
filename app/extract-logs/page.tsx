"use client";

import Link from "next/link";
import { useState } from "react";
import { ResultsPanel } from "../_lib/ResultsPanel";

type ExtractLogsResult =
  | { ok: true; logs: Record<string, unknown>[]; report: Record<string, unknown> }
  | { ok: false; error: string };

type FileReportEntry = { filename: string; detected_format: string | null; row_count: number; error: string | null };

function getFiles(report: Record<string, unknown>): FileReportEntry[] {
  return Array.isArray(report.files) ? (report.files as FileReportEntry[]) : [];
}

export default function ExtractLogsPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [format, setFormat] = useState("auto");
  const [tz, setTz] = useState("America/Sao_Paulo");
  const [result, setResult] = useState<ExtractLogsResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    setLoading(true);
    setResult(null);
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    formData.append("format", format);
    formData.append("tz", tz);
    try {
      const res = await fetch("/api/extract-logs", { method: "POST", body: formData });
      const data: ExtractLogsResult = await res.json();
      setResult(data);
    } catch (err) {
      setResult({
        ok: false,
        error: err instanceof Error ? err.message : "Request failed. Please try again.",
      });
    } finally {
      setLoading(false);
    }
  }

  const reportFiles = result && result.ok ? getFiles(result.report) : [];
  const reportFailedFiles = reportFiles.filter((f) => f.error);

  return (
    <main className="shell">
      <Link href="/" className="back-link">
        ← All tools
      </Link>
      <div className="eyebrow">tagmatch / tools / extract-logs</div>
      <h1>Log Extraction</h1>
      <p className="lede">
        Upload one or more log files (Logcat, NDJSON, Dev JSON, Firebase).
        They&apos;re parsed, merged, and deduplicated into a single events
        table.
      </p>

      <form onSubmit={handleSubmit} className="panel control-panel">
        <label className="file-input-label">
          <input
            type="file"
            accept=".txt,.log,.json,.ndjson"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
          Choose files
        </label>
        <span className="file-name">
          {files.length === 0
            ? "No files chosen"
            : files.length === 1
              ? files[0].name
              : `${files.length} files`}
        </span>
        <select value={format} onChange={(e) => setFormat(e.target.value)} aria-label="Log format">
          <option value="auto">auto-detect (default)</option>
          <option value="logcat">logcat</option>
          <option value="ndjson">ndjson</option>
          <option value="dev_json">dev_json</option>
          <option value="firebase_javascript">firebase_javascript</option>
        </select>
        <input
          value={tz}
          onChange={(e) => setTz(e.target.value)}
          aria-label="Timezone"
          className="tz-input"
        />
        <button type="submit" className="btn btn-primary" disabled={files.length === 0 || loading}>
          {loading ? "Extracting…" : "Extract →"}
        </button>
      </form>

      {result && !result.ok && (
        <p className="alert-error">Couldn&apos;t extract logs: {result.error}</p>
      )}

      {result && result.ok && (
        <>
          {reportFailedFiles.length > 0 && (
            <p className="alert-warning">
              {reportFailedFiles.length} of {reportFiles.length}{" "}
              file(s) couldn&apos;t be parsed — see Full report below for
              details.
            </p>
          )}
          <ResultsPanel
            rows={result.logs}
            report={result.report}
            entityLabel="Logs"
            badgeColumn="name_norm"
            downloadBaseName="logs"
          />
        </>
      )}
    </main>
  );
}
