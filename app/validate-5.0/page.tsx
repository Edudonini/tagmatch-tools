"use client";

import { useState } from "react";
import { badgeLabel } from "../_lib/ResultsPanel";
import { Dropzone } from "../_lib/Dropzone";
import { StatRail } from "../_lib/StatRail";
import { EventParamsCard, type Extracted5Event } from "./EventParamsCard";

async function extract5(file: File): Promise<Extracted5Event[]> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/extract-5.0", { method: "POST", body: form });
  const data = await res.json();
  if (data.ok) return data.events as Extracted5Event[];
  throw new Error(data.error || "Falha na extração");
}

export default function Validate5Page() {
  const [fileName, setFileName] = useState<string | null>(null);
  const [events, setEvents] = useState<Extracted5Event[] | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  async function handleFile(file: File | null) {
    setFileName(file ? file.name : null);
    setEvents(null);
    setExtractError(null);
    if (!file) return;
    setExtracting(true);
    try {
      const extracted = await extract5(file);
      setEvents(extracted);
    } catch (err) {
      setEvents(null);
      setExtractError(err instanceof Error ? err.message : "Request failed. Please try again.");
    } finally {
      setExtracting(false);
    }
  }

  const eventTypeCounts = (events ?? []).reduce<Record<string, number>>((acc, e) => {
    acc[e.event_type] = (acc[e.event_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <main className="shell">
      <div className="narrow">
        <div className="eyebrow">tagmatch / tools / validate-5.0</div>
        <h1>Validar mapa 5.0</h1>
        <p className="lede">
          Extrai um mapa Whimsical no padrão App 5.0 e mostra os parâmetros
          limpos por evento, para conferir a qualidade da extração.
        </p>

        <div className="panel control-panel">
          <Dropzone
            accept=".svg"
            onFiles={(f) => handleFile(f[0] ?? null)}
            selectedLabel={fileName}
            idle="Arraste um SVG do mapa 5.0"
            hint="ou clique para escolher"
          />
          {extracting && <span className="qb-parsing">Extraindo…</span>}
        </div>

        {extractError && <p className="alert-error">Não consegui extrair: {extractError}</p>}
      </div>

      {events && events.length > 0 && (
        <>
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
          </div>

          <div className="c5-events-col">
            {events.map((ev, index) => (
              <EventParamsCard key={`${String(ev.event_order ?? "?")}-${index}`} event={ev} />
            ))}
          </div>
        </>
      )}

      {events && events.length === 0 && <p className="mv-empty">Nenhum evento para exibir.</p>}
    </main>
  );
}
