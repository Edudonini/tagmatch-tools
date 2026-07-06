import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api._lib.matching import parse_records, run_matching

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "match")


def _read(name):
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def _spec(name="spec_clean.json"):
    return (name, _read(name))


def _logs(name="logs_clean.json"):
    return (name, _read(name))


# --- parse_records ---

def test_parse_json_records():
    recs = parse_records("spec_clean.json", _read("spec_clean.json"))
    assert len(recs) == 2
    assert recs[0]["name"] == "screen_view"


def test_parse_csv_records_json_safe():
    recs = parse_records("spec_clean.csv", _read("spec_clean.csv"))
    assert len(recs) == 2
    json.dumps(recs)  # numpy int64 from read_csv would raise
    assert recs[1]["ac"] == "screen_click_button"


def test_parse_rejects_invalid_json():
    try:
        parse_records("x.json", b"{not json")
        assert False
    except ValueError:
        pass


def test_parse_rejects_unsupported_extension():
    try:
        parse_records("x.svg", b"<svg/>")
        assert False
    except ValueError:
        pass


# --- run_matching: clean fixture ---

def test_match_clean_all_matched():
    result = run_matching(_spec("spec_clean.json"), _logs("logs_clean.json"))
    assert result["ok"] is True
    s = result["summary"]
    assert s["matched"] == 2
    assert s["unmatched"] == 0
    assert s["coverage_pct"] == 100.0
    assert s["extras_logs"] == 1
    assert len(result["matches"]) == 2
    assert len(result["extras"]) == 1
    assert all(m["matched"] for m in result["matches"])
    assert result["matches"][0]["confidence"] == 100.0


def test_match_clean_csv_spec():
    result = run_matching(_spec("spec_clean.csv"), _logs("logs_clean.json"))
    assert result["ok"] is True
    assert result["summary"]["matched"] == 2


# --- run_matching: mixed fixture ---

def test_match_mixed_partial_coverage():
    result = run_matching(_spec("spec_mixed.json"), _logs("logs_mixed.json"))
    assert result["ok"] is True
    s = result["summary"]
    assert s["matched"] == 2
    assert s["unmatched"] == 1
    assert s["coverage_pct"] == 66.67
    assert s["extras_logs"] == 1
    by_order = {m["event_order"]: m for m in result["matches"]}
    assert by_order[1]["matched"] is True
    assert by_order[2]["matched"] is True
    assert by_order[3]["matched"] is False
    assert by_order[3]["match_reason"] == "no_match_above_threshold"


def test_match_result_is_json_serializable():
    result = run_matching(_spec("spec_mixed.json"), _logs("logs_mixed.json"))
    json.dumps(result)  # raises if numpy types leak through
    # validation_issues stays a list, not a stringified blob
    assert isinstance(result["matches"][0]["validation_issues"], list)


# --- empty / error paths ---

def test_match_empty_logs_all_unmatched():
    result = run_matching(_spec("spec_clean.json"), ("logs.json", b"[]"))
    assert result["ok"] is True
    assert result["summary"]["matched"] == 0
    assert result["summary"]["unmatched"] == 2
    assert result["extras"] == []


def test_match_empty_spec_rejected():
    result = run_matching(("spec.json", b"[]"), _logs("logs_clean.json"))
    assert result["ok"] is False
    assert "spec" in result["error"].lower()


def test_match_spec_missing_name_rejected():
    result = run_matching(("spec.json", json.dumps([{"event_order": 1}]).encode()), _logs("logs_clean.json"))
    assert result["ok"] is False


def test_match_invalid_spec_file_rejected():
    result = run_matching(("spec.json", b"{not json"), _logs("logs_clean.json"))
    assert result["ok"] is False
