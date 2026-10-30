"""Job `enviar_comunicacao` — consumidor da outbox `comunicacao_evento` (TI-19;
REQUISITOS §3.17 RF-CM-01..03; sql/012).

Por linha pendente e vencida (`enviar_apos`, `proxima_tentativa_em`):

| canal / destinatário                 | o que acontece |
|--------------------------------------|----------------|
| `rd` (qualquer)                      | `suprimido: sem_credencial` até a Onda 3 (RD Station; flag `comunicacao_outbox`) |
| `email` + `associado`                | e-mail transacional (A04, A05, A06, A16) para o endereço do cache `associado_perfil` — o endereço NUNCA é gravado na outbox |
| `email`/`interno` + `central`/`equipe` | e-mail para `CENTRAL_EMAIL`; ausente = `suprimido: sem_credencial` |
| `app`                                | nada a enviar (a `notificacao` nasceu com o fato) — marcado `enviado` (origem `app`) |

Antes de enviar, o fato é revalidado (RF-SO-12): solicitação cancelada ou
marcador A05 já limpo → `suprimido: fato_mudou`.

Envio (só com `JOBS_APLICAR=1`): com `SMTP_MODE=stub` em development/test o
stub "envia" e a linha vira `enviado` com `externo_id='smtp_stub'`; em staging
(o site no ar, com associados reais) o stub NÃO marca nada — o e-mail fica
pendente até o SMTP real (P-27), senão a confirmação se perderia para sempre.
Claim condicional `pendente|erro →
enviando`, envio fora de transação, depois `enviado` + `comunicacao_envio`.
Falha: recuo 1, 2, 4 … 60 min; 10 tentativas ou erro permanente → `falhou`
+ `comunicacao_envio` (`falha`, código curto) + `evento_log`. Linha presa em
`enviando` há mais de 15 min (queda no meio do envio) volta a `erro`: o
e-mail pode sair duas vezes, nunca zero (transacional: entrega > duplicata).
Supressões são locais e acontecem nos dois modos.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import bindparam, text

from .. import audit
from ..config import get_settings
from ..dominio.solicitacoes import rotulos
from ..integracoes import email as email_mod
from ..integracoes.email import EmailError
from .base import Contexto
from .politica import DISJUNTOR_SEGUIDAS, PERMANENTE, SISTEMICO, classificar_email, proxima_tentativa

logger = logging.getLogger("area_associado.jobs.comunicacao")

ENVIANDO_PRESO_MIN = 15
_RE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MODELOS_ASSOCIADO = frozenset({"A04", "A05", "A06", "A16"})
MODELOS_INTERNOS = frozenset({"A05", "A16"})


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem

    return session_scope()


_SQL_FILA = (
    "SELECT id, gatilho, contact_id, referencia_tipo, referencia_id, canal, destinatario, tentativas, status, "
    " atualizado_em FROM comunicacao_evento "
    "WHERE status IN ('pendente', 'erro') AND enviar_apos <= :agora "
    "AND (proxima_tentativa_em IS NULL OR proxima_tentativa_em <= :agora)"
)


def fila(agora: datetime, lote: int, ids: Sequence[int] | None = None) -> list[Any]:
    sql, params = _SQL_FILA, {"agora": agora, "lote": int(lote)}
    if ids is not None:
        sql += " AND id IN :ids"
        params["ids"] = list(ids)
    consulta = text(sql + " ORDER BY enviar_apos, id LIMIT :lote")
    if ids is not None:
        consulta = consulta.bindparams(bindparam("ids", expanding=True))
    with _sessao() as db:
        return list(db.execute(consulta, params).all())


def _suprimir(r: Any, motivo: str, agora: datetime) -> bool:
    with _sessao() as db:
        feito = db.execute(text(
            "UPDATE comunicacao_evento SET status = 'suprimido', supressao_motivo = :motivo, atualizado_em = :agora "
            "WHERE id = :id AND status IN ('pendente', 'erro')"
        ), {"motivo": motivo, "agora": agora, "id": r.id}).rowcount
        if feito:
            db.execute(text(
                "INSERT INTO comunicacao_supressao (ocorrido_em, comunicacao_evento_id, contact_id, gatilho, canal, "
                " motivo) VALUES (:agora, :eid, :c, :gatilho, :canal, :motivo)"
            ), {"agora": agora, "eid": r.id, "c": r.contact_id, "gatilho": r.gatilho, "canal": r.canal,
                "motivo": motivo})
    return bool(feito)


def _registrar_envio(db: Any, r: Any, situacao: str, origem: str, agora: datetime, erro: str | None = None) -> None:
    db.execute(text(
        "INSERT INTO comunicacao_envio (ocorrido_em, comunicacao_evento_id, contact_id, gatilho, canal, situacao, "
        " origem_retorno, erro_codigo) VALUES (:agora, :eid, :c, :gatilho, :canal, :situacao, :origem, :erro)"
    ), {"agora": agora, "eid": r.id, "c": r.contact_id, "gatilho": r.gatilho, "canal": r.canal,
        "situacao": situacao, "origem": origem, "erro": erro})


def _marcar_enviado(r: Any, agora: datetime, *, origem: str, externo_id: str | None, de: tuple[str, ...]) -> bool:
    lista = ", ".join(f"'{s}'" for s in de)  # constantes deste módulo, nunca entrada
    with _sessao() as db:
        feito = db.execute(text(
            "UPDATE comunicacao_evento SET status = 'enviado', tentativas = LEAST(tentativas + 1, 20), "
            " proxima_tentativa_em = NULL, externo_id = :externo, atualizado_em = :agora "
            f"WHERE id = :id AND status IN ({lista})"
        ), {"externo": externo_id, "agora": agora, "id": r.id}).rowcount
        if feito:
            _registrar_envio(db, r, "enviado", origem, agora)
    return bool(feito)


def _registrar_falha(r: Any, classe: str, codigo: str, agora: datetime) -> None:
    tentativas = int(r.tentativas) + 1
    proxima = None if classe == PERMANENTE else proxima_tentativa(tentativas, agora)
    with _sessao() as db:
        feito = db.execute(text(
            "UPDATE comunicacao_evento SET status = :status, tentativas = :t, proxima_tentativa_em = :prox, "
            " atualizado_em = :agora WHERE id = :id AND status IN ('enviando', 'pendente', 'erro')"
        ), {"status": "falhou" if proxima is None else "erro", "t": min(tentativas, 20), "prox": proxima,
            "agora": agora, "id": r.id}).rowcount
        if feito:
            _registrar_envio(db, r, "falha", "smtp", agora, codigo)
    if feito and proxima is None:
        logger.error("comunicação %d (%s/%s/%s) falhou: %s", r.id, r.gatilho, r.canal, r.destinatario, codigo)
        audit.registrar_sistema(categoria="erro", tipo="comunicacao_falhou", severidade="erro",
                                origem="enviar_comunicacao", contact_id=str(r.contact_id),
                                detalhes={"comunicacao_evento_id": int(r.id), "gatilho": r.gatilho,
                                          "canal": r.canal, "destinatario": r.destinatario, "codigo": codigo,
                                          "tentativas": tentativas})


def _reabrir_presos(agora: datetime) -> int:
    """`enviando` há mais de 15 min = o processo caiu no meio: volta a `erro` já."""
    with _sessao() as db:
        return db.execute(text(
            "UPDATE comunicacao_evento SET status = 'erro', proxima_tentativa_em = :agora, atualizado_em = :agora "
            "WHERE status = 'enviando' AND atualizado_em < :limite"
        ), {"agora": agora, "limite": agora - timedelta(minutes=ENVIANDO_PRESO_MIN)}).rowcount


def _reivindicar(r: Any, agora: datetime) -> bool:
    with _sessao() as db:
        return bool(db.execute(text(
            "UPDATE comunicacao_evento SET status = 'enviando', atualizado_em = :agora "
            "WHERE id = :id AND status IN ('pendente', 'erro') AND enviar_apos <= :agora "
            "AND (proxima_tentativa_em IS NULL OR proxima_tentativa_em <= :agora)"
        ), {"agora": agora, "id": r.id}).rowcount)


# --------------------------------------------------------------- conteúdo
class SemConteudo(Exception):
    """Não há como montar a mensagem: erro permanente com código curto."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


