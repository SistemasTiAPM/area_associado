"""Fase 2 — unidades sem banco nem rede: telefone, foto, carteirinha, hub, e-mail, OIDC, config."""

from __future__ import annotations

import io
import json
import time

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError


# --------------------------------------------------------------- telefone
@pytest.mark.parametrize("bruto,celular,esperado", [
    ("11912345678", True, "(11) 91234-5678"),
    ("+55 (11) 91234-5678", True, "(11) 91234-5678"),
    ("1131886200", False, "(11) 3188-6200"),
    ("21 98765-4321", False, "(21) 98765-4321"),
])
def test_telefone_valido(bruto, celular, esperado):
    from app.api.v1.perfil import formatar_telefone

    assert formatar_telefone(bruto, celular=celular) == esperado


@pytest.mark.parametrize("bruto,celular", [
    ("1131886200", True),      # fixo como celular
    ("2012345678", False),     # DDD 20 não existe
    ("123", False),
    ("11812345678", False),    # 9 dígitos sem começar com 9
])
def test_telefone_invalido(bruto, celular):
    from app.api.v1.perfil import formatar_telefone

    with pytest.raises(ValueError):
        formatar_telefone(bruto, celular=celular)


def test_contato_entrada_regras():
    from app.api.v1.perfil import ContatoEntrada

    c = ContatoEntrada.model_validate({"telefone2": None, "celular": "11912345678"})
    assert c.campos() == {"celular": "(11) 91234-5678", "telefone2": None}
    with pytest.raises(ValidationError):
        ContatoEntrada.model_validate({"celular": None})
    with pytest.raises(ValidationError):
        ContatoEntrada.model_validate({"cpf": "123"})
    with pytest.raises(ValueError, match="nada"):
        ContatoEntrada.model_validate({}).campos()
    e = ContatoEntrada.model_validate({"endereco": {"logradouro": "Av. Brigadeiro", "numero": "278", "bairro": "Bela Vista",
                                                    "cidade": "São Paulo", "uf": "sp", "cep": "01318901"}})
    assert e.campos()["endereco"]["cep"] == "01318-901" and e.campos()["endereco"]["uf"] == "SP"
    with pytest.raises(ValidationError):
        ContatoEntrada.model_validate({"endereco": {"logradouro": "x\u0000", "numero": "1", "bairro": "b",
                                                    "cidade": "c", "uf": "XX", "cep": "1"}})


