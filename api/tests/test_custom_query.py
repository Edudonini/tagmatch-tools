import pytest

from api._lib.custom_query import (
    ALLOWED_COLUMNS,
    _compile_condition,
    _validate_column,
)


def test_allowed_columns_has_81_known_silver_columns():
    assert "event_name" in ALLOWED_COLUMNS
    assert "screenName" in ALLOWED_COLUMNS
    assert "ga_session_id" in ALLOWED_COLUMNS
    assert "component_copy" in ALLOWED_COLUMNS
    assert len(ALLOWED_COLUMNS) == 81


def test_validate_column_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown column"):
        _validate_column("evil; DROP TABLE users")


def test_validate_column_rejects_non_string():
    with pytest.raises(ValueError, match="Unknown column"):
        _validate_column(None)


def test_eq_escapes_value():
    assert _compile_condition({"column": "event_name", "op": "eq", "value": "interaction"}) == "event_name = 'interaction'"


def test_eq_escapes_single_quote_injection():
    out = _compile_condition({"column": "screenName", "op": "eq", "value": "x' OR '1'='1"})
    assert out == "screenName = 'x'' OR ''1''=''1'"


def test_eq_escapes_trailing_backslash():
    out = _compile_condition({"column": "event_name", "op": "eq", "value": "x\\"})
    assert out == "event_name = 'x\\\\'"  # backslash doubled inside the literal


def test_neq():
    assert _compile_condition({"column": "event_name", "op": "neq", "value": "screen_view"}) == "event_name <> 'screen_view'"


def test_neq_escapes_trailing_backslash():
    out = _compile_condition({"column": "event_name", "op": "neq", "value": "x\\"})
    assert out == "event_name <> 'x\\\\'"


def test_in_escapes_backslash_in_each_value():
    out = _compile_condition({"column": "event_name", "op": "in", "value": "a\\, b"})
    assert out == "event_name IN ('a\\\\', 'b')"


def test_regex_doubles_backslash_for_string_literal_layer():
    # a user regex \d+ must reach the engine as \d+, so the string literal carries \\d+
    out = _compile_condition({"column": "screenName", "op": "regex", "value": "\\d+"})
    assert out == "screenName RLIKE '\\\\d+'"


def test_contains_wraps_wildcards():
    assert _compile_condition({"column": "component_copy", "op": "contains", "value": "Continuar"}) == "component_copy LIKE '%Continuar%'"


def test_contains_escapes_literal_percent():
    # a literal % in the value must be escaped so it is not a wildcard
    out = _compile_condition({"column": "component_copy", "op": "contains", "value": "50%"})
    assert out == "component_copy LIKE '%50\\%%'"


def test_starts_with():
    assert _compile_condition({"column": "screenName", "op": "starts_with", "value": "/napp/"}) == "screenName LIKE '/napp/%'"


def test_regex():
    assert _compile_condition({"column": "screenName", "op": "regex", "value": "^/napp/fatura"}) == "screenName RLIKE '^/napp/fatura'"


def test_numeric_operators_emit_bare_number():
    assert _compile_condition({"column": "value", "op": "gt", "value": "100"}) == "value > 100"
    assert _compile_condition({"column": "value", "op": "lt", "value": "5"}) == "value < 5"
    assert _compile_condition({"column": "price", "op": "gte", "value": "-2.5"}) == "price >= -2.5"
    assert _compile_condition({"column": "quantity", "op": "lte", "value": "10"}) == "quantity <= 10"


def test_numeric_operator_rejects_non_numeric():
    with pytest.raises(ValueError, match="numeric"):
        _compile_condition({"column": "value", "op": "gt", "value": "100 OR 1=1"})


def test_in_splits_and_escapes_each():
    out = _compile_condition({"column": "event_name", "op": "in", "value": "interaction, screen_view"})
    assert out == "event_name IN ('interaction', 'screen_view')"


def test_in_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        _compile_condition({"column": "event_name", "op": "in", "value": "  "})


def test_is_empty_ignores_value():
    assert _compile_condition({"column": "eventLabel", "op": "is_empty", "value": "ignored"}) == "(eventLabel IS NULL OR eventLabel = '')"


