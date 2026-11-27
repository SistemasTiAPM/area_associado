"""Prontidão de recursos que dependem de migração aplicada pelo operador.

As migrações da Onda 2 (`sql/010`, `012`, `013`) são aplicadas pelo operador,
fora do deploy. Até lá a área continua no ar: este módulo responde se as
tabelas de cada recurso existem (`information_schema`, só leitura) e a API
responde `503 recurso_indisponivel` nas rotas do recurso; `GET /sessao`
informa `recursos` para a SPA mostrar "em construção".

- Cache por processo de `TTL_S` (60 s) quando a leitura funciona; falha de
  leitura (banco fora) vale `TTL_FALHA_S` (15 s) — fail-closed (recurso
  indisponível) sem martelar o banco e sem prender o recurso desligado por um
  minuto inteiro depois de um soluço.
- Nunca lança.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("area_associado.prontidao")

TTL_S = 60.0
TTL_FALHA_S = 15.0

# Recurso → tabelas que precisam existir. Criar solicitação grava notificação e
# outbox na mesma transação e lê `parametro`: sem as três migrações, nada.
RECURSOS: dict[str, frozenset[str]] = {
    "solicitacoes": frozenset({"solicitacao", "solicitacao_evento", "comunicacao_evento", "comunicacao_supressao",
                               "notificacao", "fila_ligacao", "parametro"}),
    "ajuda": frozenset({"faq", "parametro"}),
    # P13 (sql/017): preferências, consentimentos e pedidos do titular.
    "privacidade": frozenset({"consentimento_texto", "consentimento", "perfil_declarado", "pergunta_perfil",
                              "titular_pedido"}),
}
_TODAS: tuple[str, ...] = tuple(sorted(set().union(*RECURSOS.values())))

_lock = threading.Lock()
_cache: tuple[float, float, frozenset[str]] | None = None  # (lido_em, ttl, presentes)


def _ler_tabelas() -> frozenset[str]:
    from .database import session_scope  # import tardio: testes substituem esta função

    sql = text(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN :nomes"
    ).bindparams(bindparam("nomes", expanding=True))
    with session_scope() as db:
        return frozenset(str(r[0]) for r in db.execute(sql, {"nomes": list(_TODAS)}))


def tabelas_presentes() -> frozenset[str]:
    global _cache
    agora = time.monotonic()
    with _lock:
        if _cache is not None and agora - _cache[0] < _cache[1]:
            return _cache[2]
    try:
        presentes, ttl = _ler_tabelas(), TTL_S
    except SQLAlchemyError as exc:
        logger.error("prontidao: leitura falhou (%s); recursos indisponíveis por %ds",
                     type(exc).__name__, int(TTL_FALHA_S))
        presentes, ttl = frozenset(), TTL_FALHA_S
    with _lock:
        _cache = (agora, ttl, presentes)
    return presentes


def disponivel(recurso: str) -> bool:
    exigidas = RECURSOS.get(recurso)
    if exigidas is None:
        return False
    return exigidas <= tabelas_presentes()


def recursos() -> dict[str, bool]:
    presentes = tabelas_presentes()
    return {nome: exigidas <= presentes for nome, exigidas in RECURSOS.items()}


def limpar_cache() -> None:
    global _cache
    with _lock:
        _cache = None
