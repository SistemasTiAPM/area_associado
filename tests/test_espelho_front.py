"""Espelhos servidor ↔ SPA ↔ SQL que não podem divergir em silêncio (TI-04, TI-13).

Lê os arquivos TypeScript e SQL como texto (sem Node): o contrato é um `type` de
literais, que este teste extrai por regex. Se o formato do `type` mudar, o teste
falha ruidosamente em vez de passar com um conjunto vazio.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import flags, uso

RAIZ = Path(__file__).resolve().parents[1]
_RE_LITERAL = re.compile(r"'([a-z][a-z0-9_]*)'")


def _uniao_de_literais(arquivo: Path, nome_tipo: str) -> set[str]:
    texto = arquivo.read_text(encoding="utf-8")
    bloco = re.search(rf"export type {nome_tipo} =\s*((?:\s*\|\s*'[a-z0-9_]+')+)\s*;", texto)
    assert bloco, f"`export type {nome_tipo}` não encontrado (ou fora do formato) em {arquivo}"
    valores = _RE_LITERAL.findall(bloco.group(1))
    assert valores and len(valores) == len(set(valores)), f"{nome_tipo} vazio ou com repetição"
    return set(valores)


def test_acoes_de_ui_iguais_entre_servidor_e_spa():
    front = _uniao_de_literais(RAIZ / "frontend/src/lib/analytics.ts", "AcaoUi")
    assert front == set(uso.ACOES_UI), {
        "so_no_front": sorted(front - uso.ACOES_UI), "so_no_servidor": sorted(uso.ACOES_UI - front),
    }


def test_chaves_de_flag_iguais_entre_servidor_spa_e_migracoes():
    front = _uniao_de_literais(RAIZ / "frontend/src/api/tipos.ts", "ChaveFlag")
    servidor = set(flags.FLAGS_CONHECIDAS)
    assert front == servidor, {"so_no_front": sorted(front - servidor), "so_no_servidor": sorted(servidor - front)}

    sql = ""
    for arquivo in sorted((RAIZ / "sql").glob("*.sql")):
        texto = arquivo.read_text(encoding="utf-8")
        if "INSERT INTO `feature_flag`" in texto:
            sql += texto
    semeadas = set(re.findall(r"^\s*\('([a-z][a-z0-9_]*)',\s*0,", sql, flags=re.MULTILINE))
    ligadas_no_seed = set(re.findall(r"^\s*\('([a-z][a-z0-9_]*)',\s*1,", sql, flags=re.MULTILINE))
    assert not ligadas_no_seed, f"flag nasce ligada no seed: {sorted(ligadas_no_seed)} (regra 19)"
    assert semeadas == servidor, {"so_no_sql": sorted(semeadas - servidor), "sem_seed": sorted(servidor - semeadas)}


def test_migracao_009_so_insere_desligadas_sem_grant_e_nao_toca_ligada():
    texto = (RAIZ / "sql/009_flags_v2.sql").read_text(encoding="utf-8")
    corpo = re.sub(r"--.*", "", texto)  # sem os comentários
    assert "GRANT" not in corpo.upper()
    assert "CREATE TABLE" not in corpo.upper() and "ALTER TABLE" not in corpo.upper()
    assert re.search(r"ON DUPLICATE KEY UPDATE\s+`descricao`\s*=\s*novo\.`descricao`\s*;", corpo)
    assert "ligada` = " not in corpo  # reexecução nunca religa/desliga
    novas = {"notificacoes", "encaminhamento_parceiro", "reservas", "inscricoes", "comunicacao_outbox",
             "cancelamento_online", "lgpd_consentimentos"}
    assert set(re.findall(r"\('([a-z_]+)',\s*0,", corpo)) == novas