def test_is_not_empty():
    assert _compile_condition({"column": "eventLabel", "op": "is_not_empty"}) == "(eventLabel IS NOT NULL AND eventLabel <> '')"


def test_unknown_operator_rejected():
    with pytest.raises(ValueError, match="Unknown operator"):
        _compile_condition({"column": "event_name", "op": "haxx", "value": "x"})


def test_condition_must_be_object():
    with pytest.raises(ValueError, match="must be an object"):
        _compile_condition("event_name = 1")


from api._lib.custom_query import build_custom_query, _compile_group, _compile_filter

TABLE = "ecare_silver.b2c_ga4.silver_ga4_novo_app"


def _grp(conditions, match="and"):
    return {"match": match, "conditions": conditions}


def _filter(groups, match="and"):
    return {"match": match, "groups": groups}


def _q(payload, start="2026-01-01", end="2026-01-31"):
    return build_custom_query(payload, start, end_date=end)["query"]


# --- group / filter compilation ---

def test_compile_group_joins_by_match():
    out = _compile_group(_grp([
        {"column": "event_name", "op": "eq", "value": "interaction"},
        {"column": "component_copy", "op": "contains", "value": "Continuar"},
    ], match="and"))
    assert out == "(event_name = 'interaction' AND component_copy LIKE '%Continuar%')"


def test_compile_group_empty_returns_blank():
    assert _compile_group(_grp([])) == ""


def test_compile_filter_single_group_no_extra_parens():
    # a single group reproduces v1 output byte-for-byte (no outer wrap)
    out = _compile_filter(_filter([_grp([{"column": "event_name", "op": "eq", "value": "interaction"}])]))
    assert out == "(event_name = 'interaction')"


def test_compile_filter_two_groups_joined_by_outer_match():
    out = _compile_filter(_filter([
        _grp([{"column": "event_name", "op": "eq", "value": "interaction"}], match="and"),
        _grp([{"column": "screenName", "op": "eq", "value": "/napp/fatura"}], match="and"),
    ], match="or"))
    assert out == "((event_name = 'interaction') OR (screenName = '/napp/fatura'))"


def test_compile_filter_two_groups_joined_by_outer_and():
    out = _compile_filter(_filter([
        _grp([{"column": "event_name", "op": "eq", "value": "interaction"}], match="and"),
        _grp([{"column": "screenName", "op": "eq", "value": "/napp/fatura"}], match="and"),
    ], match="and"))
    assert out == "((event_name = 'interaction') AND (screenName = '/napp/fatura'))"


def test_compile_filter_drops_empty_group():
    out = _compile_filter(_filter([
        _grp([{"column": "event_name", "op": "eq", "value": "interaction"}]),
        _grp([]),
    ], match="or"))
    assert out == "(event_name = 'interaction')"


def test_compile_filter_all_empty_returns_blank():
    assert _compile_filter(_filter([_grp([]), _grp([])])) == ""


def test_group_match_validated():
    with pytest.raises(ValueError, match="match"):
        _compile_group(_grp([{"column": "event_name", "op": "eq", "value": "x"}], match="nand"))


def test_group_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _compile_group(_grp([{"column": "evil", "op": "eq", "value": "x"}]))


# --- build_custom_query: count modes with the new shape ---

def test_count_sessions_single_group():
    q = _q({"output_mode": "count_sessions",
            "filter": _filter([_grp([{"column": "event_name", "op": "eq", "value": "interaction"}])])})
    assert "SELECT COUNT(DISTINCT ga_session_id) AS session_count" in q
    assert f"FROM {TABLE}" in q
    assert "WHERE data BETWEEN '2026-01-01' AND '2026-01-31' AND (event_name = 'interaction')" in q
    assert "GROUP BY" not in q


def test_count_nested_groups():
    q = _q({"output_mode": "count_events",
            "filter": _filter([
                _grp([{"column": "event_name", "op": "eq", "value": "interaction"},
                      {"column": "component_copy", "op": "contains", "value": "Continuar"}], match="and"),
                _grp([{"column": "screenName", "op": "eq", "value": "/napp/fatura"}], match="and"),
            ], match="or")})
    assert "SELECT COUNT(*) AS event_count" in q
    assert "((event_name = 'interaction' AND component_copy LIKE '%Continuar%') OR (screenName = '/napp/fatura'))" in q


