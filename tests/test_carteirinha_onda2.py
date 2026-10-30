"""Onda 2 — carteirinha (TI-45, TI-46): revogação, verificação em tempo quase real,
limite global ao hub, fallback, resultado no evento, downloads PNG/PDF e 409s.

Unidades sem banco nem rede (banco falso em memória que imita as 3 consultas do
domínio). A integração com MySQL real (sql/014) fica no fim, marcada `mysql`.
"""

from __future__ import annotations

import io
import json
import re
import struct
import zlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

BASE = "https://minha.apm.org.br"
TOKEN_STUB = "t" * 40
CID = "0f8fad5b-d9cb-469f-a165-70867728950e"
NOME = "TELMA NOGUEIRA DA SILVA"


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Banco falso: só as consultas de app/dominio/carteirinha.py                   #
# --------------------------------------------------------------------------- #
class _Resultado:
    def __init__(self, linha=None, escalar=None):
        self._linha, self._escalar = linha, escalar

    def first(self):
        return self._linha

    def scalar(self):
        return self._escalar


class BancoFalso:
    def __init__(self):
        self.colunas = True
        self.linhas: dict[str, dict] = {}
        self.updates: list[dict] = []
        self.falhar_update = False

    def adicionar(self, token, **campos):
        base = {"contact_id": CID, "carteirinha_revogada_em": None, "situacao_normalizada": None,
                "situacao_consultada_em": None, "nome": NOME, "status_associativo": "Ativo",
                "atualizado_em": _agora()}
        base.update(campos)
        self.linhas[token] = base
        return base

    def _por_cid(self, cid):
        return next((l for l in self.linhas.values() if l["contact_id"] == cid), None)

    def execute(self, sql, params=None):
        from sqlalchemy.exc import OperationalError

        s = " ".join(str(sql).split())
        params = params or {}
        if "information_schema.COLUMNS" in s:
            return _Resultado(escalar=3 if self.colunas else 0)
        if s.startswith("SELECT a.contact_id"):
            if "carteirinha_revogada_em" in s and not self.colunas:
                raise OperationalError(s, params, Exception("1054 Unknown column"))
            linha = self.linhas.get(params["t"])
            return _Resultado(linha=SimpleNamespace(**linha) if linha else None)
        if s.startswith("SELECT carteirinha_revogada_em"):
            linha = self._por_cid(params["c"])
            return _Resultado(escalar=linha["carteirinha_revogada_em"] if linha else None)
        if s.startswith("UPDATE associado SET situacao_normalizada"):
            if self.falhar_update:
                raise OperationalError(s, params, Exception("2013 Lost connection"))
            self.updates.append(dict(params))
            linha = self._por_cid(params["c"])
            if linha:
                linha["situacao_normalizada"], linha["situacao_consultada_em"] = params["n"], params["agora"]
                if params["n"] == "cancelado":
                    linha["carteirinha_revogada_em"] = linha["carteirinha_revogada_em"] or params["agora"]
                elif params["n"] == "ativo":
                    linha["carteirinha_revogada_em"] = None
            return _Resultado()
        raise AssertionError(f"SQL inesperado no teste: {s[:80]}")

    @contextmanager
    def sessao(self):
        yield self


class HubFalso:
    def __init__(self, normalizada="ativo", statecode=0, erro=None, inexistente=False, outro_contato=False):
        self.normalizada, self.statecode, self.erro = normalizada, statecode, erro
        self.inexistente, self.outro_contato = inexistente, outro_contato
        self.chamadas: list[str] = []

    def situacao_consultar(self, contact_id):
        from app.integracoes.hub import SituacaoCrm

        self.chamadas.append(contact_id)
        if self.erro is not None:
            raise self.erro
        if self.inexistente:
            return None
        return SituacaoCrm(contact_id="11111111-2222-4333-8444-555555555555" if self.outro_contato else contact_id,
                           status_associativo=self.normalizada.title(), situacao_normalizada=self.normalizada,
                           statecode=self.statecode)


