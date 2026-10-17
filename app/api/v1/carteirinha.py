"""Carteirinha digital (RF-CA). Dados do cache gravado no login (escopo
`carteirinha` do IdP): funciona sem o mcp_hub."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ... import uso
from ...csrf import exigir_csrf
from ...dominio import carteirinha, perfil
from ...session_guard import require_associado
from ..erros import ApiError
from .deps import Contexto, contexto

router = APIRouter(tags=["carteirinha"])


@router.get("/carteirinha")
async def obter_carteirinha(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    p = await run_in_threadpool(perfil.ler, ctx.contact_id)
    if p is None:
        raise ApiError(503, "fonte_indisponivel", "Sua carteirinha ainda não está disponível. Entre novamente.")
    token = carteirinha.token_para(ctx.contact_id)
    verificado = p.atualizado_em.replace(tzinfo=timezone.utc) if p.atualizado_em else None
    return {
        "nome": p.nome,
        "crm": p.crm,
        "crm_uf": p.crm_uf,
        "num_contato": p.num_contato,
        "tipo_associado": p.tipo_associado,
        "status_associativo": p.status_associativo,
        "membro_desde": p.data_filiacao[:4] if p.data_filiacao else None,
        "verificado_em": verificado.isoformat().replace("+00:00", "Z") if verificado else None,
        "url_verificacao": carteirinha.url_verificacao(token),
        "qr": "/api/v1/carteirinha/qr.svg",
    }


@router.get("/carteirinha/qr.svg")
async def qr(ctx: Contexto = Depends(contexto)) -> Response:
    svg = carteirinha.qr_svg(carteirinha.url_verificacao(carteirinha.token_para(ctx.contact_id)))
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/carteirinha/compartilhar", dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def compartilhar(request: Request, ctx: Contexto = Depends(contexto)) -> dict[str, str]:
    url = carteirinha.url_verificacao(carteirinha.token_para(ctx.contact_id))
    await run_in_threadpool(uso.registrar, "carteirinha_compartilhar", "carteirinha", contact_id=ctx.contact_id,
                            sub=ctx.associado.sub, request_id=getattr(request.state, "request_id", None))
    return {"url": url}
