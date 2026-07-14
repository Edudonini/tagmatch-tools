"use client";

import { badgeClass, badgeLabel } from "../_lib/ResultsPanel";
import { ENUMS, activeFields, isKnownField, isRawField, normalize, toBlock, validate, withToggles, type ConvEvent, type ConvField } from "./taxonomy5";

type ConvertCardProps = {
  event: ConvEvent;
  onChange: (ev: ConvEvent) => void;
};

const CONFIDENCE_LABEL: Record<ConvField["confidence"], string> = {
  auto: "✅ auto",
  review: "🟡 revisar",
  manual: "⬜ manual",
};

export function ConvertCard({ event, onChange }: ConvertCardProps) {
  function updateField(key: string, value: string) {
    // Keystrokes store the raw value; snake normalization happens on blur (except screenName/error_code).
    onChange({ ...event, fields: { ...event.fields, [key]: { ...event.fields[key], value } } });
  }
  function normalizeField(key: string) {
    // Raw fields (screenName/error_code) and passthrough fields are kept verbatim,
    // matching validate()'s exemption; only known free-text fields are snaked.
    if (isRawField(key) || !isKnownField(key)) return;
    const cur = event.fields[key]?.value ?? "";
    if (/^\[.*\]$/.test(cur.trim())) return; // dynamic placeholder, e.g. [nome_do_plano]
    const n = normalize(cur);
    if (n !== cur) updateField(key, n);
  }

  const fields = activeFields(event);
  const issues = validate(event);
  const issueCount = Object.keys(issues).length;

  function handleToggle(hasError: boolean, hasProduct: boolean) {
    onChange(withToggles(event, hasError, hasProduct));
  }

  function copyEvent() {
    navigator.clipboard.writeText(toBlock(event));
  }

  return (
    <div className="panel review-card convert5-card">
      <div className="convert5-card-header">
        <span className={`badge ${badgeClass(event.event_kind)}`}>
          <span className="dot" />
          {badgeLabel(event.event_kind)}
        </span>
        <span className="mv-order">#{String(event.event_order ?? "?")}</span>
        <span className="mono convert5-card-screen">{event.fields.screenName?.value || "—"}</span>
      </div>

      <div className="convert5-field-list">
        {fields.map((key) => {
          const field: ConvField = event.fields[key] ?? { value: "", confidence: "manual" };
          const issue = issues[key];
          return (
            <div className="convert5-field-row" key={key}>
              <label className="review-field-label convert5-field-label">
                {key}
                {ENUMS[key] ? (
                  <select
                    className="review-field-input"
                    value={field.value}
                    onChange={(e) => updateField(key, e.target.value)}
                  >
                    <option value="">—</option>
                    {ENUMS[key].map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="review-field-input"
                    value={field.value}
                    onChange={(e) => updateField(key, e.target.value)}
                    onBlur={() => normalizeField(key)}
                  />
                )}
              </label>
              <span className={`convert5-confidence convert5-confidence-${field.confidence}`}>
                {CONFIDENCE_LABEL[field.confidence]}
              </span>
              {issue && <span className="convert5-flag">{issue}</span>}
            </div>
          );
        })}
      </div>

      <div className="convert5-toggles">
        <label className="convert5-toggle">
          <input
            type="checkbox"
            checked={event.has_error}
            onChange={(e) => handleToggle(e.target.checked, event.has_product)}
          />
          É erro
        </label>
        <label className="convert5-toggle">
          <input
            type="checkbox"
            checked={event.has_product}
            onChange={(e) => handleToggle(event.has_error, e.target.checked)}
          />
          Desambiguação de produto
        </label>
      </div>

      <div className="convert5-footer">
        <span className="convert5-completion">
          {issueCount === 0 ? "tudo certo" : `faltam ${issueCount} campos`}
        </span>
        <button className="btn btn-ghost" onClick={copyEvent}>
          Copiar
        </button>
      </div>
    </div>
  );
}