def test_count_no_filter_counts_everything():
    q = _q({"output_mode": "count_sessions", "filter": _filter([_grp([])])})
    assert "WHERE data BETWEEN '2026-01-01' AND '2026-01-31'" in q
    assert " AND (" not in q


def test_count_multi_dimension_group_by():
    q = _q({"output_mode": "count_events",
            "filter": _filter([_grp([])]),
            "group_by": ["screenName", "event_name"]})
    assert "SELECT screenName, event_name, COUNT(*) AS event_count" in q
    assert "GROUP BY screenName, event_name" in q
    assert "ORDER BY event_count DESC" in q
    assert "AS grupo" not in q


def test_group_by_entry_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q({"output_mode": "count_sessions", "filter": _filter([_grp([])]), "group_by": ["evil"]})


def test_group_by_must_be_list():
    with pytest.raises(ValueError, match="group_by must be a list"):
        _q({"output_mode": "count_sessions", "filter": _filter([_grp([])]), "group_by": "screenName"})


# --- session scope (flat, unchanged shape) ---

def test_session_scope_subquery():
    q = _q({"output_mode": "count_sessions",
            "filter": _filter([_grp([{"column": "event_name", "op": "eq", "value": "interaction"}])]),
            "session_scope": {"match": "and", "conditions": [{"column": "screenName", "op": "eq", "value": "/napp/home"}]}})
    assert "ga_session_id IN (SELECT ga_session_id FROM" in q
    assert "(screenName = '/napp/home')" in q


def test_nested_filter_combined_with_session_scope():
    # a multi-group (nested) main filter composes orthogonally with a flat session scope
    q = _q({"output_mode": "count_sessions",
            "filter": _filter([
                _grp([{"column": "event_name", "op": "eq", "value": "interaction"}]),
                _grp([{"column": "screenName", "op": "eq", "value": "/napp/fatura"}]),
            ], match="or"),
            "session_scope": {"match": "and", "conditions": [{"column": "screenName", "op": "eq", "value": "/napp/home"}]}})
    assert "AND ((event_name = 'interaction') OR (screenName = '/napp/fatura'))" in q
    assert "ga_session_id IN (SELECT ga_session_id FROM" in q
    assert "(screenName = '/napp/home')" in q


def test_session_scope_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q({"output_mode": "count_sessions", "filter": _filter([_grp([])]),
            "session_scope": {"match": "and", "conditions": [{"column": "evil", "op": "eq", "value": "x"}]}})


# --- extract mode (shape unchanged except group_by removed) ---

def test_extract_default_columns_and_limit():
    q = _q({"output_mode": "extract",
            "filter": _filter([_grp([{"column": "screenName", "op": "eq", "value": "/napp/fatura"}])])})
    assert "SELECT data, event_timestamp, event_name, screenName, ga_session_id" in q
    assert "ORDER BY event_timestamp" in q
    assert "LIMIT 1000" in q


def test_extract_limit_clamped():
    q = build_custom_query({"output_mode": "extract", "filter": _filter([_grp([])]), "limit": 99999},
                           "2026-01-01", end_date="2026-01-31")["query"]
    assert "LIMIT 10000" in q


# --- aggregate mode ---

def _metric(func, column=None):
    return {"func": func, "column": column}


def _aggq(metrics, group_by=None, having=None, time_bucket=None, filt=None):
    payload = {"output_mode": "aggregate", "aggregate": {"metrics": metrics}}
    if having is not None:
        payload["aggregate"]["having"] = having
    if group_by is not None:
        payload["group_by"] = group_by
    if time_bucket is not None:
        payload["time_bucket"] = time_bucket
    if filt is not None:
        payload["filter"] = filt
    return payload


def test_aggregate_single_metric_auto_alias():
    q = _q(_aggq([_metric("sum", "value")]))
    assert "SELECT SUM(value) AS sum_value" in q
    assert f"FROM {TABLE}" in q
    assert "GROUP BY" not in q
    assert "ORDER BY" not in q