# ------------------------------------------------------------------- foto
def _imagem(formato: str, tamanho=(800, 600), modo="RGB", exif: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    img = Image.new(modo, tamanho, 128 if modo in ("L", "1") else (200, 50, 50))
    kwargs = {"exif": exif} if exif else {}
    img.save(buf, format=formato, **kwargs)
    return buf.getvalue()


def test_foto_jpeg_png_webp_viram_jpeg_quadrado_sem_metadados():
    from app.dominio import foto

    exif = Image.Exif()
    exif[0x010F] = "Fabricante"  # Make
    exif[0x8825] = {2: (23.0, 33.0, 0.0)}  # GPS
    for formato, extra in (("JPEG", exif.tobytes()), ("PNG", None), ("WEBP", None)):
        grande, pequena = foto.processar(_imagem(formato, exif=extra), 5 * 1024 * 1024)
        with Image.open(io.BytesIO(grande)) as g, Image.open(io.BytesIO(pequena)) as p:
            assert g.format == "JPEG" and g.size == (512, 512) and p.size == (128, 128)
            assert not g.getexif() and "exif" not in g.info and "icc_profile" not in g.info
        assert len(pequena) <= 65536


def test_foto_png_com_transparencia_recebe_fundo_branco():
    from app.dominio import foto

    grande, _ = foto.processar(_imagem("PNG", modo="RGBA"), 5 * 1024 * 1024)
    with Image.open(io.BytesIO(grande)) as g:
        assert g.mode == "RGB"


@pytest.mark.parametrize("dados,codigo", [
    (b"", "arquivo_vazio"),
    (b"%PDF-1.7 nao sou imagem", "tipo_nao_suportado"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "tipo_nao_suportado"),
])
def test_foto_recusa_nao_imagem(dados, codigo):
    from app.dominio import foto

    with pytest.raises(foto.FotoInvalida) as e:
        foto.processar(dados, 5 * 1024 * 1024)
    assert e.value.codigo == codigo


def test_foto_truncada_ou_disfarcada():
    from app.dominio import foto

    jpeg = _imagem("JPEG")
    with pytest.raises(foto.FotoInvalida) as e:
        foto.processar(jpeg[: len(jpeg) // 3], 5 * 1024 * 1024)
    assert e.value.codigo == "foto_corrompida"
    # Assinatura de PNG com corpo JPEG: decodificador e assinatura discordam.
    disfarce = b"\x89PNG\r\n\x1a\n" + jpeg[8:]
    with pytest.raises(foto.FotoInvalida):
        foto.processar(disfarce, 5 * 1024 * 1024)


def test_foto_bomba_de_descompressao_e_limites():
    from app.dominio import foto

    bomba = _imagem("PNG", tamanho=(6000, 5000), modo="1")  # 30 MP, poucos KB
    assert len(bomba) < 200_000
    with pytest.raises(foto.FotoInvalida) as e:
        foto.processar(bomba, 5 * 1024 * 1024)
    assert e.value.codigo == "foto_grande_demais"
    with pytest.raises(foto.FotoInvalida) as e:
        foto.processar(_imagem("JPEG"), 1000)
    assert e.value.codigo == "arquivo_grande"
    with pytest.raises(foto.FotoInvalida) as e:
        foto.processar(_imagem("JPEG", tamanho=(40, 40)), 5 * 1024 * 1024)
    assert e.value.codigo == "foto_pequena"


# ------------------------------------------------------------ carteirinha
def test_token_carteirinha_estavel_opaco_e_dependente_da_chave(monkeypatch):
    from app.config import get_settings
    from app.dominio import carteirinha

    cid = "6b1f3c1e-4f3a-5d2b-9c7e-a5e0c0de57b0"
    t1 = carteirinha.token_para(cid)
    assert t1 == carteirinha.token_para(cid) and len(t1) == 20 and t1.isupper() and cid not in t1
    monkeypatch.setenv("CARTEIRINHA_HMAC_KEY", "k" * 40)
    get_settings.cache_clear()
    assert carteirinha.token_para(cid) != t1
    assert carteirinha.url_verificacao("ABC").endswith("/verificar/ABC")


def test_qr_svg_sem_script_nem_estilo_inline():
    from app.dominio import carteirinha

    svg = carteirinha.qr_svg("https://associado.apm.org.br/verificar/AAAAAAAAAAAAAAAAAAAA").decode()
    assert svg.startswith("<svg") and "<script" not in svg and "style=" not in svg and "<?xml" not in svg


# --------------------------------------------------------------- hub real
def _hub(monkeypatch, rotas):
    monkeypatch.setenv("HUB_MODE", "real")
    monkeypatch.setenv("HUB_CLIENT_SECRET", "s" * 32)
    from app.config import get_settings
    from app.integracoes.hub import ClienteHubReal

    get_settings.cache_clear()
    chamadas = []

    def tratar(req: httpx.Request) -> httpx.Response:
        chamadas.append(req)
        return rotas(req, len(chamadas))

    return ClienteHubReal(transporte=httpx.MockTransport(tratar)), chamadas


def test_hub_token_em_memoria_host_e_cpf_descartado(monkeypatch):
    def rotas(req, n):
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 600})
        return httpx.Response(200, json={"colunas": [], "linhas": [{"nome": "Ana", "cpf": "12345678901",
                                                                    "endereco": {"uf": "SP"}, "endereco_disponivel": True,
                                                                    "tem_foto": True}]})

    cliente, chamadas = _hub(monkeypatch, rotas)
    p = cliente.perfil_consultar("cid")
    p2 = cliente.perfil_consultar("cid")
    assert p.nome == "Ana" and p.tem_foto and p.endereco.uf == "SP" and p.endereco_disponivel
    assert "cpf" not in cliente.chamar("associado.perfil_consultar", {"contact_id": "cid"})[0]
    assert [c.url.path for c in chamadas].count("/oauth/token") == 1  # token reaproveitado (3 chamadas)
    chamada = chamadas[1]
    assert chamada.headers["host"] == "mcp.apm.org.br" and chamada.headers["authorization"] == "Bearer tok"
    assert json.loads(chamada.content) == {"argumentos": {"contact_id": "cid"}}
    token = chamadas[0]
    assert token.headers["authorization"].startswith("Basic ") and b"client_credentials" in token.content
    assert p2.nome == "Ana"


def test_hub_401_renova_token_uma_vez(monkeypatch):
    def rotas(req, n):
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": f"t{n}", "expires_in": 600})
        return httpx.Response(401, json={"erro": "nao_autenticado"}) if n == 2 else httpx.Response(200, json={"linhas": []})

    cliente, chamadas = _hub(monkeypatch, rotas)
    assert cliente.perfil_consultar("cid") is None
    assert [c.url.path for c in chamadas] == ["/oauth/token", "/api/v1/ferramentas/associado.perfil_consultar",
                                              "/oauth/token", "/api/v1/ferramentas/associado.perfil_consultar"]


@pytest.mark.parametrize("status,corpo,codigo,http", [
    (400, {"erro": "entrada_invalida", "detalhes": [{"campo": "celular", "mensagem": "x"}]}, "entrada_invalida", 400),
    (429, {"erro": "limite_taxa"}, "limite_taxa", 429),
    (404, {"erro": "ferramenta_inexistente"}, "fonte_indisponivel", 503),
    (409, {"erro": "endereco_indisponivel"}, "endereco_indisponivel", 409),
    (409, {"erro": "outro_conflito"}, "fonte_indisponivel", 503),
    (504, {"erro": "escrita_indeterminada"}, "fonte_indisponivel", 503),
    (403, {"erro": "nao_permitido"}, "fonte_indisponivel", 503),
    (500, {}, "fonte_indisponivel", 503),
    (302, {}, "fonte_indisponivel", 503),
])
def test_hub_mapeia_erros(monkeypatch, status, corpo, codigo, http):
    from app.integracoes.hub import HubError

    def rotas(req, n):
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 600})
        return httpx.Response(status, json=corpo, headers={"Location": "https://evil"} if status == 302 else None)

    cliente, _ = _hub(monkeypatch, rotas)
    with pytest.raises(HubError) as e:
        cliente.contato_atualizar("cid", {"celular": "x"})
    assert (e.value.codigo, e.value.status) == (codigo, http)


