"""Envio de e-mail transacional (código de troca de e-mail e aviso de segurança).

Mesmo provedor e padrão do login_associado (`app/notifications.py` de lá):
`smtplib` com STARTTLS e certificado verificado (ou TLS implícito na 465),
texto puro, cabeçalhos fixos. Destinatário validado contra injeção de
cabeçalho; corpo e destino nunca vão para o log (só o HMAC do destino).

`SMTP_MODE=stub` não envia nada (proibido em produção).
Bloqueante: chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from ..audit import _hmac
from ..config import get_settings

logger = logging.getLogger("area_associado.email")

# Validação deliberadamente estrita (sem aspas, sem comentários, sem IP literal).
_RE_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                       r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


class EmailError(RuntimeError):
    """Falha de entrega (SMTP indisponível, recusa do servidor)."""


def email_valido(endereco: str) -> bool:
    return len(endereco) <= 254 and bool(_RE_EMAIL.match(endereco)) and ".." not in endereco


def normalizar_email(endereco: str) -> str:
    return endereco.strip().lower()


def mascarar_email(endereco: str) -> str:
    """`t***@exemplo.org` — para mostrar na tela sem expor o endereço inteiro."""
    local, _, dominio = endereco.partition("@")
    return f"{local[:1]}***@{dominio}" if local and dominio else "***"


def enviar(destino: str, assunto: str, texto: str) -> None:
    if not email_valido(destino):
        raise EmailError("destinatário inválido")
    s = get_settings()
    if s.smtp_mode == "stub":
        logger.warning("e-mail (stub) NÃO enviado: destino=%s assunto=%r", (_hmac(f"email:{destino}") or "")[:12], assunto)
        return
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = destino
    msg["Subject"] = assunto
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    dominio = parseaddr(s.smtp_from)[1].rpartition("@")[2] or "apm.org.br"
    msg["Message-ID"] = make_msgid(domain=dominio)
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(texto)
    contexto = ssl.create_default_context()
    try:
        if s.smtp_starttls:
            with smtplib.SMTP(s.smtp_host or "", s.smtp_port, timeout=s.smtp_timeout) as smtp:
                smtp.ehlo()
                smtp.starttls(context=contexto)
                smtp.ehlo()
                smtp.login(s.smtp_user or "", s.smtp_password or "")
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(s.smtp_host or "", s.smtp_port, timeout=s.smtp_timeout, context=contexto) as smtp:
                smtp.login(s.smtp_user or "", s.smtp_password or "")
                smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("e-mail: falha de entrega (%s)", type(exc).__name__)
        raise EmailError("falha ao enviar e-mail") from exc


def texto_codigo(codigo: str, minutos: int) -> str:
    return (
        "Olá!\n\n"
        f"Seu código para confirmar o novo e-mail na Minha APM é: {codigo}\n\n"
        f"Ele vale por {minutos} minutos. Não compartilhe este código com ninguém — "
        "a APM nunca pede o código por telefone ou mensagem.\n\n"
        "Se você não pediu esta alteração, ignore este e-mail: nada será mudado.\n\n"
        "Associação Paulista de Medicina\n"
    )


def texto_aviso_troca(quando: str, telefone_central: str) -> str:
    return (
        "Olá!\n\n"
        f"O e-mail de acesso da sua conta na APM foi alterado em {quando} pela Minha APM.\n\n"
        "Se foi você, não é preciso fazer nada.\n"
        "Se não foi você, fale imediatamente com a Central de Relacionamento"
        f"{' (' + telefone_central + ')' if telefone_central else ''}.\n\n"
        "Associação Paulista de Medicina\n"
    )
