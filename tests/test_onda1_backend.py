"""Onda 1 — backend pequeno: TI-05 (acesso_primeiro), TI-04 (catálogo tipado),
TI-11 (campanha no servidor), TI-09 (step-up reutilizável), TI-13 (flags v2).
Sem banco e sem rede."""

from __future__ import annotations

import json
import re
import time
from datetime import date

import pytest
from sqlalchemy.exc import OperationalError

from app import uso
from app.dominio import associado as dom

GUID = "6b1f3c1e-4f3a-5d2b-9c7e-a5e0c0de57b0"


# ------------------------------------------------------------------ TI-05
@pytest.fixture
def uso_gravado(monkeypatch):
    linhas: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda ls: linhas.extend(ls))
    return linhas


def test_acesso_primeiro_so_quando_o_upsert_insere(monkeypatch, uso_gravado):
    monkeypatch.setattr(dom, "_ler_data_filiacao", lambda cid: None)
    monkeypatch.setattr(dom, "_executar", lambda p: 2)  # linha já existia (atualizou)
    assert dom.registrar_acesso(GUID, "sub-1", data_filiacao="2014-03-01") is True
    assert uso_gravado == []

    monkeypatch.setattr(dom, "_executar", lambda p: 1)  # inseriu
    assert dom.registrar_acesso(GUID, "sub-1", data_filiacao="2014-03-01") is True
    assert len(uso_gravado) == 1
    linha = uso_gravado[0]
    assert (linha["acao"], linha["entidade"], linha["origem"], linha["entidade_id"]) == (
        "acesso_primeiro", "associado", "servidor", GUID)
    assert linha["contact_id"] == GUID and linha["sub_hash"] and "sub-1" not in json.dumps(linha)
    detalhes = json.loads(linha["detalhes"])
    assert set(detalhes) == {"dias_desde_filiacao"}
    assert detalhes["dias_desde_filiacao"] == (date.today() - date(2014, 3, 1)).days


def test_acesso_primeiro_prefere_a_filiacao_do_cache_e_aceita_sem_data(monkeypatch, uso_gravado):
    monkeypatch.setattr(dom, "_executar", lambda p: 1)
    monkeypatch.setattr(dom, "_ler_data_filiacao", lambda cid: date(2020, 1, 1))
    dom.registrar_acesso(GUID, "s", data_filiacao="2014-03-01")
    assert json.loads(uso_gravado[-1]["detalhes"])["dias_desde_filiacao"] == (date.today() - date(2020, 1, 1)).days

    monkeypatch.setattr(dom, "_ler_data_filiacao", lambda cid: None)
    dom.registrar_acesso(GUID, "s", data_filiacao=None)
    assert uso_gravado[-1]["detalhes"] is None  # sem data: evento vai, sem o detalhe

    dom.registrar_acesso(GUID, "s", data_filiacao="2999-01-01")  # filiação futura = dado ruim, não negativo
    assert uso_gravado[-1]["detalhes"] is None


def test_acesso_primeiro_nunca_derruba_o_login(monkeypatch, uso_gravado):
    def fora(cid):
        raise OperationalError("select", {}, Exception("down"))

    monkeypatch.setattr(dom, "_executar", lambda p: 1)
    monkeypatch.setattr(dom, "_ler_data_filiacao", fora)
    assert dom.registrar_acesso(GUID, "s", data_filiacao="2014-03-01") is True
    assert json.loads(uso_gravado[-1]["detalhes"])["dias_desde_filiacao"] > 4000

    monkeypatch.setattr(dom, "_ler_data_filiacao", lambda cid: None)
    monkeypatch.setattr(uso, "_gravar", lambda ls: (_ for _ in ()).throw(OperationalError("insert", {}, Exception())))
    assert dom.registrar_acesso(GUID, "s") is True  # falha do evento só conta em uso.falhas()


def test_acesso_sem_contagem_do_driver_nao_emite(monkeypatch, uso_gravado):
    monkeypatch.setattr(dom, "_executar", lambda p: None)  # driver sem rowcount: não dá para afirmar
    assert dom.registrar_acesso(GUID, "s") is True
    assert uso_gravado == []
    assert dom.registrar_acesso("nao-e-guid", "s") is False


def test_dias_desde_filiacao():
    assert dom.dias_desde_filiacao(date(2026, 1, 1), hoje=date(2026, 1, 31)) == 30
    assert dom.dias_desde_filiacao(date(2026, 2, 1), hoje=date(2026, 1, 31)) is None
    assert dom.dias_desde_filiacao(None) is None
    assert dom._como_data("2014-03-01T00:00:00") == date(2014, 3, 1)
    assert dom._como_data("lixo") is None and dom._como_data(12) is None


