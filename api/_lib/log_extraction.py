"""Pure business logic for the Log Extraction tool.

Wraps tagmatch.log.utils.parse_logs_with_format with no filesystem/DB state
beyond one temp file per uploaded file, for the duration of one request.
Multi-file batches are concatenated, sorted by ts, and deduplicated using
the same hash key the full TagMatch platform uses
(ui/api/services/log_service.py: calculate_row_hash).
"""
import hashlib
import math
import os
import tempfile

import numpy as np
import pandas as pd
from tagmatch.log.utils import parse_logs_with_format

VALID_FORMATS = ("auto", "logcat", "ndjson", "dev_json", "firebase_javascript")
ALLOWED_EXTENSIONS = ("txt", "log", "json", "ndjson")


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


def _row_hash(row: dict) -> str:
    """Same dedup key as the full platform's calculate_row_hash (ui/api/services/log_service.py)."""
    ts = row.get("ts", 0)
    if ts is None or ts == "":
        ts = 0
    elif isinstance(ts, float) and math.isnan(ts):
        ts = 0
    else:
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            ts = 0

    sn = str(row.get("screenName", "") or "")
    ct = str(row.get("eventCategory", "") or "")
    ac = str(row.get("eventAction", "") or "")
    lb = str(row.get("eventLabel", "") or "")

    key = f"{row.get('origin', '')}|{row.get('name_norm', '')}|{int(ts)}|{sn}|{ct}|{ac}|{lb}"
    return hashlib.md5(key.encode()).hexdigest()


def extract_logs(files: list, format: str = "auto", tz: str = "America/Sao_Paulo") -> dict:
    """Extract and merge events from one or more uploaded log files.

    Args:
        files: list of (filename, content_bytes) tuples, in upload order.
        format: "auto" or one of VALID_FORMATS to force a parser for all files.
        tz: timezone for logcat/firebase_javascript timestamp parsing.

    Returns {"ok": True, "logs": [...], "report": {...}} on success (including
    the case where every file parses cleanly but yields zero events), or
    {"ok": False, "error": "..."} if no file could be parsed at all.
    """
    if format not in VALID_FORMATS:
        return {"ok": False, "error": f"Invalid format '{format}'. Must be one of {VALID_FORMATS}."}

    if not files:
        return {"ok": False, "error": "No files provided."}

    frames = []
    file_reports = []

    for idx, (filename, content) in enumerate(files):
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            file_reports.append(
                {
                    "filename": filename,
                    "detected_format": None,
                    "row_count": 0,
                    "error": f"Unsupported extension '.{ext}'. Must be one of {ALLOWED_EXTENSIONS}.",
                }
            )
            continue

        fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            df, detected_format = parse_logs_with_format(temp_path, format=format, tz=tz)
        except Exception as e:
            file_reports.append(
                {"filename": filename, "detected_format": None, "row_count": 0, "error": f"Failed to parse: {e}"}
            )
            continue
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        df["source_file_idx"] = idx
        df["source_filename"] = filename
        frames.append(df)
        file_reports.append(
            {"filename": filename, "detected_format": detected_format, "row_count": len(df), "error": None}
        )

    if not frames:
        errors = "; ".join(f"{r['filename']}: {r['error']}" for r in file_reports)
        return {"ok": False, "error": f"No log file could be parsed. {errors}"}

    df_all = pd.concat(frames, ignore_index=True)
    df_all["ts"] = pd.to_numeric(df_all["ts"], errors="coerce")
    df_all = df_all.sort_values(by="ts", na_position="last", kind="stable").reset_index(drop=True)

    total_events = len(df_all)
    rows = df_all.to_dict(orient="records")
    seen_hashes = set()
    unique_rows = []
    for row in rows:
        h = _row_hash(row)
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_rows.append(row)

    unique_events = len(unique_rows)
    duplicates_removed = total_events - unique_events

    df_unique = pd.DataFrame(unique_rows)
    events_by_type = (
        df_unique["name_norm"].value_counts().to_dict()
        if len(df_unique) > 0 and "name_norm" in df_unique.columns
        else {}
    )
    events_by_origin = (
        df_unique["origin"].value_counts().to_dict()
        if len(df_unique) > 0 and "origin" in df_unique.columns
        else {}
    )

    report = {
        "total_events": total_events,
        "unique_events": unique_events,
        "duplicates_removed": duplicates_removed,
        "events_by_type": events_by_type,
        "events_by_origin": events_by_origin,
        "files": file_reports,
    }

    return {"ok": True, "logs": _sanitize(unique_rows), "report": _sanitize(report)}
