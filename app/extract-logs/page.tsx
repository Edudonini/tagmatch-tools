"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ResultsPanel } from "../_lib/ResultsPanel";
import { Dropzone } from "../_lib/Dropzone";
import { NextSteps } from "../_lib/NextSteps";
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
      <div className="narrow">
        <div className="eyebrow">tagmatch / tools / extract-logs</div>
        <h1>Extração de Logs</h1>
        <p className="lede">
          Suba um ou mais arquivos de log (Logcat, NDJSON, Dev JSON, Firebase).
          Eles são interpretados, mesclados e deduplicados numa tabela única de
          eventos.
        </p>

        <form onSubmit={handleSubmit} className="panel control-panel">
          <Dropzone
            accept=".txt,.log,.json,.ndjson"
            multiple
            onFiles={(picked) => setFiles(picked)}
            selectedLabel={
              files.length === 0
                ? restoredFiles
                  ? restoredFiles.join(", ")
                  : null
                : files.length === 1
                  ? files[0].name
                  : `${files.length} arquivos`
            }
            idle="Arraste os arquivos de log, ou clique para escolher"
            hint=".txt · .log · .json · .ndjson"
          />
          <div className="control-row">
            <select value={format} onChange={(e) => setFormat(e.target.value)} aria-label="Formato do log">
              <option value="auto">detecção automática (padrão)</option>
              <option value="logcat">logcat</option>
              <option value="ndjson">ndjson</option>
              <option value="dev_json">dev_json</option>
              <option value="firebase_javascript">firebase_javascript</option>
            </select>
            <input
              value={tz}
              onChange={(e) => setTz(e.target.value)}
              aria-label="Fuso horário"
              className="tz-input"
            />
            <button type="submit" className="btn btn-primary" disabled={files.length === 0 || loading}>
              {loading ? "Extraindo…" : "Extrair →"}
            </button>
          </div>
        </form>

        {restoredFiles && result && result.ok && (
          <p className="handoff-banner">
            Logs da sessão · {restoredFiles.join(", ")} · {result.logs.length} eventos.
          </p>
        )}

        {result && !result.ok && (
          <p className="alert-error">Não consegui extrair os logs: {result.error}</p>
        )}
      </div>

      {result && result.ok && (
        <>
          {reportFailedFiles.length > 0 && (
            <div className="narrow">
              <p className="alert-warning">
                {reportFailedFiles.length} de {reportFiles.length} arquivo(s) não
                puderam ser interpretados — veja o relatório completo abaixo.
              </p>
            </div>
          )}
          <ResultsPanel
            rows={result.logs}
            report={result.report}
            entityLabel="Logs"
            badgeColumn="name_norm"
            downloadBaseName="logs"
          />
          <NextSteps tool="extract-logs" />
        </>
      )}
    </main>
  );
}
