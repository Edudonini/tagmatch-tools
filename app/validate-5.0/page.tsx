"use client";

import { useState } from "react";
import { Dropzone } from "../_lib/Dropzone";
import { StatRail } from "../_lib/StatRail";
import { FindingsTable, type Finding } from "./FindingsTable";

type Approved = { screen: string; event_type: string; event_order: number | string | null };
type OpenQuestion = { screen: string; field: string; note: string };
type Validation = {
  summary: { total: number; red: number; amber: number; green: number; adherence_pct: number };
  findings: Finding[];
  approved: Approved[];
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

  async function handleFile(file: File | null) {
    setFileName(file ? file.name : null);
    setResult(null);
    setError(null);
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

  return (
    <main className="shell">
      <div className="narrow">
        <div className="eyebrow">tagmatch / tools / validate-5.0</div>
        <h1>Validar mapa 5.0</h1>
        <p className="lede">
          Audita um mapa Whimsical no padrão App 5.0 contra o padrão de taxonomia:
          completude, campos legados, enums, nomenclatura e coerência.
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
            <FindingsTable findings={result!.findings} />

            <details className="report-section">
              <summary>Aprovados ({result!.approved.length})</summary>
              <ul className="report-list">
                {result!.approved.map((a, i) => (
                  <li key={i}>
                    <span className="mono">{a.screen || "—"}</span> · {a.event_type}
                    {a.event_order != null ? ` #${a.event_order}` : ""}
                  </li>
                ))}
              </ul>
            </details>

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
