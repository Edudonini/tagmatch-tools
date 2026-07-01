"""Pure business logic for the Map Extraction tool.

Wraps tagmatch.svg_parser.parse_svg_spec with no filesystem/DB state beyond
a single temp file for the duration of one request.
"""
import os
import tempfile

import numpy as np
import pandas as pd
from tagmatch.svg_parser import parse_svg_spec

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


def extract_map(svg_bytes: bytes, mode: str = "card") -> dict:
    """Extract a TagMatch spec from an uploaded Whimsical SVG map.

    Returns {"ok": True, "spec": [...], "report": {...}} on success,
    or {"ok": False, "error": "..."} if the SVG can't be parsed.
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
    except Exception as e:
        return {"ok": False, "error": f"Failed to parse SVG: {e}"}
    finally:
        os.remove(temp_path)

    records = df_spec.to_dict(orient="records")
    return {"ok": True, "spec": _sanitize(records), "report": _sanitize(report)}
