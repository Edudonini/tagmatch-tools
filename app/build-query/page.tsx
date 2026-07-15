"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { badgeLabel } from "../_lib/ResultsPanel";
import { Dropzone } from "../_lib/Dropzone";
import { StatRail } from "../_lib/StatRail";
import {
  getServerSnapshot,
  getSnapshot,
  loadSession,
  rowsToSpecFile,
  subscribe,
} from "../_lib/sessionStore";
import {
  CustomOptions,
  INITIAL_CUSTOM_STATE,
  buildCustomPayload,
  hasInvalidNumeric,
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
  const [handoffLoading, setHandoffLoading] = useState(false);
  const [sessionFileName, setSessionFileName] = useState<string | null>(null);
  const skipHydration = useRef(false);
  const meta = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const [queryType, setQueryType] = useState<string>("validation");
  const [startDate, setStartDate] = useState(() => isoDaysAgo(7));
  const [endDate, setEndDate] = useState(() => isoDaysAgo(0));
  const [countMode, setCountMode] = useState("session");
  const [samplePerEvent, setSamplePerEvent] = useState(5);
  const [groupBy, setGroupBy] = useState("event");
  const [includeEventCount, setIncludeEventCount] = useState(true);
  const [screenOrder, setScreenOrder] = useState<string[]>([]);
  const [customOptions, setCustomOptions] = useState<CustomOptionsState>({ ...INITIAL_CUSTOM_STATE });
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
    skipHydration.current = true;
    setFromHandoff(false);
    setFile(selected);
    setEvents(null);
    setParseError(null);
    setResult(null);
    setScreenOrder([]);
    setCustomOptions({ ...INITIAL_CUSTOM_STATE });
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
    let cancelled = false;
    // Intentional fetch-on-mount loading state; cascading-render warning accepted.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHandoffLoading(true);
    loadSession()
      .then(({ map }) => {
        if (cancelled || skipHydration.current || !map || map.spec.length === 0) return;
        setSessionFileName(map.fileName);
        return handleFileChange(rowsToSpecFile(map.spec)).then(() => {
          if (!cancelled) setFromHandoff(true);
        });
      })
      .finally(() => {
        if (!cancelled) setHandoffLoading(false);
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
      setFromHandoff(false);
      setSessionFileName(null);
      setFile(null);
      setEvents(null);
      setResult(null);
      setScreenOrder([]);
    }
  }, [meta.map, fromHandoff]);

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
      options.custom = buildCustomPayload(customOptions);
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
    (queryType === "custom" && hasInvalidNumeric(customOptions));

  return (
    <main className="shell">
      <div className="narrow">
        <div className="eyebrow">tagmatch / tools / build-query</div>
        <h1>Query Builder</h1>
        <p className="lede">
          Use um spec da Extração de Mapa e gere SQL do Databricks — validation,
          volumetry, funnel ou custom.
        </p>

        <div className="panel control-panel">
          <Dropzone
            accept=".json,.csv"
            onFiles={(files) => handleFileChange(files[0] ?? null)}
            selectedLabel={file ? file.name : null}
            idle="Arraste o spec (.json/.csv), ou clique para escolher"
            hint=".json · .csv · da Extração de Mapa"
          />
          {parsing && <span className="qb-parsing">Interpretando…</span>}
        </div>

        {handoffLoading && (
          <p className="handoff-loading">
            <span className="handoff-spinner" aria-hidden="true" />
            Carregando o mapa extraído…
          </p>
        )}

        {fromHandoff && events && (
          <p className="handoff-banner">
            Spec do mapa da sessão{sessionFileName ? ` · ${sessionFileName}` : ""} · {events.length} eventos.
          </p>
        )}

        {parseError && <p className="alert-error">Não consegui ler o spec: {parseError}</p>}
      </div>

      {events && (
        <div className="narrow">
          <StatRail
            stats={[
              { label: "eventos", value: String(events.length) },
              ...Object.entries(eventTypeCounts).map(([name, count]) => ({
                label: badgeLabel(name),
                value: String(count),
              })),
            ]}
          />

          <div className="panel qb-options">
            <div className="qb-row">
              <label className="review-field-label">
                Tipo de query
                <select value={queryType} onChange={(e) => setQueryType(e.target.value)}>
                  {QUERY_TYPES.map((t) => (
                    <option key={t.value} value={t.value} disabled={t.value === "funnel" && funnelDisabled}>
                      {t.label}
                      {t.value === "funnel" && funnelDisabled ? " — sem eventos screen_view neste spec" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="review-field-label">
                Data inicial
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="review-field-input" />
              </label>
              <label className="review-field-label">
                Data final
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="review-field-input" />
              </label>
              <label className="review-field-label">
                Modo de contagem
                <select value={countMode} onChange={(e) => setCountMode(e.target.value)}>
                  <option value="session">session</option>
                  <option value="event">event</option>
                </select>
              </label>
            </div>

            {queryType === "validation" && (
              <div className="qb-row">
                <label className="review-field-label">
                  Amostras por evento (1–100)
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
                  Agrupar por
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
                  Incluir contagem de eventos
                </label>
              </div>
            )}

            {queryType === "funnel" && (
              <div className="qb-funnel">
                <div className="qb-section-label">Ordem das telas</div>
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
              <summary>Avançado — tabela de destino</summary>
              <label className="review-field-label qb-table-field">
                Tabela do Databricks
                <input
                  value={tableName}
                  onChange={(e) => setTableName(e.target.value)}
                  className="review-field-input qb-table-input"
                />
              </label>
            </details>

            <div className="qb-generate-row">
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generateDisabled}>
                {generating ? "Gerando…" : "Gerar SQL →"}
              </button>
            </div>
          </div>
        </div>
      )}

      {result && !result.ok && (
        <div className="narrow">
          <p className="alert-error">Não consegui gerar a query: {result.error}</p>
        </div>
      )}

      {result && result.ok && (
        <div className="narrow qb-result">
          <div className="results-header">
            <h2>SQL gerado</h2>
            <div className="results-actions">
              <button className="btn btn-ghost" onClick={copyQuery}>
                Copiar
              </button>
              <button className="btn btn-ghost" onClick={downloadQuery}>
                Baixar .sql
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
