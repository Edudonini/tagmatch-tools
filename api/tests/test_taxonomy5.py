import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from api._lib.taxonomy5 import normalize, convert_events, derive_screen_name


def _endpoint_client():
    path = os.path.join(os.path.dirname(__file__), "..", "convert-taxonomy.py")
    spec = importlib.util.spec_from_file_location("convert_taxonomy_ep", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app.test_client()


def test_normalize_snake_ascii():
    assert normalize("Confirmar recarga") == "confirmar_recarga"
    # ª (ordinal indicator) NFKD-decomposes to a plain "a", so 2ª -> 2a.
    assert normalize("Emissão de 2ª via!") == "emissao_de_2a_via"
    assert normalize("já-foi/ok") == "ja_foi_ok"
    assert normalize("") == ""
    assert normalize(None) == ""


def test_derive_screen_name_strips_napp_and_kebabs():
    assert derive_screen_name("/napp/fatura", "Detalhe da Fatura", "") == "/fatura/detalhe-da-fatura"
    assert derive_screen_name("/napp/recarga", "", "Seleção do valor") == "/recarga/selecao-do-valor"
    assert derive_screen_name("/napp/suporte-tecnico", None, None) == "/suporte-tecnico/"


def test_derive_screen_name_keeps_full_multi_segment_path():
    # the whole old sn path is preserved (not just the first segment), napp/easy stripped
    assert derive_screen_name("/napp/hub-payment/insert-card-data", "x", "") == "/hub-payment/insert-card-data"
    assert derive_screen_name("/easy/hub-payment/insert-card-data", None, None) == "/hub-payment/insert-card-data"


def _one(name="screen_view", sn="/napp/fatura", ct="b2c_ecare_napp_fatura", ac="", lb="",
         screen_name="Detalhe da Fatura", screen_description="Consulta da fatura", order=1):
    return {"name": name, "sn": sn, "ct": ct, "ac": ac, "lb": lb,
            "screen_name": screen_name, "screen_description": screen_description, "event_order": order}


def _fields(ev):
    return {k: v["value"] for k, v in ev["fields"].items()}


def test_convert_screen_view_base():
    out = convert_events([_one()])[0]
    f = _fields(out)
    assert out["event_kind"] == "screen_view"
    assert f["event"] == "screen_view"
    assert f["screenName"] == "/fatura/detalhe-da-fatura"
    assert f["event_access_type"] == "b2c"
    assert f["macro_journey"] == "fatura"
    assert f["micro_journey"] == "consulta_da_fatura"
    assert f["event_detail"].startswith("visualizacao")
    assert out["fields"]["event"]["confidence"] == "auto"
    assert out["fields"]["event_access_type"]["confidence"] == "auto"
    assert out["fields"]["screenName"]["confidence"] == "review"
    # base has no component fields
    assert "component_type" not in out["fields"]


def test_convert_interaction_component_and_detail():
    out = convert_events([_one(name="interaction", ac="screen_click_button", lb="continuar_recarga",
                               sn="/napp/recarga", screen_name="Valor")])[0]
    f = _fields(out)
    assert f["event"] == "interaction"
    assert f["component_type"] == "button"
    assert out["fields"]["component_type"]["confidence"] == "auto"
    assert f["component_copy"] == "continuar_recarga"
    assert f["event_detail"] == "clique_continuar_recarga"


def test_convert_access_type_b2b_is_review():
    out = convert_events([_one(ct="b2b_mve_something")])[0]
    assert _fields(out)["event_access_type"] == "b2b_m"
    assert out["fields"]["event_access_type"]["confidence"] == "review"


def test_convert_error_detection_and_status():
    out = convert_events([_one(name="noninteraction", ac="screen_view_error",
                               lb="app&blocker&falha_diagnostico")])[0]
    assert out["has_error"] is True
    f = _fields(out)
    assert f["error_status"] == "bloqueado"
    assert out["fields"]["error_status"]["confidence"] == "auto"
    assert f["status_journey"] == "erro"
    assert out["fields"]["status_journey"]["confidence"] == "auto"
    assert "error_type" in out["fields"]
    # component_copy/event_detail seed from the message part, not the app&blocker& prefix
    assert f["component_copy"] == "falha_diagnostico"
    assert f["event_detail"] == "visualizacao_falha_diagnostico"


def test_convert_error_nonblocker_continuar():
    out = convert_events([_one(name="interaction", ac="x", lb="app&nonBlocker&aviso")])[0]
    assert out["has_error"] is True
    assert _fields(out)["error_status"] == "continuar"


def test_convert_non_error_has_no_error_fields():
    out = convert_events([_one(name="interaction", ac="screen_click_card", lb="plano_controle")])[0]
    assert out["has_error"] is False
    assert "error_status" not in out["fields"]
    assert _fields(out)["component_type"] == "card"


def test_convert_manual_fields_blank_and_flagged():
    out = convert_events([_one()])[0]
    for key in ("origin_nv", "client_category", "department"):
        assert out["fields"][key]["value"] == ""
        assert out["fields"][key]["confidence"] == "manual"


def test_convert_unknown_event_name_is_review():
    out = convert_events([_one(name="foo")])[0]
    assert out["event_kind"] == "foo"
    assert out["fields"]["event"]["value"] == "foo"
    assert out["fields"]["event"]["confidence"] == "review"


def test_convert_passthrough_old_values_and_plan():
    ev = {
        "name": "interaction", "sn": "/napp/hub-payment/insert-card-data",
        "ct": "b2x_ecare_napp_hubPayment", "ac": "screen_click_button", "lb": "continuar_insertCardData",
        "journeyVariant": "adicionarCartao", "crm_name": "siebel", "event_cnpj": "b2c_not_apply",
        "origin_nv": "home", "client_category": "adm", "event_access_type": "vivo",
        "payment_method": "pix", "info_detail": "tela_anterior",
        "plan_name": "vivo_controle_12gb", "event_plan_type": "controle",
    }
    out = convert_events([ev])[0]
    f = {k: v["value"] for k, v in out["fields"].items()}
    assert f["screenName"] == "/hub-payment/insert-card-data"      # full path preserved
    assert f["macro_journey"] == "adicionarcartao"                 # from journeyVariant
    assert f["origin_nv"] == "home" and f["client_category"] == "adm" and f["event_access_type"] == "vivo"
    assert out["fields"]["origin_nv"]["confidence"] == "review"    # carried, not blank/manual
    assert f["component_type"] == "button"
    assert f["crm_name"] == "siebel" and f["event_cnpj"] == "b2c_not_apply"
    assert f["payment_method"] == "pix" and f["info_detail"] == "tela_anterior"
    assert f["journeyVariant"] == "adicionarCartao"                # also carried through
    assert out["has_product"] is True
    assert f["plan_name"] == "vivo_controle_12gb" and f["event_plan_type"] == "controle"


def test_convert_plan_placeholder_carried_from_old():
    out = convert_events([{"name": "screen_view", "sn": "/napp/x", "plan_name": "[nomeDoPlano]"}])[0]
    assert out["has_product"] is True
    assert out["fields"]["plan_name"]["value"] == "[nomeDoPlano]"


def test_convert_rejects_non_list():
    with pytest.raises(ValueError):
        convert_events({"not": "a list"})


# --- endpoint: 400-not-500 on malformed input ---

def test_endpoint_valid_payload_200():
    r = _endpoint_client().post("/api/convert-taxonomy",
                                json={"events": [{"name": "screen_view", "sn": "/napp/fatura"}]})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and len(body["events"]) == 1


def test_endpoint_events_not_list_is_400():
    r = _endpoint_client().post("/api/convert-taxonomy", json={"events": "nope"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_endpoint_array_body_is_400():
    r = _endpoint_client().post("/api/convert-taxonomy", json=[1, 2, 3])
    assert r.status_code == 400


def test_endpoint_invalid_json_is_400():
    r = _endpoint_client().post("/api/convert-taxonomy", data="not json",
                                content_type="application/json")
    assert r.status_code == 400


def test_convert_events_empty_list_ok():
    assert convert_events([]) == []