@pytest.fixture
def dom(monkeypatch):
    from app.dominio import carteirinha
    from app.limites import LimiteJanela

    banco = BancoFalso()
    monkeypatch.setattr(carteirinha, "_sessao", banco.sessao)
    carteirinha.redefinir_cache_colunas()
    carteirinha.redefinir_limite(LimiteJanela(1000, 60))
    yield SimpleNamespace(c=carteirinha, banco=banco)
    carteirinha.redefinir_cache_colunas()
    carteirinha.redefinir_limite(None)


TOKEN = "ABCDEFGHIJKLMNOPQRST"


# --------------------------------------------------------------------- settings
def test_settings_de_verificacao_padrao_e_faixas(monkeypatch, settings):
    from app.config import Settings, get_settings

    assert settings.verificacao_cache_ttl == 600 and settings.verificacao_hub_por_minuto == 60
    for chave, valor in (("VERIFICACAO_CACHE_TTL", "59"), ("VERIFICACAO_CACHE_TTL", "3601"),
                         ("VERIFICACAO_HUB_POR_MINUTO", "0"), ("VERIFICACAO_HUB_POR_MINUTO", "601")):
        monkeypatch.setenv(chave, valor)
        get_settings.cache_clear()
        with pytest.raises(ValueError, match=chave):
            Settings()
        monkeypatch.delenv(chave)


# ------------------------------------------------------------------- revogação
def test_revogada_com_cache_fresco_nao_consulta_hub_e_nao_mostra_nome(dom):
    dom.banco.adicionar(TOKEN, carteirinha_revogada_em=_agora() - timedelta(days=2), situacao_normalizada="cancelado",
                        situacao_consultada_em=_agora() - timedelta(seconds=30))
    hub = HubFalso("cancelado")
    v = dom.c.resolver(TOKEN, hub=hub)
    assert v.revogada and v.resultado == "inativo" and v.situacao == "Sem validade" and v.verificado_em is None
    assert hub.chamadas == []


def test_hub_cancelado_revoga_e_grava(dom):
    dom.banco.adicionar(TOKEN)
    hub = HubFalso("cancelado")
    v = dom.c.resolver(TOKEN, hub=hub)
    assert hub.chamadas == [CID] and v.revogada and v.resultado == "inativo"
    linha = dom.banco.linhas[TOKEN]
    assert linha["situacao_normalizada"] == "cancelado" and linha["carteirinha_revogada_em"] is not None
    assert dom.c.revogada(CID) is True


def test_reativacao_confirmada_pelo_crm_tira_a_revogacao(dom):
    dom.banco.adicionar(TOKEN, carteirinha_revogada_em=_agora() - timedelta(days=40), situacao_normalizada="cancelado",
                        situacao_consultada_em=_agora() - timedelta(hours=3))
    v = dom.c.resolver(TOKEN, hub=HubFalso("ativo"))
    assert not v.revogada and v.resultado == "ativo" and v.situacao == "Ativo" and v.nome == NOME
    assert dom.banco.linhas[TOKEN]["carteirinha_revogada_em"] is None


def test_suspenso_nao_revoga_mas_nao_e_ativo(dom):
    dom.banco.adicionar(TOKEN)
    v = dom.c.resolver(TOKEN, hub=HubFalso("suspenso"))
    assert not v.revogada and v.resultado == "inativo" and v.situacao == "Suspenso"
    assert dom.banco.linhas[TOKEN]["carteirinha_revogada_em"] is None


def test_ativo_com_registro_desativado_no_crm_nao_e_ativo(dom):
    dom.banco.adicionar(TOKEN)
    v = dom.c.resolver(TOKEN, hub=HubFalso("ativo", statecode=1))
    assert v.resultado == "inativo" and v.situacao == "Não ativo"
    assert dom.banco.linhas[TOKEN]["situacao_normalizada"] == "outro"


