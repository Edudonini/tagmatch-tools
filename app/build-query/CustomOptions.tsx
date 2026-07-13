"use client";

export type SpecEvent = Record<string, unknown>;

export type Condition = { id: string; column: string; op: string; value: string };
export type ConditionGroup = { id: string; match: "and" | "or"; conditions: Condition[] };

export type CustomOptionsState = {
  outputMode: "count_sessions" | "count_events" | "extract" | "aggregate";
  match: "and" | "or"; // between groups
  groups: ConditionGroup[];
  scopeEnabled: boolean;
  scopeMatch: "and" | "or";
  scopeConditions: Condition[];
  groupByDims: string[];
  outputColumns: string[];
  limit: number;
  aggFunc: "sum" | "avg" | "min" | "max" | "count";
  aggColumn: string; // "" = none
};

let idSeq = 0;
function newId(): string {
  idSeq += 1;
  return `c${idSeq}`;
}
function newCondition(column = "event_name", op = "eq", value = ""): Condition {
  return { id: newId(), column, op, value };
}
function newGroup(): ConditionGroup {
  return { id: newId(), match: "and", conditions: [newCondition()] };
}

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

// Every value here is within the server's 81-column allow-list
// (api/_lib/custom_query.py ALLOWED_COLUMNS). A column added here but not in
// that set fails generation with "Unknown column".
export const COLUMN_GROUPS: { label: string; columns: string[] }[] = [
  { label: "Evento", columns: ["event_name", "eventCategory", "eventAction", "eventLabel", "screenName", "previousScreenName", "screenId", "screenNameWV", "ga_session_id", "data", "event_timestamp"] },
  { label: "Módulo / layout", columns: ["module_name", "module_title", "module_id", "module_position", "component_copy", "component_type", "component_style", "posicao", "indice", "listName"] },
  { label: "E-commerce", columns: ["item_id", "productName", "item_brand", "item_category", "productVariant", "quantity", "price", "value", "currency", "coupon", "discount", "transaction_id", "transaction_detail", "payment_method", "payment_type"] },
  { label: "Contexto / audiência", columns: ["audience", "audience_new", "client_category", "customer_segment", "user_plan", "user_access_type", "user_segment", "plan_name", "origin_nv", "source", "content", "content_category", "content_group", "page_location", "crm_name", "b2b_mve_tp_cliente", "audience_expression_1", "audience_expression_2", "audience_expression_3", "audience_expression_4", "audience_expression_5", "audience_expression_6", "audience_expression_7", "audience_expression_8", "audience_expression_9"] },
  { label: "Erro / status", columns: ["error_title", "error_type", "error_value", "tag_label", "tag_category", "badge", "title"] },
  { label: "Popup / jornada / B2B", columns: ["popup_option", "popup_title", "option_selected", "journeyVariant", "journey_origin", "event_cnpj", "info_detail", "description", "additional_product_info", "additional_product_info_1", "additional_product_info_2", "ga_event_origin", "frequency_capping"] },
];

export const ALL_COLUMNS: string[] = COLUMN_GROUPS.flatMap((g) => g.columns);

// Mirrors NUMERIC_COLUMNS in api/_lib/custom_query.py — sum/avg/min/max need one of these.
export const NUMERIC_COLUMNS = ["value", "price", "quantity", "discount", "module_position", "indice", "posicao"];

const DEFAULT_EXTRACT_COLUMNS = ["data", "event_timestamp", "event_name", "screenName", "ga_session_id"];

export const INITIAL_CUSTOM_STATE: CustomOptionsState = {
  outputMode: "count_sessions",
  match: "and",
  groups: [newGroup()],
  scopeEnabled: false,
  scopeMatch: "and",
  scopeConditions: [],
  groupByDims: [],
  outputColumns: [...DEFAULT_EXTRACT_COLUMNS],
  limit: 1000,
  aggFunc: "sum",
  aggColumn: "",
};

