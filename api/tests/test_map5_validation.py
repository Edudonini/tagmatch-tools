import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import io
import importlib.util

from api._lib.map5_validation import validate_events, is_dynamic


def _ev(event_type, **params):
    return {"event_type": event_type, "event_order": 1, "bbox": {}, "params": params}


# a fully-valid screen_view (all required, valid enums, snake_case)
_GOOD_SV = dict(
    event="screen_view", screenName="/hub-pagamentos/inserir-cartao", origin_nv="home",
    event_access_type="[vivo|b2c|b2b_c|b2b_m]", client_category="[adm|tec]",
    department="comercial", macro_journey="hub_pagamentos", micro_journey="inserir_cartao",
    event_detail="visualizacao_inserir_cartao", status_journey="sucesso",
    info_detail="detalhe_informativo",
)


def test_good_screen_view_is_green():
    r = validate_events([_ev("screen_view", **_GOOD_SV)])
    assert r["summary"]["green"] == 1 and r["summary"]["red"] == 0 and r["summary"]["amber"] == 0
    assert r["summary"]["adherence_pct"] == 100
    assert len(r["approved"]) == 1


def test_missing_required_is_red():
    p = dict(_GOOD_SV)
    del p["event_detail"]
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "completeness" and f["field"] == "event_detail" and f["severity"] == "red"
               for f in r["findings"])
    assert r["summary"]["red"] == 1


def test_interaction_requires_component_fields():
    p = dict(_GOOD_SV, event="interaction")
    r = validate_events([_ev("interaction", **p)])
    fields = {f["field"] for f in r["findings"] if f["category"] == "completeness"}
    assert "component_type" in fields and "component_copy" in fields


def test_legacy_field_is_red():
    p = dict(_GOOD_SV, sn="/napp/old/path")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "legacy" and f["field"] == "sn" and f["severity"] == "red"
               for f in r["findings"])


def test_napp_in_screenname_is_red():
    p = dict(_GOOD_SV, screenName="/napp/hub-pagamentos/x")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "legacy" and f["field"] == "screenName" for f in r["findings"])


def test_enum_option_list_flags_only_bad_option():
    p = dict(_GOOD_SV, status_journey="sucesso | erro | banana")
    r = validate_events([_ev("screen_view", **p)])
    enum_findings = [f for f in r["findings"] if f["category"] == "enum" and f["field"] == "status_journey"]
    assert len(enum_findings) == 1
    assert "banana" in enum_findings[0]["problem"] and "sucesso" not in enum_findings[0]["problem"]


def test_bracketed_option_list_is_validated():
    # options listed inside [...] are checked; all valid here → no enum finding
    p = dict(_GOOD_SV, event_access_type="[vivo|b2c|b2b_c|b2b_m]")
    r = validate_events([_ev("screen_view", **p)])
    assert not any(f["category"] == "enum" and f["field"] == "event_access_type" for f in r["findings"])


def test_event_must_not_be_dynamic():
    p = dict(_GOOD_SV, event="[screen_view]")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "dynamic_fixed" and f["field"] == "event" and f["severity"] == "red"
               for f in r["findings"])


def test_accented_fixed_value_is_amber_nomenclature():
    p = dict(_GOOD_SV, department="comércio")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "nomenclature" and f["field"] == "department" and f["severity"] == "amber"
               for f in r["findings"])


def test_dynamic_placeholder_is_not_nomenclature_error():
    p = dict(_GOOD_SV, department="[area_da_jornada]")
    r = validate_events([_ev("screen_view", **p)])
    assert not any(f["category"] == "nomenclature" and f["field"] == "department" for f in r["findings"])


def test_error_context_without_error_fields_is_amber_conditional():
    p = dict(_GOOD_SV, status_journey="erro")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "conditional" and f["severity"] == "amber" for f in r["findings"])


def test_event_detail_without_underscore_is_amber():
    p = dict(_GOOD_SV, event_detail="visualizacao")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "event_detail_format" and f["severity"] == "amber" for f in r["findings"])


def test_uninferable_placeholder_becomes_open_question():
    p = dict(_GOOD_SV, event_access_type="[contexto_do_usuario]")
    r = validate_events([_ev("screen_view", **p)])
    assert any(q["field"] == "event_access_type" for q in r["open_questions"])
    # ...and NOT an enum finding
    assert not any(f["category"] == "enum" and f["field"] == "event_access_type" for f in r["findings"])


def test_summary_math_and_semantic_note():
    good = _ev("screen_view", **_GOOD_SV)
    bad = _ev("screen_view", **{k: v for k, v in _GOOD_SV.items() if k != "event_detail"})
    r = validate_events([good, bad])
    assert r["summary"]["total"] == 2 and r["summary"]["green"] == 1 and r["summary"]["red"] == 1
    assert r["summary"]["adherence_pct"] == 50
    # a global manual-review note is always appended when there are events
    assert any(q["field"] == "coerência semântica" for q in r["open_questions"])


def test_is_dynamic():
    assert is_dynamic("[x]") and is_dynamic("{{y}}") and is_dynamic("a | b") and is_dynamic("pre/pos")
    assert not is_dynamic("sucesso") and not is_dynamic("")


def test_validate_events_non_list_raises():
    import pytest
    with pytest.raises(ValueError):
        validate_events("nope")


