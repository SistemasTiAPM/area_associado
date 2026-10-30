"""Tabela de jobs do serviço `area-associado-jobs` (docs/JOBS.md §2 espelha esta lista).

O WordPress (ADR-0006) NÃO entra nesta onda. Job novo = entrada aqui + teste +
linha na tabela do runbook.
"""

from __future__ import annotations

from datetime import time as dtime

from .. import prontidao
from ..config import get_settings
from . import carteirinha, comunicacao, solicitacoes
from .agenda import Quando
from .base import Job


def _solicitacoes_prontas() -> str | None:
    return None if prontidao.disponivel("solicitacoes") else "sql/010, 012 ou 013 ausente (solicitações)"


def jobs() -> tuple[Job, ...]:
    s = get_settings()
    return (
        Job("espelhar_solicitacoes", Quando(intervalo_s=s.jobs_intervalo_espelho),
            lambda ctx: solicitacoes.espelhar_solicitacoes(ctx), pronto=_solicitacoes_prontas, efeito_externo=True,
            descricao="outbox crm_* → solicitacao.espelhar / status_atualizar; promove criada→enviada"),
        Job("sincronizar_solicitacoes", Quando(intervalo_s=s.jobs_intervalo_sync),
            lambda ctx: solicitacoes.sincronizar_solicitacoes(ctx), pronto=_solicitacoes_prontas,
            efeito_externo=True,
            descricao="solicitacao.alteracoes_consultar(cursor) → transições com origem crm"),
        Job("marcar_sem_retorno", Quando(intervalo_s=s.jobs_intervalo_sem_retorno),
            solicitacoes.marcar_sem_retorno, pronto=_solicitacoes_prontas,
            descricao="marcador A05 no 1º vencimento do prazo; fila de ligações no 2º"),
        Job("enviar_comunicacao", Quando(intervalo_s=s.jobs_intervalo_comunicacao),
            lambda ctx: comunicacao.enviar_comunicacao(ctx), pronto=_solicitacoes_prontas, efeito_externo=True,
            descricao="outbox comunicacao_evento → e-mail transacional (A04, A05, A06, A16); RD suprimido"),
        Job("situacao_carteirinhas", Quando(horario=dtime(hour=s.jobs_situacao_hora)),
            lambda ctx: carteirinha.situacao_carteirinhas(ctx), pronto=carteirinha.pronto,
            descricao="associado.situacao no hub para quem acessou em 90 dias; revogação"),
    )


def por_nome() -> dict[str, Job]:
    return {j.nome: j for j in jobs()}
