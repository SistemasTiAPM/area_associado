"""Solicitações (Onda 2) — unidades puras e API com o domínio substituído. Sem banco, sem rede.

Cobre: tabela de transições (válidas e inválidas, exaustiva), `transitar` com
sessão falsa (404, 409, exigências), schemas por tipo, rótulos, cursor,
carência da declaração AMB, limites de negócio, prontidão, contrato da API
(códigos de erro, 200 na repetição, flag, step-up, ordem das dependências) e a
varredura de chaves proibidas nas respostas.
"""

from __future__ import annotations

import itertools
import time
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.dominio.solicitacoes import maquina, rotulos, schemas, servico

GUID = "6b1f3c1e-4f3a-5d2b-9c7e-a5e0c0de57b0"
SID = "0f8fad5b-d9cb-469f-a165-70867728950e"


# ============================================================ máquina (pura)
# Fonte independente da tabela de `maquina.REGRAS` (REQUISITOS §7.3), escrita à mão.
_PAR = {("apm", "crm"), ("apm", "backoffice"), ("parceiro", "api_parceiro"), ("parceiro", "portal_parceiro")}
ESPERADAS: set[tuple[str, str, str, str]] = set()
for a, o in {("sistema", "job"), ("apm", "backoffice"), ("parceiro", "api_parceiro"), ("parceiro", "portal_parceiro")}:
    ESPERADAS.add(("criada", "enviada", a, o))
for de in ("criada", "enviada"):
    for a, o in _PAR:
        ESPERADAS.add((de, "em_atendimento", a, o))
for a, o in _PAR:
    ESPERADAS.add(("em_atendimento", "pendente_associado", a, o))
ESPERADAS.add(("pendente_associado", "em_atendimento", "associado", "ui"))
# P-66 (ADR-0023): a Central segue sem a resposta pela área — o CRM sai de "Aguardando detalhes".
ESPERADAS.add(("pendente_associado", "em_atendimento", "apm", "crm"))
for de in ("enviada", "em_atendimento"):
    for para in ("concluida_positiva", "concluida_negativa"):
        for a, o in _PAR | {("importacao", "importacao")}:
            ESPERADAS.add((de, para, a, o))
for de in ("criada", "enviada", "pendente_associado"):
    ESPERADAS.add((de, "cancelada", "associado", "ui"))
for de in ("criada", "enviada", "em_atendimento", "pendente_associado"):
    ESPERADAS.add((de, "cancelada", "apm", "backoffice"))
# ADR-0024: o CRM recusou o produto do tipo (422) — o espelho encerra o pedido que nunca saiu.
ESPERADAS.add(("criada", "cancelada", "sistema", "job"))


def test_tabela_de_transicoes_exaustiva():
    obtidas = {(de, para, a, o)
               for de, para, a, o in itertools.product(rotulos.STATUS, rotulos.STATUS, maquina.ATORES, maquina.ORIGENS)
               if maquina.pode_transitar(de, para, a, o)}
    assert obtidas == ESPERADAS, {"sobrando": sorted(obtidas - ESPERADAS), "faltando": sorted(ESPERADAS - obtidas)}


@pytest.mark.parametrize("de,para,ator,origem", [
    ("em_atendimento", "cancelada", "associado", "ui"),          # nunca depois que o parceiro atende (DIV-24)
    ("criada", "concluida_positiva", "apm", "backoffice"),       # não pula etapas
    ("criada", "enviada", "associado", "ui"),                    # associado não promove
    ("pendente_associado", "em_atendimento", "apm", "backoffice"),  # backoffice não pula a resposta
    ("concluida_positiva", "cancelada", "apm", "backoffice"),    # terminal não muda
    ("cancelada", "criada", "associado", "ui"),
    ("enviada", "enviada", "sistema", "job"),
    ("criada", "enviada", "sistema", "ui"),                      # par ator/origem incoerente
])
def test_transicoes_invalidas(de, para, ator, origem):
    assert not maquina.pode_transitar(de, para, ator, origem)


