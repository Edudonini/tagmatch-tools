"use client";

export type SpecEvent = Record<string, unknown>;

export type Condition = { column: string; op: string; value: string };

export type CustomOptionsState = {
  outputMode: "count_sessions" | "count_events" | "extract";
  match: "and" | "or";
  conditions: Condition[];
  scopeEnabled: boolean;
  scopeMatch: "and" | "or";
  scopeConditions: Condition[];
  groupBy: string;
  outputColumns: string[];
  limit: number;
};

export const OPERATORS: { value: string; label: string; takesValue: boolean; numeric?: boolean }[] = [
  { value: "eq", label: "=", takesValue: true },
  { value: "neq", label: "≠", takesValue: true },
  { value: "contains", label: "contém", takesValue: true },
  { value: "starts_with", label: "começa com", takesValue: true },
  { value: "regex", label: "regex", takesValue: true },
  { value: "gt", label: ">", takesValue: true, numeric: true },
  { value: "lt", label: "<", takesValue: true, numeric: true },
  { value: "gte", label: "≥", takesValue: true, numeric: true },
  { value: "lte", label: "≤", takesValue: true, numeric: true },
  { value: "in", label: "na lista (IN)", takesValue: true },
  { value: "is_empty", label: "vazio", takesValue: false },
  { value: "is_not_empty", label: "não vazio", takesValue: false },
];

// Grouped for scannability. Every value here is within the server's 81-column
// allow-list (api/_lib/custom_query.py ALLOWED_COLUMNS). A column added here
// but not in that set fails generation with "Unknown column".
export const COLUMN_GROUPS: { label: string; columns: string[] }[] = [
  { label: "Evento", columns: ["event_name", "eventCategory", "eventAction", "eventLabel", "screenName", "previousScreenName", "screenId", "screenNameWV", "ga_session_id", "data", "event_timestamp"] },
  { label: "Módulo / layout", columns: ["module_name", "module_title", "module_id", "module_position", "component_copy", "component_type", "component_style", "posicao", "indice", "listName"] },
  { label: "E-commerce", columns: ["item_id", "productName", "item_brand", "item_category", "productVariant", "quantity", "price", "value", "currency", "coupon", "discount", "transaction_id", "transaction_detail", "payment_method", "payment_type"] },
  { label: "Contexto / audiência", columns: ["audience", "audience_new", "client_category", "customer_segment", "user_plan", "user_access_type", "user_segment", "plan_name", "origin_nv", "source", "content", "content_category", "content_group", "page_location", "crm_name", "b2b_mve_tp_cliente", "audience_expression_1", "audience_expression_2", "audience_expression_3", "audience_expression_4", "audience_expression_5", "audience_expression_6", "audience_expression_7", "audience_expression_8", "audience_expression_9"] },
  { label: "Erro / status", columns: ["error_title", "error_type", "error_value", "tag_label", "tag_category", "badge", "title"] },
  { label: "Popup / jornada / B2B", columns: ["popup_option", "popup_title", "option_selected", "journeyVariant", "journey_origin", "event_cnpj", "info_detail", "description", "additional_product_info", "additional_product_info_1", "additional_product_info_2", "ga_event_origin", "frequency_capping"] },
];

export const ALL_COLUMNS: string[] = COLUMN_GROUPS.flatMap((g) => g.columns);

const DEFAULT_EXTRACT_COLUMNS = ["data", "event_timestamp", "event_name", "screenName", "ga_session_id"];

export const INITIAL_CUSTOM_STATE: CustomOptionsState = {
  outputMode: "count_sessions",
  match: "and",
  conditions: [{ column: "event_name", op: "eq", value: "" }],
  scopeEnabled: false,
  scopeMatch: "and",
  scopeConditions: [],
  groupBy: "",
  outputColumns: [...DEFAULT_EXTRACT_COLUMNS],
  limit: 1000,
};

function opTakesValue(op: string): boolean {
  return OPERATORS.find((o) => o.value === op)?.takesValue ?? true;
}

function opIsNumeric(op: string): boolean {
  return OPERATORS.find((o) => o.value === op)?.numeric ?? false;
}

