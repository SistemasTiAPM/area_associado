"""Catálogo que a tela "Nova solicitação" oferece (ADR-0024).

Catálogo visível = tipos ofertáveis de `catalogo_crm` − tipos cujo produto o CRM diz
inativo (`solicitacao.produtos`). É assim que a APM liga e desliga um serviço pelo CRM,
sem deploy; grupo sem tipo visível some.

Cache em memória de processo (`HUB_PRODUTOS_TTL`, 12 min; sem dado pessoal). Falha do
hub → último resultado bom; sem nenhum → catálogo local inteiro (o `criar` do hub ainda
recusa produto inativo com 422). Depois de uma falha, nova tentativa só em 120 s. Uma
única renovação por vez: quem chega durante a renovação recebe o que já existe, sem
esperar o hub.

Bloqueante (HTTP ao hub): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from ...config import get_settings
from ...integracoes.hub import HubError, obter_hub
from . import catalogo_crm

logger = logging.getLogger("area_associado.solicitacoes.catalogo")

RETENTATIVA_APOS_FALHA_S = 120.0

_lock = threading.Lock()
_ativos: dict[str, bool] | None = None  # último resultado bom
_valido_ate = 0.0
_renovando = False


def _renovar() -> None:
    global _ativos, _valido_ate, _renovando
    try:
        ativos = obter_hub().solicitacao_produtos(catalogo_crm.produto_ids())
    except (HubError, ValueError) as exc:
        codigo = getattr(exc, "codigo", type(exc).__name__)
        logger.warning("catálogo: solicitacao.produtos falhou (%s); mantém o último resultado", codigo)
        with _lock:
            _valido_ate = time.monotonic() + RETENTATIVA_APOS_FALHA_S
            _renovando = False
        return
    with _lock:
        _ativos = ativos
        _valido_ate = time.monotonic() + get_settings().hub_produtos_ttl
        _renovando = False


def produtos_ativos() -> dict[str, bool] | None:
    """`produto_id → ativo` do último resultado bom, renovando se venceu. None = nunca
    houve resultado (vale o catálogo local inteiro)."""
    global _renovando
    with _lock:
        vencido = time.monotonic() >= _valido_ate
        renovar = vencido and not _renovando
        if renovar:
            _renovando = True
    if renovar:
        _renovar()
    with _lock:
        return dict(_ativos) if _ativos is not None else None


def invalidar() -> None:
    """O hub recusou um produto (422 `produto_inativo`): a próxima leitura renova."""
    global _valido_ate
    with _lock:
        _valido_ate = 0.0


def redefinir() -> None:
    """Testes: esquece o cache."""
    global _ativos, _valido_ate, _renovando
    with _lock:
        _ativos, _valido_ate, _renovando = None, 0.0, False


def visiveis() -> list[catalogo_crm.TipoCrm]:
    ativos = produtos_ativos()
    return [t for t in catalogo_crm.ofertaveis()
            if t.produto_id is None or ativos is None or ativos.get(t.produto_id, False)]


def disponivel(slug: str) -> bool:
    """O tipo pode ser aberto agora? Tipos antigos da área (fora do catálogo comum) sempre."""
    if slug not in catalogo_crm.TIPOS_NOVOS:
        return True
    return any(t.slug == slug for t in visiveis())


def publico() -> list[dict[str, Any]]:
    """O que a tela recebe: slug, rótulo, grupo, ordem, quem responde e a carência em
    meses. Nunca GUID nem o nome do produto no CRM."""
    return [{
        "codigo": t.slug,
        "rotulo": t.rotulo,
        "grupo": t.grupo,
        "grupo_rotulo": catalogo_crm.GRUPOS.get(t.grupo) if t.grupo else None,
        "ordem": t.ordem,
        "responde": catalogo_crm.responde(t.slug, t.entidade),
        "carencia_meses": t.carencia_meses,
    } for t in visiveis()]
