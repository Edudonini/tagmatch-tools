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


# --- event_order normalization (regression: real maps can have events with no
# event_order; the builders int() it, and a blanket fillna("") turned the
# missing value into "" which defeated their pd.notna guard -> int("")). ---

def test_parse_normalizes_missing_event_order_to_int():
    spec = [
        {"name": "screen_view", "event_order": 1, "sn": "/napp/home", "ct": "b2c_ecare_napp"},
        {"name": "interaction", "event_order": None, "sn": "/napp/home", "ac": "screen_click_button", "lb": "btn"},
    ]
    events = parse_spec_file("spec.json", json.dumps(spec).encode())
    assert events[0]["event_order"] == 1
    # missing event_order backfilled to a valid 1-based int (idx+1), not ""
    assert events[1]["event_order"] == 2
    assert isinstance(events[1]["event_order"], int)


def test_build_query_with_missing_event_order_succeeds():
    spec = [
        {"name": "screen_view", "event_order": 1, "sn": "/napp/home", "ct": "b2c_ecare_napp",
         "sn_regex": "^/napp/home$", "ct_regex": "^b2c_ecare_napp$"},
        {"name": "interaction", "event_order": None, "sn": "/napp/home", "ct": "b2c_ecare_napp",
         "ac": "screen_click_button", "lb": "btn", "sn_regex": "^/napp/home$",
         "ac_regex": "^screen_click_button$", "lb_regex": "^btn$", "ct_regex": "^b2c_ecare_napp$"},
    ]
    events = parse_spec_file("spec.json", json.dumps(spec).encode())
    result = build_query(events, "validation", BASE_OPTIONS)
    assert result["ok"] is True, result.get("error")
    assert "2" in result["event_mapping"]


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

def test_build_query_custom_count_sessions():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "count_sessions",
                   "filter": {"match": "and", "groups": [
                       {"match": "and", "conditions": [{"column": "event_name", "op": "eq", "value": "interaction"}]}]}},
    })
    assert result["ok"] is True
    assert "COUNT(DISTINCT ga_session_id) AS session_count" in result["query"]
    assert result["event_mapping"] == {}
    assert result["metadata"]["output_mode"] == "count_sessions"


def test_build_query_custom_extract_with_session_scope():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "extract",
                   "filter": {"match": "and", "groups": [
                       {"match": "and", "conditions": [{"column": "screenName", "op": "eq", "value": "/napp/fatura"}]}]},
                   "session_scope": {"match": "and", "conditions": [{"column": "screenName", "op": "eq", "value": "/napp/home"}]},
                   "output_columns": ["event_name", "screenName"], "limit": 100}})
    assert result["ok"] is True
    assert "ga_session_id IN (SELECT ga_session_id FROM" in result["query"]
    assert "LIMIT 100" in result["query"]


def test_build_query_custom_rejects_unknown_column_as_400_not_500():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "count_sessions",
                   "filter": {"match": "and", "groups": [
                       {"match": "and", "conditions": [{"column": "evil; DROP TABLE x", "op": "eq", "value": "1"}]}]}}})
    assert result["ok"] is False
    assert "Unknown column" in result["error"]


def test_build_query_custom_missing_payload_errors_cleanly():
    result = build_query([], "custom", {"start_date": "2026-01-01", "end_date": "2026-01-31"})
    assert result["ok"] is False
    assert result["error"]  # a non-empty user-readable message, not a crash


def test_build_query_custom_uses_table_override():
    result = build_query(
        [],
        "custom",
        {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "table_name": "cat.sch.tbl",
            "custom": {"output_mode": "count_events", "filter": {"match": "and", "groups": []}},
        },
    )
    assert result["ok"] is True
    assert "FROM cat.sch.tbl" in result["query"]


def test_build_query_custom_funnel_ok():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "funnel", "funnel": {"steps": [
            {"match": "and", "conditions": [{"column": "event_name", "op": "eq", "value": "screen_view"}]},
            {"match": "and", "conditions": [{"column": "event_name", "op": "eq", "value": "interaction"}]},
        ]}},
    })
    assert result["ok"] is True
    assert result["query"].startswith("WITH base AS (")
    assert result["metadata"]["output_mode"] == "funnel"
    assert result["metadata"]["step_count"] == 2


def test_build_query_custom_funnel_one_step_is_400_not_500():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "funnel", "funnel": {"steps": [
            {"match": "and", "conditions": [{"column": "event_name", "op": "eq", "value": "screen_view"}]},
        ]}},
    })
    assert result["ok"] is False
    assert "2 etapas" in result["error"]


def test_build_query_custom_aggregate_metrics_ok():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "aggregate",
                   "aggregate": {"metrics": [{"func": "sum", "column": "value"}, {"func": "count", "column": None}]},
                   "group_by": ["screenName"]},
    })
    assert result["ok"] is True
    assert "SUM(value) AS sum_value, COUNT(*) AS total" in result["query"]
    assert result["metadata"]["metric_count"] == 2


def test_build_query_custom_aggregate_empty_metrics_is_400_not_500():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "aggregate", "aggregate": {"metrics": []}},
    })
    assert result["ok"] is False
    assert "métrica" in result["error"]


def test_build_query_custom_aggregate_bad_alias_is_400_not_500():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "aggregate",
                   "aggregate": {"metrics": [{"func": "sum", "column": "value", "alias": "1; DROP"}]}},
    })
    assert result["ok"] is False
    assert "Alias inválido" in result["error"]


def test_build_query_custom_aggregate_hour_bucket_ok():
    result = build_query([], "custom", {
        "start_date": "2026-01-01", "end_date": "2026-01-31",
        "custom": {"output_mode": "aggregate",
                   "aggregate": {"metrics": [{"func": "count", "column": None}]},
                   "time_bucket": {"unit": "hour"}},
    })
    assert result["ok"] is True
    assert "date_trunc('HOUR', event_timestamp)" in result["query"]


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