def test_aggregate_count_star_alias_total():
    q = _q(_aggq([_metric("count")]))
    assert "SELECT COUNT(*) AS total" in q


def test_aggregate_count_with_column_alias():
    q = _q(_aggq([_metric("count", "item_id")]))
    assert "SELECT COUNT(item_id) AS count_item_id" in q


def test_aggregate_multiple_metrics_distinct_aliases():
    q = _q(_aggq([_metric("sum", "value"), _metric("count"), _metric("avg", "price")]))
    assert "SELECT SUM(value) AS sum_value, COUNT(*) AS total, AVG(price) AS avg_price" in q


def test_aggregate_duplicate_metric_deduped_alias():
    q = _q(_aggq([_metric("sum", "value"), _metric("sum", "value")]))
    assert "SUM(value) AS sum_value, SUM(value) AS sum_value_2" in q


def test_aggregate_approx_count_distinct():
    q = _q(_aggq([_metric("approx_count_distinct", "ga_session_id")]))
    assert "APPROX_COUNT_DISTINCT(ga_session_id) AS approx_distinct_ga_session_id" in q


def test_aggregate_stddev_numeric_gate():
    with pytest.raises(ValueError, match="numérica"):
        _q(_aggq([_metric("stddev", "screenName")]))


def test_aggregate_approx_requires_column():
    with pytest.raises(ValueError, match="approx_count_distinct"):
        _q(_aggq([_metric("approx_count_distinct")]))


def test_aggregate_empty_metrics_rejected():
    with pytest.raises(ValueError, match="métrica"):
        _q(_aggq([]))


def test_aggregate_invalid_func_rejected():
    with pytest.raises(ValueError, match="Invalid aggregate function"):
        _q(_aggq([_metric("median", "value")]))


def test_aggregate_metric_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q(_aggq([_metric("sum", "evil; DROP TABLE x")]))


def test_aggregate_grouped_orders_by_first_metric():
    q = _q(_aggq([_metric("sum", "value"), _metric("count")], group_by=["screenName", "item_category"]))
    assert "SELECT screenName, item_category, SUM(value) AS sum_value, COUNT(*) AS total" in q
    assert "GROUP BY screenName, item_category" in q
    assert "ORDER BY sum_value DESC" in q


def test_aggregate_having_single():
    q = _q(_aggq([_metric("count")], group_by=["screenName"],
                 having=[{"func": "count", "column": None, "op": "gt", "value": "100"}]))
    assert "HAVING COUNT(*) > 100" in q


def test_aggregate_having_multiple_and():
    q = _q(_aggq([_metric("sum", "value")], group_by=["screenName"],
                 having=[{"func": "sum", "column": "value", "op": "gte", "value": "1000"},
                         {"func": "count", "column": None, "op": "lt", "value": "50"}]))
    assert "HAVING SUM(value) >= 1000 AND COUNT(*) < 50" in q


def test_aggregate_having_value_must_be_numeric():
    with pytest.raises(ValueError, match="num"):
        _q(_aggq([_metric("count")], having=[{"func": "count", "column": None, "op": "gt", "value": "abc"}]))


def test_aggregate_having_op_validated():
    with pytest.raises(ValueError, match="HAVING"):
        _q(_aggq([_metric("count")], having=[{"func": "count", "column": None, "op": "like", "value": "1"}]))


def test_aggregate_having_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q(_aggq([_metric("count")], having=[{"func": "sum", "column": "evil", "op": "gt", "value": "1"}]))


def test_aggregate_time_bucket_week():
    q = _q(_aggq([_metric("count")], time_bucket={"unit": "week"}))
    assert "SELECT trunc(CAST(data AS DATE), 'WEEK') AS periodo, COUNT(*) AS total" in q
    assert "GROUP BY trunc(CAST(data AS DATE), 'WEEK')" in q
    assert "ORDER BY periodo ASC" in q


def test_aggregate_time_bucket_day_and_month():
    qd = _q(_aggq([_metric("count")], time_bucket={"unit": "day"}))
    assert "CAST(data AS DATE) AS periodo" in qd
    qm = _q(_aggq([_metric("count")], time_bucket={"unit": "month"}))
    assert "trunc(CAST(data AS DATE), 'MM') AS periodo" in qm


