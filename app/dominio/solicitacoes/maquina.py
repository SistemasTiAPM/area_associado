"""Máquina de estados das solicitações — ÚNICA fonte das transições (ADR-0018 item 6;
REQUISITOS §7.3).

Duas camadas:
1. **Tabela pura** (`REGRAS`, `origens_permitidas`, `pode_transitar`): quem
   (ator, origem) leva de quais status a qual status, e o que a regra exige
   (mensagem pública, justificativa). Testável sem banco.
2. **`transitar(sess, ...)`**: dentro da transação do chamador, trava a linha
   (`SELECT ... FOR UPDATE`), confere a tabela, faz o `UPDATE` condicional
   `WHERE id = :id AND status = :de` e grava o evento em `solicitacao_evento`
   (append-only) — tudo na mesma transação, junto com os efeitos de
   comunicação (notificação, outbox, supressão). Zero linhas ⇒ 409.

Toda mudança limpa o marcador `sem_retorno_desde` (ADR-0018 item 3) e, se o
pedido já tem espelho no CRM e a mudança não veio do próprio CRM, reabre a
outbox do espelho (`crm_sync='pendente'`). Pedido ainda sem espelho mantém a
agenda (ex.: cancelamento da associação na janela de arrependimento): o job
espelha o estado atual quando chegar a hora.

Terminais não mudam. `evento_uso` NÃO sai daqui: o chamador registra depois
do commit (regra 20).

Adenda de 2026-11-04 (ADR-0023): o hub não tem ferramenta de status, então o que
o associado faz na área depois do envio não chega ao CRM. Com o pedido já no CRM
(`crm_id`), cancelar e responder pela área são recusados (409 `na_central`) e a
tela orienta a falar com a Central pelo protocolo. E o CRM pode tirar o pedido de
`pendente_associado` sem mensagem (a Central resolveu por fora) — P-66.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import comunicacao
from . import rotulos

logger = logging.getLogger("area_associado.solicitacoes.maquina")

STATUS = rotulos.STATUS
TERMINAIS = rotulos.TERMINAIS
ATORES: tuple[str, ...] = ("associado", "sistema", "parceiro", "apm", "importacao")
ORIGENS: tuple[str, ...] = ("ui", "job", "crm", "backoffice", "importacao", "api_parceiro", "portal_parceiro")

_PARCEIRO_OU_APM = frozenset({("apm", "crm"), ("apm", "backoffice"),
                              ("parceiro", "api_parceiro"), ("parceiro", "portal_parceiro")})


@dataclass(frozen=True)
class Regra:
    de: frozenset[str]
    para: str
    quem: frozenset[tuple[str, str]]  # pares (ator, origem)
    exige_mensagem: bool = False


# REQUISITOS §7.3 / ADR-0018 item 6. Qualquer par (de, para, ator, origem)
# fora desta tabela é 409 `estado_invalido`.
REGRAS: tuple[Regra, ...] = (
    # canal confirmou (espelho ok / ack do parceiro) ou operador marcou o envio manual
    Regra(frozenset({"criada"}), "enviada",
          frozenset({("sistema", "job"), ("apm", "backoffice"),
                     ("parceiro", "api_parceiro"), ("parceiro", "portal_parceiro")})),
    # parceiro/APM assumiu
    Regra(frozenset({"criada", "enviada"}), "em_atendimento", _PARCEIRO_OU_APM),
    # pedido ao associado: mensagem pública obrigatória
    Regra(frozenset({"em_atendimento"}), "pendente_associado", _PARCEIRO_OU_APM, exige_mensagem=True),
    # associado respondeu
    Regra(frozenset({"pendente_associado"}), "em_atendimento", frozenset({("associado", "ui")}), exige_mensagem=True),
    # a Central seguiu sem a resposta pela área (P-66, ADR-0023): o CRM saiu de
    # "Aguardando detalhes"; com o caminho intermediário, o CRM também conclui daqui
    Regra(frozenset({"pendente_associado"}), "em_atendimento", frozenset({("apm", "crm")})),
    # resultado registrado
    Regra(frozenset({"enviada", "em_atendimento"}), "concluida_positiva",
          _PARCEIRO_OU_APM | {("importacao", "importacao")}),
    Regra(frozenset({"enviada", "em_atendimento"}), "concluida_negativa",
          _PARCEIRO_OU_APM | {("importacao", "importacao")}),
    # associado cancela "enquanto o parceiro ainda não atendeu" — nunca em_atendimento (DIV-24)
    Regra(frozenset({"criada", "enviada", "pendente_associado"}), "cancelada", frozenset({("associado", "ui")})),
    # APM cancela qualquer não terminal, com justificativa (CHECK no banco + conferência aqui)
    Regra(frozenset(rotulos.NAO_TERMINAIS), "cancelada", frozenset({("apm", "backoffice")})),
)


def _regras(para: str, ator: str, origem: str) -> list[Regra]:
    return [r for r in REGRAS if r.para == para and (ator, origem) in r.quem]


def origens_permitidas(para: str, ator: str, origem: str) -> frozenset[str]:
    """Status de onde `(ator, origem)` pode levar a `para` (vazio = nunca)."""
    return frozenset().union(*(r.de for r in _regras(para, ator, origem)))


def pode_transitar(de: str, para: str, ator: str, origem: str) -> bool:
    return de not in TERMINAIS and de in origens_permitidas(para, ator, origem)


def exige_mensagem(para: str, ator: str, origem: str) -> bool:
    return any(r.exige_mensagem for r in _regras(para, ator, origem))


MENSAGEM_NA_CENTRAL = ("Este pedido já está com a Central de Relacionamento. Para cancelar ou responder, "
                       "fale com a Central e informe o protocolo.")


def pode_cancelar_associado(status: str, na_central: bool = False) -> bool:
    return not na_central and pode_transitar(status, "cancelada", "associado", "ui")


def pode_responder_associado(status: str, na_central: bool = False) -> bool:
    return not na_central and pode_transitar(status, "em_atendimento", "associado", "ui")


# ---------------------------------------------------------------- exceções
class SolicitacaoNaoEncontrada(Exception):
    """404 `nao_encontrado` — inclusive de outro associado (sem oráculo)."""


class TransicaoInvalida(Exception):
    """409 `estado_invalido` (ou outro código 409 do domínio)."""

    def __init__(self, codigo: str = "estado_invalido", mensagem: str | None = None) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.mensagem = mensagem


@dataclass(frozen=True)
class Resultado:
    solicitacao_id: str
    contact_id: str
    de: str
    para: str
    tipo_servico: str | None
    tipo_ativacao: int | None
    evento_id: int
    ator: str
    origem: str = ""


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


_SQL_TRAVAR = (
    "SELECT id, contact_id, status, tipo_servico, tipo_ativacao, crm_id FROM solicitacao WHERE id = :id"
)
_SQL_EVENTO = text(
    "INSERT INTO solicitacao_evento (solicitacao_id, ocorrido_em, evento, de_status, para_status, ator, origem, "
    " usuario_interno, justificativa, mensagem_publica, conteudo_enviado, request_id) "
    "VALUES (:sid, :agora, :evento, :de, :para, :ator, :origem, :usuario, :justificativa, :mensagem, :conteudo, "
    " :request_id)"
)


def registrar_evento(sess: Session, *, solicitacao_id: str, evento: str, de: str | None, para: str, ator: str,
                     origem: str, agora: datetime, usuario_interno: str | None = None,
                     justificativa: str | None = None, mensagem: str | None = None,
                     conteudo_enviado: dict[str, object] | None = None, request_id: str | None = None) -> int:
    """INSERT no log imutável. Devolve o id do evento."""
    resultado = sess.execute(_SQL_EVENTO, {
        "sid": solicitacao_id, "agora": agora, "evento": evento, "de": de, "para": para, "ator": ator,
        "origem": origem, "usuario": usuario_interno, "justificativa": justificativa, "mensagem": mensagem,
        "conteudo": json.dumps(conteudo_enviado, ensure_ascii=False, sort_keys=True) if conteudo_enviado else None,
        "request_id": request_id,
    })
    return int(resultado.lastrowid)


def _link(solicitacao_id: str) -> str:
    return f"/area/solicitacoes/{solicitacao_id}"


def _efeitos(sess: Session, r: Resultado, *, agora: datetime) -> None:
    """Comunicação produzida na MESMA transação da transição (RF-NO-04, RF-CM-01)."""
    tipo = rotulos.rotulo_tipo(r.tipo_servico)
    if r.para == "pendente_associado":
        # Pedido vindo do CRM não tem resposta pela área (ADR-0023): a Central liga.
        corpo = (f"{tipo}: a Central de Relacionamento precisa de mais informações e vai falar com você."
                 if r.origem == "crm" else f"{tipo}: responda para seguir com o atendimento.")
        comunicacao.notificar(
            sess, contact_id=r.contact_id, tipo="solicitacao_pendente", chave=f"pendente:{r.evento_id}",
            titulo="Sua solicitação precisa de uma resposta", corpo=corpo,
            link=_link(r.solicitacao_id), referencia_tipo="solicitacao", referencia_id=r.solicitacao_id, agora=agora)
    elif r.para in rotulos.CONCLUIDAS:
        comunicacao.notificar(
            sess, contact_id=r.contact_id, tipo="solicitacao_concluida", chave=f"A06:{r.solicitacao_id}",
            titulo="Sua solicitação foi concluída", corpo=f"{tipo}. Conte como foi o atendimento.",
            link=_link(r.solicitacao_id), referencia_tipo="solicitacao", referencia_id=r.solicitacao_id, agora=agora)
        comunicacao.enfileirar(sess, gatilho="A06", contact_id=r.contact_id, referencia_tipo="solicitacao",
                               referencia_id=r.solicitacao_id, destinos=[("email", "associado"), ("rd", "associado")],
                               agora=agora)
    elif r.para == "cancelada":
        # O que ainda não saiu sobre esta solicitação não sai mais (RF-SO-12).
        comunicacao.suprimir_pendentes(sess, referencia_tipo="solicitacao", referencia_id=r.solicitacao_id,
                                       motivo="fato_mudou", agora=agora)
        if r.ator == "associado":
            return  # quem cancelou já sabe; a notificação é para cancelamento pela APM
        comunicacao.notificar(
            sess, contact_id=r.contact_id, tipo="solicitacao_cancelada", chave=f"cancelada:{r.solicitacao_id}",
            titulo="Solicitação cancelada", corpo=f"{tipo}.", link=_link(r.solicitacao_id),
            referencia_tipo="solicitacao", referencia_id=r.solicitacao_id, agora=agora)


def transitar(sess: Session, *, solicitacao_id: str, para: str, ator: str, origem: str,
              contact_id: str | None = None, mensagem: str | None = None, justificativa: str | None = None,
              usuario_interno: str | None = None, cancel_motivo: str | None = None,
              request_id: str | None = None, agora: datetime | None = None) -> Resultado:
    """Aplica uma transição da tabela. `contact_id` restringe ao dono (associado:
    sempre; jobs/backoffice: None). Levanta `SolicitacaoNaoEncontrada` ou
    `TransicaoInvalida`; o chamador faz o rollback (session_scope)."""
    if para not in STATUS or ator not in ATORES or origem not in ORIGENS:
        raise TransicaoInvalida()
    origens = origens_permitidas(para, ator, origem)
    if not origens:
        raise TransicaoInvalida()
    mensagem = mensagem.strip() if isinstance(mensagem, str) else None
    justificativa = justificativa.strip() if isinstance(justificativa, str) else None
    if exige_mensagem(para, ator, origem) and not mensagem:
        raise TransicaoInvalida("mensagem_obrigatoria", "Escreva a mensagem.")
    if origem == "backoffice" and not justificativa:
        raise TransicaoInvalida("justificativa_obrigatoria", "Mudança manual exige justificativa.")
    if mensagem is not None and len(mensagem) > 2000:
        raise TransicaoInvalida("mensagem_longa", "Mensagem acima de 2000 caracteres.")
    agora = agora or _agora()

    sql = _SQL_TRAVAR + (" AND contact_id = :c" if contact_id is not None else "") + " FOR UPDATE"
    linha = sess.execute(text(sql), {"id": solicitacao_id, "c": contact_id}).first()
    if linha is None:
        raise SolicitacaoNaoEncontrada()
    de = str(linha.status)
    if de in TERMINAIS or de not in origens:
        raise TransicaoInvalida()
    if ator == "associado" and origem == "ui" and linha.crm_id is not None:
        raise TransicaoInvalida("na_central", MENSAGEM_NA_CENTRAL)

    sets = ["status = :para", "atualizada_em = :agora", "sem_retorno_desde = NULL"]
    params: dict[str, object] = {"id": solicitacao_id, "de": de, "para": para, "agora": agora}
    if para == "enviada":
        sets.append("enviada_em = COALESCE(enviada_em, :agora)")
    if para in rotulos.CONCLUIDAS:
        sets.append("concluida_em = :agora")
    if para == "cancelada" and cancel_motivo:
        sets.append("cancel_motivo = :motivo")
        params["motivo"] = cancel_motivo[:200]
    if origem != "crm" and linha.crm_id is not None:
        sets += ["crm_sync = 'pendente'", "crm_tentativas = 0", "crm_proxima_em = :agora"]
    afetadas = sess.execute(
        text(f"UPDATE solicitacao SET {', '.join(sets)} WHERE id = :id AND status = :de"), params
    ).rowcount
    if afetadas != 1:  # defensivo: com a linha travada, só por bug
        raise TransicaoInvalida()

    evento_id = registrar_evento(
        sess, solicitacao_id=solicitacao_id, evento="transicao", de=de, para=para, ator=ator, origem=origem,
        agora=agora, usuario_interno=usuario_interno, justificativa=justificativa, mensagem=mensagem,
        request_id=request_id)
    resultado = Resultado(solicitacao_id, str(linha.contact_id), de, para, linha.tipo_servico,
                          linha.tipo_ativacao, evento_id, ator, origem)
    _efeitos(sess, resultado, agora=agora)
    return resultado


def marcar_sem_retorno(sess: Session, *, solicitacao_id: str, segundo: bool = False,
                       agora: datetime | None = None, request_id: str | None = None) -> bool:
    """Marcador A05 (ADR-0018 item 3) — para o job `marcar_sem_retorno` (frente C).

    Primeiro vencimento: põe `sem_retorno_desde` (só em `enviada`/
    `em_atendimento`, só se vazio, só com prazo vencido), evento `sem_retorno`,
    notificação e outbox A05 (associado + responsável interno). Segundo
    vencimento (`segundo=True`, prazo × 2): evento `sem_retorno_2` e pedido na
    fila de ligações. Idempotente: devolve False se nada mudou."""
    agora = agora or _agora()
    linha = sess.execute(text(
        "SELECT id, contact_id, status, tipo_servico, enviada_em, prazo_retorno_dias, sem_retorno_desde "
        "FROM solicitacao WHERE id = :id FOR UPDATE"), {"id": solicitacao_id}).first()
    if linha is None or linha.status not in ("enviada", "em_atendimento") or linha.enviada_em is None:
        return False
    fator = 2 if segundo else 1
    if linha.enviada_em + timedelta(days=int(linha.prazo_retorno_dias) * fator) >= agora:
        return False
    cid = str(linha.contact_id)
    if not segundo:
        if linha.sem_retorno_desde is not None:
            return False
        afetadas = sess.execute(text(
            "UPDATE solicitacao SET sem_retorno_desde = :agora, atualizada_em = :agora "
            "WHERE id = :id AND status = :st AND sem_retorno_desde IS NULL"),
            {"agora": agora, "id": solicitacao_id, "st": linha.status}).rowcount
        if afetadas != 1:
            return False
        registrar_evento(sess, solicitacao_id=solicitacao_id, evento="sem_retorno", de=None, para=linha.status,
                         ator="sistema", origem="job", agora=agora, request_id=request_id)
        comunicacao.notificar(
            sess, contact_id=cid, tipo="solicitacao_sem_retorno", chave=f"A05:{solicitacao_id}",
            titulo="A APM está cobrando o retorno", corpo=f"{rotulos.rotulo_tipo(linha.tipo_servico)}: o prazo venceu "
            "e já estamos cobrando.", link=_link(solicitacao_id), referencia_tipo="solicitacao",
            referencia_id=solicitacao_id, agora=agora)
        comunicacao.enfileirar(sess, gatilho="A05", contact_id=cid, referencia_tipo="solicitacao",
                               referencia_id=solicitacao_id,
                               destinos=[("email", "associado"), ("interno", "equipe"), ("rd", "associado")],
                               agora=agora)
        return True
    if linha.sem_retorno_desde is None:
        return False
    if not comunicacao.pedir_ligacao(sess, contact_id=cid, motivo="sem_retorno_2", solicitacao_id=solicitacao_id,
                                     agora=agora):
        return False
    registrar_evento(sess, solicitacao_id=solicitacao_id, evento="sem_retorno_2", de=None, para=linha.status,
                     ator="sistema", origem="job", agora=agora, request_id=request_id)
    return True
