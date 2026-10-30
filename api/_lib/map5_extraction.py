"""Extract clean App 5.0 params per event from a Whimsical SVG map.

Primary path: extract_cards_5_0 reads each card straight from the SVG's shape structure
(see "Structural card reader" below). Fallback path, for exports without that structure:
reparse_5_0 post-processes a parse_svg_spec result, as described next.

The pinned tagmatch parser finds the cards and keeps the full card text in
raw_lines, but merges multiple parameters into one value (mixing ':' and '='
separators, losing line breaks). We re-split raw_lines by known field-name
boundaries, preserving dynamic `[...]` / option-list values. The pinned package
is not modified.
"""
import re
import xml.etree.ElementTree as ET

from tagmatch.config import SUPPORTED_KEYS

from .taxonomy5 import EVENT_KINDS

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
    "error_status", "error_code", "crm_name", "crmName", "journeyVariant",
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


# --- Structural card reader (Whimsical SVG export) ---------------------------------
#
# Whimsical draws every shape as `<g>` holding the outline `<path>` followed by a
# `<g class="content">` with the shape's text. Each direct child of the content group is
# one paragraph; a paragraph's runs (bold spans, soft-wrapped visual lines) are separate
# `<text>` elements that concatenate back into the original text — the wrap keeps its
# trailing space, so joining runs with "" restores values like `sn: /[napp ou easy]/...`.
# Reading cards this way needs no geometric guessing, so it recovers maps whose layout
# the base parser's card detection misses (App 5.0 maps where it finds 1 card of 60).

_PATH_TOKEN_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_BADGE_RE = re.compile(r"^L\s*(\d+)$", re.IGNORECASE)
_BADGE_MAX_DX = 60    # badge center may sit slightly outside the card's left/right edge
_BADGE_ABOVE = 120    # badge sits on/above the card's top edge
_BADGE_BELOW = 60


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _is_content(el):
    return _local(el.tag) == "g" and el.get("class") == "content"


def _path_bbox(d):
    """Bounding box of a path's endpoints (enough for Whimsical's rounded rects/ellipses)."""
    tokens = _PATH_TOKEN_RE.findall(d or "")
    # args per segment; the current point is the segment's last (x, y) pair
    arity = {"m": 2, "l": 2, "t": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "a": 7, "z": 0}
    x = y = sx = sy = 0.0
    xs, ys = [], []
    cmd, i = None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                x, y = sx, sy
                continue
        if cmd is None:
            break
        n = arity[cmd.lower()]
        args = tokens[i:i + n]
        if len(args) < n:
            break
        try:
            a = [float(t) for t in args]
        except ValueError:
            break
        i += n
        rel = cmd.islower()
        if cmd in "Hh":
            x = x + a[0] if rel else a[0]
        elif cmd in "Vv":
            y = y + a[0] if rel else a[0]
        else:
            ex, ey = a[-2], a[-1]
            x, y = (x + ex, y + ey) if rel else (ex, ey)
        if cmd in "Mm":
            sx, sy = x, y
            cmd = "l" if rel else "L"  # extra M pairs are implicit linetos
        xs.append(x)
        ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _texts(el):
    """`<text>` elements under `el` in document order, not descending into nested content."""
    for child in el:
        if _is_content(child):
            continue
        if _local(child.tag) == "text":
            yield child
        else:
            yield from _texts(child)


def _read_shapes(root):
    """[{fill, bbox, paragraphs}] for every shape with text, in document order."""
    parent = {c: p for p in root.iter() for c in p}
    shapes = []
    for content in root.iter():
        if not _is_content(content):
            continue
        paragraphs, xs, ys = [], [], []
        for para in content:
            runs = []
            for t in _texts(para):
                runs.append("".join(t.itertext()))
                for ts in [t, *t]:
                    try:
                        xs.append(float(ts.get("x")))
                        ys.append(float(ts.get("y")))
                    except (TypeError, ValueError):
                        pass
            # a manual line break (Shift+Enter) is exported as a `\n` run inside the
            # paragraph; each line it separates starts a field of its own
            for line in "".join(runs).split("\n"):
                if line.strip():
                    paragraphs.append(line.strip())
        if not paragraphs:
            continue
        outline = next((c for c in parent.get(content, []) if _local(c.tag) == "path"), None)
        bbox = _path_bbox(outline.get("d")) if outline is not None else None
        if bbox is None and xs:
            bbox = (min(xs), min(ys), max(xs), max(ys))
        shapes.append({
            "fill": outline.get("data-fill") if outline is not None else None,
            "bbox": bbox,
            "paragraphs": paragraphs,
        })
    return shapes


