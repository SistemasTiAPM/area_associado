"""Minhas solicitações (P05) — `/api/v1/solicitacoes` (RF-SO-01..15; contrato da Onda 2).

Dependências na ordem do projeto: sessão → CSRF (escrita) → vínculo com o CRM
(`contexto`) → prontidão das tabelas (503 `recurso_indisponivel` enquanto o
operador não aplicar `sql/010`, `012`, `013`) → limite por minuto (memória,
por processo) → domínio em `run_in_threadpool`. Tetos diários e unicidade são
do domínio, por contagem no banco (ADR-0020).

Respostas nunca carregam `contact_id`, `sub`, CPF, e-mail nem `crm_*`
(RF-SO-06; teste de contrato). `evento_uso` sai depois do commit (regra 20).

Paridade com o App APM (ADR-0024), só com a flag `solicitacoes_crm` ligada e a
`sql/016` aplicada (senão 404 `recurso_desligado` nas rotas novas e o
comportamento da Onda 2 nas antigas): `GET /solicitacoes/tipos` (catálogo
comum, sem os tipos de produto inativo), lista e detalhe fundidos com o CRM
(o que o associado abriu pelo App também aparece) e a conversa em
`/solicitacoes/{id}/mensagens`. O web só LÊ o CRM; a mensagem do associado vai
para a outbox e o serviço de jobs publica.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy.exc import OperationalError, ProgrammingError
from starlette.concurrency import run_in_threadpool

from ... import audit, prontidao, uso
from ...csrf import exigir_csrf
from ...dominio.limites_negocio import LimiteNegocioExcedido, PedidoAbertoExistente
from ...dominio.solicitacoes import catalogo, catalogo_crm, esquema, leitura_crm, mensagens, schemas, servico
from ...dominio.solicitacoes.leitura_crm import FonteIndisponivel
from ...dominio.solicitacoes.maquina import Resultado, SolicitacaoNaoEncontrada, TransicaoInvalida
from ...dominio.solicitacoes.mensagens import LimiteMensagens, MensagemNaoPermitida
from ...dominio.solicitacoes.servico import CursorInvalido, NaoElegivel
from ...limites import LimiteJanela
from ...session_guard import require_associado
from ..erros import MENSAGENS_PADRAO, ApiError
from .deps import Contexto, contexto
from .modelos_solicitacoes import CatalogoTipos, Conversa, ListaSolicitacoes, MensagemConversa, Solicitacao

logger = logging.getLogger("area_associado.api.solicitacoes")
router = APIRouter(tags=["solicitacoes"])

# Abuso por minuto (por processo; × 2 workers). O teto de negócio é do banco.
limite_escrita = LimiteJanela(maximo=20, janela_s=60)
# Conversa: cada leitura consulta o hub (cota PII por LINHA) — teto por associado.
limite_conversa = LimiteJanela(maximo=30, janela_s=60)
limite_mensagem = LimiteJanela(maximo=10, janela_s=60)

MENSAGEM_INDISPONIVEL = "As solicitações estão sendo preparadas. Tente de novo mais tarde."
MENSAGEM_NAO_ENCONTRADA = "Não encontramos esta solicitação."
MENSAGEM_PARIDADE_DESLIGADA = "Este recurso ainda não está disponível."
MENSAGEM_SERVICO_INDISPONIVEL = "Este serviço não está disponível no momento."
MENSAGEM_MENSAGENS_INDISPONIVEIS = "Mensagens temporariamente indisponíveis. Tente de novo em instantes."
MENSAGEM_ABERTA_NO_CRM = "Você já tem uma solicitação deste tipo em andamento."
_MENSAGENS_409: dict[str, str] = {
    "estado_invalido": "Esta solicitação mudou de situação. Atualizamos a página.",
    "ja_avaliada": "Esta solicitação já foi avaliada.",
    "prazo_expirado": "O prazo para avaliar esta solicitação terminou.",
    "na_central": ("Este pedido já está com a Central de Relacionamento. Para cancelar ou responder, "
                   "fale com a Central e informe o protocolo."),
}

ChaveIdempotencia = Annotated[str, StringConstraints(
    strip_whitespace=True, to_lower=True,
    pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]


def _texto(maximo: int, *, multilinha: bool = False, minimo: int = 1):
    def validar(v: str | None) -> str | None:
        if v is None:
            return None
        return schemas.texto_livre(v, minimo=minimo, maximo=maximo, multilinha=multilinha)

    return validar


class NovaSolicitacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `outro`, `declaracao_associado`, `alteracao_cadastro` e, com a paridade ligada, os
    # tipos de `GET /solicitacoes/tipos`. A allowlist é conferida na rota (depende da flag).
    tipo_servico: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,49}$")]
    campos: dict[str, Any] = Field(default_factory=dict, max_length=8)
    chave_idempotencia: ChaveIdempotencia


class MensagemEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Teto bruto generoso; o limite real (2–2000 unidades UTF-16) é do domínio.
    texto: str = Field(max_length=4000)
    chave_idempotencia: ChaveIdempotencia


class CancelarEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str | None = Field(None, max_length=400)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, v: str | None) -> str | None:
        return _texto(200)(v) if v and v.strip() else None


class ResponderEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(max_length=4000)

    @field_validator("texto")
    @classmethod
    def _texto_resposta(cls, v: str) -> str:
        return _texto(2000, multilinha=True)(v) or ""


class AvaliarEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    nota: int = Field(ge=0, le=10)
    comentario: str | None = Field(None, max_length=1000)

    @field_validator("comentario")
    @classmethod
    def _comentario(cls, v: str | None) -> str | None:
        return _texto(500, multilinha=True)(v) if v and v.strip() else None


# ------------------------------------------------------------------ apoio
async def exigir_solicitacoes_prontas() -> None:
    if not await run_in_threadpool(prontidao.disponivel, "solicitacoes"):
        raise ApiError(503, "recurso_indisponivel", MENSAGEM_INDISPONIVEL)


def exigir_limite_escrita(ctx: Contexto) -> None:
    if not limite_escrita.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")


async def paridade_ativa() -> bool:
    return await run_in_threadpool(esquema.paridade_ativa)


async def exigir_paridade() -> None:
    """Regra 19: flag desligada (ou `sql/016` ausente) = 404 `recurso_desligado`."""
    if not await paridade_ativa():
        raise ApiError(404, "recurso_desligado", MENSAGEM_PARIDADE_DESLIGADA)


def erro_de_dominio(exc: Exception) -> ApiError:
    """Exceção do domínio → contrato único de erro. Desconhecida → propaga (500)."""
    if isinstance(exc, SolicitacaoNaoEncontrada):
        return ApiError(404, "nao_encontrado", MENSAGEM_NAO_ENCONTRADA)
    if isinstance(exc, TransicaoInvalida):
        return ApiError(409, exc.codigo, exc.mensagem or _MENSAGENS_409.get(exc.codigo, MENSAGENS_PADRAO[409][1]))
    if isinstance(exc, NaoElegivel):
        # O contrato de erro só tem `detalhes [{campo, mensagem}]`: a data vai como
        # campo `libera_em`, valor AAAA-MM-DD (a SPA formata).
        return ApiError(409, "nao_elegivel", exc.mensagem,
                        detalhes=[{"campo": "libera_em", "mensagem": exc.libera_em.isoformat()}])
    if isinstance(exc, PedidoAbertoExistente):
        return ApiError(409, "estado_invalido", exc.mensagem)
    if isinstance(exc, FonteIndisponivel):
        cabecalhos = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        if exc.codigo == "mensagens_indisponiveis":
            return ApiError(503, exc.codigo, MENSAGEM_MENSAGENS_INDISPONIVEIS, headers=cabecalhos)
        return ApiError(503, "fonte_indisponivel", MENSAGENS_PADRAO[503][1], headers=cabecalhos)
    if isinstance(exc, MensagemNaoPermitida):
        return ApiError(403, "mensagem_nao_permitida", mensagens.MENSAGEM_NAO_PERMITIDA)
    if isinstance(exc, LimiteMensagens):
        return ApiError(429, "limite_mensagens", exc.mensagem, headers={"Retry-After": str(exc.retry_after)})
    if isinstance(exc, LimiteNegocioExcedido):
        return ApiError(429, "limite_negocio", exc.mensagem)
    if isinstance(exc, schemas.EntradaInvalida):
        return ApiError(400, "entrada_invalida", exc.mensagem or MENSAGENS_PADRAO[400][1], detalhes=exc.detalhes)
    if isinstance(exc, CursorInvalido):
        return ApiError(400, "entrada_invalida", MENSAGENS_PADRAO[400][1],
                        detalhes=[{"campo": "cursor", "mensagem": "cursor inválido"}])
    if isinstance(exc, ProgrammingError):
        # Tabela sumiu/ainda não existe com o cache de prontidão antigo.
        prontidao.limpar_cache()
        logger.error("solicitacoes: erro de esquema (%s)", type(exc).__name__)
        return ApiError(503, "recurso_indisponivel", MENSAGEM_INDISPONIVEL)
    if isinstance(exc, OperationalError):
        codigo = _errno(exc)
        if codigo == _ER_CHECK:
            # CHECK do banco recusou o que a validação deixou passar: bug, não indisponibilidade.
            logger.error("solicitacoes: CHECK do banco recusou a escrita (validação divergente do schema)")
            raise exc
        if codigo in _ER_PRIVILEGIO:
            prontidao.limpar_cache()
            logger.error("solicitacoes: privilégio ausente (%s) — migração aplicada pela metade?", codigo)
        else:
            logger.error("solicitacoes: banco indisponível (%s)", type(exc).__name__)
        return ApiError(503, "fonte_indisponivel", MENSAGENS_PADRAO[503][1])
    raise exc


_ER_CHECK = 3819          # ER_CHECK_CONSTRAINT_VIOLATED (PyMySQL entrega como OperationalError)
_ER_PRIVILEGIO = (1142, 1143)


def _errno(exc: Exception) -> int | None:
    args = getattr(getattr(exc, "orig", None), "args", ())
    return args[0] if args and isinstance(args[0], int) else None


_ERROS_DOMINIO = (SolicitacaoNaoEncontrada, TransicaoInvalida, NaoElegivel, PedidoAbertoExistente,
                  LimiteNegocioExcedido, schemas.EntradaInvalida, CursorInvalido, FonteIndisponivel,
                  MensagemNaoPermitida, LimiteMensagens, ProgrammingError, OperationalError)


async def executar(funcao, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(funcao, *args, **kwargs)
    except _ERROS_DOMINIO as exc:
        raise erro_de_dominio(exc) from exc


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def registrar_pos_commit(request: Request, ctx: Contexto, eventos: list[tuple[str, str, str | None, dict]],
                         auditoria: tuple[str, dict[str, Any]] | None = None) -> None:
    """`evento_uso` (e, quando cabe, `evento_log`) em transações próprias,
    depois do commit do negócio. Nunca lança."""
    rid = _request_id(request)
    for acao, entidade, entidade_id, detalhes in eventos:
        uso.registrar(acao, entidade, entidade_id, contact_id=ctx.contact_id, sub=ctx.associado.sub,
                      request_id=rid, detalhes=detalhes)
    if auditoria is not None:
        tipo, detalhes = auditoria
        audit.registrar_isolado(request, categoria="negocio", tipo=tipo, sub=ctx.associado.sub,
                                contact_id=ctx.contact_id, status_http=201, detalhes=detalhes)


def resposta_solicitacao(dados: dict[str, Any], status: int) -> JSONResponse:
    """Valida contra o modelo (contrato fechado) e responde com o status pedido."""
    return JSONResponse(Solicitacao.model_validate(dados).model_dump(mode="json"), status_code=status)


async def criar_e_responder(request: Request, ctx: Contexto, *, tipo_servico: str, campos: Any,
                            chave: str) -> JSONResponse:
    """Caminho único de criação (POST /solicitacoes, /ajuda/formulario, /ajuda/cancelamento)."""
    try:
        normalizados = schemas.validar(tipo_servico, campos)
    except schemas.EntradaInvalida as exc:
        raise erro_de_dominio(exc) from exc
    criacao = await executar(servico.criar, contact_id=ctx.contact_id, sub_hash=audit.hash_sub(ctx.associado.sub),
                             tipo_servico=tipo_servico, campos=normalizados, chave_idempotencia=chave,
                             request_id=_request_id(request))
    if criacao.criada:
        eventos: list[tuple[str, str, str | None, dict]] = [
            ("solicitacao_criar", "solicitacao", criacao.id, {"tipo": tipo_servico})]
        auditoria = None
        if tipo_servico == "cancelamento_associacao":
            eventos.append(("cancelamento_pedir", "associado", None, {"motivo": normalizados.get("motivo")}))
            auditoria = ("cancelamento_pedido", {"solicitacao": criacao.id, "motivo": normalizados.get("motivo")})
        await run_in_threadpool(registrar_pos_commit, request, ctx, eventos, auditoria)
    return resposta_solicitacao(criacao.solicitacao, 201 if criacao.criada else 200)


def _eventos_transicao(acao: str, r: Resultado) -> list[tuple[str, str, str | None, dict]]:
    return [(acao, "solicitacao", r.solicitacao_id, {}),
            ("solicitacao_status_alterado", "solicitacao", r.solicitacao_id,
             {"de": r.de, "para": r.para, "origem": "associado"})]


# ------------------------------------------------------------------ rotas
@router.get("/solicitacoes", response_model=ListaSolicitacoes,
            dependencies=[Depends(exigir_solicitacoes_prontas)])
async def listar_solicitacoes(
    situacao: Literal["andamento", "encerradas"] | None = Query(None),
    cursor: str | None = Query(None, max_length=200),
    limite: int = Query(servico.LIMITE_PADRAO, ge=1, le=servico.LIMITE_MAX),
    ctx: Contexto = Depends(contexto),
) -> dict[str, Any]:
    if await paridade_ativa():
        # Fusão com o CRM (ADR-0024): sem paginação — até 200 da área + a página do hub.
        itens, parcial = await executar(leitura_crm.listar, ctx.contact_id, situacao=situacao)
        return {"itens": itens, "proximo_cursor": None, "parcial": parcial}
    itens, proximo = await executar(servico.listar, ctx.contact_id, situacao=situacao, cursor=cursor, limite=limite)
    return {"itens": itens, "proximo_cursor": proximo}


# Antes de `/solicitacoes/{solicitacao_id}`: senão "tipos" seria lido como id.
@router.get("/solicitacoes/tipos", response_model=CatalogoTipos,
            dependencies=[Depends(require_associado), Depends(exigir_solicitacoes_prontas),
                          Depends(exigir_paridade)])
async def listar_tipos(ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    return {"itens": await run_in_threadpool(catalogo.publico)}


@router.get("/solicitacoes/{solicitacao_id}", response_model=Solicitacao,
            dependencies=[Depends(exigir_solicitacoes_prontas)])
async def obter_solicitacao(solicitacao_id: str, ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    if await paridade_ativa():
        return await executar(leitura_crm.detalhe, ctx.contact_id, solicitacao_id)
    return await executar(servico.detalhe, ctx.contact_id, solicitacao_id)


_ESCRITA = [Depends(require_associado), Depends(exigir_csrf), Depends(exigir_solicitacoes_prontas)]
_RESPOSTA_REPETICAO = {200: {"model": Solicitacao, "description": "Repetição da mesma `chave_idempotencia`."}}


@router.post("/solicitacoes", status_code=201, response_model=Solicitacao, dependencies=_ESCRITA,
             responses=_RESPOSTA_REPETICAO)
async def criar_solicitacao(entrada: NovaSolicitacao, request: Request,
                            ctx: Contexto = Depends(contexto)) -> JSONResponse:
    exigir_limite_escrita(ctx)
    tipo = entrada.tipo_servico
    if tipo in catalogo_crm.TIPOS_NOVOS and await paridade_ativa():
        # Catálogo comum com o App: o CRM pode ter desligado o serviço, e o associado
        # pode já ter um registro aberto deste tipo pelo App (unicidade entre canais).
        if not await run_in_threadpool(catalogo.disponivel, tipo):
            raise ApiError(422, "servico_indisponivel", MENSAGEM_SERVICO_INDISPONIVEL)
        if await run_in_threadpool(leitura_crm.aberto_no_crm, ctx.contact_id, tipo):
            raise ApiError(409, "estado_invalido", MENSAGEM_ABERTA_NO_CRM)
    elif tipo not in schemas.TIPOS_CRIAVEIS_API:
        raise ApiError(400, "entrada_invalida", MENSAGENS_PADRAO[400][1],
                       detalhes=[{"campo": "tipo_servico", "mensagem": "tipo de solicitação inválido"}])
    return await criar_e_responder(request, ctx, tipo_servico=tipo, campos=entrada.campos,
                                   chave=entrada.chave_idempotencia)


@router.post("/solicitacoes/{solicitacao_id}/cancelar", response_model=Solicitacao, dependencies=_ESCRITA)
async def cancelar_solicitacao(solicitacao_id: str, request: Request, entrada: CancelarEntrada | None = None,
                               ctx: Contexto = Depends(contexto)) -> JSONResponse:
    exigir_limite_escrita(ctx)
    dados, r = await executar(servico.cancelar, ctx.contact_id, solicitacao_id,
                              motivo=entrada.motivo if entrada else None, request_id=_request_id(request))
    await run_in_threadpool(registrar_pos_commit, request, ctx, _eventos_transicao("solicitacao_cancelar", r))
    return resposta_solicitacao(dados, 200)


@router.post("/solicitacoes/{solicitacao_id}/responder", response_model=Solicitacao, dependencies=_ESCRITA)
async def responder_solicitacao(solicitacao_id: str, entrada: ResponderEntrada, request: Request,
                                ctx: Contexto = Depends(contexto)) -> JSONResponse:
    exigir_limite_escrita(ctx)
    dados, r = await executar(servico.responder, ctx.contact_id, solicitacao_id, texto_resposta=entrada.texto,
                              request_id=_request_id(request))
    await run_in_threadpool(registrar_pos_commit, request, ctx, _eventos_transicao("solicitacao_responder", r))
    return resposta_solicitacao(dados, 200)


@router.post("/solicitacoes/{solicitacao_id}/avaliar", response_model=Solicitacao, dependencies=_ESCRITA)
async def avaliar_solicitacao(solicitacao_id: str, entrada: AvaliarEntrada, request: Request,
                              ctx: Contexto = Depends(contexto)) -> JSONResponse:
    exigir_limite_escrita(ctx)
    dados = await executar(servico.avaliar, ctx.contact_id, solicitacao_id, nota=entrada.nota,
                           comentario=entrada.comentario, request_id=_request_id(request))
    sid = dados["id"]
    await run_in_threadpool(registrar_pos_commit, request, ctx,
                            [("solicitacao_avaliar", "solicitacao", sid, {"nota": entrada.nota})])
    return resposta_solicitacao(dados, 200)



# ------------------------------------------------- conversa (ADR-0024)
@router.get("/solicitacoes/{solicitacao_id}/mensagens", response_model=Conversa,
            dependencies=[Depends(exigir_solicitacoes_prontas), Depends(exigir_paridade)])
async def listar_mensagens(solicitacao_id: str, atualizar: bool = Query(False),
                           ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    """`atualizar=true` (botão "Atualizar conversa"): relê a lista do associado no hub antes de
    decidir se a conversa mudou. Sem ele, a conversa vem do cache enquanto não há mensagem nova."""
    if not limite_conversa.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa", headers={"Retry-After": "60"})
    return await executar(mensagens.listar, ctx.contact_id, solicitacao_id, atualizar=atualizar)


@router.post("/solicitacoes/{solicitacao_id}/mensagens", status_code=202, response_model=MensagemConversa,
             dependencies=[*_ESCRITA, Depends(exigir_paridade)],
             responses={200: {"model": MensagemConversa,
                              "description": "Repetição da mesma `chave_idempotencia`."}})
async def enviar_mensagem(solicitacao_id: str, entrada: MensagemEntrada, request: Request,
                          ctx: Contexto = Depends(contexto)) -> JSONResponse:
    """Aceita a mensagem (202): ela entra na fila e o serviço de jobs publica na conversa
    do CRM. O texto nunca vai para `evento_uso` nem para log."""
    if not limite_mensagem.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa", headers={"Retry-After": "60"})
    envio = await executar(mensagens.enviar, ctx.contact_id, solicitacao_id, texto=entrada.texto,
                           chave_idempotencia=entrada.chave_idempotencia, request_id=_request_id(request))
    if envio.criada:
        await run_in_threadpool(registrar_pos_commit, request, ctx,
                                [("solicitacao_mensagem_enviar", "solicitacao", envio.registro_id, {})])
    return JSONResponse(MensagemConversa.model_validate(envio.mensagem).model_dump(mode="json"),
                        status_code=202 if envio.criada else 200)
