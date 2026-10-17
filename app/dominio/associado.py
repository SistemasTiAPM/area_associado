"""Identidade do associado na área (`associado`, sql/005).

Chave: `contact_id` (GUID do contact no CRM) — nunca CPF (ADR-0014). Guarda só
o que é da área: primeiro e último acesso (e, a partir da Fase 2, o token da
carteirinha). Dado cadastral vive no CRM; o cache dele é `associado_perfil`.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..audit import hash_sub

logger = logging.getLogger("area_associado.associado")

_RE_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# Namespace fixo do modo stub: o contact_id de construção é derivado do CPF
# digitado e NUNCA coincide com um GUID real do Dataverse (versão 5, não 4).
_NS_STUB = uuid.UUID("6b1f3c1e-4f3a-5d2b-9c7e-a5e0c0de57b0")

_SQL_UPSERT = text(
    "INSERT INTO associado (contact_id, sub_hash, primeiro_acesso_em, ultimo_acesso_em) "
    "VALUES (:contact_id, :sub_hash, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6)) AS novo "
    "ON DUPLICATE KEY UPDATE ultimo_acesso_em = novo.ultimo_acesso_em, sub_hash = novo.sub_hash"
)


def contact_id_valido(valor: object) -> str | None:
    return valor.lower() if isinstance(valor, str) and _RE_GUID.match(valor) else None


def contact_id_stub(cpf_digitos: str) -> str:
    return str(uuid.uuid5(_NS_STUB, f"stub:{cpf_digitos}"))


def _executar(parametros: dict[str, str | None]) -> None:
    from ..database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        db.execute(_SQL_UPSERT, parametros)


def registrar_acesso(contact_id: str | None, sub: str) -> bool:
    """Upsert de primeiro/último acesso. Nunca lança: o login não depende disto."""
    cid = contact_id_valido(contact_id)
    if cid is None:
        return False
    try:
        _executar({"contact_id": cid, "sub_hash": hash_sub(sub)})
    except SQLAlchemyError as exc:
        logger.error("associado: falha ao registrar acesso: %s", type(exc).__name__)
        return False
    return True


def registrar_login(claims, *, origem: str) -> None:
    """Pós-login (callback OIDC e stub): acesso, cache do perfil e token da
    carteirinha. Cada passo nunca lança — o login não depende de nenhum deles."""
    from . import carteirinha, perfil  # import tardio: evita ciclo no import de app.main

    cid = contact_id_valido(claims.contact_id)
    if cid is None or not registrar_acesso(cid, claims.sub):
        return
    perfil.gravar_de_login(cid, claims, origem=origem)
    carteirinha.garantir_token(cid)
