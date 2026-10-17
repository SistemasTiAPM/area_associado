"""Troca de e-mail com código enviado ao novo endereço (decisão de 2026-10-17).

O e-mail do CRM é o canal de recuperação de senha do Login APM: trocá-lo é
operação de tomada de conta se feita sem prova. Regras:
- só com login recente no IdP (checado na rota, `REAUTH_MAX_IDADE`);
- código de 6 dígitos (`secrets`), validade `EMAIL_CODIGO_TTL`, 5 tentativas;
- 60 s entre envios e 5 envios por hora por associado (como o IdP);
- pedido novo invalida os pendentes; código usado não volta a valer;
- banco guarda só HMAC do e-mail e do código (`LOG_HASH_KEY`), comparação em
  tempo constante;
- o pedido só é marcado como usado DEPOIS do CRM confirmar a troca.

Bloqueante (SQL): chamar via `run_in_threadpool`.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from ..audit import _hmac
from ..config import get_settings

TENTATIVAS_MAX = 5
INTERVALO_REENVIO_S = 60
ENVIOS_POR_HORA = 5


class RecusaVerificacao(Exception):
    def __init__(self, codigo: str, status: int, mensagem: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.status = status
        self.mensagem = mensagem


@dataclass(frozen=True)
class Pedido:
    id: int
    expira_em: datetime


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


def _hash_email(contact_id: str, email: str) -> str:
    return _hmac(f"email_novo:{contact_id}:{email}") or ""


def _hash_codigo(contact_id: str, email_hash: str, codigo: str) -> str:
    return _hmac(f"codigo:{contact_id}:{email_hash}:{codigo}") or ""


def iniciar(contact_id: str, email_novo: str) -> tuple[Pedido, str]:
    """Cria o pedido e devolve (pedido, código em claro para o e-mail)."""
    agora = _agora()
    email_hash = _hash_email(contact_id, email_novo)
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    expira = agora + timedelta(seconds=get_settings().email_codigo_ttl)
    with _sessao() as db:
        envios = db.execute(text(
            "SELECT COUNT(*) AS n, MAX(criado_em) AS ultimo FROM email_verificacao "
            "WHERE contact_id = :c AND criado_em >= :desde"
        ), {"c": contact_id, "desde": agora - timedelta(hours=1)}).one()
        if envios.ultimo is not None and (agora - envios.ultimo).total_seconds() < INTERVALO_REENVIO_S:
            raise RecusaVerificacao("aguarde_reenvio", 429, "Aguarde um minuto para pedir outro código.")
        if envios.n >= ENVIOS_POR_HORA:
            raise RecusaVerificacao("limite_taxa", 429, "Muitos pedidos de código. Tente de novo em uma hora.")
        db.execute(text(
            "UPDATE email_verificacao SET invalidado_em = :agora "
            "WHERE contact_id = :c AND usado_em IS NULL AND invalidado_em IS NULL"
        ), {"c": contact_id, "agora": agora})
        resultado = db.execute(text(
            "INSERT INTO email_verificacao (contact_id, email_hash, codigo_hash, criado_em, expira_em) "
            "VALUES (:c, :eh, :ch, :agora, :expira)"
        ), {"c": contact_id, "eh": email_hash, "ch": _hash_codigo(contact_id, email_hash, codigo),
            "agora": agora, "expira": expira})
        pedido_id = int(resultado.lastrowid)
    return Pedido(pedido_id, expira), codigo


def conferir(contact_id: str, email_novo: str, codigo: str) -> Pedido:
    """Confere o código. Erro conta tentativa. NÃO marca como usado (ver `marcar_usado`)."""
    agora = _agora()
    email_hash = _hash_email(contact_id, email_novo)
    falha: RecusaVerificacao | None = None
    with _sessao() as db:
        r = db.execute(text(
            "SELECT id, email_hash, codigo_hash, expira_em, tentativas FROM email_verificacao "
            "WHERE contact_id = :c AND usado_em IS NULL AND invalidado_em IS NULL "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE"
        ), {"c": contact_id}).first()
        if r is None or r.expira_em < agora:
            raise RecusaVerificacao("codigo_expirado", 409, "O código expirou. Peça um novo.")
        email_ok = hmac.compare_digest(r.email_hash, email_hash)
        codigo_ok = hmac.compare_digest(r.codigo_hash, _hash_codigo(contact_id, r.email_hash, codigo))
        if r.tentativas >= TENTATIVAS_MAX:
            db.execute(text("UPDATE email_verificacao SET invalidado_em = :agora WHERE id = :id"),
                       {"agora": agora, "id": r.id})
            falha = RecusaVerificacao("tentativas_esgotadas", 429, "Tentativas esgotadas. Peça um novo código.")
        elif not (email_ok and codigo_ok):
            db.execute(text("UPDATE email_verificacao SET tentativas = tentativas + 1 WHERE id = :id"), {"id": r.id})
            restantes = TENTATIVAS_MAX - r.tentativas - 1
            falha = RecusaVerificacao(
                "codigo_invalido", 400,
                f"Código incorreto. {restantes} tentativa(s) restante(s)." if restantes > 0
                else "Código incorreto. Peça um novo código.",
            )
        pedido = Pedido(int(r.id), r.expira_em)
    # Levantada FORA da transação: a contagem da tentativa precisa ser gravada.
    if falha is not None:
        raise falha
    return pedido


def marcar_usado(pedido_id: int) -> None:
    with _sessao() as db:
        db.execute(text("UPDATE email_verificacao SET usado_em = :agora WHERE id = :id AND usado_em IS NULL"),
                   {"agora": _agora(), "id": pedido_id})
