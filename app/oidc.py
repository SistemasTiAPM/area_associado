"""Relying Party OIDC do login.apm.org.br (Authorization Code + PKCE S256).

Módulo sem FastAPI e sem sessão: recebe e devolve dados. A rota (main.py) é
quem guarda o pedido pendente no cookie e chama `login_from_callback`.

Decisões:
- `httpx` + `pyjwt` em vez de biblioteca OIDC: o IdP é nosso, o contrato é
  conhecido e as ~200 linhas abaixo são auditáveis. `algorithms=["RS256"]`
  fixo fecha confusão de algoritmo; `kid` desconhecido força UM refetch do JWKS
  (rotação de chave em 3 fases do IdP).
- Back-channel pela rede Docker (`OIDC_BACKCHANNEL_BASE_URL`) com `Host` do
  issuer: o `iss` do token continua `https://login.apm.org.br`.
- Sem refresh token: a área não chama API alguma depois do login; sessão
  própria por cookie, e SSO silencioso no IdP quando ela expira.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import certifi
import httpx
import jwt
from jwt import PyJWK

from .config import Settings, get_settings

logger = logging.getLogger("area_associado.oidc")

_ALGS = ["RS256"]
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "sub", "aud", "nonce", "auth_time"]
_SUB_MAX = 255


class OidcError(Exception):
    """Erro do fluxo, com código estável para auditoria e mapa HTTP na rota."""

    def __init__(self, code: str, detail: str = "", *, http_status: int = 400) -> None:
        super().__init__(detail or code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    id_token: str
    token_type: str
    expires_in: int | None


@dataclass
class AssociadoClaims:
    sub: str
    contact_id: str | None
    nome: str | None
    email: str | None
    cpf_mask: str | None
    amr: list[str] = field(default_factory=list)
    auth_time: int | None = None
    id_token: str = ""  # guardado na sessão só para o `id_token_hint` do logout
    # Escopo `carteirinha` (rótulos/valores do CRM via IdP). Com o escopo
    # pedido, tipo e status são OBRIGATÓRIOS (P-20: recusa o login sem eles).
    tipo: str | None = None
    status: str | None = None
    num_contato: str | None = None
    crm: str | None = None
    crm_uf: str | None = None
    data_filiacao: str | None = None  # AAAA-MM-DD


# --------------------------------------------------------------------------- #
# PKCE / pedido pendente / URL de autorização                                   #
# --------------------------------------------------------------------------- #
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce() -> tuple[str, str]:
    """(code_verifier, code_challenge) conforme RFC 7636, método S256."""
    verifier = _b64url(secrets.token_bytes(64))  # 86 chars, dentro de 43..128
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_pending(next_path: str, settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    verifier, challenge = generate_pkce()
    return {
        "st": secrets.token_urlsafe(32),
        "nonce": secrets.token_urlsafe(32),
        "cv": verifier,
        "cc": challenge,
        "exp": int(time.time()) + s.oidc_pending_ttl,
        "next": next_path,
    }


def pending_is_valid(pending: object) -> bool:
    return (
        isinstance(pending, dict)
        and all(isinstance(pending.get(k), str) and pending[k] for k in ("st", "nonce", "cv", "cc", "next"))
        and isinstance(pending.get("exp"), int)
        and pending["exp"] >= int(time.time())
    )


def authorize_url(
    pending: dict, *, reauth: bool = False, silencioso: bool = False, settings: Settings | None = None
) -> str:
    s = settings or get_settings()
    params = {
        "response_type": "code",
        "client_id": s.oidc_client_id,
        "redirect_uri": s.redirect_uri,
        "scope": " ".join(s.scope_list),
        "state": pending["st"],
        "nonce": pending["nonce"],
        "code_challenge": pending["cc"],
        "code_challenge_method": "S256",
    }
    if reauth:
        params["prompt"] = "login"
    elif silencioso:
        # Sem interação: com sessão no IdP volta com code; sem, com error=login_required.
        params["prompt"] = "none"
    return f"{s.effective_issuer}/oauth/authorize?{urlencode(params)}"


# --------------------------------------------------------------------------- #
# HTTP de back-channel                                                          #
# --------------------------------------------------------------------------- #
def _client(s: Settings) -> httpx.Client:
    headers = {"Accept": "application/json", "User-Agent": "area-associado/1.0"}
    if s.backchannel_host_header:
        headers["Host"] = s.backchannel_host_header
    return httpx.Client(
        timeout=httpx.Timeout(s.oidc_http_timeout),
        verify=certifi.where(),
        headers=headers,
        follow_redirects=False,
    )


def exchange_code(code: str, verifier: str, *, settings: Settings | None = None) -> TokenSet:
    """Troca o authorization code no /oauth/token (client_secret_basic)."""
    s = settings or get_settings()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": s.redirect_uri,
        "code_verifier": verifier,
    }
    try:
        with _client(s) as http:
            resp = http.post(
                f"{s.effective_backchannel}/oauth/token",
                data=data,
                # O IdP impõe o método registrado: Basic, e NUNCA client_secret no corpo.
                auth=(s.oidc_client_id, s.oidc_client_secret or ""),
            )
    except httpx.HTTPError as exc:
        logger.error("token: falha de rede com o IdP: %s", type(exc).__name__)
        raise OidcError("token_unreachable", http_status=502) from exc

    if resp.status_code != 200:
        err = _safe_error(resp)
        logger.warning("token: IdP respondeu %s (%s)", resp.status_code, err)
        # invalid_grant = code já consumido/expirado: pede login de novo.
        status = 400 if err in ("invalid_grant", "invalid_request") else 502
        raise OidcError(f"token_{err}", http_status=status)

    try:
        body = resp.json()
    except ValueError as exc:
        raise OidcError("token_malformed", http_status=502) from exc

    access = body.get("access_token")
    idt = body.get("id_token")
    ttype = str(body.get("token_type", ""))
    if not isinstance(access, str) or not isinstance(idt, str) or ttype.lower() != "bearer":
        raise OidcError("token_malformed", http_status=502)
    expires = body.get("expires_in")
    return TokenSet(access, idt, ttype, int(expires) if isinstance(expires, int) else None)


def _safe_error(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", "")
    except ValueError:
        return "http_error"
    err = str(err)[:40]
    return err if err.replace("_", "").isalnum() else "http_error"


# --------------------------------------------------------------------------- #
# JWKS                                                                          #
# --------------------------------------------------------------------------- #
class JwksCache:
    """Cache thread-safe das chaves públicas do IdP, com refetch único por `kid`
    desconhecido (rotação) e sem tempestade de requisições sob concorrência."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._lock = threading.Lock()
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at = 0.0

    def _fetch(self) -> None:
        try:
            with _client(self._s) as http:
                resp = http.get(f"{self._s.effective_backchannel}/oauth/jwks.json")
                resp.raise_for_status()
                doc = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("jwks: falha ao obter chaves: %s", type(exc).__name__)
            raise OidcError("jwks_unavailable", http_status=503) from exc
        keys: dict[str, PyJWK] = {}
        for k in doc.get("keys", []) if isinstance(doc, dict) else []:
            if not isinstance(k, dict) or k.get("kty") != "RSA" or not k.get("kid"):
                continue
            if k.get("use", "sig") != "sig" or k.get("alg", "RS256") != "RS256":
                continue
            try:
                keys[str(k["kid"])] = PyJWK(k, algorithm="RS256")
            except jwt.PyJWTError:
                logger.warning("jwks: chave kid=%s ignorada (inválida)", k.get("kid"))
        if not keys:
            raise OidcError("jwks_empty", http_status=503)
        self._keys = keys
        self._fetched_at = time.monotonic()

    def key_for(self, kid: str) -> PyJWK:
        with self._lock:
            stale = (time.monotonic() - self._fetched_at) > self._s.oidc_jwks_ttl
            if stale or not self._keys:
                self._fetch()
            key = self._keys.get(kid)
            if key is None and not stale:
                # kid novo dentro do TTL: uma única tentativa de atualizar.
                self._fetch()
                key = self._keys.get(kid)
        if key is None:
            raise OidcError("id_token_unknown_kid", http_status=502)
        return key

    def kids(self) -> list[str]:
        with self._lock:
            if not self._keys:
                self._fetch()
            return sorted(self._keys)


