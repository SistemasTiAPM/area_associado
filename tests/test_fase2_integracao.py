"""Fase 2 ponta a ponta com MySQL REAL (migrações 000–007) + hub e SMTP stub.

Rodar com TESTE_DB_HOST/TESTE_DB_USER/TESTE_DB_PASS/TESTE_DB_NAME (usuário da
aplicação, `apm_area`) — sem eles, pulados (ver conftest).
"""

from __future__ import annotations

import io
import re
import secrets
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

pytestmark = pytest.mark.mysql

BASE = "https://minha.apm.org.br"
TOKEN_STUB = "t" * 40


@pytest.fixture
def c(monkeypatch):
    from app import main
    from app.api.v1 import perfil as rota_perfil
    from app.integracoes.hub import redefinir_hub
    from app.limites import LimiteJanela

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    monkeypatch.setattr(rota_perfil, "_limite_contato", LimiteJanela(10, 3600))
    monkeypatch.setattr(rota_perfil, "_limite_foto", LimiteJanela(5, 3600))
    from app.dominio import perfil as dominio_perfil

    redefinir_hub(None)
    dominio_perfil.marcar_endereco_disponivel(None)
    cliente = TestClient(main.app, base_url=BASE)
    yield cliente
    redefinir_hub(None)
    dominio_perfil.marcar_endereco_disponivel(None)


def _cpf() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(11))


def entrar(c: TestClient, tipo="Efetivo") -> dict:
    r = c.get("/auth/login", params={"next": "/area"})
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    r = c.post("/auth/login", data={"csrf": csrf, "token": TOKEN_STUB, "nome": "TELMA NOGUEIRA",
                                    "email": "telma@exemplo.org", "cpf": _cpf(), "tipo": tipo}, follow_redirects=False)
    assert r.status_code == 303
    return c.get("/api/v1/sessao").json()


def h(sessao: dict) -> dict:
    return {"X-CSRF-Token": sessao["csrf"], "Sec-Fetch-Site": "same-origin"}


def _jpeg(lado=600) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado), (10, 120, 90)).save(buf, "JPEG")
    return buf.getvalue()


# ------------------------------------------------------------------ perfil
def test_login_grava_cache_e_perfil_completa_pelo_hub(c):
    entrar(c)
    p = c.get("/api/v1/perfil").json()
    assert p["nome"] == "TELMA NOGUEIRA" and p["email"] == "telma@exemplo.org"
    assert p["crm_uf"] == "SP" and p["tipo_associado"] == "Efetivo" and p["status_associativo"] == "Ativo"
    assert re.fullmatch(r"\(11\) 9\d{4}-\d{4}", p["celular"])  # veio do hub (stub)
    assert p["endereco"]["uf"] == "SP" and p["desatualizado"] is False and p["endereco_disponivel"] is True
    assert p["email_exige_reautenticacao"] is False  # login stub acabou de acontecer
    assert "cpf" not in p and not any(re.fullmatch(r"\d{11}", str(v)) for v in p.values())


def test_hub_fora_serve_cache_desatualizado(c):
    from app.integracoes.hub import obter_hub

    entrar(c)
    obter_hub().falhar = True
    p = c.get("/api/v1/perfil")
    assert p.status_code == 200 and p.json()["desatualizado"] is True and p.json()["nome"]


def test_atualiza_contato_so_depois_do_crm(c):
    from app.integracoes.hub import obter_hub

    s = entrar(c)
    corpo = {"celular": "(21) 98888-7777", "telefone2": "1131886200",
             "endereco": {"logradouro": "Av. Paulista", "numero": "1000", "bairro": "Bela Vista",
                          "cidade": "São Paulo", "uf": "SP", "cep": "01310-100"}}
    r = c.put("/api/v1/perfil/contato", json=corpo, headers=h(s))
    assert r.status_code == 200, r.text
    assert r.json()["celular"] == "(21) 98888-7777" and r.json()["telefone2"] == "(11) 3188-6200"
    assert r.json()["endereco"]["logradouro"] == "Av. Paulista"
    # CRM fora: nada muda no cache (sem escrita otimista).
    obter_hub().falhar = True
    r = c.put("/api/v1/perfil/contato", json={"celular": "11977776666"}, headers=h(s))
    assert r.status_code == 503 and r.json()["erro"] == "fonte_indisponivel"
    obter_hub().falhar = False
    assert c.get("/api/v1/perfil").json()["celular"] == "(21) 98888-7777"


