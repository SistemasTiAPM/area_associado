"""Carteirinha digital (RF-CA). Dados do cache gravado no login (escopo
`carteirinha` do IdP): funciona sem o mcp_hub.

Revogada (`associado.carteirinha_revogada_em`, TI-45): `GET /carteirinha`
devolve `revogada: true` com `qr`/`url_verificacao` nulos; QR, compartilhar
e downloads respondem `409 carteirinha_revogada`. Downloads (TI-46): PNG e
PDF gerados em memória, `no-store`, 10 por hora por associado (somados).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ... import uso
from ...config import get_settings
from ...csrf import exigir_csrf
from ...dominio import carteirinha, carteirinha_arquivo, perfil
from ...limites import LimiteJanela
from ...session_guard import require_associado
from ..erros import ApiError
from ..esquemas import ApiError as EsquemaApiError
from .deps import Contexto, contexto
from .modelos import CarteirinhaResposta, UrlResposta

router = APIRouter(tags=["carteirinha"])

MENSAGEM_REVOGADA = ("Sua carteirinha está sem validade. Para entender a sua situação, "
                     "fale com a Central de Relacionamento.")
MENSAGEM_SEM_CACHE = "Sua carteirinha ainda não está disponível. Entre novamente."

_limite_download = LimiteJanela(maximo=10, janela_s=3600)

_RESPOSTA_REVOGADA = {409: {"model": EsquemaApiError,
                            "description": "`carteirinha_revogada` — carteirinha sem validade"}}


def _arquivo(midia: str, descricao: str) -> dict[int | str, dict[str, Any]]:
    return {200: {"content": {midia: {"schema": {"type": "string", "format": "binary"}}}, "description": descricao},
            **_RESPOSTA_REVOGADA}


async def _perfil_e_revogacao(contact_id: str) -> tuple[perfil.Perfil | None, bool]:
    try:
        p = await run_in_threadpool(perfil.ler, contact_id)
        revogada = await run_in_threadpool(carteirinha.revogada, contact_id)
    except SQLAlchemyError as exc:
        raise ApiError(503, "fonte_indisponivel") from exc
    return p, revogada


async def _exigir_nao_revogada(contact_id: str) -> None:
    try:
        revogada = await run_in_threadpool(carteirinha.revogada, contact_id)
    except SQLAlchemyError as exc:
        raise ApiError(503, "fonte_indisponivel") from exc
    if revogada:
        raise ApiError(409, "carteirinha_revogada", MENSAGEM_REVOGADA)


@router.get("/carteirinha", response_model=CarteirinhaResposta)
async def obter_carteirinha(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    p, revogada = await _perfil_e_revogacao(ctx.contact_id)
    if p is None:
        raise ApiError(503, "fonte_indisponivel", MENSAGEM_SEM_CACHE)
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
        "revogada": revogada,
        "url_verificacao": None if revogada else carteirinha.url_verificacao(carteirinha.token_para(ctx.contact_id)),
        "qr": None if revogada else "/api/v1/carteirinha/qr.svg",
    }


@router.get("/carteirinha/qr.svg", response_class=Response,
            responses={200: {"content": {"image/svg+xml": {}}, "description": "QR da URL pública de verificação"},
                       **_RESPOSTA_REVOGADA})
async def obter_qr_carteirinha(ctx: Contexto = Depends(contexto)) -> Response:
    await _exigir_nao_revogada(ctx.contact_id)
    svg = carteirinha.qr_svg(carteirinha.url_verificacao(carteirinha.token_para(ctx.contact_id)))
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/carteirinha/compartilhar", response_model=UrlResposta, responses=_RESPOSTA_REVOGADA,
             dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def compartilhar_carteirinha(request: Request, ctx: Contexto = Depends(contexto)) -> dict[str, str]:
    await _exigir_nao_revogada(ctx.contact_id)
    url = carteirinha.url_verificacao(carteirinha.token_para(ctx.contact_id))
    await run_in_threadpool(uso.registrar, "carteirinha_compartilhar", "carteirinha", contact_id=ctx.contact_id,
                            sub=ctx.associado.sub, request_id=getattr(request.state, "request_id", None))
    return {"url": url}


# --------------------------------------------------------------------------- #
# Downloads (TI-46)                                                            #
# --------------------------------------------------------------------------- #
async def _dados_para_arquivo(ctx: Contexto) -> carteirinha_arquivo.DadosCartao:
    """Sessão → cache de perfil (503) → revogação (409) → limite (429). O limite vem
    por último para que recusa por estado não consuma a cota do associado."""
    p, revogada = await _perfil_e_revogacao(ctx.contact_id)
    if p is None or not p.nome:
        raise ApiError(503, "fonte_indisponivel", MENSAGEM_SEM_CACHE)
    if revogada:
        raise ApiError(409, "carteirinha_revogada", MENSAGEM_REVOGADA)
    if not _limite_download.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")
    # Situação impressa só se confirmada há no máximo PERFIL_CACHE_TTL (como na
    # verificação pública); senão o cartão diz "não confirmada" e remete ao QR.
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    fresco = p.atualizado_em is not None and agora - p.atualizado_em <= timedelta(
        seconds=get_settings().perfil_cache_ttl)
    return carteirinha_arquivo.DadosCartao(
        nome=p.nome,
        categoria=p.tipo_associado,
        numero=p.num_contato,
        desde=p.data_filiacao[:4] if p.data_filiacao else None,
        situacao=p.status_associativo if fresco else None,
        url_verificacao=carteirinha.url_verificacao(carteirinha.token_para(ctx.contact_id)),
    )


async def _gerar(gerador: Any, dados: carteirinha_arquivo.DadosCartao, midia: str, nome_arquivo: str,
                 *, request: Request, ctx: Contexto, formato: str) -> Response:
    try:
        conteudo = await run_in_threadpool(gerador, dados)
    except carteirinha_arquivo.CarteirinhaOcupada as exc:
        raise ApiError(503, "fonte_indisponivel", "Muitos pedidos agora. Tente novamente em instantes.") from exc
    # Evento depois de gerar (regra 20: nunca derruba a resposta; RF-CA-07).
    await run_in_threadpool(uso.registrar, "carteirinha_baixar", "carteirinha", contact_id=ctx.contact_id,
                            sub=ctx.associado.sub, request_id=getattr(request.state, "request_id", None),
                            detalhes={"formato": formato})
    return Response(conteudo, media_type=midia, headers={
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="{nome_arquivo}"',
    })


@router.get("/carteirinha/imagem.png", response_class=Response,
            responses=_arquivo("image/png", "Carteirinha em PNG (1012×638, 300 dpi), sem metadados"))
async def baixar_carteirinha_png(request: Request, ctx: Contexto = Depends(contexto)) -> Response:
    dados = await _dados_para_arquivo(ctx)
    return await _gerar(carteirinha_arquivo.png, dados, "image/png", "carteirinha-apm.png",
                        request=request, ctx=ctx, formato="png")


@router.get("/carteirinha/documento.pdf", response_class=Response,
            responses=_arquivo("application/pdf", "Carteirinha em PDF (85,6 × 54 mm), sem metadados do associado"))
async def baixar_carteirinha_pdf(request: Request, ctx: Contexto = Depends(contexto)) -> Response:
    dados = await _dados_para_arquivo(ctx)
    return await _gerar(carteirinha_arquivo.pdf, dados, "application/pdf", "carteirinha-apm.pdf",
                        request=request, ctx=ctx, formato="pdf")
