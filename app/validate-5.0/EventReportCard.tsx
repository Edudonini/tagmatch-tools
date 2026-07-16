"use client";

import { badgeClass, badgeLabel } from "../_lib/ResultsPanel";

export type FieldRow = {
  field: string;
  value: string;
  status: "ok" | "red" | "amber" | "missing" | "extra";
  reason: string;
};

export type EventReport = {
  event_type: string;
  event_order: number | string | null;
  screen: string;
  verdict: "red" | "amber" | "green";
  counts: { red: number; amber: number };
  fields: FieldRow[];
};

const STATUS_ICON: Record<FieldRow["status"], string> = {
  ok: "✓",
  red: "🔴",
  amber: "🟡",
  missing: "🔴",
  extra: "·",
};

export function EventReportCard({ event }: { event: EventReport }) {
  return (
    <div className={`panel report-card verdict-${event.verdict}`}>
      <div className="report-card-head">
        <span className={`verdict-dot v-${event.verdict}`} />
        <span className={`badge ${badgeClass(event.event_type)}`}>
          <span className="dot" />
          {badgeLabel(event.event_type)}
        </span>
        {event.event_order != null && <span className="mv-order">#{String(event.event_order)}</span>}
        <span className="mono report-screen">{event.screen || "—"}</span>
        {(event.counts.red > 0 || event.counts.amber > 0) && (
          <span className="report-counts">
            {event.counts.red > 0 && <span className="c-red">🔴 {event.counts.red}</span>}
            {event.counts.amber > 0 && <span className="c-amber">🟡 {event.counts.amber}</span>}
          </span>
        )}
      </div>
      <div className="report-fields">
        {event.fields.map((r) => (
          <div className={`report-row st-${r.status}`} key={r.field}>
            <span className="report-ico">{STATUS_ICON[r.status]}</span>
            <span className="report-field mono">{r.field}</span>
            <span className="report-value mono">
              {r.status === "missing" ? "— ausente" : r.value || "—"}
            </span>
            <span className="report-reason">{r.reason}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