def _endpoint_client():
    path = os.path.join(os.path.dirname(__file__), "..", "validate-5.0.py")
    spec = importlib.util.spec_from_file_location("validate_5_0_ep", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app.test_client()


def test_endpoint_missing_file_is_400():
    r = _endpoint_client().post("/api/validate-5.0")
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_endpoint_bad_svg_is_400_not_500():
    data = {"file": (io.BytesIO(b"not an svg"), "x.svg")}
    r = _endpoint_client().post("/api/validate-5.0", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


def test_component_type_alert_is_valid_no_enum_finding():
    p = dict(_GOOD_SV, event="interaction", component_type="alert", component_copy="[texto]")
    r = validate_events([_ev("interaction", **p)])
    assert not any(f["category"] == "enum" and f["field"] == "component_type" for f in r["findings"])
    assert r["summary"]["green"] == 1 and r["summary"]["red"] == 0 and r["summary"]["amber"] == 0


def test_component_type_invalid_value_is_red_enum():
    p = dict(_GOOD_SV, event="interaction", component_type="foo", component_copy="[texto]")
    r = validate_events([_ev("interaction", **p)])
    assert any(f["category"] == "enum" and f["field"] == "component_type" and f["severity"] == "red"
               for f in r["findings"])


def test_product_context_missing_event_plan_type_is_amber_conditional():
    p = dict(_GOOD_SV, plan_name="controle_top")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "conditional" and f["severity"] == "amber" for f in r["findings"])


def test_screen_name_not_starting_with_slash_is_amber_nomenclature():
    p = dict(_GOOD_SV, screenName="hub/x")
    r = validate_events([_ev("screen_view", **p)])
    assert any(f["category"] == "nomenclature" and f["field"] == "screenName" and f["severity"] == "amber"
               for f in r["findings"])


def test_fixed_passthrough_field_is_not_checked_for_nomenclature():
    p = dict(_GOOD_SV, title="Inserir Cartao")
    r = validate_events([_ev("screen_view", **p)])
    assert not any(f["category"] == "nomenclature" and f["field"] == "title" for f in r["findings"])
    assert r["summary"]["green"] == 1 and r["summary"]["red"] == 0 and r["summary"]["amber"] == 0


def _events_of(result):
    return {(e["event_type"], e["event_order"]): e for e in result["events"]}


def _row(event, field):
    return next((r for r in event["fields"] if r["field"] == field), None)


def test_events_green_lists_required_as_ok():
    r = validate_events([_ev("screen_view", **_GOOD_SV)])
    ev = r["events"][0]
    assert ev["verdict"] == "green"
    # every required screen_view field is present as an ok row
    for f in ["event", "screenName", "origin_nv", "event_access_type", "client_category",
              "department", "macro_journey", "micro_journey", "event_detail", "status_journey"]:
        row = _row(ev, f)
        assert row is not None and row["status"] == "ok"


def test_events_missing_required_row_is_missing_with_reason():
    p = {k: v for k, v in _GOOD_SV.items() if k != "origin_nv"}
    r = validate_events([_ev("screen_view", **p)])
    row = _row(r["events"][0], "origin_nv")
    assert row["status"] == "missing" and row["value"] == "" and "obrigat" in row["reason"].lower()


def test_events_enum_row_shows_bad_value_and_reason():
    p = dict(_GOOD_SV, event="interaction", component_type="chevron_down", component_copy="[x]")
    r = validate_events([_ev("interaction", **p)])
    row = _row(r["events"][0], "component_type")
    assert row["status"] == "red" and row["value"] == "chevron_down"
    assert "enum" in row["reason"].lower()


def test_events_legacy_sn_is_extra_red_row():
    p = dict(_GOOD_SV, sn="/napp/old")
    r = validate_events([_ev("screen_view", **p)])
    row = _row(r["events"][0], "sn")
    assert row["status"] == "red" and row["value"] == "/napp/old" and "legado" in row["reason"].lower()


def test_events_extra_present_field_is_extra():
    r = validate_events([_ev("screen_view", **_GOOD_SV)])  # _GOOD_SV has info_detail (not required)
    row = _row(r["events"][0], "info_detail")
    assert row is not None and row["status"] == "extra"


def test_events_required_rows_come_first():
    r = validate_events([_ev("screen_view", **_GOOD_SV)])
    fields = [row["field"] for row in r["events"][0]["fields"]]
    assert fields[:10] == ["event", "screenName", "origin_nv", "event_access_type", "client_category",
                           "department", "macro_journey", "micro_journey", "event_detail", "status_journey"]


def test_events_conditional_emits_per_field_rows():
    p = dict(_GOOD_SV, status_journey="erro")
    r = validate_events([_ev("screen_view", **p)])
    ev = r["events"][0]
    for f in ["error_status", "error_type", "error_code"]:
        row = _row(ev, f)
        assert row is not None and row["status"] == "amber"


def test_events_counts_and_verdict():
    p = {k: v for k, v in _GOOD_SV.items() if k != "origin_nv"}
    p["department"] = "comércio"  # amber nomenclature
    ev = validate_events([_ev("screen_view", **p)])["events"][0]
    assert ev["verdict"] == "red" and ev["counts"]["red"] >= 1 and ev["counts"]["amber"] >= 1
