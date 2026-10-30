"""Job `situacao_carteirinhas` — situação associativa noturna (TI-45; frente B).

Diário às `JOBS_SITUACAO_HORA` (03h, hora local). Associados com carteirinha
emitida (`carteirinha_token`) e acesso nos últimos 90 dias cuja leitura de
situação tem mais de 20 h: `carteirinha.atualizar_situacao(sess, cid, hub=...)`
(a mesma escrita da verificação pública — cache de situação e revogação).

- Lotes de até `JOBS_SITUACAO_LOTE` (≤ 200) por rodada, até
  `JOBS_SITUACAO_RODADAS` rodadas, com `JOBS_SITUACAO_PAUSA` entre chamadas
  (cota da conta no hub — P-41). Paginação por `contact_id` (keyset): quem
  falhou não volta na mesma execução.
- Disjuntor: 5 leituras seguidas sem resposta do hub encerram a execução com
  `erro` (o hub está fora; amanhã tenta de novo).
- Efeito local (leitura do hub): roda nos dois modos. A conta do hub deve ser
  a `area-associado-jobs` (cota própria, M-8) — `HUB_CLIENT_ID`/`HUB_CLIENT_SECRET`
  em `.env.jobs` (docs/JOBS.md §3).
- Pula a rodada inteira sem a `sql/014` (`colunas_revogacao_presentes()`).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import text

from ..config import get_settings
from ..dominio import carteirinha
from ..integracoes.hub import ClienteHub, obter_hub
from .base import Contexto

logger = logging.getLogger("area_associado.jobs.carteirinha")

ACESSO_DIAS = 90
IDADE_MINIMA_H = 20
DISJUNTOR_SEM_RESPOSTA = 5

_SQL_LOTE = text(
    "SELECT contact_id FROM associado WHERE carteirinha_token IS NOT NULL AND ultimo_acesso_em >= :desde "
    "AND (situacao_consultada_em IS NULL OR situacao_consultada_em < :velha) AND contact_id > :apos "
    "ORDER BY contact_id LIMIT :lote"
)


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem

    return session_scope()


def pronto() -> str | None:
    return None if carteirinha.colunas_revogacao_presentes() else "sql/014 ausente (colunas de revogação)"


def situacao_carteirinhas(ctx: Contexto, *, hub: ClienteHub | None = None) -> None:
    s = get_settings()
    hub = hub or obter_hub()
    desde = ctx.agora - timedelta(days=ACESSO_DIAS)
    velha = ctx.agora - timedelta(hours=IDADE_MINIMA_H)
    apos = ""
    sem_resposta = 0
    for _ in range(s.jobs_situacao_rodadas):
        with _sessao() as db:
            lote = [str(r.contact_id) for r in db.execute(_SQL_LOTE, {
                "desde": desde, "velha": velha, "apos": apos, "lote": s.jobs_situacao_lote})]
        if not lote:
            return
        for cid in lote:
            if ctx.parar():
                return
            apos = cid
            ctx.lidos += 1
            with _sessao() as db:
                leitura = carteirinha.atualizar_situacao(db, cid, hub=hub)
            if leitura is None:
                ctx.erros += 1
                sem_resposta += 1
                if sem_resposta >= DISJUNTOR_SEM_RESPOSTA:
                    ctx.erro_sistemico = f"disjuntor: {sem_resposta} consultas seguidas sem resposta do hub"
                    return
            else:
                sem_resposta = 0
                ctx.gravados += 1
            if ctx.esperar(s.jobs_situacao_pausa):
                return
        if len(lote) < s.jobs_situacao_lote:
            return