def test_terminais_nunca_transitam_e_exigencias():
    for de in rotulos.TERMINAIS:
        for para, a, o in itertools.product(rotulos.STATUS, maquina.ATORES, maquina.ORIGENS):
            assert not maquina.pode_transitar(de, para, a, o)
    assert maquina.exige_mensagem("pendente_associado", "apm", "crm")
    assert maquina.exige_mensagem("em_atendimento", "associado", "ui")
    assert not maquina.exige_mensagem("em_atendimento", "apm", "crm")
    assert [s for s in rotulos.STATUS if maquina.pode_cancelar_associado(s)] == [
        "criada", "enviada", "pendente_associado"]
    assert [s for s in rotulos.STATUS if maquina.pode_responder_associado(s)] == ["pendente_associado"]


class _Res:
    def __init__(self, linha=None, rowcount=1, lastrowid=1):
        self._linha, self.rowcount, self.lastrowid = linha, rowcount, lastrowid

    def first(self):
        return self._linha


class _SessFalsa:
    """Responde ao SELECT ... FOR UPDATE com `linha`; UPDATE com `rowcount`; registra tudo."""

    def __init__(self, linha, rowcount=1):
        self.linha, self.rowcount, self.sqls = linha, rowcount, []

    def execute(self, sql, params=None):
        texto = str(sql)
        self.sqls.append((texto, params))
        if texto.startswith("SELECT"):
            return _Res(self.linha)
        if texto.startswith("UPDATE"):
            return _Res(rowcount=self.rowcount)
        return _Res(lastrowid=42)


def _linha(status, crm_id=None):
    return SimpleNamespace(id=SID, contact_id=GUID, status=status, tipo_servico="outro", tipo_ativacao=3, crm_id=crm_id)


def test_transitar_nao_encontrada_e_estado_invalido_e_exigencias():
    with pytest.raises(maquina.SolicitacaoNaoEncontrada):
        maquina.transitar(_SessFalsa(None), solicitacao_id=SID, contact_id=GUID, para="cancelada", ator="associado",
                          origem="ui")
    with pytest.raises(maquina.TransicaoInvalida) as e:
        maquina.transitar(_SessFalsa(_linha("em_atendimento")), solicitacao_id=SID, contact_id=GUID,
                          para="cancelada", ator="associado", origem="ui")
    assert e.value.codigo == "estado_invalido"
    sess = _SessFalsa(_linha("criada"))
    with pytest.raises(maquina.TransicaoInvalida, match="justificativa"):
        maquina.transitar(sess, solicitacao_id=SID, para="cancelada", ator="apm", origem="backoffice")
    with pytest.raises(maquina.TransicaoInvalida, match="mensagem"):
        maquina.transitar(sess, solicitacao_id=SID, para="em_atendimento", ator="associado", origem="ui")
    assert sess.sqls == []  # recusado antes de tocar o banco
    with pytest.raises(maquina.TransicaoInvalida):  # UPDATE condicional sem linha ⇒ 409
        maquina.transitar(_SessFalsa(_linha("criada"), rowcount=0), solicitacao_id=SID, contact_id=GUID,
                          para="cancelada", ator="associado", origem="ui")


def test_transitar_update_condicional_limpa_marcador_e_reabre_espelho(monkeypatch):
    from app.dominio import comunicacao

    monkeypatch.setattr(comunicacao, "suprimir_pendentes", lambda *a, **k: 0)
    monkeypatch.setattr(comunicacao, "notificar", lambda *a, **k: True)
    sess = _SessFalsa(_linha("pendente_associado", crm_id=SID))
    r = maquina.transitar(sess, solicitacao_id=SID, para="cancelada", ator="apm", origem="backoffice",
                          justificativa="pedido duplicado", cancel_motivo="duplicado")
    assert (r.de, r.para, r.evento_id, r.origem) == ("pendente_associado", "cancelada", 42, "backoffice")
    select, update, insert = (s for s, _ in sess.sqls)
    assert "FOR UPDATE" in select and "contact_id = :c" not in select
    assert "WHERE id = :id AND status = :de" in update and "sem_retorno_desde = NULL" in update
    assert "crm_sync = 'pendente'" in update and "cancel_motivo" in update
    assert insert.startswith("INSERT INTO solicitacao_evento")
    # Sem espelho ainda (janela de arrependimento): a agenda do CRM não é tocada.
    sess = _SessFalsa(_linha("criada"))
    maquina.transitar(sess, solicitacao_id=SID, contact_id=GUID, para="cancelada", ator="associado", origem="ui")
    assert "crm_sync" not in sess.sqls[1][0]


