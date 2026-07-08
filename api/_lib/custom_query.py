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
