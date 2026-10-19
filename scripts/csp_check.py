"""Conferência dos cabeçalhos de segurança de uma instância em execução (RNF-01, RNF-22).

Uso:
    # dentro do container (rede Docker):
    docker compose exec area-associado python -m scripts.csp_check
    # contra outra base (ex.: túnel de construção):
    python -m scripts.csp_check --base https://minha.apm.org.br:8443 --inseguro

Não precisa de sessão: confere `/`, `/auth/login`, `/health`, `/api/v1/sessao` (401)
e `/area` (303). Sai com código 1 em qualquer divergência.
"""

from __future__ import annotations

import argparse
import ssl
import sys
import urllib.error
import urllib.request

_PROIBIDOS_NA_CSP = ("'unsafe-inline'", "'unsafe-eval'", "*", "http:", "data: 'self'")
_DIRETIVAS_OBRIGATORIAS = {
    "default-src": "'self'",
    "style-src": "'self'",
    "font-src": "'self'",
    "connect-src": "'self'",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "object-src": "'none'",
}


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003 - assinatura da stdlib
        return None


def _buscar(base: str, caminho: str, contexto: ssl.SSLContext | None) -> tuple[int, dict[str, str]]:
    abridor = urllib.request.build_opener(_SemRedirecionar, urllib.request.HTTPSHandler(context=contexto))
    try:
        with abridor.open(urllib.request.Request(base + caminho, method="GET"), timeout=10) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}


def avaliar_csp(csp: str) -> list[str]:
    """Devolve as divergências da CSP (vazia = conforme). Função pura."""
    problemas: list[str] = []
    diretivas: dict[str, list[str]] = {}
    for parte in filter(None, (p.strip() for p in csp.split(";"))):
        nome, *valores = parte.split()
        diretivas[nome] = valores
    for nome, esperado in _DIRETIVAS_OBRIGATORIAS.items():
        if diretivas.get(nome) != [esperado]:
            problemas.append(f"{nome} deveria ser exatamente {esperado}, veio {diretivas.get(nome)}")
    script = diretivas.get("script-src", [])
    if not script or script[0] != "'self'" or any(not v.startswith("'nonce-") for v in script[1:]):
        problemas.append(f"script-src deveria ser 'self' (+ nonce), veio {script}")
    for v in diretivas.get("img-src", []):
        if v not in ("'self'", "data:") and not v.startswith("https://"):
            problemas.append(f"img-src com origem não https: {v}")
    for proibido in _PROIBIDOS_NA_CSP:
        if any(proibido == v for valores in diretivas.values() for v in valores):
            problemas.append(f"valor proibido na CSP: {proibido}")
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--inseguro", action="store_true", help="não verificar o certificado (túnel/Origin CA)")
    args = parser.parse_args()
    contexto = ssl._create_unverified_context() if args.inseguro else None  # noqa: S323 - só por opção explícita
    base = args.base.rstrip("/")

    falhas: list[str] = []
    esperados = {"/": 200, "/auth/login": (200, 302), "/health": 200, "/api/v1/sessao": 401, "/area": 303}
    for caminho, status_ok in esperados.items():
        status, cab = _buscar(base, caminho, contexto)
        aceitos = status_ok if isinstance(status_ok, tuple) else (status_ok,)
        if status not in aceitos:
            falhas.append(f"{caminho}: status {status}, esperado {aceitos}")
        csp = cab.get("content-security-policy", "")
        falhas += [f"{caminho}: {p}" for p in (avaliar_csp(csp) if csp else ["sem Content-Security-Policy"])]
        for nome, valor in (("x-frame-options", "DENY"), ("x-content-type-options", "nosniff"),
                            ("referrer-policy", "no-referrer"), ("cache-control", "no-store")):
            if cab.get(nome) != valor:
                falhas.append(f"{caminho}: {nome} = {cab.get(nome)!r}, esperado {valor!r}")
        if not cab.get("x-request-id"):
            falhas.append(f"{caminho}: sem X-Request-Id")
        print(f"{caminho:<16} {status}  csp={'ok' if csp and not avaliar_csp(csp) else 'FALHA'}")
    for f in falhas:
        print(f"FALHA: {f}", file=sys.stderr)
    print("resultado : " + ("conforme" if not falhas else "NÃO CONFORME"))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
