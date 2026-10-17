"""Dependências comuns da API v1."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends

from ...dominio.associado import contact_id_valido
from ...integracoes.hub import HubError
from ...session_guard import Associado, require_associado
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


def erro_do_hub(exc: HubError) -> ApiError:
    if exc.status == 400:
        return ApiError(400, "entrada_invalida", "O cadastro recusou os dados enviados. Confira e tente de novo.",
                        detalhes=exc.detalhes)
    if exc.status == 404:
        return ApiError(404, "nao_encontrado", "Não encontramos o seu cadastro. Fale com a Central de Relacionamento.")
    if exc.status == 429:
        return ApiError(429, "limite_taxa")
    return ApiError(503, "fonte_indisponivel", MENSAGENS_PADRAO[503][1])