def test_aggregate_time_bucket_with_dims():
    q = _q(_aggq([_metric("count")], group_by=["screenName"], time_bucket={"unit": "day"}))
    assert "SELECT CAST(data AS DATE) AS periodo, screenName, COUNT(*) AS total" in q
    assert "GROUP BY CAST(data AS DATE), screenName" in q
    assert "ORDER BY periodo ASC" in q


def test_aggregate_time_bucket_unit_validated():
    with pytest.raises(ValueError, match="time_bucket"):
        _q(_aggq([_metric("count")], time_bucket={"unit": "fortnight"}))


def test_aggregate_metadata():
    res = build_custom_query(
        _aggq([_metric("sum", "value"), _metric("count")], group_by=["screenName"],
              time_bucket={"unit": "week"},
              having=[{"func": "count", "column": None, "op": "gt", "value": "10"}]),
        "2026-01-01", end_date="2026-01-31")
    assert res["metadata"]["output_mode"] == "aggregate"
    assert res["metadata"]["metric_count"] == 2
    assert res["metadata"]["group_by"] == ["screenName"]
    assert res["metadata"]["has_time_bucket"] is True
    assert res["metadata"]["having_count"] == 1


def test_aggregate_non_dict_metric_rejected():
    with pytest.raises(ValueError, match="Cada métrica deve ser um objeto"):
        _q(_aggq(["not-a-dict"]))


def test_aggregate_non_list_having_rejected():
    with pytest.raises(ValueError, match="aggregate.having deve ser uma lista"):
        _q(_aggq([_metric("count")], having="nope"))


def test_aggregate_non_dict_having_entry_rejected():
    with pytest.raises(ValueError, match="Cada condição HAVING deve ser um objeto"):
        _q(_aggq([_metric("count")], having=["nope"]))


def test_aggregate_non_dict_time_bucket_rejected():
    with pytest.raises(ValueError, match="time_bucket deve ser um objeto"):
        _q(_aggq([_metric("count")], time_bucket="nope"))


def test_aggregate_grand_total_with_having_no_group_by():
    q = _q(_aggq([_metric("count")], having=[{"func": "count", "column": None, "op": "gt", "value": "5"}]))
    assert "SELECT COUNT(*) AS total" in q
    assert "HAVING COUNT(*) > 5" in q
    assert "GROUP BY" not in q
    assert "ORDER BY" not in q


# --- enums / shapes / metadata ---

def test_invalid_output_mode_rejected():
    with pytest.raises(ValueError, match="output_mode"):
        _q({"output_mode": "delete_everything", "filter": _filter([_grp([])])})


def test_filter_groups_must_be_list():
    with pytest.raises(ValueError, match="groups must be a list"):
        _q({"output_mode": "count_sessions", "filter": {"match": "and", "groups": "nope"}})


def test_custom_table_name_used():
    q = build_custom_query({"output_mode": "count_sessions", "filter": _filter([_grp([])])},
                           "2026-01-01", end_date="2026-01-31",
                           schema_config={"table_name": "cat.sch.tbl"})["query"]
    assert "FROM cat.sch.tbl" in q


# --- restored branch coverage (test-only, v2 shape) ---

def test_compile_group_or_joiner_within_group():
    out = _compile_group(_grp([
        {"column": "event_name", "op": "eq", "value": "interaction"},
        {"column": "event_name", "op": "eq", "value": "screen_view"},
    ], match="or"))
    assert out == "(event_name = 'interaction' OR event_name = 'screen_view')"


def test_compile_filter_invalid_match_rejected():
    with pytest.raises(ValueError, match="match"):
        _compile_filter({"match": "nand", "groups": [_grp([{"column": "event_name", "op": "eq", "value": "x"}])]})


def test_extract_custom_output_columns_and_limit():
    q = build_custom_query({"output_mode": "extract", "filter": _filter([_grp([])]),
                            "output_columns": ["event_name", "screenName"], "limit": 50},
                           "2026-01-01", end_date="2026-01-31")["query"]
    assert "SELECT event_name, screenName" in q
    assert "LIMIT 50" in q