def test_revogada_com_hub_fora_continua_sem_validade(dom):
    from app.integracoes.hub import HubError

    dom.banco.adicionar(TOKEN, carteirinha_revogada_em=_agora() - timedelta(days=1), situacao_normalizada="cancelado",
                        situacao_consultada_em=_agora() - timedelta(days=1))
    v = dom.c.resolver(TOKEN, hub=HubFalso(erro=HubError("fonte_indisponivel")))
    assert v.revogada and v.resultado == "inativo"


# ------------------------------------------------------------------------- TTL
def test_ttl_fresco_usa_cache_e_vencido_consulta(dom, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "verificacao_cache_ttl", 600)
    dom.banco.adicionar(TOKEN, situacao_normalizada="ativo", situacao_consultada_em=_agora() - timedelta(seconds=590),
                        status_associativo="Pendente", atualizado_em=_agora() - timedelta(hours=2))
    hub = HubFalso("suspenso")
    v = dom.c.resolver(TOKEN, hub=hub)
    assert hub.chamadas == [] and v.resultado == "ativo" and v.situacao == "Ativo"

    dom.banco.linhas[TOKEN]["situacao_consultada_em"] = _agora() - timedelta(seconds=610)
    v = dom.c.resolver(TOKEN, hub=hub)
    assert hub.chamadas == [CID] and v.resultado == "inativo" and v.situacao == "Suspenso"
    assert dom.banco.updates[-1]["n"] == "suspenso"


def test_nunca_consultado_consulta_o_hub(dom):
    dom.banco.adicionar(TOKEN)
    hub = HubFalso("ativo")
    v = dom.c.resolver(TOKEN, hub=hub)
    assert hub.chamadas == [CID] and v.resultado == "ativo" and v.verificado_em is not None


# ----------------------------------------------------------------- limite global
def test_limite_global_por_processo_poupa_a_cota_do_hub(dom):
    from app.limites import LimiteJanela

    dom.c.redefinir_limite(LimiteJanela(2, 60))
    dom.banco.adicionar(TOKEN, status_associativo="Ativo", atualizado_em=_agora() - timedelta(hours=1))
    hub = HubFalso("cancelado")
    dom.c.resolver(TOKEN, hub=hub)  # 1ª: consulta e revoga
    dom.banco.linhas[TOKEN].update(carteirinha_revogada_em=None, situacao_normalizada=None, situacao_consultada_em=None)
    dom.c.resolver(TOKEN, hub=hub)  # 2ª: consulta
    dom.banco.linhas[TOKEN].update(carteirinha_revogada_em=None, situacao_normalizada=None, situacao_consultada_em=None)
    v = dom.c.resolver(TOKEN, hub=hub)  # 3ª: limite → cache de perfil
    assert len(hub.chamadas) == 2 and v.resultado == "ativo" and v.situacao == "Ativo"


def test_limite_global_nasce_das_settings(dom, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "verificacao_hub_por_minuto", 7)
    dom.c.redefinir_limite(None)
    assert dom.c._limite_global().maximo == 7 and dom.c._limite_global().janela_s == 60


# ---------------------------------------------------------- fallback por erro
def _erros_do_hub():
    from app.integracoes.hub import HubError

    return [
        HubError("fonte_indisponivel"),          # hub fora / timeout / 5xx
        HubError("fonte_indisponivel", 503),     # ferramenta sem grant (403 do hub vira 503)
        HubError("nao_encontrado", 404),
        HubError("limite_taxa", 429),
        HubError("entrada_invalida", 400),
        RuntimeError("bug inesperado"),
    ]


@pytest.mark.parametrize("indice", range(6))
def test_fallback_cache_fresco_em_qualquer_erro_do_hub(dom, indice):
    dom.banco.adicionar(TOKEN, status_associativo="Ativo", atualizado_em=_agora() - timedelta(hours=3))
    v = dom.c.resolver(TOKEN, hub=HubFalso(erro=_erros_do_hub()[indice]))
    assert v.resultado == "ativo" and v.situacao == "Ativo" and v.verificado_em is not None
    assert dom.banco.updates == []