def _fato(db: Any, r: Any) -> Any:
    if r.referencia_tipo != "solicitacao" or not _RE_UUID.match(str(r.referencia_id)):
        raise SemConteudo("referencia_sem_modelo")
    s = db.execute(text(
        "SELECT id, contact_id, tipo_servico, status, prazo_retorno_dias, sem_retorno_desde, enviada_em "
        "FROM solicitacao WHERE id = :id"), {"id": r.referencia_id}).first()
    if s is None or str(s.contact_id) != str(r.contact_id):
        raise SemConteudo("referencia_inexistente")
    return s


def fato_mudou(r: Any, s: Any) -> bool:
    """O fato que causou o gatilho deixou de valer (RF-SO-12): solicitação
    cancelada (inclusive o pedido de cancelamento desistido na janela — a
    confirmação A16 não sai mais) ou marcador A05 já limpo por uma transição."""
    if s.status == "cancelada":
        return True
    return r.gatilho == "A05" and s.sem_retorno_desde is None


def montar(db: Any, r: Any, s: Any, *, base_url: str, central: str | None) -> tuple[str, str, str]:
    """(destino, assunto, corpo). Endereço do associado lido do cache na hora."""
    link = f"{base_url}/area/solicitacoes/{s.id}"
    tipo = rotulos.rotulo_tipo(s.tipo_servico)
    perfil = db.execute(text("SELECT nome, email, num_contato FROM associado_perfil WHERE contact_id = :c"),
                        {"c": r.contact_id}).first()
    nome = perfil.nome if perfil is not None else None
    if r.destinatario == "associado":
        if r.canal != "email" or r.gatilho not in MODELOS_ASSOCIADO:
            raise SemConteudo("sem_modelo")
        destino = email_mod.normalizar_email(perfil.email) if perfil is not None and perfil.email else ""
        if not destino or not email_mod.email_valido(destino):
            raise SemConteudo("sem_email")
        if r.gatilho == "A04":
            assunto, corpo = email_mod.texto_solicitacao_recebida(nome, tipo, int(s.prazo_retorno_dias), link)
        elif r.gatilho == "A05":
            assunto, corpo = email_mod.texto_sem_retorno(nome, tipo, link)
        elif r.gatilho == "A06":
            assunto, corpo = email_mod.texto_como_foi(nome, tipo, link)
        else:
            assunto, corpo = email_mod.texto_cancelamento_recebido(nome, link)
        return destino, assunto, corpo
    if r.gatilho not in MODELOS_INTERNOS or not central:
        raise SemConteudo("sem_modelo")
    if r.gatilho == "A16":
        detalhe = ("Um associado pediu o cancelamento da associação pela Minha APM. "
                   "A Central deve entrar em contato para concluir ou reverter o pedido.")
    else:
        enviada = s.enviada_em.strftime("%d/%m/%Y") if s.enviada_em else "sem data"
        detalhe = (f"Uma solicitação encaminhada em {enviada} passou do prazo de retorno de "
                   f"{int(s.prazo_retorno_dias)} dias. Cobre o responsável e registre o andamento no CRM.")
    assunto, corpo = email_mod.texto_interno(r.gatilho, tipo=tipo, solicitacao_id=str(s.id), nome=nome,
                                             num_contato=perfil.num_contato if perfil is not None else None,
                                             detalhe=detalhe)
    return central, assunto, corpo