def test_endereco_indisponivel_no_crm(c):
    from app.dominio import perfil as dominio_perfil
    from app.integracoes.hub import obter_hub

    s = entrar(c)
    obter_hub().endereco_disponivel = False
    p = c.get("/api/v1/perfil").json()  # 1ª leitura do worker vai ao hub mesmo com cache fresco
    assert p["endereco_disponivel"] is False and p["endereco"] is None
    end = {"logradouro": "Av. Paulista", "numero": "1000", "bairro": "Bela Vista", "cidade": "São Paulo",
           "uf": "SP", "cep": "01310-100"}
    r = c.put("/api/v1/perfil/contato", json={"celular": "11977776666", "endereco": end}, headers=h(s))
    assert r.status_code == 409 and r.json()["erro"] == "endereco_indisponivel"
    assert c.get("/api/v1/perfil").json()["celular"] != "(11) 97777-6666"  # nada pela metade
    # Worker que ainda não perguntou: o hub decide e a área passa a saber.
    dominio_perfil.marcar_endereco_disponivel(None)
    r = c.put("/api/v1/perfil/contato", json={"endereco": end}, headers=h(s))
    assert r.status_code == 409 and dominio_perfil.endereco_disponivel() is False
    r = c.put("/api/v1/perfil/contato", json={"celular": "11977776666"}, headers=h(s))
    assert r.status_code == 200 and r.json()["celular"] == "(11) 97777-6666"


def test_contato_valida_e_exige_csrf(c):
    s = entrar(c)
    assert c.put("/api/v1/perfil/contato", json={"celular": "11977776666"},
                 headers={"Sec-Fetch-Site": "same-origin"}).status_code == 403
    r = c.put("/api/v1/perfil/contato", json={"celular": "1131886200"}, headers=h(s))
    assert r.status_code == 400 and r.json()["detalhes"][0]["campo"] == "celular"
    assert "celular inválido" in r.json()["detalhes"][0]["mensagem"]
    assert c.put("/api/v1/perfil/contato", json={"nome": "Outro"}, headers=h(s)).status_code == 400
    assert c.put("/api/v1/perfil/contato", json={}, headers=h(s)).status_code == 400


# ------------------------------------------------------------------ e-mail
def test_troca_de_email_com_codigo(c):
    s = entrar(c)
    r = c.post("/api/v1/perfil/email", json={"email": "Nova.Telma@Exemplo.org"}, headers=h(s))
    assert r.status_code == 202, r.text
    corpo = r.json()
    assert corpo["enviado_para"] == "n***@exemplo.org" and re.fullmatch(r"\d{6}", corpo["codigo_teste"])
    errado = "000000" if corpo["codigo_teste"] != "000000" else "111111"
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "nova.telma@exemplo.org", "codigo": errado}, headers=h(s))
    assert r.status_code == 400 and r.json()["erro"] == "codigo_invalido" and "4 tentativa" in r.json()["mensagem"]
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "outra@exemplo.org", "codigo": corpo["codigo_teste"]},
               headers=h(s))
    assert r.json()["erro"] == "codigo_invalido"  # código de outro e-mail não vale
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "nova.telma@exemplo.org",
                                                       "codigo": corpo["codigo_teste"]}, headers=h(s))
    assert r.status_code == 200 and r.json()["email"] == "nova.telma@exemplo.org"
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "nova.telma@exemplo.org",
                                                       "codigo": corpo["codigo_teste"]}, headers=h(s))
    assert r.json()["erro"] == "codigo_expirado"  # usado não volta a valer


