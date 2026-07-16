"use client";

import { badgeClass, badgeLabel } from "../_lib/ResultsPanel";

export type Extracted5Event = {
  event_type: string;
  event_order: number | string | null;
  bbox: Record<string, number>;
  params: Record<string, string>;
};

export function EventParamsCard({ event }: { event: Extracted5Event }) {
  const entries = Object.entries(event.params);
  return (
    <div className="panel review-card convert5-card">
      <div className="convert5-card-header">
        <span className={`badge ${badgeClass(event.event_type)}`}>
          <span className="dot" />
          {badgeLabel(event.event_type)}
        </span>
        <span className="mv-order">#{String(event.event_order ?? "?")}</span>
        <span className="mono convert5-card-screen">{event.params.screenName || event.params.sn || "—"}</span>
      </div>
      <div className="convert5-field-list">
        {entries.map(([key, value]) => (
          <div className="convert5-field-row" key={key}>
            <span className="convert5-field-label mono">{key}</span>
            <span className="mono">{value || "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
