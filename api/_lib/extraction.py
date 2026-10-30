"""Pure business logic for the Map Extraction tool.

Wraps tagmatch.svg_parser.parse_svg_spec with no filesystem/DB state beyond
a single temp file for the duration of one request.
"""
import os
import tempfile

import numpy as np
import pandas as pd
from tagmatch.config import SUPPORTED_KEYS
from tagmatch.svg_parser import parse_svg_spec
from tagmatch.svg.assembler import assemble_block, generate_metadata, generate_regex_helpers
from tagmatch.svg.reader import read_screen_images, read_text_lines
from tagmatch.svg.screen_associator import associate_screens, is_app_screen

from .map5_extraction import extract_cards_5_0

VALID_MODES = ("header", "card", "hybrid")


def _sanitize(obj):
    """Recursively convert numpy/pandas types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, set):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, float) and pd.isna(obj):
        return None
    return obj


def _structural_records(svg_bytes: bytes) -> list:
    """Spec records built from the SVG's card structure (extract_cards_5_0), assembled
    with the parser's own helpers so they carry the same columns, regexes and spec_id
    as parse_svg_spec rows. A 5.0 card's `screenName` fills `sn` when the card has no
    legacy `sn` (the parser treats screenName as an alias of sn)."""
    try:
        events = extract_cards_5_0(svg_bytes)
    except ValueError:
        return []
    records = []
    for ev in events:
        params = ev["params"]
        lines = [f"{k}: {v}" for k, v in params.items()
                 if k not in ("event", "name") and not (k == "screenName" and "sn" in params)]
        block = assemble_block(ev["event_type"].strip().lower(), lines, header={})
        generate_regex_helpers(block)
        bbox = ev["bbox"]
        generate_metadata(block, {"x": bbox.get("_bbox_x1"), "y": bbox.get("_bbox_y1")})
        # 5.0 fields outside the parser's schema (department, macro_journey, error_code, …)
        # ride along verbatim as extra columns — the map view shows them and the 5.0
        # converter carries them instead of re-deriving.
        for k, v in params.items():
            if k not in ("event", "name", "screenName") and k.lower() not in SUPPORTED_KEYS:
                block[k] = v
        order = ev["event_order"]
        block["event_order"] = float(order) if order is not None else None
        block.update(bbox)
        records.append(block)
    return records


def extract_map(svg_bytes: bytes, mode: str = "card") -> dict:
    """Extract a TagMatch spec from an uploaded Whimsical SVG map.

    Returns {"ok": True, "spec": [...], "report": {...}, "lines": [...]} on success,
    or {"ok": False, "error": "..."} if the SVG can't be parsed. `lines` are the raw
    text lines ({x, y, text}) — consumers (e.g. reparse_5_0) can re-bucket them by event
    bbox when the parser's own KV assembly is unreliable for a map's layout.
    """
    if mode not in VALID_MODES:
        return {
            "ok": False,
            "error": f"Invalid mode '{mode}'. Must be one of {VALID_MODES}.",
        }

    fd, temp_path = tempfile.mkstemp(suffix=".svg")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(svg_bytes)
        df_spec, report = parse_svg_spec(temp_path, mode=mode)
        raw_lines = read_text_lines(temp_path)
        # The base parser misses most cards on some layouts (App 5.0 maps: 1 of ~60).
        # When the SVG's own card structure yields more events, use those instead.
        structural = _structural_records(svg_bytes)
        if len(structural) > len(df_spec):
            screens = [sc for sc in read_screen_images(temp_path) if is_app_screen(sc)]
            df_spec, screen_report = associate_screens(screens, pd.DataFrame(structural))
            report.update(screen_report)
            report["events_extracted"] = len(df_spec)
            report["events_by_type"] = df_spec["name"].value_counts().to_dict()
            report["extraction_source"] = "svg_structure"
    except Exception as e:
        return {"ok": False, "error": f"Failed to parse SVG: {e}"}
    finally:
        os.remove(temp_path)

    records = df_spec.to_dict(orient="records")
    lines = [{"x": ln.get("x"), "y": ln.get("y"), "text": ln.get("text")} for ln in raw_lines]
    return {"ok": True, "spec": _sanitize(records), "report": _sanitize(report), "lines": _sanitize(lines)}