# ------------------------------------------------------------------ TI-04
def _det(acao, entidade, detalhes, origem="ui"):
    _, dump = uso._validar(uso.Evento(acao, entidade, None, detalhes), origem)
    return json.loads(dump) if dump else {}


def test_detalhes_tipados_por_acao_descartam_so_a_chave_invalida():
    assert _det("beneficio_abrir", "beneficio", {"origem": "home", "estado": "libera_em", "slug": "x"}) == {
        "origem": "home", "estado": "libera_em"}
    assert _det("beneficio_abrir", "beneficio", {"origem": "google", "estado": "ativo"}) == {"estado": "ativo"}
    assert _det("pagina_ver", "rota", {"blocos": ["pendencia", "radar"], "segmento": "efetivo-sp", "disp": "pwa",
                                       "gatilho": "A20"}) == {
        "blocos": ["pendencia", "radar"], "segmento": "efetivo-sp", "disp": "pwa", "gatilho": "A20"}
    assert _det("pagina_ver", "rota", {"blocos": ["pendencia", "pendencia"], "disp": "tv"}) == {}
    assert _det("pagina_ver", "rota", {"blocos": ["inventado"]}) == {}
    assert _det("home_bloco_clicar", "home_bloco", {"bloco": "recomendados", "posicao": 2, "item": "seguro-renda"}) == {
        "bloco": "recomendados", "posicao": 2, "item": "seguro-renda"}
    assert _det("ajuda_contatar", "central", {"canal": "whatsapp", "assunto": "financeiro"}) == {
        "canal": "whatsapp", "assunto": "financeiro"}
    assert _det("ajuda_contatar", "central", {"canal": "pombo", "assunto": "Preciso de ajuda com o boleto"}) == {}
    assert _det("notificacao_abrir", "notificacao", {"tipo": "solicitacao_concluida"}) == {"tipo": "solicitacao_concluida"}
    assert _det("noticia_abrir", "noticia", {"tema": "cardiologia", "titulo": "x"}) == {"tema": "cardiologia"}


def test_vitais_e_erro_js_so_numeros_e_tipos_sem_stack():
    assert _det("vitais_web", "rota", {"lcp": 1234.567, "inp": 180, "cls": 0.0423, "rota": "/area"}) == {
        "lcp": 1234.6, "inp": 180.0, "cls": 0.042, "rota": "/area"}
    assert _det("vitais_web", "rota", {"lcp": -1, "inp": 99_999_999, "cls": float("nan")}) == {}
    assert _det("vitais_web", "rota", {"lcp": True}) == {}
    assert _det("erro_js", "rota", {"tipo": "typeerror", "rota": "/area/perfil", "stack": "at x.js:1", "mensagem": "boom"}) == {
        "tipo": "typeerror", "rota": "/area/perfil"}


def test_servidor_e_job_tambem_sao_tipados_quando_ha_esquema():
    assert _det("solicitacao_status_alterado", "solicitacao",
                {"de": "criada", "para": "enviada", "origem": "sistema", "payload": {"cpf": "x"}}, "job") == {
        "de": "criada", "para": "enviada", "origem": "sistema"}
    assert _det("solicitacao_status_alterado", "solicitacao", {"de": "aberta", "para": "sem_retorno"}, "servidor") == {}
    assert _det("solicitacao_avaliar", "solicitacao", {"nota": 10, "comentario": "ótimo"}, "servidor") == {"nota": 10}
    assert _det("solicitacao_avaliar", "solicitacao", {"nota": 11}, "servidor") == {}
    assert _det("cancelamento_pedir", "associado", {"motivo": "preco"}, "servidor") == {"motivo": "preco"}
    assert _det("cancelamento_pedir", "associado", {"motivo": "caro demais"}, "servidor") == {}
    assert _det("consentimento_alterar", "consentimento",
                {"finalidade": "ofertas", "canal": "whatsapp", "valor": "retirado", "versao": "v2"}, "servidor") == {
        "finalidade": "ofertas", "canal": "whatsapp", "valor": "retirado", "versao": "v2"}
    assert _det("uso_registrar", "uso_valor", {"fonte": "clube", "nivel": 3, "valor": 199.9}, "job") == {
        "fonte": "clube", "nivel": 3}  # valores em reais nunca entram
    assert _det("uso_registrar", "uso_valor", {"nivel": 0}, "servidor") == {}
    assert _det("carencia_vencer", "beneficio", {"liberado_em": "2026-11-10"}, "job") == {"liberado_em": "2026-11-10"}
    assert _det("carencia_vencer", "beneficio", {"liberado_em": "10/11/2026"}, "job") == {}
    assert _det("fatura_segunda_via", "fatura", {"competencia": "2026-10", "forma": "pix", "valor": 120}, "servidor") == {
        "competencia": "2026-10", "forma": "pix"}
    assert _det("pagamento_confirmar", "fatura", {"competencia": "2026-13", "forma": "pdf"}, "job") == {"forma": "pdf"}
    assert _det("perfil_declarado_atualizar", "perfil_declarado", {"campos": ["especialidade", "consultorio"]},
                "servidor") == {"campos": ["especialidade", "consultorio"]}
    assert _det("perfil_declarado_atualizar", "perfil_declarado", {"campos": ["Especialidade: cardio"]}, "servidor") == {}
    assert _det("carteirinha_verificar", "carteirinha", {"resultado": "nao_confirmado"}, "publico") == {
        "resultado": "nao_confirmado"}
    assert _det("recomendacao_dispensar", "beneficio", {"motivo": "depois"}, "servidor") == {"motivo": "depois"}
    assert _det("acesso_primeiro", "associado", {"dias_desde_filiacao": 12, "metodo": "email"}, "servidor") == {
        "dias_desde_filiacao": 12}


