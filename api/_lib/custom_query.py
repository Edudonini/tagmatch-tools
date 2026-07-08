"""Self-contained SQL generator for the Custom query type (visual query builder).

Builds Databricks SQL directly from a structured query payload, independent of
the tagmatch CustomQueryBuilder (which can only filter by a spec's own values).
Every column name is validated against an allow-list of known Silver columns,
every operator against a whitelist, and every value is escaped or numerically
validated before it reaches SQL. Validation failures raise ValueError with a
user-readable message; the generator never emits unsafe SQL.
"""
import re

from tagmatch.databricks_schema import DEFAULT_SCHEMA_CONFIG
from tagmatch.query_builders.utils import escape_sql_string

# Allowed Silver columns: schema column_mapping values plus the fixed columns
# the mapping omits. Any column not in this set is rejected before it reaches SQL.
ALLOWED_COLUMNS = frozenset(DEFAULT_SCHEMA_CONFIG["column_mapping"].values()) | {
    "event_name", "eventCategory", "eventAction", "eventLabel", "screenName",
    "ga_session_id", "data", "event_timestamp", "previousScreenName",
}

OUTPUT_MODES = ("count_sessions", "count_events", "extract")
MATCH_MODES = ("and", "or")

DEFAULT_EXTRACT_COLUMNS = ("data", "event_timestamp", "event_name", "screenName", "ga_session_id")
DEFAULT_LIMIT = 1000
MAX_LIMIT = 10000

_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")

_NO_VALUE_OPS = ("is_empty", "is_not_empty")
_NUMERIC_OPS = ("gt", "lt", "gte", "lte")
_NUMERIC_SQL = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<="}
_ALL_OPS = (
    "eq", "neq", "contains", "starts_with", "regex",
    "gt", "lt", "gte", "lte", "in", "is_empty", "is_not_empty",
)


def _validate_column(column):
    if not isinstance(column, str) or column not in ALLOWED_COLUMNS:
        raise ValueError(f"Unknown column: '{column}'.")
    return column


def _quote(value):
    """Escape a string for a Databricks SQL literal.

    escape_sql_string only doubles single quotes; Databricks (Spark, default
    escapedStringLiterals=false) also treats backslash as a string-literal
    escape char, so a raw backslash must be doubled before quoting or a
    trailing backslash would consume the closing quote and break out.
    """
    return escape_sql_string(value.replace("\\", "\\\\"))


