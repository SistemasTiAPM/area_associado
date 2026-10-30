"""Políticas comuns aos jobs: recuo das outboxes, classificação de erro e
resumo de erro seguro para `job_execucao.erro_resumo`.

Outbox (REQUISITOS §7.5; ADR-0003 §5): depois da falha nº *t* (1-based), a
próxima tentativa sai em `RECUO_MINUTOS[t-1]` minutos; a falha nº
`MAX_TENTATIVAS` (10) marca `falhou` e gera `evento_log` severidade `erro`
(reprocessamento manual: docs/JOBS.md §5). Erro **permanente** (entrada
recusada, destinatário recusado, registro inexistente) vai direto a `falhou`.
Erro **sistêmico** (limite de taxa, credencial, escrita desligada, fonte fora
várias vezes seguidas) para a rodada inteira — disjuntor: os itens que não
foram tentados não gastam tentativa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..integracoes.email import EmailError
from ..integracoes.hub import HubError

RECUO_MINUTOS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 60, 60, 60, 60)
MAX_TENTATIVAS = len(RECUO_MINUTOS)  # 10
# Falhas transitórias SEGUIDAS na mesma rodada que acionam o disjuntor.
DISJUNTOR_SEGUIDAS = 3

PERMANENTE, TRANSITORIO, SISTEMICO = "permanente", "transitorio", "sistemico"

_HUB_PERMANENTES = frozenset({"entrada_invalida", "nao_encontrado"})
_HUB_SISTEMICOS = frozenset({"limite_taxa", "edicao_desligada"})


@dataclass(frozen=True)
class Falha:
    classe: str     # permanente | transitorio | sistemico
    codigo: str     # curto, nosso: ^[a-z][a-z0-9_]{0,47}$ (vai para erro_codigo / detalhes)


def proxima_tentativa(tentativas_feitas: int, agora: datetime) -> datetime | None:
    """Quando tentar de novo depois de `tentativas_feitas` falhas (1-based).
    None = esgotou (`falhou`)."""
    if tentativas_feitas < 1:
        raise ValueError("tentativas_feitas começa em 1")
    if tentativas_feitas >= MAX_TENTATIVAS:
        return None
    return agora + timedelta(minutes=RECUO_MINUTOS[tentativas_feitas - 1])


_RE_CODIGO = re.compile(r"[^a-z0-9_]+")


def codigo_seguro(valor: str | None, padrao: str = "erro") -> str:
    texto = _RE_CODIGO.sub("_", (valor or "").lower()).strip("_")[:48]
    return texto if texto and texto[0].isalpha() else padrao


def classificar_hub(exc: HubError) -> Falha:
    codigo = codigo_seguro(exc.codigo, "hub_erro")
    if exc.codigo in _HUB_PERMANENTES:
        return Falha(PERMANENTE, codigo)
    if exc.codigo in _HUB_SISTEMICOS:
        return Falha(SISTEMICO, codigo)
    return Falha(TRANSITORIO, codigo)


def classificar_email(exc: EmailError) -> Falha:
    codigo = codigo_seguro(getattr(exc, "codigo", None), "smtp_indisponivel")
    if getattr(exc, "permanente", False):
        return Falha(PERMANENTE, codigo)
    if getattr(exc, "sistemica", False):
        return Falha(SISTEMICO, codigo)
    return Falha(TRANSITORIO, codigo)


# Mesmo espírito dos CHECKs da sql/011: nada com cara de CPF ou de credencial.
_RE_CPF = re.compile(r"(^|[^0-9a-f])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)")
_RE_CREDENCIAL = re.compile(
    r"(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}|(senha|password|passwd|secret|segredo|token|authorization|api[_-]?key)\s*[:=]",
    re.IGNORECASE,
)
_RE_SEGURO = re.compile(r"[^A-Za-z0-9 _.:,;()/<>=+-]")


def resumo_erro(exc: BaseException | None = None, *, contexto: str | None = None) -> str:
    """Resumo curto para `job_execucao.erro_resumo`: tipo da exceção + código
    nosso. NUNCA `str(exc)` de terceiro (driver, httpx, SMTP: podem ecoar
    SQL, URL com credencial ou corpo de resposta)."""
    partes: list[str] = []
    if contexto:
        partes.append(contexto)
    if exc is not None:
        partes.append(type(exc).__name__)
        codigo = getattr(exc, "codigo", None)
        if isinstance(codigo, str):
            partes.append(codigo_seguro(codigo))
        orig = getattr(exc, "orig", None)  # SQLAlchemy DBAPIError: só o número do erro do MySQL
        args = getattr(orig, "args", None)
        if args and isinstance(args[0], int):
            partes.append(f"mysql_{args[0]}")
    texto = _RE_SEGURO.sub(" ", ": ".join(partes))
    texto = " ".join(texto.split())[:500]
    if _RE_CPF.search(texto) or _RE_CREDENCIAL.search(texto):
        return "erro (resumo omitido)"
    return texto or "erro"
