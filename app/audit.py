"""Trilha `evento_log` — INSERT parametrizado, nunca lança.

A tabela é append-only por privilégio (o usuário `apm_area` não tem UPDATE nem
DELETE). Identificadores pessoais entram só como HMAC com pepper próprio
(`LOG_HASH_KEY`): o `sub` já é um HMAC do CPF no IdP, e re-hashear aqui impede
correlacionar dumps dos dois schemas.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import get_settings

logger = logging.getLogger("area_associado.audit")

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Chaves que jamais entram em `detalhes` (há também um CHECK na tabela).
_PROIBIDAS = frozenset(
    {"token", "id_token", "access_token", "refresh_token", "client_secret", "cpf", "senha", "password", "authorization"}
)
_DETALHES_MAX = 4000

CATEGORIAS = ("seguranca", "negocio", "erro", "request")
SEVERIDADES = ("info", "aviso", "erro")


def _safe_identifier(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"identificador inválido: {name!r}")
    return name


def _hmac(value: str | None) -> str | None:
    if not value:
        return None
    key = get_settings().effective_log_hash_key.encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_sub(sub: str | None) -> str | None:
    return _hmac(f"sub:{sub}" if sub else None)


def hash_ip(ip: str | None) -> str | None:
    return _hmac(f"ip:{ip}" if ip else None)


def hash_ua(ua: str | None) -> str | None:
    return _hmac(f"ua:{ua[:512]}" if ua else None)


def client_ip(request: Request) -> str | None:
    # X-Real-IP é carimbado pelo nginx_porteiro após o real_ip (IP do visitante).
    ip = request.headers.get("x-real-ip")
    if ip:
        return ip.strip()[:45]
    return request.client.host if request.client else None


def _limpar_detalhes(detalhes: dict[str, Any] | None) -> str | None:
    if not detalhes:
        return None
    limpo = {k: v for k, v in detalhes.items() if isinstance(k, str) and k.lower() not in _PROIBIDAS}
    dump = json.dumps(limpo, ensure_ascii=False, default=str)
    if len(dump) > _DETALHES_MAX:
        dump = json.dumps({"truncado": True, "motivo": str(limpo.get("motivo", ""))[:200]}, ensure_ascii=False)
    return dump


def registrar(
    db: Session,
    request: Request,
    *,
    categoria: str,
    tipo: str,
    severidade: str = "info",
    sub: str | None = None,
    contact_id: str | None = None,
    status_http: int | None = None,
    duracao_ms: int | None = None,
    detalhes: dict[str, Any] | None = None,
) -> None:
    """Grava uma linha. Falha vira log de erro; a resposta ao associado nunca depende disto."""
    if categoria not in CATEGORIAS or severidade not in SEVERIDADES:
        logger.error("audit: categoria/severidade inválida (%s/%s)", categoria, severidade)
        return
    try:
        tabela = _safe_identifier(get_settings().evento_log_table)
        sql = text(
            f"INSERT INTO `{tabela}` "
            "(request_id, categoria, tipo, severidade, sub_hash, contact_id, ip_hash, ua_hash, "
            " metodo, rota, status_http, duracao_ms, detalhes) "
            "VALUES (:request_id, :categoria, :tipo, :severidade, :sub_hash, :contact_id, :ip_hash, :ua_hash, "
            " :metodo, :rota, :status_http, :duracao_ms, :detalhes)"
        )
        db.execute(
            sql,
            {
                "request_id": getattr(request.state, "request_id", None),
                "categoria": categoria,
                "tipo": tipo[:48],
                "severidade": severidade,
                "sub_hash": hash_sub(sub),
                "contact_id": contact_id[:64] if contact_id else None,
                "ip_hash": hash_ip(client_ip(request)),
                "ua_hash": hash_ua(request.headers.get("user-agent")),
                "metodo": request.method[:8],
                "rota": request.url.path[:160],
                "status_http": status_http,
                "duracao_ms": duracao_ms,
                "detalhes": _limpar_detalhes(detalhes),
            },
        )
        db.commit()
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        logger.error("audit: falha ao gravar evento %s/%s: %s", categoria, tipo, type(exc).__name__)


def registrar_isolado(request: Request, **kwargs: Any) -> None:
    """`registrar` em transação PRÓPRIA — para quem não tem (ou não pode
    comprometer) a sessão de banco da rota. Bloqueante: chamar via
    `run_in_threadpool`. Nunca lança."""
    from .database import SessionLocal  # import tardio: evita ciclo config→database no import do módulo

    try:
        db = SessionLocal()
    except SQLAlchemyError as exc:  # pragma: no cover - criação de sessão não toca a rede
        logger.error("audit: sessão indisponível: %s", type(exc).__name__)
        return
    try:
        registrar(db, request, **kwargs)
    finally:
        db.close()
