"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { badgeClass, badgeLabel } from "../../_lib/ResultsPanel";

export type MapRow = Record<string, unknown>;

type MapViewProps = {
  rows: MapRow[];
  report: Record<string, unknown>;
  onReview: () => void;
};

// Shown as row identity (badge + ordinal + group header), never as params.
const IDENTITY_FIELDS = ["name", "event_order", "sn"];
// GA fields lead the param list; sn is omitted (it is the group header).
const GA_FIELDS_FIRST = ["ct", "ac", "lb"];
// Derived/metadata fields, hidden from the reader (same set as EventReviewCard).
const HIDDEN_FIELDS = ["spec_id", "raw_lines", "confidence_score"];
const CHIP_LIMIT = 3;

function isHiddenField(key: string): boolean {
  return (
    key.startsWith("_") ||
    key.endsWith("_regex") ||
    HIDDEN_FIELDS.includes(key) ||
    IDENTITY_FIELDS.includes(key)
  );
}

function isPopulated(v: unknown): boolean {
  return v !== null && v !== undefined && String(v) !== "";
}

function paramEntries(row: MapRow): [string, unknown][] {
  return Object.entries(row)
    .filter(([k, v]) => !isHiddenField(k) && isPopulated(v))
    .sort(([a], [b]) => {
      const ia = GA_FIELDS_FIRST.indexOf(a);
      const ib = GA_FIELDS_FIRST.indexOf(b);
      if (ia !== -1 && ib !== -1) return ia - ib;
      if (ia !== -1) return -1;
      if (ib !== -1) return 1;
      return 0;
    });
}

type Group = { sn: string; rows: MapRow[]; minOrder: number };

function buildGroups(rows: MapRow[]): Group[] {
  const map = new Map<string, MapRow[]>();
  rows.forEach((r) => {
    const sn = String(r.sn ?? "").trim();
    if (!map.has(sn)) map.set(sn, []);
    map.get(sn)!.push(r);
  });
  const groups: Group[] = Array.from(map.entries()).map(([sn, rs]) => {
    const sorted = rs.slice().sort((a, b) => Number(a.event_order ?? 0) - Number(b.event_order ?? 0));
    const minOrder = sorted.reduce((m, r) => {
      const n = Number(r.event_order);
      return Number.isFinite(n) && n < m ? n : m;
    }, Infinity);
    return { sn, rows: sorted, minOrder };
  });
  groups.sort((a, b) => {
    if (a.sn === "" && b.sn !== "") return 1;
    if (b.sn === "" && a.sn !== "") return -1;
    return a.minOrder - b.minOrder;
  });
  return groups;
}

function copyEvent(row: MapRow) {
  const lines: string[] = [];
  ["event_order", "name", "sn"].forEach((k) => {
    if (isPopulated(row[k])) lines.push(`${k}: ${String(row[k])}`);
  });
  paramEntries(row).forEach(([k, v]) => lines.push(`${k}: ${String(v)}`));
  navigator.clipboard.writeText(lines.join("\n"));
}

function allColumnKeys(rows: MapRow[]): string[] {
  const set = new Set<string>();
  rows.forEach((r) => Object.keys(r).forEach((k) => set.add(k)));
  return Array.from(set);
}

