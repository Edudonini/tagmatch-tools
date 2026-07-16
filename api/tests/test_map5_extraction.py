import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from api._lib.map5_extraction import reparse_5_0, split_params

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
    assert p["journeyvariant"] == "[jornadaDeOrigem]"
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
