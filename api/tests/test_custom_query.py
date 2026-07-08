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

def test_aggregate_sum_grouped_two_dims():
    q = _q({"output_mode": "aggregate",
            "filter": _filter([_grp([{"column": "event_name", "op": "eq", "value": "purchase"}])]),
            "aggregate": {"func": "sum", "column": "value"},
            "group_by": ["screenName", "item_category"]})
    assert "SELECT screenName, item_category, SUM(value) AS resultado" in q
    assert "GROUP BY screenName, item_category" in q
    assert "ORDER BY resultado DESC" in q


def test_aggregate_grand_total_no_group_by():
    q = _q({"output_mode": "aggregate", "filter": _filter([_grp([])]),
            "aggregate": {"func": "avg", "column": "price"}})
    assert "SELECT AVG(price) AS resultado" in q
    assert "GROUP BY" not in q
    assert "ORDER BY" not in q


def test_aggregate_count_star_when_no_column():
    q = _q({"output_mode": "aggregate", "filter": _filter([_grp([])]),
            "aggregate": {"func": "count", "column": None}})
    assert "SELECT COUNT(*) AS resultado" in q


def test_aggregate_count_with_column():
    q = _q({"output_mode": "aggregate", "filter": _filter([_grp([])]),
            "aggregate": {"func": "count", "column": "item_id"}})
    assert "SELECT COUNT(item_id) AS resultado" in q


def test_aggregate_numeric_column_gate_rejects_non_numeric():
    with pytest.raises(ValueError, match="numérica"):
        _q({"output_mode": "aggregate", "filter": _filter([_grp([])]),
            "aggregate": {"func": "sum", "column": "screenName"}})


def test_aggregate_invalid_func_rejected():
    with pytest.raises(ValueError, match="aggregate function"):
        _q({"output_mode": "aggregate", "filter": _filter([_grp([])]),
            "aggregate": {"func": "median", "column": "value"}})


def test_aggregate_column_still_allow_listed_for_count():
    with pytest.raises(ValueError, match="Unknown column"):
        _q({"output_mode": "aggregate", "filter": _filter([_grp([])]),
            "aggregate": {"func": "count", "column": "evil"}})


# --- enums / shapes / metadata ---

def test_invalid_output_mode_rejected():
    with pytest.raises(ValueError, match="output_mode"):
        _q({"output_mode": "delete_everything", "filter": _filter([_grp([])])})


def test_filter_groups_must_be_list():
    with pytest.raises(ValueError, match="groups must be a list"):
        _q({"output_mode": "count_sessions", "filter": {"match": "and", "groups": "nope"}})


def test_metadata_reports_shape():
    result = build_custom_query({"output_mode": "aggregate",
                                 "filter": _filter([_grp([{"column": "event_name", "op": "eq", "value": "purchase"}])]),
                                 "aggregate": {"func": "sum", "column": "value"},
                                 "group_by": ["screenName"]},
                                "2026-01-01", end_date="2026-01-31")
    assert result["metadata"]["output_mode"] == "aggregate"
    assert result["metadata"]["func"] == "sum"
    assert result["metadata"]["column"] == "value"
    assert result["metadata"]["group_by"] == ["screenName"]
    assert result["metadata"]["condition_count"] == 1


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
