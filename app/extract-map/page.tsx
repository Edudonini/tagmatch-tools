"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ReviewMode } from "./review/ReviewMode";
import { MapView } from "./mapview/MapView";
import { clearSvgCropCache } from "./review/useSvgCropUrl";
import {
  getServerSnapshot,
  getSnapshot,
  loadSession,
  saveMap,
  subscribe,
  updateMapSpec,
} from "../_lib/sessionStore";

type ExtractResult =
  | { ok: true; spec: Record<string, unknown>[]; report: Record<string, unknown> }
  | { ok: false; error: string };

type View = "map" | "review";

export default function ExtractMapPage() {
  const [file, setFile] = useState<File | null>(null);
  // Survives session restore, when there is no File object to show.
  const [fileName, setFileName] = useState<string | null>(null);
  const [mode, setMode] = useState("card");
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [svgContent, setSvgContent] = useState<string | null>(null);
  const [view, setView] = useState<View>("map");
  const meta = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const hadSessionMap = useRef(false);
  // Set when the user starts a new upload; stops a slow hydration from
  // overwriting the in-flight extraction with the stale session map.
  const skipHydration = useRef(false);

  // Hydrate from the tab session on mount.
  useEffect(() => {
    let cancelled = false;
    void loadSession().then(({ map }) => {
      if (cancelled || skipHydration.current || !map) return;
      setSvgContent(map.svgText);
      setFileName(map.fileName);
      setResult({ ok: true, spec: map.spec, report: map.report });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // When the session map is cleared (✕ in the bar), drop the page state too.
  useEffect(() => {
    if (meta.map) {
      hadSessionMap.current = true;
    } else if (hadSessionMap.current) {
      hadSessionMap.current = false;
      setResult(null);
      setSvgContent(null);
      setFileName(null);
      setFile(null);
      setView("map");
      clearSvgCropCache();
    }
  }, [meta.map]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    skipHydration.current = true;
    setLoading(true);
    setResult(null);
    setView("map");
    clearSvgCropCache();
    const text = await file.text();
    setSvgContent(text);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    try {
      const res = await fetch("/api/extract-map", { method: "POST", body: formData });
      const data: ExtractResult = await res.json();
      setResult(data);
      if (data.ok) {
        setFileName(file.name);
        void saveMap({
          svgText: text,
          fileName: file.name,
          spec: data.spec,
          report: data.report,
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
        <span className="file-name">{file ? file.name : (fileName ?? "No file chosen")}</span>
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

      {result && result.ok && view === "map" && (
        <MapView rows={result.spec} report={result.report} onReview={() => setView("review")} />
      )}

      {result && result.ok && view === "review" && (
        <ReviewMode
          rows={result.spec}
          svgContent={svgContent}
          onChange={(newRows) => {
            setResult((prev) => (prev && prev.ok ? { ...prev, spec: newRows } : prev));
            void updateMapSpec(newRows);
          }}
          onExit={() => setView("map")}
        />
      )}
    </main>
  );
}