def test_origens_novas_e_removidas():
    assert "job" in uso.CATALOGO["solicitacao_status_alterado"].origens
    assert "servidor" in uso.CATALOGO["solicitacao_status_alterado"].origens
    assert uso.CATALOGO["uso_registrar"].origens == {"servidor", "job"}
    with pytest.raises(ValueError, match="acao_desconhecida"):
        uso._validar(uso.Evento("fatura_pdf_baixar", "fatura"), "servidor")
    with pytest.raises(ValueError, match="origem_invalida"):
        uso._validar(uso.Evento("acesso_primeiro", "associado"), "ui")
    # Ação sem esquema de origem servidor continua passando pelo filtro de chaves proibidas.
    assert _det("perfil_foto_atualizar", "associado_perfil", {"bytes": 10, "token": "x"}, "servidor") == {"bytes": 10}


# ------------------------------------------------------------------ TI-11
def test_campanha_validada_no_servidor_pelo_mesmo_catalogo():
    assert _det("pagina_ver", "rota", {"campanha": {"origem": "rd", "meio": "email", "campanha": "boas-vindas_1",
                                                    "gatilho": "A03", "extra": "x"}}) == {
        "campanha": {"origem": "rd", "meio": "email", "campanha": "boas-vindas_1", "gatilho": "A03"}}
    assert _det("pagina_ver", "rota", {"campanha": {"origem": "RD Station", "gatilho": "A21"}}) == {}
    assert _det("pagina_ver", "rota", {"campanha": {"origem": "a" * 33}}) == {}
    assert _det("pagina_ver", "rota", {"campanha": {"origem": "//evil.com"}}) == {}
    assert _det("pagina_ver", "rota", {"campanha": "rd"}) == {}
    assert _det("pagina_ver", "rota", {"gatilho": "a03"}) == {}  # servidor não normaliza caixa: a SPA já o fez
    assert uso.RE_GATILHO.match("A20") and not uso.RE_GATILHO.match("A00") and not uso.RE_GATILHO.match("A21")
    assert uso.RE_UTM.match("rd-station_2") and not uso.RE_UTM.match("-rd") and not uso.RE_UTM.match("")


def test_campanha_chega_pela_api_de_uso_e_e_gravada(monkeypatch):
    from app import main
    from tests.test_api import TOKEN_STUB, _cabecalhos, entrar

    from fastapi.testclient import TestClient

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    monkeypatch.setattr(dom, "_executar", lambda p: None)
    gravados: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda ls: gravados.extend(ls))
    c = TestClient(main.app, base_url="https://minha.apm.org.br")
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    r = c.post("/api/v1/uso", json={"eventos": [
        {"acao": "pagina_ver", "entidade": "rota", "entidade_id": "/area",
         "detalhes": {"campanha": {"origem": "rd", "gatilho": "A03"}, "blocos": ["pendencia"], "disp": "mobile"}},
        {"acao": "vitais_web", "entidade": "rota", "detalhes": {"lcp": 1200.5, "cls": 0.01}},
    ]}, headers=_cabecalhos(csrf))
    assert r.status_code == 202 and r.json() == {"gravados": 2, "descartados": 0}
    assert json.loads(gravados[0]["detalhes"]) == {"campanha": {"origem": "rd", "gatilho": "A03"},
                                                   "blocos": ["pendencia"], "disp": "mobile"}
    assert json.loads(gravados[1]["detalhes"]) == {"lcp": 1200.5, "cls": 0.01}
    # Sub-objeto aninhado em mais de um nível ou lista longa: recusado na borda (400), sem ecoar valores.
    r = c.post("/api/v1/uso", json={"eventos": [
        {"acao": "pagina_ver", "entidade": "rota", "detalhes": {"campanha": {"x": {"y": 1}}}}]}, headers=_cabecalhos(csrf))
    assert r.status_code == 400 and r.json()["erro"] == "entrada_invalida"
    r = c.post("/api/v1/uso", json={"eventos": [
        {"acao": "pagina_ver", "entidade": "rota", "detalhes": {"blocos": ["b"] * 17}}]}, headers=_cabecalhos(csrf))
    assert r.status_code == 400


