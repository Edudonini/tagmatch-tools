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

OUTPUT_MODES = ("count_sessions", "count_events", "extract", "aggregate", "funnel")
MATCH_MODES = ("and", "or")
AGG_FUNCS = ("sum", "avg", "min", "max", "count", "approx_count_distinct", "stddev")
_AGG_SQL = {
    "sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX", "count": "COUNT",
    "approx_count_distinct": "APPROX_COUNT_DISTINCT", "stddev": "STDDEV",
}
# Aggregate functions that require a numeric column (curated NUMERIC_COLUMNS).
_NUMERIC_AGG_FUNCS = frozenset({"sum", "avg", "min", "max", "stddev"})
TIME_BUCKET_UNITS = ("day", "week", "month")
_TIME_BUCKET_SQL = {
    "day": "CAST(data AS DATE)",
    "week": "trunc(CAST(data AS DATE), 'WEEK')",
    "month": "trunc(CAST(data AS DATE), 'MM')",
}
_HAVING_SQL = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "eq": "=", "neq": "<>"}
# Curated numeric subset of the allow-list; sum/avg/min/max require one of these.
NUMERIC_COLUMNS = frozenset({"value", "price", "quantity", "discount", "module_position", "indice", "posicao"})

DEFAULT_EXTRACT_COLUMNS = ("data", "event_timestamp", "event_name", "screenName", "ga_session_id")
DEFAULT_LIMIT = 1000
MAX_LIMIT = 10000
FUNNEL_MAX_STEPS = 10

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


def _compile_group(group):
    """Compile one group {match, conditions:[...]} into '(a AND b)' / '(a OR b)', or '' if empty."""
    if not isinstance(group, dict):
        raise ValueError("Each group must be an object.")
    conditions = group.get("conditions", [])
    if not isinstance(conditions, list):
        raise ValueError("conditions must be a list.")
    match = group.get("match", "and")
    if match not in MATCH_MODES:
        raise ValueError(f"Invalid match mode: '{match}'. Must be 'and' or 'or'.")
    compiled = [_compile_condition(c) for c in conditions]
    if not compiled:
        return ""
    joiner = " AND " if match == "and" else " OR "
    return "(" + joiner.join(compiled) + ")"


def _compile_filter(filt):
    """Compile {match, groups:[...]} into '((g1) OR (g2))', a single group verbatim, or '' if empty."""
    if not isinstance(filt, dict):
        raise ValueError("filter must be an object.")
    groups = filt.get("groups", [])
    if not isinstance(groups, list):
        raise ValueError("filter.groups must be a list.")
    match = filt.get("match", "and")
    if match not in MATCH_MODES:
        raise ValueError(f"Invalid match mode: '{match}'. Must be 'and' or 'or'.")
    compiled = [g for g in (_compile_group(gr) for gr in groups) if g]
    if not compiled:
        return ""
    if len(compiled) == 1:
        return compiled[0]  # single group -> no extra wrap (byte-for-byte v1)
    joiner = " AND " if match == "and" else " OR "
    return "(" + joiner.join(compiled) + ")"


