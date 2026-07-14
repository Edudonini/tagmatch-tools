"""App 4 -> App 5.0 taxonomy converter (pure logic, no I/O).

Source of truth: the App 5.0 taxonomy guide (public/taxonomia.html).
Every 5.0 value is snake_case + ASCII, except screenName (kebab path) and
error_code (raw). Derivation is context-free; the journey-context form is
applied on the frontend.
"""
import re
import unicodedata

# --- enums (verbatim from the guide) ---
EVENT_KINDS = ("screen_view", "interaction", "noninteraction")
ORIGIN_NV = ("home", "menu", "push", "deeplink", "fluxo-interno")
EVENT_ACCESS_TYPE = ("vivo", "b2c", "b2b_m", "b2b_c")
CLIENT_CATEGORY = ("adm_prin", "adm", "tec", "cob", "soc", "b2c_not_apply", "vivo_not_apply")
STATUS_JOURNEY = ("intencao", "sucesso", "erro", "progresso", "excecao")
# Union of the /taxonomia page's list and the detailed guide's list, so no valid
# value (incl. the page's `alert`/`input`) is ever unselectable.
COMPONENT_TYPE = ("button", "card", "link", "alert", "banner", "input", "modal", "toggle", "checkbox", "video", "dropdown")
ERROR_STATUS = ("bloqueado", "continuar")
ERROR_TYPE = ("usuario", "negocio", "aplicativo")
EVENT_PLAN_TYPE = ("pre", "pos", "controle", "fixa", "easy", "movel_corporativo", "fixo_corporativo")

_ACAO = {"screen_view": "visualizacao", "noninteraction": "visualizacao", "interaction": "clique"}


