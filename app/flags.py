"""Feature flags (ADR-0007, REQUISITOS §10).

Valor efetivo = tabela `feature_flag` **e não** `FLAGS_FORCAR_DESLIGADAS`.
Regras de segurança:
- flag fora de `FLAGS_CONHECIDAS` não existe para a aplicação (desligada);
- falha de leitura (banco fora, tabela ainda não migrada) → **todas
  desligadas**: nenhum bloco com dado sem fonte aparece por acidente;
- cache por processo de `FLAGS_CACHE_TTL` segundos, inclusive do resultado de
  falha, para não martelar o banco quando ele está fora.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings

logger = logging.getLogger("area_associado.flags")

FLAGS_CONHECIDAS: tuple[str, ...] = (
    "mensalidade_zero",
    "fatura_valor",
    "patrocinio",
    "clube_economia",
    "comunidade_posts",
    "wallet",
    "erp_financeiro",
    "totalpass",
    # v2 (ADR-0021, sql/009): tipos de ativação e módulos da spec v2 que
    # dependem de fonte/terceiro ou de parecer. Nascem desligadas.
    "notificacoes",            # P15 sino e central de notificações (DEC-08)
    "encaminhamento_parceiro",  # tipo 2: solicitação encaminhada ao parceiro (DEC-04, EXT-12)
    "reservas",                # tipo 4: reserva com disponibilidade do parceiro (F2)
    "inscricoes",              # tipo 5: inscrição real em evento (EXT-13)
    "comunicacao_outbox",      # outbox de comunicação → RD Station (DEC-18, P-46)
    "cancelamento_online",     # P14 pedido de cancelamento pela área (A16)
    "lgpd_consentimentos",     # P13 consentimentos, exportação e exclusão (P-54)
    # ADR-0024 (sql/016): paridade com o App APM — catálogo comum, lista dos dois
    # canais e conversa com a Central.
    "solicitacoes_crm",
    # ADR-0026 (sql/017): P13 preferências, perfil progressivo e tamanho de fonte.
    "perfil_preferencias",
)

_lock = threading.Lock()
_cache: tuple[float, dict[str, bool]] | None = None


def _todas_desligadas() -> dict[str, bool]:
    return {f: False for f in FLAGS_CONHECIDAS}


def _ler_tabela() -> dict[str, bool]:
    from .database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        linhas = db.execute(text("SELECT chave, ligada FROM feature_flag")).all()
    return {str(chave): bool(ligada) for chave, ligada in linhas}


def flags_efetivas() -> dict[str, bool]:
    global _cache
    s = get_settings()
    agora = time.monotonic()
    with _lock:
        if _cache is not None and agora - _cache[0] < s.flags_cache_ttl:
            return dict(_cache[1])
    try:
        tabela = _ler_tabela()
        efetivas = {f: bool(tabela.get(f, False)) and f not in s.flags_forcadas for f in FLAGS_CONHECIDAS}
    except SQLAlchemyError as exc:
        logger.error("flags: leitura falhou (%s); todas desligadas por %ds", type(exc).__name__, s.flags_cache_ttl)
        efetivas = _todas_desligadas()
    with _lock:
        _cache = (agora, efetivas)
    return dict(efetivas)


def ligada(chave: str) -> bool:
    return flags_efetivas().get(chave, False)


def limpar_cache() -> None:
    global _cache
    with _lock:
        _cache = None