def test_extract_output_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        build_custom_query({"output_mode": "extract", "filter": _filter([_grp([])]),
                            "output_columns": ["event_name", "evil"]},
                           "2026-01-01", end_date="2026-01-31")


def test_extract_limit_floor_is_one():
    q = build_custom_query({"output_mode": "extract", "filter": _filter([_grp([])]), "limit": 0},
                           "2026-01-01", end_date="2026-01-31")["query"]
    assert "LIMIT 1" in q


def test_date_filter_start_only():
    q = build_custom_query({"output_mode": "count_sessions", "filter": _filter([_grp([])])},
                           "2026-01-01", end_date=None)["query"]
    assert "WHERE data >= '2026-01-01'" in q


# --- funnel mode (ordered multi-event session funnel) ---

def _fstep(conditions, match="and", label=None):
    step = {"match": match, "conditions": conditions}
    if label is not None:
        step["label"] = label
    return step


def _funnel(steps, filt=None):
    payload = {"output_mode": "funnel", "funnel": {"steps": steps}}
    if filt is not None:
        payload["filter"] = filt
    return payload


def test_funnel_two_steps_structure():
    q = _q(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "screen_view"}]),
        _fstep([{"column": "event_name", "op": "eq", "value": "interaction"}]),
    ]))
    assert q.startswith("WITH base AS (")
    assert "CASE WHEN (event_name = 'screen_view') THEN 1 ELSE 0 END AS s1" in q
    assert "CASE WHEN (event_name = 'interaction') THEN 1 ELSE 0 END AS s2" in q
    assert f"FROM {TABLE}" in q
    assert "WHERE data BETWEEN '2026-01-01' AND '2026-01-31'" in q
    assert "MIN(CASE WHEN s1 = 1 THEN event_timestamp END) AS ts1" in q
    assert "MIN(CASE WHEN b.s2 = 1 AND b.event_timestamp > p.ts1 THEN b.event_timestamp END) AS ts2" in q
    assert "FROM base b JOIN t1 p ON b.ga_session_id = p.ga_session_id" in q
    assert "WHERE p.ts1 IS NOT NULL" in q
    assert "(SELECT COUNT(*) FROM t1 WHERE ts1 IS NOT NULL) AS c1" in q
    assert "(SELECT COUNT(*) FROM t2 WHERE ts2 IS NOT NULL) AS c2" in q
    assert "SELECT 1 AS ordem, 'Etapa 1' AS etapa, c1 AS sessoes, 100.0 AS pct_etapa1, CAST(NULL AS DOUBLE) AS pct_anterior FROM counts" in q
    assert "SELECT 2, 'Etapa 2', c2, ROUND(100.0 * c2 / NULLIF(c1, 0), 1), ROUND(100.0 * c2 / NULLIF(c1, 0), 1) FROM counts" in q
    assert q.rstrip().endswith("ORDER BY ordem")
    assert q.count("UNION ALL") == 1


def test_funnel_three_steps_ordering_and_pct():
    q = _q(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "a"}]),
        _fstep([{"column": "event_name", "op": "eq", "value": "b"}]),
        _fstep([{"column": "event_name", "op": "eq", "value": "c"}]),
    ]))
    assert "MIN(CASE WHEN b.s3 = 1 AND b.event_timestamp > p.ts2 THEN b.event_timestamp END) AS ts3" in q
    assert "FROM base b JOIN t2 p ON b.ga_session_id = p.ga_session_id" in q
    assert "(SELECT COUNT(*) FROM t3 WHERE ts3 IS NOT NULL) AS c3" in q
    assert "SELECT 3, 'Etapa 3', c3, ROUND(100.0 * c3 / NULLIF(c1, 0), 1), ROUND(100.0 * c3 / NULLIF(c2, 0), 1) FROM counts" in q
    assert q.count("UNION ALL") == 2


def test_funnel_custom_label_escaped():
    q = _q(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "a"}], label="Viu a fatura"),
        _fstep([{"column": "event_name", "op": "eq", "value": "b"}], label="O'Brien"),
    ]))
    assert "'Viu a fatura' AS etapa" in q
    assert "'O''Brien'" in q  # single quote doubled, no literal breakout


