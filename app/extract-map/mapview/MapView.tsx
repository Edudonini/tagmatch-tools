"use client";

import { badgeClass, badgeLabel } from "../../_lib/ResultsPanel";

export type MapRow = Record<string, unknown>;

type MapViewProps = {
  rows: MapRow[];
  onExit: () => void;
};

// Shown as the card's identity (badge + ordinal + group header), never as params.
const IDENTITY_FIELDS = ["name", "event_order", "sn"];
// GA fields lead the card body; sn is omitted (it is the group header).
const GA_FIELDS_FIRST = ["ct", "ac", "lb"];
// Derived/metadata fields, hidden from the reader (same set as EventReviewCard).
const HIDDEN_FIELDS = ["spec_id", "raw_lines", "confidence_score"];

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

export function MapView({ rows, onExit }: MapViewProps) {
  const groups = buildGroups(rows);
  const typeCounts = rows.reduce<Record<string, number>>((acc, r) => {
    const n = String(r.name ?? "") || "—";
    acc[n] = (acc[n] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mapview">
      <div className="mv-bar">
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
        <button className="btn btn-ghost" onClick={onExit}>
          ← Back to table
        </button>
      </div>

      {rows.length === 0 && <p className="mv-empty">No events to display.</p>}

      {groups.map((g) => (
        <section className="mv-group" key={g.sn || "__none__"}>
          <div className="mv-group-head">
            <span className="mv-screen">{g.sn || "(sem screenName)"}</span>
            <span className="mv-count">{g.rows.length} evento{g.rows.length === 1 ? "" : "s"}</span>
          </div>
          <div className="mv-cards">
            {g.rows.map((row, i) => {
              const params = paramEntries(row);
              return (
                <div className="mv-card" key={i}>
                  <div className="mv-card-head">
                    <span className="mv-order">#{String(row.event_order ?? "?")}</span>
                    <span className={`badge ${badgeClass(row.name)}`}>
                      <span className="dot" />
                      {badgeLabel(row.name)} {String(row.name ?? "")}
                    </span>
                    <button className="mv-copy" onClick={() => copyEvent(row)} aria-label="Copiar parâmetros do evento">
                      Copy
                    </button>
                  </div>
                  {params.length > 0 ? (
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
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
