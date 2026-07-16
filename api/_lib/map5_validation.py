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


def _finding(params, event_type, event_order, field, problem, severity, category, suggestion="", reason=""):
    return {
        "screen": params.get("screenName") or params.get("sn") or "",
        "event_type": event_type,
        "event_order": event_order,
        "field": field,
        "problem": problem,
        "severity": severity,
        "category": category,
        "suggestion": suggestion,
        "reason": reason,
    }


def _validate_one(event_type, event_order, params, findings, open_questions):
    def add(field, problem, severity, category, suggestion="", reason=""):
        findings.append(_finding(params, event_type, event_order, field, problem, severity, category, suggestion, reason))

    # 1. Completeness (only for the three standard 5.0 event kinds)
    required = REQUIRED_FIELDS.get(event_type)
    if required:
        for f in required:
            if not _s(params.get(f)):
                add(f, "campo obrigatório ausente", "red", "completeness",
                    "preencher o campo obrigatório", reason="obrigatório no padrão 5.0")

    # 2. Legacy fields + napp in screenName
    for lf in LEGACY_FIELDS:
        if _s(params.get(lf)):
            target = _LEGACY_MIGRATION.get(lf, "campo 5.0 correspondente")
            add(lf, "campo legado descontinuado", "red", "legacy",
                f"migrar {lf} → {target}", reason=f"campo legado — migrar para {target}")
    if "napp" in _s(params.get("screenName")).lower():
        add("screenName", "screenName usa 'napp' (descontinuado)", "red", "legacy",
            "remover 'napp' do screenName", reason="remover 'napp' do screenName")

    # 3. Enums + dynamic-vs-fixed for event
    for field, allowed in ENUMS.items():
        raw = _s(params.get(field))
        if not raw:
            continue
        if field == "event" and is_dynamic(raw):
            add("event", "event não pode ser dinâmico (deve ser fixo)", "red", "dynamic_fixed",
                "usar valor fixo: " + " | ".join(allowed), reason="deve ser fixo, não dinâmico")
            continue
        tokens = _enum_tokens(raw)
        if tokens is None:
            continue
        bad = [t for t in tokens if t not in allowed]
        if bad:
            add(field, "valor(es) fora do enum: " + ", ".join(bad), "red", "enum",
                "permitidos: " + " | ".join(allowed),
                reason="fora do enum · permitidos: " + ", ".join(allowed))

    # 4. Nomenclature (only the free-form snake_case fields the standard governs)
    for field in _NOMENCLATURE_CHECK_FIELDS:
        value = _s(params.get(field))
        if not value or is_dynamic(value):
            continue
        prob = _nomenclature_problem(value)
        if prob:
            add(field, f"nomenclatura: {prob}", "amber", "nomenclature",
                "usar snake_case, sem acento/caractere especial",
                reason="usar snake_case, sem acento/caractere especial")
    if _s(params.get("screenName")) and not _s(params.get("screenName")).startswith("/"):
        add("screenName", "screenName deve começar com '/'", "amber", "nomenclature",
            "prefixar com '/'", reason='deve começar com "/" (sem napp)')

    # 5. Conditionals (error / product) — one finding per missing field
    sj = _s(params.get("status_journey")).lower()
    if "erro" in sj or any(_s(params.get(f)) for f in ERROR_FIELDS):
        for f in ERROR_FIELDS:
            if not _s(params.get(f)):
                add(f, "campo de erro ausente", "amber", "conditional",
                    "preencher os campos error_*", reason="obrigatório quando há erro")
    if any(_s(params.get(f)) for f in PRODUCT_FIELDS):
        for f in PRODUCT_FIELDS:
            if not _s(params.get(f)):
                add(f, "campo de produto ausente", "amber", "conditional",
                    "preencher plan_name e event_plan_type", reason="obrigatório quando há produto")

    # 6. event_detail format
    ed = _s(params.get("event_detail"))
    if ed and not is_dynamic(ed) and "_" not in ed:
        add("event_detail", "event_detail deve seguir [acao]_[descricao]", "amber", "event_detail_format",
            "ex.: clique_confirmar_recarga", reason="usar formato [acao]_[descricao]")

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


def _worst_by_field(findings):
    """Worst-severity single finding per field (red beats amber)."""
    by = {}
    for f in findings:
        prev = by.get(f["field"])
        if prev is None or (f["severity"] == "red" and prev["severity"] == "amber"):
            by[f["field"]] = f
    return by


def _field_row(field, params, finding, required):
    value = _s(params.get(field))
    if finding is not None:
        status = "missing" if finding["category"] == "completeness" else finding["severity"]
        return {"field": field, "value": value, "status": status, "reason": finding["reason"]}
    if not value:
        return {"field": field, "value": "",
                "status": "missing" if required else "extra",
                "reason": "obrigatório no padrão 5.0" if required else ""}
    return {"field": field, "value": value, "status": "ok" if required else "extra", "reason": ""}


def _event_fields(event_type, params, findings):
    by_field = _worst_by_field(findings)
    rows, seen = [], set()
    for fld in REQUIRED_FIELDS.get(event_type, []):
        seen.add(fld)
        rows.append(_field_row(fld, params, by_field.get(fld), required=True))
    for fld in list(params) + list(by_field):
        if fld in seen:
            continue
        seen.add(fld)
        rows.append(_field_row(fld, params, by_field.get(fld), required=False))
    return rows


def validate_events(events):
    """Run the deterministic ruleset over reparse_5_0 events → validation report."""
    if not isinstance(events, list):
        raise ValueError("events must be a list.")
    all_findings, open_questions, report_events = [], [], []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        event_type = ev.get("event_type", "")
        event_order = ev.get("event_order")
        params = ev.get("params") or {}
        findings = []
        _validate_one(event_type, event_order, params, findings, open_questions)
        all_findings.extend(findings)
        reds = sum(1 for f in findings if f["severity"] == "red")
        ambers = sum(1 for f in findings if f["severity"] == "amber")
        verdict = "red" if reds else ("amber" if ambers else "green")
        report_events.append({
            "event_type": event_type,
            "event_order": event_order,
            "screen": params.get("screenName") or params.get("sn") or "",
            "verdict": verdict,
            "counts": {"red": reds, "amber": ambers},
            "fields": _event_fields(event_type, params, findings),
        })

    total = len(report_events)
    red = sum(1 for e in report_events if e["verdict"] == "red")
    amber = sum(1 for e in report_events if e["verdict"] == "amber")
    green = sum(1 for e in report_events if e["verdict"] == "green")
    approved = [{"screen": e["screen"], "event_type": e["event_type"], "event_order": e["event_order"]}
                for e in report_events if e["verdict"] == "green"]
    summary = {"total": total, "red": red, "amber": amber, "green": green,
               "adherence_pct": round(green / total * 100) if total else 0}
    if total:
        open_questions.append({
            "screen": "", "field": "coerência semântica",
            "note": ("Verificar manualmente se event_detail, component_copy, component_type, "
                     "macro_journey/micro_journey e status_journey coerem com a tela desenhada."),
        })
    return {"summary": summary, "events": report_events, "findings": all_findings,
            "approved": approved, "open_questions": open_questions}