function downloadRows(rows: MapRow[], format: "json" | "csv", baseName: string) {
  let blob: Blob;
  let filename: string;
  if (format === "json") {
    blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    filename = `${baseName}.json`;
  } else {
    const columns = allColumnKeys(rows);
    const lines = [
      columns.join(","),
      ...rows.map((row) =>
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
    filename = `${baseName}.csv`;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function MapView({ rows, report, onReview }: MapViewProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const groups = buildGroups(rows);
  const typeCounts = rows.reduce<Record<string, number>>((acc, r) => {
    const n = String(r.name ?? "") || "—";
    acc[n] = (acc[n] ?? 0) + 1;
    return acc;
  }, {});
  const hasRows = rows.length > 0;

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handoff(dest: "/build-query" | "/match" | "/convert-5.0") {
    // The session store already holds the spec; the destination page reads it on mount.
    router.push(dest);
  }

  return (
    <div className="mapview">
      <div className="mv-toolbar">
        {hasRows && (
          <>
            <button className="btn btn-ghost" onClick={() => downloadRows(rows, "json", "spec")}>
              Download JSON
            </button>
            <button className="btn btn-ghost" onClick={() => downloadRows(rows, "csv", "spec")}>
              Download CSV
            </button>
          </>
        )}
        <button className="btn btn-ghost" onClick={onReview}>
          Review events →
        </button>
        <button className="btn btn-primary" onClick={() => handoff("/build-query")}>
          Seguir para Query Builder →
        </button>
        <button className="btn btn-primary" onClick={() => handoff("/match")}>
          Seguir para Matching →
        </button>
        <button className="btn btn-primary" onClick={() => handoff("/convert-5.0")}>
          Converter para 5.0 →
        </button>
      </div>

      <div className="mv-summary">
        <span className="mv-summary-count">{groups.length}</span> telas
        <span className="mv-dot">·</span>
        <span className="mv-summary-count">{rows.length}</span> eventos
        <span className="mv-counts">
          {Object.entries(typeCounts).map(([name, count]) => (
            <span className={`badge ${badgeClass(name)}`} key={name}>
              <span className="dot" />
              {badgeLabel(name)} {count}
            </span>
          ))}
        </span>
      </div>

      {report && Object.keys(report).length > 0 && (
        <details className="mv-report">
          <summary>Relatório da extração</summary>
          <pre>{JSON.stringify(report, null, 2)}</pre>
        </details>
      )}

      {!hasRows && <p className="mv-empty">No events to display.</p>}

      {groups.map((g) => (
        <section className="mv-group" key={g.sn || "__none__"}>
          <div className="mv-group-head">
            <span className="mv-screen">{g.sn || "(sem screenName)"}</span>
            <span className="mv-count">{g.rows.length} evento{g.rows.length === 1 ? "" : "s"}</span>
          </div>
          <div className="mv-rows">
            {g.rows.map((row, i) => {
              const params = paramEntries(row);
              const id = `${g.sn}#${String(row.event_order ?? "")}#${i}`;
              const isOpen = expanded.has(id);
              const chips = params.slice(0, CHIP_LIMIT);
              const moreCount = params.length - chips.length;
              return (
                <div className="mv-row" key={id}>
                  <div className="mv-row-line">
                    <button className="mv-row-toggle" onClick={() => toggle(id)} aria-expanded={isOpen}>
                      <span className="mv-order">#{String(row.event_order ?? "?")}</span>
                      <span className={`badge ${badgeClass(row.name)}`}>
                        <span className="dot" />
                        {badgeLabel(row.name)} {String(row.name ?? "")}
                      </span>
                      {!isOpen &&
                        chips.map(([k, v]) => (
                          <span className="mv-chip" key={k}>
                            <span className="mv-chip-k">{k}</span> {String(v)}
                          </span>
                        ))}
                      {!isOpen && moreCount > 0 && <span className="mv-more">+{moreCount}</span>}
                      <span className="mv-caret">{isOpen ? "▾" : "▸"}</span>
                    </button>
                    {isOpen && (
                      <button className="mv-copy" onClick={() => copyEvent(row)} aria-label="Copiar parâmetros do evento">
                        Copy
                      </button>
                    )}
                  </div>
                  {isOpen &&
                    (params.length > 0 ? (
                      <div className="mv-params">
                        {params.map(([k, v]) => (
                          <div className="mv-p" key={k}>
                            <span className="mv-k">{k}</span>
                            <span className="mv-v">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="mv-noparams">Sem parâmetros adicionais.</div>
                    ))}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
