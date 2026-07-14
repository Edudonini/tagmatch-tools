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
COMPONENT_TYPE = ("button", "link", "card", "modal", "toggle", "checkbox", "banner", "video", "dropdown")
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


def _journey_segment(sn):
    segs = [p for p in str(sn or "").split("/") if p and p.lower() != "napp"]
    return segs[0] if segs else ""


def derive_screen_name(sn, screen_name, screen_description):
    """/{journey}/{tela}, kebab, no napp. tela seeded from the map's screen."""
    journey = _kebab(_journey_segment(sn))
    tela = _kebab(screen_name or screen_description or "")
    if journey and tela:
        return f"/{journey}/{tela}"
    if journey:
        return f"/{journey}/"
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
    if re.search(r"err", str(ac or ""), re.I):
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


def convert_event(ev):
    if not isinstance(ev, dict):
        ev = {}
    name = str(ev.get("name") or "").strip()
    sn, ct, ac, lb = ev.get("sn"), ev.get("ct"), ev.get("ac"), ev.get("lb")
    kind = name
    acao = _ACAO.get(kind, "visualizacao")
    has_error = _detect_error(ac, lb)

    fields = {}
    fields["event"] = _f(name, "auto" if name in EVENT_KINDS else "review")
    fields["screenName"] = _f(derive_screen_name(sn, ev.get("screen_name"), ev.get("screen_description")), "review")
    fields["origin_nv"] = _f("", "manual")
    at_val, at_conf = _access_type_from_ct(ct)
    fields["event_access_type"] = _f(at_val, at_conf)
    fields["client_category"] = _f("", "manual")
    fields["department"] = _f("", "manual")
    fields["macro_journey"] = _f(normalize(_journey_segment(sn)), "review")
    fields["micro_journey"] = _f(normalize(ev.get("screen_description")), "review")
    fields["event_detail"] = _f(_event_detail(acao, lb, ac), "review")
    # status_journey is derived (auto) for error events, else left for the analyst.
    fields["status_journey"] = _f("erro", "auto") if has_error else _f("", "manual")

    if kind in ("interaction", "noninteraction"):
        ctype = _component_type_from_ac(ac)
        fields["component_type"] = _f(ctype, "auto" if ctype else "manual")
        fields["component_copy"] = _f(normalize(_lb_text(lb)), "review")

    if has_error:
        es_val, es_conf = _error_status_from_lb(lb)
        fields["error_status"] = _f(es_val, es_conf)
        fields["error_type"] = _f("", "manual")
        fields["error_code"] = _f("", "manual")

    return {
        "event_kind": kind,
        "event_order": ev.get("event_order"),
        "has_error": has_error,
        "has_product": False,
        "fields": fields,
    }


def convert_events(events):
    """Convert a list of App 4 event rows to App 5.0. Raises ValueError on bad input."""
    if not isinstance(events, list):
        raise ValueError("events must be a list.")
    return [convert_event(ev) for ev in events]
