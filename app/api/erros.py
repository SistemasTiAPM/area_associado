"""Contrato único de erro da API (REQUISITOS §3.0).

Corpo: `{"erro": <código estável>, "mensagem": <pt-BR para o associado>,
"request_id": <X-Request-Id>, "detalhes"?: [{"campo", "mensagem"}]}`.

A SPA mostra `mensagem` em toast e decide o comportamento pelo `erro` — nunca
pelo texto. Erros de validação listam o campo e o motivo, **nunca o valor
recebido** (poderia ecoar dado pessoal em log de proxy ou de navegador).
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PREFIXO_API = "/api/"

MENSAGENS_PADRAO: dict[int, tuple[str, str]] = {
    400: ("entrada_invalida", "Confira os dados informados e tente novamente."),
    401: ("nao_autenticado", "Sua sessão terminou. Entre novamente."),
    403: ("nao_permitido", "Você não tem permissão para esta ação."),
    404: ("nao_encontrado", "Não encontramos o que você procurou."),
    405: ("metodo_nao_permitido", "Operação não permitida."),
    409: ("estado_invalido", "Esta ação não pode ser feita agora."),
    413: ("arquivo_grande", "O arquivo enviado é grande demais."),
    415: ("tipo_nao_suportado", "Formato de envio não suportado."),
    429: ("limite_taxa", "Muitas tentativas em pouco tempo. Aguarde um instante."),
    503: ("fonte_indisponivel", "Não foi possível carregar agora. Tente novamente em instantes."),
}
_PADRAO_5XX = ("erro_interno", "Algo deu errado do nosso lado. Tente novamente em instantes.")


class ApiError(Exception):
    """Erro de negócio/HTTP da API com código estável."""

    def __init__(
        self,
        status: int,
        erro: str,
        mensagem: str | None = None,
        *,
        detalhes: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(erro)
        self.status = status
        self.erro = erro
        self.mensagem = mensagem or MENSAGENS_PADRAO.get(status, _PADRAO_5XX)[1]
        self.detalhes = detalhes
        self.headers = headers


def e_rota_api(request: Request) -> bool:
    return request.url.path.startswith(PREFIXO_API)


def resposta_erro(
    request: Request,
    status: int,
    erro: str,
    mensagem: str,
    *,
    detalhes: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    corpo: dict[str, Any] = {
        "erro": erro,
        "mensagem": mensagem,
        "request_id": getattr(request.state, "request_id", None),
    }
    if detalhes:
        corpo["detalhes"] = detalhes
    return JSONResponse(corpo, status_code=status, headers=headers)


async def tratar_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return resposta_erro(request, exc.status, exc.erro, exc.mensagem, detalhes=exc.detalhes, headers=exc.headers)


def _campo(loc: tuple[Any, ...]) -> str:
    # ("body", "eventos", 0, "acao") -> "eventos.0.acao"
    partes = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(partes) or "corpo"


async def tratar_validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    detalhes = [
        {"campo": _campo(tuple(e.get("loc", ()))), "mensagem": "valor inválido ou ausente"}
        for e in exc.errors()[:20]
    ]
    erro, mensagem = MENSAGENS_PADRAO[400]
    return resposta_erro(request, 400, erro, mensagem, detalhes=detalhes)


def resposta_http_api(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    erro, mensagem = MENSAGENS_PADRAO.get(exc.status_code, _PADRAO_5XX)
    headers = dict(exc.headers) if getattr(exc, "headers", None) else None
    return resposta_erro(request, exc.status_code, erro, mensagem, headers=headers)
