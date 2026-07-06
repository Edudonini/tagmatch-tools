"use client";

import Link from "next/link";
import { useState } from "react";

type ExtractResult =
  | { ok: true; spec: Record<string, unknown>[]; report: Record<string, unknown> }
  | { ok: false; error: string };

function badgeClass(name: unknown): string {
  const v = String(name ?? "").toLowerCase();
  if (v === "screen_view") return "badge-sv";
  if (v === "interaction") return "badge-int";
  if (v === "noninteraction") return "badge-nonint";
  return "badge-other";
}

function badgeLabel(name: unknown): string {
  const v = String(name ?? "").toLowerCase();
  if (v === "screen_view") return "SV";
  if (v === "interaction") return "INT";
  if (v === "noninteraction") return "NON";
  return v ? v.slice(0, 3).toUpperCase() : "—";
}

export default function ExtractMapPage() {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("card");
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setResult(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    try {
      const res = await fetch("/api/extract-map", { method: "POST", body: formData });
      const data: ExtractResult = await res.json();
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

  function download(format: "json" | "csv") {
    if (!result || !result.ok) return;
    let blob: Blob;
    let filename: string;
    if (format === "json") {
      blob = new Blob([JSON.stringify(result.spec, null, 2)], { type: "application/json" });
      filename = "spec.json";
    } else {
      const columns = Array.from(
        result.spec.reduce((set, row) => {
          Object.keys(row).forEach((k) => set.add(k));
          return set;
        }, new Set<string>())
      );
      const lines = [
        columns.join(","),
        ...result.spec.map((row) =>
          columns
            .map((c) => {
              const v = row[c];
              const s = v === null || v === undefined ? "" : String(v);
              return `"${s.replace(/"/g, '""')}"`;
            })
            .join(",")
        ),
      ];
      blob = new Blob([lines.join("\n")], { type: "text/csv" });
      filename = "spec.csv";
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const columns = result && result.ok && result.spec.length > 0 ? Object.keys(result.spec[0]) : [];
  const nameCol = columns.find((c) => c.toLowerCase() === "name");

  const reportEntries = result && result.ok ? Object.entries(result.report) : [];
  const scalarStats = reportEntries.filter(
    ([, v]) => v === null || ["string", "number", "boolean"].includes(typeof v)
  );
  const nestedReport = Object.fromEntries(reportEntries.filter(([k]) => !scalarStats.some(([sk]) => sk === k)));

  return (
    <main className="shell">
      <Link href="/" className="back-link">
        ← All tools
      </Link>
      <div className="eyebrow">tagmatch / tools / extract-map</div>
      <h1>Map Extraction</h1>
      <p className="lede">
        Upload a Whimsical SVG export. It comes back as a structured event
        spec — same fields TagMatch uses to match logs.
      </p>

      <form onSubmit={handleSubmit} className="panel control-panel">
        <label className="file-input-label">
          <input
            type="file"
            accept=".svg"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          Choose file
        </label>
        <span className="file-name">{file ? file.name : "No file chosen"}</span>
        <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Extraction mode">
          <option value="card">card (default)</option>
          <option value="header">header</option>
          <option value="hybrid">hybrid</option>
        </select>
        <button type="submit" className="btn btn-primary" disabled={!file || loading}>
          {loading ? "Extracting…" : "Extract →"}
        </button>
      </form>

      {result && !result.ok && (
        <p className="alert-error">Couldn&apos;t extract a spec: {result.error}</p>
      )}

      {result && result.ok && (
        <>
          {scalarStats.length > 0 && (
            <div className="stats">
              {scalarStats.map(([key, value]) => (
                <div className="stat" key={key}>
                  <div className="stat-label">{key.replace(/_/g, " ")}</div>
                  <div className="stat-value">{String(value)}</div>
                </div>
              ))}
            </div>
          )}

          {Object.keys(nestedReport).length > 0 && (
            <details className="report-details">
              <summary>Full report</summary>
              <pre>{JSON.stringify(nestedReport, null, 2)}</pre>
            </details>
          )}

          <div className="results-header">
            <h2>Spec — {result.spec.length} events</h2>
            <div className="results-actions">
              <button className="btn btn-ghost" onClick={() => download("json")}>
                Download JSON
              </button>
              <button className="btn btn-ghost" onClick={() => download("csv")}>
                Download CSV
              </button>
            </div>
          </div>

          <div className="spec-table-wrap">
            <table>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.spec.map((row, i) => (
                  <tr key={i}>
                    {columns.map((c) => (
                      <td key={c}>
                        {c === nameCol ? (
                          <span className={`badge ${badgeClass(row[c])}`}>
                            <span className="dot" />
                            {badgeLabel(row[c])} {String(row[c] ?? "")}
                          </span>
                        ) : (
                          String(row[c] ?? "")
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