@pytest.mark.parametrize("indice", range(6))
def test_fallback_cache_vencido_nao_confirma(dom, indice):
    dom.banco.adicionar(TOKEN, status_associativo="Ativo", atualizado_em=_agora() - timedelta(hours=25))
    v = dom.c.resolver(TOKEN, hub=HubFalso(erro=_erros_do_hub()[indice]))
    assert v.resultado == "nao_confirmado" and v.situacao == "não confirmada no momento" and v.verificado_em is None


def test_fallback_contato_inexistente_ou_de_outro_contato(dom):
    dom.banco.adicionar(TOKEN, status_associativo="Ativo", atualizado_em=_agora() - timedelta(hours=25))
    for hub in (HubFalso(inexistente=True), HubFalso("cancelado", outro_contato=True)):
        v = dom.c.resolver(TOKEN, hub=hub)
        assert v.resultado == "nao_confirmado" and not v.revogada
    assert dom.banco.updates == []


def test_fallback_prefere_a_informacao_mais_recente(dom):
    # Hub (vencido para o TTL curto, mas dentro de 24 h) mais novo que o perfil.
    dom.banco.adicionar(TOKEN, situacao_normalizada="suspenso", situacao_consultada_em=_agora() - timedelta(hours=1),
                        status_associativo="Ativo", atualizado_em=_agora() - timedelta(hours=5))
    from app.integracoes.hub import HubError

    v = dom.c.resolver(TOKEN, hub=HubFalso(erro=HubError("fonte_indisponivel")))
    assert v.resultado == "inativo" and v.situacao == "Suspenso"


def test_falha_ao_gravar_ainda_usa_a_leitura_do_hub(dom):
    dom.banco.adicionar(TOKEN, status_associativo="Ativo")
    dom.banco.falhar_update = True
    v = dom.c.resolver(TOKEN, hub=HubFalso("suspenso"))
    assert v.resultado == "inativo" and v.situacao == "Suspenso"


def test_token_invalido_ou_inexistente(dom):
    assert dom.c.resolver("invalido") is None
    assert dom.c.resolver(TOKEN, hub=HubFalso()) is None
    dom.banco.adicionar(TOKEN, nome=None)
    assert dom.c.resolver(TOKEN, hub=HubFalso()) is None


def test_sem_sql_014_comportamento_anterior_sem_hub(dom):
    dom.banco.colunas = False
    dom.banco.adicionar(TOKEN, status_associativo="Ativo", atualizado_em=_agora() - timedelta(hours=1))
    hub = HubFalso("cancelado")
    v = dom.c.resolver(TOKEN, hub=hub)
    assert hub.chamadas == [] and v.resultado == "ativo" and not v.revogada
    assert dom.c.revogada(CID) is False


# ------------------------------------------------- atualizar_situacao (job noturno)
def test_atualizar_situacao_com_sessao_do_chamador_e_erros(dom):
    from app.integracoes.hub import HubError

    dom.banco.adicionar(TOKEN)
    sit = dom.c.atualizar_situacao(dom.banco, CID.upper(), hub=HubFalso("cancelado"))
    assert sit is not None and sit.situacao_normalizada == "cancelado"
    assert dom.banco.updates[-1]["c"] == CID and dom.banco.linhas[TOKEN]["carteirinha_revogada_em"] is not None
    assert dom.c.atualizar_situacao(dom.banco, CID, hub=HubFalso(erro=HubError("limite_taxa", 429))) is None
    with pytest.raises(ValueError):
        dom.c.atualizar_situacao(None, "nao-e-guid", hub=HubFalso())
    # Com sessão do chamador, erro de SQL propaga (o job decide o rollback).
    from sqlalchemy.exc import SQLAlchemyError

    dom.banco.falhar_update = True
    with pytest.raises(SQLAlchemyError):
        dom.c.atualizar_situacao(dom.banco, CID, hub=HubFalso("ativo"))


