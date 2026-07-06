"use client";

import { useEffect } from "react";

export type MatchRow = Record<string, unknown>;

type ValidationIssue = { field?: string; spec_value?: unknown; log_value?: unknown; type?: string };

type MatchDetailDrawerProps = {
  row: MatchRow;
  onClose: () => void;
};

const COMPARE_FIELDS: { specKey: string; logKey: string; label: string }[] = [
  { specKey: "sn", logKey: "matched_screenName", label: "sn / screenName" },
  { specKey: "ct", logKey: "matched_eventCategory", label: "ct / eventCategory" },
  { specKey: "ac", logKey: "matched_eventAction", label: "ac / eventAction" },
  { specKey: "lb", logKey: "matched_eventLabel", label: "lb / eventLabel" },
];

export function MatchDetailDrawer({ row, onClose }: MatchDetailDrawerProps) {
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const matched = row.matched === true;
  const issues = Array.isArray(row.validation_issues) ? (row.validation_issues as ValidationIssue[]) : [];

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h3>
            #{String(row.event_order ?? "?")} {String(row.name ?? "")}
          </h3>
          <button className="btn btn-ghost" onClick={onClose}>
            Close ✕
          </button>
        </div>

        <div className="drawer-meta">
          <span className={`badge ${matched ? "badge-nonint" : "badge-int"}`}>
            <span className="dot" />
            {matched ? "matched" : "unmatched"}
          </span>
          <span className="mono drawer-meta-item">confidence: {String(row.confidence ?? "")}</span>
          <span className="mono drawer-meta-item">reason: {String(row.match_reason ?? "")}</span>
        </div>

        <div className="drawer-section-label">Spec vs matched log</div>
        <table className="drawer-compare">
          <thead>
            <tr>
              <th>field</th>
              <th>spec</th>
              <th>log</th>
            </tr>
          </thead>
          <tbody>
            {COMPARE_FIELDS.map((f) => {
              const specVal = String(row[f.specKey] ?? "");
              const logVal = String(row[f.logKey] ?? "");
              const differs = matched && specVal !== "" && logVal !== "" && specVal !== logVal;
              return (
                <tr key={f.specKey} className={differs ? "drawer-differs" : undefined}>
                  <td className="mono">{f.label}</td>
                  <td className="mono">{specVal || "—"}</td>
                  <td className="mono">{logVal || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="drawer-section-label">Field divergences</div>
        {issues.length === 0 ? (
          <p className="drawer-no-issues">No field divergences reported.</p>
        ) : (
          <table className="drawer-compare">
            <thead>
              <tr>
                <th>field</th>
                <th>spec</th>
                <th>log</th>
                <th>type</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((iss, i) => (
                <tr key={i} className="drawer-differs">
                  <td className="mono">{String(iss.field ?? "")}</td>
                  <td className="mono">{String(iss.spec_value ?? "")}</td>
                  <td className="mono">{String(iss.log_value ?? "")}</td>
                  <td className="mono">{String(iss.type ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </aside>
    </div>
  );
}