_jwks: JwksCache | None = None
_jwks_lock = threading.Lock()


def jwks_cache() -> JwksCache:
    global _jwks
    with _jwks_lock:
        if _jwks is None:
            _jwks = JwksCache()
        return _jwks


# --------------------------------------------------------------------------- #
# id_token                                                                      #
# --------------------------------------------------------------------------- #
def validate_id_token(idt: str, *, nonce: str, settings: Settings | None = None,
                      cache: JwksCache | None = None) -> dict:
    s = settings or get_settings()
    cache = cache or jwks_cache()
    try:
        header = jwt.get_unverified_header(idt)
    except jwt.PyJWTError as exc:
        raise OidcError("id_token_invalid", "header") from exc
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise OidcError("id_token_invalid", "alg/kid")

    key = cache.key_for(header["kid"])
    try:
        claims = jwt.decode(
            idt,
            key=key.key,
            algorithms=_ALGS,
            issuer=s.effective_issuer,
            audience=s.oidc_client_id,
            leeway=s.oidc_leeway,
            options={"require": _REQUIRED_CLAIMS, "verify_signature": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise OidcError("id_token_expired") from exc
    except jwt.PyJWTError as exc:
        logger.warning("id_token rejeitado: %s", type(exc).__name__)
        raise OidcError("id_token_invalid", type(exc).__name__) from exc

    azp = claims.get("azp")
    if azp is not None and azp != s.oidc_client_id:
        raise OidcError("id_token_invalid", "azp")
    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not hmac.compare_digest(token_nonce, nonce):
        raise OidcError("id_token_nonce_mismatch")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > _SUB_MAX:
        raise OidcError("id_token_invalid", "sub")
    return claims


# --------------------------------------------------------------------------- #
# userinfo                                                                      #
# --------------------------------------------------------------------------- #
def fetch_userinfo(access_token: str, *, expected_sub: str, settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    try:
        with _client(s) as http:
            resp = http.get(
                f"{s.effective_backchannel}/oauth/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        logger.error("userinfo: falha de rede com o IdP: %s", type(exc).__name__)
        raise OidcError("userinfo_unreachable", http_status=502) from exc

    if resp.status_code == 503:
        # CRM fora: o IdP não entrega claims parciais, e nós não abrimos sessão parcial.
        raise OidcError("userinfo_unavailable", http_status=503)
    if resp.status_code != 200:
        raise OidcError("userinfo_http", str(resp.status_code), http_status=502)
    try:
        claims = resp.json()
    except ValueError as exc:
        raise OidcError("userinfo_malformed", http_status=502) from exc
    if not isinstance(claims, dict):
        raise OidcError("userinfo_malformed", http_status=502)
    sub = claims.get("sub")
    if not isinstance(sub, str) or not hmac.compare_digest(sub, expected_sub):
        raise OidcError("userinfo_sub_mismatch", http_status=502)
    return claims


def mask_cpf(value: object) -> str | None:
    """`***.456.789-**`: só os 6 dígitos do meio sobrevivem à sessão."""
    if not isinstance(value, str):
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 11:
        return None
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def _text(claims: dict, key: str, limit: int = 160) -> str | None:
    v = claims.get(key)
    if not isinstance(v, str):
        return None
    v = " ".join(v.split())
    return v[:limit] or None


# --------------------------------------------------------------------------- #
# Orquestração do callback                                                      #
# --------------------------------------------------------------------------- #
def login_from_callback(params: dict, pending: dict, *, settings: Settings | None = None) -> AssociadoClaims:
    """Valida state/iss, troca o code, valida o id_token e lê o userinfo.

    Lança `OidcError` em qualquer desvio; nunca devolve identidade parcial.
    """
    s = settings or get_settings()

    error = params.get("error")
    if isinstance(error, str) and error:
        code = error[:40] if error.replace("_", "").isalnum() else "unknown"
        status = {"access_denied": 403, "temporarily_unavailable": 503, "server_error": 502}.get(code, 400)
        raise OidcError(f"idp_{code}", http_status=status)

    state = params.get("state")
    if not isinstance(state, str) or not hmac.compare_digest(state, pending["st"]):
        raise OidcError("state_mismatch")

    # RFC 9207: se o IdP ecoa `iss`, tem de ser o nosso.
    iss = params.get("iss")
    if iss is not None and iss != s.effective_issuer:
        raise OidcError("issuer_mismatch")

    code = params.get("code")
    if not isinstance(code, str) or not code or len(code) > 512:
        raise OidcError("code_missing")

    tokens = exchange_code(code, pending["cv"], settings=s)
    claims = validate_id_token(tokens.id_token, nonce=pending["nonce"], settings=s)
    sub = claims["sub"]

    info = fetch_userinfo(tokens.access_token, expected_sub=sub, settings=s)

    amr = claims.get("amr")
    amr_list = [a for a in amr if isinstance(a, str)][:8] if isinstance(amr, list) else []
    contact_id = claims.get("contact_id") or info.get("contact_id")
    auth_time = claims.get("auth_time")
    carteirinha = _carteirinha(info) if "carteirinha" in s.scope_list else {}
    return AssociadoClaims(
        sub=sub,
        contact_id=str(contact_id)[:64] if contact_id else None,
        nome=_text(info, "name"),
        email=_text(info, "email", 254),
        cpf_mask=mask_cpf(info.get("cpf")),
        amr=amr_list,
        auth_time=int(auth_time) if isinstance(auth_time, int) else None,
        id_token=tokens.id_token,
        **carteirinha,
    )


_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_NUM = re.compile(r"^[0-9A-Za-z./-]{1,20}$")


def _carteirinha(info: dict) -> dict[str, str | None]:
    """Claims do escopo `carteirinha`. Sem tipo ou situação: recusa (P-20).

    Fail-closed por decisão de negócio: cadastro incompleto no CRM não abre
    sessão, para a área nunca decidir persona por palpite.
    """
    tipo = _text(info, "tipo_associado", 40)
    status = _text(info, "associado", 40)
    if not tipo or not status:
        raise OidcError("persona_incompleta", http_status=403)
    num = _text(info, "num_contato", 20)
    crm = _text(info, "crm", 20)
    data = _text(info, "data_filiacao", 10)
    return {
        "tipo": tipo,
        "status": status,
        "num_contato": num if num and _RE_NUM.match(num) else None,
        "crm": crm if crm and _RE_NUM.match(crm) else None,
        "crm_uf": _text(info, "crm_uf", 2),
        "data_filiacao": data if data and _RE_DATA.match(data) else None,
    }
