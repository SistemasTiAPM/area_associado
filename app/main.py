"""Aplicação FastAPI — Minha APM (Área do Associado).

Rotas públicas: `/`, `/auth/login`, `/auth/callback`, `/health`.
Rotas autenticadas: `/area` e `/area/{caminho}` (SPA), `/api/v1/*` (JSON),
`/auth/logout` (POST, CSRF).
Internas (bloqueadas no edge): `/db-health`, `/auth-health`.
"""

from __future__ import annotations

import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_303_SEE_OTHER

from . import audit, publico, spa, uso
from .api import v1 as api_v1
from .api.erros import (
    MENSAGENS_PADRAO,
    ApiError,
    e_rota_api,
    resposta_erro,
    resposta_http_api,
    tratar_api_error,
    tratar_validacao,
)
from .config import get_settings
from .csrf import csrf_ok, csrf_token
from .database import check_connection, get_session, tls_status
from .dominio.associado import contact_id_stub, registrar_login
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
from .sessao import SessaoCifradaMiddleware, construir_cifrador
from .templating import templates
from .session_guard import (
    SESSION_PENDING,
    LoginRequired,
    current_associado,
    login_redirect,
    safe_next,
    store_identity,
)

logger = logging.getLogger("area_associado")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent
# Assets do build do Vite têm hash no nome: podem ser imutáveis para sempre.
_PREFIXO_IMUTAVEL = "/static/spa/assets/"

# Opções do login stub para testar personas (rótulos de `alf_tipo_associado`).
TIPOS_STUB = ("Efetivo", "Aspirante", "Acadêmico", "Correspondente Nacional", "Correspondente no Exterior")


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
    # P-20 (decisão de 2026-10-17): cadastro sem tipo/situação não abre sessão.
    "persona_incompleta": "Seu cadastro na APM está incompleto (tipo de associado ou situação). "
                          "Fale com a Central de Relacionamento para regularizar e tente de novo.",
}
_OIDC_DEFAULT_MESSAGE = "Não foi possível concluir o login. Tente novamente."


def _csp(nonce: str) -> str:
    """CSP final (ADR-0013, RNF-01). Sem 'unsafe-inline' em lugar nenhum."""
    img = " ".join(["'self'", "data:", *settings.csp_img_host_list])
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self'; "
        f"img-src {img}; "
        "font-src 'self'; connect-src 'self'; manifest-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; "
        f"form-action 'self' {settings.effective_issuer}; object-src 'none'"
    )


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
    if spa.carregar_index() is None:
        logger.error("SPA não encontrada em %s: /area responderá 503.", spa.INDEX)
    if not settings.session_enc_key_list:
        logger.warning("SESSION_ENC_KEYS ausente: chave da sessão derivada de SECRET_KEY (só fora de produção).")
    yield


