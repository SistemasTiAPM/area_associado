"""Jobs das solicitações (REQUISITOS §7.3 e §7.5; ADR-0003 §5, ADR-0018).

- `espelhar_solicitacoes` (1 min, efeito EXTERNO): outbox `crm_*` →
  `solicitacao.espelhar` (sem `crm_id`) ou `solicitacao.status_atualizar` (com
  `crm_id`). Sucesso grava `crm_id`/`crm_sync=ok` e promove `criada → enviada`
  (`canal_envio='crm'`) pela máquina de estados (ator `sistema`, origem `job`).
  Falha: recuo 1, 2, 4 … 60 min; 10 tentativas (ou erro permanente) → `falhou`
  + `evento_log` severidade `erro`. Respeita `crm_proxima_em` (janela de
  arrependimento do cancelamento da associação). Só chama o hub com
  `JOBS_APLICAR=1` e `HUB_ESCRITA_HABILITADA=true`.
- `sincronizar_solicitacoes` (5 min, leitura do hub): `solicitacao.alteracoes_consultar`
  com cursor (guardado em `job_execucao.posicao` da última execução ok) e
  transições pela máquina com origem `crm`. Terminal local prevalece
  (divergência em `evento_log`; cancelamento local é reenviado). Só com `JOBS_APLICAR=1`.
- `marcar_sem_retorno` (15 min, efeito local): marcador A05 no 1.º vencimento do
  prazo e fila de ligações no 2.º — `maquina.marcar_sem_retorno` da frente A.

Nenhuma chamada HTTP acontece com transação aberta: lê → chama o hub → abre
transação curta, trava a linha e confere se nada mudou no meio (`status` e
`atualizada_em`); se mudou, o espelho fica `pendente` para levar o estado atual.
`evento_uso` sai depois do commit (regra 20).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text

from .. import audit, uso
from ..config import get_settings
from ..dominio.solicitacoes import maquina, rotulos
from ..integracoes.hub import AlteracaoCrm, ClienteHub, HubError, alteracao_de_linha, obter_hub
from .base import Contexto
from .politica import DISJUNTOR_SEGUIDAS, PERMANENTE, SISTEMICO, classificar_hub, proxima_tentativa

logger = logging.getLogger("area_associado.jobs.solicitacoes")

LOTE_SYNC = 100
PAGINAS_SYNC = 5
LOTE_SEM_RETORNO = 500

# Situação da `task` (hub) → status da área (REQUISITOS §7.5; P-06 ainda precisa
# distinguir "não seguiu" de "cancelada pela APM": as duas viram `concluida_negativa`).
MAPA_CRM: dict[str, str | None] = {
    "nao_iniciada": None,  # a área não regride (criada/enviada já cobrem)
    "em_andamento": "em_atendimento",
    "aguardando_associado": "pendente_associado",
    "concluida": "concluida_positiva",
    "nao_seguiu": "concluida_negativa",
    "cancelada": "concluida_negativa",
}
_RE_CPF = re.compile(r"(^|[^0-9a-fA-F])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9a-fA-F]|$)")


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem

    return session_scope()


def _iso(valor: datetime | None) -> str | None:
    return valor.strftime("%Y-%m-%dT%H:%M:%SZ") if valor else None


def _json(valor: Any) -> dict[str, Any]:
    if isinstance(valor, (bytes, str)):
        valor = json.loads(valor)
    return valor if isinstance(valor, dict) else {}


def _registrar_uso(transicoes: Sequence[tuple[str, str, str, str]], origem_detalhe: str) -> None:
    """(solicitacao_id, contact_id, de, para) → `solicitacao_status_alterado` (origem `job`)."""
    for sid, cid, de, para in transicoes:
        uso.registrar("solicitacao_status_alterado", "solicitacao", sid, contact_id=cid, sub=None, origem="job",
                      detalhes={"de": de, "para": para, "origem": origem_detalhe})


# =================================================================== espelho
_SQL_PENDENTES = (
    "SELECT id, contact_id, tipo_servico, beneficio_id, parceiro_id, tipo_ativacao, canal_envio, status, crm_id, "
    " crm_tentativas, prazo_retorno_dias, dados, cancel_motivo, criada_em, atualizada_em "
    "FROM solicitacao WHERE crm_sync IN ('pendente', 'erro') AND crm_proxima_em <= :agora"
)
_SQL_ULTIMA_MENSAGEM = text(
    "SELECT ator, mensagem_publica FROM solicitacao_evento WHERE solicitacao_id = :id AND evento = 'transicao' "
    "ORDER BY ocorrido_em DESC, id DESC LIMIT 1"
)


def pendentes_do_espelho(agora: datetime, lote: int, ids: Sequence[str] | None = None) -> list[Any]:
    sql = _SQL_PENDENTES
    params: dict[str, Any] = {"agora": agora, "lote": int(lote)}
    if ids is not None:
        sql += " AND id IN :ids"
        params["ids"] = list(ids)
    consulta = text(sql + " ORDER BY crm_proxima_em, id LIMIT :lote")
    if ids is not None:
        consulta = consulta.bindparams(bindparam("ids", expanding=True))
    with _sessao() as db:
        return list(db.execute(consulta, params).all())


def payload_espelho(r: Any) -> dict[str, Any]:
    """Entrada de `solicitacao.espelhar` (docs/CONTRATO-HUB.md). Chave = `contact_id`
    + `solicitacao_id`; `campos` = o que o associado preencheu (allowlist do tipo,
    CHECK anti-CPF no banco). Nunca CPF, e-mail ou telefone."""
    carga: dict[str, Any] = {
        "contact_id": str(r.contact_id),
        "solicitacao_id": str(r.id),
        "tipo": r.tipo_servico,
        "titulo": f"Minha APM: {rotulos.rotulo_tipo(r.tipo_servico)}"[:200],
        "status": r.status,
        "criada_em": _iso(r.criada_em),
        "prazo_retorno_dias": int(r.prazo_retorno_dias),
        "campos": _json(r.dados),
    }
    if r.beneficio_id:
        carga["beneficio_id"] = r.beneficio_id
        carga["parceiro_id"] = r.parceiro_id
    return carga


def payload_status(db: Any, r: Any) -> dict[str, Any]:
    """Entrada de `solicitacao.status_atualizar`: status atual + a última resposta
    do associado (se a última transição foi dele) + motivo do cancelamento."""
    carga: dict[str, Any] = {"contact_id": str(r.contact_id), "solicitacao_id": str(r.id), "crm_id": str(r.crm_id),
                             "status": r.status}
    ultima = db.execute(_SQL_ULTIMA_MENSAGEM, {"id": r.id}).first()
    if ultima is not None and ultima.ator == "associado" and ultima.mensagem_publica:
        carga["mensagem_associado"] = str(ultima.mensagem_publica)[:2000]
    if r.status == "cancelada" and r.cancel_motivo:
        carga["cancel_motivo"] = str(r.cancel_motivo)[:200]
    return carga


_SQL_TRAVAR = text(
    "SELECT status, atualizada_em, canal_envio, crm_sync, crm_tentativas FROM solicitacao WHERE id = :id FOR UPDATE"
)


def _confirmar(r: Any, crm_id: str, agora: datetime) -> list[tuple[str, str, str, str]]:
    """Sucesso no hub. Mesmo `status`/`atualizada_em` de quando o item foi lido →
    `crm_sync=ok` (+ promoção a `enviada`); mudou no meio → `pendente` já, para o
    próximo ciclo levar o estado novo. Devolve as transições (para o evento_uso)."""
    transicoes: list[tuple[str, str, str, str]] = []
    with _sessao() as db:
        atual = db.execute(_SQL_TRAVAR, {"id": r.id}).first()
        if atual is None:  # impossível sem DELETE; defensivo
            return []
        mudou = (atual.status, atual.atualizada_em) != (r.status, r.atualizada_em)
        if not mudou and atual.status == "criada" and atual.canal_envio == "crm":
            # crm_id ainda NULL aqui: a máquina não reabre o espelho por causa desta promoção.
            res = maquina.transitar(db, solicitacao_id=str(r.id), para="enviada", ator="sistema", origem="job",
                                    agora=agora)
            transicoes.append((res.solicitacao_id, res.contact_id, res.de, res.para))
        db.execute(text(
            "UPDATE solicitacao SET crm_id = :crm, crm_sync = :sync, crm_tentativas = 0, crm_proxima_em = :agora "
            "WHERE id = :id"
        ), {"crm": crm_id, "sync": "pendente" if mudou else "ok", "agora": agora, "id": r.id})
    return transicoes


def _registrar_falha(r: Any, classe: str, codigo: str, agora: datetime) -> bool:
    """Conta a tentativa (recuo) ou marca `falhou`. Devolve True se marcou `falhou`.
    Só mexe se a linha não mudou desde a leitura (uma ação nova reabre o ciclo)."""
    tentativas = int(r.crm_tentativas) + 1
    proxima = None if classe == PERMANENTE else proxima_tentativa(tentativas, agora)
    with _sessao() as db:
        afetadas = db.execute(text(
            "UPDATE solicitacao SET crm_sync = :sync, crm_tentativas = :t, crm_proxima_em = :prox "
            "WHERE id = :id AND crm_sync IN ('pendente', 'erro') AND crm_tentativas = :lidas "
            "AND atualizada_em = :lida"
        ), {"sync": "falhou" if proxima is None else "erro", "t": min(tentativas, 20), "prox": proxima or agora,
            "id": r.id, "lidas": int(r.crm_tentativas), "lida": r.atualizada_em}).rowcount
    if afetadas and proxima is None:
        logger.error("espelho: solicitação %s marcada falhou (%s, %d tentativa(s))", r.id, codigo, tentativas)
        audit.registrar_sistema(categoria="erro", tipo="solicitacao_espelho_falhou", severidade="erro",
                                origem="espelhar_solicitacoes", contact_id=str(r.contact_id),
                                detalhes={"solicitacao_id": str(r.id), "tentativas": tentativas, "codigo": codigo,
                                          "permanente": classe == PERMANENTE})
    return bool(afetadas) and proxima is None


def _nada_a_espelhar(r: Any, agora: datetime) -> bool:
    """Cancelada antes de existir no CRM (ex.: desistência na janela de
    arrependimento): não há o que espelhar. `crm_sync=ok` com `crm_id` NULL."""
    with _sessao() as db:
        return bool(db.execute(text(
            "UPDATE solicitacao SET crm_sync = 'ok', crm_tentativas = 0, crm_proxima_em = :agora "
            "WHERE id = :id AND crm_id IS NULL AND status = 'cancelada' AND crm_sync IN ('pendente', 'erro')"
        ), {"agora": agora, "id": r.id}).rowcount)


def espelhar_solicitacoes(ctx: Contexto, *, hub: ClienteHub | None = None, ids: Sequence[str] | None = None) -> None:
    s = get_settings()
    itens = pendentes_do_espelho(ctx.agora, s.jobs_lote, ids)
    ctx.lidos = len(itens)
    if not itens:
        return
    if not ctx.aplicar:
        logger.info("espelho (simulação): %d solicitação(ões) seriam enviadas ao CRM: %s", len(itens),
                    ", ".join(f"{r.id}:{'status_atualizar' if r.crm_id else 'espelhar'}" for r in itens[:10]))
        return
    if not s.hub_escrita_habilitada:
        logger.warning("espelho: HUB_ESCRITA_HABILITADA=false — %d solicitação(ões) aguardando", len(itens))
        ctx.erro_sistemico = "espelho em espera: escrita no hub desligada"
        return
    hub = hub or obter_hub()
    seguidas = 0
    for r in itens:
        if ctx.parar():
            return
        ctx.pulso()
        if r.crm_id is None and r.status == "cancelada":
            if _nada_a_espelhar(r, ctx.agora):
                ctx.gravados += 1
            continue
        try:
            if r.crm_id is None:
                crm_id = hub.solicitacao_espelhar(payload_espelho(r))
            else:
                with _sessao() as db:
                    carga = payload_status(db, r)
                hub.solicitacao_status_atualizar(carga)
                crm_id = str(r.crm_id)
        except HubError as exc:
            falha = classificar_hub(exc)
            if falha.classe == SISTEMICO:
                ctx.erro_sistemico = f"disjuntor: {falha.codigo}"
                logger.warning("espelho: rodada interrompida (%s); itens restantes não gastam tentativa", falha.codigo)
                return
            ctx.erros += 1
            _registrar_falha(r, falha.classe, falha.codigo, ctx.agora)
            if falha.classe != PERMANENTE:
                seguidas += 1
                if seguidas >= DISJUNTOR_SEGUIDAS:
                    ctx.erro_sistemico = f"disjuntor: {seguidas} falhas seguidas ({falha.codigo})"
                    logger.warning("espelho: %d falhas seguidas do hub — rodada interrompida", seguidas)
                    return
            continue
        seguidas = 0
        transicoes = _confirmar(r, crm_id, ctx.agora)
        ctx.gravados += 1
        _registrar_uso(transicoes, "sistema")


# ============================================================ sincronização
def _caminho(de: str, para: str) -> list[str]:
    """Passos pela máquina com (apm, crm). Ex.: `enviada → pendente_associado`
    passa por `em_atendimento` (o CRM pode pular etapas entre duas leituras)."""
    if maquina.pode_transitar(de, para, "apm", "crm"):
        return [para]
    meio = "em_atendimento"
    if para != meio and maquina.pode_transitar(de, meio, "apm", "crm") \
            and maquina.pode_transitar(meio, para, "apm", "crm"):
        return [meio, para]
    return []


def _mensagem_crm(texto: str | None) -> str | None:
    """Mensagem pública vinda do CRM: uma linha limpa, ≤ 2000, nunca com CPF."""
    if not texto:
        return None
    limpo = " ".join("".join(c if c.isprintable() else " " for c in texto).split())[:2000]
    if not limpo or _RE_CPF.search(limpo):
        return None
    return limpo


def _divergencia(alt: AlteracaoCrm, motivo: str, local: str | None, contact_id: str | None) -> None:
    logger.warning("sync: divergência em %s (%s; local=%s crm=%s)", alt.solicitacao_id, motivo, local, alt.situacao)
    audit.registrar_sistema(categoria="negocio", tipo="solicitacao_divergencia_crm", severidade="aviso",
                            origem="sincronizar_solicitacoes", contact_id=contact_id,
                            detalhes={"solicitacao_id": alt.solicitacao_id, "motivo": motivo, "status_local": local,
                                      "situacao_crm": alt.situacao})


def aplicar_alteracao(alt: AlteracaoCrm, agora: datetime) -> tuple[bool, list[tuple[str, str, str, str]]]:
    """Aplica UMA alteração do CRM. Devolve (gravou, transições)."""
    transicoes: list[tuple[str, str, str, str]] = []
    pendencia: tuple[str, str | None, str | None] | None = None
    with _sessao() as db:
        r = db.execute(text(
            "SELECT id, contact_id, status, crm_id, crm_sync FROM solicitacao WHERE id = :id FOR UPDATE"
        ), {"id": alt.solicitacao_id}).first()
        if r is None:
            logger.warning("sync: alteração de solicitação desconhecida (%s) — ignorada", alt.solicitacao_id)
            return False, []
        local, cid = str(r.status), str(r.contact_id)
        if cid != alt.contact_id or (r.crm_id is not None and str(r.crm_id) != alt.crm_id):
            pendencia = ("identidade_divergente", local, None)
        else:
            alvo = MAPA_CRM[alt.situacao]
            if alvo is None or alvo == local:
                return False, []
            if local in rotulos.TERMINAIS:
                pendencia = ("terminal_local_prevalece", local, cid)
                if local == "cancelada" and r.crm_sync == "ok" and r.crm_id is not None:
                    # Cancelamento local reenviado ao CRM (REQUISITOS §7.3).
                    db.execute(text(
                        "UPDATE solicitacao SET crm_sync = 'pendente', crm_tentativas = 0, crm_proxima_em = :agora "
                        "WHERE id = :id AND crm_sync = 'ok'"), {"agora": agora, "id": r.id})
            elif r.crm_sync != "ok":
                # Mudança local ainda não espelhada: o local prevalece; o CRM recebe o
                # estado atual no próximo espelho e a task volta pelo cursor.
                logger.info("sync: %s com espelho pendente — alteração do CRM adiada", alt.solicitacao_id)
                return False, []
            else:
                passos = _caminho(local, alvo)
                mensagem = _mensagem_crm(alt.mensagem_publica)
                if not passos:
                    pendencia = ("transicao_nao_prevista", local, cid)
                elif "pendente_associado" in passos and mensagem is None:
                    pendencia = ("pendente_sem_mensagem", local, cid)
                else:
                    for passo in passos:
                        res = maquina.transitar(db, solicitacao_id=alt.solicitacao_id, para=passo, ator="apm",
                                                origem="crm", agora=agora,
                                                mensagem=mensagem if passo == "pendente_associado" else None)
                        transicoes.append((res.solicitacao_id, res.contact_id, res.de, res.para))
    if pendencia is not None:
        motivo, status_local, contato = pendencia
        _divergencia(alt, motivo, status_local, contato)
        return False, []
    return bool(transicoes), transicoes


def sincronizar_solicitacoes(ctx: Contexto, *, hub: ClienteHub | None = None) -> None:
    if not ctx.aplicar:
        logger.info("sync (simulação): consultaria alterações no CRM desde a posição %s",
                    ctx.posicao_anterior or "inicial")
        return
    hub = hub or obter_hub()
    posicao = ctx.posicao_anterior
    for _ in range(PAGINAS_SYNC):
        if ctx.parar():
            return
        try:
            linhas = hub.solicitacao_alteracoes_consultar(posicao, LOTE_SYNC)
        except HubError as exc:
            ctx.erro_sistemico = f"hub: {classificar_hub(exc).codigo}"
            return
        for linha in linhas:
            ctx.pulso()
            ctx.lidos += 1
            alt = alteracao_de_linha(linha)
            if alt is None:
                ctx.erros += 1
                logger.error("sync: linha fora do contrato descartada (revisar contrato do hub)")
                # Sem cursor válido não dá para avançar com segurança: para aqui.
                ctx.erro_sistemico = "sync: linha fora do contrato"
                ctx.posicao = posicao
                return
            try:
                gravou, transicoes = aplicar_alteracao(alt, ctx.agora)
            except (maquina.TransicaoInvalida, maquina.SolicitacaoNaoEncontrada):
                ctx.erros += 1
                _divergencia(alt, "transicao_recusada", None, alt.contact_id)
                gravou, transicoes = False, []
            if gravou:
                ctx.gravados += 1
            _registrar_uso(transicoes, "apm")
            posicao = alt.cursor
            ctx.posicao = posicao
        if len(linhas) < LOTE_SYNC:
            return


# ============================================================== sem retorno
_SQL_PRIMEIRO = text(
    "SELECT id FROM solicitacao WHERE status IN ('enviada', 'em_atendimento') AND sem_retorno_desde IS NULL "
    "AND enviada_em IS NOT NULL AND enviada_em + INTERVAL prazo_retorno_dias DAY < :agora "
    "ORDER BY enviada_em LIMIT :lote"
)
_SQL_SEGUNDO = text(
    "SELECT s.id FROM solicitacao s WHERE s.status IN ('enviada', 'em_atendimento') "
    "AND s.sem_retorno_desde IS NOT NULL AND s.enviada_em + INTERVAL (s.prazo_retorno_dias * 2) DAY < :agora "
    "AND NOT EXISTS (SELECT 1 FROM fila_ligacao f WHERE f.motivo = 'sem_retorno_2' "
    "                AND f.referencia_tipo = 'solicitacao' AND f.referencia_id = s.id) "
    "ORDER BY s.enviada_em LIMIT :lote"
)


def marcar_sem_retorno(ctx: Contexto) -> None:
    """Efeito local (marcador, notificação, outbox, fila): roda nos dois modos."""
    for consulta, segundo in ((_SQL_PRIMEIRO, False), (_SQL_SEGUNDO, True)):
        with _sessao() as db:
            ids = [str(r.id) for r in db.execute(consulta, {"agora": ctx.agora, "lote": LOTE_SEM_RETORNO})]
        for sid in ids:
            if ctx.parar():
                return
            ctx.pulso()
            ctx.lidos += 1
            with _sessao() as db:
                if maquina.marcar_sem_retorno(db, solicitacao_id=sid, segundo=segundo, agora=ctx.agora):
                    ctx.gravados += 1