# ------------------------------------------------------------------ TI-09
def _associado(idp_at):
    from app.session_guard import Associado

    return Associado(sub="s", contact_id=GUID, nome=None, email=None, cpf_mask=None, auth_at=int(time.time()),
                     amr=("pwd",), idp_auth_time=idp_at)


def test_exigir_reautenticacao_e_dependencia_reutilizavel_no_contrato_unico():
    from app.api.erros import ApiError
    from app.api.v1.deps import exigir_reautenticacao, verificar_reautenticacao

    exigir_reautenticacao(_associado(int(time.time()) - 60))  # recente: passa
    with pytest.raises(ApiError) as erro:
        exigir_reautenticacao(_associado(int(time.time()) - 901))
    assert (erro.value.status, erro.value.erro) == (403, "reautenticacao_necessaria")
    assert "Login APM" in erro.value.mensagem
    with pytest.raises(ApiError):
        exigir_reautenticacao(_associado(None))  # sem auth_time do IdP não há prova (regra 22)
    with pytest.raises(ApiError, match="reautenticacao_necessaria") as erro:
        verificar_reautenticacao(_associado(None), "texto próprio")
    assert erro.value.mensagem == "texto próprio"


@pytest.fixture
def edicao_ligada(monkeypatch):
    """Sessão stub + escrita habilitada + hub espião, sem banco."""
    from app import audit, main
    from app.api.v1 import perfil as rota_perfil
    from app.dominio import perfil as dominio
    from app.integracoes.hub import redefinir_hub
    from app.limites import LimiteJanela
    from tests.test_api import TOKEN_STUB, _HubEspiao

    from fastapi.testclient import TestClient

    from app.config import get_settings

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    # As rotas leem get_settings() (instância do teste), não main.settings (instância do boot).
    monkeypatch.setattr(get_settings(), "hub_escrita_habilitada", True)
    monkeypatch.setattr(dom, "_executar", lambda p: None)
    monkeypatch.setattr(uso, "_gravar", lambda ls: None)
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: None)
    monkeypatch.setattr(LimiteJanela, "permitir", lambda self, chave: True)
    monkeypatch.setattr(dominio, "aplicar_contato", lambda cid, campos: None)
    monkeypatch.setattr(dominio, "ler", lambda cid: dominio.Perfil(contact_id=cid, nome="Telma", celular="(11) 97777-6666"))
    monkeypatch.setattr(rota_perfil.perfil, "obter", lambda cid: dominio.Perfil(contact_id=cid, nome="Telma"))
    hub = _HubEspiao()
    redefinir_hub(hub)
    c = TestClient(main.app, base_url="https://minha.apm.org.br")
    yield {"c": c, "hub": hub, "settings": get_settings()}
    redefinir_hub(None)


def _entrar_e_csrf(c, *, reauth: bool = False):
    from tests.test_api import TOKEN_STUB, _cabecalhos, entrar

    if not reauth:
        entrar(c)
    else:
        # Mesmo caminho da SPA no step-up: /auth/login?reauth=1 mostra o formulário mesmo com sessão.
        r = c.get("/auth/login", params={"next": "/area/perfil", "reauth": "1"})
        assert r.status_code == 200
        csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
        r = c.post("/auth/login", data={"csrf": csrf, "token": TOKEN_STUB, "nome": "TELMA", "email": "t@x.org",
                                        "cpf": "12345678901", "tipo": "Efetivo", "next": "/area/perfil"},
                   follow_redirects=False)
        assert r.status_code == 303
    return _cabecalhos(c.get("/api/v1/sessao").json()["csrf"])