def test_situacao_efetiva():
    from app.dominio.carteirinha import situacao_efetiva
    from app.integracoes.hub import SituacaoCrm

    assert situacao_efetiva(SituacaoCrm(situacao_normalizada="ativo", statecode=0)) == "ativo"
    assert situacao_efetiva(SituacaoCrm(situacao_normalizada="ativo", statecode=None)) == "outro"
    assert situacao_efetiva(SituacaoCrm(situacao_normalizada="cancelado", statecode=1)) == "cancelado"
    assert situacao_efetiva(SituacaoCrm(situacao_normalizada="xpto")) == "outro"


# --------------------------------------------------------- página pública + evento
@pytest.fixture
def publico(monkeypatch):
    from app import main, uso
    from app.dominio import carteirinha

    gravados: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda linhas: gravados.extend(linhas))
    estado = SimpleNamespace(verificacao=None, gravados=gravados)
    monkeypatch.setattr(carteirinha, "resolver", lambda token, **kw: estado.verificacao)
    estado.c = TestClient(main.app, base_url=BASE)
    return estado


@pytest.mark.parametrize("resultado,situacao,revogada", [
    ("ativo", "Ativo", False), ("inativo", "Suspenso", False), ("nao_confirmado", "não confirmada no momento", False),
    ("inativo", "Sem validade", True),
])
def test_pagina_publica_grava_resultado_e_minimiza_dados(publico, resultado, situacao, revogada):
    from app.dominio.carteirinha import Verificacao

    publico.verificacao = Verificacao(NOME, situacao, _agora() if resultado != "nao_confirmado" else None, CID,
                                      resultado, revogada)
    r = publico.c.get(f"/verificar/{TOKEN}")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    corpo = r.text.split("<main", 1)[-1]
    if revogada:
        assert "Carteirinha sem validade" in corpo and NOME not in corpo
    else:
        assert NOME in corpo and situacao in corpo
    for proibido in ("Efetivo", "Acadêmico", "CRM", "@", "cpf", "CPF"):
        assert proibido not in corpo
    (evento,) = publico.gravados
    assert evento["acao"] == "carteirinha_verificar" and evento["origem"] == "publico"
    detalhes = evento["detalhes"] if isinstance(evento["detalhes"], dict) else json.loads(evento["detalhes"])
    assert detalhes == {"resultado": resultado} and evento["sub_hash"] is None


def test_pagina_publica_404_sem_evento(publico):
    assert publico.c.get(f"/verificar/{TOKEN}").status_code == 404 and publico.gravados == []


# ----------------------------------------------------------------- API (sessão)
@pytest.fixture
def api(monkeypatch):
    from app import audit, flags, main, uso
    from app.api.v1 import carteirinha as rota
    from app.dominio import associado as dom_assoc
    from app.dominio import carteirinha, perfil
    from app.limites import LimiteJanela

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    gravados: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda linhas: gravados.extend(linhas))
    monkeypatch.setattr(dom_assoc, "_executar", lambda p: None)
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: None)
    monkeypatch.setattr(flags, "_ler_tabela", lambda: {})
    flags.limpar_cache()
    monkeypatch.setattr(rota, "_limite_download", LimiteJanela(maximo=10, janela_s=3600))

    estado = SimpleNamespace(revogada=False, gravados=gravados, perfil=None)
    estado.perfil = perfil.Perfil(contact_id=CID, nome=NOME, email="telma@exemplo.org", celular="(11) 98888-7777",
                                  num_contato="80012345", crm="123456", crm_uf="SP", tipo_associado="Efetivo",
                                  status_associativo="Ativo", data_filiacao="2014-03-01", atualizado_em=_agora())
    monkeypatch.setattr(perfil, "ler", lambda cid: estado.perfil)
    monkeypatch.setattr(carteirinha, "revogada", lambda cid: estado.revogada)
    c = TestClient(main.app, base_url=BASE)
    r = c.get("/auth/login", params={"next": "/area"})
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    r = c.post("/auth/login", data={"csrf": csrf, "token": TOKEN_STUB, "nome": NOME, "email": "telma@exemplo.org",
                                    "cpf": "12345678901", "tipo": "Efetivo"}, follow_redirects=False)
    assert r.status_code == 303
    estado.c = c
    estado.csrf = c.get("/api/v1/sessao").json()["csrf"]
    yield estado
    flags.limpar_cache()


