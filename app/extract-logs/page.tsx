"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ResultsPanel } from "../_lib/ResultsPanel";
import {
  getServerSnapshot,
  getSnapshot,
  loadSession,
  saveLogs,
  subscribe,
} from "../_lib/sessionStore";

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

  // Names of the files behind a session-restored result (no File objects exist then).
  const [restoredFiles, setRestoredFiles] = useState<string[] | null>(null);
  const meta = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const hadSessionLogs = useRef(false);
  const skipHydration = useRef(false);

  // Hydrate from the tab session on mount.
  useEffect(() => {
    let cancelled = false;
    void loadSession().then(({ logs }) => {
      if (cancelled || skipHydration.current || !logs) return;
      setResult({ ok: true, logs: logs.logs, report: logs.report });
      setRestoredFiles(logs.fileNames);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // When the session logs are cleared (✕ in the bar), drop the page state too.
  useEffect(() => {
    if (meta.logs) {
      hadSessionLogs.current = true;
    } else if (hadSessionLogs.current) {
      hadSessionLogs.current = false;
      setResult(null);
      setRestoredFiles(null);
      setFiles([]);
    }
  }, [meta.logs]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    skipHydration.current = true;
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
      if (data.ok) {
        setRestoredFiles(null);
        void saveLogs({
          logs: data.logs,
          report: data.report,
          fileNames: files.map((f) => f.name),
        });
      }
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
            ? (restoredFiles ? restoredFiles.join(", ") : "No files chosen")
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

      {restoredFiles && result && result.ok && (
        <p className="handoff-banner">
          Logs da sessão · {restoredFiles.join(", ")} · {result.logs.length} eventos.
        </p>
      )}

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
