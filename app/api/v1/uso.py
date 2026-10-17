"""`POST /api/v1/uso` — eventos de uso de origem `ui` (REQUISITOS §8).

Recebe lotes da SPA (`fetch` com `keepalive`). A identidade vem da sessão; o
corpo só diz O QUE aconteceu. Ação fora do catálogo de UI é descartada e
contada, sem erro: o envio é "dispare e esqueça" e não pode travar a tela.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from ... import uso
from ...csrf import exigir_csrf
from ...limites import LimiteJanela
from ...session_guard import Associado, require_associado
from ..erros import ApiError

router = APIRouter(tags=["uso"])

_limite_lotes = LimiteJanela(maximo=60, janela_s=60)

ValorDetalhe = int | Annotated[str, StringConstraints(max_length=64)]


class EventoUi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acao: str = Field(min_length=1, max_length=48)
    entidade: str = Field(min_length=1, max_length=32)
    entidade_id: str | None = Field(None, max_length=64)
    detalhes: dict[Annotated[str, StringConstraints(max_length=32)], ValorDetalhe] | None = Field(None, max_length=8)


class LoteUso(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventos: list[EventoUi] = Field(min_length=1, max_length=uso.LOTE_MAX)


# Ordem importa: sem sessão → 401 (não 403 de CSRF, que não existe sem sessão).
@router.post("/uso", status_code=202, dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def registrar_uso(
    lote: LoteUso, request: Request, associado: Associado = Depends(require_associado)
) -> JSONResponse:
    if not _limite_lotes.permitir(associado.sub):
        raise ApiError(429, "limite_taxa")
    eventos = [
        uso.Evento(e.acao, e.entidade, e.entidade_id, e.detalhes) for e in lote.eventos if e.acao in uso.ACOES_UI
    ]
    fora_do_catalogo = len(lote.eventos) - len(eventos)
    gravados, descartados = await run_in_threadpool(
        uso.registrar_lote, eventos,
        contact_id=associado.contact_id, sub=associado.sub, origem="ui",
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse({"gravados": gravados, "descartados": descartados + fora_do_catalogo}, status_code=202)