function opTakesValue(op: string): boolean {
  return OPERATORS.find((o) => o.value === op)?.takesValue ?? true;
}
function opIsNumeric(op: string): boolean {
  return OPERATORS.find((o) => o.value === op)?.numeric ?? false;
}

const NUMERIC_RE = /^-?\d+(\.\d+)?$/;

function numericError(op: string, value: string): string | null {
  if (!opIsNumeric(op)) return null;
  const v = value.trim();
  if (v === "") return "informe um número";
  if (!NUMERIC_RE.test(v)) return "número inválido";
  return null;
}

export function hasInvalidNumeric(state: CustomOptionsState): boolean {
  const all = [...state.groups.flatMap((g) => g.conditions), ...state.scopeConditions];
  return all.some((c) => numericError(c.op, c.value) !== null);
}

function cleanConditions(conditions: Condition[]): { column: string; op: string; value: string }[] {
  return conditions.filter((c) => c.column).map(({ column, op, value }) => ({ column, op, value }));
}

export function buildCustomPayload(state: CustomOptionsState): Record<string, unknown> {
  const groups = state.groups
    .map((g) => ({ match: g.match, conditions: cleanConditions(g.conditions) }))
    .filter((g) => g.conditions.length > 0);
  const payload: Record<string, unknown> = {
    output_mode: state.outputMode,
    filter: { match: state.match, groups },
  };
  if (state.scopeEnabled) {
    const scopeConds = cleanConditions(state.scopeConditions);
    if (scopeConds.length > 0) payload.session_scope = { match: state.scopeMatch, conditions: scopeConds };
  }
  if (state.outputMode === "extract") {
    payload.output_columns = state.outputColumns;
    payload.limit = state.limit;
  } else if (state.outputMode === "aggregate") {
    payload.aggregate = { func: state.aggFunc, column: state.aggColumn || null };
    payload.group_by = state.groupByDims;
  } else {
    payload.group_by = state.groupByDims;
  }
  return payload;
}

function ColumnOptions() {
  return (
    <>
      {COLUMN_GROUPS.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.columns.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </optgroup>
      ))}
    </>
  );
}

