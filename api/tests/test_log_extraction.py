import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api._lib.log_extraction import extract_logs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "logs")


def _read(relative_path):
    with open(os.path.join(FIXTURES, relative_path), "rb") as f:
        return f.read()


def test_extract_logcat_sample():
    result = extract_logs([("logcat_sample.txt", _read("logcat_sample.txt"))])
    assert result["ok"] is True
    assert result["report"]["total_events"] == 3
    assert result["report"]["unique_events"] == 3
    assert result["report"]["duplicates_removed"] == 0
    assert result["report"]["events_by_type"] == {"noninteraction": 2, "interaction": 1}
    assert result["report"]["files"] == [
        {"filename": "logcat_sample.txt", "detected_format": "logcat", "row_count": 3, "error": None}
    ]
    logs = result["logs"]
    assert len(logs) == 3
    assert logs[0]["origin"] == "tracker"
    assert logs[0]["screenName"] == "/napp/benefits"


def test_extract_dev_json_sample():
    result = extract_logs([("dev_json_sample.txt", _read("dev_json_sample.txt"))])
    assert result["ok"] is True
    assert result["report"]["total_events"] == 5
    assert result["report"]["events_by_type"] == {
        "screen_view": 2,
        "interaction": 2,
        "noninteraction": 1,
    }
    assert result["report"]["files"][0]["detected_format"] == "dev_json"


def test_extract_firebase_sample():
    result = extract_logs([("firebase_js_sample.txt", _read("firebase_js_sample.txt"))])
    assert result["ok"] is True
    assert result["report"]["total_events"] == 3
    assert result["report"]["files"][0]["detected_format"] == "firebase_javascript"
    assert result["report"]["events_by_type"] == {
        "screen_view": 1,
        "noninteraction": 1,
        "interaction": 1,
    }


def test_extract_ndjson_sample():
    result = extract_logs([("ndjson_sample.ndjson", _read("ndjson_sample.ndjson"))])
    assert result["ok"] is True
    assert result["report"]["total_events"] == 3
    assert result["report"]["files"][0]["detected_format"] == "ndjson"


def test_extract_multi_file_merge_without_cross_dedup():
    result = extract_logs(
        [
            ("logcat_sample.txt", _read("logcat_sample.txt")),
            ("firebase_js_sample.txt", _read("firebase_js_sample.txt")),
        ]
    )
    assert result["ok"] is True
    assert result["report"]["total_events"] == 6
    assert result["report"]["unique_events"] == 6
    assert result["report"]["duplicates_removed"] == 0


def test_extract_duplicate_file_is_deduped():
    content = _read("logcat_sample.txt")
    result = extract_logs(
        [
            ("logcat_sample.txt", content),
            ("logcat_sample_copy.txt", content),
        ]
    )
    assert result["ok"] is True
    assert result["report"]["total_events"] == 6
    assert result["report"]["unique_events"] == 3
    assert result["report"]["duplicates_removed"] == 3
    assert len(result["logs"]) == 3


def test_extract_all_empty_batch_is_still_ok():
    result = extract_logs(
        [
            ("empty.txt", _read("edge_cases/empty.txt")),
            ("malformed.json", _read("edge_cases/malformed.json")),
        ]
    )
    assert result["ok"] is True
    assert result["logs"] == []
    assert result["report"]["total_events"] == 0
    assert result["report"]["unique_events"] == 0


def test_extract_rejects_unsupported_extension_per_file():
    result = extract_logs(
        [
            ("logcat_sample.txt", _read("logcat_sample.txt")),
            ("notes.pdf", b"not a log file"),
        ]
    )
    assert result["ok"] is True
    assert result["report"]["total_events"] == 3
    files_report = {f["filename"]: f for f in result["report"]["files"]}
    assert files_report["notes.pdf"]["error"] is not None
    assert files_report["notes.pdf"]["row_count"] == 0


def test_extract_all_unsupported_extensions_returns_error():
    result = extract_logs([("notes.pdf", b"nope"), ("image.png", b"nope2")])
    assert result["ok"] is False
    assert "error" in result


def test_extract_no_files_returns_error():
    result = extract_logs([])
    assert result["ok"] is False
    assert "error" in result


def test_extract_invalid_format_returns_error():
    result = extract_logs([("logcat_sample.txt", _read("logcat_sample.txt"))], format="bogus")
    assert result["ok"] is False
    assert "error" in result
