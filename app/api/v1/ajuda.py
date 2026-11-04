"""Ajuda e atendimento (P14) — `/api/v1/ajuda` (RF-AJ-01..04; contrato da Onda 2).

- `GET /ajuda/faq`: FAQ publicada com busca sem acento (503
  `recurso_indisponivel` sem a `sql/013`).
- `GET /ajuda/contato`: canais da Central; funciona sem migração (só o
  WhatsApp do `Settings`; telefone e horário aparecem quando o `parametro` existe).
- `POST /ajuda/formulario` [C]: solicitação `outro` — mesmo caminho e mesmos
  limites de `POST /solicitacoes`.
- `POST /ajuda/cancelamento` [C] [F:`cancelamento_online`] + step-up:
  solicitação `cancelamento_associacao`; janela de arrependimento antes do
  espelho no CRM; **nunca** chama ferramenta de escrita do hub — quem cancela
  é a APM (RF-AJ-04).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from starlette.concurrency import run_in_threadpool

from ... import prontidao
from ...csrf import exigir_csrf
from ...dominio import ajuda
from ...dominio.solicitacoes import rotulos, schemas
from ...flags import ligada
from ...limites import LimiteJanela
from ...session_guard import Associado, require_associado
from ..erros import MENSAGENS_PADRAO, ApiError
from .deps import Contexto, contexto, verificar_reautenticacao
from .modelos_solicitacoes import ContatoCentral, FaqResposta, Solicitacao
from .solicitacoes import (
    ChaveIdempotencia,
    criar_e_responder,
    exigir_limite_escrita,
    exigir_solicitacoes_prontas,
)

router = APIRouter(tags=["ajuda"])

limite_faq = LimiteJanela(maximo=60, janela_s=60)

MENSAGEM_AJUDA_INDISPONIVEL = "As perguntas frequentes estão sendo preparadas. Fale com a Central pelos canais abaixo."
MENSAGEM_CANCELAMENTO_DESLIGADO = ("O pedido de cancelamento ainda não está disponível por aqui. "
                                   "Fale com a Central de Relacionamento.")
MENSAGEM_REAUTH_CANCELAMENTO = "Por segurança, confirme sua senha no Login APM antes de pedir o cancelamento."

CategoriaFaq = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,31}$")]


class FormularioEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assunto: Literal["beneficio", "cadastro", "financeiro", "eventos", "outro"]
    mensagem: str = Field(max_length=4000)
    chave_idempotencia: ChaveIdempotencia

    @field_validator("mensagem")
    @classmethod
    def _mensagem(cls, v: str) -> str:
        return schemas.texto_livre(v, maximo=schemas.MENSAGEM_OUTRO_MAX, multilinha=True, utf16=True)


class CancelamentoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: Literal["nao_uso", "preco", "mudanca", "insatisfacao_servico", "outro"]
    quer_conversa: bool = Field(strict=True)
    comentario: str | None = Field(None, max_length=1000)
    chave_idempotencia: ChaveIdempotencia

    @field_validator("comentario")
    @classmethod
    def _comentario(cls, v: str | None) -> str | None:
        return schemas.texto_livre(v, maximo=500, multilinha=True) if v and v.strip() else None


# ------------------------------------------------------------------ apoio
async def exigir_ajuda_pronta() -> None:
    if not await run_in_threadpool(prontidao.disponivel, "ajuda"):
        raise ApiError(503, "recurso_indisponivel", MENSAGEM_AJUDA_INDISPONIVEL)


async def exigir_cancelamento_online() -> None:
    if not await run_in_threadpool(ligada, "cancelamento_online"):
        raise ApiError(404, "recurso_desligado", MENSAGEM_CANCELAMENTO_DESLIGADO)


def exigir_reautenticacao_cancelamento(associado: Associado = Depends(require_associado)) -> None:
    verificar_reautenticacao(associado, MENSAGEM_REAUTH_CANCELAMENTO)


# ------------------------------------------------------------------ rotas
@router.get("/ajuda/faq", response_model=FaqResposta, dependencies=[Depends(exigir_ajuda_pronta)])
async def obter_faq(
    q: str | None = Query(None, max_length=ajuda.Q_MAX),
    categoria: CategoriaFaq | None = Query(None),
    ctx: Contexto = Depends(contexto),
) -> dict[str, Any]:
    if not limite_faq.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")
    try:
        return await run_in_threadpool(ajuda.buscar, q, categoria)
    except ajuda.FaqIndisponivel as exc:
        raise ApiError(503, "fonte_indisponivel", MENSAGENS_PADRAO[503][1]) from exc


@router.get("/ajuda/contato", response_model=ContatoCentral)
async def obter_contato(_: Associado = Depends(require_associado)) -> dict[str, Any]:
    return await run_in_threadpool(ajuda.contato)


_RESPOSTA_REPETICAO = {200: {"model": Solicitacao, "description": "Repetição da mesma `chave_idempotencia`."}}


@router.post("/ajuda/formulario", status_code=201, response_model=Solicitacao, responses=_RESPOSTA_REPETICAO,
             dependencies=[Depends(require_associado), Depends(exigir_csrf), Depends(exigir_solicitacoes_prontas)])
async def enviar_formulario(entrada: FormularioEntrada, request: Request,
                            ctx: Contexto = Depends(contexto)) -> JSONResponse:
    exigir_limite_escrita(ctx)
    campos = {"assunto": rotulos.ASSUNTO_FORMULARIO[entrada.assunto], "mensagem": entrada.mensagem,
              "categoria": entrada.assunto}
    return await criar_e_responder(request, ctx, tipo_servico="outro", campos=campos,
                                   chave=entrada.chave_idempotencia)


# Ordem: sessão → CSRF → flag (404) → step-up (403) → prontidão (503).
@router.post("/ajuda/cancelamento", status_code=201, response_model=Solicitacao, responses=_RESPOSTA_REPETICAO,
             dependencies=[Depends(require_associado), Depends(exigir_csrf), Depends(exigir_cancelamento_online),
                           Depends(exigir_reautenticacao_cancelamento), Depends(exigir_solicitacoes_prontas)])
async def pedir_cancelamento(entrada: CancelamentoEntrada, request: Request,
                             ctx: Contexto = Depends(contexto)) -> JSONResponse:
    exigir_limite_escrita(ctx)
    campos: dict[str, Any] = {"motivo": entrada.motivo, "quer_conversa": entrada.quer_conversa}
    if entrada.comentario:
        campos["comentario"] = entrada.comentario
    return await criar_e_responder(request, ctx, tipo_servico="cancelamento_associacao", campos=campos,
                                   chave=entrada.chave_idempotencia)