def test_hub_uf_so_sigla_e_endereco_fail_closed():
    from app.integracoes.hub import perfil_de_linha

    end = {"logradouro": "Rua A", "numero": "1", "bairro": "B", "cidade": "C", "uf": "sp", "cep": "01000-000"}
    p = perfil_de_linha({"crm_uf": "São Paulo", "endereco": end, "endereco_disponivel": True})
    assert p.crm_uf is None and p.endereco.uf == "SP"  # nunca "SÃ"
    assert perfil_de_linha({"crm_uf": " rj "}).crm_uf == "RJ"
    sem = perfil_de_linha({"endereco": end})  # hub antigo / campo ausente
    assert sem.endereco is None and sem.endereco_disponivel is False
    assert perfil_de_linha({"endereco": end, "endereco_disponivel": "true"}).endereco_disponivel is False


def test_hub_escrita_usa_timeout_proprio(monkeypatch):
    monkeypatch.setenv("HUB_TIMEOUT_ESCRITA", "30")

    def rotas(req, n):
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 600})
        return httpx.Response(200, json={"linhas": [{"campos_alterados": ["celular"]}]})

    cliente, chamadas = _hub(monkeypatch, rotas)
    cliente.perfil_consultar("cid")
    assert cliente.contato_atualizar("cid", {"celular": "x"}) == ["celular"]
    cliente.foto_atualizar("cid", None)
    leituras = [c.extensions["timeout"]["read"] for c in chamadas if c.url.path.startswith("/api/")]
    assert leituras == [10.0, 30.0, 30.0]


def test_hub_fora_do_ar(monkeypatch):
    from app.integracoes.hub import HubError

    def rotas(req, n):
        raise httpx.ConnectError("recusado")

    cliente, _ = _hub(monkeypatch, rotas)
    with pytest.raises(HubError) as e:
        cliente.foto_obter("cid")
    assert e.value.codigo == "fonte_indisponivel"


# ----------------------------------------------------------------- e-mail
def test_email_validacao_mascara_e_stub():
    from app.integracoes import email

    assert email.email_valido("telma.nogueira+apm@exemplo.org.br")
    for ruim in ("a@b", "a b@c.com", "a@b.com\r\nBcc: x@y.com", "a..b@c.com", "@c.com", "x" * 250 + "@c.com"):
        assert not email.email_valido(ruim), ruim
    assert email.mascarar_email("telma@exemplo.org") == "t***@exemplo.org"
    email.enviar("telma@exemplo.org", "assunto", "corpo")  # stub: não envia, não lança
    with pytest.raises(email.EmailError):
        email.enviar("a@b.com\nBcc: x@y.com", "assunto", "corpo")
    assert "123456" in email.texto_codigo("123456", 10)


