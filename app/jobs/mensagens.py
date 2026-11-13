"""Job das mensagens do associado para a conversa no CRM (ADR-0024).

`enviar_mensagens` (20 s, efeito EXTERNO): outbox `solicitacao_mensagem` →
`solicitacao.interagir` pela conta de jobs (a única com `ferramentas:escrever`). O `id`
da linha é o `interacao_id` do hub: repetir é seguro (o hub devolve `criada=false`).

- Sucesso → `enviada`, `enviada_em` e **`texto = NULL`** (a conversa é lida do CRM; a
  área não guarda o que o associado escreveu).
- 429 `limite_titular` (10/h e 40/dia por associado, somando App e Minha APM) → todas as
  mensagens pendentes do contato esperam o `Retry-After`, sem gastar tentativa.
- Resposta definitiva do CRM (registro fechado, mensagens bloqueadas pela Central, pai
  inexistente, conflito de id, entrada recusada) → `falhou`; a tela mostra "não enviada".
- Erro sistêmico (limite da conta, escrita desligada, mensagens desligadas no hub, conta
  sem canal) → para a rodada sem gastar tentativa. Demais → recuo 1, 2, 4 … 60 min; 10
  tentativas → `falhou` + `evento_log`.
- Ordem: dentro de um pai as mensagens saem na ordem em que foram escritas — pai com
  mensagem mais antiga esperando (recuo ou falha nesta rodada) não envia as seguintes.
- Purga: texto de mensagem `falhou` há mais de `PURGA_FALHA_DIAS` dias vira NULL (efeito
  local, roda nos dois modos).

Só chama o hub com `JOBS_APLICAR=1` e `HUB_ESCRITA_HABILITADA=true`. Nenhuma chamada
HTTP acontece com transação aberta. O texto nunca vai para log, `evento_log` ou `evento_uso`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from .. import audit
from ..config import get_settings
from ..integracoes.hub import ClienteHub, HubError, PedidoInteracao, obter_hub
from .base import Contexto
from .politica import DISJUNTOR_SEGUIDAS, PERMANENTE, SISTEMICO, classificar_hub, codigo_seguro, proxima_tentativa
from .solicitacoes import _consulta, _filtro_contatos, _sessao

logger = logging.getLogger("area_associado.jobs.mensagens")

PURGA_FALHA_DIAS = 7
# Recusas esperadas do CRM (o associado escreveu em registro que a Central fechou ou
# bloqueou no meio do caminho): aviso, não erro de operação.
_RECUSAS_ESPERADAS = frozenset({"registro_fechado", "interacao_nao_permitida"})

_SQL_FILA = (
    "SELECT id, contact_id, registro_id, entidade, texto, tentativas FROM solicitacao_mensagem "
    "WHERE status IN ('pendente', 'erro') AND proxima_em <= :agora AND texto IS NOT NULL"
)


def fila(agora: datetime, lote: int) -> list[Any]:
    params: dict[str, Any] = {"agora": agora, "lote": int(lote)}
    sql = _SQL_FILA + _filtro_contatos(params) + " ORDER BY criada_em, id LIMIT :lote"
    with _sessao() as db:
        return list(db.execute(_consulta(sql, params), params).all())


def _pais_em_espera(agora: datetime) -> set[str]:
    """Pais com mensagem aguardando o recuo: as mais novas não podem passar na frente."""
    with _sessao() as db:
        return {str(r.registro_id) for r in db.execute(text(
            "SELECT DISTINCT registro_id FROM solicitacao_mensagem "
            "WHERE status IN ('pendente', 'erro') AND proxima_em > :agora"), {"agora": agora})}


def purgar_falhas(agora: datetime) -> int:
    with _sessao() as db:
        return int(db.execute(text(
            "UPDATE solicitacao_mensagem SET texto = NULL "
            "WHERE status = 'falhou' AND texto IS NOT NULL AND criada_em < :limite"
        ), {"limite": agora - timedelta(days=PURGA_FALHA_DIAS)}).rowcount or 0)


def _confirmar(m: Any, agora: datetime) -> bool:
    with _sessao() as db:
        return bool(db.execute(text(
            "UPDATE solicitacao_mensagem SET status = 'enviada', enviada_em = :agora, texto = NULL, "
            " erro_codigo = NULL WHERE id = :id AND status IN ('pendente', 'erro')"
        ), {"agora": agora, "id": m.id}).rowcount)


def _adiar_contato(contact_id: str, quando: datetime) -> None:
    """Limite do titular: tudo o que o contato tem na fila espera até `quando`."""
    with _sessao() as db:
        db.execute(text(
            "UPDATE solicitacao_mensagem SET proxima_em = :quando, erro_codigo = 'limite_titular' "
            "WHERE contact_id = :c AND status IN ('pendente', 'erro') AND proxima_em < :quando"
        ), {"quando": quando, "c": contact_id})


def _registrar_falha(m: Any, classe: str, codigo: str, agora: datetime) -> None:
    tentativas = int(m.tentativas) + 1
    proxima = None if classe == PERMANENTE else proxima_tentativa(tentativas, agora)
    with _sessao() as db:
        afetadas = db.execute(text(
            "UPDATE solicitacao_mensagem SET status = :st, tentativas = :t, proxima_em = :prox, erro_codigo = :cod "
            "WHERE id = :id AND status IN ('pendente', 'erro') AND tentativas = :lidas"
        ), {"st": "falhou" if proxima is None else "erro", "t": min(tentativas, 20), "prox": proxima or agora,
            "cod": codigo, "id": m.id, "lidas": int(m.tentativas)}).rowcount
    if afetadas and proxima is None:
        esperada = codigo in _RECUSAS_ESPERADAS
        logger.log(logging.WARNING if esperada else logging.ERROR,
                   "mensagens: %s marcada falhou (%s, %d tentativa(s))", m.id, codigo, tentativas)
        audit.registrar_sistema(categoria="negocio" if esperada else "erro", tipo="solicitacao_mensagem_falhou",
                                severidade="aviso" if esperada else "erro", origem="enviar_mensagens",
                                contact_id=str(m.contact_id),
                                detalhes={"mensagem_id": str(m.id), "solicitacao_id": str(m.registro_id),
                                          "tentativas": tentativas, "codigo": codigo,
                                          "permanente": classe == PERMANENTE})


def enviar_mensagens(ctx: Contexto, *, hub: ClienteHub | None = None) -> None:
    s = get_settings()
    purgadas = purgar_falhas(ctx.agora)
    if purgadas:
        logger.info("mensagens: texto de %d mensagem(ns) não enviada(s) purgado", purgadas)
    itens = fila(ctx.agora, s.jobs_lote)
    ctx.lidos = len(itens)
    if not itens:
        return
    if not ctx.aplicar:
        logger.info("mensagens (simulação): %d mensagem(ns) na fila do CRM", len(itens))
        return
    if not s.hub_escrita_habilitada:
        logger.warning("mensagens: HUB_ESCRITA_HABILITADA=false — %d mensagem(ns) aguardando", len(itens))
        ctx.erro_sistemico = "mensagens em espera: escrita no hub desligada"
        return
    hub = hub or obter_hub()
    pais_parados = _pais_em_espera(ctx.agora)
    contatos_parados: set[str] = set()
    seguidas = 0
    for m in itens:
        if ctx.parar():
            return
        ctx.pulso()
        pai, cid = str(m.registro_id), str(m.contact_id)
        if pai in pais_parados or cid in contatos_parados:
            continue
        try:
            pedido = PedidoInteracao(contact_id=cid, registro_id=pai, entidade=str(m.entidade),
                                     interacao_id=str(m.id), texto=str(m.texto))
            pedido.argumentos()  # fora do contrato = permanente, sem chamar o hub
        except ValueError:
            ctx.erros += 1
            _registrar_falha(m, PERMANENTE, "conteudo_invalido", ctx.agora)
            continue
        try:
            hub.solicitacao_interagir(pedido)
        except HubError as exc:
            if exc.codigo == "limite_titular":
                espera = max(60, int(exc.retry_after or 3600))
                _adiar_contato(cid, ctx.agora + timedelta(seconds=espera))
                contatos_parados.add(cid)
                logger.info("mensagens: limite do titular — mensagens do contato adiadas por %d s", espera)
                continue
            falha = classificar_hub(exc)
            if falha.classe == SISTEMICO:
                ctx.erro_sistemico = f"disjuntor: {falha.codigo}"
                logger.warning("mensagens: rodada interrompida (%s); itens restantes não gastam tentativa",
                               falha.codigo)
                return
            ctx.erros += 1
            _registrar_falha(m, falha.classe, codigo_seguro(falha.codigo), ctx.agora)
            if falha.classe != PERMANENTE:
                pais_parados.add(pai)  # as seguintes do mesmo pai esperam esta
                seguidas += 1
                if seguidas >= DISJUNTOR_SEGUIDAS:
                    ctx.erro_sistemico = f"disjuntor: {seguidas} falhas seguidas ({falha.codigo})"
                    logger.warning("mensagens: %d falhas seguidas do hub — rodada interrompida", seguidas)
                    return
            continue
        seguidas = 0
        if _confirmar(m, ctx.agora):
            ctx.gravados += 1
