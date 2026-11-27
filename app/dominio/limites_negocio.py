"""Limites de NEGÓCIO por contagem no banco, na transação do próprio negócio (ADR-0020).

Diferente de `app/limites.py` (janela em memória por processo, para abuso por
minuto — com 2 workers o teto efetivo dobra), estes tetos precisam ser exatos e
compartilhados entre workers: solicitação `outro` 5/dia, um pedido aberto por
tipo/finalidade, um cancelamento aberto por associado.

Como fica exato sob concorrência: `bloquear_associado` trava a linha do
associado (`SELECT ... FOR UPDATE` em `associado`, criada no login) no início
da transação de criação. Duas criações simultâneas do mesmo associado (dois
workers, duas abas) ficam em fila; a contagem que vem depois do bloqueio é uma
leitura consistente feita APÓS o bloqueio (no REPEATABLE READ do InnoDB o
snapshot nasce na primeira leitura não bloqueante), então enxerga o que a
concorrente acabou de comitar. Associados diferentes não se bloqueiam.

Identificadores de SQL nunca vêm de fora: tabela e colunas passam por
allowlist fechada aqui (regra 2).

Bloqueante (SQL): chamar dentro de uma transação aberta pelo domínio, que por
sua vez roda em `run_in_threadpool`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

logger = logging.getLogger("area_associado.limites_negocio")


@dataclass(frozen=True)
class Teto:
    maximo: int
    periodo: timedelta
    mensagem: str


# Tetos por tipo de serviço (REQUISITOS §7.4; D-17). Janela móvel de 24 h:
# não "zera à meia-noite" (rajada às 23h59 + 00h00 não dobra o teto).
TETOS_POR_TIPO: dict[str, Teto] = {
    "outro": Teto(5, timedelta(hours=24),
                  "Você já enviou 5 mensagens à Central nas últimas 24 horas. "
                  "Tente de novo amanhã ou fale com a Central pelo WhatsApp."),
}

STATUS_NAO_TERMINAIS: tuple[str, ...] = ("criada", "enviada", "em_atendimento", "pendente_associado")

# tabela → (coluna de data, colunas filtráveis). Fechado: nada vem do chamador.
_TABELAS: dict[str, tuple[str, frozenset[str]]] = {
    "solicitacao": ("criada_em", frozenset({"tipo_servico", "status"})),
    "titular_pedido": ("criado_em", frozenset({"tipo", "status"})),
}


class LimiteNegocioExcedido(Exception):
    """429 `limite_negocio`."""

    def __init__(self, mensagem: str) -> None:
        super().__init__("limite_negocio")
        self.mensagem = mensagem


class PedidoAbertoExistente(Exception):
    """409 `estado_invalido`: já existe pedido não terminal do mesmo tipo/alvo."""

    def __init__(self, mensagem: str) -> None:
        super().__init__("estado_invalido")
        self.mensagem = mensagem


def bloquear_associado(sess: Session, contact_id: str) -> bool:
    """Trava a linha do associado até o fim da transação. Devolve False se a
    linha não existe (login sem registro de acesso): a contagem continua
    valendo, só sem a serialização — o caso é registrado em log."""
    achou = sess.execute(text("SELECT 1 FROM associado WHERE contact_id = :c FOR UPDATE"),
                         {"c": contact_id}).first() is not None
    if not achou:
        logger.warning("limites_negocio: associado sem linha em `associado`; contagem sem bloqueio")
    return achou


def contar_no_periodo(sess: Session, *, tabela: str, contact_id: str, desde: datetime,
                      filtros: Mapping[str, Any] | None = None) -> int:
    """Linhas do associado na `tabela` com data ≥ `desde` e colunas = valores
    (valor tupla/lista = IN). Tabela e colunas só da allowlist."""
    if tabela not in _TABELAS:
        raise ValueError(f"tabela fora da allowlist de limites: {tabela!r}")
    coluna_data, filtraveis = _TABELAS[tabela]
    condicoes = ["contact_id = :contact_id", f"{coluna_data} >= :desde"]
    params: dict[str, Any] = {"contact_id": contact_id, "desde": desde}
    expandir: list[str] = []
    for i, (coluna, valor) in enumerate(sorted((filtros or {}).items())):
        if coluna not in filtraveis:
            raise ValueError(f"coluna fora da allowlist de limites: {coluna!r}")
        nome = f"f{i}"
        if isinstance(valor, (tuple, list, frozenset, set)):
            condicoes.append(f"{coluna} IN :{nome}")
            params[nome] = list(valor)
            expandir.append(nome)
        else:
            condicoes.append(f"{coluna} = :{nome}")
            params[nome] = valor
    sql = text(f"SELECT COUNT(*) FROM {tabela} WHERE " + " AND ".join(condicoes))
    if expandir:
        sql = sql.bindparams(*(bindparam(n, expanding=True) for n in expandir))
    return int(sess.execute(sql, params).scalar_one())


def exigir_abaixo_do_teto(sess: Session, *, contact_id: str, tipo_servico: str, agora: datetime) -> None:
    teto = TETOS_POR_TIPO.get(tipo_servico)
    if teto is None:
        return
    n = contar_no_periodo(sess, tabela="solicitacao", contact_id=contact_id, desde=agora - teto.periodo,
                          filtros={"tipo_servico": tipo_servico})
    if n >= teto.maximo:
        raise LimiteNegocioExcedido(teto.mensagem)


def abertas_do_tipo(sess: Session, *, contact_id: str, tipo_servico: str) -> list[dict[str, Any]]:
    """`dados` (já decodificado) das solicitações NÃO terminais do tipo — base da
    unicidade por tipo, por finalidade ou por campo (REQUISITOS §7.4)."""
    sql = text(
        "SELECT id, dados FROM solicitacao WHERE contact_id = :c AND tipo_servico = :t AND status IN :abertos"
    ).bindparams(bindparam("abertos", expanding=True))
    linhas = sess.execute(sql, {"c": contact_id, "t": tipo_servico, "abertos": list(STATUS_NAO_TERMINAIS)}).all()
    saida: list[dict[str, Any]] = []
    for r in linhas:
        dados = r.dados
        if isinstance(dados, (str, bytes)):
            dados = json.loads(dados)
        saida.append(dados if isinstance(dados, dict) else {})
    return saida


def exigir_unico_aberto(sess: Session, *, contact_id: str, tipo_servico: str,
                        conflita: Any = None, mensagem: str) -> None:
    """409 se houver pedido aberto do tipo. `conflita(dados_existentes) -> bool`
    restringe a unicidade (por finalidade, por campo); sem ele, qualquer aberto conflita."""
    for dados in abertas_do_tipo(sess, contact_id=contact_id, tipo_servico=tipo_servico):
        if conflita is None or conflita(dados):
            raise PedidoAbertoExistente(mensagem)
