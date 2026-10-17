"""Entrega da SPA (ADR-0001): `GET /area` e `GET /area/{caminho}` → `index.html`.

- Exige sessão (`require_associado`): sem ela, 303 para `/auth/login?next=`
  via `safe_next` — a SPA nunca é servida a quem não entrou.
- `Cache-Control: no-store` (o middleware aplica a tudo fora de `/static/`).
- `index.html` lido uma vez e mantido em memória (o build é imutável dentro
  da imagem). Em `development`, relido quando o arquivo muda, para o fluxo
  `vite build --watch`.
- Sem build presente: 503 com página de erro, não 500 — falha de
  empacotamento visível e explicada.
- O HTML do Vite não tem script nem estilo inline; a CSP com `script-src 'self'`
  basta. Se um dia precisar, o marcador `__CSP_NONCE__` é substituído aqui.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from .config import get_settings
from .session_guard import Associado, require_associado

logger = logging.getLogger("area_associado.spa")

INDEX = Path(__file__).resolve().parent / "static" / "spa" / "index.html"
_MARCADOR_NONCE = "__CSP_NONCE__"

router = APIRouter(include_in_schema=False)

_lock = threading.Lock()
_cache: tuple[float, str] | None = None


def carregar_index() -> str | None:
    global _cache
    try:
        mtime = INDEX.stat().st_mtime
    except FileNotFoundError:
        return None
    with _lock:
        if _cache is not None and (_cache[0] == mtime or get_settings().app_env != "development"):
            return _cache[1]
        _cache = (mtime, INDEX.read_text(encoding="utf-8"))
        return _cache[1]


def _responder(request: Request) -> Response:
    html = carregar_index()
    if html is None:
        logger.error("SPA ausente: %s não existe (imagem sem o estágio do frontend?)", INDEX)
        return HTMLResponse(
            "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\"><title>Minha APM</title>"
            "<p>A Minha APM está temporariamente indisponível. Tente novamente em instantes.</p>"
            f"<p>Código: <code>{request.state.request_id}</code></p></html>",
            status_code=503,
        )
    if _MARCADOR_NONCE in html:
        html = html.replace(_MARCADOR_NONCE, request.state.csp_nonce)
    return HTMLResponse(html)


@router.get("/area", response_class=HTMLResponse)
async def area_raiz(request: Request, associado: Associado = Depends(require_associado)) -> Response:
    return _responder(request)


@router.get("/area/{caminho:path}", response_class=HTMLResponse)
async def area_rota(caminho: str, request: Request, associado: Associado = Depends(require_associado)) -> Response:
    # Toda rota sob /area é da SPA: o React Router decide o que mostrar
    # (inclusive a tela "não encontrada" dentro do shell).
    return _responder(request)
