"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { badgeClass, badgeLabel } from "../_lib/ResultsPanel";
import { takeSpecHandoff, rowsToSpecFile } from "../_lib/specHandoff";
import {
  CustomOptions,
  DEFAULT_OUTPUT_COLUMNS,
  type CustomOptionsState,
  type SpecEvent,
} from "./CustomOptions";

type GenerateResult =
  | { ok: true; query: string; event_mapping: Record<string, string>; metadata: Record<string, unknown> }
  | { ok: false; error: string };

const QUERY_TYPES = [
  { value: "validation", label: "Validation" },
  { value: "volumetry", label: "Volumetry" },
  { value: "funnel", label: "Funnel (linear)" },
  { value: "custom", label: "Custom" },
] as const;

const DEFAULT_TABLE = "ecare_silver.b2c_ga4.silver_ga4_novo_app";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function BuildQueryPage() {
  const [file, setFile] = useState<File | null>(null);
  const [events, setEvents] = useState<SpecEvent[] | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [fromHandoff, setFromHandoff] = useState(false);

  const [queryType, setQueryType] = useState<string>("validation");
  const [startDate, setStartDate] = useState(() => isoDaysAgo(7));
  const [endDate, setEndDate] = useState(() => isoDaysAgo(0));
  const [countMode, setCountMode] = useState("session");
  const [samplePerEvent, setSamplePerEvent] = useState(5);
  const [groupBy, setGroupBy] = useState("event");
  const [includeEventCount, setIncludeEventCount] = useState(true);
  const [screenOrder, setScreenOrder] = useState<string[]>([]);
  const [customOptions, setCustomOptions] = useState<CustomOptionsState>({
    selectedOrders: [],
    filterFields: {},
    outputColumns: [...DEFAULT_OUTPUT_COLUMNS],
  });
  const [tableName, setTableName] = useState(DEFAULT_TABLE);

  const [result, setResult] = useState<GenerateResult | null>(null);
  const [generating, setGenerating] = useState(false);

  const screenViews = (events ?? []).filter((e) => String(e.name ?? "") === "screen_view");
  const eventTypeCounts = (events ?? []).reduce<Record<string, number>>((acc, e) => {
    const n = String(e.name ?? "");
    acc[n] = (acc[n] ?? 0) + 1;
    return acc;
  }, {});

  async function handleFileChange(selected: File | null) {
    setFromHandoff(false);
    setFile(selected);
    setEvents(null);
    setParseError(null);
    setResult(null);
    setScreenOrder([]);
    setCustomOptions({ selectedOrders: [], filterFields: {}, outputColumns: [...DEFAULT_OUTPUT_COLUMNS] });
    if (!selected) return;
    setParsing(true);
    const formData = new FormData();
    formData.append("file", selected);
    formData.append("mode", "parse");
    try {
      const res = await fetch("/api/build-query", { method: "POST", body: formData });
      const data = await res.json();
      if (data.ok) {
        setEvents(data.events);
        setScreenOrder(
          data.events
            .filter((e: SpecEvent) => String(e.name ?? "") === "screen_view")
            .map((e: SpecEvent) => String(e.sn ?? ""))
            .filter(Boolean)
        );
      } else {
        setParseError(data.error);
      }
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Request failed. Please try again.");
    } finally {
      setParsing(false);
    }
  }

  useEffect(() => {
    const rows = takeSpecHandoff();
    if (rows && rows.length > 0) {
      handleFileChange(rowsToSpecFile(rows)).then(() => setFromHandoff(true));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function moveScreen(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= screenOrder.length) return;
    const next = screenOrder.slice();
    [next[index], next[target]] = [next[target], next[index]];
    setScreenOrder(next);
  }

  async function handleGenerate() {
    if (!file) return;
    setGenerating(true);
    setResult(null);
    const options: Record<string, unknown> = {
      start_date: startDate,
      end_date: endDate,
      count_mode: countMode,
    };
    if (tableName && tableName !== DEFAULT_TABLE) options.table_name = tableName;
    if (queryType === "validation") options.sample_per_event = samplePerEvent;
    if (queryType === "volumetry") {
      options.group_by = groupBy;
      options.include_event_count = includeEventCount;
    }
    if (queryType === "funnel") options.screen_order = screenOrder;
    if (queryType === "custom") {
      options.selected_event_orders = customOptions.selectedOrders;
      options.filter_fields_per_event = customOptions.filterFields;
      options.output_columns = customOptions.outputColumns;
    }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", "generate");
    formData.append("query_type", queryType);
    formData.append("options", JSON.stringify(options));
    try {
      const res = await fetch("/api/build-query", { method: "POST", body: formData });
      const data: GenerateResult = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ ok: false, error: err instanceof Error ? err.message : "Request failed. Please try again." });
    } finally {
      setGenerating(false);
    }
  }

  function copyQuery() {
    if (result && result.ok) navigator.clipboard.writeText(result.query);
  }

  function downloadQuery() {
    if (!result || !result.ok) return;
    const blob = new Blob([result.query], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `query_${startDate}.sql`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const funnelDisabled = screenViews.length === 0;
  const generateDisabled =
    !events ||
    generating ||
    (queryType === "funnel" && funnelDisabled) ||
    (queryType === "custom" && customOptions.selectedOrders.length === 0);

  return (
    <main className="shell">
      <Link href="/" className="back-link">
        ← All tools
      </Link>
      <div className="eyebrow">tagmatch / tools / build-query</div>
      <h1>Query Builder</h1>
      <p className="lede">
        Upload a spec from Map Extraction and generate Databricks SQL —
        validation, volumetry, funnel, or custom queries.
      </p>

      <div className="panel control-panel">
        <label className="file-input-label">
          <input
            type="file"
            accept=".json,.csv"
            onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
          />
          Choose spec file
        </label>
        <span className="file-name">{file ? file.name : "No file chosen"}</span>
        {parsing && <span className="qb-parsing">Parsing…</span>}
      </div>

      {fromHandoff && events && (
        <p className="handoff-banner">Spec carregado da Extração de Mapa · {events.length} eventos.</p>
      )}

      {parseError && <p className="alert-error">Couldn&apos;t read the spec: {parseError}</p>}

      {events && (
        <>
          <div className="stats">
            <div className="stat">
              <div className="stat-label">events</div>
              <div className="stat-value">{events.length}</div>
            </div>
            {Object.entries(eventTypeCounts).map(([name, count]) => (
              <div className="stat" key={name}>
                <div className="stat-label">
                  <span className={`badge ${badgeClass(name)}`}>
                    <span className="dot" />
                    {badgeLabel(name)}
                  </span>
                </div>
                <div className="stat-value">{count}</div>
              </div>
            ))}
          </div>

          <div className="panel qb-options">
            <div className="qb-row">
              <label className="review-field-label">
                Query type
                <select value={queryType} onChange={(e) => setQueryType(e.target.value)}>
                  {QUERY_TYPES.map((t) => (
                    <option key={t.value} value={t.value} disabled={t.value === "funnel" && funnelDisabled}>
                      {t.label}
                      {t.value === "funnel" && funnelDisabled ? " — no screen_view events in this spec" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="review-field-label">
                Start date
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="review-field-input" />
              </label>
              <label className="review-field-label">
                End date
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="review-field-input" />
              </label>
              <label className="review-field-label">
                Count mode
                <select value={countMode} onChange={(e) => setCountMode(e.target.value)}>
                  <option value="session">session</option>
                  <option value="event">event</option>
                </select>
              </label>
            </div>

            {queryType === "validation" && (
              <div className="qb-row">
                <label className="review-field-label">
                  Samples per event (1–100)
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={samplePerEvent}
                    onChange={(e) => setSamplePerEvent(Math.max(1, Math.min(100, Number(e.target.value) || 5)))}
                    className="review-field-input"
                  />
                </label>
              </div>
            )}

            {queryType === "volumetry" && (
              <div className="qb-row">
                <label className="review-field-label">
                  Group by
                  <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
                    <option value="event">event</option>
                    <option value="day">day</option>
                    <option value="both">both</option>
                  </select>
                </label>
                <label className="qb-check">
                  <input
                    type="checkbox"
                    checked={includeEventCount}
                    onChange={(e) => setIncludeEventCount(e.target.checked)}
                  />
                  Include event count
                </label>
              </div>
            )}

            {queryType === "funnel" && (
              <div className="qb-funnel">
                <div className="qb-section-label">Screen order</div>
                {screenOrder.map((sn, i) => (
                  <div key={`${sn}-${i}`} className="qb-funnel-step">
                    <span className="mono qb-funnel-num">{i + 1}.</span>
                    <span className="mono qb-funnel-sn">{sn}</span>
                    <button className="btn btn-ghost qb-move" onClick={() => moveScreen(i, -1)} disabled={i === 0}>
                      ↑
                    </button>
                    <button
                      className="btn btn-ghost qb-move"
                      onClick={() => moveScreen(i, 1)}
                      disabled={i === screenOrder.length - 1}
                    >
                      ↓
                    </button>
                  </div>
                ))}
              </div>
            )}

            {queryType === "custom" && events && (
              <CustomOptions events={events} value={customOptions} onChange={setCustomOptions} />
            )}

            <details className="report-details">
              <summary>Advanced — target table</summary>
              <label className="review-field-label qb-table-field">
                Databricks table
                <input
                  value={tableName}
                  onChange={(e) => setTableName(e.target.value)}
                  className="review-field-input qb-table-input"
                />
              </label>
            </details>

            <div className="qb-generate-row">
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generateDisabled}>
                {generating ? "Generating…" : "Generate SQL →"}
              </button>
            </div>
          </div>
        </>
      )}

      {result && !result.ok && <p className="alert-error">Couldn&apos;t generate the query: {result.error}</p>}

      {result && result.ok && (
        <div className="qb-result">
          <div className="results-header">
            <h2>Generated SQL</h2>
            <div className="results-actions">
              <button className="btn btn-ghost" onClick={copyQuery}>
                Copy
              </button>
              <button className="btn btn-ghost" onClick={downloadQuery}>
                Download .sql
              </button>
            </div>
          </div>
          {Object.keys(result.event_mapping).length > 0 && (
            <div className="qb-mapping">
              {Object.entries(result.event_mapping).map(([order, name]) => (
                <span key={order} className="qb-mapping-item mono">
                  {order} → {name}
                </span>
              ))}
            </div>
          )}
          <pre className="qb-sql">{result.query}</pre>
        </div>
      )}
    </main>
  );
}
