"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { badgeClass, badgeLabel } from "../_lib/ResultsPanel";
import { loadSession } from "../_lib/sessionStore";
import { ConvertCard } from "./ConvertCard";
import { CONTEXT_FIELDS, ENUMS, validate, toBlock, withProductDisambiguation, type ConvEvent } from "./taxonomy5";

async function convert(rows: unknown[]): Promise<ConvEvent[]> {
  const res = await fetch("/api/convert-taxonomy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ events: rows }),
  });
  const data = await res.json();
  if (data.ok) return data.events as ConvEvent[];
  throw new Error(data.error || "Falha na conversão");
}

function applyContext(events: ConvEvent[], ctx: Record<string, string>): ConvEvent[] {
  return events.map((ev) => {
    const fields = { ...ev.fields };
    for (const key of CONTEXT_FIELDS) {
      const v = (ctx[key] ?? "").trim();
      if (v !== "" && fields[key]) fields[key] = { value: v, confidence: fields[key].confidence === "auto" ? "auto" : "review" };
    }
    return { ...ev, fields };
  });
}

type ContextField = (typeof CONTEXT_FIELDS)[number];
type ContextState = Record<ContextField, string>;

const EMPTY_CONTEXT: ContextState = Object.fromEntries(
  CONTEXT_FIELDS.map((k) => [k, ""])
) as ContextState;

const CONTEXT_LABELS: Record<ContextField, string> = {
  department: "Department",
  macro_journey: "Macro journey",
  micro_journey: "Micro journey",
  event_access_type: "Event access type",
  client_category: "Client category",
  origin_nv: "Origin",
};

export default function ConvertTaxonomyPage() {
  const [file, setFile] = useState<File | null>(null);
  const [events, setEvents] = useState<ConvEvent[] | null>(null);
  const [journeyContext, setJourneyContext] = useState<ContextState>({ ...EMPTY_CONTEXT });
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState<string | null>(null);
  const [productJourney, setProductJourney] = useState(false);
  const [fromHandoff, setFromHandoff] = useState(false);
  const [sessionFileName, setSessionFileName] = useState<string | null>(null);

  async function runConvert(rows: unknown[], viaHandoff = false) {
    setConverting(true);
    setConvertError(null);
    setFromHandoff(viaHandoff);
    try {
      const converted = await convert(rows);
      setEvents(converted);
    } catch (err) {
      setEvents(null);
      setConvertError(err instanceof Error ? err.message : "Request failed. Please try again.");
    } finally {
      setConverting(false);
    }
  }

  // Convert the session spec once on mount. Setting the loading state on
  // mount is intentional here (a fetch-on-mount), so the cascading-render
  // warning is explicitly accepted rather than worked around.
  useEffect(() => {
    let cancelled = false;
    void loadSession().then(({ map }) => {
      if (cancelled || !map || map.spec.length === 0) return;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSessionFileName(map.fileName);
      void runConvert(map.spec, true);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFileChange(selected: File | null) {
    setFromHandoff(false);
    setFile(selected);
    setEvents(null);
    setConvertError(null);
    setJourneyContext({ ...EMPTY_CONTEXT });
    if (!selected) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(await selected.text());
    } catch {
      setConvertError("O arquivo não é um JSON válido.");
      return;
    }
    if (!Array.isArray(parsed)) {
      setConvertError("O arquivo deve conter uma lista de eventos.");
      return;
    }
    await runConvert(parsed);
  }

  function updateContext(key: ContextField, value: string) {
    setJourneyContext((prev) => ({ ...prev, [key]: value }));
  }

  function applyContextToAll() {
    if (!events) return;
    let next = applyContext(events, journeyContext);
    if (productJourney) next = next.map(withProductDisambiguation);
    setEvents(next);
  }

  function updateEvent(index: number, updated: ConvEvent) {
    if (!events) return;
    setEvents(events.map((ev, i) => (i === index ? updated : ev)));
  }

  function copyAll() {
    if (!events) return;
    navigator.clipboard.writeText(events.map((ev) => toBlock(ev)).join("\n\n"));
  }

  const eventTypeCounts = (events ?? []).reduce<Record<string, number>>((acc, e) => {
    acc[e.event_kind] = (acc[e.event_kind] ?? 0) + 1;
    return acc;
  }, {});

  const pendingCount = (events ?? []).reduce(
    (acc, e) => acc + (Object.keys(validate(e)).length > 0 ? 1 : 0),
    0
  );

  return (
    <main className="shell">
      <Link href="/" className="back-link">
        ← All tools
      </Link>
      <div className="eyebrow">tagmatch / tools / convert-5.0</div>
      <h1>Converter para 5.0</h1>
      <p className="lede">
        Converte um mapa extraído (App 4) para a taxonomia App 5.0 — sugestões
        assistidas por evento, revisão sempre manual, nenhuma execução automática.
      </p>

      <div className="panel control-panel">
        <label className="file-input-label">
          <input
            type="file"
            accept=".json"
            onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
          />
          Choose events file
        </label>
        <span className="file-name">{file ? file.name : "No file chosen"}</span>
        {converting && !fromHandoff && <span className="qb-parsing">Convertendo…</span>}
      </div>

      {fromHandoff && converting && (
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

      {convertError && <p className="alert-error">Couldn&apos;t convert: {convertError}</p>}

      {events && events.length > 0 && (
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
            <div className="qb-section-label">Contexto da jornada</div>
            <div className="qb-row">
              {CONTEXT_FIELDS.map((key) => (
                <label className="review-field-label" key={key}>
                  {CONTEXT_LABELS[key]}
                  {ENUMS[key] ? (
                    <select value={journeyContext[key]} onChange={(e) => updateContext(key, e.target.value)}>
                      <option value="">—</option>
                      {ENUMS[key].map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={journeyContext[key]}
                      onChange={(e) => updateContext(key, e.target.value)}
                      className="review-field-input"
                    />
                  )}
                </label>
              ))}
            </div>
            <label className="convert5-check">
              <input
                type="checkbox"
                checked={productJourney}
                onChange={(e) => setProductJourney(e.target.checked)}
              />
              Jornada de desambiguação de produto (adiciona plan_name / event_plan_type em todos os eventos)
            </label>
            <div className="qb-generate-row">
              <button className="btn btn-primary" onClick={applyContextToAll}>
                Aplicar a todos
              </button>
            </div>
          </div>

          <div className="convert5-copy-all">
            <span className="convert5-summary">
              {events.length} eventos · {pendingCount} com pendências
            </span>
            <button className="btn btn-primary" onClick={copyAll}>
              Copiar tudo
            </button>
          </div>

          <div className="convert5-cards">
            {events.map((ev, i) => (
              <ConvertCard
                key={`${String(ev.event_order ?? "?")}-${i}`}
                event={ev}
                onChange={(updated) => updateEvent(i, updated)}
              />
            ))}
          </div>
        </>
      )}

      {events && events.length === 0 && <p className="mv-empty">No events to display.</p>}
    </main>
  );
}
