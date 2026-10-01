"""Smoke do Relying Party: discovery, JWKS e coerência do client.

Uso (dentro do container):
    docker compose exec area-associado python -m scripts.check_oidc
Não imprime segredos. Sai com 1 em qualquer divergência.
"""

from __future__ import annotations

import sys

import certifi
import httpx

from app.config import get_settings
from app.oidc import JwksCache, OidcError


def main() -> int:
    s = get_settings()
    if s.auth_mode != "oidc":
        print(f"AUTH_MODE={s.auth_mode}: nada a verificar (modo interino).")
        return 0
    headers = {"Host": s.backchannel_host_header} if s.backchannel_host_header else {}
    ok = True
    print(f"issuer      : {s.effective_issuer}")
    print(f"backchannel : {s.effective_backchannel} (Host={headers.get('Host', '-')})")
    print(f"client_id   : {s.oidc_client_id}")
    print(f"redirect_uri: {s.redirect_uri}")
    print(f"scopes      : {' '.join(s.scope_list)}")
    try:
        with httpx.Client(timeout=s.oidc_http_timeout, verify=certifi.where(), headers=headers) as http:
            disc = http.get(f"{s.effective_backchannel}/.well-known/openid-configuration")
            disc.raise_for_status()
            doc = disc.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"FALHA: discovery indisponível ({type(exc).__name__})", file=sys.stderr)
        return 1
    if doc.get("issuer") != s.effective_issuer:
        print(f"FALHA: issuer do discovery = {doc.get('issuer')!r}", file=sys.stderr)
        ok = False
    for campo, esperado in (
        ("authorization_endpoint", f"{s.effective_issuer}/oauth/authorize"),
        ("token_endpoint", f"{s.effective_issuer}/oauth/token"),
        ("userinfo_endpoint", f"{s.effective_issuer}/oauth/userinfo"),
        ("jwks_uri", f"{s.effective_issuer}/oauth/jwks.json"),
    ):
        if doc.get(campo) != esperado:
            print(f"AVISO: {campo} = {doc.get(campo)!r} (esperado {esperado})", file=sys.stderr)
    if "S256" not in doc.get("code_challenge_methods_supported", []):
        print("FALHA: IdP não anuncia PKCE S256", file=sys.stderr)
        ok = False
    if "client_secret_basic" not in doc.get("token_endpoint_auth_methods_supported", []):
        print("FALHA: IdP não anuncia client_secret_basic", file=sys.stderr)
        ok = False
    faltam = set(s.scope_list) - set(doc.get("scopes_supported", s.scope_list))
    if faltam:
        print(f"AVISO: escopos não anunciados: {sorted(faltam)}", file=sys.stderr)
    try:
        kids = JwksCache(s).kids()
        print(f"jwks kids   : {kids}")
    except OidcError as exc:
        print(f"FALHA: JWKS ({exc.code})", file=sys.stderr)
        ok = False
    print("OK" if ok else "COM FALHAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
