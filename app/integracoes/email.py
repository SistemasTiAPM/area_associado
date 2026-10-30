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
    """Falha de entrega (SMTP indisponível, recusa do servidor).

    `codigo` é curto e nosso (vai para `comunicacao_envio.erro_codigo`);
    `permanente` = repetir não adianta (destinatário inválido ou recusado pelo
    servidor) — o job da outbox marca `falhou` sem esperar as 10 tentativas.
    Falha de autenticação/remetente é do NOSSO lado (configuração): não é
    permanente para a mensagem, mas é sistêmica (o job para a rodada)."""

    def __init__(self, mensagem: str, *, codigo: str = "smtp_indisponivel", permanente: bool = False,
                 sistemica: bool = False) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.permanente = permanente
        self.sistemica = sistemica


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
        raise EmailError("destinatário inválido", codigo="destinatario_invalido", permanente=True)
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
    except smtplib.SMTPRecipientsRefused as exc:
        logger.warning("e-mail: destinatário recusado pelo servidor")
        raise EmailError("destinatário recusado", codigo="destinatario_recusado", permanente=True) from exc
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("e-mail: autenticação SMTP recusada (credencial da área — P-27)")
        raise EmailError("falha ao enviar e-mail", codigo="smtp_autenticacao", sistemica=True) from exc
    except smtplib.SMTPSenderRefused as exc:
        logger.error("e-mail: remetente recusado pelo servidor (SMTP_FROM)")
        raise EmailError("falha ao enviar e-mail", codigo="smtp_remetente", sistemica=True) from exc
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


# --------------------------------------------------------------------------- #
# Transacionais das solicitações (gatilhos A04, A05, A06, A16 — spec v2 §12.2)  #
# Voz da APM (spec §3.3): primeira pessoa do plural, sem exclamação, sem jargão.#
# Ao associado: nenhum dado pessoal além do primeiro nome. Textos da spec como  #
# PROPOSTA até a P-44 (mudar texto = mudar só aqui).                            #
# --------------------------------------------------------------------------- #
_ASSINATURA = "Associação Paulista de Medicina\n"
_RODAPE = ("\nEste é um aviso automático da Minha APM. Para falar com a gente, use a Ajuda na Minha APM "
           "ou a Central de Relacionamento.\n\n")


def _limpo(texto: str | None, limite: int) -> str:
    """Uma linha, sem caractere de controle (o texto vai no corpo, nunca em cabeçalho)."""
    if not texto:
        return ""
    sem_controle = "".join(c if c.isprintable() else " " for c in str(texto))
    return " ".join(sem_controle.split())[:limite]


def primeiro_nome(nome: str | None) -> str:
    """`TELMA NOGUEIRA` → `Telma`; `MARIA-JOSÉ` → `Maria-José`. Vazio quando não há nome."""
    partes = _limpo(nome, 160).split()
    if not partes:
        return ""
    return "-".join(p[:1].upper() + p[1:].lower() for p in partes[0].split("-") if p)[:40]


def _saudacao(nome: str | None) -> str:
    primeiro = primeiro_nome(nome)
    return f"Olá, {primeiro}.\n\n" if primeiro else "Olá.\n\n"


def texto_solicitacao_recebida(nome: str | None, tipo: str, prazo_dias: int, link: str) -> tuple[str, str]:
    """A04 — confirmação ao associado. Devolve (assunto, corpo)."""
    corpo = (
        _saudacao(nome)
        + f"Recebemos sua solicitação: {_limpo(tipo, 80)}.\n\n"
        "Nós cuidamos do encaminhamento e avisamos você a cada etapa. "
        f"O retorno é esperado em até {int(prazo_dias)} dias depois do encaminhamento.\n\n"
        f"Acompanhe por aqui: {link}\n"
        + _RODAPE + _ASSINATURA
    )
    return "Recebemos sua solicitação", corpo


def texto_sem_retorno(nome: str | None, tipo: str, link: str) -> tuple[str, str]:
    """A05 — ao associado: o prazo venceu e a APM está cobrando."""
    corpo = (
        _saudacao(nome)
        + f"O prazo de retorno da sua solicitação ({_limpo(tipo, 80)}) venceu. "
        "Já estamos cobrando o retorno e avisamos você assim que houver novidade.\n\n"
        "Você não precisa fazer nada agora.\n\n"
        f"Acompanhe por aqui: {link}\n"
        + _RODAPE + _ASSINATURA
    )
    return "Estamos cobrando o retorno da sua solicitação", corpo


def texto_como_foi(nome: str | None, tipo: str, link: str) -> tuple[str, str]:
    """A06 — solicitação concluída: pergunta "como foi?" (nota de 0 a 10 na própria solicitação)."""
    corpo = (
        _saudacao(nome)
        + f"Sua solicitação ({_limpo(tipo, 80)}) foi concluída.\n\n"
        "Como foi o atendimento? Leva menos de um minuto: dê uma nota de 0 a 10 na própria solicitação. "
        "Sua resposta nos ajuda a cobrar e melhorar cada serviço.\n\n"
        f"Avaliar: {link}\n"
        + _RODAPE + _ASSINATURA
    )
    return "Como foi o atendimento da sua solicitação", corpo


def texto_cancelamento_recebido(nome: str | None, link: str) -> tuple[str, str]:
    """A16 — confirmação do PEDIDO de cancelamento (nada foi cancelado ainda)."""
    corpo = (
        _saudacao(nome)
        + "Recebemos seu pedido de cancelamento da associação.\n\n"
        "A Central de Relacionamento vai entrar em contato para concluir o pedido. "
        "Até lá, sua associação continua ativa e todos os benefícios seguem disponíveis.\n\n"
        f"Acompanhe por aqui: {link}\n"
        + _RODAPE + _ASSINATURA
    )
    return "Recebemos seu pedido de cancelamento", corpo


def texto_interno(gatilho: str, *, tipo: str, solicitacao_id: str, nome: str | None, num_contato: str | None,
                  detalhe: str) -> tuple[str, str]:
    """Aviso interno (Central/equipe). Identifica o associado pelo nome e pelo
    número de associado — sem CPF, e-mail, telefone ou o que ele escreveu (o
    atendente vê o pedido no CRM)."""
    assunto = {
        "A05": "Minha APM: solicitação sem retorno no prazo",
        "A16": "Minha APM: pedido de cancelamento da associação",
    }.get(gatilho, f"Minha APM: aviso {gatilho}")
    corpo = (
        f"{_limpo(detalhe, 400)}\n\n"
        f"Tipo: {_limpo(tipo, 80)}\n"
        f"Associado: {_limpo(nome, 160) or 'não informado'}\n"
        f"Número de associado: {_limpo(num_contato, 20) or 'não informado'}\n"
        f"Solicitação: {_limpo(solicitacao_id, 36)}\n\n"
        "Aviso automático da Minha APM (serviço de jobs). Não responda este e-mail.\n"
    )
    return assunto, corpo
