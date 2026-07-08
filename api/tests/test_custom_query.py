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


from api._lib.custom_query import build_custom_query

TABLE = "ecare_silver.b2c_ga4.silver_ga4_novo_app"


def _q(payload, start="2026-01-01", end="2026-01-31"):
    return build_custom_query(payload, start, end_date=end)["query"]


def test_count_sessions_no_group_by():
    q = _q({
        "output_mode": "count_sessions",
        "match": "and",
        "conditions": [{"column": "event_name", "op": "eq", "value": "interaction"}],
    })
    assert "SELECT COUNT(DISTINCT ga_session_id) AS session_count" in q
    assert f"FROM {TABLE}" in q
    assert "WHERE data BETWEEN '2026-01-01' AND '2026-01-31'" in q
    assert "(event_name = 'interaction')" in q
    assert "GROUP BY" not in q


def test_count_events():
    q = _q({
        "output_mode": "count_events",
        "match": "and",
        "conditions": [{"column": "event_name", "op": "eq", "value": "interaction"}],
    })
    assert "SELECT COUNT(*) AS event_count" in q


def test_conditions_joined_by_or():
    q = _q({
        "output_mode": "count_sessions",
        "match": "or",
        "conditions": [
            {"column": "event_name", "op": "eq", "value": "interaction"},
            {"column": "component_copy", "op": "contains", "value": "Continuar"},
        ],
    })
    assert "(event_name = 'interaction' OR component_copy LIKE '%Continuar%')" in q


def test_count_with_group_by():
    q = _q({
        "output_mode": "count_events",
        "match": "and",
        "conditions": [],
        "group_by": "screenName",
    })
    assert "SELECT screenName AS grupo, COUNT(*) AS event_count" in q
    assert "GROUP BY screenName" in q
    assert "ORDER BY event_count DESC" in q


def test_group_by_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q({"output_mode": "count_sessions", "match": "and", "conditions": [], "group_by": "evil"})


def test_no_conditions_counts_everything_in_range():
    q = _q({"output_mode": "count_sessions", "match": "and", "conditions": []})
    assert "WHERE data BETWEEN '2026-01-01' AND '2026-01-31'" in q
    assert " AND (" not in q  # no conditions clause appended


def test_date_filter_start_only():
    q = build_custom_query(
        {"output_mode": "count_sessions", "match": "and", "conditions": []},
        "2026-01-01", end_date=None,
    )["query"]
    assert "WHERE data >= '2026-01-01'" in q


def test_extract_default_columns_and_limit():
    q = _q({"output_mode": "extract", "match": "and", "conditions": [{"column": "screenName", "op": "eq", "value": "/napp/fatura"}]})
    assert "SELECT data, event_timestamp, event_name, screenName, ga_session_id" in q
    assert "ORDER BY event_timestamp" in q
    assert "LIMIT 1000" in q


def test_extract_custom_columns_and_limit():
    q = build_custom_query({
        "output_mode": "extract",
        "match": "and",
        "conditions": [],
        "output_columns": ["event_name", "screenName"],
        "limit": 50,
    }, "2026-01-01", end_date="2026-01-31")["query"]
    assert "SELECT event_name, screenName" in q
    assert "LIMIT 50" in q


def test_extract_output_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        build_custom_query({
            "output_mode": "extract", "match": "and", "conditions": [],
            "output_columns": ["event_name", "evil"],
        }, "2026-01-01", end_date="2026-01-31")


def test_limit_clamped_to_max():
    q = build_custom_query({
        "output_mode": "extract", "match": "and", "conditions": [], "limit": 99999,
    }, "2026-01-01", end_date="2026-01-31")["query"]
    assert "LIMIT 10000" in q


def test_limit_floor_is_one():
    q = build_custom_query({
        "output_mode": "extract", "match": "and", "conditions": [], "limit": 0,
    }, "2026-01-01", end_date="2026-01-31")["query"]
    assert "LIMIT 1" in q


def test_session_scope_subquery():
    q = _q({
        "output_mode": "count_sessions",
        "match": "and",
        "conditions": [{"column": "event_name", "op": "eq", "value": "interaction"}],
        "session_scope": {
            "match": "and",
            "conditions": [{"column": "screenName", "op": "eq", "value": "/napp/home"}],
        },
    })
    assert "ga_session_id IN (SELECT ga_session_id FROM" in q
    assert "(screenName = '/napp/home')" in q


def test_session_scope_column_validated():
    with pytest.raises(ValueError, match="Unknown column"):
        _q({
            "output_mode": "count_sessions", "match": "and", "conditions": [],
            "session_scope": {"match": "and", "conditions": [{"column": "evil", "op": "eq", "value": "x"}]},
        })


def test_invalid_output_mode_rejected():
    with pytest.raises(ValueError, match="output_mode"):
        _q({"output_mode": "delete_everything", "match": "and", "conditions": []})


def test_invalid_match_rejected():
    with pytest.raises(ValueError, match="match"):
        _q({"output_mode": "count_sessions", "match": "nand", "conditions": []})


def test_conditions_must_be_list():
    with pytest.raises(ValueError, match="conditions must be a list"):
        _q({"output_mode": "count_sessions", "match": "and", "conditions": "nope"})


def test_metadata_reports_shape():
    result = build_custom_query({
        "output_mode": "count_sessions", "match": "and",
        "conditions": [{"column": "event_name", "op": "eq", "value": "interaction"}],
        "group_by": "screenName",
    }, "2026-01-01", end_date="2026-01-31")
    assert result["metadata"]["output_mode"] == "count_sessions"
    assert result["metadata"]["condition_count"] == 1
    assert result["metadata"]["group_by"] == "screenName"


def test_custom_table_name_used():
    q = build_custom_query(
        {"output_mode": "count_sessions", "match": "and", "conditions": []},
        "2026-01-01", end_date="2026-01-31",
        schema_config={"table_name": "my_catalog.my_schema.my_table"},
    )["query"]
    assert "FROM my_catalog.my_schema.my_table" in q
