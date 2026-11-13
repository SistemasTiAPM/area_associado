"""Paridade com o App APM com MySQL REAL (migrações 000–016) — ADR-0024.

Rodar com TESTE_DB_* (usuário da aplicação, `apm_area`): prova que os grants por coluna
da `sql/016` bastam (e que nada fora deles é tocado). O hub é o simulado, com escrita
ligada nos jobs. Cada teste usa contatos novos.

Cobre: espelho com slug do App e produto (503 → sem produto; 422 → cancelada pelo
sistema), lista e detalhe fundidos com o CRM (registro do App, situação e rótulos do App,
lista parcial com o hub fora), conversa (outbox, idempotência, limites, bloqueios),
job `enviar_mensagens` (purga do texto, limite do titular, falha definitiva, ordem),
sincronização com os status da conversa e as rotas da API atrás da flag.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.integracoes.hub import CANAL_APP, HubError

pytestmark = pytest.mark.mysql

PRODUTO_AUTO = "c0fce926-6e88-e911-a968-000d3ac1b6c7"
TEXTO = "Quero uma cotação para o meu carro."


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _db():
    from app.database import session_scope

    return session_scope()


@pytest.fixture
def ambiente(monkeypatch):
    from app import flags, prontidao
    from app.config import get_settings
    from app.dominio import ajuda
    from app.dominio.solicitacoes import catalogo, esquema, leitura_crm, mensagens, parametros
    from app.integracoes.hub import redefinir_hub
    from app.integracoes.hub_stub import ClienteHubStub
    from app.jobs import base

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    get_settings.cache_clear()
    for modulo in (prontidao, flags, parametros, ajuda):
        modulo.limpar_cache()
    base.redefinir_cache_rastro()
    esquema.redefinir()
    catalogo.redefinir()
    leitura_crm.redefinir()
    mensagens.redefinir()
    monkeypatch.setattr(flags, "_ler_tabela", lambda: {"solicitacoes_crm": True})
    stub = ClienteHubStub()
    redefinir_hub(stub)
    yield stub
    redefinir_hub(None)
    flags.limpar_cache()
    catalogo.redefinir()
    leitura_crm.redefinir()
    get_settings.cache_clear()


def _ctx(agora: datetime | None = None, aplicar: bool = True):
    from app.jobs.base import Contexto

    return Contexto(job="teste_job", aplicar=aplicar, agora=agora or _agora())


def _cid() -> str:
    """Contato novo, com a linha de `associado` (serializa criações e envios)."""
    cid = str(uuid.uuid4())
    with _db() as db:
        db.execute(text(
            "INSERT INTO associado (contact_id, sub_hash, primeiro_acesso_em, ultimo_acesso_em) "
            "VALUES (:c, :h, :agora, :agora)"), {"c": cid, "h": secrets.token_hex(32), "agora": _agora()})
    return cid


def _criar(cid: str, tipo: str = "seguro_carro", campos: dict | None = None) -> str:
    from app.dominio.solicitacoes import schemas, servico

    campos = schemas.validar(tipo, campos or {"mensagem": TEXTO})
    return servico.criar(contact_id=cid, sub_hash=secrets.token_hex(32), tipo_servico=tipo, campos=campos,
                         chave_idempotencia=str(uuid.uuid4())).id


def _sol(sid: str):
    with _db() as db:
        return db.execute(text("SELECT * FROM solicitacao WHERE id = :id"), {"id": sid}).mappings().first()


def _msg(mid: str):
    with _db() as db:
        return db.execute(text("SELECT * FROM solicitacao_mensagem WHERE id = :id"), {"id": mid}).mappings().first()


def _espelhar(stub, sid: str, agora: datetime | None = None):
    from app.jobs import solicitacoes

    ctx = _ctx(agora)
    solicitacoes.espelhar_solicitacoes(ctx, hub=stub, ids=[sid])
    return ctx


def _enviar_fila(stub, cid: str, agora: datetime | None = None, aplicar: bool = True):
    """Roda o job só para o contato do teste (`JOBS_ENSAIO_CONTATOS`): a base é compartilhada."""
    import os

    from app.config import get_settings
    from app.jobs import mensagens

    anterior = os.environ.get("JOBS_ENSAIO_CONTATOS")
    os.environ["JOBS_ENSAIO_CONTATOS"] = cid
    get_settings.cache_clear()
    try:
        ctx = _ctx(agora, aplicar)
        mensagens.enviar_mensagens(ctx, hub=stub)
        return ctx
    finally:
        if anterior is None:
            os.environ.pop("JOBS_ENSAIO_CONTATOS", None)
        else:
            os.environ["JOBS_ENSAIO_CONTATOS"] = anterior
        get_settings.cache_clear()


def _recarregar_crm():
    from app.dominio.solicitacoes import leitura_crm

    leitura_crm.redefinir()


# ================================================================== espelho
def test_espelho_manda_slug_do_app_e_produto_na_oportunidade(ambiente):
    cid = _cid()
    sid = _criar(cid)
    assert _espelhar(ambiente, sid).gravados == 1
    chamada = ambiente.criar_chamadas[-1]
    assert (chamada["tipo"], chamada["entidade"], chamada["assunto_id"], chamada["produto_id"]) == (
        "seguro_carro", "oportunidade", None, PRODUTO_AUTO)
    assert (chamada["titulo"], chamada["descricao"]) == ("Seguro Auto", TEXTO)
    s = _sol(sid)
    assert (s["status"], s["crm_id"], s["crm_entidade"], s["crm_protocolo"], s["crm_sync"]) == (
        "enviada", sid, "oportunidade", None, "ok")

    duvida = _criar(cid, "duvida", {"mensagem": "Como emito a segunda via do boleto?"})
    _espelhar(ambiente, duvida)
    chamada = ambiente.criar_chamadas[-1]
    assert chamada["tipo"] == "duvida" and "produto_id" not in chamada and chamada["entidade"] == "ocorrencia"
    assert _sol(duvida)["crm_protocolo"].startswith("CAS-")


def test_produto_indisponivel_reenvia_o_mesmo_registro_sem_produto(ambiente):
    sid = _criar(_cid())
    ambiente.produto_indisponivel = True
    assert _espelhar(ambiente, sid).gravados == 1
    com, sem = ambiente.criar_chamadas[-2:]
    assert com["registro_id"] == sem["registro_id"] == sid
    assert com["produto_id"] == PRODUTO_AUTO and "produto_id" not in sem
    assert _sol(sid)["status"] == "enviada" and ambiente.registros[sid]["produto_id"] is None


def test_produto_inativo_cancela_pelo_sistema_com_mensagem_publica(ambiente):
    from app.dominio.solicitacoes import rotulos

    cid = _cid()
    sid = _criar(cid)
    ambiente.produtos_inativos.add(PRODUTO_AUTO)
    ctx = _espelhar(ambiente, sid)
    assert (ctx.gravados, ctx.erros, ctx.erro_sistemico) == (1, 0, None)
    s = _sol(sid)
    assert (s["status"], s["crm_id"], s["crm_sync"], s["cancel_motivo"]) == ("cancelada", None, "ok",
                                                                             "servico_indisponivel")
    with _db() as db:
        ultimo = db.execute(text(
            "SELECT ator, origem, mensagem_publica FROM solicitacao_evento WHERE solicitacao_id = :s "
            "ORDER BY id DESC LIMIT 1"), {"s": sid}).first()
        avisos = db.execute(text(
            "SELECT COUNT(*) FROM notificacao WHERE contact_id = :c AND tipo = 'solicitacao_cancelada'"),
            {"c": cid}).scalar()
    assert tuple(ultimo) == ("sistema", "job", rotulos.MENSAGEM_SERVICO_INDISPONIVEL) and avisos == 1
    assert sid not in ambiente.registros
    assert _espelhar(ambiente, sid).lidos == 0  # saiu da fila


# ============================================================ lista e detalhe
def test_lista_funde_area_e_crm_com_rotulos_do_app(ambiente):
    from app.dominio.solicitacoes import leitura_crm

    cid = _cid()
    local_pendente = _criar(cid, "duvida", {"mensagem": "Ainda não chegou ao CRM."})
    no_crm = _criar(cid)
    _espelhar(ambiente, no_crm)
    do_app = ambiente.registro_app(cid, "outros", descricao="Texto que escrevi no app.")
    legado = ambiente.registro_app(cid, "seguros", entidade="oportunidade")
    ambiente.registros_central(cid, 1)  # aberto pela Central: nunca aparece
    ambiente.registro_app(_cid(), "duvida")  # de outro associado

    itens, parcial = leitura_crm.listar(cid)
    assert not parcial and {i["id"] for i in itens} == {local_pendente, no_crm, do_app, legado}
    por_id = {i["id"]: i for i in itens}

    # Ainda só na área: rótulos da spec v2, sem situação do CRM, sem conversa.
    p = por_id[local_pendente]
    assert (p["situacao"], p["rotulo_status"], p["pode_enviar_mensagem"], p["canal"], p["responde"]) == (
        None, "Recebida pela APM", False, "minha_apm", "central")
    # No CRM, aberto pela Minha APM: situação e rótulo do App.
    c = por_id[no_crm]
    assert (c["situacao"], c["rotulo_status"], c["status"], c["canal"], c["responde"], c["na_central"]) == (
        "aberta", "Aberta", "enviada", "minha_apm", "apm", True)
    assert c["pode_enviar_mensagem"] and not c["pode_cancelar"] and not c["nova_resposta"]
    # Aberto pelo App: aparece sem linha na área.
    a = por_id[do_app]
    assert (a["tipo"], a["canal"], a["situacao"], a["protocolo"], a["responde"]) == (
        {"codigo": "outros", "rotulo": "Outros assuntos"}, "app", "aberta", "CAS-000002-APPAPM", "central")
    assert a["pode_enviar_mensagem"] and not a["pode_avaliar"] and a["beneficio"] is None
    assert por_id[legado]["tipo"]["rotulo"] == "Seguros" and por_id[legado]["pode_enviar_mensagem"]
    with _db() as db:  # registro do App nunca ganha linha na área
        assert db.execute(text("SELECT COUNT(*) FROM solicitacao WHERE id IN (:a, :b)"),
                          {"a": do_app, "b": legado}).scalar() == 0

    # A Central responde no registro do App: situação, rótulo e selo; some ao abrir a conversa.
    ambiente.central_responder(do_app, "Pode nos enviar o comprovante?")
    _recarregar_crm()
    a = {i["id"]: i for i in leitura_crm.listar(cid)[0]}[do_app]
    assert (a["situacao"], a["rotulo_status"], a["nova_resposta"]) == (
        "aguardando_associado", "A Central aguarda seu retorno", True)
    leitura_crm.marcar_visto(cid, do_app)
    leitura_crm.marcar_visto(cid, do_app)  # UPDATE da mesma linha (grant só em visto_em)
    assert not {i["id"]: i for i in leitura_crm.listar(cid)[0]}[do_app]["nova_resposta"]

    # Abas: encerradas pelo estado do CRM.
    ambiente.definir_estado(no_crm, 2, 4)
    ambiente.definir_estado(do_app, 1, 5)
    _recarregar_crm()
    encerradas, _ = leitura_crm.listar(cid, situacao="encerradas")
    assert {(i["id"], i["rotulo_status"]) for i in encerradas} == {(no_crm, "Cancelada"), (do_app, "Concluída")}
    assert not any(i["pode_enviar_mensagem"] for i in encerradas)
    andamento, _ = leitura_crm.listar(cid, situacao="andamento")
    assert {i["id"] for i in andamento} == {local_pendente, legado}


def test_detalhe_do_registro_do_app_e_isolamento(ambiente):
    from app.dominio.solicitacoes import leitura_crm
    from app.dominio.solicitacoes.maquina import SolicitacaoNaoEncontrada

    cid, outro = _cid(), _cid()
    do_app = ambiente.registro_app(cid, "duvida", descricao="Texto que escrevi no app.")
    d = leitura_crm.detalhe(cid, do_app)
    assert d["campos"] == {"mensagem": "Texto que escrevi no app."} and d["linha_do_tempo"] == []
    assert d["avaliacao"] is None and d["canal"] == "app" and d["tipo"]["rotulo"] == "Dúvidas e perguntas"
    for chave in ("contact_id", "crm_id", "descricao", "titulo"):
        assert chave not in d
    with pytest.raises(SolicitacaoNaoEncontrada):
        leitura_crm.detalhe(outro, do_app)  # de outro associado = inexistente
    with pytest.raises(SolicitacaoNaoEncontrada):
        leitura_crm.detalhe(cid, str(uuid.uuid4()))

    local = _criar(cid)
    _espelhar(ambiente, local)
    _recarregar_crm()
    d = leitura_crm.detalhe(cid, local)
    assert d["campos"] == {"mensagem": TEXTO} and d["situacao"] == "aberta" and len(d["linha_do_tempo"]) == 2
    with pytest.raises(SolicitacaoNaoEncontrada):
        leitura_crm.detalhe(outro, local)


def test_hub_fora_lista_parcial_e_detalhe_503(ambiente):
    from app.dominio.solicitacoes import leitura_crm

    cid = _cid()
    local = _criar(cid)
    _espelhar(ambiente, local)
    do_app = ambiente.registro_app(cid, "duvida")
    ambiente.definir_estado(local, 0, 100000002)  # o job ainda não viu: vale o par gravado (0/1)
    ambiente.falhar = True
    _recarregar_crm()
    itens, parcial = leitura_crm.listar(cid)
    assert parcial and [i["id"] for i in itens] == [local]
    assert (itens[0]["situacao"], itens[0]["rotulo_status"], itens[0]["pode_enviar_mensagem"]) == (
        "aberta", "Aberta", True)
    assert leitura_crm.detalhe(cid, local)["id"] == local  # o que é da área continua abrindo
    with pytest.raises(leitura_crm.FonteIndisponivel):
        leitura_crm.detalhe(cid, do_app)  # só o CRM sabe: 503, nunca 404 enganoso
    antes = len(ambiente.listar_chamadas)
    leitura_crm.listar(cid)
    assert len(ambiente.listar_chamadas) == antes  # falha em cache: não martela o hub


def test_cache_da_lista_poupa_a_cota_do_hub(ambiente):
    from app.dominio.solicitacoes import leitura_crm

    cid = _cid()
    ambiente.registro_app(cid, "duvida")
    for _ in range(3):
        leitura_crm.listar(cid)
        leitura_crm.aberto_no_crm(cid, "duvida")
    assert ambiente.listar_chamadas == [(cid, 50)]
    assert leitura_crm.aberto_no_crm(cid, "duvida") and not leitura_crm.aberto_no_crm(cid, "seguro_carro")


# =================================================================== conversa
def test_conversa_outbox_job_e_purga_do_texto(ambiente):
    from app.dominio.solicitacoes import leitura_crm, mensagens

    cid = _cid()
    do_app = ambiente.registro_app(cid, "duvida")
    vazia = mensagens.listar(cid, do_app)
    assert vazia == {"mensagens": [], "pode_enviar": True, "motivo_bloqueio": None, "responde": "central",
                     "truncado": False}

    chave = str(uuid.uuid4())
    envio = mensagens.enviar(cid, do_app, texto="  Olá!\r\nSegue o que pediram.  ", chave_idempotencia=chave,
                             request_id="ab" * 8)
    assert envio.criada and envio.mensagem["estado"] == "enviando" and envio.mensagem["autor"] == "voce"
    assert envio.mensagem["texto"] == "Olá!\nSegue o que pediram."
    repetida = mensagens.enviar(cid, do_app, texto="outro texto, mesma chave", chave_idempotencia=chave)
    assert not repetida.criada and repetida.mensagem["texto"] == "Olá!\nSegue o que pediram."
    assert ambiente.interagir_chamadas == []  # o web nunca escreve no CRM

    conversa = mensagens.listar(cid, do_app)
    assert [(m["id"], m["estado"]) for m in conversa["mensagens"]] == [(chave, "enviando")]

    # Simulação (JOBS_APLICAR=0): nada sai.
    assert _enviar_fila(ambiente, cid, aplicar=False).gravados == 0 and ambiente.interagir_chamadas == []
    ctx = _enviar_fila(ambiente, cid)
    assert (ctx.gravados, ctx.erros) == (1, 0)
    m = _msg(chave)
    assert (m["status"], m["texto"], m["erro_codigo"]) == ("enviada", None, None) and m["enviada_em"] is not None
    assert ambiente.interagir_chamadas[-1]["interacao_id"] == chave

    # O job acabou de publicar: o cache (vazio) está velho mesmo sem a lista saber — relê do hub.
    assert [m["estado"] for m in mensagens.listar(cid, do_app)["mensagens"]] == ["enviada"]
    ambiente.central_responder(do_app, "Recebido, obrigado!")
    # A lista do contato ainda está em cache (60 s): a conversa vem da memória, sem gastar cota.
    antes = len(ambiente.interacoes_chamadas)
    assert [m["autor"] for m in mensagens.listar(cid, do_app)["mensagens"]] == ["voce"]
    assert len(ambiente.interacoes_chamadas) == antes
    # "Atualizar conversa": relê a lista, vê `ultima_interacao_em` novo e só então relê a conversa.
    conversa = mensagens.listar(cid, do_app, atualizar=True)
    assert len(ambiente.interacoes_chamadas) == antes + 1
    assert [(m["autor"], m["estado"]) for m in conversa["mensagens"]] == [("voce", "enviada"), ("central", "enviada")]
    mensagens.listar(cid, do_app, atualizar=True)  # nada mudou: lista relida, conversa não
    assert len(ambiente.interacoes_chamadas) == antes + 1
    assert ambiente.interacoes_chamadas and all(c == (cid, do_app) for c in ambiente.interacoes_chamadas)
    assert conversa["mensagens"][0]["texto"] == "Olá!\nSegue o que pediram."  # agora lido do CRM
    _recarregar_crm()
    assert not {i["id"]: i for i in leitura_crm.listar(cid)[0]}[do_app]["nova_resposta"]  # conversa foi aberta

    # Outro associado não lê nem escreve na conversa.
    from app.dominio.solicitacoes.maquina import SolicitacaoNaoEncontrada

    outro = _cid()
    with pytest.raises(SolicitacaoNaoEncontrada):
        mensagens.listar(outro, do_app)
    with pytest.raises(SolicitacaoNaoEncontrada):
        mensagens.enviar(outro, do_app, texto="não é minha", chave_idempotencia=str(uuid.uuid4()))


def test_enviar_valida_texto_estado_e_limites(ambiente, monkeypatch):
    from app.dominio.solicitacoes import mensagens, schemas
    from app.dominio.solicitacoes.maquina import TransicaoInvalida

    cid = _cid()
    do_app = ambiente.registro_app(cid, "duvida")
    for ruim in ("x", "meu cpf é 123.456.789-09", "<script>alert(1)</script>", "😀" * 1001):
        with pytest.raises(schemas.EntradaInvalida):
            mensagens.enviar(cid, do_app, texto=ruim, chave_idempotencia=str(uuid.uuid4()))
    with pytest.raises(schemas.EntradaInvalida):
        mensagens.enviar(cid, do_app, texto="texto bom", chave_idempotencia="6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    # Ainda não chegou ao CRM → aguardando_envio; encerrada → solicitacao_encerrada; legado aceita.
    local = _criar(cid)
    with pytest.raises(TransicaoInvalida) as e:
        mensagens.enviar(cid, local, texto="já posso escrever?", chave_idempotencia=str(uuid.uuid4()))
    assert e.value.codigo == "aguardando_envio"
    assert mensagens.listar(cid, local)["motivo_bloqueio"] == "aguardando_envio"
    ambiente.definir_estado(do_app, 1, 5)
    _recarregar_crm()
    with pytest.raises(TransicaoInvalida) as e:
        mensagens.enviar(cid, do_app, texto="ainda dá tempo?", chave_idempotencia=str(uuid.uuid4()))
    assert e.value.codigo == "solicitacao_encerrada"
    fechada = mensagens.listar(cid, do_app)
    assert (fechada["pode_enviar"], fechada["motivo_bloqueio"]) == (False, "encerrada")
    sem_tipo = ambiente.registro_app(cid, "tipo_que_o_app_inventou")
    _recarregar_crm()
    with pytest.raises(mensagens.MensagemNaoPermitida):
        mensagens.enviar(cid, sem_tipo, texto="este tipo não conversa", chave_idempotencia=str(uuid.uuid4()))

    # 1 a cada 30 s; 10 por hora.
    aberto = ambiente.registro_app(cid, "outros")
    _recarregar_crm()
    mensagens.enviar(cid, aberto, texto="primeira mensagem", chave_idempotencia=str(uuid.uuid4()))
    with pytest.raises(mensagens.LimiteMensagens) as e:
        mensagens.enviar(cid, aberto, texto="segunda, cedo demais", chave_idempotencia=str(uuid.uuid4()))
    assert 1 <= e.value.retry_after <= 30
    monkeypatch.setattr(mensagens, "INTERVALO_MIN_S", 0)
    for i in range(9):
        mensagens.enviar(cid, aberto, texto=f"mensagem número {i}", chave_idempotencia=str(uuid.uuid4()))
    with pytest.raises(mensagens.LimiteMensagens) as e:
        mensagens.enviar(cid, aberto, texto="a décima primeira", chave_idempotencia=str(uuid.uuid4()))
    assert 3500 <= e.value.retry_after <= 3600


def test_job_limite_do_titular_falha_definitiva_e_ordem(ambiente, monkeypatch):
    from app.dominio.solicitacoes import mensagens

    monkeypatch.setattr(mensagens, "INTERVALO_MIN_S", 0)
    cid = _cid()
    pai = ambiente.registro_app(cid, "duvida")
    chaves = [str(uuid.uuid4()) for _ in range(3)]
    for i, chave in enumerate(chaves):
        mensagens.enviar(cid, pai, texto=f"mensagem {i} na ordem", chave_idempotencia=chave)

    # Limite do titular: tudo do contato espera o Retry-After, sem gastar tentativa.
    ambiente.limite_titular = 1
    agora = _agora()
    ctx = _enviar_fila(ambiente, cid, agora)
    assert (ctx.gravados, ctx.erros, ctx.erro_sistemico) == (1, 0, None)
    assert _msg(chaves[0])["status"] == "enviada"
    for chave in chaves[1:]:
        m = _msg(chave)
        assert (m["status"], m["tentativas"], m["erro_codigo"]) == ("pendente", 0, "limite_titular")
        assert m["proxima_em"] >= agora + timedelta(seconds=1790) and m["texto"] is not None
    assert _enviar_fila(ambiente, cid, agora + timedelta(minutes=5)).lidos == 0

    # Passado o prazo: falha transitória na 2ª segura a 3ª (ordem dentro do pai).
    ambiente.limite_titular = None
    depois = agora + timedelta(hours=1)
    ambiente.falhar_interacoes[chaves[1]] = HubError("fonte_indisponivel")
    ctx = _enviar_fila(ambiente, cid, depois)
    assert (ctx.gravados, ctx.erros) == (0, 1)
    assert (_msg(chaves[1])["status"], _msg(chaves[1])["tentativas"]) == ("erro", 1)
    assert _msg(chaves[2])["status"] == "pendente"
    ctx = _enviar_fila(ambiente, cid, depois + timedelta(seconds=30))  # 2ª em recuo: a 3ª não passa na frente
    assert ctx.gravados == 0 and _msg(chaves[2])["status"] == "pendente"
    del ambiente.falhar_interacoes[chaves[1]]
    ctx = _enviar_fila(ambiente, cid, depois + timedelta(minutes=2))
    assert ctx.gravados == 2
    assert [m["interacao_id"] for m in ambiente.interagir_chamadas if m["registro_id"] == pai][-2:] == chaves[1:]

    # A Central fecha o registro com mensagem na fila: falha definitiva, visível na conversa, depois purgada.
    tardia = str(uuid.uuid4())
    mensagens.enviar(cid, pai, texto="escrevi antes de fecharem", chave_idempotencia=tardia)
    ambiente.definir_estado(pai, 1, 5)
    quando = depois + timedelta(hours=2)
    ctx = _enviar_fila(ambiente, cid, quando)
    assert ctx.erros == 1
    m = _msg(tardia)
    assert (m["status"], m["erro_codigo"], m["texto"]) == ("falhou", "registro_fechado", "escrevi antes de fecharem")
    from app.dominio.solicitacoes import leitura_crm

    leitura_crm.redefinir()
    assert mensagens.listar(cid, pai)["mensagens"][-1]["estado"] == "falhou"
    from app.jobs import mensagens as job_mensagens

    assert job_mensagens.purgar_falhas(quando) == 0
    with _db() as db:  # só para o teste: envelhece a linha? criada_em é imutável — a purga usa a data real
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE solicitacao_mensagem SET criada_em = :d WHERE id = :id"),
                       {"d": quando - timedelta(days=30), "id": tardia})
    assert job_mensagens.purgar_falhas(_agora() + timedelta(days=8)) >= 1
    assert (_msg(tardia)["status"], _msg(tardia)["texto"]) == ("falhou", None)


def test_job_escrita_desligada_e_erro_sistemico_nao_gastam_tentativa(ambiente, monkeypatch):
    from app.config import get_settings
    from app.dominio.solicitacoes import mensagens

    cid = _cid()
    pai = ambiente.registro_app(cid, "duvida")
    chave = str(uuid.uuid4())
    mensagens.enviar(cid, pai, texto="vai ficar esperando", chave_idempotencia=chave)

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "false")
    get_settings.cache_clear()
    ctx = _enviar_fila(ambiente, cid)
    assert ctx.erro_sistemico == "mensagens em espera: escrita no hub desligada"
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    get_settings.cache_clear()

    ambiente.falhar_interacoes[chave] = HubError("interacao_desabilitada")
    ctx = _enviar_fila(ambiente, cid)
    assert ctx.erro_sistemico == "disjuntor: interacao_desabilitada" and ctx.erros == 0
    assert (_msg(chave)["status"], _msg(chave)["tentativas"]) == ("pendente", 0)
    assert ambiente.interagir_chamadas == []


def test_grants_e_checks_das_tabelas_novas(ambiente):
    cid = _cid()
    mid, rid = str(uuid.uuid4()), str(uuid.uuid4())
    base = {"id": mid, "c": cid, "r": rid, "agora": _agora()}
    inserir = ("INSERT INTO solicitacao_mensagem (id, contact_id, registro_id, entidade, texto, status, tentativas, "
               "proxima_em, criada_em) VALUES (:id, :c, :r, 'ocorrencia', :t, :s, 0, :agora, :agora)")
    for texto_ruim, status in (("cpf 123.456.789-09", "pendente"), (None, "pendente"), ("x", "pendente"),
                               ("guardado", "enviada")):
        with pytest.raises(DBAPIError):
            with _db() as db:
                db.execute(text(inserir), {**base, "t": texto_ruim, "s": status})
    with _db() as db:
        db.execute(text(inserir), {**base, "t": "texto válido", "s": "pendente"})
    for proibido in ("UPDATE solicitacao_mensagem SET contact_id = :c WHERE id = :id",
                     "UPDATE solicitacao_mensagem SET registro_id = :c WHERE id = :id",
                     "DELETE FROM solicitacao_mensagem WHERE id = :id",
                     "UPDATE solicitacao_leitura SET registro_id = :c WHERE contact_id = :c",
                     "DELETE FROM solicitacao_leitura WHERE contact_id = :c"):
        with pytest.raises(DBAPIError):
            with _db() as db:
                db.execute(text(proibido), {"c": cid, "id": mid})


# ============================================================ sincronização
def test_sincronizacao_segue_a_conversa(ambiente):
    from app.dominio.solicitacoes import rotulos
    from app.jobs import solicitacoes

    cid = _cid()
    sid = _criar(cid, "duvida", {"mensagem": "Como emito a segunda via do boleto?"})
    _espelhar(ambiente, sid)
    reg = lambda: ambiente.solicitacao_listar(cid, 10)[0]  # noqa: E731

    ambiente.central_responder(sid, "Pode nos dizer o mês?")
    transitou, _ = solicitacoes.aplicar_registro(sid, reg(), _agora())
    assert transitou and _sol(sid)["status"] == "pendente_associado"
    with _db() as db:
        mensagem = db.execute(text(
            "SELECT mensagem_publica FROM solicitacao_evento WHERE solicitacao_id = :s ORDER BY id DESC LIMIT 1"),
            {"s": sid}).scalar()
    assert mensagem == rotulos.MENSAGEM_RESPOSTA_NA_CONVERSA

    ambiente.definir_estado(sid, 0, 100000001)  # o associado respondeu (fluxo do CRM)
    transitou, _ = solicitacoes.aplicar_registro(sid, reg(), _agora())
    assert transitou and _sol(sid)["status"] == "em_atendimento"
    with _db() as db:
        divergencias = db.execute(text(
            "SELECT COUNT(*) FROM evento_log WHERE tipo = 'solicitacao_divergencia_crm' "
            "AND JSON_UNQUOTE(JSON_EXTRACT(detalhes, '$.solicitacao_id')) = :s"), {"s": sid}).scalar()
    assert divergencias == 0


# ========================================================================= API
@pytest.fixture
def api(ambiente, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.v1 import deps, solicitacoes as rota
    from app.main import app
    from app.session_guard import Associado, require_associado
    from app.csrf import exigir_csrf

    cid = _cid()
    associado = Associado(sub="sub-" + cid[:8], contact_id=cid, nome=None, email=None, cpf_mask=None, auth_at=0,
                          amr=("pwd",))
    app.dependency_overrides[require_associado] = lambda: associado
    app.dependency_overrides[deps.contexto] = lambda: deps.Contexto(associado, cid)
    app.dependency_overrides[exigir_csrf] = lambda: None
    monkeypatch.setattr(rota, "registrar_pos_commit", lambda *a, **k: None)
    for limite in (rota.limite_escrita, rota.limite_conversa, rota.limite_mensagem):
        limite._eventos.clear()
    try:
        yield TestClient(app), cid, ambiente
    finally:
        app.dependency_overrides.clear()


def test_api_catalogo_criacao_e_conversa(api, monkeypatch):
    from app import flags
    from app.dominio.solicitacoes import catalogo

    c, cid, stub = api
    tipos = c.get("/api/v1/solicitacoes/tipos").json()["itens"]
    assert [t["codigo"] for t in tipos][:2] == ["planos_de_saude", "seguro_vida"] and len(tipos) == 15
    assert set(tipos[0]) == {"codigo", "rotulo", "grupo", "grupo_rotulo", "ordem", "responde", "carencia_meses"}

    chave = str(uuid.uuid4())
    corpo = {"tipo_servico": "seguro_carro", "campos": {"mensagem": TEXTO}, "chave_idempotencia": chave}
    r = c.post("/api/v1/solicitacoes", json=corpo)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["tipo"] == {"codigo": "seguro_carro", "rotulo": "Seguro Auto"}
    assert c.post("/api/v1/solicitacoes", json=corpo).status_code == 200  # idempotente
    outra = {**corpo, "chave_idempotencia": str(uuid.uuid4())}
    assert c.post("/api/v1/solicitacoes", json=outra).status_code == 409  # um aberto por tipo

    # Aberto pelo App no mesmo tipo → 409 entre canais; produto inativo → 422.
    stub.registro_app(cid, "seguro_pet", entidade="oportunidade")
    _recarregar_crm()
    r = c.post("/api/v1/solicitacoes", json={**outra, "tipo_servico": "seguro_pet"})
    assert (r.status_code, r.json()["erro"]) == (409, "estado_invalido")
    stub.produtos_inativos.add("b8cfc64a-6e88-e911-a968-000d3ac1b6c7")  # seguro_viagem
    catalogo.invalidar()
    r = c.post("/api/v1/solicitacoes", json={**outra, "tipo_servico": "seguro_viagem"})
    assert (r.status_code, r.json()["erro"]) == (422, "servico_indisponivel")
    assert "seguro_viagem" not in [t["codigo"] for t in c.get("/api/v1/solicitacoes/tipos").json()["itens"]]
    r = c.post("/api/v1/solicitacoes", json={**outra, "tipo_servico": "seguros"})  # legado não abre
    assert (r.status_code, r.json()["detalhes"][0]["campo"]) == (400, "tipo_servico")

    # Lista fundida e conversa.
    _espelhar(stub, sid)
    _recarregar_crm()
    lista = c.get("/api/v1/solicitacoes?situacao=andamento").json()
    assert lista["parcial"] is False and lista["proximo_cursor"] is None
    assert {i["canal"] for i in lista["itens"]} == {"app", "minha_apm"}
    r = c.get(f"/api/v1/solicitacoes/{sid}/mensagens")
    assert r.status_code == 200 and r.json()["pode_enviar"] is True and r.json()["responde"] == "apm"
    mid = str(uuid.uuid4())
    r = c.post(f"/api/v1/solicitacoes/{sid}/mensagens", json={"texto": "Qual o prazo?", "chave_idempotencia": mid})
    assert r.status_code == 202 and r.json() == {"id": mid, "autor": "voce", "texto": "Qual o prazo?",
                                                 "quando": r.json()["quando"], "estado": "enviando"}
    r = c.post(f"/api/v1/solicitacoes/{sid}/mensagens", json={"texto": "Qual o prazo?", "chave_idempotencia": mid})
    assert r.status_code == 200
    r = c.post(f"/api/v1/solicitacoes/{sid}/mensagens",
               json={"texto": "Outra, logo em seguida.", "chave_idempotencia": str(uuid.uuid4())})
    assert (r.status_code, r.json()["erro"]) == (429, "limite_mensagens") and int(r.headers["Retry-After"]) >= 1
    r = c.post(f"/api/v1/solicitacoes/{uuid.uuid4()}/mensagens",
               json={"texto": "Não existe.", "chave_idempotencia": str(uuid.uuid4())})
    assert r.status_code == 404
    stub.falhar_interacoes[sid] = HubError("interacao_desabilitada")
    assert c.get(f"/api/v1/solicitacoes/{sid}/mensagens?atualizar=true").status_code == 200  # nada mudou: cache
    from app.dominio.solicitacoes import mensagens as dominio_mensagens

    dominio_mensagens.redefinir()  # sem cache, a leitura depende do hub
    r = c.get(f"/api/v1/solicitacoes/{sid}/mensagens")
    assert (r.status_code, r.json()["erro"]) == (503, "mensagens_indisponiveis")

    # Flag desligada: rotas novas em 404 `recurso_desligado`, tipos novos recusados, lista da Onda 2.
    monkeypatch.setattr(flags, "_ler_tabela", lambda: {})
    flags.limpar_cache()
    for metodo, caminho in (("get", "/api/v1/solicitacoes/tipos"), ("get", f"/api/v1/solicitacoes/{sid}/mensagens")):
        r = getattr(c, metodo)(caminho)
        assert (r.status_code, r.json()["erro"]) == (404, "recurso_desligado")
    r = c.post(f"/api/v1/solicitacoes/{sid}/mensagens", json={"texto": "desligado", "chave_idempotencia": mid})
    assert (r.status_code, r.json()["erro"]) == (404, "recurso_desligado")
    r = c.post("/api/v1/solicitacoes", json={**outra, "tipo_servico": "duvida",
                                             "campos": {"mensagem": "com a flag desligada"}})
    assert (r.status_code, r.json()["detalhes"][0]["campo"]) == (400, "tipo_servico")
    antiga = c.get("/api/v1/solicitacoes").json()
    assert [i["id"] for i in antiga["itens"]] == [sid] and antiga["parcial"] is False
    assert antiga["itens"][0]["situacao"] is None and antiga["itens"][0]["rotulo_status"] == "Encaminhada à equipe"
    assert CANAL_APP  # (registro do App não aparece com a flag desligada: conferido acima)


def test_pode_enviar_mensagem_do_hub_manda_e_o_bloqueio_local_cede(ambiente, monkeypatch):
    """Adendo do hub de 2026-11-13: a lista diz `pode_enviar_mensagem` por registro. `false` em
    registro aberto = "encerrada pela Central"; a Central pode desbloquear, e aí o que a área
    aprendeu no 403 deixa de valer na leitura seguinte."""
    from app.dominio.solicitacoes import leitura_crm, mensagens

    monkeypatch.setattr(mensagens, "INTERVALO_MIN_S", 0)
    cid = _cid()
    rid = ambiente.registro_app(cid, "duvida")
    livre = ambiente.registro_app(cid, "outros")

    # Bloqueado pela Central, sem nenhuma tentativa de envio pela área: a coluna basta.
    ambiente.bloqueados.add(rid)
    leitura_crm.redefinir()
    por_id = {i["id"]: i for i in leitura_crm.listar(cid)[0]}
    assert not por_id[rid]["pode_enviar_mensagem"] and por_id[livre]["pode_enviar_mensagem"]
    assert por_id[rid]["situacao"] == "aberta"  # aberto, só não aceita mensagem
    assert not leitura_crm.detalhe(cid, rid)["pode_enviar_mensagem"]
    conversa = mensagens.listar(cid, rid)
    assert (conversa["pode_enviar"], conversa["motivo_bloqueio"]) == (False, "nao_permitida")
    with pytest.raises(mensagens.MensagemNaoPermitida):
        mensagens.enviar(cid, rid, texto="nem entra na fila", chave_idempotencia=str(uuid.uuid4()))

    # Desbloqueia: volta a aceitar na leitura seguinte.
    ambiente.bloqueados.discard(rid)
    leitura_crm.redefinir()
    assert leitura_crm.pai(cid, rid).pode_enviar
    # Bloqueia entre a lista (em cache, ainda `true`) e o envio: o 403 da fila vale na hora…
    chave = str(uuid.uuid4())
    mensagens.enviar(cid, rid, texto="a Central bloqueou no meio do caminho", chave_idempotencia=chave)
    ambiente.bloqueados.add(rid)
    _enviar_fila(ambiente, cid)
    assert _msg(chave)["erro_codigo"] == "interacao_nao_permitida"
    assert leitura_crm.registros_do_contato(cid).registros[rid].pode_enviar_mensagem is True  # cache antigo
    assert leitura_crm.pai(cid, rid).motivo == "nao_permitida"
    # …e, quando a Central desbloqueia, a lista nova (posterior à falha) libera de novo.
    ambiente.bloqueados.discard(rid)
    leitura_crm.redefinir()
    assert leitura_crm.pai(cid, rid).pode_enviar
    assert {i["id"]: i for i in leitura_crm.listar(cid)[0]}[rid]["pode_enviar_mensagem"]
    assert mensagens.enviar(cid, rid, texto="agora vai", chave_idempotencia=str(uuid.uuid4())).criada


def test_bloqueio_pela_central_esconde_o_envio_dali_em_diante(ambiente, monkeypatch):
    """Hub anterior ao adendo (lista sem `pode_enviar_mensagem`): a área aprende no 403
    `interacao_nao_permitida` e guarda por registro — a caixa de envio some naquele registro, só nele."""
    from app.dominio.solicitacoes import leitura_crm, mensagens

    monkeypatch.setattr(mensagens, "INTERVALO_MIN_S", 0)
    monkeypatch.setattr(ambiente, "sem_coluna_envio", True)
    cid = _cid()
    bloqueado = ambiente.registro_app(cid, "duvida")
    livre = ambiente.registro_app(cid, "outros")
    assert all(i["pode_enviar_mensagem"] for i in leitura_crm.listar(cid)[0])

    chave = str(uuid.uuid4())
    mensagens.enviar(cid, bloqueado, texto="a Central bloqueou no meio do caminho", chave_idempotencia=chave)
    ambiente.bloqueados.add(bloqueado)
    ctx = _enviar_fila(ambiente, cid)
    assert ctx.erros == 1 and (_msg(chave)["status"], _msg(chave)["erro_codigo"]) == ("falhou",
                                                                                 "interacao_nao_permitida")
    por_id = {i["id"]: i for i in leitura_crm.listar(cid)[0]}
    assert not por_id[bloqueado]["pode_enviar_mensagem"] and por_id[livre]["pode_enviar_mensagem"]
    assert not leitura_crm.detalhe(cid, bloqueado)["pode_enviar_mensagem"]
    conversa = mensagens.listar(cid, bloqueado)
    assert (conversa["pode_enviar"], conversa["motivo_bloqueio"]) == (False, "nao_permitida")
    assert conversa["mensagens"][-1]["estado"] == "falhou"
    with pytest.raises(mensagens.MensagemNaoPermitida):
        mensagens.enviar(cid, bloqueado, texto="nem entra na fila", chave_idempotencia=str(uuid.uuid4()))
    assert mensagens.enviar(cid, livre, texto="o outro registro segue", chave_idempotencia=str(uuid.uuid4())).criada


def test_conversa_pede_20_mensagens_e_cota_esgotada_degrada(ambiente):
    from app.dominio.solicitacoes import leitura_crm, mensagens

    cid = _cid()
    rid = ambiente.registro_app(cid, "duvida")
    for i in range(22):
        ambiente.central_responder(rid, f"mensagem {i} da Central")
    conversa = mensagens.listar(cid, rid)
    assert len(conversa["mensagens"]) == 20 and conversa["truncado"] is True  # limite modesto (cota por mensagem)
    assert conversa["mensagens"][-1]["texto"] == "mensagem 21 da Central"

    # Cota esgotada: lista parcial (só o que é da área) e conversa indisponível, sem insistir no hub.
    ambiente.falhar_solicitacoes[cid] = HubError("cota_esgotada", 429, retry_after=900)
    leitura_crm.redefinir()
    mensagens.redefinir()
    itens, parcial = leitura_crm.listar(cid)
    assert parcial and itens == []
    with pytest.raises(leitura_crm.FonteIndisponivel):
        mensagens.listar(cid, rid)
