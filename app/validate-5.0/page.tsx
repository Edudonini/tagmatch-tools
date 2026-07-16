"use client";

import { useMemo, useState } from "react";
import { Dropzone } from "../_lib/Dropzone";
import { StatRail } from "../_lib/StatRail";
import { EventReportCard, type EventReport } from "./EventReportCard";

type OpenQuestion = { screen: string; field: string; note: string };
type Validation = {
  summary: { total: number; red: number; amber: number; green: number; adherence_pct: number };
  events: EventReport[];
  open_questions: OpenQuestion[];
};

async function validate5(file: File): Promise<Validation> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/validate-5.0", { method: "POST", body: form });
  const data = await res.json();
  if (data.ok) return data.validation as Validation;
  throw new Error(data.error || "Falha na validação");
}

export default function Validate5Page() {
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<Validation | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onlyProblems, setOnlyProblems] = useState(false);

  async function handleFile(file: File | null) {
    setFileName(file ? file.name : null);
    setResult(null);
    setError(null);
    setOnlyProblems(false);
    if (!file) return;
    setRunning(true);
    try {
      setResult(await validate5(file));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Request failed. Please try again.");
    } finally {
      setRunning(false);
    }
  }

  const s = result?.summary;
  const events = useMemo(() => result?.events ?? [], [result]);
  const problemCount = useMemo(() => events.filter((e) => e.verdict !== "green").length, [events]);
  const shown = useMemo(
    () => events.filter((e) => !onlyProblems || e.verdict !== "green"),
    [events, onlyProblems],
  );

  return (
    <main className="shell">
      <div className="narrow">
        <div className="eyebrow">tagmatch / tools / validate-5.0</div>
        <h1>Validar mapa 5.0</h1>
        <p className="lede">
          Audita um mapa Whimsical no padrão App 5.0: cada evento com todos os campos,
          status, valor e o motivo vindo do padrão de taxonomia.
        </p>

        <div className="panel control-panel">
          <Dropzone
            accept=".svg"
            onFiles={(f) => handleFile(f[0] ?? null)}
            selectedLabel={fileName}
            idle="Arraste um SVG do mapa 5.0"
            hint="ou clique para escolher"
          />
          {running && <span className="qb-parsing">Validando…</span>}
        </div>

        {error && <p className="alert-error">Não consegui validar: {error}</p>}
      </div>

      {s && (
        <>
          <div className="narrow">
            <StatRail
              stats={[
                { label: "aderência", value: `${s.adherence_pct}%`, tone: "accent" },
                { label: "🔴 críticos", value: String(s.red) },
                { label: "🟡 atenção", value: String(s.amber) },
                { label: "🟢 ok", value: String(s.green) },
                { label: "eventos", value: String(s.total) },
              ]}
            />
          </div>

          <div className="narrow">
            <div className="report-toolbar">
              <button className={`chip${!onlyProblems ? " on" : ""}`} onClick={() => setOnlyProblems(false)}>
                todos ({events.length})
              </button>
              <button className={`chip${onlyProblems ? " on" : ""}`} onClick={() => setOnlyProblems(true)}>
                só com problemas ({problemCount})
              </button>
            </div>

            <div className="report-cards">
              {shown.map((e, i) => (
                <EventReportCard key={`${String(e.event_order ?? "?")}-${i}`} event={e} />
              ))}
            </div>

            <details className="report-section">
              <summary>Perguntas em aberto ({result!.open_questions.length})</summary>
              <ul className="report-list">
                {result!.open_questions.map((q, i) => (
                  <li key={i}>
                    {q.field ? <span className="mono">{q.field}</span> : null}
                    {q.field ? " · " : ""}
                    {q.note}
                    {q.screen ? <span className="mono"> ({q.screen})</span> : null}
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </>
      )}
    </main>
  );
}