def _badge_order(card_bbox, badges, used):
    """event_order from the nearest unused `L<n>` badge sitting on the card's top edge."""
    x1, y1, x2, _ = card_bbox
    best = None  # (distance, index, order)
    for i, (bx, by, order) in enumerate(badges):
        if i in used:
            continue
        if not (x1 - _BADGE_MAX_DX <= bx <= x2 + _BADGE_MAX_DX and y1 - _BADGE_ABOVE <= by <= y1 + _BADGE_BELOW):
            continue
        dist = abs(by - y1) + abs(bx - min(max(bx, x1), x2))
        if best is None or dist < best[0]:
            best = (dist, i, order)
    if best is None:
        return None
    used.add(best[1])
    return best[2]


_LEADING_FIELD_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(.*)$", re.DOTALL)


def card_params(paragraphs):
    """{field: value} from a card's paragraphs. A paragraph that opens with `field:`/`field=`
    starts a field even when the name is not in the known vocabulary (so it is not swallowed
    into the previous value); a paragraph with no leading field continues the previous one."""
    out, last = {}, None
    for para in paragraphs:
        m = _FIELD_RE.match(para.lstrip())
        if m:
            parsed = split_params(para)
        else:
            g = _LEADING_FIELD_RE.match(para)
            parsed = {g.group(1): g.group(2).strip()} if g else {}
        if not parsed:
            if last is not None:
                out[last] = f"{out[last]} {para}".strip()
            continue
        for key, value in parsed.items():
            if key not in out:  # first occurrence wins
                out[key] = value
            last = key
    return out


def _is_template(params, order):
    """Legend/example card: no badge and every value (besides the kind) is a placeholder."""
    values = [v for k, v in params.items() if k not in ("event", "name")]
    return order is None and bool(values) and all("[" in v for v in values)


def extract_cards_5_0(svg_bytes):
    """Read App 5.0 events straight from the SVG's shape structure.

    Returns [{event_type, event_order, bbox, params}] (same shape as reparse_5_0). A shape
    is an event when it names a known event kind (`event:` or legacy `name:`), or carries
    at least two taxonomy fields — so annotation notes that mention one field are dropped.
    Legend/example cards (no `L<n>` badge, every value a placeholder) are dropped too.
    Raises ValueError when the bytes are not parseable SVG/XML.
    """
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse SVG: {e}") from e
    shapes = _read_shapes(root)

    badges = []
    for s in shapes:
        m = _BADGE_RE.match(s["paragraphs"][0]) if len(s["paragraphs"]) == 1 else None
        if m and s["bbox"]:
            x1, y1, x2, y2 = s["bbox"]
            badges.append(((x1 + x2) / 2, (y1 + y2) / 2, int(m.group(1))))

    events = []
    for s in shapes:
        params = card_params(s["paragraphs"])
        event_type = params.get("event") or params.get("name") or ""
        signals = sum(1 for f in _EVENT_SIGNAL_FIELDS if f in params)
        if event_type.strip().lower() not in EVENT_KINDS and signals < 2:
            continue
        events.append((s, event_type, params))

    used = set()
    out = []
    # claim badges top-down so a card never steals the badge of the card right above it
    for s, event_type, params in sorted(events, key=lambda e: (e[0]["bbox"] or (0, 0, 0, 0))[1]):
        order = _badge_order(s["bbox"], badges, used) if s["bbox"] else None
        if _is_template(params, order):
            continue
        bbox = dict(zip(_BBOX_KEYS, s["bbox"])) if s["bbox"] else {}
        out.append({"event_type": event_type, "event_order": order, "bbox": bbox, "params": params})
    out.sort(key=lambda e: (e["event_order"] is None, e["event_order"] or 0,
                            e["bbox"].get("_bbox_y1", 0), e["bbox"].get("_bbox_x1", 0)))
    return out
