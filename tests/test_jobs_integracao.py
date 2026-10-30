"""Serviço de jobs com MySQL REAL (migrações 000–014) — frente C da Onda 2.

Rodar com TESTE_DB_HOST/TESTE_DB_USER/TESTE_DB_PASS/TESTE_DB_NAME (usuário da
aplicação, `apm_area`): os jobs rodam com os grants por coluna de verdade, o
que prova que o UPDATE concedido basta (e que nada fora dele é tocado). Sem as
variáveis, pulados (conftest). O hub é o simulado (`ClienteHubStub`) com escrita
ligada; o SMTP é o stub (`SMTP_MODE=stub`, nada sai).

Cada teste cria associados novos (contact_id aleatório) e restringe o espelho e
a comunicação aos próprios itens (`ids=`) — a base do ensaio é compartilhada.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.integracoes.hub import HubError

pytestmark = pytest.mark.mysql


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _db():
    from app.database import session_scope

    return session_scope()


@pytest.fixture
def ambiente(monkeypatch):
    from app import flags, prontidao
    from app.config import get_settings
    from app.dominio import ajuda, carteirinha
    from app.dominio.solicitacoes import parametros
    from app.integracoes.hub import redefinir_hub
    from app.integracoes.hub_stub import ClienteHubStub
    from app.jobs import base

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    monkeypatch.setenv("JOBS_SITUACAO_PAUSA", "0.1")
    get_settings.cache_clear()
    for modulo in (prontidao, flags, parametros, ajuda):
        modulo.limpar_cache()
    base.redefinir_cache_rastro()
    carteirinha.redefinir_cache_colunas()
    stub = ClienteHubStub()
    redefinir_hub(stub)
    yield stub
    redefinir_hub(None)
    get_settings.cache_clear()


def _ctx(agora: datetime, aplicar: bool = True, **kw):
    from app.jobs.base import Contexto

    return Contexto(job="teste_job", aplicar=aplicar, agora=agora, **kw)


def _cid() -> str:
    return str(uuid.uuid4())


def _criar(cid: str, tipo: str = "outro", campos: dict | None = None) -> str:
    from app.dominio.solicitacoes import schemas, servico

    campos = schemas.validar(tipo, campos or {"assunto": "Dúvida", "mensagem": "Quero saber do seguro."})
    return servico.criar(contact_id=cid, sub_hash=secrets.token_hex(32), tipo_servico=tipo, campos=campos,
                         chave_idempotencia=str(uuid.uuid4())).id


def _sol(sid: str):
    with _db() as db:
        return db.execute(text("SELECT * FROM solicitacao WHERE id = :id"), {"id": sid}).mappings().first()


def _eventos(sid: str) -> list:
    with _db() as db:
        return list(db.execute(text(
            "SELECT evento, de_status, para_status, ator, origem, mensagem_publica FROM solicitacao_evento "
            "WHERE solicitacao_id = :id ORDER BY id"), {"id": sid}).mappings())


def _outbox(sid: str) -> dict[tuple[str, str, str], dict]:
    with _db() as db:
        linhas = db.execute(text(
            "SELECT * FROM comunicacao_evento WHERE referencia_id = :id"), {"id": sid}).mappings()
        return {(r["gatilho"], r["canal"], r["destinatario"]): dict(r) for r in linhas}


def _perfil(cid: str, email: str | None = "telma@exemplo.org") -> None:
    with _db() as db:
        db.execute(text(
            "INSERT INTO associado_perfil (contact_id, nome, email, num_contato, origem, atualizado_em) "
            "VALUES (:c, 'TELMA NOGUEIRA', :e, '123456', 'userinfo', :agora)"), {"c": cid, "e": email,
                                                                                   "agora": _agora()})


def _espelhar(stub, sid: str, agora: datetime, aplicar: bool = True):
    from app.jobs import solicitacoes

    ctx = _ctx(agora, aplicar)
    solicitacoes.espelhar_solicitacoes(ctx, hub=stub, ids=[sid])
    return ctx


# ============================================================ job_execucao
def test_job_execucao_aberta_fechada_orfa_trava_e_grants(ambiente):
    from app.jobs.agenda import Quando
    from app.jobs.base import Executor, Job, abrir_execucao

    nome = f"teste_{secrets.token_hex(4)}"
    vistos = []

    def trabalho(ctx):
        with _db() as db:
            vistos.append(db.execute(text("SELECT status FROM job_execucao WHERE job = :j ORDER BY id DESC LIMIT 1"),
                                     {"j": nome}).scalar())
        ctx.lidos, ctx.gravados, ctx.erros = 5, 4, 1

    job = Job(nome, Quando(intervalo_s=60), trabalho)
    # Linha órfã (processo morreu no meio): a próxima execução a fecha como abortado.
    orfa, _ = abrir_execucao(nome, aplicar=False, host="h", versao="v1", agora=_agora() - timedelta(minutes=5))
    ex = Executor()
    assert ex.executar(job) == "ok"
    assert vistos == ["executando"]  # a linha nasce aberta antes do trabalho
    with _db() as db:
        linhas = db.execute(text("SELECT * FROM job_execucao WHERE job = :j ORDER BY id"), {"j": nome}).mappings().all()
    assert [r["status"] for r in linhas] == ["abortado", "ok"] and linhas[0]["id"] == orfa
    ok = linhas[1]
    assert ok["modo"] == "simular" and ok["terminado_em"] >= ok["iniciado_em"]
    assert (ok["itens_lidos"], ok["itens_gravados"], ok["itens_erro"]) == (5, 4, 1)
    assert ok["versao_app"].startswith("src-") and ok["erro_resumo"] is None

    # Trava ocupada por outro processo: não roda, não abre linha.
    from app.database import engine

    with engine.connect() as outra:
        assert outra.execute(text("SELECT GET_LOCK(:n, 0)"), {"n": f"area_job_{nome}"}).scalar() == 1
        assert ex.executar(job) == "ocupado"
        outra.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": f"area_job_{nome}"})
    with _db() as db:
        assert db.execute(text("SELECT COUNT(*) FROM job_execucao WHERE job = :j"), {"j": nome}).scalar() == 2

    # Grants por coluna (sql/011): só o que fecha a linha.
    for sql, codigo in (
        ("UPDATE job_execucao SET job = 'outro_job' WHERE id = :id", 1143),
        ("UPDATE job_execucao SET iniciado_em = UTC_TIMESTAMP(6) WHERE id = :id", 1143),
        ("UPDATE job_execucao SET host = 'x' WHERE id = :id", 1143),
        ("DELETE FROM job_execucao WHERE id = :id", 1142),
        ("UPDATE job_execucao SET erro_resumo = 'cpf 123.456.789-09' WHERE id = :id", 3819),
        ("UPDATE job_execucao SET erro_resumo = 'Authorization: Bearer abcdefghijkl' WHERE id = :id", 3819),
        ("UPDATE job_execucao SET terminado_em = NULL WHERE id = :id", 3819),
    ):
        with pytest.raises(DBAPIError) as e:
            with _db() as db:
                db.execute(text(sql), {"id": ok["id"]})
        assert e.value.orig.args[0] == codigo, sql
    with pytest.raises(DBAPIError) as e:
        abrir_execucao("Nome-Invalido", aplicar=False, host="h", versao="v", agora=_agora())
    assert e.value.orig.args[0] == 3819


def test_executor_real_fecha_erro_com_resumo_seguro(ambiente):
    from app.jobs.agenda import Quando
    from app.jobs.base import Executor, Job

    nome = f"teste_{secrets.token_hex(4)}"

    def quebra(ctx):
        raise RuntimeError("password=nao-pode 123.456.789-09")

    assert Executor().executar(Job(nome, Quando(intervalo_s=60), quebra)) == "erro"
    with _db() as db:
        r = db.execute(text("SELECT status, erro_resumo FROM job_execucao WHERE job = :j"), {"j": nome}).first()
    assert r.status == "erro" and r.erro_resumo == "RuntimeError"


def test_rastro_para_db_health_e_alertas(ambiente):
    from app.jobs import rastro

    ultimas = rastro.ultimas_execucoes_ok()
    assert isinstance(ultimas, dict)
    estado = rastro.estado()
    assert estado["tabela"] is True and {j["job"] for j in estado["jobs"]} >= {"espelhar_solicitacoes"}


# ================================================================== espelho
def test_espelho_dry_run_nao_muda_nada(ambiente):
    cid = _cid()
    sid = _criar(cid)
    ctx = _espelhar(ambiente, sid, _agora() + timedelta(seconds=1), aplicar=False)
    s = _sol(sid)
    assert ctx.lidos == 1 and s["status"] == "criada" and s["crm_sync"] == "pendente" and s["crm_id"] is None
    assert ambiente.espelhar_chamadas == []


def test_espelho_com_stub_promove_enviada_e_leva_o_cancelamento(ambiente):
    cid = _cid()
    sid = _criar(cid)
    agora = _agora() + timedelta(seconds=1)
    ctx = _espelhar(ambiente, sid, agora)
    s = _sol(sid)
    assert ctx.gravados == 1 and s["status"] == "enviada" and s["crm_sync"] == "ok" and s["enviada_em"] == agora
    assert s["crm_id"] == ambiente.espelhos[sid] and s["crm_tentativas"] == 0
    chamada = ambiente.espelhar_chamadas[-1]
    assert chamada["contact_id"] == cid and chamada["status"] == "criada" and "cpf" not in chamada
    ev = _eventos(sid)
    assert ev[-1]["evento"] == "transicao" and (ev[-1]["de_status"], ev[-1]["para_status"]) == ("criada", "enviada")
    assert (ev[-1]["ator"], ev[-1]["origem"]) == ("sistema", "job")
    with _db() as db:
        uso = db.execute(text(
            "SELECT origem, JSON_UNQUOTE(JSON_EXTRACT(detalhes, '$.para')) AS para FROM evento_uso "
            "WHERE acao = 'solicitacao_status_alterado' AND entidade_id = :id"), {"id": sid}).first()
    assert uso.origem == "job" and uso.para == "enviada"

    # O associado cancela (enviada → cancelada): a máquina reabre o espelho; o job leva o status.
    from app.dominio.solicitacoes import servico

    servico.cancelar(cid, sid, motivo="Resolvi de outro jeito")
    assert _sol(sid)["crm_sync"] == "pendente"
    _espelhar(ambiente, sid, _agora() + timedelta(seconds=1))
    assert _sol(sid)["crm_sync"] == "ok" and len(ambiente.espelhar_chamadas) == 1
    enviado = ambiente.status_enviados[-1]
    assert enviado["status"] == "cancelada" and enviado["crm_id"] == s["crm_id"]
    assert enviado["cancel_motivo"] == "Resolvi de outro jeito"


def test_espelho_recuo_e_falhou_apos_10_tentativas(ambiente):
    cid = _cid()
    sid = _criar(cid)
    ambiente.falhar_solicitacoes[sid] = HubError("fonte_indisponivel")
    agora = _agora() + timedelta(seconds=1)
    _espelhar(ambiente, sid, agora)
    s = _sol(sid)
    assert s["crm_sync"] == "erro" and s["crm_tentativas"] == 1 and s["crm_proxima_em"] == agora + timedelta(minutes=1)
    # Antes do recuo vencer, nada acontece.
    ctx = _espelhar(ambiente, sid, agora + timedelta(seconds=30))
    assert ctx.lidos == 0 and _sol(sid)["crm_tentativas"] == 1
    for i in range(2, 11):
        agora += timedelta(hours=2)
        _espelhar(ambiente, sid, agora)
        assert _sol(sid)["crm_tentativas"] == i
    s = _sol(sid)
    assert s["crm_sync"] == "falhou" and s["status"] == "criada"
    with _db() as db:
        log = db.execute(text(
            "SELECT severidade, contact_id, JSON_EXTRACT(detalhes, '$.tentativas') AS tentativas FROM evento_log "
            "WHERE tipo = 'solicitacao_espelho_falhou' AND JSON_UNQUOTE(JSON_EXTRACT(detalhes, '$.solicitacao_id')) "
            "= :id"), {"id": sid}).first()
    assert log.severidade == "erro" and log.contact_id == cid and int(log.tentativas) == 10
    # `falhou` sai da fila até o reprocessamento manual (docs/JOBS.md §5).
    assert _espelhar(ambiente, sid, agora + timedelta(days=1)).lidos == 0


def test_espelho_erro_permanente_vai_direto_a_falhou(ambiente):
    sid = _criar(_cid())
    ambiente.falhar_solicitacoes[sid] = HubError("entrada_invalida", 400)
    _espelhar(ambiente, sid, _agora() + timedelta(seconds=1))
    s = _sol(sid)
    assert s["crm_sync"] == "falhou" and s["crm_tentativas"] == 1


def test_janela_de_arrependimento_e_desistencia(ambiente):
    from app.dominio.solicitacoes import servico

    cid = _cid()
    campos = {"motivo": "preco", "quer_conversa": False}
    sid = _criar(cid, "cancelamento_associacao", campos)
    agora = _agora() + timedelta(seconds=1)
    assert _espelhar(ambiente, sid, agora).lidos == 0  # dentro da janela: nada sai
    _espelhar(ambiente, sid, agora + timedelta(hours=25))
    assert _sol(sid)["status"] == "enviada" and ambiente.espelhar_chamadas[-1]["tipo"] == "cancelamento_associacao"

    # Desistiu dentro da janela: nunca chega ao CRM.
    cid2 = _cid()
    sid2 = _criar(cid2, "cancelamento_associacao", campos)
    servico.cancelar(cid2, sid2, motivo=None)
    chamadas = len(ambiente.espelhar_chamadas)
    ctx = _espelhar(ambiente, sid2, _agora() + timedelta(hours=25))
    s2 = _sol(sid2)
    assert ctx.gravados == 1 and s2["crm_sync"] == "ok" and s2["crm_id"] is None
    assert len(ambiente.espelhar_chamadas) == chamadas


# ============================================================ sincronização
def test_sincronizar_aplica_crm_e_terminal_local_prevalece(ambiente):
    from app.dominio.solicitacoes import servico
    from app.jobs import solicitacoes

    cid = _cid()
    sid = _criar(cid)
    _espelhar(ambiente, sid, _agora() + timedelta(seconds=1))
    crm_id = _sol(sid)["crm_id"]
    base = {"solicitacao_id": sid, "crm_id": crm_id, "contact_id": cid, "modificado_em": "2026-10-30T12:00:00Z"}
    ambiente.alteracoes = [{**base, "situacao": "aguardando_associado", "mensagem_publica": "Envie o diploma."}]
    ctx = _ctx(_agora() + timedelta(seconds=2))
    solicitacoes.sincronizar_solicitacoes(ctx, hub=ambiente)
    assert ctx.posicao == "1" and ctx.gravados == 1
    s = _sol(sid)
    assert s["status"] == "pendente_associado" and s["crm_sync"] == "ok"  # origem crm não reabre o espelho
    ev = _eventos(sid)
    assert [(e["para_status"], e["origem"]) for e in ev[-2:]] == [("em_atendimento", "crm"),
                                                                 ("pendente_associado", "crm")]
    assert ev[-1]["mensagem_publica"] == "Envie o diploma."

    # Mesma posição de novo: nada muda (idempotente); posição avança só com linha nova.
    ctx2 = _ctx(_agora() + timedelta(seconds=3), posicao_anterior="1", posicao="1")
    solicitacoes.sincronizar_solicitacoes(ctx2, hub=ambiente)
    assert ctx2.lidos == 0 and ctx2.posicao == "1"

    # Associado cancela (terminal local), espelho leva; o CRM ainda "conclui": local prevalece.
    servico.cancelar(cid, sid, motivo=None)
    _espelhar(ambiente, sid, _agora() + timedelta(seconds=4))
    assert _sol(sid)["crm_sync"] == "ok"
    ambiente.alteracoes.append({**base, "situacao": "concluida", "mensagem_publica": None})
    ctx3 = _ctx(_agora() + timedelta(seconds=5), posicao_anterior="1", posicao="1")
    solicitacoes.sincronizar_solicitacoes(ctx3, hub=ambiente)
    s = _sol(sid)
    assert s["status"] == "cancelada" and s["crm_sync"] == "pendente" and ctx3.posicao == "2"
    with _db() as db:
        aviso = db.execute(text(
            "SELECT severidade FROM evento_log WHERE tipo = 'solicitacao_divergencia_crm' "
            "AND JSON_UNQUOTE(JSON_EXTRACT(detalhes, '$.solicitacao_id')) = :id"), {"id": sid}).first()
    assert aviso.severidade == "aviso"


def test_sincronizar_recusa_identidade_divergente(ambiente):
    from app.jobs import solicitacoes

    cid = _cid()
    sid = _criar(cid)
    _espelhar(ambiente, sid, _agora() + timedelta(seconds=1))
    ambiente.alteracoes = [{"solicitacao_id": sid, "crm_id": _sol(sid)["crm_id"], "contact_id": _cid(),
                            "situacao": "concluida", "modificado_em": "2026-10-30T12:00:00Z"}]
    ctx = _ctx(_agora() + timedelta(seconds=2))
    solicitacoes.sincronizar_solicitacoes(ctx, hub=ambiente)
    assert _sol(sid)["status"] == "enviada" and ctx.gravados == 0


# ============================================================== sem retorno
def test_sem_retorno_primeiro_e_segundo_vencimento(ambiente):
    from app.jobs import solicitacoes

    cid = _cid()
    sid = _criar(cid)
    agora = _agora() + timedelta(seconds=1)
    _espelhar(ambiente, sid, agora)
    prazo = int(_sol(sid)["prazo_retorno_dias"])
    solicitacoes.marcar_sem_retorno(_ctx(agora + timedelta(days=prazo - 1)))
    assert _sol(sid)["sem_retorno_desde"] is None
    primeiro = agora + timedelta(days=prazo, hours=1)
    ctx = _ctx(primeiro, aplicar=False)  # efeito local: roda também em dry-run
    solicitacoes.marcar_sem_retorno(ctx)
    assert _sol(sid)["sem_retorno_desde"] == primeiro and ctx.gravados >= 1
    assert {("A05", "email", "associado"), ("A05", "interno", "equipe"), ("A05", "rd", "associado")} \
        <= set(_outbox(sid))
    assert _eventos(sid)[-1]["evento"] == "sem_retorno"
    solicitacoes.marcar_sem_retorno(_ctx(primeiro + timedelta(hours=1)))  # idempotente
    assert [e["evento"] for e in _eventos(sid)].count("sem_retorno") == 1
    segundo = agora + timedelta(days=2 * prazo, hours=1)
    solicitacoes.marcar_sem_retorno(_ctx(segundo))
    with _db() as db:
        fila = db.execute(text("SELECT motivo, status FROM fila_ligacao WHERE referencia_id = :id"),
                          {"id": sid}).all()
    assert [(f.motivo, f.status) for f in fila] == [("sem_retorno_2", "pendente")]
    assert _eventos(sid)[-1]["evento"] == "sem_retorno_2"
    solicitacoes.marcar_sem_retorno(_ctx(segundo + timedelta(hours=1)))
    assert [e["evento"] for e in _eventos(sid)].count("sem_retorno_2") == 1


# ============================================================== comunicação
def _comunicar(ids, agora, aplicar=True):
    from app.jobs import comunicacao

    ctx = _ctx(agora, aplicar)
    comunicacao.enviar_comunicacao(ctx, ids=ids)
    return ctx


def test_comunicacao_dry_run_suprime_rd_e_nao_envia_email(ambiente):
    cid = _cid()
    _perfil(cid)
    sid = _criar(cid)
    fila = _outbox(sid)
    ids = [r["id"] for r in fila.values()]
    _comunicar(ids, _agora() + timedelta(seconds=1), aplicar=False)
    fila = _outbox(sid)
    assert fila[("A04", "email", "associado")]["status"] == "pendente"
    assert fila[("A04", "rd", "associado")]["status"] == "suprimido"
    assert fila[("A04", "rd", "associado")]["supressao_motivo"] == "sem_credencial"


def test_comunicacao_envia_email_marca_enviado_e_registra(ambiente):
    cid = _cid()
    _perfil(cid)
    sid = _criar(cid)
    ids = [r["id"] for r in _outbox(sid).values()]
    ctx = _comunicar(ids, _agora() + timedelta(seconds=1))
    fila = _outbox(sid)
    email = fila[("A04", "email", "associado")]
    assert email["status"] == "enviado" and email["externo_id"] == "smtp_stub" and email["tentativas"] == 1
    assert fila[("A04", "rd", "associado")]["status"] == "suprimido" and ctx.gravados == 2
    with _db() as db:
        envio = db.execute(text("SELECT situacao, origem_retorno, erro_codigo FROM comunicacao_envio "
                                "WHERE comunicacao_evento_id = :id"), {"id": email["id"]}).all()
        supressao = db.execute(text("SELECT motivo FROM comunicacao_supressao WHERE comunicacao_evento_id = :id"),
                               {"id": fila[("A04", "rd", "associado")]["id"]}).all()
    assert [(e.situacao, e.origem_retorno, e.erro_codigo) for e in envio] == [("enviado", "smtp", None)]
    assert [s.motivo for s in supressao] == ["sem_credencial"]
    # Repetir não reenvia.
    assert _comunicar(ids, _agora() + timedelta(seconds=2)).lidos == 0


def test_comunicacao_sem_email_no_cache_falha_permanente(ambiente):
    cid = _cid()  # sem associado_perfil
    sid = _criar(cid)
    alvo = _outbox(sid)[("A04", "email", "associado")]
    _comunicar([alvo["id"]], _agora() + timedelta(seconds=1))
    linha = _outbox(sid)[("A04", "email", "associado")]
    assert linha["status"] == "falhou" and linha["tentativas"] == 1
    with _db() as db:
        envio = db.execute(text("SELECT situacao, erro_codigo FROM comunicacao_envio "
                                "WHERE comunicacao_evento_id = :id"), {"id": alvo["id"]}).first()
        log = db.execute(text("SELECT severidade FROM evento_log WHERE tipo = 'comunicacao_falhou' "
                              "AND JSON_EXTRACT(detalhes, '$.comunicacao_evento_id') = :id"), {"id": alvo["id"]}).first()
    assert (envio.situacao, envio.erro_codigo) == ("falha", "sem_email") and log.severidade == "erro"


def test_comunicacao_interna_com_e_sem_central_email_e_fato_mudou(ambiente, monkeypatch):
    from app.config import get_settings
    from app.dominio.solicitacoes import maquina
    from app.jobs import solicitacoes

    cid = _cid()
    _perfil(cid)
    sid = _criar(cid)
    agora = _agora() + timedelta(seconds=1)
    _espelhar(ambiente, sid, agora)
    prazo = int(_sol(sid)["prazo_retorno_dias"])
    marco = agora + timedelta(days=prazo, hours=1)
    solicitacoes.marcar_sem_retorno(_ctx(marco))
    fila = _outbox(sid)
    interno = fila[("A05", "interno", "equipe")]
    # Sem CENTRAL_EMAIL: o aviso interno é suprimido, nunca vai a outro lugar.
    _comunicar([interno["id"]], marco + timedelta(seconds=1))
    assert _outbox(sid)[("A05", "interno", "equipe")]["supressao_motivo"] == "sem_credencial"

    # Outro pedido, agora com CENTRAL_EMAIL: o interno sai; o marcador some antes do
    # e-mail ao associado (atendimento começou) → `fato_mudou`.
    monkeypatch.setenv("CENTRAL_EMAIL", "central@exemplo.org")
    get_settings.cache_clear()
    sid2 = _criar(cid, campos={"assunto": "Outra", "mensagem": "Segunda dúvida."})
    _espelhar(ambiente, sid2, _agora() + timedelta(seconds=1))
    solicitacoes.marcar_sem_retorno(_ctx(marco))
    fila2 = _outbox(sid2)
    _comunicar([fila2[("A05", "interno", "equipe")]["id"]], marco + timedelta(seconds=1))
    assert _outbox(sid2)[("A05", "interno", "equipe")]["status"] == "enviado"
    with _db() as db:
        maquina.transitar(db, solicitacao_id=sid2, para="em_atendimento", ator="apm", origem="crm",
                          agora=marco + timedelta(seconds=2))
    _comunicar([fila2[("A05", "email", "associado")]["id"]], marco + timedelta(seconds=3))
    linha = _outbox(sid2)[("A05", "email", "associado")]
    assert linha["status"] == "suprimido" and linha["supressao_motivo"] == "fato_mudou"


def test_comunicacao_recuo_e_falhou_apos_10_no_smtp(ambiente, monkeypatch):
    from app.integracoes import email as email_mod
    from app.integracoes.email import EmailError

    cid = _cid()
    _perfil(cid)
    sid = _criar(cid)
    alvo = _outbox(sid)[("A04", "email", "associado")]

    def falha(*a):
        raise EmailError("x")

    monkeypatch.setattr(email_mod, "enviar", falha)
    agora = _agora() + timedelta(seconds=1)
    for i in range(1, 11):
        _comunicar([alvo["id"]], agora)
        linha = _outbox(sid)[("A04", "email", "associado")]
        assert linha["tentativas"] == i
        agora += timedelta(hours=2)
    assert linha["status"] == "falhou" and linha["proxima_tentativa_em"] is None
    with _db() as db:
        n = db.execute(text("SELECT COUNT(*) FROM comunicacao_envio WHERE comunicacao_evento_id = :id "
                            "AND situacao = 'falha' AND erro_codigo = 'smtp_indisponivel'"), {"id": alvo["id"]}).scalar()
    assert n == 10


# ================================================================ carteirinha
def test_situacao_carteirinhas_revoga_e_disjuntor(ambiente):
    from app.dominio.carteirinha import token_para
    from app.jobs import carteirinha

    agora = _agora()
    cancelado, ativo, velho = _cid(), _cid(), _cid()
    with _db() as db:
        for cid, acesso in ((cancelado, agora), (ativo, agora), (velho, agora - timedelta(days=120))):
            db.execute(text(
                "INSERT INTO associado (contact_id, sub_hash, primeiro_acesso_em, ultimo_acesso_em, carteirinha_token) "
                "VALUES (:c, :h, :a, :a, :t)"), {"c": cid, "h": secrets.token_hex(32), "a": acesso,
                                                 "t": token_para(cid)})
    ambiente.situacoes[cancelado] = "cancelado"
    ctx = _ctx(agora + timedelta(seconds=1), aplicar=False)  # leitura: roda nos dois modos
    carteirinha.situacao_carteirinhas(ctx, hub=ambiente)
    with _db() as db:
        linhas = {r.contact_id: r for r in db.execute(text(
            "SELECT contact_id, carteirinha_revogada_em, situacao_normalizada, situacao_consultada_em FROM associado "
            "WHERE contact_id IN (:a, :b, :c)"), {"a": cancelado, "b": ativo, "c": velho})}
    assert linhas[cancelado].situacao_normalizada == "cancelado" and linhas[cancelado].carteirinha_revogada_em
    assert linhas[ativo].situacao_normalizada == "ativo" and linhas[ativo].carteirinha_revogada_em is None
    assert linhas[velho].situacao_consultada_em is None  # sem acesso em 90 dias: fora do lote
    assert ctx.gravados >= 2 and ctx.erro_sistemico is None

    # Leitura recente (< 20 h) não é repetida: só os 5 novos entram; hub fora → disjuntor no 5º.
    novos = [_cid() for _ in range(5)]
    with _db() as db:
        for cid in novos:
            db.execute(text(
                "INSERT INTO associado (contact_id, sub_hash, primeiro_acesso_em, ultimo_acesso_em, "
                " carteirinha_token) VALUES (:c, :h, :a, :a, :t)"),
                {"c": cid, "h": secrets.token_hex(32), "a": agora, "t": token_para(cid)})
    ambiente.falhar = True
    ctx2 = _ctx(agora + timedelta(seconds=2))
    carteirinha.situacao_carteirinhas(ctx2, hub=ambiente)
    assert ctx2.erro_sistemico and ctx2.erros == 5 and ctx2.gravados == 0
    assert ctx2.lidos == 5  # os lidos há menos de 20 h não voltam


def test_job_real_pelo_executor_registra_execucao(ambiente):
    from app.jobs import registro
    from app.jobs.base import Executor

    assert Executor().executar(registro.por_nome()["marcar_sem_retorno"]) == "ok"
    with _db() as db:
        r = db.execute(text("SELECT status, modo FROM job_execucao WHERE job = 'marcar_sem_retorno' "
                            "ORDER BY id DESC LIMIT 1")).first()
    assert (r.status, r.modo) == ("ok", "simular")