app = FastAPI(
    title="Minha APM",
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_openapi else None,
    redoc_url="/redoc" if settings.expose_openapi else None,
    openapi_url="/openapi.json" if settings.expose_openapi else None,
)
app.add_middleware(
    SessaoCifradaMiddleware,
    cifrador=construir_cifrador(settings.session_enc_key_list, settings.secret_key),
    cookie_name=settings.session_cookie_name,
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
    response.headers.setdefault("Content-Security-Policy", _csp(request.state.csp_nonce))
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    caminho = request.scope.get("path", "")
    if caminho.startswith(_PREFIXO_IMUTAVEL):
        # Só sucesso é imutável: um 404 de asset (deploy pela metade) nunca
        # pode ficar preso no cache do navegador por um ano.
        response.headers.setdefault(
            "Cache-Control", "public, max-age=31536000, immutable" if response.status_code == 200 else "no-store"
        )
    elif caminho.startswith("/static/"):
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
app.include_router(api_v1.router)
app.include_router(spa.router)
app.include_router(publico.router)


# --------------------------------------------------------------------------- #
# Erros: JSON em /api/, HTML no resto                                           #
# --------------------------------------------------------------------------- #
def _erro(request: Request, mensagem: str, status: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "erro.html",
        {"mensagem": mensagem, "request_id": request.state.request_id, "status": status},
        status_code=status,
    )


@app.exception_handler(LoginRequired)
async def _login_required(request: Request, exc: LoginRequired) -> Response:
    if e_rota_api(request):
        # API nunca redireciona: a SPA recebe 401 e navega para o login (RF-AU-02/08).
        erro, mensagem = MENSAGENS_PADRAO[401]
        return resposta_erro(request, 401, erro, mensagem)
    return login_redirect(exc.next_path)


app.add_exception_handler(ApiError, tratar_api_error)


@app.exception_handler(RequestValidationError)
async def _validacao(request: Request, exc: RequestValidationError) -> Response:
    if e_rota_api(request):
        return await tratar_validacao(request, exc)
    return _erro(request, "Requisição inválida.", 400)


@app.exception_handler(StarletteHTTPException)
async def _http(request: Request, exc: StarletteHTTPException) -> Response:
    if e_rota_api(request):
        return resposta_http_api(request, exc)
    if exc.status_code == 404:
        return _erro(request, "Página não encontrada.", 404)
    if exc.status_code == 405:
        return _erro(request, "Operação não permitida.", 405)
    return _erro(request, _OIDC_DEFAULT_MESSAGE if exc.status_code < 500 else "Algo deu errado.", exc.status_code)


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
        # reauth=1 (step-up) exige digitar o token de novo, como o prompt=login do IdP.
        if current_associado(request) is not None and reauth != "1":
            return RedirectResponse(destino, status_code=HTTP_303_SEE_OTHER)
        return templates.TemplateResponse(
            request, "stub_login.html", {"csrf": csrf_token(request), "next": destino, "tipos": TIPOS_STUB}
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
    tipo: str = Form("Efetivo"),
    next: str = Form("/area"),
    db: Session = Depends(get_session),
):
    if settings.auth_mode != "stub":
        return _erro(request, "Recurso indisponível.", 404)
    if not csrf_ok(request, csrf):
        return _erro(request, "Sessão expirada. Recarregue a página e tente novamente.", 400)
    destino = safe_next(next)
    if not secrets.compare_digest(token, settings.dev_stub_token or ""):
        audit.registrar(db, request, categoria="seguranca", tipo="login_stub_falha", severidade="aviso", status_http=403)
        return _erro(request, "Token de construção inválido.", 403)
    digits = "".join(ch for ch in cpf if ch.isdigit())
    if len(digits) != 11 or tipo not in TIPOS_STUB:
        return templates.TemplateResponse(
            request, "stub_login.html",
            {"csrf": csrf_token(request), "next": destino, "tipos": TIPOS_STUB,
             "error": "Informe um CPF com 11 dígitos e um tipo de associado da lista."},
            status_code=400,
        )
    sub = audit.hash_sub(f"stub:{digits}") or "stub"
    claims = AssociadoClaims(
        sub=sub, contact_id=contact_id_stub(digits), nome=" ".join(nome.split())[:160] or "Associado (stub)",
        email=email.strip()[:254] or None, cpf_mask=mask_cpf(digits), amr=["stub"], auth_time=int(time.time()),
        tipo=tipo, status="Ativo", num_contato=f"800{digits[:5]}", crm=str(100000 + int(digits[:5]) % 900000),
        crm_uf="SP", data_filiacao="2014-03-01",
    )
    store_identity(request, claims)
    audit.registrar(db, request, categoria="seguranca", tipo="login_stub", sub=sub,
                    contact_id=claims.contact_id, status_http=303)
    await run_in_threadpool(registrar_login, claims, origem="stub")
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
    await run_in_threadpool(registrar_login, claims, origem="userinfo")
    return RedirectResponse(pending["next"], status_code=HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Autenticado (a área em si é a SPA: app/spa.py + app/api/v1)                   #
# --------------------------------------------------------------------------- #
@app.post("/auth/logout")
async def auth_logout(request: Request, csrf: str = Form(""), db: Session = Depends(get_session)):
    associado = current_associado(request)
    if associado is None:
        request.session.clear()
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    if not csrf_ok(request, csrf):
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
    corpo = {"database": settings.db_name, "uso_falhas": uso.falhas(), "spa": spa.carregar_index() is not None}
    try:
        st = await run_in_threadpool(tls_status)
        return JSONResponse({"status": "ok", **corpo, "user": st.get("current_user"),
                             "ssl_version": st.get("Ssl_version"), "ssl_cipher": st.get("Ssl_cipher")})
    except SQLAlchemyError as exc:
        logger.error("db-health falhou: %s", exc)
        return JSONResponse({"status": "error", **corpo, "detail": "database unavailable"}, status_code=503)


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
