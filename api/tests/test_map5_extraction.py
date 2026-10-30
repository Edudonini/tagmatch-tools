import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from api._lib.map5_extraction import (
    card_params, extract_cards_5_0, reparse_5_0, split_params, _path_bbox,
)

# Real merged card text from the 5.0 test map.
INTERACTION_RAW = (
    "sn:/[nappoueasy]/hub-payment/insert-card-data/failed-invalid-card-error\n"
    "ct:b2x_ecare_[nappoueasy]_hubPayment\nac:screen_click_button\n"
    "lb:[elementText]_failedInvalidCardError\nclient_category:[categoriaDoCliente]\n"
    "error_type:[usuario|negocio|aplicativo]error_status=[bloqueado|continue]\n"
    "event_cnpj:[cnpjVinculado]\n"
    "info_detail:[telaDeOrigem]department=comercialmacro_journey=[traducao_do_journey_variant]"
    "micro_journey=hub_de_pagamentosevent_detail=clique_botao_[element_text]status_journey=erro"
    "error_code=[codigodoerro]\n"
    "journeyvariant:[jornadaDeOrigem]crm_name:[nomeDaBase]\norigin_nv:[origemDoEntryPoint]\n"
    "payment_method:[metodoDePagamentoSelecionado]\n"
    "plan_name:[nomeDoPlano]event_plan_type:[tipoDoPlano]"
)


def test_split_unmerges_all_fields():
    p = split_params(INTERACTION_RAW)
    # the info_detail run splits into its 7 distinct fields
    assert p["info_detail"] == "[telaDeOrigem]"
    assert p["department"] == "comercial"
    assert p["macro_journey"] == "[traducao_do_journey_variant]"
    assert p["micro_journey"] == "hub_de_pagamentos"
    assert p["event_detail"] == "clique_botao_[element_text]"
    assert p["status_journey"] == "erro"
    assert p["error_code"] == "[codigodoerro]"
    # colon+equals mixed pairs split too
    assert p["error_type"] == "[usuario|negocio|aplicativo]"
    assert p["error_status"] == "[bloqueado|continue]"
    assert p["journeyVariant"] == "[jornadaDeOrigem]"  # canonical casing, even though raw was lowercased
    assert p["crm_name"] == "[nomeDaBase]"
    assert p["plan_name"] == "[nomeDoPlano]"
    assert p["event_plan_type"] == "[tipoDoPlano]"
    # legacy fields preserved
    assert p["sn"] == "/[nappoueasy]/hub-payment/insert-card-data/failed-invalid-card-error"
    assert p["ct"] == "b2x_ecare_[nappoueasy]_hubPayment"
    assert p["ac"] == "screen_click_button"


def test_split_keeps_field_name_inside_placeholder_as_value():
    # a known field name inside a [a|b|c] option list is NOT a boundary
    p = split_params("client_category:[adm_prin|adm|tec|cob|soc|b2c_not-apply]\norigin_nv:home")
    assert p["client_category"] == "[adm_prin|adm|tec|cob|soc|b2c_not-apply]"
    assert p["origin_nv"] == "home"


def test_split_ignores_field_marker_inside_placeholder():
    # a `field:`/`field=` token INSIDE `[...]` is part of the value, not a boundary —
    # the bracket-depth filter must suppress it (a real `:`/`=` inside the brackets,
    # unlike the `|`-only option lists above).
    # `event:` and `value=` are real known fields, here nested inside the placeholder.
    p = split_params("info_detail:[event:x,value=y]\ndepartment:comercial")
    assert p["info_detail"] == "[event:x,value=y]"
    assert p["department"] == "comercial"
    assert "event" not in p  # the inner `event:` did not open a new field
    assert "value" not in p  # the inner `value=` did not open a new field


def test_split_emits_canonical_field_casing():
    # keys carry the taxonomy's canonical casing even when the raw card lowercased them —
    # the tool header reads params.screenName directly, so this contract must hold.
    p = split_params("screenname:/hub-payment/insert-card\njourneyvariant:[jornada]")
    assert p["screenName"] == "/hub-payment/insert-card"
    assert p["journeyVariant"] == "[jornada]"
    assert "screenname" not in p and "journeyvariant" not in p