def _strip_accents(text):
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text):
    """snake_case, ASCII, no special chars; '' for falsy input."""
    if text is None:
        return ""
    s = _strip_accents(text).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _kebab(text):
    if text is None:
        return ""
    s = _strip_accents(text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


_SN_PREFIXES = {"napp", "easy"}


def _sn_segments(sn):
    """The meaningful path segments of an old sn, minus the napp/easy prefix."""
    return [p for p in str(sn or "").split("/") if p and p.lower() not in _SN_PREFIXES]


def _journey_segment(sn):
    segs = _sn_segments(sn)
    return segs[0] if segs else ""


def derive_screen_name(sn, screen_name, screen_description):
    """Kebab path from the FULL old sn (all segments, no napp/easy). A single-segment
    sn (just the journey) is completed with the map's screen as the tela."""
    segs = [s for s in (_kebab(p) for p in _sn_segments(sn)) if s]
    if len(segs) >= 2:
        return "/" + "/".join(segs)
    if len(segs) == 1:
        tela = _kebab(screen_name or screen_description or "")
        return f"/{segs[0]}/{tela}" if tela else f"/{segs[0]}/"
    return ""


def _access_type_from_ct(ct):
    c = str(ct or "").lower()
    if c.startswith("b2c"):
        return "b2c", "auto"
    if c.startswith("b2b"):
        return "b2b_m", "review"
    if c.startswith("vivo"):
        return "vivo", "auto"
    return "", "manual"


def _component_type_from_ac(ac):
    # If ac mentions more than one component word, the first in COMPONENT_TYPE
    # order wins (rare; the analyst can correct it — this is a "review" seed).
    a = str(ac or "").lower()
    for ctype in COMPONENT_TYPE:
        if ctype in a:
            return ctype
    return ""


def _detect_error(ac, lb):
    if re.search(r"erro", str(ac or ""), re.I):  # matches "erro" and "error"
        return True
    if re.search(r"&\s*(blocker|nonblocker)\s*&", str(lb or ""), re.I):
        return True
    return False


def _error_status_from_lb(lb):
    m = re.search(r"&\s*(blocker|nonblocker)\s*&", str(lb or ""), re.I)
    if not m:
        return "", "manual"
    return ("bloqueado", "auto") if m.group(1).lower() == "blocker" else ("continuar", "auto")


def _lb_text(lb):
    """The human-facing part of lb. Error labels are `app&[blocker|nonBlocker]&message`;
    return the message so component_copy/event_detail aren't seeded with the noisy prefix."""
    s = str(lb or "")
    m = re.search(r"&\s*(?:blocker|nonblocker)\s*&(.*)$", s, re.I)
    return m.group(1) if m else s


def _event_detail(acao, lb, ac):
    desc = normalize(_lb_text(lb)) or normalize(ac)
    return f"{acao}_{desc}" if desc else acao


def _f(value, confidence):
    return {"value": value, "confidence": confidence}


# Legacy fields renamed/removed by the migration (never carried through as-is).
_LEGACY = {"name", "sn", "ct", "ac", "lb"}
# Map/derivation metadata — used to derive, never emitted as a 5.0 field.
_META = {"screen_name", "screen_description", "event_order", "spec_id", "raw_lines",
         "confidence_score", "trigger", "bbox", "svg_bbox"}


def _carryable(key):
    return (key not in _LEGACY and key not in _META
            and not key.startswith("_") and not key.endswith("_regex"))


def _old(ev, key):
    """Trimmed string value of an old-event field, or '' if absent."""
    v = ev.get(key)
    return str(v).strip() if v is not None else ""


def convert_event(ev):
    if not isinstance(ev, dict):
        ev = {}
    name = str(ev.get("name") or "").strip()
    sn, ct, ac, lb = ev.get("sn"), ev.get("ct"), ev.get("ac"), ev.get("lb")
    kind = name
    acao = _ACAO.get(kind, "visualizacao")
    has_error = _detect_error(ac, lb)

    fields = {}
    # --- base fields: derived, but the old event's own value wins when present ---
    fields["event"] = _f(name, "auto" if name in EVENT_KINDS else "review")
    fields["screenName"] = _f(derive_screen_name(sn, ev.get("screen_name"), ev.get("screen_description")), "review")
    fields["origin_nv"] = _f(_old(ev, "origin_nv"), "review" if _old(ev, "origin_nv") else "manual")
    if _old(ev, "event_access_type"):
        fields["event_access_type"] = _f(_old(ev, "event_access_type"), "review")
    else:
        at_val, at_conf = _access_type_from_ct(ct)
        fields["event_access_type"] = _f(at_val, at_conf)
    fields["client_category"] = _f(_old(ev, "client_category"), "review" if _old(ev, "client_category") else "manual")
    fields["department"] = _f(_old(ev, "department"), "review" if _old(ev, "department") else "manual")
    jv = _old(ev, "journeyVariant")
    fields["macro_journey"] = _f(normalize(jv) if jv else normalize(_journey_segment(sn)), "review")
    fields["micro_journey"] = _f(_old(ev, "micro_journey") or normalize(ev.get("screen_description")), "review")
    fields["event_detail"] = _f(_old(ev, "event_detail") or _event_detail(acao, lb, ac), "review")
    if has_error:
        fields["status_journey"] = _f("erro", "auto")
    else:
        fields["status_journey"] = _f(_old(ev, "status_journey"), "review" if _old(ev, "status_journey") else "manual")

    if kind in ("interaction", "noninteraction"):
        if _old(ev, "component_type"):
            fields["component_type"] = _f(_old(ev, "component_type"), "review")
        else:
            ctype = _component_type_from_ac(ac)
            fields["component_type"] = _f(ctype, "auto" if ctype else "manual")
        fields["component_copy"] = _f(_old(ev, "component_copy") or normalize(_lb_text(lb)), "review")

    if has_error:
        es_val, es_conf = _error_status_from_lb(lb)
        fields["error_status"] = _f(_old(ev, "error_status") or es_val,
                                    "review" if _old(ev, "error_status") else es_conf)
        fields["error_type"] = _f(_old(ev, "error_type"), "review" if _old(ev, "error_type") else "manual")
        fields["error_code"] = _f(_old(ev, "error_code"), "review" if _old(ev, "error_code") else "manual")

    # --- product disambiguation: present when the old event carries a plan field;
    # carry the old value, else a dynamic placeholder filled in the metrics map ---
    has_product = bool(_old(ev, "plan_name") or _old(ev, "event_plan_type"))
    if has_product:
        fields["plan_name"] = _f(_old(ev, "plan_name") or "[nome_do_plano]", "review")
        fields["event_plan_type"] = _f(_old(ev, "event_plan_type") or "[tipo_do_plano]", "review")

    # --- passthrough: any other old field not already mapped is carried through ---
    for k, v in ev.items():
        if _carryable(k) and k not in fields:
            fields[k] = _f(str(v).strip() if v is not None else "", "review")

    return {
        "event_kind": kind,
        "event_order": ev.get("event_order"),
        "has_error": has_error,
        "has_product": has_product,
        "fields": fields,
    }


def convert_events(events):
    """Convert a list of App 4 event rows to App 5.0. Raises ValueError on bad input."""
    if not isinstance(events, list):
        raise ValueError("events must be a list.")
    return [convert_event(ev) for ev in events]