def _h(csrf):
    return {"X-CSRF-Token": csrf, "Sec-Fetch-Site": "same-origin"}


def test_get_carteirinha_revogada_e_num_contato(api):
    d = api.c.get("/api/v1/carteirinha").json()
    assert d["revogada"] is False and d["num_contato"] == "80012345"
    assert d["qr"] == "/api/v1/carteirinha/qr.svg" and d["url_verificacao"].startswith(f"{BASE}/verificar/")
    api.revogada = True
    d = api.c.get("/api/v1/carteirinha").json()
    assert d["revogada"] is True and d["qr"] is None and d["url_verificacao"] is None and d["nome"] == NOME
    for proibido in ("cpf", "email", "celular", "contact_id"):
        assert proibido not in d


def test_revogada_bloqueia_qr_compartilhar_e_downloads_com_409(api):
    api.revogada = True
    for metodo, rota in (("get", "/api/v1/carteirinha/qr.svg"), ("post", "/api/v1/carteirinha/compartilhar"),
                         ("get", "/api/v1/carteirinha/imagem.png"), ("get", "/api/v1/carteirinha/documento.pdf")):
        r = getattr(api.c, metodo)(rota, **({"json": {}, "headers": _h(api.csrf)} if metodo == "post" else {}))
        assert r.status_code == 409 and r.json()["erro"] == "carteirinha_revogada", rota
    assert api.gravados == []  # compartilhar recusado não vira evento


def test_compartilhar_continua_funcionando(api):
    r = api.c.post("/api/v1/carteirinha/compartilhar", json={}, headers=_h(api.csrf))
    assert r.status_code == 200 and r.json()["url"].startswith(f"{BASE}/verificar/")
    assert [g["acao"] for g in api.gravados] == ["carteirinha_compartilhar"]


def test_download_sem_cache_de_perfil_503_e_banco_fora_503(api, monkeypatch):
    api.perfil = None
    for rota in ("/api/v1/carteirinha/imagem.png", "/api/v1/carteirinha/documento.pdf", "/api/v1/carteirinha"):
        r = api.c.get(rota)
        assert r.status_code == 503 and r.json()["erro"] == "fonte_indisponivel"
    from sqlalchemy.exc import OperationalError

    from app.dominio import carteirinha

    def fora(cid):
        raise OperationalError("SELECT", {}, Exception("down"))

    monkeypatch.setattr(carteirinha, "revogada", fora)
    assert api.c.post("/api/v1/carteirinha/compartilhar", json={}, headers=_h(api.csrf)).status_code == 503


def _chunks_png(dados: bytes) -> list[str]:
    assert dados[:8] == b"\x89PNG\r\n\x1a\n"
    pos, nomes = 8, []
    while pos < len(dados):
        (tamanho,) = struct.unpack(">I", dados[pos:pos + 4])
        tipo = dados[pos + 4:pos + 8].decode("ascii")
        corpo = dados[pos + 8:pos + 8 + tamanho]
        (crc,) = struct.unpack(">I", dados[pos + 8 + tamanho:pos + 12 + tamanho])
        assert zlib.crc32(dados[pos + 4:pos + 8] + corpo) == crc
        nomes.append(tipo)
        pos += 12 + tamanho
    return nomes


def test_download_png_valido_sem_metadados(api):
    r = api.c.get("/api/v1/carteirinha/imagem.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"] == 'attachment; filename="carteirinha-apm.png"'
    chunks = _chunks_png(r.content)
    assert chunks[0] == "IHDR" and chunks[-1] == "IEND"
    assert not set(chunks) & {"tEXt", "zTXt", "iTXt", "eXIf", "iCCP", "tIME"}
    img = Image.open(io.BytesIO(r.content))
    assert img.size == (1012, 638) and img.format == "PNG" and not img.text
    for pii in (b"12345678901", b"telma@", b"98888", NOME.encode()):
        assert pii not in r.content


