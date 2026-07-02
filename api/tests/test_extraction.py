import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api._lib.extraction import extract_map

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "svg")


def _read(relative_path):
    with open(os.path.join(FIXTURES, relative_path), "rb") as f:
        return f.read()


def test_extract_simple_header_svg():
    result = extract_map(_read("simple_header.svg"), mode="header")
    assert result["ok"] is True
    assert result["report"]["events_extracted"] == 2
    assert result["report"]["events_by_type"] == {"screen_view": 1, "interaction": 1}
    spec = result["spec"]
    assert len(spec) == 2
    assert spec[0]["name"] == "screen_view"
    assert spec[0]["sn"] == "/napp/home"
    assert spec[0]["ct"] == "b2c_ecare_napp"
    assert spec[1]["name"] == "interaction"
    assert spec[1]["ac"] == "screen_click_button"
    assert spec[1]["lb"] == "test_button"


def test_extract_wrapped_lines_svg():
    result = extract_map(_read("wrapped_lines.svg"), mode="header")
    assert result["ok"] is True
    assert result["report"]["events_extracted"] == 2
    spec = result["spec"]
    assert spec[0]["sn"] == "/napp/recharge/start"
    assert spec[1]["ac"] == "screen_click_button"
    assert spec[1]["lb"] == "continue_recharge"


def test_extract_badge_test_svg():
    result = extract_map(_read("badge_test.svg"), mode="header")
    assert result["ok"] is True
    assert result["report"]["events_extracted"] == 2
    assert result["report"]["badges_found"] == 2


def test_extract_empty_svg_returns_empty_spec():
    result = extract_map(_read("edge_cases/empty.svg"), mode="header")
    assert result["ok"] is True
    assert result["spec"] == []
    assert result["report"]["events_extracted"] == 0


def test_extract_no_headers_svg_returns_empty_spec():
    result = extract_map(_read("edge_cases/no_headers.svg"), mode="header")
    assert result["ok"] is True
    assert result["spec"] == []


def test_extract_malformed_svg_returns_friendly_error():
    result = extract_map(_read("edge_cases/malformed.svg"), mode="header")
    assert result["ok"] is False
    assert "error" in result


def test_extract_invalid_mode_returns_error():
    result = extract_map(_read("simple_header.svg"), mode="bogus")
    assert result["ok"] is False
    assert "error" in result


def test_extract_card_mode_with_synthetic_cards():
    result = extract_map(_read("card_test.svg"), mode="card")
    assert result["ok"] is True
    assert result["report"]["events_extracted"] == 2
    assert result["report"]["cards_used"] == 2
    spec = result["spec"]
    assert len(spec) == 2
    assert spec[0]["name"] == "screen_view"
    assert spec[0]["sn"] == "/napp/test-card"
    assert spec[0]["ct"] == "b2c_ecare_napp"
    assert spec[1]["name"] == "interaction"
    assert spec[1]["ac"] == "screen_click_button"
    assert spec[1]["lb"] == "test_button"
