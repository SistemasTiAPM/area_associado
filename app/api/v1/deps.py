"""Dependências comuns da API v1."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends

from ...config import get_settings
from ...dominio.associado import contact_id_valido
from ...integracoes.hub import HubError
from ...session_guard import Associado, autenticacao_recente, require_associado
from ..erros import MENSAGENS_PADRAO, ApiError


@dataclass(frozen=True)
class Contexto:
    associado: Associado
    contact_id: str  # GUID normalizado (minúsculas) — chave de tudo (ADR-0014)


def contexto(associado: Associado = Depends(require_associado)) -> Contexto:
    cid = contact_id_valido(associado.contact_id)
    if cid is None:
        # Sessão sem vínculo com o CRM não acessa dado de cadastro.
        raise ApiError(403, "cadastro_sem_contato",
                       "Não encontramos o seu cadastro. Fale com a Central de Relacionamento.")
    return Contexto(associado, cid)


MENSAGEM_REAUTENTICACAO = "Por segurança, confirme sua senha no Login APM antes de continuar."


def reautenticacao_recente(associado: Associado) -> bool:
    """Senha digitada no IdP há no máximo `REAUTH_MAX_IDADE` (regra 22: `idp_at`, nunca `auth_at`)."""
    return autenticacao_recente(associado, get_settings().reauth_max_idade)


def verificar_reautenticacao(associado: Associado, mensagem: str | None = None) -> None:
    """Step-up (ADR-0015, TI-09): 403 `reautenticacao_necessaria` no contrato único
    de erro. A SPA reage ao código (`/auth/login?reauth=1`), nunca ao texto."""
    if not reautenticacao_recente(associado):
        raise ApiError(403, "reautenticacao_necessaria", mensagem or MENSAGEM_REAUTENTICACAO)


def exigir_reautenticacao(associado: Associado = Depends(require_associado)) -> None:
    """Dependência de rota: `dependencies=[..., Depends(exigir_reautenticacao)]` em
    cancelamento, exclusão/exportação de dados, troca de canais (Fases 3/3b)."""
    verificar_reautenticacao(associado)


MENSAGEM_EDICAO_DESLIGADA = ("A alteração do cadastro ainda não está disponível por aqui. "
                             "Para alterar, fale com a Central de Relacionamento.")


def exigir_edicao() -> None:
    """Escrita no CRM desligada (`HUB_ESCRITA_HABILITADA`): 404 `recurso_desligado`
    antes de limite, upload, código por e-mail ou hub (regra 19)."""
    if not get_settings().hub_escrita_habilitada:
        raise ApiError(404, "recurso_desligado", MENSAGEM_EDICAO_DESLIGADA)


MENSAGEM_ENDERECO_INDISPONIVEL = ("O endereço ainda não pode ser alterado por aqui. "
                                  "Para corrigir, fale com a Central de Relacionamento.")


def erro_do_hub(exc: HubError) -> ApiError:
    if exc.status == 400:
        return ApiError(400, "entrada_invalida", "O cadastro recusou os dados enviados. Confira e tente de novo.",
                        detalhes=exc.detalhes)
    if exc.codigo == "edicao_desligada":
        return ApiError(404, "recurso_desligado", MENSAGEM_EDICAO_DESLIGADA)
    if exc.status == 404:
        return ApiError(404, "nao_encontrado", "Não encontramos o seu cadastro. Fale com a Central de Relacionamento.")
    if exc.status == 409 and exc.codigo == "endereco_indisponivel":
        return ApiError(409, "endereco_indisponivel", MENSAGEM_ENDERECO_INDISPONIVEL)
    if exc.status == 429:
        return ApiError(429, "limite_taxa")
    return ApiError(503, "fonte_indisponivel", MENSAGENS_PADRAO[503][1])