def _validate_group_by(raw):
    """Return a validated list of group-by columns (allow-listed), or [] if none."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("group_by must be a list.")
    return [_validate_column(c) for c in raw]


def _count_conditions(filt):
    if not isinstance(filt, dict):
        return 0
    return sum(len(g.get("conditions", []) or []) for g in filt.get("groups", []) if isinstance(g, dict))


def _clamp_limit(raw):
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _build_funnel_query(funnel_spec, table, base_where):
    """Build an ordered multi-event session funnel (Approach A: layered CTEs).

    Returns (query, step_count, total_condition_count). Raises ValueError on
    invalid input. Each step reuses _compile_group (column/op/value validated);
    labels are emitted only as _quote-escaped string literals.
    """
    if not isinstance(funnel_spec, dict):
        raise ValueError("funnel deve ser um objeto.")
    steps = funnel_spec.get("steps")
    if not isinstance(steps, list):
        raise ValueError("funnel.steps deve ser uma lista.")
    if len(steps) < 2:
        raise ValueError("O funil precisa de ao menos 2 etapas.")
    if len(steps) > FUNNEL_MAX_STEPS:
        raise ValueError(f"O funil aceita no máximo {FUNNEL_MAX_STEPS} etapas.")

    clauses = []
    labels = []
    total_conditions = 0
    for i, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError("Cada etapa deve ser um objeto.")
        clause = _compile_group(step)  # validates every column/op/value; "" if no conditions
        if not clause:
            raise ValueError("Cada etapa do funil precisa de ao menos uma condição.")
        clauses.append(clause)
        total_conditions += len(step.get("conditions", []) or [])
        raw = step.get("label")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            labels.append(f"Etapa {i}")
        elif isinstance(raw, str):
            labels.append(raw)
        else:
            raise ValueError("O rótulo da etapa precisa ser texto.")

    n = len(steps)

    flags = ",\n    ".join(
        f"CASE WHEN {clauses[i]} THEN 1 ELSE 0 END AS s{i + 1}" for i in range(n)
    )
    base_cte = (
        "base AS (\n"
        "  SELECT ga_session_id, event_timestamp,\n"
        f"    {flags}\n"
        f"  FROM {table}\n"
        f"  WHERE {base_where}\n"
        ")"
    )

    t_ctes = [
        "t1 AS (\n"
        "  SELECT ga_session_id, MIN(CASE WHEN s1 = 1 THEN event_timestamp END) AS ts1\n"
        "  FROM base GROUP BY ga_session_id\n"
        ")"
    ]
    for k in range(2, n + 1):
        prev = k - 1
        t_ctes.append(
            f"t{k} AS (\n"
            f"  SELECT b.ga_session_id, p.ts{prev},\n"
            f"    MIN(CASE WHEN b.s{k} = 1 AND b.event_timestamp > p.ts{prev} THEN b.event_timestamp END) AS ts{k}\n"
            f"  FROM base b JOIN t{prev} p ON b.ga_session_id = p.ga_session_id\n"
            f"  WHERE p.ts{prev} IS NOT NULL\n"
            f"  GROUP BY b.ga_session_id, p.ts{prev}\n"
            ")"
        )

    count_lines = ",\n    ".join(
        f"(SELECT COUNT(*) FROM t{k} WHERE ts{k} IS NOT NULL) AS c{k}" for k in range(1, n + 1)
    )
    counts_cte = f"counts AS (\n  SELECT\n    {count_lines}\n)"

    all_ctes = ",\n".join([base_cte] + t_ctes + [counts_cte])

    union_rows = []
    for k in range(1, n + 1):
        label_lit = _quote(labels[k - 1])
        if k == 1:
            union_rows.append(
                f"SELECT 1 AS ordem, {label_lit} AS etapa, c1 AS sessoes, "
                "100.0 AS pct_etapa1, CAST(NULL AS DOUBLE) AS pct_anterior FROM counts"
            )
        else:
            union_rows.append(
                f"SELECT {k}, {label_lit}, c{k}, "
                f"ROUND(100.0 * c{k} / NULLIF(c1, 0), 1), "
                f"ROUND(100.0 * c{k} / NULLIF(c{k - 1}, 0), 1) FROM counts"
            )
    union_sql = "\nUNION ALL\n".join(union_rows)

    query = f"WITH {all_ctes}\n{union_sql}\nORDER BY ordem"
    return query, n, total_conditions


def _funnel_result(payload, table, start_date, end_date):
    base_where_parts = [_date_filter(start_date, end_date)]
    global_clause = _compile_filter(payload.get("filter") or {})
    if global_clause:
        base_where_parts.append(global_clause)
    base_where = " AND ".join(base_where_parts)
    query, step_count, condition_count = _build_funnel_query(payload.get("funnel"), table, base_where)
    return {
        "query": query,
        "metadata": {
            "output_mode": "funnel",
            "step_count": step_count,
            "condition_count": condition_count,
            "has_global_filter": bool(global_clause),
        },
    }


def _agg_expr(func, column):
    """Compile a validated aggregate SQL expression from func + column. Raises ValueError."""
    if func not in AGG_FUNCS:
        raise ValueError(f"Invalid aggregate function: '{func}'. Must be one of {AGG_FUNCS}.")
    if func == "count":
        return "COUNT(*)" if not column else f"COUNT({_validate_column(column)})"
    if func == "approx_count_distinct":
        if not isinstance(column, str) or not column:
            raise ValueError("A função 'approx_count_distinct' precisa de uma coluna.")
        return f"APPROX_COUNT_DISTINCT({_validate_column(column)})"
    # sum / avg / min / max / stddev -> numeric column required
    if func in _NUMERIC_AGG_FUNCS:
        # allow-list first, so an unknown/injected column is rejected as such
        col = _validate_column(column) if isinstance(column, str) and column else None
        if col is None or col not in NUMERIC_COLUMNS:
            raise ValueError(
                f"A função '{func}' precisa de uma coluna numérica {sorted(NUMERIC_COLUMNS)}, recebi '{column}'."
            )
        return f"{_AGG_SQL[func]}({col})"
    # count and approx_count_distinct are handled above; no other func is possible
    raise ValueError(f"Invalid aggregate function: '{func}'.")


def _agg_alias(func, column):
    """Deterministic, safe alias from func + (already allow-listed) column."""
    if func == "count":
        return "total" if not column else f"count_{column}"
    if func == "approx_count_distinct":
        return f"approx_distinct_{column}"
    return f"{func}_{column}"


def _dedupe_aliases(aliases):
    """Suffix duplicates in list order: a, a -> a, a_2, a_3, ..."""
    seen = {}
    out = []
    for a in aliases:
        if a in seen:
            seen[a] += 1
            out.append(f"{a}_{seen[a]}")
        else:
            seen[a] = 1
            out.append(a)
    return out


def _compile_metrics(metrics):
    """Compile the metrics list into ('EXPR AS alias', ...) SELECT terms and their aliases."""
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("aggregate.metrics precisa de ao menos uma métrica.")
    exprs = []
    raw_aliases = []
    for m in metrics:
        if not isinstance(m, dict):
            raise ValueError("Cada métrica deve ser um objeto.")
        func = m.get("func")
        column = m.get("column")
        exprs.append(_agg_expr(func, column))
        raw_aliases.append(_agg_alias(func, column if isinstance(column, str) and column else None))
    aliases = _dedupe_aliases(raw_aliases)
    select_terms = [f"{e} AS {a}" for e, a in zip(exprs, aliases)]
    return select_terms, aliases


def _compile_having(having):
    """Compile the optional HAVING list into ('<agg> <op> <num> AND ...', count)."""
    if having is None:
        return "", 0
    if not isinstance(having, list):
        raise ValueError("aggregate.having deve ser uma lista.")
    parts = []
    for h in having:
        if not isinstance(h, dict):
            raise ValueError("Cada condição HAVING deve ser um objeto.")
        expr = _agg_expr(h.get("func"), h.get("column"))
        op = h.get("op")
        if op not in _HAVING_SQL:
            raise ValueError(f"Operador HAVING inválido: '{op}'.")
        val = str(h.get("value", "")).strip()
        if not _NUMERIC_RE.match(val):
            raise ValueError(f"HAVING precisa de um valor numérico, recebi '{h.get('value')}'.")
        parts.append(f"{expr} {_HAVING_SQL[op]} {val}")
    return " AND ".join(parts), len(parts)


def _time_bucket_expr(spec):
    """Return the SQL expression for a time bucket, or None. Raises ValueError on a bad unit."""
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError("time_bucket deve ser um objeto.")
    unit = spec.get("unit")
    if unit not in TIME_BUCKET_UNITS:
        raise ValueError(f"time_bucket.unit inválido: '{unit}'. Deve ser um de {TIME_BUCKET_UNITS}.")
    return _TIME_BUCKET_SQL[unit]


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

    if output_mode == "funnel":
        return _funnel_result(payload, table, start_date, end_date)

    where_parts = [_date_filter(start_date, end_date)]
    main_clause = _compile_filter(payload.get("filter") or {})
    if main_clause:
        where_parts.append(main_clause)

    scope = payload.get("session_scope")
    scope_condition_count = 0
    if scope:
        if not isinstance(scope, dict):
            raise ValueError("session_scope must be an object.")
        scope_condition_count = len(scope.get("conditions", []) or [])
        scope_clause = _compile_group(scope)
        if scope_clause:
            subq_where = f"{_date_filter(start_date, end_date)} AND {scope_clause}"
            where_parts.append(f"ga_session_id IN (SELECT ga_session_id FROM {table} WHERE {subq_where})")

    where = " AND ".join(where_parts)
    group_by = _validate_group_by(payload.get("group_by"))
    condition_count = _count_conditions(payload.get("filter") or {})
    base_meta = {
        "condition_count": condition_count,
        "session_condition_count": scope_condition_count,
    }

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
        return {"query": query, "metadata": {**base_meta, "output_mode": output_mode, "group_by": [], "limit": limit}}

    if output_mode == "aggregate":
        agg_spec = payload.get("aggregate")
        if not isinstance(agg_spec, dict):
            raise ValueError("aggregate must be an object.")
        select_terms, aliases = _compile_metrics(agg_spec.get("metrics"))
        having_clause, having_count = _compile_having(agg_spec.get("having"))
        bucket_expr = _time_bucket_expr(payload.get("time_bucket"))

        select_dims = ([f"{bucket_expr} AS periodo"] if bucket_expr else []) + group_by
        group_by_sql = ([bucket_expr] if bucket_expr else []) + group_by
        select_list = ", ".join(select_dims + select_terms)

        query = f"SELECT {select_list}\nFROM {table}\nWHERE {where}"
        if group_by_sql:
            query += f"\nGROUP BY {', '.join(group_by_sql)}"
        if having_clause:
            query += f"\nHAVING {having_clause}"
        if bucket_expr:
            query += "\nORDER BY periodo ASC"
        elif group_by:
            query += f"\nORDER BY {aliases[0]} DESC"

        return {"query": query, "metadata": {**base_meta, "output_mode": output_mode,
                "metric_count": len(aliases), "group_by": group_by,
                "has_time_bucket": bucket_expr is not None,
                "having_count": having_count, "limit": None}}

    # count_sessions / count_events
    agg = "COUNT(DISTINCT ga_session_id) AS session_count" if output_mode == "count_sessions" else "COUNT(*) AS event_count"
    order_col = "session_count" if output_mode == "count_sessions" else "event_count"
    if group_by:
        cols = ", ".join(group_by)
        query = (
            f"SELECT {cols}, {agg}\n"
            f"FROM {table}\n"
            f"WHERE {where}\n"
            f"GROUP BY {cols}\n"
            f"ORDER BY {order_col} DESC"
        )
    else:
        query = f"SELECT {agg}\nFROM {table}\nWHERE {where}"
    return {"query": query, "metadata": {**base_meta, "output_mode": output_mode, "group_by": group_by, "limit": None}}
