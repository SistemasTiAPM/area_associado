"""Esquema OpenAPI do contrato único de erro (TI-07).

Módulo sem dependências internas para poder ser importado por `erros.py` (que
define a exceção `ApiError`) e pelos roteadores. No OpenAPI exportado o
componente chama-se `ApiError`, igual ao nome do contrato em REQUISITOS §3.0.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DetalheErro(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campo: str
    mensagem: str


class ApiError(BaseModel):
    """`{"erro", "mensagem", "request_id", "detalhes"?}` — a exceção que o produz é `app.api.erros.ApiError`."""

    model_config = ConfigDict(extra="forbid")
    erro: str = Field(description="Código estável; a SPA decide por ele, nunca pelo texto.")
    mensagem: str = Field(description="Texto em pt-BR para o associado.")
    request_id: str | None = Field(description="Mesmo valor do cabeçalho X-Request-Id.")
    detalhes: list[DetalheErro] | None = Field(None, description="Campo e motivo; nunca o valor recebido.")
