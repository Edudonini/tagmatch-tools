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
