"""A `sql/015` (colunas do espelho por incident/opportunity, ADR-0023) já foi aplicada?

O operador aplica a migração com a área no ar: até lá a API devolve `protocolo: null`
e o espelho fica parado (o job registra e espera, sem gastar tentativa). Presença fica
em cache para sempre (coluna não some); ausência ou falha de leitura, por 60 s.
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("area_associado.solicitacoes.esquema")

COLUNAS_015 = ("crm_entidade", "crm_protocolo", "crm_estado", "crm_status", "crm_consultado_em")
_TTL_AUSENTE = 60.0
_lock = threading.Lock()
_estado: tuple[bool, float] | None = None  # (presentes, expira_em monotônico)


def _sessao():
    from ...database import session_scope  # import tardio: testes substituem

    return session_scope()


def colunas_crm_presentes() -> bool:
    global _estado
    agora = time.monotonic()
    with _lock:
        if _estado is not None and (_estado[0] or _estado[1] > agora):
            return _estado[0]
    try:
        with _sessao() as db:
            total = db.execute(text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'solicitacao' AND COLUMN_NAME IN :colunas"
            ).bindparams(bindparam("colunas", expanding=True)), {"colunas": list(COLUNAS_015)}).scalar()
        presentes = int(total or 0) == len(COLUNAS_015)
    except SQLAlchemyError as exc:
        logger.error("solicitações: conferência da sql/015 falhou (%s)", type(exc).__name__)
        presentes = False
    if not presentes:
        logger.info("solicitações: sql/015 ausente — espelho no CRM parado, protocolo indisponível")
    with _lock:
        _estado = (presentes, agora + _TTL_AUSENTE)
    return presentes


TABELAS_016 = ("solicitacao_mensagem", "solicitacao_leitura")
_estado_016: tuple[bool, float] | None = None


def paridade_presente() -> bool:
    """A `sql/016` (outbox de mensagens, leitura e tipos do catálogo comum, ADR-0024) já
    foi aplicada? Mesmo cache das colunas da 015: presença para sempre, ausência por 60 s."""
    global _estado_016
    agora = time.monotonic()
    with _lock:
        if _estado_016 is not None and (_estado_016[0] or _estado_016[1] > agora):
            return _estado_016[0]
    try:
        with _sessao() as db:
            total = db.execute(text(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME IN :tabelas"
            ).bindparams(bindparam("tabelas", expanding=True)), {"tabelas": list(TABELAS_016)}).scalar()
        presente = int(total or 0) == len(TABELAS_016)
    except SQLAlchemyError as exc:
        logger.error("solicitações: conferência da sql/016 falhou (%s)", type(exc).__name__)
        presente = False
    with _lock:
        _estado_016 = (presente, agora + _TTL_AUSENTE)
    return presente


def paridade_ativa() -> bool:
    """Catálogo comum, lista dos dois canais e conversa: flag `solicitacoes_crm` ligada
    E migrações 015/016 aplicadas. Qualquer dúvida = desligado (comportamento da Onda 2)."""
    from ... import flags  # import tardio: evita ciclo com config em testes

    return flags.ligada("solicitacoes_crm") and colunas_crm_presentes() and paridade_presente()


def redefinir() -> None:
    """Testes: esquece o cache."""
    global _estado, _estado_016
    with _lock:
        _estado = None
        _estado_016 = None
