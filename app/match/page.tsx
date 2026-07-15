"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ResultsPanel, type ResultRow } from "../_lib/ResultsPanel";
import { MatchDetailDrawer, type MatchRow } from "./MatchDetailDrawer";
import { Dropzone } from "../_lib/Dropzone";
import { StatRail } from "../_lib/StatRail";
import {
  getServerSnapshot,
  getSnapshot,
  loadSession,
  logsToFile,
  rowsToSpecFile,
  subscribe,
} from "../_lib/sessionStore";

type MatchResult =
  | {
      ok: true;
      matches: Record<string, unknown>[];
      extras: Record<string, unknown>[];
      summary: Record<string, unknown>;
    }
  | { ok: false; error: string };

const SUMMARY_ORDER = [
  "coverage_pct",
  "matched",
  "unmatched",
  "extras_logs",
  "spec_count",
  "log_count",
];

export default function MatchPage() {
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [logsFile, setLogsFile] = useState<File | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [drawerIndex, setDrawerIndex] = useState<number | null>(null);
  const [fromHandoff, setFromHandoff] = useState(false);
  const [handoffCount, setHandoffCount] = useState(0);
  const [sessionFileName, setSessionFileName] = useState<string | null>(null);
  const [logsFromSessionCount, setLogsFromSessionCount] = useState(0);
  const specTouched = useRef(false);
  const logsTouched = useRef(false);
  const meta = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  useEffect(() => {
    let cancelled = false;
    void loadSession().then(({ map, logs }) => {
      if (cancelled) return;
      if (!specTouched.current && map && map.spec.length > 0) {
        setSpecFile(rowsToSpecFile(map.spec));
        setHandoffCount(map.spec.length);
        setSessionFileName(map.fileName);
        setFromHandoff(true);
      }
      if (!logsTouched.current && logs && logs.logs.length > 0) {
        setLogsFile(logsToFile(logs.logs));
        setLogsFromSessionCount(logs.logs.length);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Drop session-derived state when the session map is cleared (✕ in the bar).
  // Syncing from the external session store is intentional; the guard makes it idempotent.
  useEffect(() => {
    if (!meta.map && fromHandoff) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSpecFile(null);
      setFromHandoff(false);
      setHandoffCount(0);
      setSessionFileName(null);
    }
  }, [meta.map, fromHandoff]);

  useEffect(() => {
    if (!meta.logs && logsFromSessionCount > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLogsFile(null);
      setLogsFromSessionCount(0);
    }
  }, [meta.logs, logsFromSessionCount]);

  async function handleMatch() {
    if (!specFile || !logsFile) return;
    setLoading(true);
    setResult(null);
    setDrawerIndex(null);
    const formData = new FormData();
    formData.append("spec", specFile);
    formData.append("logs", logsFile);
    try {
      const res = await fetch("/api/match", { method: "POST", body: formData });
      const data: MatchResult = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ ok: false, error: err instanceof Error ? err.message : "Request failed. Please try again." });
    } finally {
      setLoading(false);
    }
  }

  const summaryTiles =
    result && result.ok
      ? SUMMARY_ORDER.filter((k) => k in result.summary).map((k) => ({
          key: k,
          value: result.summary[k],
        }))
      : [];

  const matches = result && result.ok ? result.matches : [];
  const coveragePct = result && result.ok ? Number(result.summary.coverage_pct ?? 0) : 0;
  const coverageTone =
    coveragePct >= 80 ? "var(--nonint)" : coveragePct >= 50 ? "var(--warning)" : "var(--error)";

  return (
    <main className="shell">
      <div className="narrow">
        <div className="eyebrow">tagmatch / tools / match</div>
        <h1>Matching</h1>
        <p className="lede">
          Use um spec extraído e os logs extraídos. Veja quais eventos do spec
          dispararam, com confiança, divergências e os logs que não casaram com
          nada.
        </p>

        <div className="panel control-panel">
          <Dropzone
            accept=".json,.csv"
            onFiles={(files) => {
              specTouched.current = true;
              setSpecFile(files[0] ?? null);
              setFromHandoff(false);
            }}
            selectedLabel={specFile ? specFile.name : null}
            idle="Arraste o spec (.json/.csv), ou clique para escolher"
            hint="spec · da Extração de Mapa"
          />
          <Dropzone
            accept=".json,.csv"
            onFiles={(files) => {
              logsTouched.current = true;
              setLogsFile(files[0] ?? null);
              setLogsFromSessionCount(0);
            }}
            selectedLabel={logsFile ? logsFile.name : null}
            idle="Arraste os logs (.json/.csv), ou clique para escolher"
            hint="logs · da Extração de Logs"
          />
          <div className="control-row">
            <button className="btn btn-primary" onClick={handleMatch} disabled={!specFile || !logsFile || loading}>
              {loading ? "Casando…" : "Casar →"}
            </button>
          </div>
        </div>

        {fromHandoff && specFile && (
          <p className="handoff-banner">
            Spec do mapa da sessão{sessionFileName ? ` · ${sessionFileName}` : ""} · {handoffCount} eventos.
          </p>
        )}
        {logsFromSessionCount > 0 && logsFile && (
          <p className="handoff-banner">Logs da sessão · {logsFromSessionCount} eventos.</p>
        )}

        {result && !result.ok && (
          <p className="alert-error">Não consegui rodar o matching: {result.error}</p>
        )}
      </div>

      {result && result.ok && (
        <>
          <div className="narrow">
            <StatRail
              stats={summaryTiles.map((t) => {
                const isCoverage = t.key === "coverage_pct";
                return {
                  label: t.key.replace(/_/g, " "),
                  value: isCoverage ? `${Number(t.value).toFixed(1)}%` : String(t.value),
                  tone: isCoverage ? ("accent" as const) : ("default" as const),
                  accessory: isCoverage ? (
                    <div className="coverage-bar">
                      <span style={{ width: `${Math.min(100, coveragePct)}%`, background: coverageTone }} />
                    </div>
                  ) : undefined,
                };
              })}
            />
          </div>

          <ResultsPanel
            rows={result.matches}
            report={{}}
            entityLabel="Matches"
            badgeColumn="name"
            downloadBaseName="matches"
            onRowClick={(row: ResultRow) => setDrawerIndex(result.matches.indexOf(row))}
          />

          <ResultsPanel
            rows={result.extras}
            report={{}}
            entityLabel="Extras"
            badgeColumn="name_norm"
            downloadBaseName="extras"
          />
        </>
      )}

      {drawerIndex !== null && matches[drawerIndex] && (
        <MatchDetailDrawer
          row={matches[drawerIndex] as MatchRow}
          position={{ index: drawerIndex, total: matches.length }}
          onPrev={drawerIndex > 0 ? () => setDrawerIndex(drawerIndex - 1) : undefined}
          onNext={drawerIndex < matches.length - 1 ? () => setDrawerIndex(drawerIndex + 1) : undefined}
          onClose={() => setDrawerIndex(null)}
        />
      )}
    </main>
  );
}
