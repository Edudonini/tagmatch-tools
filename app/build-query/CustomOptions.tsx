"use client";

export type SpecEvent = Record<string, unknown>;

export type CustomOptionsState = {
  selectedOrders: number[];
  filterFields: Record<string, string[]>;
  outputColumns: string[];
};

// Mirrors the platform's CustomQueryPanel constants (CustomQueryPanel.tsx:35-49).
export const FILTER_FIELDS = [
  "sn", "ct", "ac", "lb",
  "component_copy", "component_type", "module_name", "item_name", "item_id",
];

export const ALL_OUTPUT_COLUMNS = [
  "event_date", "data", "hora", "event_name",
  "screenName", "eventCategory", "eventAction", "eventLabel",
  "ga_session_id", "event_timestamp",
  "component_copy", "component_type", "module_name",
  "item_name", "item_id", "value", "transaction_id",
  "price", "quantity", "origin_nv", "tag_label",
];

export const DEFAULT_OUTPUT_COLUMNS = ["event_name", "screenName", "eventCategory", "eventAction", "eventLabel"];

function eventLabelFor(ev: SpecEvent): string {
  const order = String(ev.event_order ?? "?");
  const name = String(ev.name ?? "");
  const detail = String(ev.sn || ev.lb || ev.ac || "");
  return `#${order} ${name}${detail ? ` — ${detail}` : ""}`;
}

type CustomOptionsProps = {
  events: SpecEvent[];
  value: CustomOptionsState;
  onChange: (next: CustomOptionsState) => void;
};

export function CustomOptions({ events, value, onChange }: CustomOptionsProps) {
  function toggleEvent(order: number) {
    const selected = value.selectedOrders.includes(order)
      ? value.selectedOrders.filter((o) => o !== order)
      : [...value.selectedOrders, order];
    onChange({ ...value, selectedOrders: selected });
  }

  function toggleFilterField(order: number, field: string) {
    const key = String(order);
    const current = value.filterFields[key] ?? [];
    const next = current.includes(field) ? current.filter((f) => f !== field) : [...current, field];
    onChange({ ...value, filterFields: { ...value.filterFields, [key]: next } });
  }

  function toggleOutputColumn(col: string) {
    const next = value.outputColumns.includes(col)
      ? value.outputColumns.filter((c) => c !== col)
      : [...value.outputColumns, col];
    onChange({ ...value, outputColumns: next });
  }

  return (
    <div className="qb-custom">
      <div className="qb-section-label">Events to include</div>
      {events.map((ev) => {
        const order = Number(ev.event_order);
        const selected = value.selectedOrders.includes(order);
        const populatedFilterFields = FILTER_FIELDS.filter((f) => String(ev[f] ?? "") !== "");
        return (
          <div key={order} className="qb-custom-event">
            <label className="qb-check">
              <input type="checkbox" checked={selected} onChange={() => toggleEvent(order)} />
              <span className="mono">{eventLabelFor(ev)}</span>
            </label>
            {selected && populatedFilterFields.length > 0 && (
              <div className="qb-filter-fields">
                {populatedFilterFields.map((f) => (
                  <label key={f} className="qb-check qb-check-small">
                    <input
                      type="checkbox"
                      checked={(value.filterFields[String(order)] ?? []).includes(f)}
                      onChange={() => toggleFilterField(order, f)}
                    />
                    <span className="mono">{f}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}

      <div className="qb-section-label">Output columns</div>
      <div className="qb-columns-grid">
        {ALL_OUTPUT_COLUMNS.map((col) => (
          <label key={col} className="qb-check qb-check-small">
            <input
              type="checkbox"
              checked={value.outputColumns.includes(col)}
              onChange={() => toggleOutputColumn(col)}
            />
            <span className="mono">{col}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