def test_split_recognizes_supported_keys_fields():
    # Real collapse case from a 5.0 map: title/module_name/position/tag_label are in the
    # parser's SUPPORTED_KEYS, so the re-parser must split them, not swallow them into the
    # previous field's value.
    raw = ("event_cnpj:[area_da_jornada]\ntitle:[titulo_principal]\n"
           "module_name:hub_pagamentos\nposition:2\ntag_label:[rotulo]")
    p = split_params(raw)
    assert p["event_cnpj"] == "[area_da_jornada]"  # no longer swallows title
    assert p["title"] == "[titulo_principal]"
    assert p["module_name"] == "hub_pagamentos"
    assert p["position"] == "2"
    assert p["tag_label"] == "[rotulo]"


def test_split_longest_name_precedence():
    p = split_params("event_detail:clique_x\nevent:interaction")
    assert p["event_detail"] == "clique_x"
    assert p["event"] == "interaction"


def test_split_duplicate_first_wins():
    p = split_params("department:comercial\ndepartment:financeiro")
    assert p["department"] == "comercial"


def test_split_carries_unknown_enum_value_verbatim():
    # component_type:bottomSheet is off-enum but must be carried as-is (Phase 2 flags it)
    p = split_params("component_type:bottomSheet\ndescription:querRemoverOCartao")
    assert p["component_type"] == "bottomSheet"
    assert p["description"] == "querRemoverOCartao"


def test_reparse_shapes_events():
    spec = [{
        "name": "interaction", "event_order": 40.0, "raw_lines": INTERACTION_RAW,
        "_bbox_x1": 1.0, "_bbox_y1": 2.0, "_bbox_x2": 3.0, "_bbox_y2": 4.0,
    }]
    out = reparse_5_0(spec)[0]
    assert out["event_type"] == "interaction"       # from color-detected name (no explicit event: line)
    assert out["event_order"] == 40.0
    assert out["bbox"] == {"_bbox_x1": 1.0, "_bbox_y1": 2.0, "_bbox_x2": 3.0, "_bbox_y2": 4.0}
    assert out["params"]["department"] == "comercial"


def test_reparse_prefers_explicit_event_field():
    out = reparse_5_0([{"name": "screen_view", "raw_lines": "event:interaction\nsn:/x"}])[0]
    assert out["event_type"] == "interaction"


def test_reparse_empty_spec():
    assert reparse_5_0([]) == []


def test_reparse_rebuckets_lines_by_bbox():
    # The base parser's raw_lines dropped fields on this layout; re-bucketing the raw text
    # lines inside the event's bbox recovers them. Lines outside the bbox are excluded.
    spec = [{
        "name": "screen_view", "event_order": 1.0,
        "_bbox_x1": 0.0, "_bbox_y1": 0.0, "_bbox_x2": 100.0, "_bbox_y2": 100.0,
        "raw_lines": "sn:profile",  # broken/partial from the parser
    }]
    lines = [
        {"x": 10, "y": 10, "text": "event: screen_view"},
        {"x": 10, "y": 20, "text": "screenName: profile"},
        {"x": 10, "y": 30, "text": "macro_journey: menu_perfil"},
        {"x": 999, "y": 999, "text": "department: fora_do_bbox"},  # outside → not bucketed
    ]
    out = reparse_5_0(spec, lines)
    assert len(out) == 1
    p = out[0]["params"]
    assert p["event"] == "screen_view"
    assert p["screenName"] == "profile"
    assert p["macro_journey"] == "menu_perfil"
    assert "department" not in p  # the outside-bbox line was excluded


def test_reparse_noise_filter_drops_legacy_only_card():
    # a scratch/placeholder card carrying only a legacy sn is not a real event
    spec = [{"name": "screen_view", "event_order": None,
             "_bbox_x1": 0.0, "_bbox_y1": 0.0, "_bbox_x2": 50.0, "_bbox_y2": 50.0,
             "raw_lines": "sn:Thundercats"}]
    lines = [{"x": 10, "y": 10, "text": "sn: Thundercats"}]
    assert reparse_5_0(spec, lines) == []


def test_reparse_tightest_bbox_wins():
    # a line inside two overlapping bboxes is assigned to the smaller (tightest) one
    spec = [
        {"name": "screen_view", "event_order": 1,
         "_bbox_x1": 0.0, "_bbox_y1": 0.0, "_bbox_x2": 200.0, "_bbox_y2": 200.0, "raw_lines": ""},
        {"name": "interaction", "event_order": 2,
         "_bbox_x1": 0.0, "_bbox_y1": 0.0, "_bbox_x2": 50.0, "_bbox_y2": 50.0, "raw_lines": ""},
    ]
    lines = [{"x": 10, "y": 10, "text": "component_type: button"}]
    out = reparse_5_0(spec, lines)
    # the smaller (interaction) box claims the line; the empty screen_view is noise-filtered
    assert len(out) == 1 and out[0]["event_type"] == "interaction"
    assert out[0]["params"]["component_type"] == "button"


