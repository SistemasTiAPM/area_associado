"""Exporta o contrato OpenAPI da API como ARTEFATO versionado (TI-07, DEC-32).

A rota `/openapi.json` só existe com `APP_ENV=development` (e o edge devolve
403): a documentação vive em `docs/api/openapi.json`, gerada daqui e conferida
pelo teste `tests/test_openapi.py` e pelo build (`Dockerfile`).

Uso (na imagem ou num venv com requirements.txt):
    python -m scripts.openapi_export                 # grava docs/api/openapi.json
    python -m scripts.openapi_export --verificar     # sai 1 se o arquivo divergir
    python -m scripts.openapi_export --verificar /caminho/openapi.json

O app é instanciado com ambiente FICTÍCIO (igual ao de tests/conftest.py): sem
rede, sem banco, sem segredo real — o `.env` do diretório é ignorado porque
variáveis de ambiente vencem o arquivo. Saída determinística: chaves ordenadas,
indentação fixa, UTF-8, quebra final.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
DESTINO_PADRAO = RAIZ / "docs" / "api" / "openapi.json"

# Mesmo ambiente de tests/conftest.py: valores inventados, nenhum deles sai daqui.
AMBIENTE_FICTICIO: dict[str, str] = {
    "DB_HOST": "localhost",
    "DB_USER": "apm_area",
    "DB_PASS": "x",
    "DB_NAME": "area_associado",
    "DB_SSL_VERIFY": "0",
    "APP_ENV": "test",
    "SECRET_KEY": "s" * 48,
    "LOG_HASH_KEY": "l" * 48,
    "AUTH_MODE": "oidc",
    "OIDC_CLIENT_SECRET": "c" * 48,
    "OIDC_ISSUER": "https://login.apm.org.br",
    "OIDC_BACKCHANNEL_BASE_URL": "http://login_associado:8000",
    "PUBLIC_BASE_URL": "https://minha.apm.org.br",
    "HUB_MODE": "stub",
    "SMTP_MODE": "stub",
}


def _preparar_ambiente() -> None:
    # Força os valores fictícios (um `.env` local ou o ambiente do shell não
    # podem mudar o contrato gerado). Único lugar do projeto, fora de config.py,
    # que mexe em variáveis de ambiente — e só ESCREVE, para o Settings ler.
    os.environ.update(AMBIENTE_FICTICIO)


def gerar() -> dict[str, Any]:
    """Esquema OpenAPI do app, com `operation_id` únicos (senão levanta ValueError)."""
    _preparar_ambiente()
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app  # import tardio: depende do ambiente acima

    esquema = app.openapi()
    vistos: dict[str, str] = {}
    for caminho, metodos in esquema.get("paths", {}).items():
        for metodo, operacao in metodos.items():
            oid = operacao.get("operationId")
            if not oid:
                raise ValueError(f"rota sem operationId: {metodo.upper()} {caminho}")
            if oid in vistos:
                raise ValueError(f"operationId repetido: {oid!r} em {vistos[oid]} e {metodo.upper()} {caminho}")
            vistos[oid] = f"{metodo.upper()} {caminho}"
    return esquema


def serializar(esquema: dict[str, Any]) -> str:
    return json.dumps(esquema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def verificar(destino: Path) -> list[str]:
    """Devolve a lista de divergências (vazia = em dia)."""
    gerado = serializar(gerar())
    if not destino.is_file():
        return [f"{destino} não existe — gere com `python -m scripts.openapi_export`"]
    atual = destino.read_text(encoding="utf-8")
    if atual == gerado:
        return []
    import difflib

    diff = difflib.unified_diff(atual.splitlines(), gerado.splitlines(), "versionado", "gerado", lineterm="", n=2)
    linhas = list(diff)
    return linhas[:200] + ([f"... (+{len(linhas) - 200} linhas)"] if len(linhas) > 200 else [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verificar", nargs="?", const=str(DESTINO_PADRAO), metavar="ARQUIVO",
                        help="não grava: compara com o arquivo e sai 1 se divergir")
    parser.add_argument("--saida", default=str(DESTINO_PADRAO), help="arquivo a gravar (padrão: docs/api/openapi.json)")
    args = parser.parse_args(argv)

    if args.verificar:
        divergencias = verificar(Path(args.verificar))
        if divergencias:
            print("openapi: contrato versionado DIVERGE do código:", file=sys.stderr)
            print("\n".join(divergencias), file=sys.stderr)
            return 1
        print("openapi: em dia")
        return 0

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(serializar(gerar()), encoding="utf-8")
    print(f"openapi: gravado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