def test_email_reenvio_e_tentativas(c):
    s = entrar(c)
    assert c.post("/api/v1/perfil/email", json={"email": "a1@exemplo.org"}, headers=h(s)).status_code == 202
    r = c.post("/api/v1/perfil/email", json={"email": "a2@exemplo.org"}, headers=h(s))
    assert r.status_code == 429 and r.json()["erro"] == "aguarde_reenvio"
    assert c.post("/api/v1/perfil/email", json={"email": "telma@exemplo.org"}, headers=h(s)).json()["erro"] in (
        "email_igual", "aguarde_reenvio")
    for _ in range(5):
        c.post("/api/v1/perfil/email/confirmar", json={"email": "a1@exemplo.org", "codigo": "999999"}, headers=h(s))
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "a1@exemplo.org", "codigo": "999999"}, headers=h(s))
    assert r.json()["erro"] == "tentativas_esgotadas"
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "a1@exemplo.org", "codigo": "999999"}, headers=h(s))
    assert r.json()["erro"] == "codigo_expirado"  # invalidado de fato (persistiu)


def test_email_exige_login_recente(c, monkeypatch):
    s = entrar(c)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 1000)  # senha digitada há ~17 min
    r = c.post("/api/v1/perfil/email", json={"email": "x@exemplo.org"}, headers=h(s))
    assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria"
    assert c.get("/api/v1/perfil").json()["email_exige_reautenticacao"] is True


# -------------------------------------------------------------------- foto
def test_foto_envio_avatar_etag_e_remocao(c):
    s = entrar(c)
    r = c.post("/api/v1/perfil/foto", files={"foto": ("eu.png", _jpeg(), "image/png")}, headers=h(s))
    assert r.status_code == 200, r.text
    versao = r.json()["foto_versao"]
    assert c.get("/api/v1/sessao").json()["associado"]["foto_versao"] == versao
    r = c.get("/api/v1/perfil/foto")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.headers["etag"] == f'"{versao}"'
    assert r.headers["cache-control"] == "private, no-cache"
    assert c.get("/api/v1/perfil/foto", headers={"If-None-Match": f'"{versao}"'}).status_code == 304
    r = c.delete("/api/v1/perfil/foto", headers={**h(s), "Content-Type": "application/json"})
    assert r.status_code == 200 and c.get("/api/v1/perfil/foto").status_code == 404


def test_foto_recusas(c):
    s = entrar(c)
    r = c.post("/api/v1/perfil/foto", files={"foto": ("x.jpg", b"%PDF-1.4 falso", "image/jpeg")}, headers=h(s))
    assert r.status_code == 415 and r.json()["erro"] == "tipo_nao_suportado"
    r = c.post("/api/v1/perfil/foto", files={"foto": ("x.jpg", _jpeg()[:500], "image/jpeg")}, headers=h(s))
    assert r.status_code == 400 and r.json()["erro"] == "foto_corrompida"
    r = c.post("/api/v1/perfil/foto", files={"outro": ("x.jpg", _jpeg(), "image/jpeg")}, headers=h(s))
    assert r.status_code == 400
    # Sem CSRF: recusado ANTES de ler o corpo.
    r = c.post("/api/v1/perfil/foto", files={"foto": ("x.jpg", _jpeg(), "image/jpeg")},
               headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 403


# ------------------------------------------------------------- carteirinha
def test_carteirinha_qr_e_verificacao_publica(c):
    s = entrar(c)
    cart = c.get("/api/v1/carteirinha").json()
    assert cart["nome"] == "TELMA NOGUEIRA" and cart["crm_uf"] == "SP" and cart["membro_desde"] == "2014"
    assert cart["status_associativo"] == "Ativo" and "validade" not in cart
    token = cart["url_verificacao"].rsplit("/", 1)[1]
    qr = c.get("/api/v1/carteirinha/qr.svg")
    assert qr.headers["content-type"].startswith("image/svg+xml") and b"<script" not in qr.content
    assert c.post("/api/v1/carteirinha/compartilhar", json={}, headers=h(s)).json()["url"] == cart["url_verificacao"]

    publico = TestClient(c.app, base_url=BASE)  # sem sessão
    r = publico.get(f"/verificar/{token}")
    assert r.status_code == 200 and "TELMA NOGUEIRA" in r.text and "Ativo" in r.text
    assert r.headers["x-robots-tag"] == "noindex, nofollow" and r.headers["cache-control"] == "no-store"
    assert "CRM" not in r.text.split("<main", 1)[-1] and "telma@exemplo.org" not in r.text
    assert publico.get("/verificar/AAAAAAAAAAAAAAAAAAAA").status_code == 404
    assert publico.get("/verificar/'or'1'='1").status_code == 404
