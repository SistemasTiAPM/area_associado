"""Aplicação FastAPI — Área do Associado (APM).

Rotas públicas: `/`, `/auth/login`, `/auth/callback`, `/health`.
Rotas autenticadas: `/area`, `/auth/logout` (POST, CSRF).
Internas (bloqueadas no edge): `/db-health`, `/auth-health`.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER

from . import audit
from .config import get_settings
from .database import check_connection, get_session, session_scope, tls_status
from .oidc import (
    AssociadoClaims,
    OidcError,
    authorize_url,
    build_pending,
    jwks_cache,
    login_from_callback,
    mask_cpf,
    pending_is_valid,
)
from .session_guard import (
    SESSION_PENDING,
    Associado,
    LoginRequired,
    current_associado,
    login_redirect,
    require_associado,
    safe_next,
    store_identity,
)

logger = logging.getLogger("area_associado")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_VERSIONED_STATIC = ("style.css", "fonts.css", "boot.js")


def _static_version() -> str:
    digest = hashlib.md5(usedforsecurity=False)
    for nome in _VERSIONED_STATIC:
        caminho = BASE_DIR / "static" / nome
        digest.update(nome.encode("utf-8"))
        if caminho.is_file():
            digest.update(caminho.read_bytes())
    return digest.hexdigest()[:8]


templates.env.globals["static_v"] = _static_version()
templates.env.globals["auth_mode"] = settings.auth_mode
templates.env.globals["app_env"] = settings.app_env
templates.env.globals["issuer"] = settings.effective_issuer

# Mensagens ao associado por código de erro do fluxo OIDC. O código vai para o
# evento_log; o associado vê só a frase e o request_id.
_OIDC_MESSAGES = {
    "idp_access_denied": "O acesso não foi liberado pelo Login APM. Se a sua situação associativa "
                         "estiver regular, fale com a Central de Relacionamento.",
    "idp_login_required": "Sua sessão no Login APM expirou. Entre novamente.",
    "idp_temporarily_unavailable": "O Login APM está temporariamente indisponível. Tente novamente em instantes.",
    "state_mismatch": "A sessão de login expirou ou foi reiniciada. Tente entrar novamente.",
    "pending_missing": "A sessão de login expirou ou foi reiniciada. Tente entrar novamente.",
    "token_invalid_grant": "O código de acesso já foi utilizado ou expirou. Entre novamente.",
    "userinfo_unavailable": "Não foi possível obter seus dados cadastrais agora. Tente novamente em instantes.",
    "jwks_unavailable": "O Login APM está temporariamente indisponível. Tente novamente em instantes.",
}
_OIDC_DEFAULT_MESSAGE = "Não foi possível concluir o login. Tente novamente."


# --------------------------------------------------------------------------- #
# CSRF (token por sessão, comparação em tempo constante)                       #
# --------------------------------------------------------------------------- #
def _csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def _csrf_ok(request: Request, token: str | None) -> bool:
    expected = request.session.get("csrf")
    return bool(expected) and secrets.compare_digest(expected, token or "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        check_connection()
        st = tls_status()
        logger.info(
            "RDS %s/%s ok — usuário=%s tls=%s %s",
            settings.db_host, settings.db_name, st.get("current_user"),
            st.get("Ssl_version") or "-", st.get("Ssl_cipher") or "SEM CIFRA",
        )
    except (SQLAlchemyError, FileNotFoundError) as exc:
        logger.error("Falha ao validar conexão com o RDS na inicialização: %s", exc)
    if settings.auth_mode == "oidc":
        try:
            kids = await run_in_threadpool(jwks_cache().kids)
            logger.info("OIDC issuer=%s backchannel=%s kids=%s",
                        settings.effective_issuer, settings.effective_backchannel, kids)
        except OidcError as exc:
            logger.error("JWKS indisponível no boot (%s); será buscado no primeiro login.", exc.code)
    else:
        logger.warning("AUTH_MODE=stub ativo (APP_ENV=%s): login sem IdP. NUNCA em produção.", settings.app_env)
    yield


app = FastAPI(
    title="Área do Associado",
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_openapi else None,
    redoc_url="/redoc" if settings.expose_openapi else None,
    openapi_url="/openapi.json" if settings.expose_openapi else None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,
    https_only=settings.session_https_only,
    # `lax`, não `strict`: o retorno do IdP (/auth/callback) é navegação top-level
    # cross-site; com `strict` o cookie com state/verifier não viaja e o login
    # falha em silêncio com "state_mismatch".
    same_site="lax",
)


@app.middleware("http")
async def _request_context(request: Request, call_next):
    request.state.request_id = secrets.token_hex(8)
    request.state.csp_nonce = secrets.token_urlsafe(16)
    inicio = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{request.state.csp_nonce}'; "
        "style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self' "
        f"{settings.effective_issuer}; object-src 'none'",
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.scope.get("path", "").startswith("/static/"):
        query = request.scope.get("query_string", b"").decode("latin-1")
        versionada = query.startswith("v=") or "&v=" in query
        response.headers.setdefault(
            "Cache-Control",
            "public, max-age=31536000, immutable" if versionada else "public, max-age=86400",
        )
    else:
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    request.state.duracao_ms = int((time.perf_counter() - inicio) * 1000)
    return response


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.exception_handler(LoginRequired)
async def _login_required(request: Request, exc: LoginRequired) -> RedirectResponse:
    return login_redirect(exc.next_path)


def _erro(request: Request, mensagem: str, status: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "erro.html",
        {"mensagem": mensagem, "request_id": request.state.request_id, "status": status},
        status_code=status,
    )


# --------------------------------------------------------------------------- #
# Público                                                                       #
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if current_associado(request) is not None:
        return RedirectResponse("/area", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "home.html", {})


@app.get("/auth/login")
async def auth_login(request: Request, next: str | None = None, reauth: str | None = None):
    destino = safe_next(next)
    if settings.auth_mode == "stub":
        if current_associado(request) is not None:
            return RedirectResponse(destino, status_code=HTTP_303_SEE_OTHER)
        return templates.TemplateResponse(
            request, "stub_login.html", {"csrf": _csrf_token(request), "next": destino}
        )
    if current_associado(request) is not None and reauth != "1":
        return RedirectResponse(destino, status_code=HTTP_303_SEE_OTHER)
    pending = build_pending(destino)
    request.session[SESSION_PENDING] = pending
    return RedirectResponse(authorize_url(pending, reauth=reauth == "1"), status_code=302,
                            headers={"Cache-Control": "no-store"})


@app.post("/auth/login")
async def auth_login_stub(
    request: Request,
    csrf: str = Form(""),
    token: str = Form(""),
    nome: str = Form(""),
    email: str = Form(""),
    cpf: str = Form(""),
    next: str = Form("/area"),
    db: Session = Depends(get_session),
):
    if settings.auth_mode != "stub":
        return _erro(request, "Recurso indisponível.", 404)
    if not _csrf_ok(request, csrf):
        return _erro(request, "Sessão expirada. Recarregue a página e tente novamente.", 400)
    destino = safe_next(next)
    if not secrets.compare_digest(token, settings.dev_stub_token or ""):
        audit.registrar(db, request, categoria="seguranca", tipo="login_stub_falha", severidade="aviso", status_http=403)
        return _erro(request, "Token de construção inválido.", 403)
    digits = "".join(ch for ch in cpf if ch.isdigit())
    if len(digits) != 11:
        return templates.TemplateResponse(
            request, "stub_login.html",
            {"csrf": _csrf_token(request), "next": destino, "error": "Informe um CPF com 11 dígitos."},
            status_code=400,
        )
    sub = audit.hash_sub(f"stub:{digits}") or "stub"
    claims = AssociadoClaims(
        sub=sub, contact_id=None, nome=" ".join(nome.split())[:160] or "Associado (stub)",
        email=email.strip()[:254] or None, cpf_mask=mask_cpf(digits), amr=["stub"], auth_time=int(time.time()),
    )
    store_identity(request, claims)
    audit.registrar(db, request, categoria="seguranca", tipo="login_stub", sub=sub, status_http=303)
    return RedirectResponse(destino, status_code=HTTP_303_SEE_OTHER)


@app.get("/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_session)):
    if settings.auth_mode != "oidc":
        return _erro(request, "Recurso indisponível.", 404)
    pending = request.session.pop(SESSION_PENDING, None)
    if not pending_is_valid(pending):
        audit.registrar(db, request, categoria="seguranca", tipo="login_falha", severidade="aviso",
                        status_http=400, detalhes={"motivo": "pending_missing"})
        return _erro(request, _OIDC_MESSAGES["pending_missing"], 400)

    params = dict(request.query_params)
    try:
        claims = await run_in_threadpool(login_from_callback, params, pending)
    except OidcError as exc:
        if exc.code == "idp_login_required":
            return login_redirect(pending["next"])
        severidade = "erro" if exc.http_status >= 500 else "aviso"
        audit.registrar(db, request, categoria="seguranca", tipo="login_falha", severidade=severidade,
                        status_http=exc.http_status, detalhes={"motivo": exc.code})
        return _erro(request, _OIDC_MESSAGES.get(exc.code, _OIDC_DEFAULT_MESSAGE), exc.http_status)

    store_identity(request, claims)
    audit.registrar(db, request, categoria="seguranca", tipo="login_ok", sub=claims.sub,
                    contact_id=claims.contact_id, status_http=303, detalhes={"amr": claims.amr})
    return RedirectResponse(pending["next"], status_code=HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Autenticado                                                                   #
# --------------------------------------------------------------------------- #
@app.get("/area", response_class=HTMLResponse)
async def area(request: Request, associado: Associado = Depends(require_associado)):
    return templates.TemplateResponse(
        request, "area.html", {"a": associado, "csrf": _csrf_token(request)}
    )


@app.post("/auth/logout")
async def auth_logout(request: Request, csrf: str = Form(""), db: Session = Depends(get_session)):
    associado = current_associado(request)
    if associado is None:
        request.session.clear()
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    if not _csrf_ok(request, csrf):
        return _erro(request, "Sessão expirada. Recarregue a página e tente novamente.", 400)
    idt = request.session.get("idt")
    request.session.clear()
    audit.registrar(db, request, categoria="seguranca", tipo="logout", sub=associado.sub,
                    contact_id=associado.contact_id, status_http=303)
    if settings.auth_mode == "oidc" and isinstance(idt, str) and idt:
        # RP-Initiated Logout: encerra a sessão do IdP também, senão o próximo
        # /auth/login volta por SSO silencioso.
        qs = urlencode({"id_token_hint": idt, "post_logout_redirect_uri": settings.post_logout_redirect_uri})
        return RedirectResponse(f"{settings.effective_issuer}/oauth/logout?{qs}", status_code=HTTP_303_SEE_OTHER,
                                headers={"Cache-Control": "no-store"})
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Probes                                                                        #
# --------------------------------------------------------------------------- #
@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> RedirectResponse:
    return RedirectResponse("/static/favicon-32.png")


@app.get("/db-health", include_in_schema=False)
async def db_health() -> JSONResponse:
    try:
        st = await run_in_threadpool(tls_status)
        return JSONResponse({"status": "ok", "database": settings.db_name, "user": st.get("current_user"),
                             "ssl_version": st.get("Ssl_version"), "ssl_cipher": st.get("Ssl_cipher")})
    except SQLAlchemyError as exc:
        logger.error("db-health falhou: %s", exc)
        return JSONResponse({"status": "error", "detail": "database unavailable"}, status_code=503)


@app.get("/auth-health", include_in_schema=False)
async def auth_health() -> JSONResponse:
    body = {"auth_mode": settings.auth_mode, "app_env": settings.app_env, "issuer": settings.effective_issuer}
    if settings.auth_mode != "oidc":
        return JSONResponse(body)
    try:
        body["jwks_kids"] = await run_in_threadpool(jwks_cache().kids)
        return JSONResponse(body)
    except OidcError as exc:
        body["detail"] = exc.code
        return JSONResponse(body, status_code=503)
