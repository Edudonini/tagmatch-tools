"use client";

import { useEffect, useRef, useState } from "react";
import { StatRail } from "./StatRail";
import { rowMatchesQuery, rowTypeKey, type RowTypeKey } from "./rowFilter";

export type ResultRow = Record<string, unknown>;

export type ResultsPanelProps = {
  rows: ResultRow[];
  report: Record<string, unknown>;
  entityLabel: string;
  badgeColumn: string;
  downloadBaseName: string;
  onRowClick?: (row: ResultRow) => void;
};

export function badgeClass(name: unknown): string {
  const v = String(name ?? "").toLowerCase();
  if (v === "screen_view") return "badge-sv";
  if (v === "interaction") return "badge-int";
  if (v === "noninteraction") return "badge-nonint";
  return "badge-other";
}

export function badgeLabel(name: unknown): string {
  const v = String(name ?? "").toLowerCase();
  if (v === "screen_view") return "SV";
  if (v === "interaction") return "INT";
  if (v === "noninteraction") return "NON";
  return v ? v.slice(0, 3).toUpperCase() : "—";
}

function triggerDownload(rows: ResultRow[], columns: string[], format: "json" | "csv", baseName: string) {
  let blob: Blob;
  let filename: string;
  if (format === "json") {
    blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    filename = `${baseName}.json`;
  } else {
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

export function ResultsPanel({ rows, report, entityLabel, badgeColumn, downloadBaseName, onRowClick }: ResultsPanelProps) {
  const [showAllColumns, setShowAllColumns] = useState(false);
  const [query, setQuery] = useState("");
  const [activeTypes, setActiveTypes] = useState<Set<RowTypeKey>>(new Set());
  const [downloadOpen, setDownloadOpen] = useState(false);
  const downloadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!downloadOpen) return;

    function handlePointerDown(e: PointerEvent) {
      if (downloadRef.current && !downloadRef.current.contains(e.target as Node)) {
        setDownloadOpen(false);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setDownloadOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [downloadOpen]);

  const allColumns = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row).forEach((k) => set.add(k));
      return set;
    }, new Set<string>())
  );
  const populatedColumns = allColumns.filter((c) =>
    rows.some((r) => {
      const v = r[c];
      return v !== null && v !== undefined && String(v) !== "";
    })
  );
  const hasHiddenColumns = populatedColumns.length > 0 && populatedColumns.length < allColumns.length;
  const columns = showAllColumns || !hasHiddenColumns ? allColumns : populatedColumns;
  const hiddenCount = allColumns.length - populatedColumns.length;
  const badgeCol = columns.find((c) => c.toLowerCase() === badgeColumn.toLowerCase());

  const typeCounts = rows.reduce<Record<RowTypeKey, number>>(
    (acc, r) => {
      const k = rowTypeKey(badgeCol ? r[badgeCol] : undefined);
      acc[k] = (acc[k] ?? 0) + 1;
      return acc;
    },
    { SV: 0, INT: 0, NON: 0, other: 0 }
  );
  const typeFilters: RowTypeKey[] = (["SV", "INT", "NON", "other"] as RowTypeKey[]).filter((k) => typeCounts[k] > 0);
  const showTypeFilters = !!badgeCol && typeFilters.length > 1;

  const visibleRows = rows.filter((r) => {
    if (showTypeFilters && activeTypes.size > 0 && !activeTypes.has(rowTypeKey(badgeCol ? r[badgeCol] : undefined))) {
      return false;
    }
    return rowMatchesQuery(r, query);
  });

  const reportEntries = Object.entries(report ?? {});
  const scalarStats = reportEntries.filter(
    ([, v]) => v === null || ["string", "number", "boolean"].includes(typeof v)
  );
  const nestedReport = Object.fromEntries(reportEntries.filter(([k]) => !scalarStats.some(([sk]) => sk === k)));

  function toggleType(k: RowTypeKey) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  return (
    <>
      {scalarStats.length > 0 && (
        <StatRail
          stats={scalarStats.map(([key, value]) => ({
            label: key.replace(/_/g, " "),
            value: String(value),
          }))}
        />
      )}

      {Object.keys(nestedReport).length > 0 && (
        <details className="report-details">
          <summary>Relatório completo</summary>
          <pre>{JSON.stringify(nestedReport, null, 2)}</pre>
        </details>
      )}

      <div className="results-header">
        <h2>
          {entityLabel} — {visibleRows.length}
          {visibleRows.length !== rows.length ? ` de ${rows.length}` : ""} eventos
        </h2>
        <div className="results-actions">
          {hasHiddenColumns && (
            <button className="btn btn-ghost" onClick={() => setShowAllColumns((s) => !s)}>
              {showAllColumns ? "Ocultar colunas vazias" : `Mostrar todas as colunas (+${hiddenCount})`}
            </button>
          )}
          <div className="results-download" ref={downloadRef}>
            <button className="btn btn-ghost" aria-expanded={downloadOpen} onClick={() => setDownloadOpen((o) => !o)}>
              Baixar ▾
            </button>
            {downloadOpen && (
              <div className="results-download-menu">
                <button
                  onClick={() => {
                    triggerDownload(rows, allColumns, "json", downloadBaseName);
                    setDownloadOpen(false);
                  }}
                >
                  JSON
                </button>
                <button
                  onClick={() => {
                    triggerDownload(rows, allColumns, "csv", downloadBaseName);
                    setDownloadOpen(false);
                  }}
                >
                  CSV
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="results-filters">
        <input
          className="results-search"
          placeholder="Buscar…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Buscar nos resultados"
        />
        {showTypeFilters && (
          <div className="results-type-filters">
            {typeFilters.map((k) => (
              <button
                key={k}
                className={`badge ${k === "SV" ? "badge-sv" : k === "INT" ? "badge-int" : k === "NON" ? "badge-nonint" : "badge-other"}${
                  activeTypes.size > 0 && !activeTypes.has(k) ? " badge-off" : ""
                }`}
                onClick={() => toggleType(k)}
                aria-pressed={activeTypes.has(k)}
              >
                <span className="dot" />
                {k} {typeCounts[k]}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="spec-table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr
                key={i}
                className={onRowClick ? "row-clickable" : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((c) => (
                  <td key={c}>
                    {c === badgeCol ? (
                      <span className={`badge ${badgeClass(row[c])}`}>
                        <span className="dot" />
                        {badgeLabel(row[c])} {String(row[c] ?? "")}
                      </span>
                    ) : (
                      String(row[c] ?? "")
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
