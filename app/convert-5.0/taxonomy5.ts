export type Confidence = "auto" | "review" | "manual";
export type ConvField = { value: string; confidence: Confidence };
export type ConvEvent = {
  event_kind: string;
  event_order: number | string | null;
  has_error: boolean;
  has_product: boolean;
  fields: Record<string, ConvField>;
};

export const ENUMS: Record<string, readonly string[]> = {
  event: ["screen_view", "interaction", "noninteraction"],
  origin_nv: ["home", "menu", "push", "deeplink", "fluxo-interno"],
  event_access_type: ["vivo", "b2c", "b2b_m", "b2b_c"],
  client_category: ["adm_prin", "adm", "tec", "cob", "soc", "b2c_not_apply", "vivo_not_apply"],
  status_journey: ["intencao", "sucesso", "erro", "progresso", "excecao"],
  component_type: ["button", "link", "card", "modal", "toggle", "checkbox", "banner", "video", "dropdown"],
  error_status: ["bloqueado", "continuar"],
  error_type: ["usuario", "negocio", "aplicativo"],
  event_plan_type: ["pre", "pos", "controle", "fixa", "easy", "movel_corporativo", "fixo_corporativo"],
};

export const BASE_FIELDS = [
  "event", "screenName", "origin_nv", "event_access_type", "client_category",
  "department", "macro_journey", "micro_journey", "event_detail", "status_journey",
] as const;
export const COMPONENT_FIELDS = ["component_type", "component_copy"] as const;
export const ERROR_FIELDS = ["error_status", "error_type", "error_code"] as const;
export const PRODUCT_FIELDS = ["plan_name", "event_plan_type"] as const;

// Fields the journey-context form fills/overrides across all events.
export const CONTEXT_FIELDS = ["department", "macro_journey", "event_access_type", "client_category", "origin_nv"] as const;

// snake_case + ASCII, mirror of the backend normalize (screenName/error_code excluded).
export function normalize(text: string): string {
  const noAccent = text.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  return noAccent.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

const SNAKE_RE = /^[a-z0-9_]+$/;
const PATH_RE = /^\/[a-z0-9-]+(\/[a-z0-9-]+)*\/?$/;

// The ordered list of active field keys for an event given its toggles.
export function activeFields(ev: ConvEvent): string[] {
  const keys: string[] = [...BASE_FIELDS];
  if (ev.event_kind === "interaction" || ev.event_kind === "noninteraction") keys.push(...COMPONENT_FIELDS);
  if (ev.has_error) keys.push(...ERROR_FIELDS);
  if (ev.has_product) keys.push(...PRODUCT_FIELDS);
  return keys;
}

// Advisory validation: returns per-field issue strings for the active set.
export function validate(ev: ConvEvent): Record<string, string> {
  const issues: Record<string, string> = {};
  for (const key of activeFields(ev)) {
    const v = (ev.fields[key]?.value ?? "").trim();
    if (v === "") { issues[key] = "obrigatório"; continue; }
    if (ENUMS[key] && !ENUMS[key].includes(v)) { issues[key] = "valor fora do enum"; continue; }
    if (key === "screenName") { if (!PATH_RE.test(v)) issues[key] = "caminho inválido"; continue; }
    if (key === "error_code") continue; // raw code
    if (!ENUMS[key] && !SNAKE_RE.test(v)) issues[key] = "use snake_case sem acento";
  }
  return issues;
}

// The copy-paste block for one event: "chave: valor" per active field.
export function toBlock(ev: ConvEvent): string {
  return activeFields(ev)
    .map((k) => `${k}: ${ev.fields[k]?.value ?? ""}`)
    .join("\n");
}

// Ensures the toggled set's fields are present (blank `manual` if missing) when
// the analyst turns error/product on for an event that wasn't auto-detected as such.
export function withToggles(ev: ConvEvent, hasError: boolean, hasProduct: boolean): ConvEvent {
  const fields = { ...ev.fields };
  const ensure = (keys: readonly string[]) => {
    for (const k of keys) if (!fields[k]) fields[k] = { value: "", confidence: "manual" };
  };
  if (hasError) ensure(ERROR_FIELDS); if (hasProduct) ensure(PRODUCT_FIELDS);
  return { ...ev, has_error: hasError, has_product: hasProduct, fields };
}