// Mirrors the server's numeric literal check exactly (api/_lib/custom_query.py).
const NUMERIC_RE = /^-?\d+(\.\d+)?$/;

// Returns null if the numeric field is fine, else the inline hint text to show.
function numericError(op: string, value: string): string | null {
  if (!opIsNumeric(op)) return null;
  const v = value.trim();
  if (v === "") return "informe um número";
  if (!NUMERIC_RE.test(v)) return "número inválido";
  return null;
}

export function hasInvalidNumeric(state: CustomOptionsState): boolean {
  const all = [...state.conditions, ...state.scopeConditions];
  return all.some((c) => numericError(c.op, c.value) !== null);
}

function cleanConditions(conditions: Condition[]): Condition[] {
  // Drop rows with no column; value-less operators keep an empty value.
  return conditions.filter((c) => c.column);
}

export function buildCustomPayload(state: CustomOptionsState): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    output_mode: state.outputMode,
    match: state.match,
    conditions: cleanConditions(state.conditions),
  };
  if (state.scopeEnabled) {
    const scopeConds = cleanConditions(state.scopeConditions);
    if (scopeConds.length > 0) {
      payload.session_scope = { match: state.scopeMatch, conditions: scopeConds };
    }
  }
  if (state.outputMode === "extract") {
    payload.output_columns = state.outputColumns;
    payload.limit = state.limit;
  } else if (state.groupBy) {
    payload.group_by = state.groupBy;
  }
  return payload;
}

function ColumnSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select className="qb-cond-col" value={value} onChange={(e) => onChange(e.target.value)}>
      {COLUMN_GROUPS.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.columns.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

function ConditionList({
  conditions,
  onChange,
}: {
  conditions: Condition[];
  onChange: (next: Condition[]) => void;
}) {
  function update(i: number, patch: Partial<Condition>) {
    const next = conditions.map((c, idx) => (idx === i ? { ...c, ...patch } : c));
    onChange(next);
  }
  function remove(i: number) {
    onChange(conditions.filter((_, idx) => idx !== i));
  }
  return (
    <>
      {conditions.map((c, i) => {
        const numErr = numericError(c.op, c.value);
        return (
        <div key={i} className="qb-cond-row">
          <ColumnSelect value={c.column} onChange={(v) => update(i, { column: v })} />
          <select className="qb-cond-op" value={c.op} onChange={(e) => update(i, { op: e.target.value })}>
            {OPERATORS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {opTakesValue(c.op) && (
            <>
              <input
                className={`qb-cond-val review-field-input${numErr ? " qb-cond-val--invalid" : ""}`}
                value={c.value}
                placeholder={c.op === "in" ? "a, b, c" : "valor"}
                inputMode={opIsNumeric(c.op) ? "decimal" : undefined}
                aria-invalid={numErr ? true : undefined}
                onChange={(e) => update(i, { value: e.target.value })}
              />
              {numErr && (
                <span className="qb-cond-err">{numErr}</span>
              )}
            </>
          )}
          <button type="button" className="qb-cond-x" onClick={() => remove(i)} aria-label="Remover condição">✕</button>
        </div>
        );
      })}
    </>
  );
}

type CustomOptionsProps = {
  events: SpecEvent[];
  value: CustomOptionsState;
  onChange: (next: CustomOptionsState) => void;
};

export function CustomOptions({ events, value, onChange }: CustomOptionsProps) {
  function addCondition() {
    onChange({ ...value, conditions: [...value.conditions, { column: "event_name", op: "eq", value: "" }] });
  }
  function addFromMap() {
    const ev = events.find((e) => String(e.sn ?? "") !== "");
    const column = "screenName";
    const val = ev ? String(ev.sn ?? "") : "";
    onChange({ ...value, conditions: [...value.conditions, { column, op: "eq", value: val }] });
  }
  function addScopeCondition() {
    onChange({
      ...value,
      scopeEnabled: true,
      scopeConditions: [...value.scopeConditions, { column: "screenName", op: "eq", value: "" }],
    });
  }
  function toggleOutputColumn(col: string) {
    const next = value.outputColumns.includes(col)
      ? value.outputColumns.filter((c) => c !== col)
      : [...value.outputColumns, col];
    onChange({ ...value, outputColumns: next });
  }

  const MODES: { key: CustomOptionsState["outputMode"]; label: string }[] = [
    { key: "count_sessions", label: "Contar sessões" },
    { key: "count_events", label: "Contar eventos" },
    { key: "extract", label: "Extrair linhas" },
  ];

  return (
    <div className="qb-custom">
      {/* Block 1: output mode */}
      <div className="qb-cb-block">
        <div className="qb-section-label">O que gerar</div>
        <div className="qb-seg">
          {MODES.map((m) => (
            <button
              type="button"
              key={m.key}
              className={`qb-seg-btn${value.outputMode === m.key ? " on" : ""}`}
              onClick={() => onChange({ ...value, outputMode: m.key })}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Block 2: conditions */}
      <div className="qb-cb-block">
        <div className="qb-cb-head">
          <div className="qb-section-label">Condições (eventos que batem)</div>
          <div className="qb-andor">
            <button type="button" className={`qb-andor-btn${value.match === "and" ? " on" : ""}`} onClick={() => onChange({ ...value, match: "and" })}>E</button>
            <button type="button" className={`qb-andor-btn${value.match === "or" ? " on" : ""}`} onClick={() => onChange({ ...value, match: "or" })}>OU</button>
          </div>
        </div>
        <ConditionList conditions={value.conditions} onChange={(next) => onChange({ ...value, conditions: next })} />
        <div className="qb-cb-actions">
          <button type="button" className="qb-add" onClick={addCondition}>+ Adicionar condição</button>
          {events.length > 0 && (
            <button type="button" className="qb-chip" onClick={addFromMap}>↳ a partir de um evento do mapa</button>
          )}
        </div>
      </div>

      {/* Block 3: session scope */}
      <div className="qb-cb-block">
        <div className="qb-cb-head">
          <label className="qb-check">
            <input
              type="checkbox"
              checked={value.scopeEnabled}
              onChange={(e) => onChange({ ...value, scopeEnabled: e.target.checked })}
            />
            Limitar a sessões que passaram por…
          </label>
          {value.scopeEnabled && (
            <div className="qb-andor">
              <button type="button" className={`qb-andor-btn${value.scopeMatch === "and" ? " on" : ""}`} onClick={() => onChange({ ...value, scopeMatch: "and" })}>E</button>
              <button type="button" className={`qb-andor-btn${value.scopeMatch === "or" ? " on" : ""}`} onClick={() => onChange({ ...value, scopeMatch: "or" })}>OU</button>
            </div>
          )}
        </div>
        {value.scopeEnabled && (
          <>
            <ConditionList conditions={value.scopeConditions} onChange={(next) => onChange({ ...value, scopeConditions: next })} />
            <button type="button" className="qb-add" onClick={addScopeCondition}>+ Adicionar condição de sessão</button>
            <p className="qb-hint">Considera sessões cujo algum evento satisfaz isto (subquery sobre ga_session_id).</p>
          </>
        )}
      </div>

      {/* Block 4: mode-dependent */}
      {value.outputMode === "extract" ? (
        <div className="qb-cb-block">
          <div className="qb-section-label">Colunas de saída</div>
          <div className="qb-columns-grid">
            {ALL_COLUMNS.map((col) => (
              <label key={col} className="qb-check qb-check-small">
                <input type="checkbox" checked={value.outputColumns.includes(col)} onChange={() => toggleOutputColumn(col)} />
                <span className="mono">{col}</span>
              </label>
            ))}
          </div>
          <label className="review-field-label qb-limit-field">
            Limite de linhas
            <input
              type="number"
              min={1}
              max={10000}
              value={value.limit}
              onChange={(e) => onChange({ ...value, limit: Math.max(1, Math.min(10000, Number(e.target.value) || 1000)) })}
              className="review-field-input"
            />
          </label>
        </div>
      ) : (
        <div className="qb-cb-block">
          <div className="qb-section-label">Agrupar por (opcional)</div>
          <select className="qb-cond-col" value={value.groupBy} onChange={(e) => onChange({ ...value, groupBy: e.target.value })}>
            <option value="">— sem agrupamento —</option>
            {COLUMN_GROUPS.map((g) => (
              <optgroup key={g.label} label={g.label}>
                {g.columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