def _escape_like(value):
    """Escape LIKE wildcards so a literal % or _ in the value is not a wildcard.

    Databricks/Spark SQL LIKE treats backslash as the default escape character.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _compile_condition(cond):
    """Compile one {column, op, value} into a SQL boolean expression, or raise ValueError."""
    if not isinstance(cond, dict):
        raise ValueError("Each condition must be an object.")
    column = _validate_column(cond.get("column"))
    op = cond.get("op")
    if op not in _ALL_OPS:
        raise ValueError(f"Unknown operator: '{op}'.")
    value = cond.get("value", "")

    if op in _NO_VALUE_OPS:
        if op == "is_empty":
            return f"({column} IS NULL OR {column} = '')"
        return f"({column} IS NOT NULL AND {column} <> '')"

    if op in _NUMERIC_OPS:
        sval = str(value).strip()
        if not _NUMERIC_RE.match(sval):
            raise ValueError(f"Operator '{op}' on '{column}' needs a numeric value, got '{value}'.")
        return f"{column} {_NUMERIC_SQL[op]} {sval}"

    if op == "in":
        parts = [p.strip() for p in str(value).split(",") if p.strip()]
        if not parts:
            raise ValueError(f"Operator 'in' on '{column}' needs at least one value.")
        escaped = ", ".join(_quote(p) for p in parts)
        return f"{column} IN ({escaped})"

    sval = str(value)
    if op == "eq":
        return f"{column} = {_quote(sval)}"
    if op == "neq":
        return f"{column} <> {_quote(sval)}"
    if op == "contains":
        return f"{column} LIKE {escape_sql_string('%' + _escape_like(sval) + '%')}"
    if op == "starts_with":
        return f"{column} LIKE {escape_sql_string(_escape_like(sval) + '%')}"
    # op == "regex"
    return f"{column} RLIKE {_quote(sval)}"


def _date_filter(start_date, end_date):
    if end_date:
        return f"data BETWEEN '{start_date}' AND '{end_date}'"
    return f"data >= '{start_date}'"


def _compile_conditions(conditions, match):
    """Compile a condition list into a single '(a AND b)' / '(a OR b)' clause, or '' if empty."""
    if not isinstance(conditions, list):
        raise ValueError("conditions must be a list.")
    if match not in MATCH_MODES:
        raise ValueError(f"Invalid match mode: '{match}'. Must be 'and' or 'or'.")
    compiled = [_compile_condition(c) for c in conditions]
    if not compiled:
        return ""
    joiner = " AND " if match == "and" else " OR "
    return "(" + joiner.join(compiled) + ")"


def _clamp_limit(raw):
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def build_custom_query(payload, start_date, end_date=None, schema_config=None):
    """Build Databricks SQL from a structured custom-query payload.

    Returns {"query": str, "metadata": dict}. Raises ValueError on invalid input.
    """
    if not isinstance(payload, dict):
        raise ValueError("Custom query payload must be an object.")

    output_mode = payload.get("output_mode")
    if output_mode not in OUTPUT_MODES:
        raise ValueError(f"Invalid output_mode: '{output_mode}'. Must be one of {OUTPUT_MODES}.")

    table = (schema_config or DEFAULT_SCHEMA_CONFIG)["table_name"]
    match = payload.get("match", "and")

    where_parts = [_date_filter(start_date, end_date)]
    main_clause = _compile_conditions(payload.get("conditions", []), match)
    if main_clause:
        where_parts.append(main_clause)

    scope = payload.get("session_scope")
    if scope:
        if not isinstance(scope, dict):
            raise ValueError("session_scope must be an object.")
        scope_clause = _compile_conditions(scope.get("conditions", []), scope.get("match", "and"))
        if scope_clause:
            subq_where = f"{_date_filter(start_date, end_date)} AND {scope_clause}"
            where_parts.append(f"ga_session_id IN (SELECT ga_session_id FROM {table} WHERE {subq_where})")

    where = " AND ".join(where_parts)

    group_by = payload.get("group_by")
    if group_by is not None:
        _validate_column(group_by)

    if output_mode == "extract":
        raw_cols = payload.get("output_columns") or list(DEFAULT_EXTRACT_COLUMNS)
        if not isinstance(raw_cols, list):
            raise ValueError("output_columns must be a list.")
        columns = [_validate_column(c) for c in raw_cols] or list(DEFAULT_EXTRACT_COLUMNS)
        limit = _clamp_limit(payload.get("limit", DEFAULT_LIMIT))
        query = (
            f"SELECT {', '.join(columns)}\n"
            f"FROM {table}\n"
            f"WHERE {where}\n"
            f"ORDER BY event_timestamp\n"
            f"LIMIT {limit}"
        )
        metadata = {
            "output_mode": output_mode,
            "condition_count": len(payload.get("conditions", []) or []),
            "session_condition_count": len((scope or {}).get("conditions", []) or []) if scope else 0,
            "group_by": None,
            "limit": limit,
        }
        return {"query": query, "metadata": metadata}

    # count_sessions / count_events
    agg = "COUNT(DISTINCT ga_session_id) AS session_count" if output_mode == "count_sessions" else "COUNT(*) AS event_count"
    order_col = "session_count" if output_mode == "count_sessions" else "event_count"
    if group_by:
        query = (
            f"SELECT {group_by} AS grupo, {agg}\n"
            f"FROM {table}\n"
            f"WHERE {where}\n"
            f"GROUP BY {group_by}\n"
            f"ORDER BY {order_col} DESC"
        )
    else:
        query = (
            f"SELECT {agg}\n"
            f"FROM {table}\n"
            f"WHERE {where}"
        )
    metadata = {
        "output_mode": output_mode,
        "condition_count": len(payload.get("conditions", []) or []),
        "session_condition_count": len((scope or {}).get("conditions", []) or []) if scope else 0,
        "group_by": group_by,
        "limit": None,
    }
    return {"query": query, "metadata": metadata}