def test_celular_sem_step_up_por_padrao_e_com_step_up_quando_ligado(edicao_ligada, monkeypatch):
    c, hub, s = edicao_ligada["c"], edicao_ligada["hub"], edicao_ligada["settings"]
    h = _entrar_e_csrf(c)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 1000)  # senha digitada há ~17 min

    assert s.celular_exige_reauth is False  # padrão documentado: ligar quando o IdP mandar OTP por celular
    r = c.put("/api/v1/perfil/contato", json={"celular": "11988887777"}, headers=h)
    assert r.status_code == 200 and hub.chamadas == ["contato_atualizar"]
    assert r.json()["celular_exige_reautenticacao"] is False and r.json()["email_exige_reautenticacao"] is True

    monkeypatch.setattr(s, "celular_exige_reauth", True)
    hub.chamadas.clear()
    r = c.put("/api/v1/perfil/contato", json={"celular": "11988887777"}, headers=h)
    assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria"
    assert "celular" in r.json()["mensagem"] and hub.chamadas == []  # antes do hub e do limite
    assert c.get("/api/v1/perfil").json()["celular_exige_reautenticacao"] is True
    # Telefone fixo não é canal de OTP: segue sem step-up.
    r = c.put("/api/v1/perfil/contato", json={"telefone": "1133334444"}, headers=h)
    assert r.status_code == 200 and hub.chamadas == ["contato_atualizar"]

    # Senha digitada de novo (reauth=1 → novo login, idp_at recente): celular passa.
    h = _entrar_e_csrf(c, reauth=True)
    r = c.put("/api/v1/perfil/contato", json={"celular": "11988887777"}, headers=h)
    assert r.status_code == 200 and r.json()["celular_exige_reautenticacao"] is False


def test_troca_de_email_mantem_comportamento_e_mensagem(edicao_ligada, monkeypatch):
    c = edicao_ligada["c"]
    h = _entrar_e_csrf(c)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 1000)
    r = c.post("/api/v1/perfil/email", json={"email": "x@exemplo.org"}, headers=h)
    assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria"
    assert r.json()["mensagem"] == "Por segurança, confirme sua senha no Login APM antes de trocar o e-mail."
    r = c.post("/api/v1/perfil/email/confirmar", json={"email": "x@exemplo.org", "codigo": "123456"}, headers=h)
    assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria"


def test_celular_exige_reauth_e_booleano(monkeypatch):
    from pydantic import ValidationError

    from app.config import Settings

    monkeypatch.setenv("CELULAR_EXIGE_REAUTH", "true")
    assert Settings().celular_exige_reauth is True
    monkeypatch.setenv("CELULAR_EXIGE_REAUTH", "talvez")
    with pytest.raises(ValidationError):
        Settings()


# ------------------------------------------------------------------ TI-13
def test_flags_v2_conhecidas_nascem_desligadas_e_forcadas_continuam_validadas(monkeypatch):
    from pydantic import ValidationError

    from app import flags
    from app.config import Settings

    novas = {"notificacoes", "encaminhamento_parceiro", "reservas", "inscricoes", "comunicacao_outbox",
             "cancelamento_online", "lgpd_consentimentos"}
    assert novas <= set(flags.FLAGS_CONHECIDAS) and len(flags.FLAGS_CONHECIDAS) == 15
    assert len(set(flags.FLAGS_CONHECIDAS)) == 15
    assert all(re.fullmatch(r"[a-z][a-z0-9_]{1,47}", f) for f in flags.FLAGS_CONHECIDAS)

    monkeypatch.setattr(flags, "_ler_tabela", lambda: {})  # 009 ainda não aplicada
    flags.limpar_cache()
    efetivas = flags.flags_efetivas()
    assert set(efetivas) == set(flags.FLAGS_CONHECIDAS) and not any(efetivas.values())

    monkeypatch.setattr(flags, "_ler_tabela", lambda: {"notificacoes": True, "lgpd_consentimentos": True})
    flags.limpar_cache()
    assert flags.ligada("notificacoes") is True and flags.ligada("reservas") is False
    monkeypatch.setenv("FLAGS_FORCAR_DESLIGADAS", "notificacoes")
    from app.config import get_settings

    get_settings.cache_clear()
    flags.limpar_cache()
    assert flags.ligada("notificacoes") is False and flags.ligada("lgpd_consentimentos") is True
    flags.limpar_cache()

    monkeypatch.setenv("FLAGS_FORCAR_DESLIGADAS", "Chave Ruim")
    with pytest.raises(ValidationError, match="FLAGS_FORCAR_DESLIGADAS"):
        Settings()