# ------------------------------------------------------------------- OIDC
def test_carteirinha_obrigatoria_p20():
    from app.oidc import OidcError, _carteirinha

    ok = _carteirinha({"tipo_associado": "Efetivo", "associado": "Ativo", "num_contato": "80012345", "crm": "123456",
                       "crm_uf": "SP", "data_filiacao": "2014-03-01"})
    assert ok == {"tipo": "Efetivo", "status": "Ativo", "num_contato": "80012345", "crm": "123456",
                  "crm_uf": "SP", "data_filiacao": "2014-03-01"}
    assert _carteirinha({"tipo_associado": "Efetivo", "associado": "Ativo", "data_filiacao": "01/03/2014",
                         "crm": "<script>"})["data_filiacao"] is None
    for faltando in ({"associado": "Ativo"}, {"tipo_associado": "Efetivo"}, {"tipo_associado": " ", "associado": "Ativo"}):
        with pytest.raises(OidcError) as e:
            _carteirinha(faltando)
        assert e.value.code == "persona_incompleta" and e.value.http_status == 403


def test_step_up_usa_auth_time_do_idp():
    from app.session_guard import Associado, autenticacao_recente

    agora = int(time.time())
    base = dict(sub="s", contact_id=None, nome=None, email=None, cpf_mask=None, auth_at=agora, amr=("pwd",))
    assert autenticacao_recente(Associado(**base, idp_auth_time=agora - 60), 900)
    assert not autenticacao_recente(Associado(**base, idp_auth_time=agora - 901), 900)
    assert not autenticacao_recente(Associado(**base, idp_auth_time=None), 900)  # login novo na área, senha velha


# ------------------------------------------------------------------ config
def _build(monkeypatch, **over):
    for k, v in over.items():
        monkeypatch.setenv(k, v)
    from app.config import Settings

    return Settings()


def test_producao_exige_hub_smtp_reais_e_chave_da_carteirinha(monkeypatch):
    base = {"APP_ENV": "production", "DB_SSL_VERIFY": "1", "SESSION_ENC_KEYS": "zX0Z2j1Qqk7pM8l3dV3Yf5bQx0bJ8m1Y2c3d4e5f6g8="}
    with pytest.raises(ValidationError, match="HUB_MODE=stub"):
        _build(monkeypatch, **base)
    with pytest.raises(ValidationError, match="SMTP_MODE=stub"):
        _build(monkeypatch, **base, HUB_MODE="real", HUB_CLIENT_SECRET="s" * 32)
    with pytest.raises(ValidationError, match="CARTEIRINHA_HMAC_KEY"):
        _build(monkeypatch, **base, HUB_MODE="real", HUB_CLIENT_SECRET="s" * 32, SMTP_MODE="real",
               SMTP_HOST="smtp.x", SMTP_USER="u", SMTP_PASSWORD="p")


@pytest.mark.parametrize("valor", ["4", "61", "abc"])
def test_timeout_de_escrita_validado(monkeypatch, valor):
    with pytest.raises(ValidationError):
        _build(monkeypatch, HUB_TIMEOUT_ESCRITA=valor)


@pytest.mark.parametrize("url", ["http://mcp.apm.org.br", "ftp://mcp_hub", "https://mcp.apm.org.br/api", "https://u@h.com"])
def test_hub_url_insegura_recusada(monkeypatch, url):
    with pytest.raises(ValidationError, match="HUB_BASE_URL"):
        _build(monkeypatch, HUB_MODE="real", HUB_CLIENT_SECRET="s" * 32, HUB_BASE_URL=url)


def test_hub_url_interna_e_https_aceitas(monkeypatch):
    assert _build(monkeypatch, HUB_MODE="real", HUB_CLIENT_SECRET="s" * 32).hub_base_url == "http://mcp_hub:8000"
    assert _build(monkeypatch, HUB_MODE="real", HUB_CLIENT_SECRET="s" * 32, HUB_BASE_URL="https://mcp.apm.org.br")


def test_escopo_carteirinha_no_padrao(settings):
    assert "carteirinha" in settings.scope_list