def test_associado_nao_cancela_nem_responde_pedido_que_ja_esta_na_central(monkeypatch):
    """ADR-0023: sem ferramenta de status no hub, a ação não chegaria ao CRM."""
    for para, extra in (("cancelada", {}), ("em_atendimento", {"mensagem": "segue o documento"})):
        sess = _SessFalsa(_linha("pendente_associado", crm_id=SID))
        with pytest.raises(maquina.TransicaoInvalida) as e:
            maquina.transitar(sess, solicitacao_id=SID, contact_id=GUID, para=para, ator="associado", origem="ui",
                              **extra)
        assert e.value.codigo == "na_central" and "protocolo" in e.value.mensagem
        assert [s for s, _ in sess.sqls if not s.startswith("SELECT")] == []  # nada gravado
    assert maquina.pode_cancelar_associado("enviada") and not maquina.pode_cancelar_associado("enviada", True)
    assert maquina.pode_responder_associado("pendente_associado")
    assert not maquina.pode_responder_associado("pendente_associado", True)


# ============================================================== schemas
def test_outro_normaliza_e_recusa_html_cpf_e_invisiveis():
    d = schemas.validar("outro", {"assunto": "  Dúvida   sobre  benefício ", "mensagem": "Linha 1\r\n\r\n\r\n\r\nLinha  2"})
    assert d == {"assunto": "Dúvida sobre benefício", "mensagem": "Linha 1\n\nLinha 2"}
    for ruim in ("<script>alert(1)</script>", "veja &lt;b&gt;", "<!-- x -->", "meu cpf 123.456.789-09",
                 "12345678909", "texto‮oculto", "a\x00b"):
        with pytest.raises(schemas.EntradaInvalida) as e:
            schemas.validar("outro", {"assunto": "Assunto", "mensagem": ruim})
        assert e.value.detalhes[0]["campo"] == "campos.mensagem"
        assert ruim not in str(e.value.detalhes)  # nunca ecoa o valor
    # Telefone formatado e UUID não são CPF.
    ok = schemas.validar("outro", {"assunto": "Ligar", "mensagem": "(11) 98765-4321 ref 0f8fad5b-d9cb-469f"})
    assert "98765-4321" in ok["mensagem"]


def test_campo_fora_da_allowlist_obrigatorio_e_tipo_errado():
    with pytest.raises(schemas.EntradaInvalida) as e:
        schemas.validar("outro", {"assunto": "x", "mensagem": "y", "cpf": "1", "Campo Estranho!": 1})
    campos = [d["campo"] for d in e.value.detalhes]
    assert campos == ["campos.cpf", "campos"]  # chave fora do padrão não é ecoada
    with pytest.raises(schemas.EntradaInvalida) as e:
        schemas.validar("outro", {"assunto": "   "})
    assert {d["campo"] for d in e.value.detalhes} == {"campos.assunto", "campos.mensagem"}
    with pytest.raises(schemas.EntradaInvalida):
        schemas.validar("outro", {"assunto": 123, "mensagem": "y"})
    with pytest.raises(schemas.EntradaInvalida):
        schemas.validar("inexistente", {})
    with pytest.raises(schemas.EntradaInvalida):
        schemas.validar("outro", ["lista"])
    with pytest.raises(schemas.EntradaInvalida):
        schemas.validar("outro", {"assunto": "x" * 121, "mensagem": "y"})


def test_declaracao_alteracao_e_cancelamento():
    assert schemas.validar("declaracao_associado", {"finalidade": "amb_prova_titulo"}) == {
        "finalidade": "amb_prova_titulo"}
    with pytest.raises(schemas.EntradaInvalida):
        schemas.validar("declaracao_associado", {"finalidade": "imposto"})
    d = schemas.validar("alteracao_cadastro", {"alteracoes": {"sobrenome": "Nogueira  da Silva", "nome": "Telma"}})
    assert d == {"alteracoes": {"nome": "Telma", "sobrenome": "Nogueira da Silva"}}
    for ruins in ({}, {"email": "a@b.c"}, {"cpf": "1"}, {"celular": "11999999999"}, {"nome": "T3lma"},
                  {"data_nascimento": "2020-01-01"}, {"data_nascimento": "1900-01-01"},
                  {"data_nascimento": "1980-02-30"}, {"sexo": "x"}):
        with pytest.raises(schemas.EntradaInvalida):
            schemas.validar("alteracao_cadastro", {"alteracoes": ruins})
    assert schemas.validar("alteracao_cadastro", {"alteracoes": {"data_nascimento": "1980-05-12"}})
    c = schemas.validar("cancelamento_associacao", {"motivo": "preco", "quer_conversa": False})
    assert c == {"motivo": "preco", "quer_conversa": False}
    with pytest.raises(schemas.EntradaInvalida):
        schemas.validar("cancelamento_associacao", {"motivo": "preco", "quer_conversa": "sim"})
    assert schemas.TIPOS_CRIAVEIS_API == {"outro", "declaracao_associado", "alteracao_cadastro"}


