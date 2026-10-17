"""Carteirinha digital e verificação pública (RF-CA, ADR-0014).

Token público = base32(HMAC-SHA256(CARTEIRINHA_HMAC_KEY, contact_id))[:20]
(100 bits): estável por associado, não revela o `contact_id` e só é
resolvido por igualdade na coluna indexada `associado.carteirinha_token`.

A página pública mostra SÓ nome, situação e "verificado em" (spec,
"Privacidade"; validade omitida até P-10). Situação de cache com mais de
PERFIL_CACHE_TTL não é afirmada: aparece "não confirmada no momento" (RNF-04).

Bloqueante (SQL): chamar via `run_in_threadpool`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import segno
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..config import get_settings

logger = logging.getLogger("area_associado.carteirinha")

_RE_TOKEN = re.compile(r"^[A-Z2-7]{20}$")


def token_para(contact_id: str) -> str:
    mac = hmac.new(get_settings().effective_carteirinha_key, contact_id.encode("utf-8"), hashlib.sha256).digest()
    return base64.b32encode(mac).decode("ascii")[:20]


def url_verificacao(token: str) -> str:
    return f"{get_settings().effective_public_base_url}/verificar/{token}"


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


def garantir_token(contact_id: str) -> str | None:
    """Grava o token no login (idempotente). Nunca lança."""
    token = token_para(contact_id)
    try:
        with _sessao() as db:
            db.execute(text("UPDATE associado SET carteirinha_token = :t WHERE contact_id = :c "
                            "AND (carteirinha_token IS NULL OR carteirinha_token <> :t)"),
                       {"t": token, "c": contact_id})
    except SQLAlchemyError as exc:
        logger.error("carteirinha: gravação do token falhou (%s)", type(exc).__name__)
        return None
    return token


@dataclass(frozen=True)
class Verificacao:
    nome: str
    situacao: str
    verificado_em: datetime | None
    contact_id: str


def resolver(token: str) -> Verificacao | None:
    if not _RE_TOKEN.match(token):
        return None
    with _sessao() as db:
        r = db.execute(text(
            "SELECT a.contact_id, p.nome, p.status_associativo, p.atualizado_em FROM associado a "
            "JOIN associado_perfil p ON p.contact_id = a.contact_id WHERE a.carteirinha_token = :t"
        ), {"t": token}).first()
    if r is None or not r.nome:
        return None
    limite = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=get_settings().perfil_cache_ttl)
    fresco = r.atualizado_em is not None and r.atualizado_em >= limite and bool(r.status_associativo)
    return Verificacao(
        nome=r.nome,
        situacao=r.status_associativo if fresco else "não confirmada no momento",
        verificado_em=r.atualizado_em if fresco else None,
        contact_id=r.contact_id,
    )


def qr_svg(url: str) -> bytes:
    """QR em SVG puro (sem script, sem estilo inline) — servido como imagem."""
    buffer = io.BytesIO()
    segno.make(url, error="m", micro=False).save(
        buffer, kind="svg", scale=4, border=2, dark="#13233a", light="#ffffff", xmldecl=False,
        title="QR de verificação da carteirinha APM",
    )
    return buffer.getvalue()
