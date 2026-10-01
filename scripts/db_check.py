"""Prova de conexão ao RDS: usuário efetivo, TLS e privilégios.

Uso (dentro do container):
    docker compose exec area-associado python -m scripts.db_check
Sai com código 1 se não houver cifra TLS ou se o usuário for a conta master.
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from app.config import get_settings
from app.database import engine, tls_status


def main() -> int:
    s = get_settings()
    st = tls_status()
    with engine.connect() as conn:
        grants = [r[0] for r in conn.execute(text("SHOW GRANTS"))]
        versao = conn.execute(text("SELECT VERSION()")).scalar_one()
    print(f"host      : {s.db_host}:{s.db_port}/{s.db_name}")
    print(f"usuario   : {st.get('current_user')}")
    print(f"mysql     : {versao}")
    print(f"tls       : {st.get('Ssl_version') or '-'} {st.get('Ssl_cipher') or 'SEM CIFRA'}")
    for g in grants:
        print(f"grant     : {g}")
    ok = True
    if not st.get("Ssl_cipher"):
        print("FALHA: conexão sem TLS", file=sys.stderr)
        ok = False
    if str(st.get("current_user", "")).startswith("apm_bd@"):
        print("FALHA: a aplicação está usando a conta master do RDS", file=sys.stderr)
        ok = False
    if any(" ALL " in g.upper() or "UPDATE" in g.upper() or "DELETE" in g.upper() for g in grants):
        print("AVISO: usuário tem UPDATE/DELETE/ALL em nível de schema — rever grants", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
