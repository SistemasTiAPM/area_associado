"""TI-07 — OpenAPI como artefato: `docs/api/openapi.json` tem de ser exatamente o
que `scripts/openapi_export.py` gera do código (chaves ordenadas, determinístico).
Regenerar: `python -m scripts.openapi_export`."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import openapi_export

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "docs" / "api" / "openapi.json"


def test_contrato_versionado_bate_com_o_codigo():
    divergencias = openapi_export.verificar(ARQUIVO)
    assert not divergencias, "docs/api/openapi.json desatualizado — rode `python -m scripts.openapi_export`:\n" + \
        "\n".join(divergencias[:60])


def test_esquema_tem_operation_ids_unicos_em_pt_br_e_modelos_de_resposta():
    esquema = openapi_export.gerar()
    assert json.loads(openapi_export.serializar(esquema)) == esquema  # serializável e estável
    operacoes = {op["operationId"]: (metodo, caminho)
                 for caminho, metodos in esquema["paths"].items() for metodo, op in metodos.items()}
    for oid in operacoes:
        assert oid.isidentifier() and oid == oid.lower() and "__" not in oid, oid
    for esperado in ("obter_sessao", "registrar_uso", "obter_perfil", "atualizar_contato", "iniciar_troca_email",
                     "confirmar_troca_email", "enviar_foto", "remover_foto", "obter_foto", "obter_carteirinha",
                     "obter_qr_carteirinha", "compartilhar_carteirinha", "auth_callback", "auth_logout"):
        assert esperado in operacoes, esperado

    modelos = esquema["components"]["schemas"]
    for nome in ("ApiError", "SessaoResposta", "PerfilResposta", "CarteirinhaResposta", "UsoResposta"):
        assert nome in modelos, nome
    assert set(modelos["ApiError"]["required"]) >= {"erro", "mensagem", "request_id"}
    sessao = modelos["SessaoResposta"]["properties"]
    for proibido in ("cpf", "cpf_mask", "email", "sub", "contact_id", "cid", "idt"):
        assert proibido not in sessao, proibido
    assert set(modelos["PerfilResposta"]["properties"]) >= {"email_exige_reautenticacao", "celular_exige_reautenticacao"}

    sessao_get = esquema["paths"]["/api/v1/sessao"]["get"]
    assert sessao_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("SessaoResposta")
    assert sessao_get["responses"]["401"]["content"]["application/json"]["schema"]["$ref"].endswith("ApiError")
    # Probes internos e a página pública HTML ficam fora do contrato (routers com include_in_schema=False).
    for fora in ("/health", "/db-health", "/auth-health", "/verificar/{token}"):
        assert fora not in esquema["paths"], fora


def test_openapi_nao_e_servido_fora_de_development(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    c = TestClient(main.app, base_url="https://minha.apm.org.br")
    for rota in ("/openapi.json", "/docs", "/redoc"):
        r = c.get(rota)
        assert r.status_code == 404, rota
