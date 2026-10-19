"""Perfil do associado: cache local (`associado_perfil`) do cadastro do CRM.

O CRM é a verdade (ADR-0002). Este módulo:
- grava no login os campos do userinfo (nome, e-mail, carteirinha) — o IdP
  os lê do CRM na hora, então renovam `atualizado_em`;
- busca contatos/endereço no mcp_hub quando `contato_atualizado_em` passou de
  `PERFIL_CACHE_TTL` (ou nunca foi lido);
- com o hub fora, devolve o cache marcado `desatualizado` (RNF-18); sem cache,
  propaga `HubError` (503 na tela de perfil, o resto da área segue);
- só escreve contato/e-mail/foto no cache DEPOIS do hub confirmar (RNF-04:
  nada de escrita "otimista").

Bloqueante (SQL + HTTP): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..config import get_settings
from ..integracoes.hub import Endereco, HubError, PerfilCrm, obter_hub
from ..oidc import AssociadoClaims

logger = logging.getLogger("area_associado.perfil")

CAMPOS_ENDERECO = ("logradouro", "numero", "complemento", "bairro", "cidade", "uf", "cep")


@dataclass
class Perfil:
    contact_id: str
    nome: str | None = None
    email: str | None = None
    celular: str | None = None
    telefone: str | None = None
    telefone2: str | None = None
    endereco: dict[str, str | None] | None = None
    num_contato: str | None = None
    crm: str | None = None
    crm_uf: str | None = None
    tipo_associado: str | None = None
    status_associativo: str | None = None
    data_filiacao: str | None = None
    foto_etag: str | None = None
    origem: str = "userinfo"
    atualizado_em: datetime | None = None
    contato_atualizado_em: datetime | None = None
    desatualizado: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def tem_foto(self) -> bool:
        return self.foto_etag is not None


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


# ------------------------------------------------------------------ leitura
_SQL_LER = text(
    "SELECT contact_id, nome, email, celular, telefone, telefone2, endereco, num_contato, crm, crm_uf, "
    "tipo_associado, status_associativo, data_filiacao, foto_etag, origem, atualizado_em, contato_atualizado_em "
    "FROM associado_perfil WHERE contact_id = :c"
)


def _de_linha(r: Any) -> Perfil:
    endereco = r.endereco
    if isinstance(endereco, (str, bytes)):
        endereco = json.loads(endereco)
    data = r.data_filiacao
    return Perfil(
        contact_id=r.contact_id, nome=r.nome, email=r.email, celular=r.celular, telefone=r.telefone,
        telefone2=r.telefone2, endereco=endereco if isinstance(endereco, dict) else None,
        num_contato=r.num_contato, crm=r.crm, crm_uf=r.crm_uf, tipo_associado=r.tipo_associado,
        status_associativo=r.status_associativo,
        data_filiacao=data.isoformat() if isinstance(data, date) else data,
        foto_etag=r.foto_etag, origem=r.origem, atualizado_em=r.atualizado_em,
        contato_atualizado_em=r.contato_atualizado_em,
    )


def ler(contact_id: str) -> Perfil | None:
    with _sessao() as db:
        r = db.execute(_SQL_LER, {"c": contact_id}).first()
    return _de_linha(r) if r else None


def foto_etag(contact_id: str | None) -> str | None:
    """Para o `GET /sessao` (avatar). Falha de banco = sem foto, nunca erro."""
    if not contact_id:
        return None
    try:
        with _sessao() as db:
            return db.execute(text("SELECT foto_etag FROM associado_perfil WHERE contact_id = :c"),
                              {"c": contact_id}).scalar()
    except SQLAlchemyError as exc:
        logger.error("perfil: leitura do etag falhou (%s)", type(exc).__name__)
        return None


# ------------------------------------------------------------------- login
_SQL_LOGIN = text(
    "INSERT INTO associado_perfil (contact_id, nome, email, num_contato, crm, crm_uf, tipo_associado, "
    " status_associativo, data_filiacao, origem, atualizado_em) "
    "VALUES (:c, :nome, :email, :num, :crm, :uf, :tipo, :status, :filiacao, :origem, :agora) AS novo "
    "ON DUPLICATE KEY UPDATE nome = COALESCE(novo.nome, associado_perfil.nome), "
    " email = COALESCE(novo.email, associado_perfil.email), "
    " num_contato = COALESCE(novo.num_contato, associado_perfil.num_contato), "
    " crm = COALESCE(novo.crm, associado_perfil.crm), crm_uf = COALESCE(novo.crm_uf, associado_perfil.crm_uf), "
    " tipo_associado = novo.tipo_associado, status_associativo = novo.status_associativo, "
    " data_filiacao = COALESCE(novo.data_filiacao, associado_perfil.data_filiacao), "
    " atualizado_em = novo.atualizado_em"
)


def gravar_de_login(contact_id: str, claims: AssociadoClaims, *, origem: str) -> bool:
    """Grava o que o IdP acabou de ler do CRM. Nunca lança (o login não depende disto)."""
    try:
        with _sessao() as db:
            db.execute(_SQL_LOGIN, {
                "c": contact_id, "nome": claims.nome, "email": claims.email, "num": claims.num_contato,
                "crm": claims.crm, "uf": (claims.crm_uf or "").upper()[:2] or None, "tipo": claims.tipo,
                "status": claims.status, "filiacao": claims.data_filiacao, "origem": origem, "agora": _agora(),
            })
    except SQLAlchemyError as exc:
        logger.error("perfil: gravação no login falhou (%s)", type(exc).__name__)
        return False
    return True


# --------------------------------------------------------------------- hub
_SQL_HUB = text(
    "INSERT INTO associado_perfil (contact_id, nome, email, celular, telefone, telefone2, endereco, num_contato, "
    " crm, crm_uf, tipo_associado, status_associativo, data_filiacao, origem, atualizado_em, contato_atualizado_em) "
    "VALUES (:c, :nome, :email, :cel, :tel, :tel2, :end, :num, :crm, :uf, :tipo, :status, :filiacao, :origem, "
    " :agora, :agora) AS novo "
    "ON DUPLICATE KEY UPDATE nome = COALESCE(novo.nome, associado_perfil.nome), "
    " email = COALESCE(novo.email, associado_perfil.email), "
    " celular = novo.celular, telefone = novo.telefone, telefone2 = novo.telefone2, endereco = novo.endereco, "
    " num_contato = COALESCE(novo.num_contato, associado_perfil.num_contato), "
    " crm = COALESCE(novo.crm, associado_perfil.crm), crm_uf = COALESCE(novo.crm_uf, associado_perfil.crm_uf), "
    " tipo_associado = COALESCE(novo.tipo_associado, associado_perfil.tipo_associado), "
    " status_associativo = COALESCE(novo.status_associativo, associado_perfil.status_associativo), "
    " data_filiacao = COALESCE(novo.data_filiacao, associado_perfil.data_filiacao), "
    " origem = novo.origem, contato_atualizado_em = novo.contato_atualizado_em, "
    " atualizado_em = IF(novo.status_associativo IS NULL, associado_perfil.atualizado_em, novo.atualizado_em)"
)


def _endereco_json(endereco: Endereco | dict[str, Any] | None) -> str | None:
    if endereco is None:
        return None
    dados = endereco.como_dict() if isinstance(endereco, Endereco) else endereco
    limpo = {k: dados.get(k) for k in CAMPOS_ENDERECO}
    return json.dumps(limpo, ensure_ascii=False) if any(limpo.values()) else None


def _gravar_do_hub(contact_id: str, crm: PerfilCrm) -> None:
    origem = "stub" if get_settings().hub_mode == "stub" else "hub"
    with _sessao() as db:
        db.execute(_SQL_HUB, {
            "c": contact_id, "nome": crm.nome, "email": crm.email, "cel": crm.celular, "tel": crm.telefone,
            "tel2": crm.telefone2, "end": _endereco_json(crm.endereco), "num": crm.num_contato, "crm": crm.crm,
            "uf": crm.crm_uf, "tipo": crm.tipo_associado, "status": crm.status_associativo,
            "filiacao": crm.data_filiacao, "origem": origem, "agora": _agora(),
        })


# Disponibilidade do endereço é propriedade do HUB (flag + Metadata do CRM),
# não do contato: guardada por processo a cada resposta do hub. None = este
# worker ainda não perguntou (aí o perfil vai ao hub mesmo com cache fresco).
_endereco_disponivel: bool | None = None


def endereco_disponivel() -> bool | None:
    return _endereco_disponivel


def marcar_endereco_disponivel(valor: bool | None) -> None:
    global _endereco_disponivel
    _endereco_disponivel = valor


def _contato_fresco(p: Perfil) -> bool:
    if p.contato_atualizado_em is None:
        return False
    return _agora() - p.contato_atualizado_em < timedelta(seconds=get_settings().perfil_cache_ttl)


def obter(contact_id: str, *, forcar: bool = False) -> Perfil:
    """Perfil para a tela. Levanta `HubError` só se não houver nem cache."""
    atual = ler(contact_id)
    if atual is not None and not forcar and _contato_fresco(atual) and _endereco_disponivel is not None:
        return atual
    try:
        crm = obter_hub().perfil_consultar(contact_id)
    except HubError:
        if atual is None:
            raise
        atual.desatualizado = True
        return atual
    if crm is None:
        logger.error("perfil: contato ausente no CRM via hub (contact_id com sessão válida)")
        if atual is None:
            raise HubError("nao_encontrado", 404)
        atual.desatualizado = True
        return atual
    marcar_endereco_disponivel(crm.endereco_disponivel)
    _gravar_do_hub(contact_id, crm)
    novo = ler(contact_id)
    if novo is None:  # pragma: no cover - acabou de ser gravado
        raise HubError("fonte_indisponivel")
    return novo


# --------------------------------------------- escritas confirmadas pelo CRM
def aplicar_contato(contact_id: str, campos: dict[str, Any]) -> None:
    """Reflete no cache o que o hub CONFIRMOU. Colunas vêm de lista fixa."""
    colunas = {"celular", "telefone", "telefone2", "endereco", "email"}
    sets, params = [], {"c": contact_id, "agora": _agora()}
    for chave, valor in campos.items():
        if chave not in colunas:
            raise ValueError(f"campo não permitido: {chave}")
        sets.append(f"{chave} = :{chave}")
        params[chave] = _endereco_json(valor) if chave == "endereco" else valor
    if not sets:
        return
    with _sessao() as db:
        db.execute(text(f"UPDATE associado_perfil SET {', '.join(sets)}, contato_atualizado_em = :agora "
                        "WHERE contact_id = :c"), params)


def aplicar_foto(contact_id: str, miniatura: bytes | None, etag: str | None) -> None:
    with _sessao() as db:
        db.execute(text("UPDATE associado_perfil SET foto_miniatura = :m, foto_etag = :e, foto_atualizada_em = :agora "
                        "WHERE contact_id = :c"), {"c": contact_id, "m": miniatura, "e": etag, "agora": _agora()})


def miniatura(contact_id: str) -> tuple[bytes, str] | None:
    with _sessao() as db:
        r = db.execute(text("SELECT foto_miniatura, foto_etag FROM associado_perfil WHERE contact_id = :c"),
                       {"c": contact_id}).first()
    if r is None or r.foto_miniatura is None or r.foto_etag is None:
        return None
    return bytes(r.foto_miniatura), r.foto_etag
