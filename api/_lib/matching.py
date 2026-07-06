"""Pure business logic for the Matching tool.

Wraps tagmatch.matching.matcher.match_spec_vs_logs (imported via the leaf
module to avoid pulling the whole tagmatch package). Both inputs are the
direct outputs of the Map Extraction (spec) and Log Extraction (logs)
tools - no adapter, only shape conversion (records -> DataFrame -> records).
"""
import io
import json

import numpy as np
import pandas as pd
from tagmatch.matching.matcher import match_spec_vs_logs


def _sanitize(obj):
    """Recursively convert numpy/pandas types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
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


def parse_records(filename: str, content: bytes) -> list:
    """Parse a spec or logs file (JSON array or CSV) into records.

    Raises ValueError with a user-readable message on any problem.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "json":
        try:
            data = json.loads(content.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid JSON: {e}")
        if not isinstance(data, list):
            raise ValueError("File must be a JSON array of records.")
        df = pd.DataFrame(data)
    elif ext == "csv":
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        except Exception as e:
            raise ValueError(f"Invalid CSV: {e}")
    else:
        raise ValueError(f"Unsupported file type '.{ext}'. Upload a .json or .csv file.")

    df = df.fillna("")
    return _sanitize(df.to_dict(orient="records"))


def run_matching(spec_file: tuple, logs_file: tuple) -> dict:
    """Match an extracted spec against extracted logs.

    Each arg is a (filename, content_bytes) tuple. Returns
    {"ok": True, "matches", "extras", "summary"} or {"ok": False, "error"}.
    Never raises for user-input problems.
    """
    try:
        spec_records = parse_records(spec_file[0], spec_file[1])
        logs_records = parse_records(logs_file[0], logs_file[1])
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    if len(spec_records) == 0:
        return {"ok": False, "error": "The spec file contains no events."}
    if not isinstance(spec_records[0], dict):
        return {"ok": False, "error": "The spec file must be an array of event objects."}
    if "name" not in spec_records[0]:
        return {"ok": False, "error": "The spec file has no 'name' field - is this a Map Extraction output?"}

    try:
        df_spec = pd.DataFrame(spec_records)
        df_logs = pd.DataFrame(logs_records)
        df_matches, df_extras, summary = match_spec_vs_logs(df_spec, df_logs)
    except Exception as e:
        return {"ok": False, "error": f"Matching failed: {e}"}

    return {
        "ok": True,
        "matches": _sanitize(df_matches.to_dict(orient="records")),
        "extras": _sanitize(df_extras.to_dict(orient="records")),
        "summary": _sanitize(summary),
    }
