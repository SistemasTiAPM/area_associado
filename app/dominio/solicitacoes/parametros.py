"""Leitura de `parametro` (sql/013) — só leitura para `apm_area` (ADR-0022).

Dois modos:
- `inteiro(sess, chave)`: dentro da transação de negócio (o prazo copiado na
  criação e o prazo de avaliação valem o que o banco diz NAQUELE instante);
- `texto_cacheado(chave)`: fora de transação, cache por processo de 60 s, para
  telas de leitura (contato da Central).

Valor ausente, de tipo errado ou fora da faixa → valor-padrão seguro com log de
erro (nunca derruba a requisição por causa de configuração).
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger("area_associado.parametros")

TTL_S = 60.0

# chave → (padrão, mínimo, máximo). Padrões = seed da sql/013.
INTEIROS: dict[str, tuple[int, int, int]] = {
    "avaliacao_prazo_dias": (30, 1, 365),
    "prazo_retorno_padrao_dias": (10, 1, 365),
    "cancelamento_janela_horas": (24, 0, 720),
}
TEXTOS: dict[str, int] = {  # chave → tamanho máximo aceito
    "central_horario": 120,
    "central_telefone": 20,
}

_SQL = text("SELECT valor FROM parametro WHERE chave = :k")

_lock = threading.Lock()
_cache: dict[str, tuple[float, str | None]] = {}


def interpretar_inteiro(chave: str, bruto: object) -> int:
    padrao, minimo, maximo = INTEIROS[chave]
    try:
        valor = int(str(bruto).strip())
    except (TypeError, ValueError):
        logger.error("parametro: %s ausente ou não inteiro; usando %d", chave, padrao)
        return padrao
    if not minimo <= valor <= maximo:
        logger.error("parametro: %s fora da faixa [%d, %d]; usando %d", chave, minimo, maximo, padrao)
        return padrao
    return valor


def inteiro(sess: Session, chave: str) -> int:
    if chave not in INTEIROS:
        raise KeyError(chave)
    return interpretar_inteiro(chave, sess.execute(_SQL, {"k": chave}).scalar())


def _ler_texto(chave: str) -> str | None:
    from ...database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        bruto = db.execute(_SQL, {"k": chave}).scalar()
    if bruto is None:
        return None
    valor = " ".join(str(bruto).split())
    return valor[: TEXTOS[chave]] or None


def texto_cacheado(chave: str) -> str | None:
    """Texto do parâmetro (vazio = None). Banco fora ou tabela ausente = None."""
    if chave not in TEXTOS:
        raise KeyError(chave)
    agora = time.monotonic()
    with _lock:
        item = _cache.get(chave)
        if item is not None and agora - item[0] < TTL_S:
            return item[1]
    try:
        valor = _ler_texto(chave)
    except SQLAlchemyError as exc:
        logger.error("parametro: leitura de %s falhou (%s)", chave, type(exc).__name__)
        valor = None
    with _lock:
        _cache[chave] = (agora, valor)
    return valor


def limpar_cache() -> None:
    with _lock:
        _cache.clear()