def test_download_pdf_valido_sem_metadados_do_associado(api):
    r = api.c.get("/api/v1/carteirinha/documento.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"] == 'attachment; filename="carteirinha-apm.pdf"'
    assert r.content.startswith(b"%PDF-") and r.content.rstrip().endswith(b"%%EOF")
    for pii in (b"TELMA", b"12345678901", b"telma@", b"98888", b"80012345"):
        assert pii not in r.content
    # Dicionário /Info: só chaves genéricas, valores fixos (UTF-16BE no Pillow), nada do associado.
    info = r.content[r.content.index(b"6 0 obj"):].split(b">>endobj", 1)[0]
    chaves = set(re.findall(rb"/([A-Za-z]+) ", info))
    assert chaves <= {b"Title", b"Author", b"Creator", b"Producer", b"CreationDate", b"ModDate"}, chaves
    assert "Carteirinha APM".encode("utf-16-be") in info
    for pii in (NOME, "TELMA", "80012345", "Efetivo"):
        assert pii.encode("utf-16-be") not in r.content
    assert b"/MediaBox [ 0 0 242.88 153.12 ]" in r.content  # 85,6 × 54 mm


def test_download_limite_10_por_hora_somando_formatos(api):
    for i in range(10):
        rota = "/api/v1/carteirinha/imagem.png" if i % 2 else "/api/v1/carteirinha/documento.pdf"
        assert api.c.get(rota).status_code == 200
    r = api.c.get("/api/v1/carteirinha/imagem.png")
    assert r.status_code == 429 and r.json()["erro"] == "limite_taxa"


def test_download_exige_sessao():
    from app import main

    c = TestClient(main.app, base_url=BASE)
    for rota in ("/api/v1/carteirinha/imagem.png", "/api/v1/carteirinha/documento.pdf"):
        assert c.get(rota).status_code == 401


# ----------------------------------------------------------------- render puro
def test_render_texto_fora_dos_subconjuntos_e_situacao_nao_confirmada():
    from app.dominio import carteirinha_arquivo as ca

    assert ca.limpar("  JOÃO\x00 \u200bDA\tSILVA  ") == "JOÃO DA SILVA"
    assert ca._trechos("Łódź 中 ç") == [("Ł", "latin-ext"), ("ód", "latin"), ("ź", "latin-ext"), ("  ç", "latin")]
    dados = ca.DadosCartao("A" * 160, "Efetivo", None, None, None, "https://minha.apm.org.br/verificar/" + TOKEN)
    img = ca.desenhar(dados)
    assert img.size == (ca.LARGURA, ca.ALTURA) and img.mode == "RGB"