function ConditionRow({ cond, onChange, onRemove }: { cond: Condition; onChange: (patch: Partial<Condition>) => void; onRemove: () => void }) {
  const numErr = numericError(cond.op, cond.value);
  return (
    <div className="qb-cond-row">
      <select className="qb-cond-col" value={cond.column} onChange={(e) => onChange({ column: e.target.value })}>
        <ColumnOptions />
      </select>
      <select className="qb-cond-op" value={cond.op} onChange={(e) => onChange({ op: e.target.value })}>
        {OPERATORS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {opTakesValue(cond.op) && (
        <>
          <input
            className={`qb-cond-val review-field-input${numErr ? " qb-cond-val--invalid" : ""}`}
            value={cond.value}
            placeholder={cond.op === "in" ? "a, b, c" : "valor"}
            inputMode={opIsNumeric(cond.op) ? "decimal" : undefined}
            aria-invalid={numErr ? true : undefined}
            onChange={(e) => onChange({ value: e.target.value })}
          />
          {numErr && <span className="qb-cond-err">{numErr}</span>}
        </>
      )}
      <button type="button" className="qb-cond-x" onClick={onRemove} aria-label="Remover condição">✕</button>
    </div>
  );
}

function AndOrToggle({ value, onChange }: { value: "and" | "or"; onChange: (v: "and" | "or") => void }) {
  return (
    <div className="qb-andor">
      <button type="button" className={`qb-andor-btn${value === "and" ? " on" : ""}`} onClick={() => onChange("and")}>E</button>
      <button type="button" className={`qb-andor-btn${value === "or" ? " on" : ""}`} onClick={() => onChange("or")}>OU</button>
    </div>
  );
}

type CustomOptionsProps = {
  events: SpecEvent[];
  value: CustomOptionsState;
  onChange: (next: CustomOptionsState) => void;
};

export function CustomOptions({ events, value, onChange }: CustomOptionsProps) {
  function setGroups(groups: ConditionGroup[]) {
    onChange({ ...value, groups });
  }
  function updateCondition(gi: number, ci: number, patch: Partial<Condition>) {
    setGroups(value.groups.map((g, i) => i !== gi ? g : { ...g, conditions: g.conditions.map((c, j) => j === ci ? { ...c, ...patch } : c) }));
  }
  function removeCondition(gi: number, ci: number) {
    setGroups(value.groups.map((g, i) => i !== gi ? g : { ...g, conditions: g.conditions.filter((_, j) => j !== ci) }));
  }
  function addCondition(gi: number) {
    setGroups(value.groups.map((g, i) => i !== gi ? g : { ...g, conditions: [...g.conditions, newCondition()] }));
  }
  function addFromMap(gi: number) {
    const ev = events.find((e) => String(e.sn ?? "") !== "");
    const val = ev ? String(ev.sn ?? "") : "";
    setGroups(value.groups.map((g, i) => i !== gi ? g : { ...g, conditions: [...g.conditions, newCondition("screenName", "eq", val)] }));
  }
  function setGroupMatch(gi: number, m: "and" | "or") {
    setGroups(value.groups.map((g, i) => i === gi ? { ...g, match: m } : g));
  }
  function addGroup() {
    setGroups([...value.groups, newGroup()]);
  }
  function removeGroup(gi: number) {
    if (value.groups.length <= 1) return;
    setGroups(value.groups.filter((_, i) => i !== gi));
  }
  function updateScope(ci: number, patch: Partial<Condition>) {
    onChange({ ...value, scopeConditions: value.scopeConditions.map((c, j) => j === ci ? { ...c, ...patch } : c) });
  }
  function removeScope(ci: number) {
    onChange({ ...value, scopeConditions: value.scopeConditions.filter((_, j) => j !== ci) });
  }
  function addScopeCondition() {
    onChange({ ...value, scopeEnabled: true, scopeConditions: [...value.scopeConditions, newCondition("screenName", "eq", "")] });
  }
  function toggleOutputColumn(col: string) {
    const next = value.outputColumns.includes(col) ? value.outputColumns.filter((c) => c !== col) : [...value.outputColumns, col];
    onChange({ ...value, outputColumns: next });
  }
  function toggleGroupByDim(col: string) {
    const next = value.groupByDims.includes(col) ? value.groupByDims.filter((c) => c !== col) : [...value.groupByDims, col];
    onChange({ ...value, groupByDims: next });
  }

  const MODES: { key: CustomOptionsState["outputMode"]; label: string }[] = [
    { key: "count_sessions", label: "Contar sessões" },
    { key: "count_events", label: "Contar eventos" },
    { key: "extract", label: "Extrair linhas" },
    { key: "aggregate", label: "Agregar" },
  ];
  const AGG_FUNCS: { key: CustomOptionsState["aggFunc"]; label: string }[] = [
    { key: "sum", label: "SUM" }, { key: "avg", label: "AVG" }, { key: "min", label: "MIN" }, { key: "max", label: "MAX" }, { key: "count", label: "COUNT" },
  ];

  return (
    <div className="qb-custom">
      {/* Block 1: output mode */}
      <div className="qb-cb-block">
        <div className="qb-section-label">O que gerar</div>
        <div className="qb-seg">
          {MODES.map((m) => (
            <button type="button" key={m.key} className={`qb-seg-btn${value.outputMode === m.key ? " on" : ""}`} onClick={() => onChange({ ...value, outputMode: m.key })}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Block 2: condition groups */}
      <div className="qb-cb-block">
        <div className="qb-section-label">Condições (eventos que batem)</div>
        {value.groups.map((g, gi) => (
          <div key={g.id}>
            {gi > 0 && (
              <div className="qb-group-join">
                <AndOrToggle value={value.match} onChange={(m) => onChange({ ...value, match: m })} />
              </div>
            )}
            <div className="qb-group">
              <div className="qb-cb-head">
                <AndOrToggle value={g.match} onChange={(m) => setGroupMatch(gi, m)} />
                {value.groups.length > 1 && (
                  <button type="button" className="qb-cond-x" onClick={() => removeGroup(gi)} aria-label="Remover grupo">Remover grupo ✕</button>
                )}
              </div>
              {g.conditions.map((c, ci) => (
                <ConditionRow key={c.id} cond={c} onChange={(patch) => updateCondition(gi, ci, patch)} onRemove={() => removeCondition(gi, ci)} />
              ))}
              <div className="qb-cb-actions">
                <button type="button" className="qb-add" onClick={() => addCondition(gi)}>+ Adicionar condição</button>
                {events.length > 0 && (
                  <button type="button" className="qb-chip" onClick={() => addFromMap(gi)}>↳ a partir de um evento do mapa</button>
                )}
              </div>
            </div>
          </div>
        ))}
        <button type="button" className="qb-add qb-add-group" onClick={addGroup}>+ Adicionar grupo</button>
      </div>

      {/* Block 3: session scope */}
      <div className="qb-cb-block">
        <div className="qb-cb-head">
          <label className="qb-check">
            <input type="checkbox" checked={value.scopeEnabled} onChange={(e) => onChange({ ...value, scopeEnabled: e.target.checked })} />
            Limitar a sessões que passaram por…
          </label>
          {value.scopeEnabled && <AndOrToggle value={value.scopeMatch} onChange={(m) => onChange({ ...value, scopeMatch: m })} />}
        </div>
        {value.scopeEnabled && (
          <>
            {value.scopeConditions.map((c, ci) => (
              <ConditionRow key={c.id} cond={c} onChange={(patch) => updateScope(ci, patch)} onRemove={() => removeScope(ci)} />
            ))}
            <button type="button" className="qb-add" onClick={addScopeCondition}>+ Adicionar condição de sessão</button>
            <p className="qb-hint">Considera sessões cujo algum evento satisfaz isto (subquery sobre ga_session_id).</p>
          </>
        )}
      </div>

      {/* Block 4: mode-dependent */}
      {value.outputMode === "extract" && (
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
            <input type="number" min={1} max={10000} value={value.limit}
              onChange={(e) => onChange({ ...value, limit: Math.max(1, Math.min(10000, Number(e.target.value) || 1000)) })}
              className="review-field-input" />
          </label>
        </div>
      )}

      {value.outputMode === "aggregate" && (
        <div className="qb-cb-block">
          <div className="qb-section-label">Agregar</div>
          <div className="qb-agg-row">
            <select className="qb-cond-op" value={value.aggFunc} onChange={(e) => onChange({ ...value, aggFunc: e.target.value as CustomOptionsState["aggFunc"], aggColumn: "" })}>
              {AGG_FUNCS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
            </select>
            <span className="qb-agg-of">de</span>
            <select className="qb-cond-col" value={value.aggColumn} onChange={(e) => onChange({ ...value, aggColumn: e.target.value })}>
              <option value="">{value.aggFunc === "count" ? "— todas as linhas (COUNT *) —" : "— escolha uma coluna —"}</option>
              {value.aggFunc === "count"
                ? <ColumnOptions />
                : NUMERIC_COLUMNS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          {value.aggFunc !== "count" && !value.aggColumn && (
            <p className="qb-hint">Escolha uma coluna numérica ({NUMERIC_COLUMNS.join(", ")}).</p>
          )}
        </div>
      )}

      {(value.outputMode === "count_sessions" || value.outputMode === "count_events" || value.outputMode === "aggregate") && (
        <div className="qb-cb-block">
          <div className="qb-section-label">Agrupar por (opcional)</div>
          <div className="qb-columns-grid">
            {ALL_COLUMNS.map((col) => (
              <label key={col} className="qb-check qb-check-small">
                <input type="checkbox" checked={value.groupByDims.includes(col)} onChange={() => toggleGroupByDim(col)} />
                <span className="mono">{col}</span>
              </label>
            ))}
          </div>
          {value.groupByDims.length > 0 && (
            <p className="qb-hint">Dimensões: {value.groupByDims.join(", ")}</p>
          )}
        </div>
      )}
    </div>
  );
}
