"""Produção de comunicação: outbox de gatilhos e notificações no app (TI-18).

A área **produz** (REQUISITOS §3.17 RF-CM-01, §3.16 RF-NO-04): toda linha
nasce na MESMA transação da mudança de negócio que a causou — se o negócio
volta (rollback), a comunicação some junto; se comita, nada se perde. Quem
**envia** é o serviço de jobs (SMTP da área para transacionais; RD Station só
com a flag `comunicacao_outbox`).

- Idempotente pelo índice único `(gatilho, contact_id, referencia_id, canal,
  destinatario)`: a mesma causa nunca dispara duas vezes. A tentativa duplicada
  roda num SAVEPOINT e é descartada sem derrubar a transação de negócio.
- Supressão básica na produção (RF-CM-03): quem tem pedido de cancelamento
  aberto sai dos fluxos de oferta/engajamento do RD. A linha nasce
  `suprimido` (rastro de por que não saiu) e ganha `comunicacao_supressao`.
  O resto da supressão (limite semanal, consentimento, financeiro) é do job.
- Sem PII: nem e-mail, nem telefone, nem texto de marketing. Título e corpo da
  notificação vêm de rótulos fixos (app/dominio/solicitacoes/rotulos.py).

Bloqueante (SQL): só dentro de transação aberta pelo domínio.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger("area_associado.comunicacao")

GATILHOS: tuple[str, ...] = tuple(f"A{n:02d}" for n in range(1, 21))
CANAIS: tuple[str, ...] = ("email", "rd", "app", "interno")
DESTINATARIOS: tuple[str, ...] = ("associado", "central", "equipe")
REFERENCIAS: tuple[str, ...] = ("solicitacao", "beneficio", "evento", "associado", "fatura", "trilha")
MOTIVOS_SUPRESSAO: tuple[str, ...] = ("limite_semana", "financeiro", "cancelamento", "sem_consentimento",
                                      "recomendado_recente", "sem_credencial", "fato_mudou")
TIPOS_NOTIFICACAO: tuple[str, ...] = ("solicitacao_criada", "solicitacao_pendente", "solicitacao_sem_retorno",
                                      "solicitacao_concluida", "solicitacao_cancelada", "cancelamento_recebido",
                                      "beneficio_liberado", "evento", "pagamento", "novidade")

# Fluxos de oferta/engajamento (spec §12.2) que um pedido de cancelamento
# aberto suprime no RD. Transacionais (A04, A05, A06, A16, A19) nunca.
GATILHOS_OFERTA: frozenset[str] = frozenset({"A03", "A07", "A08", "A10", "A11", "A12", "A14", "A15", "A20"})

_RE_REFERENCIA = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_RE_CHAVE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_RE_LINK = re.compile(r"^/area(/[A-Za-z0-9_-]+)*/?$")
_ER_DUPLICADO = 1062


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _duplicado(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    args = getattr(orig, "args", ())
    return bool(args) and args[0] == _ER_DUPLICADO


def _inserir_idempotente(sess: Session, sql: object, params: dict[str, object]) -> int | None:
    """INSERT num SAVEPOINT: duplicata (1062) → None, sem afetar a transação.
    Qualquer outra integridade (CHECK, FK) propaga — é bug, não repetição."""
    try:
        with sess.begin_nested():
            resultado = sess.execute(sql, params)  # type: ignore[arg-type]
    except IntegrityError as exc:
        if _duplicado(exc):
            return None
        raise
    return int(resultado.lastrowid)


def _tem_cancelamento_aberto(sess: Session, contact_id: str) -> bool:
    sql = text(
        "SELECT 1 FROM solicitacao WHERE contact_id = :c AND tipo_servico = 'cancelamento_associacao' "
        "AND status IN ('criada','enviada','em_atendimento','pendente_associado') LIMIT 1"
    )
    return sess.execute(sql, {"c": contact_id}).first() is not None


def motivo_supressao(sess: Session, *, gatilho: str, contact_id: str, canal: str) -> str | None:
    """Supressão aplicada já na produção. `None` = enfileira normalmente."""
    if canal == "rd" and gatilho in GATILHOS_OFERTA and _tem_cancelamento_aberto(sess, contact_id):
        return "cancelamento"
    return None


_SQL_EVENTO = text(
    "INSERT INTO comunicacao_evento (gatilho, contact_id, referencia_tipo, referencia_id, canal, destinatario, "
    " criado_em, enviar_apos, status, supressao_motivo, atualizado_em) "
    "VALUES (:gatilho, :c, :rt, :rid, :canal, :dest, :agora, :apos, :status, :motivo, :agora)"
)
_SQL_SUPRESSAO = text(
    "INSERT INTO comunicacao_supressao (ocorrido_em, comunicacao_evento_id, contact_id, gatilho, canal, motivo) "
    "VALUES (:agora, :eid, :c, :gatilho, :canal, :motivo)"
)


def enfileirar(sess: Session, *, gatilho: str, contact_id: str, referencia_tipo: str, referencia_id: str,
               destinos: Iterable[tuple[str, str]], enviar_apos: datetime | None = None,
               agora: datetime | None = None) -> int:
    """Grava um gatilho para cada `(canal, destinatario)`. Devolve quantas linhas
    NOVAS nasceram (repetição da mesma causa = 0). Entrada fora do catálogo é
    bug do chamador: `ValueError` (a transação de negócio volta inteira)."""
    if gatilho not in GATILHOS:
        raise ValueError(f"gatilho desconhecido: {gatilho!r}")
    if referencia_tipo not in REFERENCIAS or not _RE_REFERENCIA.match(referencia_id or ""):
        raise ValueError("referência inválida")
    agora = agora or _agora()
    apos = enviar_apos or agora
    novas = 0
    vistos: set[tuple[str, str]] = set()
    for canal, destinatario in destinos:
        if canal not in CANAIS or destinatario not in DESTINATARIOS:
            raise ValueError(f"destino inválido: {canal!r}/{destinatario!r}")
        if (canal, destinatario) in vistos:
            continue
        vistos.add((canal, destinatario))
        motivo = motivo_supressao(sess, gatilho=gatilho, contact_id=contact_id, canal=canal)
        eid = _inserir_idempotente(sess, _SQL_EVENTO, {
            "gatilho": gatilho, "c": contact_id, "rt": referencia_tipo, "rid": referencia_id, "canal": canal,
            "dest": destinatario, "agora": agora, "apos": apos,
            "status": "suprimido" if motivo else "pendente", "motivo": motivo,
        })
        if eid is None:
            continue
        novas += 1
        if motivo:
            sess.execute(_SQL_SUPRESSAO, {"agora": agora, "eid": eid, "c": contact_id, "gatilho": gatilho,
                                          "canal": canal, "motivo": motivo})
    return novas


def suprimir_pendentes(sess: Session, *, referencia_tipo: str, referencia_id: str, motivo: str,
                       gatilhos: Iterable[str] | None = None, agora: datetime | None = None) -> int:
    """O fato mudou (ex.: solicitação cancelada): o que ainda não saiu não sai
    mais (RF-SO-12). Marca `suprimido` e registra cada supressão. Devolve quantas."""
    if motivo not in MOTIVOS_SUPRESSAO:
        raise ValueError(f"motivo de supressão desconhecido: {motivo!r}")
    agora = agora or _agora()
    filtro_gatilho = ""
    params: dict[str, object] = {"rt": referencia_tipo, "rid": referencia_id}
    lista = sorted(set(gatilhos)) if gatilhos is not None else None
    if lista is not None:
        if not lista:
            return 0
        if any(g not in GATILHOS for g in lista):
            raise ValueError("gatilho desconhecido")
        filtro_gatilho = " AND gatilho IN :gatilhos"
        params["gatilhos"] = lista
    sql = text(
        "SELECT id, contact_id, gatilho, canal FROM comunicacao_evento "
        "WHERE referencia_tipo = :rt AND referencia_id = :rid AND status IN ('pendente','erro')"
        + filtro_gatilho + " FOR UPDATE"
    )
    if lista is not None:
        sql = sql.bindparams(bindparam("gatilhos", expanding=True))
    linhas = sess.execute(sql, params).all()
    for r in linhas:
        sess.execute(text(
            "UPDATE comunicacao_evento SET status = 'suprimido', supressao_motivo = :motivo, atualizado_em = :agora "
            "WHERE id = :id AND status IN ('pendente','erro')"
        ), {"motivo": motivo, "agora": agora, "id": r.id})
        sess.execute(_SQL_SUPRESSAO, {"agora": agora, "eid": r.id, "c": r.contact_id, "gatilho": r.gatilho,
                                      "canal": r.canal, "motivo": motivo})
    return len(linhas)


_SQL_NOTIFICACAO = text(
    "INSERT INTO notificacao (contact_id, tipo, chave, referencia_tipo, referencia_id, titulo, corpo, link, criada_em) "
    "VALUES (:c, :tipo, :chave, :rt, :rid, :titulo, :corpo, :link, :agora)"
)


def notificar(sess: Session, *, contact_id: str, tipo: str, chave: str, titulo: str, corpo: str | None = None,
              link: str | None = None, referencia_tipo: str | None = None, referencia_id: str | None = None,
              agora: datetime | None = None) -> bool:
    """Notificação no app, idempotente por `(contact_id, chave)`. True = nova."""
    if tipo not in TIPOS_NOTIFICACAO:
        raise ValueError(f"tipo de notificação desconhecido: {tipo!r}")
    if not _RE_CHAVE.match(chave or ""):
        raise ValueError("chave de notificação inválida")
    if link is not None and (not _RE_LINK.match(link) or ".." in link):
        raise ValueError("link de notificação fora da área")
    if referencia_tipo is not None and referencia_tipo not in REFERENCIAS:
        raise ValueError("referência inválida")
    if referencia_id is not None and not _RE_REFERENCIA.match(referencia_id):
        raise ValueError("referência inválida")
    titulo = " ".join(titulo.split())[:120]
    corpo = " ".join(corpo.split())[:300] if corpo else None
    if not titulo:
        raise ValueError("título vazio")
    return _inserir_idempotente(sess, _SQL_NOTIFICACAO, {
        "c": contact_id, "tipo": tipo, "chave": chave, "rt": referencia_tipo, "rid": referencia_id,
        "titulo": titulo, "corpo": corpo, "link": link, "agora": agora or _agora(),
    }) is not None


_SQL_LIGACAO = text(
    "INSERT INTO fila_ligacao (contact_id, motivo, referencia_tipo, referencia_id, criada_em) "
    "VALUES (:c, :motivo, 'solicitacao', :rid, :agora)"
)


def pedir_ligacao(sess: Session, *, contact_id: str, motivo: str, solicitacao_id: str,
                  agora: datetime | None = None) -> bool:
    """Item na fila de ligações da Central (só INSERT; o resultado é do backoffice)."""
    if motivo not in ("sem_retorno_2", "cancelamento_conversa"):
        raise ValueError(f"motivo de ligação desconhecido: {motivo!r}")
    return _inserir_idempotente(sess, _SQL_LIGACAO, {
        "c": contact_id, "motivo": motivo, "rid": solicitacao_id, "agora": agora or _agora(),
    }) is not None
