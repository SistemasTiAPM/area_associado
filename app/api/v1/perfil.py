"""Perfil do associado (RF-PE): leitura, contato, e-mail com código e foto.

- Dado cadastral é do CRM; escrita só via mcp_hub e só reflete no cache
  depois de confirmada (RNF-04).
- Toda escrita: CSRF (dependência), limite por associado, `evento_log`
  (só NOMES de campos, nunca valores) e `evento_uso` em transação própria.
- E-mail é o canal de recuperação do Login APM: troca exige login recente no
  IdP (`REAUTH_MAX_IDADE`) e código enviado ao novo endereço.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from starlette.concurrency import run_in_threadpool

from ... import audit, uso
from ...config import get_settings
from ...csrf import exigir_csrf
from ...dominio import email_verificacao, foto, perfil
from ...integracoes import email as correio
from ...integracoes.hub import HubError, obter_hub
from ...limites import LimiteJanela
from ...session_guard import autenticacao_recente, require_associado
from ..erros import ApiError
from .deps import MENSAGEM_ENDERECO_INDISPONIVEL, Contexto, contexto, erro_do_hub

logger = logging.getLogger("area_associado.api.perfil")
router = APIRouter(tags=["perfil"])

_limite_contato = LimiteJanela(maximo=10, janela_s=3600)
_limite_foto = LimiteJanela(maximo=5, janela_s=3600)

# DDDs válidos no Brasil (Anatel).
_DDDS = frozenset({
    *range(11, 20), 21, 22, 24, 27, 28, *range(31, 36), 37, 38, *range(41, 47), 47, 48, 49, 51, 53, 54, 55,
    *range(61, 70), 71, 73, 74, 75, 77, 79, *range(81, 90), *range(91, 100),
})
_UFS = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")
_FUSO = ZoneInfo("America/Sao_Paulo")

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _sem_controle(valor: str) -> str:
    if _CONTROLE.search(valor):
        raise ValueError("caracteres inválidos")
    return " ".join(valor.split())


def formatar_telefone(bruto: str, *, celular: bool) -> str:
    digitos = "".join(c for c in bruto if c.isdigit())
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11) or int(digitos[:2]) not in _DDDS:
        raise ValueError("telefone inválido: use DDD + número")
    numero = digitos[2:]
    if celular and (len(numero) != 9 or numero[0] != "9"):
        raise ValueError("celular inválido: use DDD + 9 dígitos começando com 9")
    if len(numero) == 9 and numero[0] != "9":
        raise ValueError("telefone inválido")
    meio = 5 if len(numero) == 9 else 4
    return f"({digitos[:2]}) {numero[:meio]}-{numero[meio:]}"


class EnderecoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logradouro: Texto
    numero: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10,
                                             pattern=r"^[0-9A-Za-z /-]+$")]
    complemento: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    bairro: Texto
    cidade: Texto
    uf: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=2, max_length=2)]
    cep: Annotated[str, StringConstraints(strip_whitespace=True, max_length=9)]

    @field_validator("logradouro", "bairro", "cidade", "complemento")
    @classmethod
    def _textos(cls, v: str | None) -> str | None:
        return _sem_controle(v) or None if v else None

    @field_validator("uf")
    @classmethod
    def _uf(cls, v: str) -> str:
        if v not in _UFS:
            raise ValueError("UF inválida")
        return v

    @field_validator("cep")
    @classmethod
    def _cep(cls, v: str) -> str:
        digitos = "".join(c for c in v if c.isdigit())
        if len(digitos) != 8 or len(v) > 9:
            raise ValueError("CEP inválido")
        return f"{digitos[:5]}-{digitos[5:]}"


class ContatoEntrada(BaseModel):
    """Campos de edição direta (REQUISITOS §9). Ausente = não muda; `null` em
    telefone/telefone2 = apagar. Nome, CPF, CRM e situação nunca por aqui."""

    model_config = ConfigDict(extra="forbid")

    celular: Annotated[str, StringConstraints(max_length=20)] | None = None
    telefone: Annotated[str, StringConstraints(max_length=20)] | None = None
    telefone2: Annotated[str, StringConstraints(max_length=20)] | None = None
    endereco: EnderecoEntrada | None = None

    @field_validator("celular")
    @classmethod
    def _celular(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("o celular não pode ser apagado")
        return formatar_telefone(v, celular=True)

    @field_validator("telefone", "telefone2")
    @classmethod
    def _fixo(cls, v: str | None) -> str | None:
        return formatar_telefone(v, celular=False) if v else None

    def campos(self) -> dict[str, Any]:
        enviados = self.model_fields_set
        if not enviados:
            raise ValueError("nada para alterar")
        saida: dict[str, Any] = {}
        for nome in ("celular", "telefone", "telefone2"):
            if nome in enviados:
                saida[nome] = getattr(self, nome)
        if "endereco" in enviados:
            if self.endereco is None:
                raise ValueError("o endereço não pode ser apagado")
            saida["endereco"] = self.endereco.model_dump()
        return saida


class EmailEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # 100 = limite de emailaddress1 no CRM (CONTRATO-HUB): recusar aqui, antes de mandar código.
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=100)]


class ConfirmacaoEntrada(EmailEntrada):
    codigo: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{6}$")]


# ------------------------------------------------------------------ saída
def _iso(valor: datetime | None) -> str | None:
    return valor.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if valor else None


def _saida(p: perfil.Perfil, request: Request, ctx: Contexto) -> dict[str, Any]:
    s = get_settings()
    return {
        "nome": p.nome, "email": p.email, "celular": p.celular, "telefone": p.telefone, "telefone2": p.telefone2,
        "endereco": p.endereco, "num_contato": p.num_contato, "crm": p.crm, "crm_uf": p.crm_uf,
        "tipo_associado": p.tipo_associado, "status_associativo": p.status_associativo,
        "data_filiacao": p.data_filiacao, "tem_foto": p.tem_foto, "foto_versao": p.foto_etag,
        "endereco_disponivel": perfil.endereco_disponivel() is True,
        "atualizado_em": _iso(p.contato_atualizado_em or p.atualizado_em), "desatualizado": p.desatualizado,
        "email_exige_reautenticacao": not autenticacao_recente(ctx.associado, s.reauth_max_idade),
    }


def _exigir_reautenticacao(ctx: Contexto) -> None:
    if not autenticacao_recente(ctx.associado, get_settings().reauth_max_idade):
        raise ApiError(403, "reautenticacao_necessaria",
                       "Por segurança, confirme sua senha no Login APM antes de trocar o e-mail.")


def _registrar(request: Request, ctx: Contexto, *, categoria: str, tipo: str, detalhes: dict[str, Any] | None,
               acao: str | None = None) -> None:
    """evento_log + evento_uso, cada um em transação própria; nunca lança."""
    audit.registrar_isolado(request, categoria=categoria, tipo=tipo, sub=ctx.associado.sub,
                            contact_id=ctx.contact_id, status_http=200, detalhes=detalhes)
    if acao:
        uso.registrar(acao, "associado_perfil", contact_id=ctx.contact_id, sub=ctx.associado.sub,
                      request_id=getattr(request.state, "request_id", None), detalhes=detalhes)


# ------------------------------------------------------------------ rotas
@router.get("/perfil")
async def obter_perfil(request: Request, ctx: Contexto = Depends(contexto)) -> dict[str, Any]:
    try:
        p = await run_in_threadpool(perfil.obter, ctx.contact_id)
    except HubError as exc:
        raise erro_do_hub(exc) from exc
    return _saida(p, request, ctx)


@router.put("/perfil/contato", dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def atualizar_contato(entrada: ContatoEntrada, request: Request, ctx: Contexto = Depends(contexto)):
    try:
        campos = entrada.campos()
    except ValueError as exc:
        raise ApiError(400, "entrada_invalida", str(exc).capitalize() + ".") from exc
    # Sabidamente indisponível: recusa aqui, sem gastar o limite nem chamar o hub.
    # Desconhecido neste worker: o hub decide (409 se indisponível).
    if "endereco" in campos and perfil.endereco_disponivel() is False:
        raise ApiError(409, "endereco_indisponivel", MENSAGEM_ENDERECO_INDISPONIVEL)
    if not _limite_contato.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")
    try:
        await run_in_threadpool(obter_hub().contato_atualizar, ctx.contact_id, campos)
    except HubError as exc:
        if exc.codigo == "endereco_indisponivel":
            perfil.marcar_endereco_disponivel(False)
        raise erro_do_hub(exc) from exc
    await run_in_threadpool(perfil.aplicar_contato, ctx.contact_id, campos)
    detalhes = {"campos": sorted(campos)}
    await run_in_threadpool(_registrar, request, ctx, categoria="negocio", tipo="perfil_contato_atualizado",
                            detalhes=detalhes, acao="perfil_contato_atualizar")
    p = await run_in_threadpool(perfil.ler, ctx.contact_id)
    if p is None:
        raise ApiError(503, "fonte_indisponivel")
    return _saida(p, request, ctx)


@router.post("/perfil/email", status_code=202, dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def iniciar_troca_email(entrada: EmailEntrada, request: Request, ctx: Contexto = Depends(contexto)):
    _exigir_reautenticacao(ctx)
    novo = entrada.email
    if not correio.email_valido(novo):
        raise ApiError(400, "entrada_invalida", "Informe um e-mail válido.",
                       detalhes=[{"campo": "email", "mensagem": "formato inválido"}])
    atual = await run_in_threadpool(perfil.ler, ctx.contact_id)
    if atual is not None and atual.email and atual.email.strip().lower() == novo:
        raise ApiError(400, "email_igual", "Este já é o seu e-mail cadastrado.")
    s = get_settings()
    try:
        pedido, codigo = await run_in_threadpool(email_verificacao.iniciar, ctx.contact_id, novo)
    except email_verificacao.RecusaVerificacao as exc:
        raise ApiError(exc.status, exc.codigo, exc.mensagem) from exc
    try:
        await run_in_threadpool(correio.enviar, novo, "Código para confirmar seu novo e-mail — Minha APM",
                                correio.texto_codigo(codigo, s.email_codigo_ttl // 60))
    except correio.EmailError as exc:
        raise ApiError(503, "envio_indisponivel",
                       "Não conseguimos enviar o código agora. Tente novamente em alguns minutos.") from exc
    await run_in_threadpool(_registrar, request, ctx, categoria="seguranca", tipo="email_codigo_enviado", detalhes=None)
    corpo: dict[str, Any] = {"enviado_para": correio.mascarar_email(novo), "expira_em": _iso(pedido.expira_em)}
    if s.smtp_mode == "stub" and not s.is_production:
        corpo["codigo_teste"] = codigo  # só construção: SMTP_MODE=stub é proibido em produção
    return JSONResponse(corpo, status_code=202)


def _telefone_central() -> str:
    numero = get_settings().whatsapp_central
    if numero.startswith("55") and len(numero) in (12, 13):
        try:
            return formatar_telefone(numero, celular=False)
        except ValueError:
            return ""
    return ""


def _avisar_email_antigo(antigo: str) -> None:
    quando = datetime.now(_FUSO).strftime("%d/%m/%Y às %H:%M")
    try:
        correio.enviar(antigo, "Seu e-mail de acesso à APM foi alterado",
                       correio.texto_aviso_troca(quando, _telefone_central()))
    except correio.EmailError:
        logger.error("perfil: aviso ao e-mail antigo não entregue")


@router.post("/perfil/email/confirmar", dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def confirmar_troca_email(entrada: ConfirmacaoEntrada, request: Request, ctx: Contexto = Depends(contexto)):
    _exigir_reautenticacao(ctx)
    try:
        pedido = await run_in_threadpool(email_verificacao.conferir, ctx.contact_id, entrada.email, entrada.codigo)
    except email_verificacao.RecusaVerificacao as exc:
        if exc.codigo in ("codigo_invalido", "tentativas_esgotadas"):
            await run_in_threadpool(_registrar, request, ctx, categoria="seguranca", tipo="email_codigo_recusado",
                                    detalhes={"motivo": exc.codigo})
        raise ApiError(exc.status, exc.codigo, exc.mensagem) from exc
    antes = await run_in_threadpool(perfil.ler, ctx.contact_id)
    try:
        await run_in_threadpool(obter_hub().contato_atualizar, ctx.contact_id, {"email": entrada.email})
    except HubError as exc:
        raise erro_do_hub(exc) from exc
    await run_in_threadpool(email_verificacao.marcar_usado, pedido.id)
    await run_in_threadpool(perfil.aplicar_contato, ctx.contact_id, {"email": entrada.email})
    await run_in_threadpool(_registrar, request, ctx, categoria="seguranca", tipo="perfil_email_alterado",
                            detalhes={"campos": ["email"]}, acao="perfil_contato_atualizar")
    if antes is not None and antes.email and antes.email.strip().lower() != entrada.email:
        await run_in_threadpool(_avisar_email_antigo, antes.email)
    p = await run_in_threadpool(perfil.ler, ctx.contact_id)
    if p is None:
        raise ApiError(503, "fonte_indisponivel")
    return _saida(p, request, ctx)


# ------------------------------------------------------------------- foto
@router.post("/perfil/foto", dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def enviar_foto(request: Request, ctx: Contexto = Depends(contexto)):
    # Corpo lido SÓ depois de sessão, CSRF e limites (o FastAPI leria um
    # UploadFile antes das dependências).
    s = get_settings()
    tamanho = request.headers.get("content-length")
    if tamanho is None or not tamanho.isdigit():
        raise ApiError(411, "tamanho_ausente", "Envio sem tamanho declarado.")
    if int(tamanho) > s.foto_max_bytes + 64 * 1024:
        raise ApiError(413, "arquivo_grande", f"A foto deve ter até {s.foto_max_bytes // (1024 * 1024)} MB.")
    if not _limite_foto.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")
    formulario = await request.form(max_files=1, max_fields=1)
    try:
        arquivo = formulario.get("foto")
        if arquivo is None or isinstance(arquivo, str):
            raise ApiError(400, "entrada_invalida", "Envie a foto no campo 'foto'.")
        dados = await arquivo.read(s.foto_max_bytes + 1)
    finally:
        await formulario.close()
    try:
        grande, pequena = await run_in_threadpool(foto.processar, dados, s.foto_max_bytes)
    except foto.FotoInvalida as exc:
        status = {"arquivo_grande": 413, "tipo_nao_suportado": 415}.get(exc.codigo, 400)
        raise ApiError(status, exc.codigo, exc.mensagem) from exc
    except foto.FotoOcupada as exc:
        raise ApiError(503, "ocupado", "Estamos processando outras fotos. Tente de novo em instantes.") from exc
    try:
        await run_in_threadpool(obter_hub().foto_atualizar, ctx.contact_id, grande)
    except HubError as exc:
        raise erro_do_hub(exc) from exc
    versao = foto.etag(pequena)
    await run_in_threadpool(perfil.aplicar_foto, ctx.contact_id, pequena, versao)
    await run_in_threadpool(_registrar, request, ctx, categoria="negocio", tipo="perfil_foto_atualizada",
                            detalhes={"bytes": len(grande)}, acao="perfil_foto_atualizar")
    return {"tem_foto": True, "foto_versao": versao}


@router.delete("/perfil/foto", dependencies=[Depends(require_associado), Depends(exigir_csrf)])
async def remover_foto(request: Request, ctx: Contexto = Depends(contexto)):
    if not _limite_foto.permitir(ctx.contact_id):
        raise ApiError(429, "limite_taxa")
    try:
        await run_in_threadpool(obter_hub().foto_atualizar, ctx.contact_id, None)
    except HubError as exc:
        raise erro_do_hub(exc) from exc
    await run_in_threadpool(perfil.aplicar_foto, ctx.contact_id, None, None)
    await run_in_threadpool(_registrar, request, ctx, categoria="negocio", tipo="perfil_foto_removida",
                            detalhes={"removida": True}, acao="perfil_foto_atualizar")
    return {"tem_foto": False, "foto_versao": None}


@router.get("/perfil/foto")
async def obter_foto(request: Request, ctx: Contexto = Depends(contexto)) -> Response:
    achado = await run_in_threadpool(perfil.miniatura, ctx.contact_id)
    if achado is None:
        raise ApiError(404, "nao_encontrado", "Sem foto.")
    dados, versao = achado
    etag = f'"{versao}"'
    cabecalhos = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cabecalhos)
    return Response(dados, media_type="image/jpeg", headers=cabecalhos)
