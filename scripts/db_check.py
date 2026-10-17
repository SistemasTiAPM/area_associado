"""Prova de conexão ao RDS: usuário efetivo, TLS e privilégios.

Uso (dentro do container):
    docker compose exec area-associado python -m scripts.db_check

Sai com código 1 se:
- a conexão não tiver cifra TLS;
- o usuário for a conta master do RDS;
- os grants violarem a ADR-0004 (CLAUDE.md, regra 14):
  * no schema, só SELECT, INSERT, EXECUTE;
  * UPDATE só por tabela, e só nas tabelas de `TABELAS_COM_UPDATE`;
  * DELETE, ALL ou DDL em lugar nenhum; nada em outros schemas.
"""

from __future__ import annotations

import re
import sys

# REQUISITOS §6 — tabelas mutáveis pela aplicação. Tabela nova com UPDATE
# entra aqui NO MESMO commit da migração que concede o grant.
TABELAS_COM_UPDATE: frozenset[str] = frozenset({
    "associado",
    "associado_perfil",
    "solicitacao",
    "beneficio_ativacao",
    "noticia_cache",
    "evento_cache",
    "associado_tema",
    "noticia_salva",
    "evento_inscricao",
    "comunidade_adesao",
    "job_execucao",
    "email_verificacao",
})
PRIVILEGIOS_DO_SCHEMA: frozenset[str] = frozenset({"SELECT", "INSERT", "EXECUTE"})

_RE_GRANT = re.compile(r"^GRANT\s+(?P<privs>.+?)\s+ON\s+(?P<alvo>\S+)\s+TO\s+", re.IGNORECASE)
_RE_COLUNAS = re.compile(r"\([^)]*\)")


def _privilegios(texto: str) -> set[str]:
    sem_colunas = _RE_COLUNAS.sub("", texto)
    return {" ".join(p.split()).upper() for p in sem_colunas.split(",") if p.strip()}


def _alvo(texto: str) -> tuple[str, str]:
    schema, _, tabela = texto.partition(".")
    return schema.strip("`"), tabela.strip("`")


def avaliar_grants(grants: list[str], schema: str) -> list[str]:
    """Devolve a lista de violações (vazia = conforme). Função pura, testável."""
    violacoes: list[str] = []
    for linha in grants:
        m = _RE_GRANT.match(linha.strip())
        if not m:
            if linha.strip().upper().startswith("GRANT"):
                violacoes.append(f"grant não reconhecido: {linha}")
            continue  # REVOKE parcial, PROXY etc. não aparecem para este usuário
        privs = _privilegios(m.group("privs"))
        alvo_schema, tabela = _alvo(m.group("alvo"))
        if any(p.startswith("ALL") for p in privs):
            violacoes.append(f"ALL PRIVILEGES proibido: {linha}")
            continue
        if "DELETE" in privs:
            violacoes.append(f"DELETE proibido (ADR-0004): {linha}")
        if alvo_schema == "*":
            extras = privs - {"USAGE"}
            if extras:
                violacoes.append(f"privilégio global proibido ({', '.join(sorted(extras))}): {linha}")
            continue
        if alvo_schema != schema:
            violacoes.append(f"privilégio em outro schema ({alvo_schema}): {linha}")
            continue
        if tabela == "*":
            extras = privs - PRIVILEGIOS_DO_SCHEMA
            if extras:
                violacoes.append(f"no nível do schema só {sorted(PRIVILEGIOS_DO_SCHEMA)}; "
                                 f"encontrado {sorted(extras)}: {linha}")
            continue
        extras = privs - {"UPDATE"}
        if extras - {"DELETE"}:
            violacoes.append(f"privilégio de tabela além de UPDATE ({sorted(extras)}): {linha}")
        if "UPDATE" in privs and tabela not in TABELAS_COM_UPDATE:
            violacoes.append(f"UPDATE em tabela fora da allowlist ({tabela}): {linha}")
    return violacoes


def main() -> int:
    from sqlalchemy import text

    from app.config import get_settings
    from app.database import engine, tls_status

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
    for v in avaliar_grants(grants, s.db_name):
        print(f"FALHA: {v}", file=sys.stderr)
        ok = False
    print("resultado : " + ("conforme" if ok else "NÃO CONFORME"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