def test_funnel_label_backslash_escaped():
    # the label is the one free-text funnel string; a trailing backslash must be
    # doubled (via _quote) so it cannot escape the closing quote in Databricks
    q = _q(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "a"}], label="path\\"),
        _fstep([{"column": "event_name", "op": "eq", "value": "b"}]),
    ]))
    assert "'path\\\\' AS etapa" in q


def test_funnel_global_filter_applied_to_base():
    q = _q(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "a"}]),
        _fstep([{"column": "event_name", "op": "eq", "value": "b"}]),
    ], filt=_filter([_grp([{"column": "audience", "op": "eq", "value": "premium"}])])))
    assert "WHERE data BETWEEN '2026-01-01' AND '2026-01-31' AND (audience = 'premium')" in q


def test_funnel_requires_at_least_two_steps():
    with pytest.raises(ValueError, match="2 etapas"):
        _q(_funnel([_fstep([{"column": "event_name", "op": "eq", "value": "a"}])]))


def test_funnel_rejects_more_than_max_steps():
    steps = [_fstep([{"column": "event_name", "op": "eq", "value": str(i)}]) for i in range(11)]
    with pytest.raises(ValueError, match="máximo"):
        _q(_funnel(steps))


def test_funnel_rejects_empty_step():
    with pytest.raises(ValueError, match="ao menos uma condição"):
        _q(_funnel([
            _fstep([{"column": "event_name", "op": "eq", "value": "a"}]),
            _fstep([]),
        ]))


def test_funnel_step_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q(_funnel([
            _fstep([{"column": "evil; DROP TABLE x", "op": "eq", "value": "a"}]),
            _fstep([{"column": "event_name", "op": "eq", "value": "b"}]),
        ]))


def test_funnel_rejects_non_string_label():
    with pytest.raises(ValueError, match="rótulo"):
        _q(_funnel([
            _fstep([{"column": "event_name", "op": "eq", "value": "a"}], label=123),
            _fstep([{"column": "event_name", "op": "eq", "value": "b"}]),
        ]))


def test_funnel_metadata():
    res = build_custom_query(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "a"}]),
        _fstep([{"column": "event_name", "op": "eq", "value": "b"},
                {"column": "screenName", "op": "eq", "value": "/x"}]),
    ]), "2026-01-01", end_date="2026-01-31")
    assert res["metadata"] == {
        "output_mode": "funnel", "step_count": 2, "condition_count": 3, "has_global_filter": False,
    }


def test_funnel_metadata_flags_global_filter():
    res = build_custom_query(_funnel([
        _fstep([{"column": "event_name", "op": "eq", "value": "a"}]),
        _fstep([{"column": "event_name", "op": "eq", "value": "b"}]),
    ], filt=_filter([_grp([{"column": "audience", "op": "eq", "value": "premium"}])])),
        "2026-01-01", end_date="2026-01-31")
    assert res["metadata"]["has_global_filter"] is True


def test_funnel_accepts_exactly_max_steps():
    # FUNNEL_MAX_STEPS (10) is the accepting boundary: 10 steps must succeed
    steps = [_fstep([{"column": "event_name", "op": "eq", "value": str(i)}]) for i in range(10)]
    q = _q(_funnel(steps))
    assert "(SELECT COUNT(*) FROM t10 WHERE ts10 IS NOT NULL) AS c10" in q
    assert q.count("UNION ALL") == 9


def test_funnel_rejects_non_dict_funnel_spec():
    with pytest.raises(ValueError, match="funnel deve ser um objeto"):
        build_custom_query({"output_mode": "funnel", "funnel": "nope"},
                           "2026-01-01", end_date="2026-01-31")


def test_funnel_rejects_non_dict_step():
    with pytest.raises(ValueError, match="Cada etapa deve ser um objeto"):
        _q(_funnel([
            _fstep([{"column": "event_name", "op": "eq", "value": "a"}]),
            "not-a-dict",
        ]))


