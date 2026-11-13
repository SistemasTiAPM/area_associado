"""Casos de uso das solicitações do associado (RF-SO-01..15, RF-AJ-03/04, RF-FI-04).

Toda escrita é UMA transação: regra de negócio + `solicitacao` +
`solicitacao_evento` + notificação + outbox (+ fila de ligação). Se qualquer
parte falha, nada fica (session_scope faz o rollback). `evento_uso` e
`evento_log` ficam com a rota, DEPOIS do commit (regra 20).

Isolamento: toda leitura e escrita do associado filtra por `contact_id` da
sessão; id de outro associado é indistinguível de id inexistente (404).

Nada daqui chama o mcp_hub: o espelho no CRM é do serviço de jobs, pela
outbox `crm_*` (ADR-0003). Em especial o pedido de cancelamento da associação
**nunca** escreve no CRM — quem cancela é a APM (RF-AJ-04).

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import base64
import binascii
import calendar
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .. import comunicacao, limites_negocio
from ..ajuda import contato_resumo
from . import catalogo_crm, esquema, maquina, parametros, rotulos, schemas
from .maquina import SolicitacaoNaoEncontrada, TransicaoInvalida

logger = logging.getLogger("area_associado.solicitacoes")

LIMITE_PADRAO = 20
LIMITE_MAX = 20
CARENCIA_AMB_MESES = 1  # RF-FI-04: AMB para prova de título só após 1 mês de filiação
_ER_DUPLICADO = 1062
_RE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_RE_CURSOR_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

# Destino declarado no "conteúdo enviado" dos serviços da APM (tipo 3).
DESTINO_SERVICO_APM = "central_apm"


class NaoElegivel(Exception):
    """409 `nao_elegivel` com a data em que libera."""

    def __init__(self, libera_em: date, mensagem: str) -> None:
        super().__init__("nao_elegivel")
        self.libera_em = libera_em
        self.mensagem = mensagem


class CursorInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Criacao:
    solicitacao: dict[str, Any]
    criada: bool  # False = repetição da mesma chave de idempotência (200)
    id: str


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sessao():
    from ...database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


def _iso(valor: datetime | None) -> str | None:
    if valor is None:
        return None
    return valor.replace(tzinfo=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def somar_meses(d: date, meses: int) -> date:
    """`d` + `meses` meses de calendário; dia inexistente vira o último do mês."""
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def validar_id(solicitacao_id: str) -> str:
    """Id inválido é indistinguível de inexistente (404), sem consulta ao banco."""
    sid = solicitacao_id.strip().lower() if isinstance(solicitacao_id, str) else ""
    if not _RE_UUID.match(sid):
        raise SolicitacaoNaoEncontrada()
    return sid


# ------------------------------------------------------------- cursor
def codificar_cursor(atualizada_em: datetime, sid: str) -> str:
    bruto = json.dumps([atualizada_em.isoformat(timespec="microseconds"), sid], separators=(",", ":"))
    return base64.urlsafe_b64encode(bruto.encode()).decode().rstrip("=")


def decodificar_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        if len(cursor) > 200:
            raise ValueError
        bruto = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        quando, sid = json.loads(bruto)
        if not isinstance(quando, str) or not isinstance(sid, str) or not _RE_CURSOR_ID.match(sid):
            raise ValueError
        return datetime.fromisoformat(quando).replace(tzinfo=None), sid
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CursorInvalido("cursor inválido") from exc


# ------------------------------------------------------------- montagem
_COLUNAS_BASE = (
    "id, tipo_servico, beneficio_id, tipo_ativacao, status, enviada_em, prazo_retorno_dias, sem_retorno_desde, "
    "dados, avaliacao_nota, avaliacao_comentario, avaliada_em, criada_em, atualizada_em, concluida_em, crm_id"
)


def _colunas() -> str:
    """`crm_protocolo` só existe depois da sql/015 (ADR-0023)."""
    return _COLUNAS_BASE + (", crm_protocolo" if esquema.colunas_crm_presentes() else ", NULL AS crm_protocolo")


def _prazo_em(linha: Any) -> str | None:
    if linha.enviada_em is None or linha.status in rotulos.TERMINAIS:
        return None
    fim = (linha.enviada_em + timedelta(days=int(linha.prazo_retorno_dias))).replace(tzinfo=timezone.utc)
    return fim.astimezone(schemas.FUSO).date().isoformat()


def _pode_avaliar(linha: Any, prazo_avaliacao_dias: int, agora: datetime) -> bool:
    return (linha.status in rotulos.CONCLUIDAS and linha.avaliada_em is None and linha.concluida_em is not None
            and linha.concluida_em + timedelta(days=prazo_avaliacao_dias) >= agora)


def resumo(linha: Any, *, contato: dict[str, str] | None, prazo_avaliacao_dias: int,
           agora: datetime) -> dict[str, Any]:
    """`Resumo` do contrato da Onda 2. Nunca `contact_id` nem campos internos; do CRM, só o
    protocolo (que o associado usa com a Central) e se o pedido já está lá (ADR-0023)."""
    tipo_codigo = linha.tipo_servico or "beneficio"
    na_central = linha.crm_id is not None
    return {
        "id": linha.id,
        "tipo": {"codigo": tipo_codigo, "rotulo": rotulos.rotulo_tipo(linha.tipo_servico)},
        # Catálogo como dado só na Fase 4 (sql/015): sem ficha, não há slug/título a mostrar.
        "beneficio": None,
        "status": linha.status,
        "rotulo_status": rotulos.rotulo_status(linha.status, linha.tipo_ativacao),
        "aguardando_parceiro": linha.sem_retorno_desde is not None,
        "prazo_em": _prazo_em(linha),
        "contato": contato,
        "criada_em": _iso(linha.criada_em),
        "atualizada_em": _iso(linha.atualizada_em),
        "protocolo": linha.crm_protocolo,
        "na_central": na_central,
        "pode_cancelar": maquina.pode_cancelar_associado(linha.status, na_central),
        "pode_responder": maquina.pode_responder_associado(linha.status, na_central),
        "pode_avaliar": _pode_avaliar(linha, prazo_avaliacao_dias, agora),
    }


def _dados(linha: Any) -> dict[str, Any]:
    dados = linha.dados
    if isinstance(dados, (str, bytes)):
        dados = json.loads(dados)
    return dados if isinstance(dados, dict) else {}


def _linha_do_tempo(db: Session, sid: str, tipo_ativacao: int | None) -> list[dict[str, Any]]:
    eventos = db.execute(text(
        "SELECT evento, para_status, ator, mensagem_publica, ocorrido_em FROM solicitacao_evento "
        "WHERE solicitacao_id = :s AND evento <> 'avaliacao' ORDER BY ocorrido_em, id"
    ), {"s": sid}).all()
    return [{
        "quando": _iso(e.ocorrido_em),
        "status": e.para_status,
        "rotulo": rotulos.rotulo_evento(e.evento, e.para_status, tipo_ativacao),
        "ator": rotulos.ATOR_PUBLICO.get(e.ator, "sistema"),
        # Só a mensagem PÚBLICA: justificativa, usuário interno e conteúdo enviado nunca saem.
        "mensagem": e.mensagem_publica,
    } for e in eventos]


def _detalhe(db: Session, contact_id: str, sid: str, *, contato: dict[str, str] | None,
             agora: datetime) -> dict[str, Any]:
    linha = db.execute(text(f"SELECT {_colunas()} FROM solicitacao WHERE id = :s AND contact_id = :c"),
                       {"s": sid, "c": contact_id}).first()
    if linha is None:
        raise SolicitacaoNaoEncontrada()
    prazo_avaliacao = parametros.inteiro(db, "avaliacao_prazo_dias")
    saida = resumo(linha, contato=contato, prazo_avaliacao_dias=prazo_avaliacao, agora=agora)
    saida["campos"] = schemas.campos_publicos(linha.tipo_servico, _dados(linha))
    saida["linha_do_tempo"] = _linha_do_tempo(db, sid, linha.tipo_ativacao)
    saida["avaliacao"] = None if linha.avaliada_em is None else {
        "nota": int(linha.avaliacao_nota),
        "comentario": linha.avaliacao_comentario,
        "avaliada_em": _iso(linha.avaliada_em),
    }
    return saida


# --------------------------------------------------------------- leitura
def listar(contact_id: str, *, situacao: str | None = None, cursor: str | None = None,
           limite: int = LIMITE_PADRAO) -> tuple[list[dict[str, Any]], str | None]:
    """Página de `Resumo` por última atualização (desc). `situacao`:
    `andamento` (não terminais), `encerradas` (terminais) ou None (todas)."""
    limite = max(1, min(int(limite), LIMITE_MAX))
    condicoes = ["contact_id = :c"]
    params: dict[str, Any] = {"c": contact_id, "n": limite + 1}
    expandir = []
    if situacao is not None:
        condicoes.append("status IN :st")
        params["st"] = list(rotulos.NAO_TERMINAIS if situacao == "andamento" else sorted(rotulos.TERMINAIS))
        expandir.append(bindparam("st", expanding=True))
    if cursor:
        quando, ultimo = decodificar_cursor(cursor)
        condicoes.append("(atualizada_em < :t OR (atualizada_em = :t AND id < :u))")
        params.update(t=quando, u=ultimo)
    sql = text(f"SELECT {_colunas()} FROM solicitacao WHERE " + " AND ".join(condicoes)
               + " ORDER BY atualizada_em DESC, id DESC LIMIT :n")
    if expandir:
        sql = sql.bindparams(*expandir)
    contato = contato_resumo()
    agora = _agora()
    with _sessao() as db:
        linhas = db.execute(sql, params).all()
        prazo_avaliacao = parametros.inteiro(db, "avaliacao_prazo_dias")
    pagina = linhas[:limite]
    itens = [resumo(r, contato=contato, prazo_avaliacao_dias=prazo_avaliacao, agora=agora) for r in pagina]
    proximo = codificar_cursor(pagina[-1].atualizada_em, pagina[-1].id) if len(linhas) > limite else None
    return itens, proximo


def detalhe(contact_id: str, solicitacao_id: str) -> dict[str, Any]:
    sid = validar_id(solicitacao_id)
    contato = contato_resumo()
    with _sessao() as db:
        return _detalhe(db, contact_id, sid, contato=contato, agora=_agora())


def contar_aguardando(contact_id: str | None) -> int:
    """Contador do menu (RF-SO-07). Nunca lança: falha = 0 (o menu não depende disto)."""
    if not contact_id:
        return 0
    try:
        with _sessao() as db:
            return int(db.execute(text(
                "SELECT COUNT(*) FROM solicitacao WHERE contact_id = :c AND status = 'pendente_associado'"
            ), {"c": contact_id}).scalar_one())
    except SQLAlchemyError as exc:
        logger.error("solicitacoes: contagem de pendentes falhou (%s)", type(exc).__name__)
        return 0


# ---------------------------------------------------------------- criação
_MSG_UNICO: dict[str, str] = {
    "declaracao_associado": "Já existe um pedido desta declaração em andamento.",
    "alteracao_cadastro": "Já existe um pedido de alteração em andamento para um desses campos.",
    "cancelamento_associacao": "Você já tem um pedido de cancelamento em andamento.",
}
_MSG_UNICO_PADRAO = "Já existe uma solicitação deste tipo em andamento."


def _data_filiacao(db: Session, contact_id: str) -> date | None:
    valor = db.execute(text("SELECT data_filiacao FROM associado_perfil WHERE contact_id = :c"),
                       {"c": contact_id}).scalar()
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def exigir_elegibilidade(db: Session, contact_id: str, tipo_servico: str, campos: dict[str, Any],
                         hoje: date) -> None:
    """Carências: declaração AMB (RF-FI-04), 1 mês desde a filiação; tipos do catálogo
    comum com o App (ADR-0024), os mesmos meses do App (`catalogo_crm.TipoCrm.carencia_meses`).

    Sem data de filiação no cache (não deveria acontecer: vem do IdP no login)
    a área NÃO bloqueia — o pedido é avaliado por uma pessoa da Central, que
    confere no CRM; bloquear aqui recusaria quem tem direito."""
    if tipo_servico in catalogo_crm.TIPOS_NOVOS:
        tipo = catalogo_crm.TIPOS_CRM[tipo_servico]
        if tipo.carencia_meses <= 0:
            return
        filiacao = _data_filiacao(db, contact_id)
        if filiacao is None:
            logger.warning("solicitacoes: %s sem data de filiação no cache; segue para a APM", tipo_servico)
            return
        libera = somar_meses(filiacao, tipo.carencia_meses)
        if hoje < libera:
            raise NaoElegivel(libera, f"{tipo.rotulo} fica disponível a partir de {libera:%d/%m/%Y}, "
                                      f"{tipo.carencia_meses} meses depois da filiação.")
        return
    if tipo_servico != "declaracao_associado" or campos.get("finalidade") != "amb_prova_titulo":
        return
    filiacao = _data_filiacao(db, contact_id)
    if filiacao is None:
        logger.warning("solicitacoes: declaração AMB sem data de filiação no cache; segue para a Central")
        return
    libera = somar_meses(filiacao, CARENCIA_AMB_MESES)
    if hoje < libera:
        raise NaoElegivel(libera, f"A declaração para a AMB fica disponível a partir de {libera:%d/%m/%Y}, "
                                  "1 mês depois da filiação.")


def _conflito(tipo_servico: str, campos: dict[str, Any]):
    if tipo_servico == "outro":
        return None  # sem unicidade: limitado por contagem (5/24 h)
    if tipo_servico == "declaracao_associado":
        return lambda dados: dados.get("finalidade") == campos.get("finalidade")
    if tipo_servico == "alteracao_cadastro":
        novos = set(campos.get("alteracoes") or {})
        return lambda dados: bool(novos & set((dados.get("alteracoes") or {}) if isinstance(
            dados.get("alteracoes"), dict) else {}))
    return lambda dados: True  # demais: 1 não terminal por tipo


def _por_chave(db: Session, contact_id: str, chave: str) -> Any:
    return db.execute(text(
        "SELECT id, tipo_servico FROM solicitacao WHERE contact_id = :c AND chave_idempotencia = :k"
    ), {"c": contact_id, "k": chave}).first()


_SQL_INSERIR = text(
    "INSERT INTO solicitacao (id, contact_id, sub_hash, tipo_servico, tipo_ativacao, canal_envio, prazo_retorno_dias, "
    " status, dados, chave_idempotencia, crm_sync, crm_proxima_em, criada_em, atualizada_em) "
    "VALUES (:id, :c, :sub_hash, :tipo, 3, 'crm', :prazo, 'criada', :dados, :chave, 'pendente', :crm_em, "
    " :agora, :agora)"
)


def _repeticao(existente: Any, tipo_servico: str) -> None:
    if existente.tipo_servico != tipo_servico:
        raise TransicaoInvalida("estado_invalido", "Esta chave já foi usada em outra solicitação. Recarregue a página.")


def criar(*, contact_id: str, sub_hash: str, tipo_servico: str, campos: dict[str, Any], chave_idempotencia: str,
          request_id: str | None = None) -> Criacao:
    """Cria (201) ou devolve a da mesma chave (200). `campos` JÁ validados por
    `schemas.validar`. Levanta `NaoElegivel`, `PedidoAbertoExistente`,
    `LimiteNegocioExcedido` ou `TransicaoInvalida` (chave reaproveitada em outro tipo)."""
    chave = chave_idempotencia.lower()
    if not _RE_UUID.match(chave):
        raise schemas.EntradaInvalida([{"campo": "chave_idempotencia", "mensagem": "deve ser um UUID"}])
    if tipo_servico not in schemas.SCHEMAS:
        raise schemas.EntradaInvalida([{"campo": "tipo_servico", "mensagem": "tipo de solicitação inválido"}])
    contato = contato_resumo()
    agora = _agora()
    with _sessao() as db:
        # Serializa as criações do associado (unicidade e teto exatos, ADR-0020).
        limites_negocio.bloquear_associado(db, contact_id)
        existente = _por_chave(db, contact_id, chave)
        if existente is not None:
            _repeticao(existente, tipo_servico)
            return Criacao(_detalhe(db, contact_id, existente.id, contato=contato, agora=agora), False, existente.id)

        exigir_elegibilidade(db, contact_id, tipo_servico, campos, schemas.hoje_sp())
        conflita = _conflito(tipo_servico, campos)
        if conflita is not None:
            limites_negocio.exigir_unico_aberto(db, contact_id=contact_id, tipo_servico=tipo_servico,
                                                conflita=conflita,
                                                mensagem=_MSG_UNICO.get(tipo_servico, _MSG_UNICO_PADRAO))
        limites_negocio.exigir_abaixo_do_teto(db, contact_id=contact_id, tipo_servico=tipo_servico, agora=agora)

        prazo = parametros.inteiro(db, "prazo_retorno_padrao_dias")
        cancelamento = tipo_servico == "cancelamento_associacao"
        # Janela de arrependimento: o espelho no CRM só sai depois dela (RF-AJ-04).
        crm_em = agora + timedelta(hours=parametros.inteiro(db, "cancelamento_janela_horas")) if cancelamento \
            else agora
        sid = str(uuid.uuid4())
        dados_json = schemas.serializar(campos)
        try:
            with db.begin_nested():
                db.execute(_SQL_INSERIR, {
                    "id": sid, "c": contact_id, "sub_hash": sub_hash, "tipo": tipo_servico, "prazo": prazo,
                    "dados": dados_json, "chave": chave, "crm_em": crm_em, "agora": agora,
                })
        except IntegrityError as exc:
            orig = getattr(exc, "orig", None)
            if not (getattr(orig, "args", None) and orig.args[0] == _ER_DUPLICADO):
                raise
            existente = _por_chave(db, contact_id, chave)  # corrida sem a linha de `associado`
            if existente is None:
                raise
            _repeticao(existente, tipo_servico)
            return Criacao(_detalhe(db, contact_id, existente.id, contato=contato, agora=agora), False, existente.id)

        maquina.registrar_evento(
            db, solicitacao_id=sid, evento="criacao", de=None, para="criada", ator="associado", origem="ui",
            agora=agora, request_id=request_id,
            conteudo_enviado={"campos": sorted(campos), "sha256": schemas.sha256_conteudo(campos),
                              "destino": DESTINO_SERVICO_APM, "canal": "crm"})
        _efeitos_criacao(db, contact_id=contact_id, sid=sid, tipo_servico=tipo_servico, campos=campos,
                         prazo=prazo, agora=agora)
        return Criacao(_detalhe(db, contact_id, sid, contato=contato, agora=agora), True, sid)


def _efeitos_criacao(db: Session, *, contact_id: str, sid: str, tipo_servico: str, campos: dict[str, Any],
                     prazo: int, agora: datetime) -> None:
    """Notificação + outbox (+ fila de ligação) na MESMA transação da criação."""
    link = f"/area/solicitacoes/{sid}"
    tipo = rotulos.rotulo_tipo(tipo_servico)
    if tipo_servico == "cancelamento_associacao":
        comunicacao.notificar(
            db, contact_id=contact_id, tipo="cancelamento_recebido", chave=f"A16:{sid}",
            titulo="Recebemos seu pedido de cancelamento",
            corpo="A Central de Relacionamento vai entrar em contato. Até lá, sua associação continua ativa.",
            link=link, referencia_tipo="solicitacao", referencia_id=sid, agora=agora)
        comunicacao.enfileirar(db, gatilho="A16", contact_id=contact_id, referencia_tipo="solicitacao",
                               referencia_id=sid,
                               destinos=[("email", "associado"), ("interno", "central"), ("rd", "associado")],
                               agora=agora)
        if campos.get("quer_conversa") is True:
            comunicacao.pedir_ligacao(db, contact_id=contact_id, motivo="cancelamento_conversa",
                                      solicitacao_id=sid, agora=agora)
        return
    comunicacao.notificar(
        db, contact_id=contact_id, tipo="solicitacao_criada", chave=f"A04:{sid}",
        titulo="Recebemos sua solicitação", corpo=f"{tipo}. Retorno em até {prazo} dias após o encaminhamento.",
        link=link, referencia_tipo="solicitacao", referencia_id=sid, agora=agora)
    comunicacao.enfileirar(db, gatilho="A04", contact_id=contact_id, referencia_tipo="solicitacao",
                           referencia_id=sid, destinos=[("email", "associado"), ("rd", "associado")], agora=agora)


# ------------------------------------------------------- ações do associado
def cancelar(contact_id: str, solicitacao_id: str, *, motivo: str | None,
             request_id: str | None = None) -> tuple[dict[str, Any], maquina.Resultado]:
    sid = validar_id(solicitacao_id)
    contato = contato_resumo()
    agora = _agora()
    with _sessao() as db:
        r = maquina.transitar(db, solicitacao_id=sid, contact_id=contact_id, para="cancelada", ator="associado",
                              origem="ui", cancel_motivo=motivo, request_id=request_id, agora=agora)
        return _detalhe(db, contact_id, sid, contato=contato, agora=agora), r


def responder(contact_id: str, solicitacao_id: str, *, texto_resposta: str,
              request_id: str | None = None) -> tuple[dict[str, Any], maquina.Resultado]:
    sid = validar_id(solicitacao_id)
    contato = contato_resumo()
    agora = _agora()
    with _sessao() as db:
        r = maquina.transitar(db, solicitacao_id=sid, contact_id=contact_id, para="em_atendimento",
                              ator="associado", origem="ui", mensagem=texto_resposta, request_id=request_id,
                              agora=agora)
        return _detalhe(db, contact_id, sid, contato=contato, agora=agora), r


def avaliar(contact_id: str, solicitacao_id: str, *, nota: int, comentario: str | None,
            request_id: str | None = None) -> dict[str, Any]:
    """Uma vez, 0–10, só concluída, até `avaliacao_prazo_dias` após `concluida_em` (RF-SO-10)."""
    if isinstance(nota, bool) or not isinstance(nota, int) or not 0 <= nota <= 10:
        raise schemas.EntradaInvalida([{"campo": "nota", "mensagem": "de 0 a 10"}])
    sid = validar_id(solicitacao_id)
    contato = contato_resumo()
    agora = _agora()
    with _sessao() as db:
        linha = db.execute(text(
            "SELECT status, avaliada_em, concluida_em FROM solicitacao WHERE id = :s AND contact_id = :c FOR UPDATE"
        ), {"s": sid, "c": contact_id}).first()
        if linha is None:
            raise SolicitacaoNaoEncontrada()
        if linha.status not in rotulos.CONCLUIDAS:
            raise TransicaoInvalida("estado_invalido", "Só dá para avaliar uma solicitação concluída.")
        if linha.avaliada_em is not None:
            raise TransicaoInvalida("ja_avaliada", "Esta solicitação já foi avaliada.")
        prazo = parametros.inteiro(db, "avaliacao_prazo_dias")
        if linha.concluida_em is None or linha.concluida_em + timedelta(days=prazo) < agora:
            raise TransicaoInvalida("prazo_expirado", "O prazo para avaliar esta solicitação terminou.")
        afetadas = db.execute(text(
            "UPDATE solicitacao SET avaliacao_nota = :n, avaliacao_comentario = :com, avaliada_em = :agora, "
            " atualizada_em = :agora "
            "WHERE id = :s AND contact_id = :c AND avaliada_em IS NULL "
            " AND status IN ('concluida_positiva','concluida_negativa')"
        ), {"n": nota, "com": comentario, "agora": agora, "s": sid, "c": contact_id}).rowcount
        if afetadas != 1:
            raise TransicaoInvalida("ja_avaliada", "Esta solicitação já foi avaliada.")
        maquina.registrar_evento(db, solicitacao_id=sid, evento="avaliacao", de=None, para=linha.status,
                                 ator="associado", origem="ui", agora=agora, request_id=request_id)
        return _detalhe(db, contact_id, sid, contato=contato, agora=agora)
