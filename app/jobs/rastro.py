"""Leitura do rastro `job_execucao` para o web (`/db-health`) e para o
`scripts/alertas.sh` — só SELECT, nunca lança, sem dado pessoal.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("area_associado.jobs.rastro")

_SQL_EXISTE = text(
    "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'job_execucao'"
)
_SQL_ULTIMAS_OK = text(
    "SELECT job, MAX(terminado_em) AS ultima FROM job_execucao WHERE status = 'ok' GROUP BY job"
)
_SQL_EVENTOS_24H = text(
    "SELECT tipo, COUNT(*) AS n FROM evento_log WHERE ocorrido_em >= :desde AND severidade = 'erro' "
    "AND rota LIKE :prefixo GROUP BY tipo"
)
_SQL_RESUMO_24H = text(
    "SELECT job, SUM(status = 'erro') AS erros, SUM(status = 'abortado') AS abortados, COUNT(*) AS execucoes "
    "FROM job_execucao WHERE iniciado_em >= :desde GROUP BY job"
)


def _iso(valor: datetime | None) -> str | None:
    return f"{valor.isoformat(timespec='seconds')}Z" if valor else None


def ultimas_execucoes_ok() -> dict[str, str | None] | str:
    """`{job: "AAAA-MM-DDTHH:MM:SSZ"}` (UTC) da última execução ok de cada job;
    `"n/a"` sem a sql/011; `"indisponivel"` com o banco fora."""
    from ..database import session_scope

    try:
        with session_scope() as db:
            if not db.execute(_SQL_EXISTE).scalar():
                return "n/a"
            return {str(r.job): _iso(r.ultima) for r in db.execute(_SQL_ULTIMAS_OK)}
    except SQLAlchemyError as exc:
        logger.error("rastro: leitura de job_execucao falhou (%s)", type(exc).__name__)
        return "indisponivel"


def estado(agora: datetime | None = None) -> dict[str, Any]:
    """Visão para alertas: por job da tabela, última ok, atraso, erros/abortos em 24 h.
    `ativo` = houve qualquer execução nas últimas 24 h (serviço ligado);
    `eventos_erro_24h` = contagem por tipo do `evento_log` de erro gravado pelos jobs."""
    from ..database import session_scope
    from .registro import jobs

    agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
    with session_scope() as db:
        if not db.execute(_SQL_EXISTE).scalar():
            return {"tabela": False, "ativo": False, "jobs": []}
        ultimas = {str(r.job): r.ultima for r in db.execute(_SQL_ULTIMAS_OK)}
        resumo = {str(r.job): r for r in db.execute(_SQL_RESUMO_24H, {"desde": agora - timedelta(days=1)})}
        eventos = {str(r.tipo): int(r.n) for r in db.execute(_SQL_EVENTOS_24H, {
            "desde": agora - timedelta(days=1), "prefixo": "job:%"})}
    itens = []
    for job in jobs():
        ultima = ultimas.get(job.nome)
        limite = timedelta(seconds=job.quando.atraso_maximo_s)
        r = resumo.get(job.nome)
        itens.append({
            "job": job.nome,
            "agenda": job.quando.descricao,
            "ultima_ok": _iso(ultima),
            "parado": ultima is None or agora - ultima > limite,
            "erros_24h": int(r.erros or 0) if r is not None else 0,
            "abortados_24h": int(r.abortados or 0) if r is not None else 0,
            "execucoes_24h": int(r.execucoes or 0) if r is not None else 0,
        })
    # `evento_log` severidade erro gravado pelos jobs (3 falhas seguidas, espelho/comunicação `falhou`).
    return {"tabela": True, "ativo": any(i["execucoes_24h"] for i in itens), "jobs": itens,
            "eventos_erro_24h": eventos}
