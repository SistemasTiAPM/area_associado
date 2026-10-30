"""Prova de conexão ao RDS: usuário efetivo, TLS, privilégios e partições.

Uso (dentro do container):
    docker compose exec area-associado python -m scripts.db_check

Sai com código 1 se:
- a conexão não tiver cifra TLS;
- o usuário for a conta master do RDS, ou não tiver política aqui;
- os grants violarem a ADR-0004 (CLAUDE.md, regra 14):
  * no schema, só o que a política do usuário permite (`apm_area`: SELECT,
    INSERT, EXECUTE);
  * UPDATE só por tabela, e só nas tabelas da allowlist do usuário;
  * tabela da allowlist que EXISTE no schema sem o GRANT UPDATE (ADR-0004 §6:
    allowlist e grants divergiram — a migração foi aplicada pela metade);
  * DELETE, ALL ou DDL em lugar nenhum; nada em outros schemas;
- `evento_uso`/`evento_log` não estiverem particionadas com a `sql/008`
  registrada em `schema_migrations` (sem o registro é só aviso).

Avisos (não falham): `sql/008` ainda não aplicada; última partição mensal a
menos de 90 dias (criar as próximas — procedimento no cabeçalho da `sql/008`).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------- políticas
# Uma política por usuário de banco. A allowlist de UPDATE só lista tabelas
# JÁ MIGRADAS: tabela nova entra aqui NO MESMO commit da migração que concede
# o grant (ADR-0004 §2 e §6) — nunca antes, senão o item (b) acima vira ruído.
#
# `apm_area`        — processo web (sql/000): SELECT, INSERT, EXECUTE no schema;
#                     UPDATE em `associado` (005), `associado_perfil` (006),
#                     `email_verificacao` (007).
# `apm_area_bo`     — backoffice (ADR-0022, Onda 6): UPDATE em catálogo e
#                     configuração; a allowlist nasce com a migração dele.
# `apm_area_painel` — painéis (ADR-0022): só SELECT em views `vw_*`, nada no
#                     nível do schema, nenhum UPDATE em hipótese alguma.


@dataclass(frozen=True)
class Politica:
    privilegios_schema: frozenset[str]
    tabelas_com_update: frozenset[str] = frozenset()
    # O que um GRANT por tabela pode conter (além de UPDATE já coberto acima).
    privilegios_tabela: frozenset[str] = frozenset({"UPDATE"})
    # Padrão que o nome do objeto de um GRANT por tabela precisa casar (None = qualquer).
    padrao_objeto: re.Pattern[str] | None = field(default=None, compare=False)


POLITICAS: dict[str, Politica] = {
    "apm_area": Politica(
        privilegios_schema=frozenset({"SELECT", "INSERT", "EXECUTE"}),
        tabelas_com_update=frozenset({"associado", "associado_perfil", "email_verificacao"}),
    ),
    "apm_area_bo": Politica(
        privilegios_schema=frozenset({"SELECT", "INSERT", "EXECUTE"}),
        tabelas_com_update=frozenset(),  # ADR-0022: catálogo/configuração — entra com a migração
    ),
    "apm_area_painel": Politica(
        privilegios_schema=frozenset(),  # nada em `schema`.*
        tabelas_com_update=frozenset(),
        privilegios_tabela=frozenset({"SELECT"}),
        padrao_objeto=re.compile(r"^vw_[a-z0-9_]+$"),
    ),
}

# Compatibilidade: a allowlist do processo web continua exportada com este nome
# (docs/PROVISIONAMENTO.md, CLAUDE.md regra 14).
TABELAS_COM_UPDATE: frozenset[str] = POLITICAS["apm_area"].tabelas_com_update
PRIVILEGIOS_DO_SCHEMA: frozenset[str] = POLITICAS["apm_area"].privilegios_schema

# Tabelas que a sql/008 particiona; a versão registrada em schema_migrations.
TABELAS_PARTICIONADAS: frozenset[str] = frozenset({"evento_uso", "evento_log"})
MIGRACAO_PARTICAO = "008"
DIAS_AVISO_PARTICAO = 90

_RE_GRANT = re.compile(r"^GRANT\s+(?P<privs>.+?)\s+ON\s+(?P<alvo>\S+)\s+TO\s+", re.IGNORECASE)
_RE_COLUNAS = re.compile(r"\([^)]*\)")


def _privilegios(texto: str) -> set[str]:
    sem_colunas = _RE_COLUNAS.sub("", texto)
    return {" ".join(p.split()).upper() for p in sem_colunas.split(",") if p.strip()}


def _alvo(texto: str) -> tuple[str, str]:
    schema, _, tabela = texto.partition(".")
    return schema.strip("`"), tabela.strip("`")


def _politica(usuario: str) -> Politica | None:
    return POLITICAS.get(usuario.split("@", 1)[0].strip("'`"))


def grants_de_update(grants: list[str], schema: str) -> set[str]:
    """Tabelas de `schema` que aparecem em GRANT por tabela contendo UPDATE."""
    tabelas: set[str] = set()
    for linha in grants:
        m = _RE_GRANT.match(linha.strip())
        if not m:
            continue
        alvo_schema, tabela = _alvo(m.group("alvo"))
        if alvo_schema == schema and tabela != "*" and "UPDATE" in _privilegios(m.group("privs")):
            tabelas.add(tabela)
    return tabelas


def avaliar_grants(grants: list[str], schema: str, usuario: str = "apm_area") -> list[str]:
    """Devolve a lista de violações (vazia = conforme). Função pura, testável."""
    politica = _politica(usuario)
    if politica is None:
        return [f"usuário sem política no db_check ({usuario}); cadastrar em POLITICAS antes de usar"]
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
            extras = privs - politica.privilegios_schema
            if extras:
                permitido = sorted(politica.privilegios_schema) or "nada"
                violacoes.append(f"no nível do schema só {permitido}; encontrado {sorted(extras)}: {linha}")
            continue
        extras = privs - politica.privilegios_tabela - {"DELETE"}
        if extras:
            violacoes.append(f"privilégio de tabela além de {', '.join(sorted(politica.privilegios_tabela))} "
                             f"({sorted(extras)}): {linha}")
        if politica.padrao_objeto is not None and not politica.padrao_objeto.match(tabela):
            violacoes.append(f"objeto fora do padrão permitido ao usuário ({tabela}): {linha}")
        if "UPDATE" in privs and tabela not in politica.tabelas_com_update:
            violacoes.append(f"UPDATE em tabela fora da allowlist ({tabela}): {linha}")
    return violacoes


def avaliar_allowlist(grants: list[str], schema: str, tabelas_existentes: set[str],
                      usuario: str = "apm_area") -> list[str]:
    """ADR-0004 §6: tabela da allowlist que existe no schema e não tem o GRANT UPDATE.

    Tabela da allowlist ainda não criada não é violação (a migração não chegou).
    """
    politica = _politica(usuario)
    if politica is None:
        return []
    com_update = grants_de_update(grants, schema)
    return [f"tabela da allowlist existe sem GRANT UPDATE ({t}) — migração aplicada pela metade?"
            for t in sorted(politica.tabelas_com_update)
            if t in tabelas_existentes and t not in com_update]


def avaliar_particoes(migracoes: set[str], particoes: dict[str, list[tuple[str | None, str | None]]],
                      hoje_dias: int) -> tuple[list[str], list[str]]:
    """Confere a partição mensal de evento_uso/evento_log (sql/008).

    `particoes[tabela]` = lista `(PARTITION_NAME, PARTITION_DESCRIPTION)` de
    information_schema.PARTITIONS (tabela sem partição = um item `(None, None)`).
    `hoje_dias` = TO_DAYS(CURRENT_DATE). Devolve `(falhas, avisos)`.
    """
    falhas: list[str] = []
    avisos: list[str] = []
    registrada = MIGRACAO_PARTICAO in migracoes
    for tabela in sorted(TABELAS_PARTICIONADAS):
        itens = [(n, d) for n, d in particoes.get(tabela, []) if n]
        if not itens:
            if tabela in particoes:
                msg = f"{tabela} sem partição"
                (falhas if registrada else avisos).append(
                    msg + (f" com a sql/{MIGRACAO_PARTICAO} registrada em schema_migrations" if registrada
                           else f" (sql/{MIGRACAO_PARTICAO} ainda não aplicada)"))
            continue
        limites = [int(d) for _, d in itens if d and d.strip().isdigit()]
        if not limites:
            falhas.append(f"{tabela} particionada sem limite mensal legível (só MAXVALUE?)")
            continue
        if not any((d or "").strip().upper() == "MAXVALUE" for _, d in itens):
            falhas.append(f"{tabela} sem partição MAXVALUE (pMAX): INSERT fora da grade seria recusado")
        restante = max(limites) - hoje_dias
        if restante < 0:
            avisos.append(f"{tabela}: grade mensal vencida há {-restante} dias; linhas novas caem em pMAX "
                          f"— reorganizar (sql/{MIGRACAO_PARTICAO}, procedimento 1)")
        elif restante < DIAS_AVISO_PARTICAO:
            avisos.append(f"{tabela}: última partição mensal termina em {restante} dias — criar as próximas "
                          f"(sql/{MIGRACAO_PARTICAO}, procedimento 1)")
    return falhas, avisos


def main() -> int:
    from sqlalchemy import text

    from app.config import get_settings
    from app.database import engine, tls_status

    s = get_settings()
    st = tls_status()
    with engine.connect() as conn:
        grants = [r[0] for r in conn.execute(text("SHOW GRANTS"))]
        versao = conn.execute(text("SELECT VERSION()")).scalar_one()
        hoje_dias = int(conn.execute(text("SELECT TO_DAYS(CURRENT_DATE)")).scalar_one())
        tabelas = {r[0] for r in conn.execute(
            text("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = :s"), {"s": s.db_name})}
        migracoes: set[str] = set()
        if "schema_migrations" in tabelas:
            migracoes = {str(r[0]) for r in conn.execute(text("SELECT versao FROM schema_migrations"))}
        particoes: dict[str, list[tuple[str | None, str | None]]] = {}
        for nome, pnome, pdesc in conn.execute(text(
                "SELECT TABLE_NAME, PARTITION_NAME, PARTITION_DESCRIPTION FROM information_schema.PARTITIONS "
                "WHERE TABLE_SCHEMA = :s AND TABLE_NAME IN :t ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION"),
                {"s": s.db_name, "t": tuple(sorted(TABELAS_PARTICIONADAS))}):
            particoes.setdefault(nome, []).append((pnome, pdesc))

    usuario = str(st.get("current_user") or s.db_user)
    print(f"host      : {s.db_host}:{s.db_port}/{s.db_name}")
    print(f"usuario   : {usuario}")
    print(f"mysql     : {versao}")
    print(f"tls       : {st.get('Ssl_version') or '-'} {st.get('Ssl_cipher') or 'SEM CIFRA'}")
    for g in grants:
        print(f"grant     : {g}")
    print(f"tabelas   : {len(tabelas)} | migracoes: {', '.join(sorted(migracoes)) or '-'}")
    print("particoes : " + " ".join(
        f"{t}={sum(1 for n, _ in particoes.get(t, []) if n)}" for t in sorted(TABELAS_PARTICIONADAS)))

    ok = True
    if not st.get("Ssl_cipher"):
        print("FALHA: conexão sem TLS", file=sys.stderr)
        ok = False
    if usuario.startswith("apm_bd@"):
        print("FALHA: a aplicação está usando a conta master do RDS", file=sys.stderr)
        ok = False
    for v in avaliar_grants(grants, s.db_name, usuario):
        print(f"FALHA: {v}", file=sys.stderr)
        ok = False
    for v in avaliar_allowlist(grants, s.db_name, tabelas, usuario):
        print(f"FALHA: {v}", file=sys.stderr)
        ok = False
    falhas, avisos = avaliar_particoes(migracoes, particoes, hoje_dias)
    for v in falhas:
        print(f"FALHA: {v}", file=sys.stderr)
        ok = False
    for a in avisos:
        print(f"AVISO: {a}")
    print("resultado : " + ("conforme" if ok else "NÃO CONFORME"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
