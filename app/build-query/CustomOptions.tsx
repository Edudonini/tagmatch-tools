"use client";

import { useMemo } from "react";

export type SpecEvent = Record<string, unknown>;

export type Condition = { id: string; column: string; op: string; value: string };
export type ConditionGroup = { id: string; match: "and" | "or"; conditions: Condition[] };
export type FunnelStep = { id: string; label: string; match: "and" | "or"; conditions: Condition[] };
export type AggMetric = { id: string; func: string; column: string };
export type HavingCond = { id: string; func: string; column: string; op: string; value: string };

export type CustomOptionsState = {
  outputMode: "count_sessions" | "count_events" | "extract" | "aggregate" | "funnel";
  match: "and" | "or"; // between groups
  groups: ConditionGroup[];
  scopeEnabled: boolean;
  scopeMatch: "and" | "or";
  scopeConditions: Condition[];
  groupByDims: string[];
  outputColumns: string[];
  limit: number;
  metrics: AggMetric[];
  having: HavingCond[];
  timeBucketEnabled: boolean;
  timeBucketUnit: "day" | "week" | "month";
  funnelSteps: FunnelStep[];
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
function newFunnelStep(): FunnelStep {
  return { id: newId(), label: "", match: "and", conditions: [newCondition()] };
}
function newMetric(): AggMetric {
  return { id: newId(), func: "count", column: "" };
}
function newHaving(): HavingCond {
  return { id: newId(), func: "count", column: "", op: "gt", value: "" };
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

export const AGG_FUNCTIONS: { value: string; label: string }[] = [
  { value: "count", label: "COUNT" },
  { value: "sum", label: "SUM" },
  { value: "avg", label: "AVG" },
  { value: "min", label: "MIN" },
  { value: "max", label: "MAX" },
  { value: "approx_count_distinct", label: "DISTINCT (aprox.)" },
  { value: "stddev", label: "STDDEV" },
];
// Functions that require a numeric column (mirrors _NUMERIC_AGG_FUNCS in custom_query.py).
const NUMERIC_AGG_FUNCS = new Set(["sum", "avg", "min", "max", "stddev"]);
const HAVING_OPS: { value: string; label: string }[] = [
  { value: "gt", label: ">" }, { value: "lt", label: "<" }, { value: "gte", label: "≥" },
  { value: "lte", label: "≤" }, { value: "eq", label: "=" }, { value: "neq", label: "≠" },
];
const TIME_BUCKET_UNITS: { value: string; label: string }[] = [
  { value: "day", label: "dia" }, { value: "week", label: "semana" }, { value: "month", label: "mês" },
];

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
  metrics: [newMetric()],
  having: [],
  timeBucketEnabled: false,
  timeBucketUnit: "day",
  funnelSteps: [newFunnelStep(), newFunnelStep()],
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
  const all = [
    ...state.groups.flatMap((g) => g.conditions),
    ...state.scopeConditions,
    ...state.funnelSteps.flatMap((s) => s.conditions),
  ];
  if (all.some((c) => numericError(c.op, c.value) !== null)) return true;
  if (state.outputMode === "aggregate") {
    // Every numeric-requiring metric needs a numeric column; approx_count_distinct needs a column.
    const metricInvalid = state.metrics.some(
      (m) =>
        (NUMERIC_AGG_FUNCS.has(m.func) && !NUMERIC_COLUMNS.includes(m.column)) ||
        (m.func === "approx_count_distinct" && !m.column)
    );
    if (state.metrics.length === 0 || metricInvalid) return true;
    // Every filled HAVING row needs a numeric value and (for numeric funcs) a numeric column.
    const havingInvalid = state.having.some(
      (h) =>
        h.value.trim() !== "" &&
        (numericError("gt", h.value) !== null ||
          (NUMERIC_AGG_FUNCS.has(h.func) && !NUMERIC_COLUMNS.includes(h.column)) ||
          (h.func === "approx_count_distinct" && !h.column))
    );
    if (havingInvalid) return true;
  }
  // Funnel mode: need at least 2 steps that each carry a real condition.
  if (state.outputMode === "funnel") {
    const usable = state.funnelSteps.filter((s) => s.conditions.some((c) => c.column));
    if (usable.length < 2) return true;
  }
  return false;
}

function cleanConditions(conditions: Condition[]): { column: string; op: string; value: string }[] {
  return conditions.filter((c) => c.column).map(({ column, op, value }) => ({ column, op, value }));
}

// Maps the spec's short field names to their Silver columns for suggestions.
const SPEC_FIELD_TO_COLUMN: Record<string, string> = {
  sn: "screenName",
  name: "event_name",
  ct: "eventCategory",
  ac: "eventAction",
  lb: "eventLabel",
};

// Build column -> distinct spec values (advisory autocomplete only; the server
// still validates/escapes every value). Empty for columns with no spec values.
function buildSuggestionIndex(events: SpecEvent[]): Record<string, string[]> {
  const allowed = new Set(ALL_COLUMNS);
  const acc: Record<string, Set<string>> = {};
  const add = (col: string, raw: unknown) => {
    // Only scalar spec fields yield suggestions; skip arrays/objects so a
    // non-flat field never surfaces as "[object Object]".
    if (typeof raw !== "string" && typeof raw !== "number") return;
    const v = String(raw).trim();
    if (!v) return;
    (acc[col] ??= new Set()).add(v);
  };
  for (const ev of events) {
    for (const [key, col] of Object.entries(SPEC_FIELD_TO_COLUMN)) {
      if (key in ev) add(col, (ev as Record<string, unknown>)[key]);
    }
    for (const [key, val] of Object.entries(ev)) {
      if (allowed.has(key)) add(key, val);
    }
  }
  const out: Record<string, string[]> = {};
  for (const [col, set] of Object.entries(acc)) {
    out[col] = Array.from(set).sort().slice(0, 50);
  }
  return out;
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
    const aggregate: Record<string, unknown> = {
      metrics: state.metrics.map((m) => ({ func: m.func, column: m.column || null })),
    };
    const having = state.having
      // Every HAVING row needs a numeric value; drop rows the user started but
      // left blank so an unfinished row does not 400 (the server rejects "").
      .filter((h) => h.value.trim() !== "")
      .map((h) => ({ func: h.func, column: h.column || null, op: h.op, value: h.value }));
    if (having.length > 0) aggregate.having = having;
    payload.aggregate = aggregate;
    payload.group_by = state.groupByDims;
    if (state.timeBucketEnabled) payload.time_bucket = { unit: state.timeBucketUnit };
  } else if (state.outputMode === "funnel") {
    // The global filter is optional in funnel mode: drop conditions that need a
    // value but have none (and groups left empty) so an untouched filter emits
    // nothing, instead of a base-scan-zeroing `event_name = ''`.
    const globalGroups = state.groups
      .map((g) => ({
        match: g.match,
        conditions: cleanConditions(g.conditions).filter((c) => !opTakesValue(c.op) || c.value.trim() !== ""),
      }))
      .filter((g) => g.conditions.length > 0);
    payload.filter = { match: state.match, groups: globalGroups };
    payload.funnel = {
      steps: state.funnelSteps.map((s) => {
        const step: Record<string, unknown> = { match: s.match, conditions: cleanConditions(s.conditions) };
        if (s.label.trim()) step.label = s.label.trim();
        return step;
      }),
    };
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

// Column options for an aggregate func/metric: numeric-only for funcs that require a
// numeric column, otherwise the full column list plus a leading empty option (only
// meaningful for COUNT, which accepts "no column" = COUNT *).
function AggColumnOptions({ func }: { func: string }) {
  if (NUMERIC_AGG_FUNCS.has(func)) {
    return <>{NUMERIC_COLUMNS.map((c) => <option key={c} value={c}>{c}</option>)}</>;
  }
  return (
    <>
      <option value="">— nenhuma —</option>
      <ColumnOptions />
    </>
  );
}

function ConditionRow({ cond, suggestions, onChange, onRemove }: { cond: Condition; suggestions?: string[]; onChange: (patch: Partial<Condition>) => void; onRemove: () => void }) {
  const numErr = numericError(cond.op, cond.value);
  const listId = suggestions && suggestions.length > 0 ? `dl-${cond.id}` : undefined;
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
            list={listId}
            onChange={(e) => onChange({ value: e.target.value })}
          />
          {listId && (
            <datalist id={listId}>
              {suggestions!.map((s) => <option key={s} value={s} />)}
            </datalist>
          )}
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
  function updateFunnelStep(id: string, patch: Partial<FunnelStep>) {
    onChange({ ...value, funnelSteps: value.funnelSteps.map((s) => (s.id === id ? { ...s, ...patch } : s)) });
  }
  function addFunnelStep() {
    if (value.funnelSteps.length >= 10) return;
    onChange({ ...value, funnelSteps: [...value.funnelSteps, newFunnelStep()] });
  }
  function removeFunnelStep(id: string) {
    if (value.funnelSteps.length <= 2) return;
    onChange({ ...value, funnelSteps: value.funnelSteps.filter((s) => s.id !== id) });
  }
  function moveFunnelStep(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= value.funnelSteps.length) return;
    const next = value.funnelSteps.slice();
    [next[index], next[target]] = [next[target], next[index]];
    onChange({ ...value, funnelSteps: next });
  }
  function addStepCondition(stepId: string) {
    const step = value.funnelSteps.find((s) => s.id === stepId);
    if (!step) return;
    updateFunnelStep(stepId, { conditions: [...step.conditions, newCondition()] });
  }
  function removeStepCondition(stepId: string, condId: string) {
    const step = value.funnelSteps.find((s) => s.id === stepId);
    if (!step || step.conditions.length <= 1) return;
    updateFunnelStep(stepId, { conditions: step.conditions.filter((c) => c.id !== condId) });
  }
  function updateStepCondition(stepId: string, condId: string, patch: Partial<Condition>) {
    const step = value.funnelSteps.find((s) => s.id === stepId);
    if (!step) return;
    updateFunnelStep(stepId, {
      conditions: step.conditions.map((c) => (c.id === condId ? { ...c, ...patch } : c)),
    });
  }
  function updateMetric(id: string, patch: Partial<AggMetric>) {
    onChange({ ...value, metrics: value.metrics.map((m) => (m.id === id ? { ...m, ...patch } : m)) });
  }
  function addMetric() {
    onChange({ ...value, metrics: [...value.metrics, newMetric()] });
  }
  function removeMetric(id: string) {
    if (value.metrics.length <= 1) return;
    onChange({ ...value, metrics: value.metrics.filter((m) => m.id !== id) });
  }
  function updateHaving(id: string, patch: Partial<HavingCond>) {
    onChange({ ...value, having: value.having.map((h) => (h.id === id ? { ...h, ...patch } : h)) });
  }
  function addHaving() {
    onChange({ ...value, having: [...value.having, newHaving()] });
  }
  function removeHaving(id: string) {
    onChange({ ...value, having: value.having.filter((h) => h.id !== id) });
  }

  const MODES: { key: CustomOptionsState["outputMode"]; label: string }[] = [
    { key: "count_sessions", label: "Contar sessões" },
    { key: "count_events", label: "Contar eventos" },
    { key: "extract", label: "Extrair linhas" },
    { key: "aggregate", label: "Agregar" },
    { key: "funnel", label: "Funil" },
  ];

  const suggestionIndex = useMemo(() => buildSuggestionIndex(events), [events]);

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

      {/* Block 1b: funnel steps (funnel mode only) */}
      {value.outputMode === "funnel" && (
        <div className="qb-cb-block">
          <div className="qb-section-label">ETAPAS DO FUNIL</div>
          {value.funnelSteps.map((s, si) => (
            <div key={s.id} className="qb-funnel-step-card">
              <div className="qb-funnel-step-head">
                <span className="mono">{si + 1}.</span>
                <input
                  className="review-field-input"
                  value={s.label}
                  placeholder="Rótulo (opcional)"
                  onChange={(e) => updateFunnelStep(s.id, { label: e.target.value })}
                />
                <button type="button" className="qb-funnel-step-btn" onClick={() => moveFunnelStep(si, -1)} disabled={si === 0} aria-label="Mover etapa para cima">↑</button>
                <button type="button" className="qb-funnel-step-btn" onClick={() => moveFunnelStep(si, 1)} disabled={si === value.funnelSteps.length - 1} aria-label="Mover etapa para baixo">↓</button>
                <button type="button" className="qb-funnel-step-btn" onClick={() => removeFunnelStep(s.id)} disabled={value.funnelSteps.length <= 2} aria-label="Remover etapa">Remover ✕</button>
              </div>
              <AndOrToggle value={s.match} onChange={(m) => updateFunnelStep(s.id, { match: m })} />
              {s.conditions.map((c) => (
                <ConditionRow key={c.id} cond={c} suggestions={suggestionIndex[c.column]} onChange={(patch) => updateStepCondition(s.id, c.id, patch)} onRemove={() => removeStepCondition(s.id, c.id)} />
              ))}
              <div className="qb-cb-actions">
                <button type="button" className="qb-add" onClick={() => addStepCondition(s.id)}>+ Adicionar condição</button>
              </div>
            </div>
          ))}
          <button type="button" className="qb-add qb-add-group" onClick={addFunnelStep} disabled={value.funnelSteps.length >= 10}>+ Adicionar etapa</button>
        </div>
      )}

      {/* Block 2: condition groups */}
      <div className="qb-cb-block">
        <div className="qb-section-label">{value.outputMode === "funnel" ? "FILTRO GLOBAL (OPCIONAL)" : "Condições (eventos que batem)"}</div>
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
                <ConditionRow key={c.id} cond={c} suggestions={suggestionIndex[c.column]} onChange={(patch) => updateCondition(gi, ci, patch)} onRemove={() => removeCondition(gi, ci)} />
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
      {value.outputMode !== "funnel" && (
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
                <ConditionRow key={c.id} cond={c} suggestions={suggestionIndex[c.column]} onChange={(patch) => updateScope(ci, patch)} onRemove={() => removeScope(ci)} />
              ))}
              <button type="button" className="qb-add" onClick={addScopeCondition}>+ Adicionar condição de sessão</button>
              <p className="qb-hint">Considera sessões cujo algum evento satisfaz isto (subquery sobre ga_session_id).</p>
            </>
          )}
        </div>
      )}

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
          <div className="qb-section-label">MÉTRICAS</div>
          {value.metrics.map((m) => (
            <div key={m.id}>
              <div className="qb-cond-row">
                <select className="qb-cond-op" value={m.func} onChange={(e) => {
                  const func = e.target.value;
                  const patch: Partial<AggMetric> = { func };
                  // Clear a now-invalid column when switching to a numeric func.
                  if (NUMERIC_AGG_FUNCS.has(func) && !NUMERIC_COLUMNS.includes(m.column)) patch.column = "";
                  updateMetric(m.id, patch);
                }}>
                  {AGG_FUNCTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
                </select>
                <span className="qb-agg-of">de</span>
                <select className="qb-cond-col" value={m.column} onChange={(e) => updateMetric(m.id, { column: e.target.value })}>
                  <AggColumnOptions func={m.func} />
                </select>
                <button type="button" className="qb-cond-x" onClick={() => removeMetric(m.id)} disabled={value.metrics.length <= 1} aria-label="Remover métrica">✕</button>
              </div>
              {NUMERIC_AGG_FUNCS.has(m.func) && !NUMERIC_COLUMNS.includes(m.column) && (
                <p className="qb-hint">Escolha uma coluna numérica ({NUMERIC_COLUMNS.join(", ")}).</p>
              )}
              {m.func === "approx_count_distinct" && !m.column && (
                <p className="qb-hint">Escolha uma coluna.</p>
              )}
            </div>
          ))}
          <button type="button" className="qb-add" onClick={addMetric}>+ Adicionar métrica</button>
        </div>
      )}

      {value.outputMode !== "funnel" && (value.outputMode === "count_sessions" || value.outputMode === "count_events" || value.outputMode === "aggregate") && (
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
          {value.outputMode === "aggregate" && (
            <div className="qb-cb-head">
              <label className="qb-check">
                <input type="checkbox" checked={value.timeBucketEnabled} onChange={(e) => onChange({ ...value, timeBucketEnabled: e.target.checked })} />
                Bucket de tempo (opcional)
              </label>
              {value.timeBucketEnabled && (
                <select className="qb-cond-op" value={value.timeBucketUnit} onChange={(e) => onChange({ ...value, timeBucketUnit: e.target.value as CustomOptionsState["timeBucketUnit"] })}>
                  {TIME_BUCKET_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              )}
            </div>
          )}
        </div>
      )}

      {value.outputMode === "aggregate" && (
        <div className="qb-cb-block">
          <div className="qb-section-label">HAVING (FILTRAR GRUPOS)</div>
          {value.having.map((h) => {
            const numErr = numericError("gt", h.value);
            return (
              <div key={h.id}>
                <div className="qb-cond-row">
                  <select className="qb-cond-op" value={h.func} onChange={(e) => {
                    const func = e.target.value;
                    const patch: Partial<HavingCond> = { func };
                    if (NUMERIC_AGG_FUNCS.has(func) && !NUMERIC_COLUMNS.includes(h.column)) patch.column = "";
                    updateHaving(h.id, patch);
                  }}>
                    {AGG_FUNCTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
                  </select>
                  <select className="qb-cond-col" value={h.column} onChange={(e) => updateHaving(h.id, { column: e.target.value })}>
                    <AggColumnOptions func={h.func} />
                  </select>
                  <select className="qb-cond-op" value={h.op} onChange={(e) => updateHaving(h.id, { op: e.target.value })}>
                    {HAVING_OPS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <input
                    className={`qb-cond-val review-field-input${numErr ? " qb-cond-val--invalid" : ""}`}
                    value={h.value}
                    placeholder="valor"
                    inputMode="decimal"
                    aria-invalid={numErr ? true : undefined}
                    onChange={(e) => updateHaving(h.id, { value: e.target.value })}
                  />
                  <button type="button" className="qb-cond-x" onClick={() => removeHaving(h.id)} aria-label="Remover filtro de grupo">✕</button>
                </div>
                {h.value.trim() !== "" && NUMERIC_AGG_FUNCS.has(h.func) && !NUMERIC_COLUMNS.includes(h.column) && (
                  <p className="qb-hint">Escolha uma coluna numérica ({NUMERIC_COLUMNS.join(", ")}).</p>
                )}
                {h.value.trim() !== "" && h.func === "approx_count_distinct" && !h.column && (
                  <p className="qb-hint">Escolha uma coluna.</p>
                )}
                {numErr && <p className="qb-hint">{numErr}</p>}
              </div>
            );
          })}
          <button type="button" className="qb-add" onClick={addHaving}>+ Adicionar filtro de grupo</button>
        </div>
      )}
    </div>
  );
}
