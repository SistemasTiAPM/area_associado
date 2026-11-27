"""P13 Perfil e privacidade — unidades sem banco (Onda 3; ADR-0025 e ADR-0026).

Cobre: catálogos e validação do perfil declarado, escolha da pergunta do perfil
progressivo, recorte mínimo de agregados (TI-90), registro de acesso a dado
pessoal, protocolo do pedido do titular e a ordem das dependências das rotas
(flag → step-up → prontidão), sem tocar o banco.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.dominio import agregacao, consentimento, preferencias, titular


# ------------------------------------------------------------ preferências
@pytest.mark.parametrize("bruto,esperado", [
    ("  Dra.   Ana ", "Dra. Ana"),
    ("Dr. João d'Ávila", "Dr. João d'Ávila"),
    ("Ana-Maria", "Ana-Maria"),
    ("", None),
    ("   ", None),
    (None, None),
])
def test_tratamento_normaliza_e_vazio_vira_saudacao_neutra(bruto, esperado):
    assert preferencias.validar_tratamento(bruto) == esperado


@pytest.mark.parametrize("bruto", [
    "A",                      # curto
    "x" * 41,                 # longo
    "Dra. Ana 123",           # dígito (barra CPF e telefone)
    "123.456.789-09",
    "<b>Ana</b>",             # marcação
    "Ana & Cia",
    "Ana\x00",
    ".Ana",                   # começa por pontuação
    42,
])
def test_tratamento_recusa_digito_marcacao_e_tamanho(bruto):
    with pytest.raises(preferencias.PreferenciaInvalida) as erro:
        preferencias.validar_tratamento(bruto)
    assert erro.value.detalhes[0]["campo"] == "tratamento"
    # O valor recebido nunca volta na mensagem (contrato de erro).
    assert str(bruto) not in erro.value.detalhes[0]["mensagem"]


def test_validar_listas_seguem_a_ordem_do_catalogo_e_recusam_fora_dele():
    campos = preferencias.validar({"atuacao": ["plantao", "consultorio_proprio", "plantao"], "temas": [],
                                   "frequencia": "minima", "fonte": "grande", "canal_preferido": "email"})
    assert campos == {"atuacao": ("consultorio_proprio", "plantao"), "temas": (), "frequencia": "minima",
                      "fonte": "grande", "canal_preferido": "email"}
    assert preferencias.validar({"canal_preferido": None, "frequencia": None}) == {"canal_preferido": None,
                                                                                   "frequencia": None}
    for invalido in ({"atuacao": ["cirurgia"]}, {"temas": "tecnologia_ia"}, {"canal_preferido": "whatsapp"},
                     {"canal_preferido": "sms"}, {"canal_preferido": ["email"]}, {"frequencia": "diaria"},
                     {"fonte": None}, {"fonte": "enorme"}, {"especialidade": "cardiologia"}, {"canais": ["email"]},
                     {}):
        with pytest.raises(preferencias.PreferenciaInvalida):
            preferencias.validar(invalido)


def test_catalogos_da_spec_e_canais_so_os_que_existem():
    # REQUISITOS §9.1: slugs da área de atuação e frequência `normal`/`minima`.
    assert list(preferencias.ATUACAO) == ["consultorio_proprio", "hospital", "plantao", "pesquisa", "gestao",
                                          "docencia"]
    assert len(preferencias.TEMAS) == 8 and list(preferencias.FREQUENCIA) == ["normal", "minima"]
    # Regra 19: WhatsApp e SMS só entram quando houver canal contratado (P-64).
    assert list(preferencias.CANAL_PREFERIDO) == ["email"]
    assert consentimento.pares_visiveis() == [("ofertas_parceiros", "email")]
    assert [p.chave for p in preferencias.PERGUNTAS] == list(preferencias.CAMPOS_PERFIL)
    assert set(preferencias.opcoes()) == {"atuacao", "temas", "canal_preferido", "frequencia", "fonte"}


def test_pergunta_escolhida_pula_respondidas_recentes_e_esgotadas():
    agora = datetime(2026, 11, 19, 12, 0)
    vazio = preferencias.Preferencias()
    assert preferencias._escolher(vazio, {}, agora).chave == "tratamento"
    # Respondida → próxima.
    assert preferencias._escolher(preferencias.Preferencias(tratamento="Dra. Ana"), {}, agora).chave == "atuacao"
    # Pulada há pouco → próxima; passado o intervalo, volta.
    recente = {"tratamento": (agora - timedelta(days=3), 1)}
    assert preferencias._escolher(vazio, recente, agora).chave == "atuacao"
    antiga = {"tratamento": (agora - preferencias.PULAR_INTERVALO - timedelta(seconds=1), 1)}
    assert preferencias._escolher(vazio, antiga, agora).chave == "tratamento"
    # Pulada vezes demais → nunca mais (continua editável no perfil).
    esgotada = {"tratamento": (agora - timedelta(days=400), preferencias.PULAR_MAX)}
    assert preferencias._escolher(vazio, esgotada, agora).chave == "atuacao"
    completo = preferencias.Preferencias(tratamento="Ana", atuacao=("hospital",), temas=("comunidade",),
                                         frequencia="normal")
    assert preferencias._escolher(completo, {}, agora) is None and completo.faltam() == []
    assert vazio.faltam() == ["tratamento", "atuacao", "temas", "frequencia"]


def test_sql_de_gravacao_so_aceita_colunas_da_allowlist():
    sql = str(preferencias._sql_gravar(("tratamento", "fonte")))
    assert "tratamento = novo.tratamento" in sql and "fonte = novo.fonte" in sql and "atuacao" not in sql
    with pytest.raises(ValueError):
        preferencias._sql_gravar(("contact_id",))
    with pytest.raises(ValueError):
        preferencias._sql_gravar(("fonte; DROP TABLE associado",))


def test_resumo_da_sessao_nunca_lanca(monkeypatch):
    from sqlalchemy.exc import OperationalError

    def fora(_cid):
        raise OperationalError("x", {}, Exception("down"))

    monkeypatch.setattr(preferencias, "ler", fora)
    assert preferencias.resumo_sessao("c") == {"fonte": "padrao", "tratamento": None}
    assert preferencias.resumo_sessao(None) == {"fonte": "padrao", "tratamento": None}
    monkeypatch.setattr(preferencias, "ler", lambda cid: preferencias.Preferencias(tratamento="Dra. Ana",
                                                                                   fonte="maior"))
    assert preferencias.resumo_sessao("c") == {"fonte": "maior", "tratamento": "Dra. Ana"}


# -------------------------------------------------------------- agregação
def test_agregar_suprime_recorte_pequeno_e_nao_revela_o_total():
    r = agregacao.agregar({"cardiologia": 40, "pediatria": 20, "genetica": 3})
    assert r.grupos == {"cardiologia": 40, "pediatria": 20}
    # O total é o do que foi publicado: 63 − 60 devolveria o grupo escondido.
    assert r.total == 60 and r.suprimidos == 1


def test_agregar_junta_pequenos_em_outros_so_quando_alcancam_o_minimo():
    r = agregacao.agregar([("a", 30), ("b", 12), ("c", 9)])
    assert r.grupos == {"a": 30, "outros": 21} and r.total == 51 and r.suprimidos == 0
    r = agregacao.agregar([("a", 30), ("b", 12), ("c", 5)])
    assert r.grupos == {"a": 30} and r.suprimidos == 2
    # Um único grupo pequeno, mesmo ≥ mínimo não existe; com n < mínimo nunca vira `outros`.
    r = agregacao.agregar({"a": 30, "b": 19})
    assert r.grupos == {"a": 30} and r.suprimidos == 1
    assert agregacao.agregar({"a": 19, "b": 0}).grupos == {}
    assert agregacao.agregar({"a": 5}, min_n=5).grupos == {"a": 5}


@pytest.mark.parametrize("entrada,min_n", [({"a": -1}, 20), ({"a": True}, 20), ({"a": 1.5}, 20),
                                           ({"outros": 30}, 20), ({"a": 30}, 1), ({"a": 30}, True)])
def test_agregar_recusa_entrada_invalida(entrada, min_n):
    with pytest.raises(ValueError):
        agregacao.agregar(entrada, min_n=min_n)


# ------------------------------------------------- acesso a dado pessoal
def test_registro_de_acesso_a_dado_pessoal_grava_hash_do_titular_e_nomes(monkeypatch):
    from app import audit

    gravados: list[dict] = []
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: gravados.append(kw))
    alvo = "1538029d-dbde-f111-84e8-7ced8db12239"
    audit.registrar_acesso_dado_pessoal(SimpleNamespace(), sub="s", ator_contact_id=alvo, alvo_contact_id=alvo,
                                        campos=["cadastro", "uso", "cadastro", "Valor Inválido", "x" * 40],
                                        finalidade="exportacao_titular")
    assert len(gravados) == 1
    linha = gravados[0]
    assert linha["categoria"] == "seguranca" and linha["tipo"] == "acesso_dado_pessoal"
    detalhes = linha["detalhes"]
    assert detalhes["campos"] == ["cadastro", "uso"] and detalhes["finalidade"] == "exportacao_titular"
    assert re.fullmatch(r"[0-9a-f]{64}", detalhes["alvo_contact_hash"]) and alvo not in str(detalhes)
    assert detalhes["alvo_contact_hash"] == audit.hash_contato(alvo.upper())  # normalizado
    # Finalidade fora do catálogo: nada gravado (e nada lançado).
    audit.registrar_acesso_dado_pessoal(SimpleNamespace(), sub="s", ator_contact_id=alvo, alvo_contact_id=alvo,
                                        campos=["cadastro"], finalidade="curiosidade")
    assert len(gravados) == 1


# ------------------------------------------------------------------ titular
def test_protocolo_tem_o_formato_do_check_e_varia():
    agora = datetime(2026, 11, 19, 15, 0)
    protocolos = {titular.gerar_protocolo(agora) for _ in range(50)}
    assert len(protocolos) == 50
    assert all(re.fullmatch(r"LGPD-20261119-[A-Z2-7]{6}", p) for p in protocolos)


def test_status_efetivo_le_o_cancelamento_da_solicitacao():
    assert titular._status_efetivo("registrado", "cancelada") == "cancelado"
    assert titular._status_efetivo("em_analise", "cancelada") == "cancelado"
    assert titular._status_efetivo("registrado", "criada") == "registrado"
    assert titular._status_efetivo("concluido", "cancelada") == "concluido"
    assert titular._status_efetivo("concluido", None) == "concluido"


def test_exportacao_declara_os_grupos_e_nao_promete_cpf():
    assert "cadastro" in titular.GRUPOS_EXPORTADOS and "uso" in titular.GRUPOS_EXPORTADOS
    assert any("CPF" in o for o in titular.OBSERVACOES_EXPORTACAO)
    assert titular.EXPORTACAO_INTERVALO == timedelta(days=7)


# ---------------------------------------------------------------- rotas
@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient

    from app import audit, flags, prontidao, uso
    from app.api.v1 import deps, privacidade as rota
    from app.csrf import exigir_csrf
    from app.limites import LimiteJanela
    from app.main import app
    from app.session_guard import Associado, require_associado

    cid = "1538029d-dbde-f111-84e8-7ced8db12239"
    estado = SimpleNamespace(
        flags={}, tabelas=frozenset(), idp=int(time.time()), cid=cid, usos=[], auditados=[],
    )

    def associado() -> Associado:
        return Associado(sub="sub-teste", contact_id=cid, nome="Ana", email=None, cpf_mask=None,
                         auth_at=int(time.time()), amr=("pwd",), idp_auth_time=estado.idp)

    app.dependency_overrides[require_associado] = associado
    app.dependency_overrides[deps.contexto] = lambda: deps.Contexto(associado(), cid)
    app.dependency_overrides[exigir_csrf] = lambda: None
    monkeypatch.setattr(flags, "_ler_tabela", lambda: estado.flags)
    monkeypatch.setattr(prontidao, "_ler_tabelas", lambda: estado.tabelas)
    monkeypatch.setattr(uso, "_gravar", lambda linhas: estado.usos.extend(linhas))
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: estado.auditados.append(kw))
    for nome in ("_limite_preferencias", "_limite_consentimento", "_limite_dados"):
        monkeypatch.setattr(rota, nome, LimiteJanela(1000, 60))

    def recarregar() -> None:
        flags.limpar_cache()
        prontidao.limpar_cache()

    estado.recarregar = recarregar
    recarregar()
    try:
        yield TestClient(app, base_url="https://minha.apm.org.br"), estado
    finally:
        app.dependency_overrides.clear()
        recarregar()


_TODAS = frozenset({"consentimento_texto", "consentimento", "perfil_declarado", "pergunta_perfil", "titular_pedido"})
_ROTAS_PREFERENCIAS = [("get", "/api/v1/perfil/preferencias", None), ("put", "/api/v1/perfil/preferencias",
                       {"fonte": "grande"}), ("get", "/api/v1/perfil/pergunta", None),
                       ("post", "/api/v1/perfil/pergunta/temas", {"pular": True})]
_ROTAS_LGPD = [("get", "/api/v1/perfil/consentimentos", None),
               ("put", "/api/v1/perfil/consentimentos", {"finalidade": "ofertas_parceiros", "canal": "email",
                                                         "concedido": True, "versao": "v0"}),
               ("get", "/api/v1/perfil/dados/pedidos", None), ("post", "/api/v1/perfil/dados/exportar", None),
               ("post", "/api/v1/perfil/dados/exclusao", {"confirmacao": "EXCLUIR",
                                                          "chave_idempotencia": "0b5c8f5e-3d5a-4c1e-9a55-2f1f6f0a7a11"})]


def _chamar(c, metodo, caminho, corpo):
    return getattr(c, metodo)(caminho, json=corpo) if corpo is not None else getattr(c, metodo)(caminho)


def test_flag_desligada_responde_404_recurso_desligado_em_todas_as_rotas(api):
    c, estado = api
    estado.tabelas = _TODAS
    estado.recarregar()
    for metodo, caminho, corpo in _ROTAS_PREFERENCIAS + _ROTAS_LGPD:
        r = _chamar(c, metodo, caminho, corpo)
        assert r.status_code == 404 and r.json()["erro"] == "recurso_desligado", caminho
    # Uma flag não liga a outra.
    estado.flags = {"perfil_preferencias": True}
    estado.recarregar()
    for metodo, caminho, corpo in _ROTAS_LGPD:
        assert _chamar(c, metodo, caminho, corpo).json()["erro"] == "recurso_desligado", caminho


def test_flag_ligada_sem_a_migracao_responde_503_sem_tocar_o_banco(api):
    c, estado = api
    estado.flags = {"perfil_preferencias": True, "lgpd_consentimentos": True}
    estado.recarregar()
    for metodo, caminho, corpo in _ROTAS_PREFERENCIAS + _ROTAS_LGPD:
        r = _chamar(c, metodo, caminho, corpo)
        assert r.status_code == 503 and r.json()["erro"] == "recurso_indisponivel", caminho


def test_exportar_e_excluir_exigem_senha_recente_antes_de_qualquer_coisa(api, monkeypatch):
    c, estado = api
    estado.flags = {"lgpd_consentimentos": True}
    estado.tabelas = _TODAS
    estado.idp = int(time.time()) - 86_400  # senha digitada ontem
    estado.recarregar()
    chamado = []
    monkeypatch.setattr(titular, "exportar", lambda **kw: chamado.append("exportar"))
    monkeypatch.setattr(titular, "pedir_exclusao", lambda **kw: chamado.append("excluir"))
    for metodo, caminho, corpo in _ROTAS_LGPD[3:]:
        r = _chamar(c, metodo, caminho, corpo)
        assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria", caminho
    assert chamado == [] and estado.usos == [] and estado.auditados == []
    # A listagem diz à tela que vai pedir a senha, sem exigir.
    monkeypatch.setattr(titular, "listar_pedidos", lambda cid: {"itens": [], "exportacao_disponivel_em": None,
                                                                "exclusao_aberta": None})
    r = c.get("/api/v1/perfil/dados/pedidos")
    assert r.status_code == 200 and r.json()["exige_reautenticacao"] is True


def test_exportar_entrega_anexo_no_store_e_registra_o_acesso(api, monkeypatch):
    c, estado = api
    estado.flags = {"lgpd_consentimentos": True}
    estado.tabelas = _TODAS
    estado.recarregar()
    monkeypatch.setattr(titular, "exportar", lambda **kw: titular.Exportacao(
        "LGPD-20261119-ABC234", {"formato": titular.FORMATO_EXPORTACAO, "cadastro": {"nome": "Ana"}}))
    r = c.post("/api/v1/perfil/dados/exportar")
    assert r.status_code == 200 and r.json()["cadastro"] == {"nome": "Ana"}
    assert r.headers["cache-control"] == "no-store"
    assert re.fullmatch(r'attachment; filename="minha-apm-dados-\d{8}\.json"', r.headers["content-disposition"])
    assert [u["acao"] for u in estado.usos] == ["dados_exportar"]
    acesso = [a for a in estado.auditados if a["tipo"] == "acesso_dado_pessoal"]
    assert len(acesso) == 1 and acesso[0]["detalhes"]["finalidade"] == "exportacao_titular"
    assert "Ana" not in str(acesso[0]["detalhes"])  # nomes de grupos, nunca valores

    def no_limite(**kw):
        raise titular.LimiteExportacao(datetime(2026, 11, 26, 15, 0))

    monkeypatch.setattr(titular, "exportar", no_limite)
    r = c.post("/api/v1/perfil/dados/exportar")
    assert r.status_code == 429 and r.json()["erro"] == "limite_negocio"
    assert "26/11/2026 às 12:00" in r.json()["mensagem"]  # horário de Brasília
    assert r.json()["detalhes"] == [{"campo": "disponivel_em", "mensagem": "2026-11-26T15:00:00Z"}]


def test_exclusao_exige_a_palavra_de_confirmacao(api, monkeypatch):
    c, estado = api
    estado.flags = {"lgpd_consentimentos": True}
    estado.tabelas = _TODAS | frozenset({"solicitacao"})
    estado.recarregar()
    chamado = []
    monkeypatch.setattr(titular, "pedir_exclusao", lambda **kw: chamado.append(kw))
    r = c.post("/api/v1/perfil/dados/exclusao", json={"confirmacao": "sim",
                                                      "chave_idempotencia": "0b5c8f5e-3d5a-4c1e-9a55-2f1f6f0a7a11"})
    assert r.status_code == 400 and r.json()["detalhes"][0]["campo"] == "confirmacao" and chamado == []
    # Sem as tabelas de solicitação, 503 antes de criar qualquer coisa.
    r = c.post("/api/v1/perfil/dados/exclusao", json={"confirmacao": "excluir",
                                                      "chave_idempotencia": "0b5c8f5e-3d5a-4c1e-9a55-2f1f6f0a7a11"})
    assert r.status_code == 503 and chamado == []


def test_entradas_fora_do_contrato_sao_recusadas(api):
    c, estado = api
    estado.flags = {"perfil_preferencias": True, "lgpd_consentimentos": True}
    estado.tabelas = _TODAS
    estado.recarregar()
    for corpo in ({"fonte": "enorme"}, {"especialidade": "cardio"}, {"tratamento": "x" * 200}, {}):
        r = c.put("/api/v1/perfil/preferencias", json=corpo)
        assert r.status_code == 400 and r.json()["erro"] == "entrada_invalida", corpo
    r = c.post("/api/v1/perfil/pergunta/tratamento", json={"pular": True, "resposta": "Ana"})
    assert r.status_code == 400
    r = c.post("/api/v1/perfil/pergunta/Inválida!", json={"pular": True})
    assert r.status_code == 400
    for corpo in ({"finalidade": "ofertas_parceiros", "canal": "email", "concedido": "sim", "versao": "v0"},
                  {"finalidade": "ofertas_parceiros", "canal": "fax", "concedido": True, "versao": "v0"},
                  {"finalidade": "ofertas_parceiros", "canal": "email", "concedido": True}):
        assert c.put("/api/v1/perfil/consentimentos", json=corpo).status_code == 400, corpo
