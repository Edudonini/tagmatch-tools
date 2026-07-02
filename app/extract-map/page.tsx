"use client";

import { useState } from "react";

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

  return (
    <main style={{ padding: 24, fontFamily: "sans-serif" }}>
      <h1>Map Extraction</h1>
      <p>Upload a Whimsical SVG export to extract the TagMatch event spec.</p>

      <form onSubmit={handleSubmit}>
        <input
          type="file"
          accept=".svg"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="card">card (default, matches production)</option>
          <option value="header">header</option>
          <option value="hybrid">hybrid</option>
        </select>
        <button type="submit" disabled={!file || loading}>
          {loading ? "Extracting..." : "Extract"}
        </button>
      </form>

      {result && !result.ok && (
        <p style={{ color: "red" }}>Error: {result.error}</p>
      )}

      {result && result.ok && (
        <>
          <h2>Report</h2>
          <pre>{JSON.stringify(result.report, null, 2)}</pre>

          <h2>Spec ({result.spec.length} events)</h2>
          <div>
            <button onClick={() => download("json")}>Download JSON</button>
            <button onClick={() => download("csv")}>Download CSV</button>
          </div>
          <table border={1} cellPadding={4}>
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
                    <td key={c}>{String(row[c] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