def test_campos_publicos_e_sha256_canonico():
    dados = {"assunto": "A", "mensagem": "B", "interno": "nunca"}
    assert schemas.campos_publicos("outro", dados) == {"assunto": "A", "mensagem": "B"}
    assert schemas.campos_publicos(None, dados) == {}
    assert schemas.sha256_conteudo({"a": 1, "b": "ç"}) == schemas.sha256_conteudo({"b": "ç", "a": 1})
    assert len(schemas.sha256_conteudo({})) == 64


def test_tamanho_maximo_de_dados(monkeypatch):
    monkeypatch.setattr(schemas, "DADOS_MAX_BYTES", 50)
    with pytest.raises(schemas.EntradaInvalida, match="entrada_invalida"):
        schemas.validar("outro", {"assunto": "x", "mensagem": "y" * 60})


# ============================================================== rótulos
def test_rotulos_sete_status_tipo3_e_marcador():
    assert [rotulos.rotulo_status(s) for s in rotulos.STATUS] == [
        "Recebida pela APM", "Enviada ao parceiro", "Em atendimento", "O parceiro precisa de algo seu",
        "Concluída", "Não seguiu", "Cancelada"]
    assert rotulos.rotulo_status("enviada", 3) == "Encaminhada à equipe"
    assert rotulos.rotulo_status("em_atendimento", 3) == "Em atendimento"
    assert rotulos.rotulo_evento("sem_retorno", "enviada", 3) == "Aguardando o parceiro, a APM já está cobrando"
    assert set(rotulos.ATOR_PUBLICO.values()) == {"voce", "equipe_apm", "parceiro", "sistema"}
    assert all(t in rotulos.ROTULO_TIPO for t in schemas.SCHEMAS)