def test_qr_do_arquivo_aponta_para_a_url_de_verificacao():
    """O QR desenhado é a matriz do segno da URL: confere módulos no canto (padrão localizador)."""
    import segno

    from app.dominio import carteirinha_arquivo as ca

    url = "https://minha.apm.org.br/verificar/" + TOKEN
    img = ca.desenhar(ca.DadosCartao(NOME, None, None, None, "Ativo", url))
    n = len(segno.make(url, error="m", micro=False).matrix)
    modulo = (250 - 32) // n
    x0 = ca.LARGURA - 56 - 250 + (250 - modulo * n) // 2
    y0 = 196 + (250 - modulo * n) // 2
    canto = img.getpixel((x0 + modulo // 2, y0 + modulo // 2))
    centro_branco = img.getpixel((x0 + modulo + modulo // 2, y0 + modulo + modulo // 2))
    assert canto == (0x00, 0x17, 0x2D) and centro_branco == (255, 255, 255)


# ------------------------------------------------------- integração MySQL (014)
@pytest.mark.mysql
def test_mysql_sql014_revogacao_e_situacao_ponta_a_ponta(monkeypatch):
    """Requer sql/000..009 + 014 aplicadas (usuário apm_area). Usa o UPDATE real."""
    import uuid

    from sqlalchemy import text

    from app.database import session_scope
    from app.dominio import carteirinha
    from app.limites import LimiteJanela

    carteirinha.redefinir_cache_colunas()
    carteirinha.redefinir_limite(LimiteJanela(1000, 60))
    assert carteirinha.colunas_revogacao_presentes() is True
    cid = str(uuid.uuid4())
    token = carteirinha.token_para(cid)
    agora = _agora()
    with session_scope() as db:
        db.execute(text("INSERT INTO associado (contact_id, sub_hash, primeiro_acesso_em, ultimo_acesso_em, "
                        "carteirinha_token) VALUES (:c, :h, :a, :a, :t)"), {"c": cid, "h": "0" * 64, "a": agora,
                                                                            "t": token})
        db.execute(text("INSERT INTO associado_perfil (contact_id, nome, status_associativo, origem, atualizado_em) "
                        "VALUES (:c, 'ENSAIO ONDA DOIS', 'Ativo', 'stub', :a)"), {"c": cid, "a": agora})

    v = carteirinha.resolver(token, hub=HubFalso("ativo"))
    assert v.resultado == "ativo" and not v.revogada

    with session_scope() as db:  # força o TTL vencido
        db.execute(text("UPDATE associado SET situacao_consultada_em = :v WHERE contact_id = :c"),
                   {"v": agora - timedelta(hours=1), "c": cid})
    v = carteirinha.resolver(token, hub=HubFalso("cancelado"))
    assert v.revogada and v.resultado == "inativo" and carteirinha.revogada(cid) is True
    with session_scope() as db:
        primeira = db.execute(text("SELECT carteirinha_revogada_em, situacao_normalizada FROM associado "
                                   "WHERE contact_id = :c"), {"c": cid}).first()
    assert primeira.situacao_normalizada == "cancelado" and primeira.carteirinha_revogada_em is not None

    # Nova leitura "cancelado" mantém a data original da revogação.
    with session_scope() as db:
        carteirinha.atualizar_situacao(db, cid, hub=HubFalso("cancelado"))
        segunda = db.execute(text("SELECT carteirinha_revogada_em FROM associado WHERE contact_id = :c"),
                             {"c": cid}).scalar()
    assert segunda == primeira.carteirinha_revogada_em

    # Reativação confirmada pelo CRM.
    with session_scope() as db:
        carteirinha.atualizar_situacao(db, cid, hub=HubFalso("ativo"))
    assert carteirinha.revogada(cid) is False

    # CHECK do par: situação sem data é recusada pelo banco.
    from sqlalchemy.exc import SQLAlchemyError

    with pytest.raises(SQLAlchemyError), session_scope() as db:
        db.execute(text("UPDATE associado SET situacao_consultada_em = NULL WHERE contact_id = :c"), {"c": cid})
    # DELETE continua proibido para apm_area.
    with pytest.raises(SQLAlchemyError), session_scope() as db:
        db.execute(text("DELETE FROM associado WHERE contact_id = :c"), {"c": cid})
    carteirinha.redefinir_limite(None)


def test_download_registra_carteirinha_baixar_com_formato(api):
    """RF-CA-07: cada download gerado grava `carteirinha_baixar` com o formato; recusa não grava."""
    for rota, formato in (("/api/v1/carteirinha/imagem.png", "png"), ("/api/v1/carteirinha/documento.pdf", "pdf")):
        antes = len(api.gravados)
        assert api.c.get(rota).status_code == 200
        novos = [g for g in api.gravados[antes:] if g.get("acao") == "carteirinha_baixar"]
        assert len(novos) == 1, novos
        assert novos[0]["origem"] == "servidor"
        assert '"formato": "%s"' % formato in str(novos[0]["detalhes"]) or novos[0]["detalhes"].get("formato") == formato
    api.revogada = True
    antes = len(api.gravados)
    assert api.c.get("/api/v1/carteirinha/imagem.png").status_code == 409
    assert not [g for g in api.gravados[antes:] if g.get("acao") == "carteirinha_baixar"]
