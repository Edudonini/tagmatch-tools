"""Post-process a parse_svg_spec result into clean App 5.0 params per event.

The pinned tagmatch parser finds the cards and keeps the full card text in
raw_lines, but merges multiple parameters into one value (mixing ':' and '='
separators, losing line breaks). We re-split raw_lines by known field-name
boundaries, preserving dynamic `[...]` / option-list values. The pinned package
is not modified.
"""
import re

from tagmatch.config import SUPPORTED_KEYS

# Field names used as split boundaries. The pinned parser recognizes SUPPORTED_KEYS
# (title, module_name, position, tag_label, component_*, …) as fields when parsing KV
# pairs, so the re-parser must treat every one of them as a boundary — otherwise an
# unrecognized field collapses into the previous field's value. Deriving from
# SUPPORTED_KEYS keeps the re-parser's vocabulary in lockstep with the parser.
#
# App 5.0 additionally uses these fields, which are NOT in SUPPORTED_KEYS (the base
# parser merges them into adjacent values); the re-parser must still split them.
_EXTRA_5_0_FIELDS = [
    "event", "screenName", "event_access_type", "event_plan_type", "event_detail",
    "event_order", "department", "macro_journey", "micro_journey", "status_journey",
    "error_status", "error_code", "crm_name", "journeyVariant",
]
_KNOWN_FIELDS = [*SUPPORTED_KEYS, *_EXTRA_5_0_FIELDS]
# dedup preserving first-seen order, then stable-sort longest-first, so the
# boundary precedence is deterministic even between same-length field names.
_SORTED = sorted(dict.fromkeys(_KNOWN_FIELDS), key=len, reverse=True)
_FIELD_RE = re.compile(r"(?i)(" + "|".join(re.escape(f) for f in _SORTED) + r")\s*[:=]")
# Deliberately no `\b` before the alternation: on merged cards a field name is
# glued directly to the previous value with no boundary (e.g. `comercialmacro_journey=`),
# so a word boundary would miss exactly the merges this re-parser exists to split.
# Map each matched token (matched case-insensitively, and the base parser may have
# lowercased it) back to the canonical field name, so keys keep their taxonomy casing
# (`screenName`, `journeyVariant`) for display and downstream field/enum matching.
_CANONICAL = {f.lower(): f for f in _KNOWN_FIELDS}


def split_params(text):
    """Split merged card text into {field: value}. Markers inside `[...]` are not boundaries."""
    text = str(text or "")
    markers = []
    for m in _FIELD_RE.finditer(text):
        pre = text[:m.start()]
        # A field marker inside an open `[...]` placeholder is part of a value, not a
        # boundary. A stray `]` yields a negative depth (still <= 0 → treated as a
        # boundary, correct). An unmatched `[` leaves depth > 0 and swallows the rest of
        # the card into the current value — a malformed card the Phase-2 validator flags.
        if pre.count("[") - pre.count("]") <= 0:
            markers.append((m.start(), m.end(), m.group(1)))
    out = {}
    for i, (start, end, name) in enumerate(markers):
        value_end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        key = _CANONICAL.get(name.lower(), name.lower())
        if key not in out:  # first occurrence wins
            out[key] = text[end:value_end].strip()
    return out


_BBOX_KEYS = ("_bbox_x1", "_bbox_y1", "_bbox_x2", "_bbox_y2")

# A card is a real event only if it carries at least one of these taxonomy fields
# (OR filter). Scratch/placeholder cards (e.g. only a legacy `sn` with junk text) are
# dropped. `sn`/`ct`/`ac`/`lb` are deliberately NOT signals — a legacy-only card is noise.
_EVENT_SIGNAL_FIELDS = frozenset({
    "event", "screenName", "origin_nv", "event_access_type", "client_category",
    "department", "macro_journey", "micro_journey", "event_detail", "status_journey",
    "component_type", "component_copy", "event_cnpj", "info_detail", "module_name",
    "position", "tag_label", "plan_name", "event_plan_type", "error_type", "error_status",
})


def _bucket_lines_by_bbox(spec, lines):
    """Assign each text line to the tightest event bbox that contains it, returning
    {spec_index: [line_text, ...]} y-sorted. The base parser's KV assembly mangles
    raw_lines on some layouts, but its line reading and card bboxes are correct — so we
    re-derive each event's text from the raw lines it geometrically contains."""
    boxes = []  # (index, x1, y1, x2, y2, area)
    for i, e in enumerate(spec):
        if not isinstance(e, dict):
            continue
        vals = [e.get(k) for k in _BBOX_KEYS]
        if any(v is None for v in vals):
            continue
        try:
            x1, y1, x2, y2 = (float(v) for v in vals)
        except (TypeError, ValueError):
            continue
        boxes.append((i, x1, y1, x2, y2, (x2 - x1) * (y2 - y1)))
    buckets = {}
    for ln in lines or []:
        if not isinstance(ln, dict):
            continue
        text = str(ln.get("text") or "")
        if not text.strip():
            continue
        try:
            lx, ly = float(ln.get("x")), float(ln.get("y"))
        except (TypeError, ValueError):
            continue
        best = None  # (index, area)
        for (i, x1, y1, x2, y2, area) in boxes:
            if x1 <= lx <= x2 and y1 <= ly <= y2 and (best is None or area < best[1]):
                best = (i, area)
        if best is not None:
            buckets.setdefault(best[0], []).append((ly, text))
    return {i: [t for _, t in sorted(v)] for i, v in buckets.items()}


def reparse_5_0(spec, lines=None):
    """Turn parse_svg_spec records into [{event_type, event_order, bbox, params}].

    When `lines` (the raw text lines from extract_map) is given, each event's params are
    re-derived from the lines inside its bbox (robust against the base parser's KV-assembly
    mangling); otherwise the base parser's `raw_lines` is used. Scratch/placeholder cards
    that carry no real taxonomy field are dropped.
    """
    if not isinstance(spec, list):
        raise ValueError("spec must be a list.")
    line_buckets = _bucket_lines_by_bbox(spec, lines) if lines else None
    out = []
    for i, e in enumerate(spec):
        if not isinstance(e, dict):
            continue
        if line_buckets is not None and line_buckets.get(i):
            params = split_params("\n".join(line_buckets[i]))
        else:
            params = split_params(e.get("raw_lines"))
        if not any(f in params for f in _EVENT_SIGNAL_FIELDS):
            continue  # noise / placeholder card, not a real event
        event_type = params.get("event") or (str(e.get("name")) if e.get("name") is not None else "")
        bbox = {k: e.get(k) for k in _BBOX_KEYS if e.get(k) is not None}
        out.append({
            "event_type": event_type,
            "event_order": e.get("event_order"),
            "bbox": bbox,
            "params": params,
        })
    return out