def test_reparse_without_lines_uses_raw_lines():
    # backward compatibility: no lines → split the parser's raw_lines as before
    spec = [{"name": "interaction", "event_order": 1,
             "raw_lines": "event:interaction\ncomponent_type:button"}]
    out = reparse_5_0(spec)
    assert len(out) == 1 and out[0]["params"]["component_type"] == "button"


import importlib.util


def _endpoint_client():
    path = os.path.join(os.path.dirname(__file__), "..", "extract-5.0.py")
    spec = importlib.util.spec_from_file_location("extract_5_0_ep", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app.test_client()


def test_endpoint_missing_file_is_400():
    r = _endpoint_client().post("/api/extract-5.0")
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_endpoint_bad_svg_is_400_not_500():
    import io
    data = {"file": (io.BytesIO(b"not an svg"), "x.svg")}
    r = _endpoint_client().post("/api/extract-5.0", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


# --- Structural card reader (extract_cards_5_0) ---

FIXTURE_SVG = os.path.join(os.path.dirname(__file__), "fixtures", "svg", "map5_cards.svg")


def _fixture_events():
    with open(FIXTURE_SVG, "rb") as f:
        return extract_cards_5_0(f.read())


def test_cards_reads_each_shape_as_one_event():
    events = _fixture_events()
    # the note (one taxonomy field) and the legend card (all placeholders, no badge) are dropped
    assert [e["event_type"] for e in events] == ["screen_view", "interaction"]


def test_cards_badge_gives_event_order():
    sv, inter = _fixture_events()
    assert sv["event_order"] == 7
    assert inter["event_order"] is None  # no badge above the interaction card


def test_cards_joins_soft_wrapped_runs():
    sv, inter = _fixture_events()
    assert inter["params"]["sn"] == "/[napp ou easy]/hub-payment/insert-card-data/failed-invalid-card-error"
    assert inter["params"]["lb"] == "[tipo de erro]&[blocker ou nonBlocker]&cartaoInvalido"
    assert sv["params"]["macro_journey"] == "[jornada_de_origem]"
    assert sv["params"]["journeyVariant"] == "[jornadaDeOrigem] *VERIFICAR*"


def test_cards_crmname_is_not_split_into_name():
    sv, _ = _fixture_events()
    assert sv["params"]["crmName"] == "[siebel|next]"
    assert "name" not in sv["params"]
    assert sv["params"]["department"] == "comercial"


def test_cards_unknown_leading_field_is_its_own_param():
    _, inter = _fixture_events()
    assert inter["params"]["custom_flag"] == "sim"
    assert inter["params"]["status_journey"] == "erro"  # not swallowing the unknown field


def test_cards_manual_line_break_splits_fields():
    # Shift+Enter inside one paragraph is exported as a `\n` run; the unknown field after it
    # must still become its own param instead of being glued to the previous value
    _, inter = _fixture_events()
    assert inter["params"]["ac"] == "screen_click_button"
    assert inter["params"]["other_flag"] == "nao"


def test_cards_bbox_from_outline_path():
    sv, inter = _fixture_events()
    assert sv["bbox"] == {"_bbox_x1": 100.0, "_bbox_y1": 100.0, "_bbox_x2": 775.0, "_bbox_y2": 540.0}
    assert inter["bbox"] == {"_bbox_x1": 1000.0, "_bbox_y1": 100.0, "_bbox_x2": 1400.0, "_bbox_y2": 700.0}


def test_cards_invalid_xml_raises_value_error():
    with pytest.raises(ValueError):
        extract_cards_5_0(b"not an svg")


def test_card_params_continuation_paragraph_appends_to_previous_field():
    p = card_params(["event_detail = ", "visualizacao_erro", "status_journey: erro"])
    assert p == {"event_detail": "visualizacao_erro", "status_journey": "erro"}


def test_path_bbox_relative_commands():
    assert _path_bbox("M10,20h30v40h-30z") == (10.0, 20.0, 40.0, 60.0)
    assert _path_bbox("") is None


def test_endpoint_uses_structural_reader():
    import io
    with open(FIXTURE_SVG, "rb") as f:
        data = {"file": (io.BytesIO(f.read()), "map.svg")}
    r = _endpoint_client().post("/api/extract-5.0", data=data, content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200 and body["ok"] is True
    assert [e["event_type"] for e in body["events"]] == ["screen_view", "interaction"]
