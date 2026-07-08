"""Pure business logic for the Query Builder tool.

Wraps the current-generation builders in tagmatch.query_builders (NOT the
legacy tagmatch.query_builder.QueryBuilder). All builders are pure:
df_spec + options -> {"query": SQL, "event_mapping", "metadata", ...}.
User-controlled strings that reach SQL as raw text - the table name and the
dates - are validated here before any builder is called. The custom query
type's own payload (columns, operators, values) is validated inside
api._lib.custom_query.build_custom_query.
"""
import io
import json
import re

import numpy as np
import pandas as pd
from api._lib.custom_query import build_custom_query
from tagmatch.databricks_schema import DEFAULT_SCHEMA_CONFIG, validate_table_name
from tagmatch.query_builders.validation_builder import ValidationQueryBuilder
from tagmatch.query_builders.volumetry_builder import VolumetryQueryBuilder

VALID_QUERY_TYPES = ("validation", "volumetry", "funnel", "custom")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    if isinstance(obj, float) and pd.isna(obj):
        return None
    return obj


def parse_spec_file(filename: str, content: bytes) -> list:
    """Parse a Tool 1 spec download (spec.json or spec.csv) into event records.

    Raises ValueError with a user-readable message on any problem.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "json":
        try:
            data = json.loads(content.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid JSON: {e}")
        if not isinstance(data, list):
            raise ValueError("Spec JSON must be an array of event objects.")
        df = pd.DataFrame(data)
    elif ext == "csv":
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        except Exception as e:
            raise ValueError(f"Invalid CSV: {e}")
    else:
        raise ValueError(f"Unsupported file type '.{ext}'. Upload the spec.json or spec.csv downloaded from Map Extraction.")

    if len(df) == 0:
        raise ValueError("The spec file contains no events.")
    if "name" not in df.columns:
        raise ValueError("The spec file has no 'name' column - is this a Map Extraction output?")

    df = df.fillna("")
    # Normalize event_order to a valid 1-based int. A spec straight from Map
    # Extraction can carry events with no event_order (a null that fillna("")
    # above turned into ""), and every query builder does int(event_order).
    # The builders guard with pd.notna() and fall back to idx+1, but "" is not
    # NaN so that guard is defeated and int("") raises. Backfill the same
    # idx+1 fallback here so every builder receives a clean int.
    if "event_order" not in df.columns:
        df["event_order"] = range(1, len(df) + 1)
    else:
        orders = pd.to_numeric(df["event_order"], errors="coerce")
        df["event_order"] = [int(o) if pd.notna(o) else i + 1 for i, o in enumerate(orders)]

    return _sanitize(df.to_dict(orient="records"))


def _validated_dates(options: dict):
    start_date = options.get("start_date")
    end_date = options.get("end_date")
    if not start_date or not _DATE_RE.match(str(start_date)):
        raise ValueError(f"Invalid or missing start date: '{start_date}'. Use YYYY-MM-DD.")
    if end_date and not _DATE_RE.match(str(end_date)):
        raise ValueError(f"Invalid end date: '{end_date}'. Use YYYY-MM-DD.")
    return str(start_date), (str(end_date) if end_date else None)


def _schema_config(options: dict):
    table_name = options.get("table_name")
    if not table_name:
        return None
    if not validate_table_name(str(table_name)):
        raise ValueError(f"Invalid table name: '{table_name}'.")
    return {**DEFAULT_SCHEMA_CONFIG, "table_name": str(table_name)}


def build_query(events: list, query_type: str, options: dict) -> dict:
    """Route to the right tagmatch builder. Returns {"ok": ...} - never raises for user input."""
    if query_type not in VALID_QUERY_TYPES:
        return {"ok": False, "error": f"Invalid query type '{query_type}'. Must be one of {VALID_QUERY_TYPES}."}

    try:
        start_date, end_date = _validated_dates(options)
        schema_config = _schema_config(options)
        df = pd.DataFrame(events).fillna("")
        count_mode = options.get("count_mode", "session")

        if query_type == "validation":
            builder = ValidationQueryBuilder(schema_config=schema_config)
            result = builder.build_validation_query(
                df,
                start_date,
                end_date=end_date,
                sample_per_event=int(options.get("sample_per_event", 5)),
                count_mode=count_mode,
            )
        elif query_type == "volumetry":
            builder = VolumetryQueryBuilder(schema_config=schema_config)
            result = builder.build_volumetry_query(
                df,
                start_date,
                end_date=end_date,
                group_by=options.get("group_by", "event"),
                include_event_count=bool(options.get("include_event_count", True)),
                count_mode=count_mode,
            )
        elif query_type == "funnel":
            builder = VolumetryQueryBuilder(schema_config=schema_config)
            result = builder.build_funnel_query(
                df,
                start_date,
                end_date=end_date,
                screen_order=options.get("screen_order") or None,
                count_mode=count_mode,
            )
        else:  # custom
            payload = options.get("custom")
            if not isinstance(payload, dict):
                raise ValueError("Missing custom query configuration.")
            result = build_custom_query(
                payload,
                start_date,
                end_date=end_date,
                schema_config=schema_config,
            )
            result = {"query": result["query"], "event_mapping": {}, "metadata": result["metadata"]}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Query generation failed: {e}"}

    return {
        "ok": True,
        "query": result["query"],
        "event_mapping": result.get("event_mapping", {}),
        "metadata": result.get("metadata", {}),
    }
