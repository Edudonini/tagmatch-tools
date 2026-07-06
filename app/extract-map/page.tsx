"use client";

import Link from "next/link";
import { useState } from "react";
import { ResultsPanel } from "../_lib/ResultsPanel";

type ExtractResult =
  | { ok: true; spec: Record<string, unknown>[]; report: Record<string, unknown> }
  | { ok: false; error: string };

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
        <ResultsPanel
          rows={result.spec}
          report={result.report}
          entityLabel="Spec"
          badgeColumn="name"
          downloadBaseName="spec"
        />
      )}
    </main>
  );
}
