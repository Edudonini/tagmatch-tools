"""Validate clean App 5.0 events (from reparse_5_0) against the taxonomy standard.

Deterministic rules only — completeness, legacy fields, closed-enum membership,
dynamic-vs-fixed, nomenclature, conditionals, event_detail format. Semantic
coherence with the drawn screen and un-inferable placeholders are surfaced as
open_questions (they never affect a verdict). No I/O, no LLM.
"""
import re
import unicodedata

from .taxonomy5 import (
    EVENT_KINDS, EVENT_ACCESS_TYPE, CLIENT_CATEGORY, STATUS_JOURNEY,
    COMPONENT_TYPE, ERROR_STATUS, ERROR_TYPE, EVENT_PLAN_TYPE,
)

# --- Reference standard (App 5.0 taxonomy / techlead QA prompt) ---

_REQUIRED_BASE = [
    "event", "screenName", "origin_nv", "event_access_type", "client_category",
    "department", "macro_journey", "micro_journey", "event_detail", "status_journey",
]
REQUIRED_FIELDS = {
    "screen_view": _REQUIRED_BASE,
    "interaction": _REQUIRED_BASE + ["component_type", "component_copy"],
    "noninteraction": _REQUIRED_BASE + ["component_type", "component_copy"],
}

ENUMS = {
    "event": list(EVENT_KINDS),
    "event_access_type": list(EVENT_ACCESS_TYPE),
    "client_category": list(CLIENT_CATEGORY),
    "status_journey": list(STATUS_JOURNEY),
    "component_type": list(COMPONENT_TYPE),
    "error_status": list(ERROR_STATUS),
    "error_type": list(ERROR_TYPE),
    "event_plan_type": list(EVENT_PLAN_TYPE),
}

LEGACY_FIELDS = ["name", "sn", "ct", "ac", "lb", "eventCategory", "eventAction", "eventLabel"]
_LEGACY_MIGRATION = {
    "name": "event", "sn": "screenName",
    "eventCategory": "component_type/event_detail",
    "eventAction": "event_detail", "eventLabel": "component_copy",
}

ERROR_FIELDS = ["error_status", "error_type", "error_code"]
PRODUCT_FIELDS = ["plan_name", "event_plan_type"]

# Free-form snake_case fields the nomenclature standard actually governs.
_NOMENCLATURE_CHECK_FIELDS = ("department", "macro_journey", "micro_journey", "event_detail")

# --- Dynamic value detection ---
_VAR_RE = re.compile(r"\{\{.*?\}\}|\[.*?\]|<.*?>|\$\w+|%[sd]")
_OPTION_SPLIT_RE = re.compile(r"\s*(?:\||/|,|\bou\b)\s*")
_WRAP_RE = re.compile(r"^\[(.*)\]$|^\{\{(.*)\}\}$|^<(.*)>$", re.DOTALL)


def _s(value):
    return str(value).strip() if value is not None else ""


def _split_options(value):
    return [o.strip() for o in _OPTION_SPLIT_RE.split(_s(value)) if o.strip()]


def is_dynamic(value):
    """A value is dynamic if it uses variable notation or is a multi-option list."""
    v = _s(value)
    if not v:
        return False
    if _VAR_RE.search(v):
        return True
    return len(_split_options(v)) > 1


def _enum_tokens(value):
    """Option tokens to validate for a closed-enum field, or None when the value is a
    single un-inferable runtime variable (e.g. `[contexto]`)."""
    v = _s(value)
    if not v:
        return None
    m = _WRAP_RE.match(v)
    inner = next((g for g in m.groups() if g is not None), v) if m else v
    opts = _split_options(inner)
    if len(opts) <= 1:
        # single token: if it (still) carries variable markers, it's an un-inferable var
        if _VAR_RE.search(v) or not opts:
            return None
        return opts
    return opts


def _has_accent(value):
    return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFKD", str(value)))


def _nomenclature_problem(value):
    """Problem string if a FIXED value violates snake_case/accent/special-char, else ''."""
    v = _s(value)
    if not v:
        return ""
    if _has_accent(v):
        return "contém acento"
    if v != v.lower():
        return "não está em snake_case (maiúsculas)"
    deacc = "".join(c for c in unicodedata.normalize("NFKD", v) if unicodedata.category(c) != "Mn")
    if re.search(r"[^0-9a-z_]", deacc):
        return "contém caractere especial ou espaço"
    return ""


def _finding(params, event_type, event_order, field, problem, severity, category, suggestion=""):
    return {
        "screen": params.get("screenName") or params.get("sn") or "",
        "event_type": event_type,
        "event_order": event_order,
        "field": field,
        "problem": problem,
        "severity": severity,
        "category": category,
        "suggestion": suggestion,
    }


