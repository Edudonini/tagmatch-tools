"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ResultsPanel, type ResultRow } from "../_lib/ResultsPanel";
import { MatchDetailDrawer, type MatchRow } from "./MatchDetailDrawer";
import { takeSpecHandoff, rowsToSpecFile } from "../_lib/specHandoff";

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
  const [drawerRow, setDrawerRow] = useState<MatchRow | null>(null);
  const [fromHandoff, setFromHandoff] = useState(false);
  const [handoffCount, setHandoffCount] = useState(0);

  useEffect(() => {
    const rows = takeSpecHandoff();
    if (rows && rows.length > 0) {
      setSpecFile(rowsToSpecFile(rows));
      setHandoffCount(rows.length);
      setFromHandoff(true);
    }
  }, []);

  async function handleMatch() {
    if (!specFile || !logsFile) return;
    setLoading(true);
    setResult(null);
    setDrawerRow(null);
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

  return (
    <main className="shell">
      <Link href="/" className="back-link">
        ← All tools
      </Link>
      <div className="eyebrow">tagmatch / tools / match</div>
      <h1>Matching</h1>
      <p className="lede">
        Upload an extracted spec and extracted logs. See which spec events
        fired, with confidence, divergences, and the logs that matched
        nothing.
      </p>

      <div className="panel control-panel">
        <label className="file-input-label">
          <input
            type="file"
            accept=".json,.csv"
            onChange={(e) => {
              setSpecFile(e.target.files?.[0] ?? null);
              setFromHandoff(false);
            }}
          />
          Choose spec
        </label>
        <span className="file-name">{specFile ? specFile.name : "No spec chosen"}</span>
        <label className="file-input-label">
          <input type="file" accept=".json,.csv" onChange={(e) => setLogsFile(e.target.files?.[0] ?? null)} />
          Choose logs
        </label>
        <span className="file-name">{logsFile ? logsFile.name : "No logs chosen"}</span>
        <button className="btn btn-primary" onClick={handleMatch} disabled={!specFile || !logsFile || loading}>
          {loading ? "Matching…" : "Match →"}
        </button>
      </div>

      {fromHandoff && specFile && (
        <p className="handoff-banner">Spec carregado da Extração de Mapa · {handoffCount} eventos.</p>
      )}

      {result && !result.ok && <p className="alert-error">Couldn&apos;t run matching: {result.error}</p>}

      {result && result.ok && (
        <>
          <div className="stats">
            {summaryTiles.map((t) => (
              <div className="stat" key={t.key}>
                <div className="stat-label">{t.key.replace(/_/g, " ")}</div>
                <div className="stat-value">{String(t.value)}</div>
              </div>
            ))}
          </div>

          <ResultsPanel
            rows={result.matches}
            report={{}}
            entityLabel="Matches"
            badgeColumn="name"
            downloadBaseName="matches"
            onRowClick={(row: ResultRow) => setDrawerRow(row as MatchRow)}
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

      {drawerRow && <MatchDetailDrawer row={drawerRow} onClose={() => setDrawerRow(null)} />}
    </main>
  );
}
