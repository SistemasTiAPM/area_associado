"""Identidade do associado na área (`associado`, sql/005).

Chave: `contact_id` (GUID do contact no CRM) — nunca CPF (ADR-0014). Guarda só
o que é da área: primeiro e último acesso (e, a partir da Fase 2, o token da
carteirinha). Dado cadastral vive no CRM; o cache dele é `associado_perfil`.

Primeiro acesso (spec v2 §11.2 `acesso_primeiro`, TI-05): quando o upsert de
`registrar_acesso` INSERE (e não atualiza), sai um `evento_uso` de origem
`servidor` com `dias_desde_filiacao` — base do gatilho A02 e do indicador de
ativação. A decisão vem do resultado do próprio INSERT, sem SELECT antes.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .. import uso
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
_SQL_FILIACAO = text("SELECT data_filiacao FROM associado_perfil WHERE contact_id = :c")

# Linhas afetadas do INSERT ... ON DUPLICATE KEY UPDATE (MySQL): 1 = inseriu,
# 2 = atualizou linha existente. O driver liga CLIENT_FOUND_ROWS, então uma
# atualização que não mude nada também devolve 1 — impossível aqui na prática,
# porque `ultimo_acesso_em` recebe UTC_TIMESTAMP(6) a cada login.
_INSERIU = 1


def contact_id_valido(valor: object) -> str | None:
    return valor.lower() if isinstance(valor, str) and _RE_GUID.match(valor) else None


def contact_id_stub(cpf_digitos: str) -> str:
    return str(uuid.uuid5(_NS_STUB, f"stub:{cpf_digitos}"))


def _executar(parametros: dict[str, str | None]) -> int | None:
    """Upsert; devolve as linhas afetadas (None quando o driver não informa)."""
    from ..database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        resultado = db.execute(_SQL_UPSERT, parametros)
        linhas = getattr(resultado, "rowcount", None)
    return linhas if isinstance(linhas, int) and linhas >= 0 else None


def _ler_data_filiacao(contact_id: str) -> date | None:
    from ..database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        valor = db.execute(_SQL_FILIACAO, {"c": contact_id}).scalar()
    return _como_data(valor)


def _como_data(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and valor:
        try:
            return date.fromisoformat(valor[:10])
        except ValueError:
            return None
    return None


def dias_desde_filiacao(data_filiacao: date | None, hoje: date | None = None) -> int | None:
    """Dias inteiros desde a filiação; filiação futura ou ausente → None."""
    if data_filiacao is None:
        return None
    dias = ((hoje or date.today()) - data_filiacao).days
    return dias if dias >= 0 else None


def _emitir_acesso_primeiro(contact_id: str, sub: str, data_filiacao: object) -> None:
    """`evento_uso acesso_primeiro` (origem servidor). Nunca lança."""
    filiacao: date | None = None
    try:
        filiacao = _ler_data_filiacao(contact_id)
    except SQLAlchemyError as exc:
        logger.error("associado: leitura da filiação falhou (%s)", type(exc).__name__)
    if filiacao is None:
        # Primeiro login: `associado_perfil` ainda não foi gravado; vale o que o
        # IdP acabou de ler do CRM (é o mesmo valor que entrará no cache).
        filiacao = _como_data(data_filiacao)
    dias = dias_desde_filiacao(filiacao)
    detalhes = {"dias_desde_filiacao": dias} if dias is not None else None
    uso.registrar("acesso_primeiro", "associado", contact_id, contact_id=contact_id, sub=sub,
                  origem="servidor", detalhes=detalhes)


def registrar_acesso(contact_id: str | None, sub: str, *, data_filiacao: object = None) -> bool:
    """Upsert de primeiro/último acesso. Nunca lança: o login não depende disto.
    Quando o upsert insere, emite `acesso_primeiro` (TI-05)."""
    cid = contact_id_valido(contact_id)
    if cid is None:
        return False
    try:
        linhas = _executar({"contact_id": cid, "sub_hash": hash_sub(sub)})
    except SQLAlchemyError as exc:
        logger.error("associado: falha ao registrar acesso: %s", type(exc).__name__)
        return False
    if linhas == _INSERIU:
        _emitir_acesso_primeiro(cid, sub, data_filiacao)
    return True


def registrar_login(claims, *, origem: str) -> None:
    """Pós-login (callback OIDC e stub): acesso, cache do perfil e token da
    carteirinha. Cada passo nunca lança — o login não depende de nenhum deles."""
    from . import carteirinha, perfil  # import tardio: evita ciclo no import de app.main

    cid = contact_id_valido(claims.contact_id)
    if cid is None or not registrar_acesso(cid, claims.sub, data_filiacao=getattr(claims, "data_filiacao", None)):
        return
    perfil.gravar_de_login(cid, claims, origem=origem)
    carteirinha.garantir_token(cid)
