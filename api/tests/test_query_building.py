import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api._lib.query_building import parse_spec_file, build_query, VALID_QUERY_TYPES

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "spec")


def _read(name):
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def _events():
    return parse_spec_file("spec_sample.json", _read("spec_sample.json"))


BASE_OPTIONS = {"start_date": "2026-07-01", "end_date": "2026-07-06", "count_mode": "session"}


# --- parse_spec_file ---

def test_parse_json():
    events = _events()
    assert len(events) == 2
    assert events[0]["name"] == "screen_view"
    assert events[0]["sn"] == "/napp/test-card"
    assert events[1]["ac"] == "screen_click_button"


def test_parse_csv_matches_json():
    from_csv = parse_spec_file("spec_sample.csv", _read("spec_sample.csv"))
    assert len(from_csv) == 2
    assert from_csv[0]["name"] == "screen_view"
    assert from_csv[0]["sn"] == "/napp/test-card"
    # Empty CSV cells come back as empty strings, not NaN/None
    assert from_csv[0]["ac"] == ""
    assert from_csv[1]["event_order"] == 2


def test_parse_csv_output_is_json_serializable():
    # pd.read_csv yields numpy int64 values, which Flask's jsonify cannot
    # serialize - parse_spec_file must return plain Python types.
    from_csv = parse_spec_file("spec_sample.csv", _read("spec_sample.csv"))
    json.dumps(from_csv)  # raises TypeError if numpy types leak through
    assert type(from_csv[1]["event_order"]) is int


def test_parse_rejects_invalid_json():
    try:
        parse_spec_file("bad.json", b"{not json")
        assert False, "should have raised"
    except ValueError:
        pass


def test_parse_rejects_missing_name_column():
    try:
        parse_spec_file("x.json", json.dumps([{"event_order": 1}]).encode())
        assert False, "should have raised"
    except ValueError:
        pass


def test_parse_rejects_empty_spec():
    try:
        parse_spec_file("x.json", b"[]")
        assert False, "should have raised"
    except ValueError:
        pass


def test_parse_rejects_unsupported_extension():
    try:
        parse_spec_file("x.svg", b"<svg/>")
        assert False, "should have raised"
    except ValueError:
        pass


# --- build_query: validation ---

def test_validation_query():
    result = build_query(_events(), "validation", {**BASE_OPTIONS, "sample_per_event": 5})
    assert result["ok"] is True
    assert result["event_mapping"] == {"1": "View - Test-card", "2": "Clique - Button"}
    assert result["metadata"]["events_classified"] == 2
    q = result["query"]
    assert "FROM ecare_silver.b2c_ga4.silver_ga4_novo_app" in q
    assert "WHERE data BETWEEN '2026-07-01' AND '2026-07-06'" in q
    assert "THEN 'View - Test-card -- 1'" in q
    assert "THEN 'Clique - Button -- 2'" in q
    assert "row_num <= 5" in q


# --- build_query: volumetry ---

def test_volumetry_query_session_mode():
    result = build_query(_events(), "volumetry", {**BASE_OPTIONS, "group_by": "event", "include_event_count": True})
    assert result["ok"] is True
    assert "COUNT(DISTINCT ga_session_id)" in result["query"]
    assert result["metadata"]["group_by"] == "event"
    assert result["metadata"]["count_mode"] == "session"
    assert result["event_mapping"] == {"1": "View - Test-card", "2": "Clique - Button"}


# --- build_query: funnel ---

def test_funnel_query():
    result = build_query(_events(), "funnel", {**BASE_OPTIONS, "screen_order": ["/napp/test-card"]})
    assert result["ok"] is True
    assert result["metadata"]["funnel_steps"] == 2
    assert "THEN 'View - Test-card -- 1'" in result["query"]
    assert "COUNT(DISTINCT ga_session_id)" in result["query"]


# --- build_query: custom ---

def test_custom_query():
    result = build_query(
        _events(),
        "custom",
        {
            **BASE_OPTIONS,
            "selected_event_orders": [1, 2],
            "filter_fields_per_event": {"1": ["sn"], "2": ["ac", "lb"]},
            "output_columns": ["event_name", "screenName"],
        },
    )
    assert result["ok"] is True
    assert result["metadata"]["events_selected"] == 2
    q = result["query"]
    assert "THEN 'spec_1'" in q
    assert "THEN 'spec_2'" in q
    assert "screenName" in q
    assert "FROM ecare_silver.b2c_ga4.silver_ga4_novo_app" in q


# --- table override + validation ---

def test_table_name_override():
    result = build_query(_events(), "validation", {**BASE_OPTIONS, "table_name": "outro_schema.tabela.x"})
    assert result["ok"] is True
    assert "FROM outro_schema.tabela.x" in result["query"]
    assert "ecare_silver.b2c_ga4.silver_ga4_novo_app" not in result["query"]


def test_invalid_table_name_rejected():
    result = build_query(_events(), "validation", {**BASE_OPTIONS, "table_name": "bad; DROP TABLE x"})
    assert result["ok"] is False
    assert "table" in result["error"].lower()


def test_custom_rejects_injected_output_column():
    result = build_query(
        _events(),
        "custom",
        {**BASE_OPTIONS, "selected_event_orders": [1], "output_columns": ["event_name, (SELECT 1) --"]},
    )
    assert result["ok"] is False
    assert "output column" in result["error"].lower()


def test_custom_rejects_injected_filter_field():
    result = build_query(
        _events(),
        "custom",
        {
            **BASE_OPTIONS,
            "selected_event_orders": [1],
            "filter_fields_per_event": {"1": ["sn); DROP TABLE x; --"]},
            "output_columns": ["event_name"],
        },
    )
    assert result["ok"] is False
    assert "filter field" in result["error"].lower()


# --- error paths ---

def test_invalid_query_type():
    result = build_query(_events(), "bogus", BASE_OPTIONS)
    assert result["ok"] is False
    assert "bogus" in result["error"]


def test_invalid_date_rejected():
    result = build_query(_events(), "validation", {**BASE_OPTIONS, "start_date": "07/01/2026"})
    assert result["ok"] is False
    assert "date" in result["error"].lower()


def test_missing_start_date_rejected():
    result = build_query(_events(), "validation", {"count_mode": "session"})
    assert result["ok"] is False


def test_valid_query_types_constant():
    assert VALID_QUERY_TYPES == ("validation", "volumetry", "funnel", "custom")
