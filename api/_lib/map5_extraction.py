"""Post-process a parse_svg_spec result into clean App 5.0 params per event.

The pinned tagmatch parser finds the cards and keeps the full card text in
raw_lines, but merges multiple parameters into one value (mixing ':' and '='
separators, losing line breaks). We re-split raw_lines by known field-name
boundaries, preserving dynamic `[...]` / option-list values. The pinned package
is not modified.
"""
import re

# Known field names used as split boundaries. Longest first so multi-word names
# (event_detail, event_access_type, event_plan_type) win over their prefixes.
_KNOWN_FIELDS = [
    "event_access_type", "event_plan_type", "event_detail", "event_cnpj", "event_order",
    "screenName", "origin_nv", "client_category", "department", "macro_journey",
    "micro_journey", "status_journey", "component_type", "component_copy",
    "error_status", "error_type", "error_code", "plan_name", "journeyVariant",
    "crm_name", "payment_method", "info_detail", "description", "value",
    "event", "name", "sn", "ct", "ac", "lb",
]
_SORTED = sorted(set(_KNOWN_FIELDS), key=len, reverse=True)
_FIELD_RE = re.compile(r"(?i)(" + "|".join(re.escape(f) for f in _SORTED) + r")\s*[:=]")


def split_params(text):
    """Split merged card text into {field: value}. Markers inside `[...]` are not boundaries."""
    text = str(text or "")
    markers = []
    for m in _FIELD_RE.finditer(text):
        pre = text[:m.start()]
        # a field marker inside an open `[...]` placeholder is part of a value, not a boundary
        if pre.count("[") - pre.count("]") <= 0:
            markers.append((m.start(), m.end(), m.group(1)))
    out = {}
    for i, (start, end, name) in enumerate(markers):
        value_end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        key = name.lower()
        if key not in out:  # first occurrence wins
            out[key] = text[end:value_end].strip()
    return out


_BBOX_KEYS = ("_bbox_x1", "_bbox_y1", "_bbox_x2", "_bbox_y2")


def reparse_5_0(spec):
    """Turn parse_svg_spec records into [{event_type, event_order, bbox, params}]."""
    if not isinstance(spec, list):
        raise ValueError("spec must be a list.")
    out = []
    for e in spec:
        if not isinstance(e, dict):
            continue
        params = split_params(e.get("raw_lines"))
        event_type = params.get("event") or (str(e.get("name")) if e.get("name") is not None else "")
        bbox = {k: e.get(k) for k in _BBOX_KEYS if e.get(k) is not None}
        out.append({
            "event_type": event_type,
            "event_order": e.get("event_order"),
            "bbox": bbox,
            "params": params,
        })
    return out