def _aggq_hm(metrics, having, match, group_by=None):
    payload = _aggq(metrics, group_by=group_by, having=having)
    payload["aggregate"]["having_match"] = match
    return payload


def test_aggregate_approx_percentile():
    q = _q(_aggq([{"func": "approx_percentile", "column": "value", "p": 0.5}]))
    assert "approx_percentile(value, 0.5) AS approx_pct_value" in q


def test_aggregate_approx_percentile_numeric_gate():
    with pytest.raises(ValueError, match="numérica"):
        _q(_aggq([{"func": "approx_percentile", "column": "screenName", "p": 0.5}]))


def test_aggregate_approx_percentile_p_out_of_range():
    with pytest.raises(ValueError, match="percentil"):
        _q(_aggq([{"func": "approx_percentile", "column": "value", "p": 1.5}]))


def test_aggregate_approx_percentile_p_non_numeric():
    with pytest.raises(ValueError, match="percentil"):
        _q(_aggq([{"func": "approx_percentile", "column": "value", "p": "abc"}]))


def test_aggregate_approx_percentile_p_missing():
    with pytest.raises(ValueError, match="percentil"):
        _q(_aggq([{"func": "approx_percentile", "column": "value"}]))


def test_aggregate_approx_percentile_boundary_p():
    q1 = _q(_aggq([{"func": "approx_percentile", "column": "value", "p": ".95"}]))
    assert "approx_percentile(value, .95)" in q1
    q2 = _q(_aggq([{"func": "approx_percentile", "column": "value", "p": 1}]))
    assert "approx_percentile(value, 1)" in q2


def test_aggregate_named_alias():
    q = _q(_aggq([{"func": "sum", "column": "value", "alias": "receita"}]))
    assert "SUM(value) AS receita" in q


def test_aggregate_named_alias_invalid_rejected():
    for bad in ["a; DROP", "1abc", "a b"]:
        with pytest.raises(ValueError, match="Alias inválido"):
            _q(_aggq([{"func": "sum", "column": "value", "alias": bad}]))


def test_aggregate_duplicate_named_alias_deduped():
    q = _q(_aggq([{"func": "sum", "column": "value", "alias": "receita"},
                  {"func": "avg", "column": "price", "alias": "receita"}]))
    assert "SUM(value) AS receita, AVG(price) AS receita_2" in q


def test_aggregate_empty_alias_falls_back_to_auto():
    q = _q(_aggq([{"func": "sum", "column": "value", "alias": "   "}]))
    assert "SUM(value) AS sum_value" in q


def test_aggregate_having_or():
    q = _q(_aggq_hm([_metric("sum", "value")],
                    [{"func": "count", "column": None, "op": "gt", "value": "100"},
                     {"func": "sum", "column": "value", "op": "gte", "value": "1000"}],
                    "or", group_by=["screenName"]))
    assert "HAVING COUNT(*) > 100 OR SUM(value) >= 1000" in q


def test_aggregate_having_match_defaults_and():
    q = _q(_aggq([_metric("count")], group_by=["screenName"],
                 having=[{"func": "count", "column": None, "op": "gt", "value": "1"},
                         {"func": "count", "column": None, "op": "lt", "value": "9"}]))
    assert "HAVING COUNT(*) > 1 AND COUNT(*) < 9" in q


def test_aggregate_having_match_invalid_rejected():
    with pytest.raises(ValueError, match="having_match"):
        _q(_aggq_hm([_metric("count")], [{"func": "count", "column": None, "op": "gt", "value": "1"}], "nand"))


def test_aggregate_having_approx_percentile():
    q = _q(_aggq([_metric("count")], group_by=["screenName"],
                 having=[{"func": "approx_percentile", "column": "value", "p": 0.9, "op": "gt", "value": "50"}]))
    assert "HAVING approx_percentile(value, 0.9) > 50" in q


def test_aggregate_time_bucket_hour():
    q = _q(_aggq([_metric("count")], time_bucket={"unit": "hour"}))
    assert "SELECT date_trunc('HOUR', event_timestamp) AS periodo, COUNT(*) AS total" in q
    assert "GROUP BY date_trunc('HOUR', event_timestamp)" in q
    assert "ORDER BY periodo ASC" in q
