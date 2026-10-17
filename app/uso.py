"""Eventos de uso — analytics da Minha APM (ADR-0012, REQUISITOS §8).

Spec: "cada resgate vira dado" → `{associadoId, acao, entidade, id, timestamp}`.
Aqui: `evento_uso(contact_id, sub_hash, acao, entidade, entidade_id, origem,
request_id, detalhes, ocorrido_em)`, append-only por privilégio.

Garantias:
- `acao` só do catálogo fechado `CATALOGO`; entidade e origem conferidas.
- Eventos de origem `ui` (vêm do navegador): `entidade_id` com formato
  restrito e `detalhes` só com chaves tipadas por ação — nenhum texto livre
  (o termo de busca, por exemplo, nunca é gravado). A identidade vem SEMPRE
  da sessão, nunca do corpo.
- Transação PRÓPRIA (nunca a sessão da rota: `audit.registrar` comita a sessão
  recebida e acoplaria as duas). Chamar depois do commit do negócio.
- Nunca lança. Toda falha vai para o log e para o contador `falhas()`,
  exposto em `/db-health`.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .audit import _PROIBIDAS, hash_sub

logger = logging.getLogger("area_associado.uso")

ORIGENS = ("servidor", "ui", "job", "publico")
LOTE_MAX = 20
_DETALHES_MAX = 2000

_RE_ENTIDADE_ID = re.compile(r"^[A-Za-z0-9_/.:-]{1,64}$")
_RE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_RE_ROTA = re.compile(r"^/area(/[a-z0-9-]{1,32}){0,3}$")
_RE_HEX16 = re.compile(r"^[0-9a-f]{16}$")
# Mesmo padrão do CHECK de sql/004: barra CPF (com ou sem pontuação) em
# `detalhes` ANTES do banco — senão o CHECK recusaria o lote inteiro.
_RE_CPF = re.compile(r"(^|[^0-9a-fA-F])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9a-fA-F]|$)")


def _inteiro(valor: Any) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= 1_000_000:
        return None
    return valor


def _regex(padrao: re.Pattern[str]) -> Callable[[Any], str | None]:
    def validar(valor: Any) -> str | None:
        return valor if isinstance(valor, str) and padrao.match(valor) else None

    return validar


_INT = _inteiro
_SLUG = _regex(_RE_SLUG)
_ROTA = _regex(_RE_ROTA)
_HEX16 = _regex(_RE_HEX16)


@dataclass(frozen=True)
class Acao:
    entidades: frozenset[str]
    origens: frozenset[str]
    # Só para origem `ui`: chave → validador (devolve o valor limpo ou None).
    detalhes_ui: dict[str, Callable[[Any], Any]] = field(default_factory=dict)


def _a(entidades: str, origens: str, **detalhes_ui: Callable[[Any], Any]) -> Acao:
    return Acao(frozenset(entidades.split()), frozenset(origens.split()), detalhes_ui)


# REQUISITOS §8 — ação nova = linha nova aqui E na tabela do documento.
CATALOGO: dict[str, Acao] = {
    "pagina_ver": _a("rota", "ui"),
    "busca_global": _a("rota", "ui", resultados=_INT, tamanho=_INT),
    "filtro_aplicar": _a("beneficio noticia", "ui", filtro=_SLUG),
    "categoria_abrir": _a("beneficio_categoria", "ui"),
    "beneficio_ativar": _a("beneficio", "servidor"),
    "beneficio_desativar": _a("beneficio", "servidor"),
    "beneficio_gerenciar": _a("beneficio", "ui"),
    "beneficio_abrir": _a("beneficio", "ui"),
    "totalpass_abrir": _a("beneficio", "ui"),
    "plantoes_abrir": _a("beneficio", "ui"),
    "clube_oferta_usar": _a("oferta", "ui"),
    "noticia_abrir": _a("noticia", "ui"),
    "noticia_salvar": _a("noticia", "servidor"),
    "noticia_dessalvar": _a("noticia", "servidor"),
    "tema_seguir": _a("tema", "servidor"),
    "tema_deixar": _a("tema", "servidor"),
    "evento_inscrever": _a("evento", "servidor"),
    "congresso_garantir_vaga": _a("evento", "servidor"),
    "congresso_programacao_abrir": _a("evento", "ui"),
    "comunidade_entrar": _a("comunidade", "servidor"),
    "comunidade_abrir": _a("comunidade", "ui"),
    "programa_saber_mais": _a("comunidade", "ui"),
    "rede_entrar": _a("comunidade", "servidor"),
    "solicitacao_criar": _a("solicitacao", "servidor"),
    "solicitacao_cancelar": _a("solicitacao", "servidor"),
    "solicitacao_responder": _a("solicitacao", "servidor"),
    "solicitacao_status_alterado": _a("solicitacao", "job"),
    "onboarding_passo_concluir": _a("onboarding_passo", "servidor"),
    "perfil_contato_atualizar": _a("associado_perfil", "servidor"),
    "perfil_foto_atualizar": _a("associado_perfil", "servidor"),
    "carteirinha_compartilhar": _a("carteirinha", "servidor"),
    "carteirinha_verificar": _a("carteirinha", "publico"),
    "wallet_adicionar": _a("carteirinha", "ui"),
    "fatura_pdf_baixar": _a("fatura", "servidor"),
    "central_whatsapp_abrir": _a("central", "ui"),
    "erro_exibido": _a("rota", "ui", codigo=_SLUG, request_id=_HEX16, rota=_ROTA),
}

ACOES_UI: frozenset[str] = frozenset(nome for nome, a in CATALOGO.items() if "ui" in a.origens)


@dataclass(frozen=True)
class Evento:
    acao: str
    entidade: str
    entidade_id: str | None = None
    detalhes: dict[str, Any] | None = None


_falhas = 0
_falhas_lock = threading.Lock()


def falhas() -> int:
    with _falhas_lock:
        return _falhas


def _contar_falha() -> None:
    global _falhas
    with _falhas_lock:
        _falhas += 1


def _validar(evento: Evento, origem: str) -> tuple[str | None, str | None]:
    """Devolve (entidade_id limpo, detalhes JSON) ou levanta ValueError."""
    acao = CATALOGO.get(evento.acao)
    if acao is None:
        raise ValueError("acao_desconhecida")
    if origem not in ORIGENS or origem not in acao.origens:
        raise ValueError("origem_invalida")
    if evento.entidade not in acao.entidades:
        raise ValueError("entidade_invalida")
    entidade_id = evento.entidade_id
    if entidade_id is not None and not _RE_ENTIDADE_ID.match(entidade_id):
        raise ValueError("entidade_id_invalido")

    detalhes: dict[str, Any] = {}
    if origem == "ui":
        for chave, validador in acao.detalhes_ui.items():
            valor = validador((evento.detalhes or {}).get(chave))
            if valor is not None:
                detalhes[chave] = valor
    elif evento.detalhes:
        detalhes = {k: v for k, v in evento.detalhes.items() if isinstance(k, str) and k.lower() not in _PROIBIDAS}
    dump = json.dumps(detalhes, ensure_ascii=False, default=str) if detalhes else None
    if dump is not None and _RE_CPF.search(dump):
        raise ValueError("detalhes_com_cpf")
    if dump is not None and len(dump) > _DETALHES_MAX:
        dump = json.dumps({"truncado": True})
    return entidade_id, dump


_SQL = text(
    "INSERT INTO evento_uso (contact_id, sub_hash, acao, entidade, entidade_id, origem, request_id, detalhes) "
    "VALUES (:contact_id, :sub_hash, :acao, :entidade, :entidade_id, :origem, :request_id, :detalhes)"
)


def _gravar(linhas: list[dict[str, Any]]) -> None:
    from .database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        db.execute(_SQL, linhas)


def registrar_lote(
    eventos: Iterable[Evento],
    *,
    contact_id: str | None,
    sub: str | None,
    origem: str,
    request_id: str | None,
) -> tuple[int, int]:
    """Grava os eventos válidos numa transação. Devolve (gravados, descartados). Nunca lança."""
    linhas: list[dict[str, Any]] = []
    descartados = 0
    sub_hash = hash_sub(sub)
    for evento in eventos:
        try:
            entidade_id, detalhes = _validar(evento, origem)
        except ValueError as exc:
            descartados += 1
            logger.warning("uso: evento descartado (%s): acao=%.48s", exc, evento.acao)
            continue
        linhas.append({
            "contact_id": contact_id, "sub_hash": sub_hash, "acao": evento.acao, "entidade": evento.entidade,
            "entidade_id": entidade_id, "origem": origem, "request_id": request_id, "detalhes": detalhes,
        })
    if not linhas:
        return 0, descartados
    try:
        _gravar(linhas)
    except SQLAlchemyError as exc:
        _contar_falha()
        logger.error("uso: falha ao gravar %d evento(s): %s", len(linhas), type(exc).__name__)
        return 0, descartados + len(linhas)
    return len(linhas), descartados


def registrar(
    acao: str,
    entidade: str,
    entidade_id: str | None = None,
    *,
    contact_id: str | None,
    sub: str | None,
    origem: str = "servidor",
    request_id: str | None = None,
    detalhes: dict[str, Any] | None = None,
) -> bool:
    gravados, _ = registrar_lote(
        [Evento(acao, entidade, entidade_id, detalhes)],
        contact_id=contact_id, sub=sub, origem=origem, request_id=request_id,
    )
    return gravados == 1