# ------------------------------------------------------------------- job
def envio_efetivo() -> bool:
    """O SMTP configurado entrega de verdade, ou estamos em development/test (stub vale)."""
    s = get_settings()
    return s.smtp_mode == "real" or s.app_env in ("development", "test")


def enviar_comunicacao(ctx: Contexto, *, ids: Sequence[int] | None = None) -> None:
    s = get_settings()
    enviar_de_verdade = ctx.aplicar and envio_efetivo()
    if ctx.aplicar and not enviar_de_verdade:
        logger.warning("comunicação: SMTP_MODE=stub em %s — e-mails ficam pendentes até o SMTP real (P-27)",
                       s.app_env)
    if ctx.aplicar:
        presos = _reabrir_presos(ctx.agora)
        if presos:
            logger.warning("comunicação: %d envio(s) preso(s) em 'enviando' reabertos", presos)
    itens = fila(ctx.agora, s.jobs_lote, ids)
    ctx.lidos = len(itens)
    seguidas = 0
    simulados: list[str] = []
    for r in itens:
        if ctx.parar():
            return
        ctx.pulso()
        # 1) Supressões locais (dois modos).
        if r.canal == "rd":
            if _suprimir(r, "sem_credencial", ctx.agora):
                ctx.gravados += 1
            continue
        if r.destinatario in ("central", "equipe") and not s.central_email:
            if _suprimir(r, "sem_credencial", ctx.agora):
                ctx.gravados += 1
            continue
        if r.canal == "app":
            if not ctx.aplicar:
                simulados.append(f"{r.id}:{r.gatilho}/app")
            elif _marcar_enviado(r, ctx.agora, origem="app", externo_id=None, de=("pendente", "erro")):
                ctx.gravados += 1
            continue
        # 2) Fato e conteúdo.
        try:
            with _sessao() as db:
                fato = _fato(db, r)
                if fato_mudou(r, fato):
                    conteudo = None
                else:
                    conteudo = montar(db, r, fato, base_url=s.effective_public_base_url, central=s.central_email)
        except SemConteudo as exc:
            ctx.erros += 1
            if ctx.aplicar:
                _registrar_falha(r, PERMANENTE, exc.codigo, ctx.agora)
            else:
                simulados.append(f"{r.id}:{r.gatilho}/{r.canal}/{r.destinatario}=falharia({exc.codigo})")
            continue
        if conteudo is None:
            if _suprimir(r, "fato_mudou", ctx.agora):
                ctx.gravados += 1
            continue
        destino, assunto, corpo = conteudo
        # 3) Envio (só com JOBS_APLICAR=1 e SMTP que entrega — ou stub em development/test).
        if not enviar_de_verdade:
            simulados.append(f"{r.id}:{r.gatilho}/{r.canal}/{r.destinatario}")
            continue
        if not _reivindicar(r, ctx.agora):
            continue  # outro consumidor pegou ou o fato mudou entre a leitura e o envio
        try:
            email_mod.enviar(destino, assunto, corpo)
        except EmailError as exc:
            falha = classificar_email(exc)
            ctx.erros += 1
            if falha.classe == SISTEMICO:
                # Problema nosso (credencial/remetente): devolve a linha sem gastar tentativa.
                _devolver(r, ctx.agora)
                ctx.erro_sistemico = f"disjuntor: {falha.codigo}"
                return
            _registrar_falha(r, falha.classe, falha.codigo, ctx.agora)
            if falha.classe != PERMANENTE:
                seguidas += 1
                if seguidas >= DISJUNTOR_SEGUIDAS:
                    ctx.erro_sistemico = f"disjuntor: {seguidas} falhas seguidas ({falha.codigo})"
                    return
            continue
        seguidas = 0
        externo = "smtp_stub" if s.smtp_mode == "stub" else None
        if _marcar_enviado(r, ctx.agora, origem="smtp", externo_id=externo, de=("enviando",)):
            ctx.gravados += 1
    if simulados:
        logger.info("comunicação (simulação): %d envio(s) seriam feitos: %s", len(simulados),
                    ", ".join(simulados[:10]))


def _devolver(r: Any, agora: datetime) -> None:
    with _sessao() as db:
        db.execute(text(
            "UPDATE comunicacao_evento SET status = :status, atualizado_em = :agora "
            "WHERE id = :id AND status = 'enviando'"
        ), {"status": r.status, "agora": agora, "id": r.id})