# ============================================================ serviço puro
def test_somar_meses_cursor_e_id():
    assert servico.somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert servico.somar_meses(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert servico.somar_meses(date(2026, 12, 15), 1) == date(2027, 1, 15)
    quando = datetime(2026, 10, 30, 12, 0, 0, 123456)
    assert servico.decodificar_cursor(servico.codificar_cursor(quando, SID)) == (quando, SID)
    for ruim in ("xx", "!!!", "W10", servico.codificar_cursor(quando, SID)[:-3], "a" * 300):
        with pytest.raises(servico.CursorInvalido):
            servico.decodificar_cursor(ruim)
    assert servico.validar_id(SID.upper()) == SID
    for ruim in ("1", "../x", SID + "0", None):
        with pytest.raises(maquina.SolicitacaoNaoEncontrada):
            servico.validar_id(ruim)


def _linha_resumo(**k):
    base = dict(id=SID, tipo_servico="outro", beneficio_id=None, tipo_ativacao=3, status="enviada",
                enviada_em=datetime(2026, 10, 30, 2, 0), prazo_retorno_dias=10, sem_retorno_desde=None,
                dados='{"assunto":"A","mensagem":"B"}', avaliacao_nota=None, avaliacao_comentario=None,
                avaliada_em=None, criada_em=datetime(2026, 10, 29, 12), atualizada_em=datetime(2026, 10, 30, 2),
                concluida_em=None, crm_id=None, crm_protocolo=None)
    base.update(k)
    return SimpleNamespace(**base)


def test_resumo_prazo_marcador_e_pode_avaliar():
    agora = datetime(2026, 11, 1)
    r = servico.resumo(_linha_resumo(), contato=None, prazo_avaliacao_dias=30, agora=agora)
    assert r["prazo_em"] == "2026-11-08"  # 02:00 UTC + 10 d = 23:00 do dia 8 em São Paulo
    assert r["rotulo_status"] == "Encaminhada à equipe" and r["pode_cancelar"] and not r["pode_responder"]
    assert servico.resumo(_linha_resumo(enviada_em=None, status="criada"), contato=None, prazo_avaliacao_dias=30,
                          agora=agora)["prazo_em"] is None
    marcada = servico.resumo(_linha_resumo(sem_retorno_desde=agora), contato=None, prazo_avaliacao_dias=30, agora=agora)
    assert marcada["aguardando_parceiro"] is True
    concluida = _linha_resumo(status="concluida_positiva", concluida_em=agora - timedelta(days=29))
    assert servico.resumo(concluida, contato=None, prazo_avaliacao_dias=30, agora=agora)["pode_avaliar"] is True
    assert servico.resumo(concluida, contato=None, prazo_avaliacao_dias=28, agora=agora)["pode_avaliar"] is False
    assert servico.resumo(concluida, contato=None, prazo_avaliacao_dias=30, agora=agora)["prazo_em"] is None
    assert (r["protocolo"], r["na_central"]) == (None, False)
    # Já no CRM: protocolo para a Central e nada de cancelar/responder pela área (ADR-0023).
    na_central = servico.resumo(_linha_resumo(crm_id=SID, crm_protocolo="CAS-285497-M7P9T5"), contato=None,
                                prazo_avaliacao_dias=30, agora=agora)
    assert na_central["protocolo"] == "CAS-285497-M7P9T5" and na_central["na_central"] is True
    assert not na_central["pode_cancelar"] and not na_central["pode_responder"]
    pendente = servico.resumo(_linha_resumo(status="pendente_associado", crm_id=SID), contato=None,
                              prazo_avaliacao_dias=30, agora=agora)
    assert not pendente["pode_responder"] and not pendente["pode_cancelar"]


class _DbFiliacao:
    def __init__(self, filiacao):
        self.filiacao = filiacao

    def execute(self, sql, params=None):
        return SimpleNamespace(scalar=lambda: self.filiacao)


def test_carencia_da_declaracao_amb():
    campos = {"finalidade": "amb_prova_titulo"}
    with pytest.raises(servico.NaoElegivel) as e:
        servico.exigir_elegibilidade(_DbFiliacao(date(2026, 10, 15)), GUID, "declaracao_associado", campos,
                                     date(2026, 11, 14))
    assert e.value.libera_em == date(2026, 11, 15) and "15/11/2026" in e.value.mensagem
    servico.exigir_elegibilidade(_DbFiliacao(date(2026, 10, 15)), GUID, "declaracao_associado", campos,
                                 date(2026, 11, 15))
    servico.exigir_elegibilidade(_DbFiliacao(date(2026, 10, 15)), GUID, "declaracao_associado",
                                 {"finalidade": "geral"}, date(2026, 10, 16))  # só a AMB tem carência
    servico.exigir_elegibilidade(_DbFiliacao(None), GUID, "declaracao_associado", campos, date(2026, 10, 16))


# ============================================================ limites
class _DbContagem:
    def __init__(self, n):
        self.n, self.sqls = n, []

    def execute(self, sql, params=None):
        self.sqls.append((str(sql), params))
        return SimpleNamespace(scalar_one=lambda: self.n)


def test_teto_outro_5_em_24h_e_allowlist_de_identificadores():
    from app.dominio import limites_negocio as ln

    agora = datetime(2026, 10, 30, 12)
    ln.exigir_abaixo_do_teto(_DbContagem(4), contact_id=GUID, tipo_servico="outro", agora=agora)
    with pytest.raises(ln.LimiteNegocioExcedido):
        ln.exigir_abaixo_do_teto(_DbContagem(5), contact_id=GUID, tipo_servico="outro", agora=agora)
    db = _DbContagem(99)
    ln.exigir_abaixo_do_teto(db, contact_id=GUID, tipo_servico="declaracao_associado", agora=agora)
    assert db.sqls == []  # sem teto para o tipo: nem consulta
    db = _DbContagem(0)
    ln.exigir_abaixo_do_teto(db, contact_id=GUID, tipo_servico="outro", agora=agora)
    assert db.sqls[0][1]["desde"] == agora - timedelta(hours=24)
    with pytest.raises(ValueError):
        ln.contar_no_periodo(db, tabela="evento_log", contact_id=GUID, desde=agora)
    with pytest.raises(ValueError):
        ln.contar_no_periodo(db, tabela="solicitacao", contact_id=GUID, desde=agora, filtros={"1=1; --": "x"})


# ============================================================ prontidão
def test_prontidao_cache_e_falha_fechada(monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app import prontidao

    chamadas = []

    def ler():
        chamadas.append(1)
        return frozenset({"faq", "parametro"})

    monkeypatch.setattr(prontidao, "_ler_tabelas", ler)
    prontidao.limpar_cache()
    assert prontidao.recursos() == {"solicitacoes": False, "ajuda": True}
    assert prontidao.disponivel("ajuda") and not prontidao.disponivel("inexistente")
    assert len(chamadas) == 1  # cache

    def fora():
        raise OperationalError("x", {}, Exception("down"))

    monkeypatch.setattr(prontidao, "_ler_tabelas", fora)
    prontidao.limpar_cache()
    assert prontidao.recursos() == {"solicitacoes": False, "ajuda": False}
    monkeypatch.setattr(prontidao, "_ler_tabelas", lambda: frozenset(set().union(*prontidao.RECURSOS.values())))
    assert prontidao.recursos()["solicitacoes"] is False  # falha também fica em cache (curto)
    real = time.monotonic
    monkeypatch.setattr(prontidao.time, "monotonic", lambda: real() + prontidao.TTL_FALHA_S + 1)
    assert prontidao.recursos() == {"solicitacoes": True, "ajuda": True}
    prontidao.limpar_cache()


# ============================================================ API (domínio substituído)
_PROIBIDAS = {"contact_id", "sub", "sub_hash", "cpf", "email", "crm_id", "crm_sync", "crm_tentativas",
              "crm_proxima_em", "justificativa", "usuario_interno", "conteudo_enviado", "chave_idempotencia",
              "responsavel", "dados"}


def varrer_chaves(obj, caminho="$"):
    """Todas as chaves (recursivo) — para o teste de contrato."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, f"{caminho}.{k}"
            yield from varrer_chaves(v, f"{caminho}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from varrer_chaves(v, f"{caminho}[{i}]")


def detalhe_falso(status="criada", **extra):
    base = servico.resumo(_linha_resumo(status=status, enviada_em=None), contato={"canal": "whatsapp",
                          "texto": "Central de Relacionamento · WhatsApp (11) 3188-6200"},
                          prazo_avaliacao_dias=30, agora=datetime(2026, 10, 30))
    base.update(campos={"assunto": "A", "mensagem": "B"},
                linha_do_tempo=[{"quando": "2026-10-30T12:00:00Z", "status": "criada", "rotulo": "Recebida pela APM",
                                 "ator": "voce", "mensagem": None}], avaliacao=None)
    base.update(extra)
    return base


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient

    from app import audit, flags, main, prontidao, uso
    from app.api.v1 import solicitacoes as rota
    from app.dominio import associado as dom
    from app.dominio.solicitacoes import parametros
    from app.limites import LimiteJanela
    from tests.test_api import TOKEN_STUB

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    monkeypatch.setattr(dom, "_executar", lambda p: None)
    gravados: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda linhas: gravados.extend(linhas))
    auditados: list[dict] = []
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: auditados.append(kw))
    estado = {"tabelas": frozenset(set().union(*prontidao.RECURSOS.values())), "flags": {}}
    monkeypatch.setattr(prontidao, "_ler_tabelas", lambda: estado["tabelas"])
    prontidao.limpar_cache()
    monkeypatch.setattr(flags, "_ler_tabela", lambda: estado["flags"])
    flags.limpar_cache()
    monkeypatch.setattr(parametros, "_ler_texto", lambda chave: None)
    parametros.limpar_cache()
    monkeypatch.setattr(rota, "limite_escrita", LimiteJanela(100, 60))
    monkeypatch.setattr(servico, "contar_aguardando", lambda cid: 2)
    c = TestClient(main.app, base_url="https://minha.apm.org.br")
    yield SimpleNamespace(c=c, gravados=gravados, auditados=auditados, estado=estado)
    prontidao.limpar_cache()
    flags.limpar_cache()
    parametros.limpar_cache()


def _entrar(c):
    from tests.test_api import _cabecalhos, entrar

    entrar(c)
    return _cabecalhos(c.get("/api/v1/sessao").json()["csrf"])


def test_sessao_traz_recursos_e_contador_real(api):
    from app import prontidao

    h = _entrar(api.c)
    s = api.c.get("/api/v1/sessao").json()
    assert s["recursos"] == {"solicitacoes": True, "ajuda": True} and s["solicitacoes_aguardando"] == 2
    api.estado["tabelas"] = frozenset({"faq", "parametro"})
    prontidao.limpar_cache()
    s = api.c.get("/api/v1/sessao").json()
    assert s["recursos"] == {"solicitacoes": False, "ajuda": True} and s["solicitacoes_aguardando"] == 0
    assert h  # sessão válida


def test_sem_tabelas_503_recurso_indisponivel(api):
    from app import prontidao

    h = _entrar(api.c)
    api.estado["tabelas"] = frozenset()
    prontidao.limpar_cache()
    for r in (api.c.get("/api/v1/solicitacoes"), api.c.get(f"/api/v1/solicitacoes/{SID}"),
              api.c.post("/api/v1/solicitacoes", json={"tipo_servico": "outro", "campos": {},
                                                       "chave_idempotencia": SID}, headers=h)):
        assert r.status_code == 503 and r.json()["erro"] == "recurso_indisponivel"


def test_criar_201_repeticao_200_e_uso_so_na_criacao(api, monkeypatch):
    chamadas = []

    def criar(**kw):
        chamadas.append(kw)
        return servico.Criacao(detalhe_falso(), len(chamadas) == 1, SID)

    monkeypatch.setattr(servico, "criar", criar)
    h = _entrar(api.c)
    corpo = {"tipo_servico": "outro", "campos": {"assunto": " Oi ", "mensagem": "Tudo bem"},
             "chave_idempotencia": SID.upper()}
    r = api.c.post("/api/v1/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    assert chamadas[0]["campos"] == {"assunto": "Oi", "mensagem": "Tudo bem"}  # normalizado antes do domínio
    assert chamadas[0]["chave_idempotencia"] == SID and len(chamadas[0]["sub_hash"]) == 64
    assert [g["acao"] for g in api.gravados] == ["solicitacao_criar"]
    r = api.c.post("/api/v1/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 200 and [g["acao"] for g in api.gravados] == ["solicitacao_criar"]


@pytest.mark.parametrize("corpo,campo", [
    ({"tipo_servico": "cancelamento_associacao", "campos": {}, "chave_idempotencia": SID}, "tipo_servico"),
    ({"tipo_servico": "exclusao_dados", "campos": {}, "chave_idempotencia": SID}, "tipo_servico"),
    ({"tipo_servico": "outro", "campos": {}, "chave_idempotencia": "nao-e-uuid"}, "chave_idempotencia"),
    ({"tipo_servico": "outro", "campos": {"assunto": "x"}, "chave_idempotencia": SID}, "campos.mensagem"),
    ({"tipo_servico": "outro", "campos": {"assunto": "x", "mensagem": "y", "x": 1}, "chave_idempotencia": SID},
     "campos.x"),
    ({"tipo_servico": "outro", "chave_idempotencia": SID, "contact_id": GUID}, "contact_id"),
])
def test_criar_400_entrada_invalida(api, corpo, campo):
    h = _entrar(api.c)
    r = api.c.post("/api/v1/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 400 and r.json()["erro"] == "entrada_invalida", r.text
    assert campo in [d["campo"] for d in r.json()["detalhes"]]


def test_erros_de_dominio_no_contrato(api, monkeypatch):
    from app.dominio.limites_negocio import LimiteNegocioExcedido, PedidoAbertoExistente

    h = _entrar(api.c)
    corpo = {"tipo_servico": "declaracao_associado", "campos": {"finalidade": "amb_prova_titulo"},
             "chave_idempotencia": SID}
    casos = [
        (servico.NaoElegivel(date(2026, 12, 1), "A declaração fica disponível a partir de 01/12/2026."), 409,
         "nao_elegivel"),
        (PedidoAbertoExistente("Já existe."), 409, "estado_invalido"),
        (LimiteNegocioExcedido("Limite."), 429, "limite_negocio"),
    ]
    for exc, status, codigo in casos:
        def falhar(exc=exc, **kw):
            raise exc

        monkeypatch.setattr(servico, "criar", falhar)
        r = api.c.post("/api/v1/solicitacoes", json=corpo, headers=h)
        assert (r.status_code, r.json()["erro"]) == (status, codigo)
        if codigo == "nao_elegivel":
            assert r.json()["detalhes"] == [{"campo": "libera_em", "mensagem": "2026-12-01"}]
    assert api.gravados == []  # nada de evento de uso em recusa


def test_cancelar_responder_avaliar_mapeiam_409_e_404(api, monkeypatch):
    h = _entrar(api.c)

    def levantar(exc):
        def f(*a, **k):
            raise exc
        return f

    monkeypatch.setattr(servico, "cancelar", levantar(maquina.TransicaoInvalida()))
    r = api.c.post(f"/api/v1/solicitacoes/{SID}/cancelar", json={}, headers=h)
    assert r.status_code == 409 and r.json()["erro"] == "estado_invalido"
    monkeypatch.setattr(servico, "responder", levantar(maquina.SolicitacaoNaoEncontrada()))
    r = api.c.post(f"/api/v1/solicitacoes/{SID}/responder", json={"texto": "Segue."}, headers=h)
    assert r.status_code == 404 and r.json()["erro"] == "nao_encontrado"
    for codigo in ("ja_avaliada", "prazo_expirado", "estado_invalido"):
        monkeypatch.setattr(servico, "avaliar", levantar(maquina.TransicaoInvalida(codigo)))
        r = api.c.post(f"/api/v1/solicitacoes/{SID}/avaliar", json={"nota": 9}, headers=h)
        assert (r.status_code, r.json()["erro"]) == (409, codigo)
    for ruim in ({"nota": 11}, {"nota": -1}, {"nota": "9"}, {"nota": 9.5}, {"nota": 9, "comentario": "<b>x</b>"},
                 {"nota": True}):
        r = api.c.post(f"/api/v1/solicitacoes/{SID}/avaliar", json=ruim, headers=h)
        assert r.status_code == 400, ruim
    r = api.c.post(f"/api/v1/solicitacoes/{SID}/responder", json={"texto": ""}, headers=h)
    assert r.status_code == 400
    r = api.c.post(f"/api/v1/solicitacoes/{SID}/responder", json={"texto": "x" * 2001}, headers=h)
    assert r.status_code == 400
    r = api.c.post(f"/api/v1/solicitacoes/{SID}/cancelar", json={"motivo": "x" * 201}, headers=h)
    assert r.status_code == 400


def test_escrita_exige_csrf_e_sessao(api):
    r = api.c.post("/api/v1/solicitacoes", json={})
    assert r.status_code == 401
    _entrar(api.c)
    r = api.c.post("/api/v1/solicitacoes", json={"tipo_servico": "outro", "campos": {}, "chave_idempotencia": SID},
                   headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 403 and r.json()["erro"] == "csrf_invalido"
    assert api.c.get("/api/v1/solicitacoes", params={"limite": 21}).status_code == 400
    assert api.c.get("/api/v1/solicitacoes", params={"situacao": "todas"}).status_code == 400


def test_lista_e_detalhe_passam_pelo_contrato_sem_chaves_proibidas(api, monkeypatch):
    _entrar(api.c)
    resumo = {k: v for k, v in detalhe_falso().items() if k not in ("campos", "linha_do_tempo", "avaliacao")}
    pedidos = []
    monkeypatch.setattr(servico, "listar", lambda cid, **k: pedidos.append(k) or ([resumo], None))
    r = api.c.get("/api/v1/solicitacoes", params={"situacao": "andamento", "limite": 5})
    assert r.status_code == 200 and r.json()["proximo_cursor"] is None
    assert pedidos == [{"situacao": "andamento", "cursor": None, "limite": 5}]
    monkeypatch.setattr(servico, "detalhe", lambda cid, sid: detalhe_falso())
    d = api.c.get(f"/api/v1/solicitacoes/{SID}")
    assert d.status_code == 200
    for corpo in (r.json(), d.json(), api.c.get("/api/v1/sessao").json()):
        chaves = {k for k, _ in varrer_chaves(corpo)}
        assert not (chaves & _PROIBIDAS), chaves & _PROIBIDAS


def test_resposta_com_chave_interna_vaza_nunca(api, monkeypatch):
    """Se o domínio um dia devolver `crm_sync`, o modelo fechado derruba a resposta em vez de vazar."""
    monkeypatch.setattr(servico, "detalhe", lambda cid, sid: detalhe_falso(crm_sync="erro"))
    _entrar(api.c)
    with pytest.raises(Exception):
        api.c.get(f"/api/v1/solicitacoes/{SID}")
