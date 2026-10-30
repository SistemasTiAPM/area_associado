"""Unidades do serviço de jobs (ADR-0019; frente C da Onda 2) — sem rede e sem banco.

Agendador (intervalo, jitter, diário local, ordem), trava e rastro do executor
(pulado, ocupado, ok, erro, abortado, 3 falhas seguidas), dry-run de cada job
com efeito externo, recuo e classificação de erro, prontidão, heartbeat,
contrato novo do hub (real e simulado), textos dos e-mails e validadores.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from datetime import time as dtime
from types import SimpleNamespace

import httpx
import pytest

from app.integracoes.email import EmailError
from app.integracoes.hub import HubError

UTC3 = timezone(timedelta(hours=-3))
SID = "0b9c3c6e-5d0f-4a5e-8b1a-2f3c4d5e6f70"
CID = "11111111-2222-3333-4444-555555555555"


# =================================================================== agenda
def _agenda(quandos, agora=1_000_000.0, sorteio=0.5):
    from app.jobs.agenda import Agenda

    relogio = {"t": agora}
    ag = Agenda(quandos, relogio=lambda: relogio["t"], sorteio=lambda: sorteio, fuso=UTC3)
    return ag, relogio


def test_quando_exige_um_dos_dois_e_descreve():
    from app.jobs.agenda import Quando

    with pytest.raises(ValueError):
        Quando()
    with pytest.raises(ValueError):
        Quando(intervalo_s=60, horario=dtime(3))
    with pytest.raises(ValueError):
        Quando(intervalo_s=0)
    assert Quando(intervalo_s=300).descricao == "a cada 5 min"
    assert Quando(horario=dtime(3)).descricao.startswith("diário 03:00")
    assert Quando(intervalo_s=60).atraso_maximo_s == 15 * 60  # piso de 15 min
    assert Quando(intervalo_s=900).atraso_maximo_s == 2700
    assert Quando(horario=dtime(3)).atraso_maximo_s == 26 * 3600


def test_agenda_periodica_jitter_inicial_e_reagendamento_limitados():
    from app.jobs.agenda import Quando

    for sorteio in (0.0, 0.5, 0.999):
        ag, _ = _agenda([("a", Quando(intervalo_s=60)), ("b", Quando(intervalo_s=3600))], sorteio=sorteio)
        assert 1_000_000.0 <= ag.proxima["a"] <= 1_000_000.0 + 20
        assert 1_000_000.0 <= ag.proxima["b"] <= 1_000_000.0 + 20
        # Do FIM da execução: intervalo ± 10%, com teto de 30 s de jitter.
        assert 2_000_054 <= ag.reagendar("a", 2_000_000.0) <= 2_000_066
        assert 2_003_570 <= ag.reagendar("b", 2_000_000.0) <= 2_003_630


def test_agenda_vencidos_em_ordem_e_espera_com_teto():
    from app.jobs.agenda import Quando

    ag, relogio = _agenda([("lento", Quando(intervalo_s=600)), ("rapido", Quando(intervalo_s=60))])
    ag.proxima.update({"lento": 1_000_010.0, "rapido": 1_000_005.0})
    assert ag.vencidos(1_000_000.0) == []
    assert ag.espera(1_000_000.0) == 5.0
    assert ag.vencidos(1_000_020.0) == ["rapido", "lento"]
    ag.proxima.update({"lento": 1_000_500.0, "rapido": 1_000_400.0})
    assert ag.espera(1_000_000.0) == 15.0  # acorda para o heartbeat
    assert ag.espera(1_000_900.0) == 0.0


def test_agenda_diaria_na_hora_local():
    from app.jobs.agenda import Quando

    duas_da_manha = datetime(2026, 10, 30, 2, 0, tzinfo=UTC3).timestamp()
    ag, _ = _agenda([("noite", Quando(horario=dtime(3)))], agora=duas_da_manha, sorteio=0.0)
    assert datetime.fromtimestamp(ag.proxima["noite"], UTC3) == datetime(2026, 10, 30, 3, 0, tzinfo=UTC3)
    # Depois da hora (boot às 10h ou fim da execução das 3h): amanhã às 3h, + até 2 min de jitter.
    dez = datetime(2026, 10, 30, 10, 0, tzinfo=UTC3).timestamp()
    proxima = datetime.fromtimestamp(ag.reagendar("noite", dez), UTC3)
    assert proxima == datetime(2026, 10, 31, 3, 0, tzinfo=UTC3)
    ag2, _ = _agenda([("noite", Quando(horario=dtime(3)))], agora=dez, sorteio=0.999)
    p2 = datetime.fromtimestamp(ag2.proxima["noite"], UTC3)
    assert datetime(2026, 10, 31, 3, 0, tzinfo=UTC3) <= p2 <= datetime(2026, 10, 31, 3, 2, tzinfo=UTC3)


def test_laco_roda_um_job_por_vez_e_para_no_sinal():
    from app.jobs import __main__ as principal
    from app.jobs.agenda import Quando

    evento = threading.Event()
    rodados = []

    class Exec:
        def executar(self, job):
            rodados.append(job.nome)
            if len(rodados) == 2:
                evento.set()  # SIGTERM durante o 2º job: o laço não começa outro
            return "ok"

    class Bat:
        batidas = 0

        def bater(self, forcar=False):
            Bat.batidas += 1

    ag, _ = _agenda([("a", Quando(intervalo_s=60)), ("b", Quando(intervalo_s=60)), ("c", Quando(intervalo_s=60))])
    ag.proxima.update({"a": 0.0, "b": 1.0, "c": 2.0})
    registro = {n: SimpleNamespace(nome=n) for n in "abc"}
    principal.laco(Exec(), ag, registro, evento, Bat())
    assert rodados == ["a", "b"]  # em ordem de vencimento, um por vez; "c" não começa depois do sinal
    assert ag.proxima["a"] > 1_000_000.0 and ag.proxima["b"] > 1_000_000.0 and ag.proxima["c"] == 2.0
    assert Bat.batidas >= 1


# ================================================================= política
def test_recuo_1_2_4_ate_60_e_falhou_na_decima():
    from app.jobs.politica import MAX_TENTATIVAS, proxima_tentativa

    agora = datetime(2026, 10, 30, 12, 0)
    esperado = [1, 2, 4, 8, 16, 32, 60, 60, 60]
    assert [int((proxima_tentativa(t, agora) - agora).total_seconds() // 60) for t in range(1, 10)] == esperado
    assert MAX_TENTATIVAS == 10
    assert proxima_tentativa(10, agora) is None
    assert proxima_tentativa(15, agora) is None
    with pytest.raises(ValueError):
        proxima_tentativa(0, agora)


@pytest.mark.parametrize("codigo,classe", [
    ("entrada_invalida", "permanente"), ("nao_encontrado", "permanente"),
    ("limite_taxa", "sistemico"), ("edicao_desligada", "sistemico"),
    ("fonte_indisponivel", "transitorio"), ("qualquer_outro", "transitorio"),
])
def test_classificacao_do_hub(codigo, classe):
    from app.jobs.politica import classificar_hub

    falha = classificar_hub(HubError(codigo))
    assert falha.classe == classe and falha.codigo == codigo


def test_classificacao_do_smtp():
    from app.jobs.politica import classificar_email

    assert classificar_email(EmailError("x", codigo="destinatario_recusado", permanente=True)).classe == "permanente"
    assert classificar_email(EmailError("x", codigo="smtp_autenticacao", sistemica=True)).classe == "sistemico"
    assert classificar_email(EmailError("x")).classe == "transitorio"
    assert classificar_email(EmailError("x")).codigo == "smtp_indisponivel"


def test_resumo_de_erro_nunca_traz_a_mensagem_de_terceiro():
    from sqlalchemy.exc import OperationalError

    from app.jobs.politica import codigo_seguro, resumo_erro

    exc = RuntimeError("senha=hunter2 cpf 123.456.789-09 Bearer abcdefghijklmnop")
    resumo = resumo_erro(exc)
    assert resumo == "RuntimeError"
    db = OperationalError("SELECT * FROM x WHERE email='a@b.c'", {"p": "segredo"}, Exception(2003, "conn refused"))
    assert resumo_erro(db, contexto="abrir") == "abrir: OperationalError: mysql_2003"
    assert resumo_erro(HubError("limite_taxa", 429)) == "HubError: limite_taxa"
    assert resumo_erro(contexto="token=abc") == "erro (resumo omitido)"
    assert codigo_seguro("Fonte Indisponível!") == "fonte_indispon_vel"
    assert codigo_seguro("9x") == "erro"


# ================================================================ heartbeat
def test_heartbeat_grava_atomico_com_intervalo(tmp_path):
    from app.jobs.base import Batimento

    t = {"v": 100.0}
    caminho = tmp_path / "jobs.heartbeat"
    b = Batimento(str(caminho), intervalo_min=5.0, relogio=lambda: t["v"])
    b.bater()
    primeiro = caminho.read_text()
    assert primeiro.endswith("Z\n") and not (tmp_path / "jobs.heartbeat.tmp").exists()
    caminho.write_text("antigo")
    t["v"] = 103.0
    b.bater()
    assert caminho.read_text() == "antigo"  # dentro do intervalo
    b.bater(forcar=True)
    assert caminho.read_text() != "antigo"
    ruim = Batimento(str(tmp_path / "nao" / "existe"), relogio=lambda: 0.0)
    ruim.bater()
    ruim.bater(forcar=True)  # não lança


# ================================================================= executor
class _Conexao:
    def __init__(self, obtida=1):
        self.obtida = obtida
        self.sql: list[str] = []
        self.fechada = False

    def execute(self, sql, params=None):
        self.sql.append(str(sql))
        return SimpleNamespace(scalar=lambda: self.obtida if "GET_LOCK" in str(sql) else 1)

    def commit(self):
        pass

    def close(self):
        self.fechada = True


@pytest.fixture
def executor(monkeypatch):
    from app import audit, database
    from app.jobs import base

    estado = {"abertas": [], "fechadas": [], "auditoria": [], "conexao": _Conexao(), "posicao": "p-7"}
    monkeypatch.setattr(base, "rastro_presente", lambda: True)
    monkeypatch.setattr(database.engine, "connect", lambda: estado["conexao"])

    def abrir(job, **kw):
        estado["abertas"].append((job, kw))
        return 42, estado["posicao"]

    def fechar(execucao_id, *, status, ctx, resumo, agora):
        estado["fechadas"].append({"id": execucao_id, "status": status, "resumo": resumo, "lidos": ctx.lidos,
                                   "gravados": ctx.gravados, "erros": ctx.erros, "posicao": ctx.posicao})

    monkeypatch.setattr(base, "abrir_execucao", abrir)
    monkeypatch.setattr(base, "fechar_execucao", fechar)
    monkeypatch.setattr(audit, "registrar_sistema", lambda **kw: estado["auditoria"].append(kw))
    estado["executor"] = base.Executor()
    return estado


def _job(funcao, pronto=lambda: None, nome="job_teste"):
    from app.jobs.agenda import Quando
    from app.jobs.base import Job

    return Job(nome, Quando(intervalo_s=60), funcao, pronto=pronto)


def test_job_nome_validado():
    with pytest.raises(ValueError):
        _job(lambda ctx: None, nome="Job-Ruim")


def test_executor_ok_trava_rastro_e_contagens(executor):
    def trabalho(ctx):
        assert ctx.posicao_anterior == "p-7" and ctx.aplicar is False
        ctx.lidos, ctx.gravados = 3, 2

    assert executor["executor"].executar(_job(trabalho)) == "ok"
    conexao = executor["conexao"]
    assert any("GET_LOCK" in s for s in conexao.sql) and any("RELEASE_LOCK" in s for s in conexao.sql)
    assert conexao.fechada
    assert executor["abertas"][0][0] == "job_teste" and executor["abertas"][0][1]["aplicar"] is False
    assert executor["fechadas"] == [{"id": 42, "status": "ok", "resumo": None, "lidos": 3, "gravados": 2,
                                     "erros": 0, "posicao": "p-7"}]


def test_executor_sem_rastro_ou_sem_prontidao_nao_roda(executor, monkeypatch):
    from app.jobs import base

    rodou = []
    assert executor["executor"].executar(_job(rodou.append, pronto=lambda: "sql/014 ausente")) == "pulado"
    monkeypatch.setattr(base, "rastro_presente", lambda: False)
    assert executor["executor"].executar(_job(rodou.append)) == "pulado"
    assert rodou == [] and executor["abertas"] == []


def test_executor_trava_ocupada_nao_roda(executor):
    executor["conexao"].obtida = 0
    rodou = []
    assert executor["executor"].executar(_job(rodou.append)) == "ocupado"
    assert rodou == [] and executor["abertas"] == [] and executor["conexao"].fechada
    assert not any("RELEASE_LOCK" in s for s in executor["conexao"].sql)


def test_executor_falha_isolada_tres_seguidas_alertam_e_recuperacao(executor):
    def quebra(ctx):
        raise RuntimeError("senha=nao-pode-aparecer")

    ex = executor["executor"]
    for _ in range(2):
        assert ex.executar(_job(quebra)) == "erro"
    assert executor["auditoria"] == []
    assert ex.executar(_job(quebra)) == "erro"
    assert [a["tipo"] for a in executor["auditoria"]] == ["job_falhas_seguidas"]
    assert executor["auditoria"][0]["severidade"] == "erro" and executor["auditoria"][0]["detalhes"]["falhas"] == 3
    assert all("senha" not in (f["resumo"] or "") for f in executor["fechadas"])
    assert executor["fechadas"][-1]["resumo"] == "RuntimeError"
    assert ex.executar(_job(lambda ctx: None)) == "ok"
    assert executor["auditoria"][-1]["tipo"] == "job_recuperado" and ex.falhas == {}


def test_executor_erro_sistemico_e_abortado(executor):
    def disjuntor(ctx):
        ctx.erro_sistemico = "disjuntor: limite_taxa"

    assert executor["executor"].executar(_job(disjuntor)) == "erro"
    assert executor["fechadas"][-1]["resumo"] == "disjuntor: limite_taxa"

    def para_no_meio(ctx):
        ctx.evento_parar.set()
        assert ctx.parar()

    assert executor["executor"].executar(_job(para_no_meio)) == "abortado"
    assert executor["fechadas"][-1]["status"] == "abortado"


def test_fechar_execucao_so_grava_posicao_em_ok_aplicar(monkeypatch):
    from contextlib import contextmanager

    from app import database
    from app.jobs import base

    gravados = []

    class Sess:
        def execute(self, sql, params):
            gravados.append(params)

    @contextmanager
    def escopo():
        yield Sess()

    monkeypatch.setattr(database, "session_scope", escopo)
    agora = datetime(2026, 10, 30, 12, 0)
    for status, aplicar, posicao, esperado in (("ok", True, "123", "123"), ("ok", False, "123", None),
                                               ("erro", True, "123", None), ("ok", True, "inválida!", None)):
        ctx = base.Contexto(job="x_job", aplicar=aplicar, agora=agora, posicao=posicao)
        base.fechar_execucao(1, status=status, ctx=ctx, resumo="r" * 600, agora=agora)
        assert gravados[-1]["posicao"] == esperado and len(gravados[-1]["resumo"]) == 500


def test_identidade_do_processo_casa_com_os_checks_da_011():
    import re

    from app.jobs.base import identidade_processo

    host, versao = identidade_processo()
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,64}", host)
    assert re.fullmatch(r"src-[0-9a-f]{12}", versao)


# ================================================================ prontidão
def test_prontidao_dos_jobs(monkeypatch):
    from app import prontidao
    from app.dominio import carteirinha as dom_carteirinha
    from app.jobs import carteirinha, registro

    monkeypatch.setattr(prontidao, "tabelas_presentes", lambda: frozenset())
    jobs = registro.por_nome()
    for nome in ("espelhar_solicitacoes", "sincronizar_solicitacoes", "marcar_sem_retorno", "enviar_comunicacao"):
        assert jobs[nome].pronto() and "ausente" in jobs[nome].pronto()
    monkeypatch.setattr(prontidao, "tabelas_presentes", lambda: prontidao.RECURSOS["solicitacoes"])
    assert jobs["espelhar_solicitacoes"].pronto() is None
    monkeypatch.setattr(dom_carteirinha, "colunas_revogacao_presentes", lambda: False)
    assert "014" in carteirinha.pronto()
    monkeypatch.setattr(dom_carteirinha, "colunas_revogacao_presentes", lambda: True)
    assert carteirinha.pronto() is None


def test_registro_tabela_de_jobs():
    from app.jobs import registro

    jobs = registro.jobs()
    nomes = [j.nome for j in jobs]
    assert nomes == ["espelhar_solicitacoes", "sincronizar_solicitacoes", "marcar_sem_retorno",
                     "enviar_comunicacao", "situacao_carteirinhas"]
    assert {j.nome for j in jobs if j.efeito_externo} == {"espelhar_solicitacoes", "sincronizar_solicitacoes",
                                                         "enviar_comunicacao"}
    q = registro.por_nome()
    assert q["espelhar_solicitacoes"].quando.intervalo_s == 60
    assert q["sincronizar_solicitacoes"].quando.intervalo_s == 300
    assert q["marcar_sem_retorno"].quando.intervalo_s == 900
    assert q["situacao_carteirinhas"].quando.horario == dtime(3)


# =================================================================== dry-run
def _ctx(aplicar=False, **kw):
    from app.jobs.base import Contexto

    return Contexto(job="teste_job", aplicar=aplicar, agora=datetime(2026, 10, 30, 12, 0), **kw)


class _HubProibido:
    def __getattr__(self, nome):
        raise AssertionError(f"hub chamado em dry-run: {nome}")


def _linha_solicitacao(**kw):
    base = dict(id=SID, contact_id=CID, tipo_servico="outro", beneficio_id=None, parceiro_id=None, tipo_ativacao=3,
                canal_envio="crm", status="criada", crm_id=None, crm_tentativas=0, prazo_retorno_dias=10,
                dados='{"assunto":"Dúvida","mensagem":"Oi"}', cancel_motivo=None,
                criada_em=datetime(2026, 10, 30, 11, 0), atualizada_em=datetime(2026, 10, 30, 11, 0))
    base.update(kw)
    return SimpleNamespace(**base)


def test_espelho_em_dry_run_nao_chama_o_hub_nem_muda_estado(monkeypatch):
    from app.jobs import solicitacoes

    monkeypatch.setattr(solicitacoes, "pendentes_do_espelho", lambda *a, **k: [_linha_solicitacao()])
    for nome in ("_confirmar", "_registrar_falha", "_nada_a_espelhar"):
        monkeypatch.setattr(solicitacoes, nome, lambda *a, **k: pytest.fail("mudou estado em dry-run"))
    ctx = _ctx(aplicar=False)
    solicitacoes.espelhar_solicitacoes(ctx, hub=_HubProibido())
    assert ctx.lidos == 1 and ctx.gravados == 0 and ctx.erro_sistemico is None


def test_espelho_com_escrita_desligada_espera_sem_gastar_tentativa(monkeypatch):
    from app.jobs import solicitacoes

    monkeypatch.setattr(solicitacoes, "pendentes_do_espelho", lambda *a, **k: [_linha_solicitacao()])
    monkeypatch.setattr(solicitacoes, "_registrar_falha", lambda *a, **k: pytest.fail("gastou tentativa"))
    ctx = _ctx(aplicar=True)
    solicitacoes.espelhar_solicitacoes(ctx, hub=_HubProibido())
    assert "escrita no hub desligada" in ctx.erro_sistemico


class _HubFalho:
    def __init__(self, erro):
        self.erro = erro
        self.chamadas = 0

    def solicitacao_espelhar(self, dados):
        self.chamadas += 1
        raise self.erro


def _espelho_aplicar(monkeypatch, linhas, hub):
    from app.jobs import solicitacoes

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    falhas = []
    monkeypatch.setattr(solicitacoes, "pendentes_do_espelho", lambda *a, **k: linhas)
    monkeypatch.setattr(solicitacoes, "_registrar_falha", lambda r, classe, codigo, agora: falhas.append(
        (r.id, classe, codigo)))
    ctx = _ctx(aplicar=True)
    solicitacoes.espelhar_solicitacoes(ctx, hub=hub)
    return ctx, falhas


def test_espelho_disjuntor_apos_tres_transitorias(monkeypatch):
    linhas = [_linha_solicitacao(id=f"0b9c3c6e-5d0f-4a5e-8b1a-2f3c4d5e6f7{i}") for i in range(6)]
    hub = _HubFalho(HubError("fonte_indisponivel"))
    ctx, falhas = _espelho_aplicar(monkeypatch, linhas, hub)
    assert hub.chamadas == 3 and len(falhas) == 3 and all(f[1] == "transitorio" for f in falhas)
    assert ctx.erro_sistemico.startswith("disjuntor: 3 falhas seguidas") and ctx.erros == 3


def test_espelho_limite_de_taxa_para_sem_gastar_tentativa(monkeypatch):
    hub = _HubFalho(HubError("limite_taxa", 429))
    ctx, falhas = _espelho_aplicar(monkeypatch, [_linha_solicitacao(), _linha_solicitacao()], hub)
    assert hub.chamadas == 1 and falhas == [] and ctx.erro_sistemico == "disjuntor: limite_taxa"


def test_espelho_erro_permanente_nao_conta_para_o_disjuntor(monkeypatch):
    linhas = [_linha_solicitacao(id=f"0b9c3c6e-5d0f-4a5e-8b1a-2f3c4d5e6f7{i}") for i in range(4)]
    hub = _HubFalho(HubError("entrada_invalida", 400))
    ctx, falhas = _espelho_aplicar(monkeypatch, linhas, hub)
    assert hub.chamadas == 4 and [f[1] for f in falhas] == ["permanente"] * 4 and ctx.erro_sistemico is None


def test_payload_do_espelho_sem_dado_de_contato():
    from app.jobs.solicitacoes import payload_espelho

    carga = payload_espelho(_linha_solicitacao())
    assert carga == {"contact_id": CID, "solicitacao_id": SID, "tipo": "outro", "titulo": "Minha APM: Outro assunto",
                     "status": "criada", "criada_em": "2026-10-30T11:00:00Z", "prazo_retorno_dias": 10,
                     "campos": {"assunto": "Dúvida", "mensagem": "Oi"}}
    assert not {"cpf", "email", "celular", "telefone"} & set(json.dumps(carga).lower().split('"'))


def test_sync_em_dry_run_nao_consulta_o_hub():
    from app.jobs import solicitacoes

    ctx = _ctx(aplicar=False, posicao_anterior="12")
    solicitacoes.sincronizar_solicitacoes(ctx, hub=_HubProibido())
    assert ctx.lidos == 0 and ctx.erro_sistemico is None


def test_sync_linha_fora_do_contrato_para_sem_avancar(monkeypatch):
    from app.jobs import solicitacoes

    class Hub:
        def solicitacao_alteracoes_consultar(self, cursor, limite):
            return [{"solicitacao_id": "x", "situacao": "concluida", "cursor": "1"}]

    monkeypatch.setattr(solicitacoes, "aplicar_alteracao", lambda *a: pytest.fail("aplicou linha inválida"))
    ctx = _ctx(aplicar=True, posicao_anterior="7", posicao="7")
    solicitacoes.sincronizar_solicitacoes(ctx, hub=Hub())
    assert ctx.posicao == "7" and ctx.erro_sistemico and ctx.erros == 1


def test_sync_hub_fora_e_erro_sistemico():
    from app.jobs import solicitacoes

    class Hub:
        def solicitacao_alteracoes_consultar(self, cursor, limite):
            raise HubError("fonte_indisponivel")

    ctx = _ctx(aplicar=True)
    solicitacoes.sincronizar_solicitacoes(ctx, hub=Hub())
    assert ctx.erro_sistemico == "hub: fonte_indisponivel"


def test_mapa_e_caminho_do_crm():
    from app.jobs.solicitacoes import MAPA_CRM, _caminho, _mensagem_crm

    from app.integracoes.hub import SITUACOES_TASK

    assert set(MAPA_CRM) == SITUACOES_TASK
    assert _caminho("enviada", "em_atendimento") == ["em_atendimento"]
    assert _caminho("enviada", "pendente_associado") == ["em_atendimento", "pendente_associado"]
    assert _caminho("criada", "concluida_positiva") == ["em_atendimento", "concluida_positiva"]
    assert _caminho("pendente_associado", "em_atendimento") == []  # só o associado responde
    assert _caminho("cancelada", "concluida_negativa") == []
    assert _mensagem_crm("  Envie\n o comprovante  ") == "Envie o comprovante"
    assert _mensagem_crm("CPF 123.456.789-09") is None
    assert _mensagem_crm("") is None


def _linha_com(**kw):
    return SimpleNamespace(**{"id": 7, "gatilho": "A04", "contact_id": CID, "referencia_tipo": "solicitacao",
                              "referencia_id": SID, "canal": "email", "destinatario": "associado", "tentativas": 0,
                              "status": "pendente", "atualizado_em": None, **kw})


def test_comunicacao_dry_run_suprime_localmente_e_nao_envia(monkeypatch):
    from app.integracoes import email as email_mod
    from app.jobs import comunicacao

    linhas = [_linha_com(id=1, canal="rd"), _linha_com(id=2, canal="interno", destinatario="central"),
              _linha_com(id=3), _linha_com(id=4, canal="app")]
    suprimidos = []
    monkeypatch.setattr(comunicacao, "fila", lambda *a, **k: linhas)
    monkeypatch.setattr(comunicacao, "_suprimir", lambda r, motivo, agora: suprimidos.append((r.id, motivo)) or True)
    monkeypatch.setattr(comunicacao, "_reabrir_presos", lambda agora: pytest.fail("mexeu em 'enviando' no dry-run"))
    monkeypatch.setattr(comunicacao, "_fato", lambda db, r: SimpleNamespace(status="criada"))
    monkeypatch.setattr(comunicacao, "montar", lambda *a, **k: ("a@b.org", "assunto", "corpo"))
    for nome in ("_reivindicar", "_marcar_enviado", "_registrar_falha"):
        monkeypatch.setattr(comunicacao, nome, lambda *a, **k: pytest.fail(f"{nome} em dry-run"))
    monkeypatch.setattr(email_mod, "enviar", lambda *a: pytest.fail("enviou em dry-run"))

    from contextlib import contextmanager

    @contextmanager
    def escopo():
        yield None

    monkeypatch.setattr(comunicacao, "_sessao", escopo)
    ctx = _ctx(aplicar=False)
    comunicacao.enviar_comunicacao(ctx)
    # RD: sem credencial até a Onda 3; interno sem CENTRAL_EMAIL: sem credencial.
    assert suprimidos == [(1, "sem_credencial"), (2, "sem_credencial")]
    assert ctx.lidos == 4 and ctx.gravados == 2


def test_comunicacao_smtp_simulado_em_staging_nao_marca_enviado(monkeypatch):
    from contextlib import contextmanager

    from app.config import get_settings
    from app.integracoes import email as email_mod
    from app.jobs import comunicacao

    assert comunicacao.envio_efetivo() is True  # APP_ENV=test: o stub vale
    monkeypatch.setattr(get_settings(), "app_env", "staging")
    assert comunicacao.envio_efetivo() is False

    @contextmanager
    def escopo():
        yield None

    monkeypatch.setattr(comunicacao, "_sessao", escopo)
    monkeypatch.setattr(comunicacao, "_reabrir_presos", lambda agora: 0)
    monkeypatch.setattr(comunicacao, "fila", lambda *a, **k: [_linha_com(id=9)])
    monkeypatch.setattr(comunicacao, "_fato", lambda db, r: SimpleNamespace(status="criada", sem_retorno_desde=None))
    monkeypatch.setattr(comunicacao, "montar", lambda *a, **k: ("a@b.org", "assunto", "corpo"))
    for nome in ("_reivindicar", "_marcar_enviado", "_registrar_falha"):
        monkeypatch.setattr(comunicacao, nome, lambda *a, **k: pytest.fail("marcou com SMTP simulado em staging"))
    monkeypatch.setattr(email_mod, "enviar", lambda *a: pytest.fail("enviou"))
    ctx = _ctx(aplicar=True)
    comunicacao.enviar_comunicacao(ctx)
    assert ctx.lidos == 1 and ctx.gravados == 0


def test_comunicacao_fato_mudou():
    from app.jobs.comunicacao import fato_mudou

    assert fato_mudou(_linha_com(gatilho="A04"), SimpleNamespace(status="cancelada", sem_retorno_desde=None))
    assert fato_mudou(_linha_com(gatilho="A16"), SimpleNamespace(status="cancelada", sem_retorno_desde=None))
    assert fato_mudou(_linha_com(gatilho="A05"), SimpleNamespace(status="em_atendimento", sem_retorno_desde=None))
    assert not fato_mudou(_linha_com(gatilho="A05"),
                          SimpleNamespace(status="enviada", sem_retorno_desde=datetime(2026, 10, 1)))
    assert not fato_mudou(_linha_com(gatilho="A06"), SimpleNamespace(status="concluida_positiva",
                                                                       sem_retorno_desde=None))


def test_comunicacao_smtp_sistemico_devolve_e_para(monkeypatch):
    from contextlib import contextmanager

    from app.integracoes import email as email_mod
    from app.jobs import comunicacao

    linhas = [_linha_com(id=1), _linha_com(id=2)]
    devolvidos, falhas = [], []

    @contextmanager
    def escopo():
        yield None

    monkeypatch.setattr(comunicacao, "_sessao", escopo)
    monkeypatch.setattr(comunicacao, "_reabrir_presos", lambda agora: 0)
    monkeypatch.setattr(comunicacao, "fila", lambda *a, **k: linhas)
    monkeypatch.setattr(comunicacao, "_fato", lambda db, r: SimpleNamespace(status="criada", sem_retorno_desde=None))
    monkeypatch.setattr(comunicacao, "montar", lambda *a, **k: ("a@b.org", "assunto", "corpo"))
    monkeypatch.setattr(comunicacao, "_reivindicar", lambda r, agora: True)
    monkeypatch.setattr(comunicacao, "_devolver", lambda r, agora: devolvidos.append(r.id))
    monkeypatch.setattr(comunicacao, "_registrar_falha", lambda *a: falhas.append(a))

    def falha(*a):
        raise EmailError("x", codigo="smtp_autenticacao", sistemica=True)

    monkeypatch.setattr(email_mod, "enviar", falha)
    ctx = _ctx(aplicar=True)
    comunicacao.enviar_comunicacao(ctx)
    assert devolvidos == [1] and falhas == [] and ctx.erro_sistemico == "disjuntor: smtp_autenticacao"


# ======================================================= contrato do hub
def test_alteracao_de_linha_valida_tudo():
    from app.integracoes.hub import alteracao_de_linha

    boa = {"solicitacao_id": SID.upper(), "crm_id": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE", "contact_id": CID,
           "situacao": "aguardando_associado", "mensagem_publica": "Envie o diploma", "modificado_em":
           "2026-10-30T12:00:00Z", "cursor": "MjAyNi0xMC0zMA=="}
    alt = alteracao_de_linha(boa)
    assert alt.solicitacao_id == SID and alt.crm_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    for chave, valor in (("situacao", "outra"), ("cursor", "tem espaço"), ("solicitacao_id", "x"),
                         ("contact_id", None), ("modificado_em", "ontem"), ("mensagem_publica", 3)):
        assert alteracao_de_linha({**boa, chave: valor}) is None, chave


def test_hub_stub_solicitacoes(monkeypatch):
    from app.config import get_settings
    from app.integracoes.hub_stub import ClienteHubStub

    stub = ClienteHubStub()
    with pytest.raises(HubError) as e:
        stub.solicitacao_espelhar({"solicitacao_id": SID})
    assert e.value.codigo == "edicao_desligada"
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    get_settings.cache_clear()
    crm = stub.solicitacao_espelhar({"solicitacao_id": SID, "contact_id": CID, "campos": {}})
    assert crm == stub.solicitacao_espelhar({"solicitacao_id": SID, "contact_id": CID, "campos": {}})  # idempotente
    stub.solicitacao_status_atualizar({"solicitacao_id": SID, "crm_id": crm, "status": "cancelada"})
    with pytest.raises(HubError):
        stub.solicitacao_status_atualizar({"solicitacao_id": SID, "crm_id": CID, "status": "cancelada"})
    with pytest.raises(HubError):
        stub.solicitacao_espelhar({"solicitacao_id": SID, "campos": {"cpf": "1"}})
    stub.alteracoes = [{"n": 1}, {"n": 2}, {"n": 3}]
    pagina = stub.solicitacao_alteracoes_consultar(None, 2)
    assert [p["cursor"] for p in pagina] == ["1", "2"]
    assert stub.solicitacao_alteracoes_consultar("2", 2) == [{"n": 3, "cursor": "3"}]


def test_hub_real_solicitacoes_contrato_e_ferramenta_ausente(monkeypatch):
    monkeypatch.setenv("HUB_MODE", "real")
    monkeypatch.setenv("HUB_CLIENT_SECRET", "s" * 32)
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    from app.config import get_settings
    from app.integracoes.hub import ClienteHubReal

    get_settings.cache_clear()
    pedidos = []

    def tratar(req):
        pedidos.append(req)
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 600})
        nome = req.url.path.rsplit("/", 1)[-1]
        if nome == "solicitacao.espelhar":
            return httpx.Response(200, json={"colunas": [], "linhas": [{"crm_id": "AAAAAAAA-BBBB-CCCC-DDDD-"
                                                                                 "EEEEEEEEEEEE", "criada": True}]})
        return httpx.Response(404, json={"erro": "ferramenta_inexistente"})

    hub = ClienteHubReal(transporte=httpx.MockTransport(tratar))
    assert hub.solicitacao_espelhar({"solicitacao_id": SID}) == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    corpo = json.loads(pedidos[-1].content)
    assert corpo == {"argumentos": {"solicitacao_id": SID}}
    assert "ferramentas%3Aescrever" in pedidos[0].content.decode()
    with pytest.raises(HubError) as e:
        hub.solicitacao_alteracoes_consultar(None, 100)
    assert e.value.codigo == "fonte_indisponivel"  # ferramenta ainda não existe (P-06): o job registra e recua


# ================================================================== e-mails
def test_textos_transacionais_voz_da_apm():
    from app.integracoes import email

    link = f"https://minha.apm.org.br/area/solicitacoes/{SID}"
    textos = [
        email.texto_solicitacao_recebida("TELMA NOGUEIRA", "Outro assunto", 10, link),
        email.texto_sem_retorno("TELMA NOGUEIRA", "Outro assunto", link),
        email.texto_como_foi("TELMA NOGUEIRA", "Outro assunto", link),
        email.texto_cancelamento_recebido("TELMA NOGUEIRA", link),
    ]
    for assunto, corpo in textos:
        assert "!" not in assunto + corpo
        assert corpo.startswith("Olá, Telma.") and link in corpo and "NOGUEIRA" not in corpo
        assert "Nogueira" not in corpo
    assert "10 dias" in textos[0][1] and "0 a 10" in textos[2][1] and "continua ativa" in textos[3][1]
    assert email.texto_como_foi(None, "x", link)[1].startswith("Olá.\n")
    assert email.primeiro_nome("MARIA-JOSÉ DA SILVA") == "Maria-José"
    assert email.primeiro_nome("  \x00 ") == ""
    assunto, corpo = email.texto_interno("A16", tipo="Cancelamento da associação", solicitacao_id=SID,
                                         nome="TELMA\nNOGUEIRA", num_contato="12345", detalhe="Pedido.")
    assert "!" not in assunto + corpo and "TELMA NOGUEIRA" in corpo and "12345" in corpo and SID in corpo


def test_email_error_compativel_e_tipado():
    erro = EmailError("falha")
    assert str(erro) == "falha" and erro.codigo == "smtp_indisponivel" and not erro.permanente
    from app.integracoes import email

    with pytest.raises(EmailError) as e:
        email.enviar("nao-e-email", "a", "b")
    assert e.value.permanente and e.value.codigo == "destinatario_invalido"


# =============================================================== settings
@pytest.mark.parametrize("chave,valor", [
    ("JOBS_HEARTBEAT", "relativo/arquivo"), ("JOBS_HEARTBEAT", "/tmp/../etc/x"),
    ("JOBS_INTERVALO_ESPELHO", "5"), ("JOBS_LOTE", "500"), ("JOBS_SITUACAO_HORA", "24"),
    ("JOBS_SITUACAO_LOTE", "201"), ("JOBS_SITUACAO_PAUSA", "0"), ("CENTRAL_EMAIL", "Central <c@apm.org.br>"),
])
def test_settings_dos_jobs_recusam_valor_invalido(monkeypatch, chave, valor):
    from pydantic import ValidationError

    from app.config import Settings

    monkeypatch.setenv(chave, valor)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_dos_jobs_padroes_e_aplicar_com_stub(monkeypatch):
    from pydantic import ValidationError

    from app.config import Settings

    s = Settings()
    assert s.jobs_aplicar is False and s.jobs_heartbeat == "/tmp/jobs.heartbeat" and s.central_email is None
    monkeypatch.setenv("CENTRAL_EMAIL", " Central@APM.org.br ")
    assert Settings().central_email == "central@apm.org.br"
    monkeypatch.setenv("CENTRAL_EMAIL", "")
    assert Settings().central_email is None
    monkeypatch.setenv("JOBS_APLICAR", "1")
    assert Settings().jobs_aplicar is True  # APP_ENV=test com hub simulado: permitido
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValidationError):
        Settings()  # staging + HUB_MODE=stub + JOBS_APLICAR=1: gravaria crm_id falso
