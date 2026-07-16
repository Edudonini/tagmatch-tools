"use client";

import { useState } from "react";

export type Finding = {
  screen: string;
  event_type: string;
  event_order: number | string | null;
  field: string;
  problem: string;
  severity: "red" | "amber";
  category: string;
  suggestion: string;
};

const SEV_LABEL: Record<string, string> = { red: "Crítico", amber: "Atenção" };

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [filter, setFilter] = useState<"all" | "red" | "amber">("all");
  const rows = findings.filter((f) => filter === "all" || f.severity === filter);

  if (findings.length === 0) {
    return <p className="mv-empty">Nenhum problema encontrado 🎉</p>;
  }

  return (
    <div className="findings">
      <div className="findings-filter">
        <button className={`chip${filter === "all" ? " on" : ""}`} onClick={() => setFilter("all")}>
          todos ({findings.length})
        </button>
        <button className={`chip${filter === "red" ? " on" : ""}`} onClick={() => setFilter("red")}>
          🔴 críticos ({findings.filter((f) => f.severity === "red").length})
        </button>
        <button className={`chip${filter === "amber" ? " on" : ""}`} onClick={() => setFilter("amber")}>
          🟡 atenção ({findings.filter((f) => f.severity === "amber").length})
        </button>
      </div>
      <div className="findings-scroll">
        <table className="findings-table">
          <thead>
            <tr>
              <th>Tela</th>
              <th>Evento</th>
              <th>Campo</th>
              <th>Problema</th>
              <th>Sev.</th>
              <th>Correção sugerida</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f, i) => (
              <tr key={i}>
                <td className="mono">{f.screen || "—"}</td>
                <td>{f.event_type}{f.event_order != null ? ` #${f.event_order}` : ""}</td>
                <td className="mono">{f.field}</td>
                <td>{f.problem}</td>
                <td>
                  <span className={`sev-dot sev-${f.severity}`} />
                  {SEV_LABEL[f.severity]}
                </td>
                <td>{f.suggestion || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
