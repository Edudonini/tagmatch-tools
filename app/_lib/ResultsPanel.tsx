"use client";

import { useState } from "react";

export type ResultRow = Record<string, unknown>;

export type ResultsPanelProps = {
  rows: ResultRow[];
  report: Record<string, unknown>;
  entityLabel: string;
  badgeColumn: string;
  downloadBaseName: string;
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

export function ResultsPanel({ rows, report, entityLabel, badgeColumn, downloadBaseName }: ResultsPanelProps) {
  const [showAllColumns, setShowAllColumns] = useState(false);

  const allColumns = rows.length > 0 ? Object.keys(rows[0]) : [];
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

  const reportEntries = Object.entries(report ?? {});
  const scalarStats = reportEntries.filter(
    ([, v]) => v === null || ["string", "number", "boolean"].includes(typeof v)
  );
  const nestedReport = Object.fromEntries(reportEntries.filter(([k]) => !scalarStats.some(([sk]) => sk === k)));

  return (
    <>
      {scalarStats.length > 0 && (
        <div className="stats">
          {scalarStats.map(([key, value]) => (
            <div className="stat" key={key}>
              <div className="stat-label">{key.replace(/_/g, " ")}</div>
              <div className="stat-value">{String(value)}</div>
            </div>
          ))}
        </div>
      )}

      {Object.keys(nestedReport).length > 0 && (
        <details className="report-details">
          <summary>Full report</summary>
          <pre>{JSON.stringify(nestedReport, null, 2)}</pre>
        </details>
      )}

      <div className="results-header">
        <h2>
          {entityLabel} — {rows.length} events
        </h2>
        <div className="results-actions">
          {hasHiddenColumns && (
            <button className="btn btn-ghost" onClick={() => setShowAllColumns((s) => !s)}>
              {showAllColumns ? "Hide empty columns" : `Show all columns (+${hiddenCount})`}
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => triggerDownload(rows, allColumns, "json", downloadBaseName)}>
            Download JSON
          </button>
          <button className="btn btn-ghost" onClick={() => triggerDownload(rows, allColumns, "csv", downloadBaseName)}>
            Download CSV
          </button>
        </div>
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
            {rows.map((row, i) => (
              <tr key={i}>
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