def _validate_one(event_type, event_order, params, findings, open_questions):
    def add(field, problem, severity, category, suggestion=""):
        findings.append(_finding(params, event_type, event_order, field, problem, severity, category, suggestion))

    # 1. Completeness (only for the three standard 5.0 event kinds)
    required = REQUIRED_FIELDS.get(event_type)
    if required:
        for f in required:
            if not _s(params.get(f)):
                add(f, "campo obrigatório ausente", "red", "completeness", "preencher o campo obrigatório")

    # 2. Legacy fields + napp in screenName
    for lf in LEGACY_FIELDS:
        if _s(params.get(lf)):
            add(lf, "campo legado descontinuado", "red", "legacy",
                f"migrar {lf} → {_LEGACY_MIGRATION.get(lf, 'campo 5.0 correspondente')}")
    if "napp" in _s(params.get("screenName")).lower():
        add("screenName", "screenName usa 'napp' (descontinuado)", "red", "legacy", "remover 'napp' do screenName")

    # 3. Enums + dynamic-vs-fixed for event
    for field, allowed in ENUMS.items():
        raw = _s(params.get(field))
        if not raw:
            continue
        if field == "event" and is_dynamic(raw):
            add("event", "event não pode ser dinâmico (deve ser fixo)", "red", "dynamic_fixed",
                "usar valor fixo: " + " | ".join(allowed))
            continue
        tokens = _enum_tokens(raw)
        if tokens is None:
            continue  # un-inferable runtime var → handled as open_question below
        bad = [t for t in tokens if t not in allowed]
        if bad:
            add(field, "valor(es) fora do enum: " + ", ".join(bad), "red", "enum",
                "permitidos: " + " | ".join(allowed))

    # 4. Nomenclature (only the free-form snake_case fields the standard governs)
    for field in _NOMENCLATURE_CHECK_FIELDS:
        value = _s(params.get(field))
        if not value or is_dynamic(value):
            continue
        prob = _nomenclature_problem(value)
        if prob:
            add(field, f"nomenclatura: {prob}", "amber", "nomenclature",
                "usar snake_case, sem acento/caractere especial")
    if _s(params.get("screenName")) and not _s(params.get("screenName")).startswith("/"):
        add("screenName", "screenName deve começar com '/'", "amber", "nomenclature", "prefixar com '/'")

    # 5. Conditionals (error / product)
    sj = _s(params.get("status_journey")).lower()
    if "erro" in sj or any(_s(params.get(f)) for f in ERROR_FIELDS):
        missing = [f for f in ERROR_FIELDS if not _s(params.get(f))]
        if missing:
            add(", ".join(missing), "contexto de erro mas faltam: " + ", ".join(missing),
                "amber", "conditional", "preencher os campos error_*")
    if any(_s(params.get(f)) for f in PRODUCT_FIELDS):
        missing = [f for f in PRODUCT_FIELDS if not _s(params.get(f))]
        if missing:
            add(", ".join(missing), "contexto de produto mas faltam: " + ", ".join(missing),
                "amber", "conditional", "preencher plan_name e event_plan_type")

    # 6. event_detail format
    ed = _s(params.get("event_detail"))
    if ed and not is_dynamic(ed) and "_" not in ed:
        add("event_detail", "event_detail deve seguir [acao]_[descricao]", "amber", "event_detail_format",
            "ex.: clique_confirmar_recarga")

    # Open questions: closed-enum fields whose dynamic value can't be inferred
    for field in ENUMS:
        if field == "event":
            continue
        raw = _s(params.get(field))
        if raw and is_dynamic(raw) and _enum_tokens(raw) is None:
            open_questions.append({
                "screen": params.get("screenName") or params.get("sn") or "",
                "field": field,
                "note": f"valor dinâmico de {field} não permite inferir as opções ({raw})",
            })


def validate_events(events):
    """Run the deterministic ruleset over reparse_5_0 events → validation report."""
    if not isinstance(events, list):
        raise ValueError("events must be a list.")
    all_findings = []
    open_questions = []
    verdicts = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        event_type = ev.get("event_type", "")
        event_order = ev.get("event_order")
        params = ev.get("params") or {}
        findings = []
        _validate_one(event_type, event_order, params, findings, open_questions)
        all_findings.extend(findings)
        if any(f["severity"] == "red" for f in findings):
            verdict = "red"
        elif any(f["severity"] == "amber" for f in findings):
            verdict = "amber"
        else:
            verdict = "green"
        verdicts.append((event_type, event_order, params, verdict))

    total = len(verdicts)
    red = sum(1 for *_, v in verdicts if v == "red")
    amber = sum(1 for *_, v in verdicts if v == "amber")
    green = sum(1 for *_, v in verdicts if v == "green")
    approved = [
        {"screen": p.get("screenName") or p.get("sn") or "", "event_type": et, "event_order": eo}
        for et, eo, p, v in verdicts if v == "green"
    ]
    summary = {
        "total": total, "red": red, "amber": amber, "green": green,
        "adherence_pct": round(green / total * 100) if total else 0,
    }
    if total:
        open_questions.append({
            "screen": "", "field": "coerência semântica",
            "note": ("Verificar manualmente se event_detail, component_copy, component_type, "
                     "macro_journey/micro_journey e status_journey coerem com a tela desenhada."),
        })
    return {"summary": summary, "findings": all_findings, "approved": approved,
            "open_questions": open_questions}
