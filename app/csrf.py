"""CSRF: token por sessão (formulários HTML e API JSON).

Formulários (`/auth/*`): campo `csrf` comparado em tempo constante.

API (`/api/*`, métodos não seguros — RF-AU-05), três condições, todas obrigatórias:
1. `X-CSRF-Token` igual a `session["csrf"]` (tempo constante). Um site
   terceiro não lê o token (same-origin policy) nem envia cabeçalho
   customizado sem preflight CORS — e esta API não responde CORS.
2. Origem da requisição: `Sec-Fetch-Site: same-origin` quando o navegador
   envia o cabeçalho (não pode ser forjado por JavaScript); sem ele, `Origin`
   precisa ser exatamente `PUBLIC_BASE_URL`. Isso aceita o acesso de
   construção por túnel (`:8443`), que é same-origin, sem afrouxar a regra.
3. `Content-Type` JSON ou multipart: corta `text/plain` e
   `application/x-www-form-urlencoded`, que um `<form>` de terceiro
   consegue enviar sem preflight.
"""

from __future__ import annotations

import secrets

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from . import audit
from .api.erros import ApiError
from .config import get_settings

_METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
_TIPOS_ACEITOS = ("application/json", "multipart/form-data")


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def csrf_ok(request: Request, token: str | None) -> bool:
    esperado = request.session.get("csrf")
    return isinstance(esperado, str) and bool(esperado) and secrets.compare_digest(esperado, token or "")


def _motivo_recusa(request: Request) -> str | None:
    if not csrf_ok(request, request.headers.get("x-csrf-token")):
        return "token"
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        if site != "same-origin":
            return "sec_fetch_site"
    elif request.headers.get("origin") != get_settings().effective_public_base_url:
        return "origin"
    return None


async def exigir_csrf(request: Request) -> None:
    """Dependência das rotas `/api/` que alteram estado."""
    if request.method in _METODOS_SEGUROS:
        return
    tipo = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if tipo not in _TIPOS_ACEITOS:
        raise ApiError(415, "tipo_nao_suportado", "Formato de envio não suportado.")
    motivo = _motivo_recusa(request)
    if motivo is None:
        return
    await run_in_threadpool(
        audit.registrar_isolado, request, categoria="seguranca", tipo="csrf_recusado",
        severidade="aviso", sub=request.session.get("sub"), status_http=403, detalhes={"motivo": motivo},
    )
    raise ApiError(403, "csrf_invalido", "Sua sessão foi atualizada. Tente de novo.")
