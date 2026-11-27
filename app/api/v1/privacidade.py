"""Perfil e privacidade (P13) — preferências, perfil progressivo, consentimentos
e direitos do titular (spec v2 §6 P13 e §11.6; ADR-0025 e ADR-0026; `sql/017`).

Ordem das dependências em toda rota: sessão → CSRF (escritas) → flag (404
`recurso_desligado`, regra 19) → step-up (403, só exportação e exclusão) →
prontidão da `sql/017` (503 `recurso_indisponivel`) → limite de taxa.

- Flag `perfil_preferencias`: `/perfil/preferencias` e `/perfil/pergunta`.
- Flag `lgpd_consentimentos`: `/perfil/consentimentos` e `/perfil/dados/*`
  (textos e prazos do jurídico: P-54).
- Exportação e pedido de exclusão exigem senha recente no Login APM (`idp_at`,
  regra 22): quem senta num navegador aberto não leva os dados nem pede a
  exclusão de outra pessoa.
- A exportação sai `no-store`, só da própria sessão, e fica no `evento_log`
  como acesso a dado pessoal (TI-90) — grupos de campos, nunca valores.
- Nada aqui chama o hub: é dado da área.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from ... import audit, prontidao, uso
from ...config import get_settings
from ...csrf import exigir_csrf
from ...dominio import consentimento, preferencias, titular
from ...flags import ligada
from ...limites import LimiteJanela
from ...session_guard import Associado, require_associado
from ..erros import ApiError
from .deps import Contexto, contexto, reautenticacao_recente, verificar_reautenticacao
from .modelos import (
    ConsentimentoItem,
    ConsentimentosResposta,
    ExclusaoResposta,
    PedidosTitularResposta,
    PerguntaResposta,
    PreferenciasResposta,
)
from .solicitacoes import ChaveIdempotencia, executar, registrar_pos_commit

logger = logging.getLogger("area_associado.api.privacidade")
router = APIRouter(tags=["perfil"])

_FUSO = ZoneInfo("America/Sao_Paulo")

MENSAGEM_PREFERENCIAS_DESLIGADAS = "As preferências ainda não estão disponíveis por aqui."
MENSAGEM_LGPD_DESLIGADA = ("Esta opção ainda não está disponível por aqui. "
                           "Para tratar dos seus dados, fale com a Central de Relacionamento.")
MENSAGEM_INDISPONIVEL = "Esta parte do perfil está sendo preparada. Tente de novo mais tarde."
MENSAGEM_REAUTH_EXPORTACAO = "Por segurança, confirme sua senha no Login APM antes de baixar seus dados."
MENSAGEM_REAUTH_EXCLUSAO = "Por segurança, confirme sua senha no Login APM antes de pedir a exclusão."
MENSAGEM_VERSAO = "O texto desta autorização foi atualizado. Leia a versão nova e confirme de novo."
PALAVRA_CONFIRMACAO = "EXCLUIR"

_limite_preferencias = LimiteJanela(maximo=30, janela_s=60)
_limite_consentimento = LimiteJanela(maximo=20, janela_s=3600)
_limite_dados = LimiteJanela(maximo=6, janela_s=3600)


# ----------------------------------------------------------------- entradas
class PreferenciasEntrada(BaseModel):
    """Ausente = não muda. `tratamento` vazio ou `null` = saudação neutra;
    lista vazia = sem resposta. Catálogos fechados no domínio."""

    model_config = ConfigDict(extra="forbid")

    tratamento: str | None = Field(None, max_length=120)
    atuacao: list[Annotated[str, StringConstraints(max_length=32)]] | None = Field(None, max_length=8)
    temas: list[Annotated[str, StringConstraints(max_length=32)]] | None = Field(None, max_length=12)
    canal_preferido: Annotated[str, StringConstraints(max_length=32)] | None = None
    frequencia: Annotated[str, StringConstraints(max_length=32)] | None = None
    fonte: Annotated[str, StringConstraints(max_length=32)] | None = None


class RespostaPerguntaEntrada(BaseModel):
    """`{"pular": true}` ou `{"resposta": <texto | opção | lista de opções>}`."""

    model_config = ConfigDict(extra="forbid")

    pular: bool = Field(False, strict=True)
    resposta: (Annotated[str, StringConstraints(max_length=120)]
               | Annotated[list[Annotated[str, StringConstraints(max_length=32)]], Field(max_length=12)]
               | None) = None


class ConsentimentoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finalidade: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,31}$")]
    canal: Literal["email", "whatsapp", "sms", "push", "telefone"]
    concedido: bool = Field(strict=True)
    versao: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,15}$")]


class ExclusaoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Digitada pelo associado: pedir exclusão nunca é um clique só.
    confirmacao: Annotated[str, StringConstraints(strip_whitespace=True, max_length=16)]
    chave_idempotencia: ChaveIdempotencia


ChavePergunta = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,31}$")]


# -------------------------------------------------------------- dependências
async def exigir_preferencias() -> None:
    if not await run_in_threadpool(ligada, "perfil_preferencias"):
        raise ApiError(404, "recurso_desligado", MENSAGEM_PREFERENCIAS_DESLIGADAS)


async def exigir_lgpd() -> None:
    if not await run_in_threadpool(ligada, "lgpd_consentimentos"):
        raise ApiError(404, "recurso_desligado", MENSAGEM_LGPD_DESLIGADA)


async def exigir_privacidade_pronta() -> None:
    if not await run_in_threadpool(prontidao.disponivel, "privacidade"):
        raise ApiError(503, "recurso_indisponivel", MENSAGEM_INDISPONIVEL)


def exigir_reautenticacao_exportacao(associado: Associado = Depends(require_associado)) -> None:
    verificar_reautenticacao(associado, MENSAGEM_REAUTH_EXPORTACAO)


def exigir_reautenticacao_exclusao(associado: Associado = Depends(require_associado)) -> None:
    verificar_reautenticacao(associado, MENSAGEM_REAUTH_EXCLUSAO)


_SESSAO = Depends(require_associado)
_CSRF = Depends(exigir_csrf)
_PRONTA = Depends(exigir_privacidade_pronta)
_LER_PREFERENCIAS = [_SESSAO, Depends(exigir_preferencias), _PRONTA]
_ESCREVER_PREFERENCIAS = [_SESSAO, _CSRF, Depends(exigir_preferencias), _PRONTA]
_LER_LGPD = [_SESSAO, Depends(exigir_lgpd), _PRONTA]
_ESCREVER_LGPD = [_SESSAO, _CSRF, Depends(exigir_lgpd), _PRONTA]


# -------------------------------------------------------------------- apoio
def _iso(valor: datetime | None) -> str | None:
    return valor.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if valor else None


def _limitar(limite: LimiteJanela, ctx: Contexto) -> None:
    if not limite.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")


def _saida_preferencias(p: preferencias.Preferencias) -> dict[str, Any]:
    return {
        "tratamento": p.tratamento, "atuacao": list(p.atuacao), "temas": list(p.temas),
        "canal_preferido": p.canal_preferido, "frequencia": p.frequencia, "fonte": p.fonte, "atualizado_em": _iso(p.atualizado_em),
        "faltam": p.faltam(), "opcoes": preferencias.opcoes(),
    }


def _saida_pergunta(p: preferencias.Pergunta | None) -> dict[str, Any]:
    if p is None:
        return {"pergunta": None}
    return {"pergunta": {
        "chave": p.chave, "titulo": p.titulo, "ajuda": p.ajuda, "tipo": p.tipo, "maximo": p.maximo,
        "opcoes": [{"valor": valor, "rotulo": rotulo} for valor, rotulo in p.opcoes.items()],
    }}


async def _preferencias(funcao, *args: Any) -> Any:
    """Domínio de preferências → contrato de erro (banco pelo `executar` comum)."""
    try:
        return await executar(funcao, *args)
    except preferencias.PreferenciaInvalida as exc:
        raise ApiError(400, "entrada_invalida", detalhes=exc.detalhes) from exc
    except preferencias.PerguntaDesconhecida as exc:
        raise ApiError(404, "nao_encontrado", "Esta pergunta não existe mais. Recarregue a página.") from exc


async def _registrar_mudanca(request: Request, ctx: Contexto, mudou: list[str]) -> None:
    """`evento_uso` e `evento_log` com os NOMES dos campos que mudaram, nunca os valores."""
    if not mudou:
        return
    detalhes = {"campos": sorted(mudou)}
    await run_in_threadpool(registrar_pos_commit, request, ctx,
                            [("perfil_declarado_atualizar", "perfil_declarado", None, detalhes)],
                            ("perfil_declarado_atualizado", detalhes))


# -------------------------------------------------------------- preferências
@router.get("/perfil/preferencias", response_model=PreferenciasResposta, dependencies=_LER_PREFERENCIAS)
async def obter_preferencias(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    return _saida_preferencias(await _preferencias(preferencias.ler, ctx.contact_id))


@router.put("/perfil/preferencias", response_model=PreferenciasResposta, dependencies=_ESCREVER_PREFERENCIAS)
async def atualizar_preferencias(entrada: PreferenciasEntrada, request: Request,
                                 ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    _limitar(_limite_preferencias, ctx)
    enviados = {campo: getattr(entrada, campo) for campo in entrada.model_fields_set}
    try:
        campos = preferencias.validar(enviados)
    except preferencias.PreferenciaInvalida as exc:
        raise ApiError(400, "entrada_invalida", detalhes=exc.detalhes) from exc
    atual, mudou = await _preferencias(preferencias.salvar, ctx.contact_id, campos)
    await _registrar_mudanca(request, ctx, mudou)
    return _saida_preferencias(atual)


@router.get("/perfil/pergunta", response_model=PerguntaResposta, dependencies=_LER_PREFERENCIAS)
async def obter_pergunta(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    return _saida_pergunta(await _preferencias(preferencias.proxima_pergunta, ctx.contact_id))


@router.post("/perfil/pergunta/{chave}", response_model=PreferenciasResposta,
             dependencies=_ESCREVER_PREFERENCIAS)
async def responder_pergunta(chave: ChavePergunta, entrada: RespostaPerguntaEntrada, request: Request,
                             ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    _limitar(_limite_preferencias, ctx)
    if entrada.pular:
        if entrada.resposta is not None:
            raise ApiError(400, "entrada_invalida", "Envie a resposta ou pule a pergunta, não os dois.")
        await _preferencias(preferencias.pular, ctx.contact_id, chave)
        return _saida_preferencias(await _preferencias(preferencias.ler, ctx.contact_id))
    atual, mudou = await _preferencias(preferencias.responder, ctx.contact_id, chave, entrada.resposta)
    await _registrar_mudanca(request, ctx, mudou)
    return _saida_preferencias(atual)


# ------------------------------------------------------------ consentimentos
@router.get("/perfil/consentimentos", response_model=ConsentimentosResposta, dependencies=_LER_LGPD)
async def listar_consentimentos(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    return {"itens": await executar(consentimento.listar, ctx.contact_id)}


@router.put("/perfil/consentimentos", response_model=ConsentimentoItem, dependencies=_ESCREVER_LGPD)
async def decidir_consentimento(entrada: ConsentimentoEntrada, request: Request,
                                ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    _limitar(_limite_consentimento, ctx)
    valor = "concedido" if entrada.concedido else "retirado"
    try:
        item, gravou = await executar(
            consentimento.registrar, contact_id=ctx.contact_id, sub_hash=audit.hash_sub(ctx.associado.sub),
            finalidade=entrada.finalidade, canal=entrada.canal, valor=valor, versao=entrada.versao,
            request_id=getattr(request.state, "request_id", None))
    except consentimento.ConsentimentoDesconhecido as exc:
        raise ApiError(404, "nao_encontrado", "Esta autorização não está disponível.") from exc
    except consentimento.VersaoDesatualizada as exc:
        raise ApiError(409, "versao_desatualizada", MENSAGEM_VERSAO,
                       detalhes=[{"campo": "versao", "mensagem": exc.vigente}]) from exc
    if gravou:
        detalhes = {"finalidade": entrada.finalidade, "canal": entrada.canal, "valor": valor,
                    "versao": entrada.versao}
        await run_in_threadpool(registrar_pos_commit, request, ctx,
                                [("consentimento_alterar", "consentimento", entrada.finalidade, detalhes)],
                                ("consentimento_alterado", detalhes))
    return item


# ------------------------------------------------------- direitos do titular
@router.get("/perfil/dados/pedidos", response_model=PedidosTitularResposta, dependencies=_LER_LGPD)
async def listar_pedidos(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    saida = await executar(titular.listar_pedidos, ctx.contact_id)
    saida["exige_reautenticacao"] = not reautenticacao_recente(ctx.associado)
    return saida


@router.post(
    "/perfil/dados/exportar", response_class=JSONResponse,
    responses={200: {"description": "Arquivo JSON (`Content-Disposition: attachment`) com os dados que a área "
                                    "guarda sobre o associado. Uma exportação a cada 7 dias."}},
    dependencies=[_SESSAO, _CSRF, Depends(exigir_lgpd), Depends(exigir_reautenticacao_exportacao), _PRONTA])
async def exportar_dados(request: Request, ctx: Contexto = Depends(contexto)) -> JSONResponse:
    _limitar(_limite_dados, ctx)
    s = get_settings()
    try:
        exportacao = await executar(
            titular.exportar, contact_id=ctx.contact_id, sub_hash=audit.hash_sub(ctx.associado.sub),
            request_id=getattr(request.state, "request_id", None),
            demonstracao=s.hub_mode == "stub" or s.smtp_mode == "stub")
    except titular.LimiteExportacao as exc:
        quando = exc.libera_em.replace(tzinfo=timezone.utc).astimezone(_FUSO)
        raise ApiError(429, "limite_negocio",
                       f"Você já baixou seus dados nos últimos 7 dias. Um novo arquivo fica disponível em "
                       f"{quando:%d/%m/%Y} às {quando:%H:%M}.",
                       detalhes=[{"campo": "disponivel_em", "mensagem": _iso(exc.libera_em) or ""}]) from exc
    await run_in_threadpool(audit.registrar_acesso_dado_pessoal, request, sub=ctx.associado.sub,
                            ator_contact_id=ctx.contact_id, alvo_contact_id=ctx.contact_id,
                            campos=list(titular.GRUPOS_EXPORTADOS), finalidade="exportacao_titular")
    await run_in_threadpool(uso.registrar, "dados_exportar", "associado", contact_id=ctx.contact_id,
                            sub=ctx.associado.sub, request_id=getattr(request.state, "request_id", None))
    nome = f"minha-apm-dados-{datetime.now(_FUSO):%Y%m%d}.json"
    return JSONResponse(exportacao.dados, headers={
        "Content-Disposition": f'attachment; filename="{nome}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.post(
    "/perfil/dados/exclusao", status_code=201, response_model=ExclusaoResposta,
    responses={200: {"model": ExclusaoResposta, "description": "Repetição da mesma `chave_idempotencia`."}},
    dependencies=[_SESSAO, _CSRF, Depends(exigir_lgpd), Depends(exigir_reautenticacao_exclusao), _PRONTA])
async def pedir_exclusao(entrada: ExclusaoEntrada, request: Request,
                         ctx: Contexto = Depends(contexto)) -> JSONResponse:
    if entrada.confirmacao.upper() != PALAVRA_CONFIRMACAO:
        raise ApiError(400, "entrada_invalida", f"Para confirmar, digite {PALAVRA_CONFIRMACAO}.",
                       detalhes=[{"campo": "confirmacao", "mensagem": f"digite {PALAVRA_CONFIRMACAO}"}])
    if not await run_in_threadpool(prontidao.disponivel, "solicitacoes"):
        raise ApiError(503, "recurso_indisponivel", MENSAGEM_INDISPONIVEL)
    _limitar(_limite_dados, ctx)
    pedido = await executar(
        titular.pedir_exclusao, contact_id=ctx.contact_id, sub_hash=audit.hash_sub(ctx.associado.sub),
        chave_idempotencia=entrada.chave_idempotencia, request_id=getattr(request.state, "request_id", None))
    if pedido.criado:
        await run_in_threadpool(
            registrar_pos_commit, request, ctx,
            [("solicitacao_criar", "solicitacao", pedido.solicitacao_id, {"tipo": "exclusao_dados"}),
             ("exclusao_pedir", "associado", None, {})],
            ("exclusao_pedida", {"solicitacao": pedido.solicitacao_id, "protocolo": pedido.protocolo}))
    corpo = {"protocolo": pedido.protocolo, "solicitacao_id": pedido.solicitacao_id,
             "registrado_em": _iso(pedido.registrado_em)}
    return JSONResponse(corpo, status_code=201 if pedido.criado else 200)
