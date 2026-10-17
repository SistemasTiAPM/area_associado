"""Rotas públicas sem sessão: verificação da carteirinha (RF-CA-03).

`GET /verificar/{token}` mostra SÓ nome, situação e "verificado em" (spec,
"Privacidade"). Token inválido e inexistente têm a mesma resposta (404).
Rate limit estrito no vhost (zona `area_verificar`); `noindex`; `no-store`.
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from . import uso
from .dominio import carteirinha
from .templating import templates

logger = logging.getLogger("area_associado.publico")
_FUSO = ZoneInfo("America/Sao_Paulo")
_CABECALHOS = {"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "no-store"}

router = APIRouter(include_in_schema=False)


@router.get("/verificar/{token}", response_class=HTMLResponse)
async def verificar(token: str, request: Request) -> HTMLResponse:
    try:
        resultado = await run_in_threadpool(carteirinha.resolver, token[:64])
    except SQLAlchemyError as exc:
        logger.error("verificar: banco indisponível (%s)", type(exc).__name__)
        return templates.TemplateResponse(request, "verificar.html", {"indisponivel": True},
                                          status_code=503, headers=_CABECALHOS)
    if resultado is None:
        return templates.TemplateResponse(request, "verificar.html", {"encontrado": False},
                                          status_code=404, headers=_CABECALHOS)
    await run_in_threadpool(uso.registrar, "carteirinha_verificar", "carteirinha", contact_id=resultado.contact_id,
                            sub=None, origem="publico", request_id=getattr(request.state, "request_id", None))
    quando = (resultado.verificado_em.replace(tzinfo=ZoneInfo("UTC")).astimezone(_FUSO).strftime("%d/%m/%Y às %H:%M")
              if resultado.verificado_em else None)
    return templates.TemplateResponse(
        request, "verificar.html",
        {"encontrado": True, "nome": resultado.nome, "situacao": resultado.situacao, "quando": quando},
        headers=_CABECALHOS,
    )
