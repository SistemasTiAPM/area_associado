"""Jobs das solicitações (REQUISITOS §7.3 e §7.5; ADR-0003 §5, ADR-0018, ADR-0023).

- `espelhar_solicitacoes` (1 min, efeito EXTERNO): outbox `crm_*`.
  Pedido sem `crm_id` e com destino no catálogo (`catalogo_crm`) → `solicitacao.criar`
  (o `registro_id` é o próprio `id`; idempotente) com o slug do catálogo comum com o App
  e, em oportunidade, o `produto_id` (ADR-0024). 503 `produto_indisponivel` → o MESMO
  pedido sem `produto_id`; 422 `produto_inativo` → o pedido é cancelado pelo sistema com
  "Este serviço não está disponível no momento.". Sucesso grava `crm_id = id`,
  entidade, protocolo e o par `statecode/statuscode` da criação e promove
  `criada → enviada` (`canal_envio='crm'`) pela máquina (ator `sistema`, origem `job`).
  Pedido COM `crm_id` (mudança local depois do envio) ou sem destino no catálogo →
  `crm_sync='retido'` + aviso no `evento_log`: o hub não tem ferramenta de status, e o
  que fica retido é reprocessável quando houver (`WHERE crm_sync = 'retido'`).
  Falha: recuo 1, 2, 4 … 60 min; 10 tentativas (ou erro permanente) → `falhou`
  + `evento_log` severidade `erro`. Respeita `crm_proxima_em` (janela de
  arrependimento do cancelamento da associação). Só chama o hub com
  `JOBS_APLICAR=1` e `HUB_ESCRITA_HABILITADA=true`.
- `sincronizar_solicitacoes` (15 min, leitura do hub): para cada contato com pedido no
  CRM, não terminal e consultado há mais de `JOBS_SYNC_CADENCIA_H` horas,
  `solicitacao.listar` (até `JOBS_SYNC_LIMITE` linhas; 50 se o pedido não estiver na
  página) e casamento por `registro_id`. Transita SÓ quando o par
  `statecode/statuscode` MUDA em relação ao último visto (`crm_estado/crm_status`):
  depois de o associado agir na área o CRM continua no estado anterior, e reagir
  ao estado faria o pedido oscilar. Teto diário de linhas lidas
  (`JOBS_SYNC_LINHAS_DIA`): a cota PII do hub conta LINHAS. Só com `JOBS_APLICAR=1`.
- `marcar_sem_retorno` (15 min, efeito local): marcador A05 no 1.º vencimento do
  prazo e fila de ligações no 2.º — `maquina.marcar_sem_retorno` da frente A.

`JOBS_ENSAIO_CONTATOS` (lista de contact_id) restringe espelho e sincronização a esses
contatos — ensaio em produção sem tocar pedido de associado real.

Nenhuma chamada HTTP acontece com transação aberta: lê → chama o hub → abre
transação curta, trava a linha e confere se nada mudou no meio (`status` e
`atualizada_em`); se mudou, o espelho fica `pendente` para tratar o estado novo.
`evento_uso` sai depois do commit (regra 20).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import bindparam, text

from .. import audit, uso
from ..config import get_settings
from ..dominio.solicitacoes import catalogo_crm, crm, maquina, rotulos
from ..dominio.solicitacoes.schemas import FUSO
from ..integracoes.hub import ClienteHub, CriacaoCrm, HubError, PedidoCrm, RegistroCrm, obter_hub
from .base import Contexto
from .politica import DISJUNTOR_SEGUIDAS, PERMANENTE, SISTEMICO, classificar_hub, proxima_tentativa

logger = logging.getLogger("area_associado.jobs.solicitacoes")

LOTE_SEM_RETORNO = 500
LIMITE_AMPLIADO = 50
PAUSA_SYNC_S = 0.25  # entre contatos: ≤ 4 chamadas/s, longe dos 300/min da conta

# statecode/statuscode do CRM → status da área. Códigos padrão do Dataverse;
# customização do tenant a confirmar (pendência no hub). None = não muda a área
# (0/1 "Em andamento" é o status de CRIAÇÃO: ninguém da Central abriu ainda).
_OCORRENCIA: dict[tuple[int, int], str | None] = {
    (0, 1): None,                    # Em andamento (criação)
    (0, 2): "em_atendimento",        # Em espera
    (0, 3): "pendente_associado",    # Aguardando detalhes
    (0, 4): "em_atendimento",        # Pesquisando
    (1, 5): "concluida_positiva",    # Problema resolvido
    (1, 1000): "concluida_positiva",  # Informações fornecidas
    (2, 6): "concluida_negativa",    # Cancelada
    (2, 2000): None,                 # Mesclada em outra ocorrência: segue lá (divergência)
    # Conversa na Timeline (ADR-0024): fluxos do CRM marcam quem falou por último.
    (0, 100000001): "em_atendimento",      # Respondido pelo associado
    (0, 100000002): "pendente_associado",  # Respondido pela Central
}
_OPORTUNIDADE: dict[tuple[int, int], str | None] = {
    (0, 1): None,                    # Em andamento (criação)
    (0, 2): "em_atendimento",        # Em espera
    (0, 100000001): "em_atendimento",      # Respondido pelo associado
    (0, 100000002): "pendente_associado",  # Respondido pela Central
}
STATUS_RESPONDIDO_CENTRAL = 100000002
_ESTADO_FINAL = {1: "concluida_positiva", 2: "concluida_negativa"}  # resolvida/ganha · cancelada/perdida


def mapear_crm(entidade: str, statecode: int, statuscode: int) -> tuple[str | None, bool]:
    """(status alvo da área ou None, código conhecido). Estado final (1/2) com
    statuscode customizado vale pelo statecode; ativo (0) desconhecido não muda nada."""
    tabela = _OCORRENCIA if entidade == "ocorrencia" else _OPORTUNIDADE
    if (statecode, statuscode) in tabela:
        return tabela[(statecode, statuscode)], (statecode, statuscode) != (2, 2000)
    if statecode in _ESTADO_FINAL:
        return _ESTADO_FINAL[statecode], False
    return None, False


def mensagem_pendente_crm(protocolo: str | None, statuscode: int | None = None) -> str:
    """Mensagem pública de `pendente_associado` vindo do CRM: a Central respondeu na
    conversa (100000002) ou pediu detalhes por fora ("Aguardando detalhes")."""
    if statuscode == STATUS_RESPONDIDO_CENTRAL:
        return rotulos.MENSAGEM_RESPOSTA_NA_CONVERSA
    texto = rotulos.MENSAGEM_PENDENTE_CRM
    return f"{texto} Protocolo: {protocolo}." if protocolo else texto


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem

    return session_scope()


def _json(valor: Any) -> dict[str, Any]:
    if isinstance(valor, (bytes, str)):
        valor = json.loads(valor)
    return valor if isinstance(valor, dict) else {}


def _registrar_uso(transicoes: Sequence[tuple[str, str, str, str]], origem_detalhe: str) -> None:
    """(solicitacao_id, contact_id, de, para) → `solicitacao_status_alterado` (origem `job`)."""
    for sid, cid, de, para in transicoes:
        uso.registrar("solicitacao_status_alterado", "solicitacao", sid, contact_id=cid, sub=None, origem="job",
                      detalhes={"de": de, "para": para, "origem": origem_detalhe})


def _filtro_contatos(params: dict[str, Any], coluna: str = "contact_id") -> str:
    """Ensaio (`JOBS_ENSAIO_CONTATOS`): só estes contatos; vazio = todos."""
    contatos = get_settings().jobs_ensaio_contatos_lista
    if not contatos:
        return ""
    params["ensaio"] = list(contatos)
    return f" AND {coluna} IN :ensaio"


def _consulta(sql: str, params: dict[str, Any]) -> Any:
    consulta = text(sql)
    expandir = [nome for nome in ("ids", "ensaio", "abertos") if nome in params]
    return consulta.bindparams(*(bindparam(n, expanding=True) for n in expandir)) if expandir else consulta


# =================================================================== espelho
_SQL_PENDENTES = (
    "SELECT id, contact_id, tipo_servico, beneficio_id, status, crm_id, crm_protocolo, crm_tentativas, dados, "
    " atualizada_em "
    "FROM solicitacao WHERE crm_sync IN ('pendente', 'erro') AND crm_proxima_em <= :agora"
)


def pendentes_do_espelho(agora: datetime, lote: int, ids: Sequence[str] | None = None) -> list[Any]:
    sql = _SQL_PENDENTES
    params: dict[str, Any] = {"agora": agora, "lote": int(lote)}
    if ids is not None:
        sql += " AND id IN :ids"
        params["ids"] = list(ids)
    sql += _filtro_contatos(params)
    with _sessao() as db:
        return list(db.execute(_consulta(sql + " ORDER BY crm_proxima_em, id LIMIT :lote", params), params).all())


def pedido_crm(r: Any) -> PedidoCrm | None:
    """Pedido de `solicitacao.criar` a partir da linha; None = sem destino no catálogo.
    `crm.ConteudoRecusado` se o texto não puder ir (CPF/tamanho)."""
    destino = catalogo_crm.destino(r.tipo_servico, r.beneficio_id)
    if destino is None:
        return None
    texto = crm.texto_para_crm(r.tipo_servico, _json(r.dados))
    if texto.cortado:
        logger.warning("espelho: texto de %s cortado para caber no CRM (revisar limite na origem)", r.id)
    return PedidoCrm(contact_id=str(r.contact_id), registro_id=str(r.id), entidade=destino.entidade,
                     tipo=destino.tipo, titulo=texto.titulo, descricao=texto.descricao,
                     assunto_id=destino.assunto_id, time_id=destino.time_id, produto_id=destino.produto_id)


def _criar_no_crm(hub: ClienteHub, pedido: PedidoCrm) -> CriacaoCrm:
    """`solicitacao.criar`; se o CRM não consegue ligar o produto agora (503
    `produto_indisponivel`), reenvia o MESMO pedido, mesmo `registro_id`, sem `produto_id`
    (contrato do hub §7): o atendimento nasce e a linha do produto fica para a equipe."""
    try:
        return hub.solicitacao_criar(pedido)
    except HubError as exc:
        if exc.codigo != "produto_indisponivel" or pedido.produto_id is None:
            raise
        logger.warning("espelho: produto indisponível no CRM para %s — reenviando sem produto", pedido.registro_id)
        return hub.solicitacao_criar(pedido.sem_produto())


def _cancelar_servico_indisponivel(r: Any, agora: datetime) -> list[tuple[str, str, str, str]]:
    """O CRM recusou o produto do tipo (422 `produto_inativo`): a APM desligou o serviço
    depois de o associado pedir. O pedido não chegou à Central; é cancelado pelo sistema,
    com a mensagem pública, e o espelho encerra. Só se nada mudou desde a leitura."""
    with _sessao() as db:
        atual = db.execute(_SQL_TRAVAR, {"id": r.id}).first()
        if atual is None or (atual.status, atual.atualizada_em) != (r.status, r.atualizada_em) \
                or atual.status != "criada":
            return []
        res = maquina.transitar(db, solicitacao_id=str(r.id), para="cancelada", ator="sistema", origem="job",
                                mensagem=rotulos.MENSAGEM_SERVICO_INDISPONIVEL,
                                cancel_motivo="servico_indisponivel", agora=agora)
        db.execute(text("UPDATE solicitacao SET crm_sync = 'ok', crm_tentativas = 0, crm_proxima_em = :agora "
                        "WHERE id = :id AND crm_id IS NULL"), {"agora": agora, "id": r.id})
    logger.warning("espelho: %s cancelada — produto inativo no CRM (%s)", r.id, r.tipo_servico)
    audit.registrar_sistema(categoria="negocio", tipo="solicitacao_servico_indisponivel", severidade="aviso",
                            origem="espelhar_solicitacoes", contact_id=str(r.contact_id),
                            detalhes={"solicitacao_id": str(r.id), "tipo": str(r.tipo_servico)})
    return [(res.solicitacao_id, res.contact_id, res.de, res.para)]


_SQL_TRAVAR = text(
    "SELECT status, atualizada_em, canal_envio, crm_sync, crm_tentativas FROM solicitacao WHERE id = :id FOR UPDATE"
)


def _confirmar(r: Any, criacao: CriacaoCrm, agora: datetime) -> list[tuple[str, str, str, str]]:
    """Sucesso no hub. Grava a identidade no CRM (sempre: o registro existe lá) e,
    se nada mudou desde a leitura, `crm_sync=ok` + promoção a `enviada`; mudou no
    meio → `pendente`, e o próximo ciclo trata o estado novo (retido)."""
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
            "UPDATE solicitacao SET crm_id = id, crm_entidade = :ent, crm_protocolo = :prot, crm_estado = :est, "
            " crm_status = :sts, crm_consultado_em = :agora, crm_sync = :sync, crm_tentativas = 0, "
            " crm_proxima_em = :agora WHERE id = :id"
        ), {"ent": criacao.entidade, "prot": criacao.protocolo, "est": criacao.statecode, "sts": criacao.statuscode,
            "agora": agora, "sync": "pendente" if mudou else "ok", "id": r.id})
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


def _reter(r: Any, motivo: str, agora: datetime) -> bool:
    """O CRM não pode receber este estado: fica na área (`retido`), sem tentativa,
    com aviso. Só se a linha não mudou desde a leitura."""
    with _sessao() as db:
        afetadas = db.execute(text(
            "UPDATE solicitacao SET crm_sync = 'retido', crm_tentativas = 0, crm_proxima_em = :agora "
            "WHERE id = :id AND crm_sync IN ('pendente', 'erro') AND atualizada_em = :lida"
        ), {"agora": agora, "id": r.id, "lida": r.atualizada_em}).rowcount
    if afetadas:
        tipo = "solicitacao_transicao_retida" if motivo == "sem_ferramenta_status" else "solicitacao_sem_destino_crm"
        logger.warning("espelho: %s retida na área (%s, status %s)", r.id, motivo, r.status)
        audit.registrar_sistema(categoria="negocio", tipo=tipo, severidade="aviso", origem="espelhar_solicitacoes",
                                contact_id=str(r.contact_id),
                                detalhes={"solicitacao_id": str(r.id), "status": r.status, "motivo": motivo,
                                          "protocolo": r.crm_protocolo})
    return bool(afetadas)


def _nada_a_espelhar(r: Any, agora: datetime) -> bool:
    """Cancelada antes de existir no CRM (ex.: desistência na janela de
    arrependimento): não há o que espelhar. `crm_sync=ok` com `crm_id` NULL."""
    with _sessao() as db:
        return bool(db.execute(text(
            "UPDATE solicitacao SET crm_sync = 'ok', crm_tentativas = 0, crm_proxima_em = :agora "
            "WHERE id = :id AND crm_id IS NULL AND status = 'cancelada' AND crm_sync IN ('pendente', 'erro')"
        ), {"agora": agora, "id": r.id}).rowcount)


def _acao_prevista(r: Any) -> str:
    if r.crm_id is None and r.status == "cancelada":
        return "nada"
    if r.crm_id is not None:
        return "reter"
    return "criar" if catalogo_crm.destino(r.tipo_servico, r.beneficio_id) else "reter"


def espelhar_solicitacoes(ctx: Contexto, *, hub: ClienteHub | None = None, ids: Sequence[str] | None = None) -> None:
    s = get_settings()
    itens = pendentes_do_espelho(ctx.agora, s.jobs_lote, ids)
    ctx.lidos = len(itens)
    if not itens:
        return
    if not ctx.aplicar:
        logger.info("espelho (simulação): %d solicitação(ões) na fila do CRM: %s", len(itens),
                    ", ".join(f"{r.id}:{_acao_prevista(r)}" for r in itens[:10]))
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
        if r.crm_id is not None:
            if _reter(r, "sem_ferramenta_status", ctx.agora):
                ctx.gravados += 1
            continue
        try:
            pedido = pedido_crm(r)
        except crm.ConteudoRecusado as exc:
            ctx.erros += 1
            _registrar_falha(r, PERMANENTE, f"conteudo_{exc.motivo}", ctx.agora)
            continue
        if pedido is None:
            if _reter(r, "sem_destino_no_catalogo", ctx.agora):
                ctx.gravados += 1
            continue
        try:
            criacao = _criar_no_crm(hub, pedido)
        except HubError as exc:
            if exc.codigo == "produto_inativo":
                transicoes = _cancelar_servico_indisponivel(r, ctx.agora)
                if transicoes:
                    ctx.gravados += 1
                    _registrar_uso(transicoes, "sistema")
                continue
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
        transicoes = _confirmar(r, criacao, ctx.agora)
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


def _divergencia(sid: str, contact_id: str | None, motivo: str, local: str | None,
                 reg: RegistroCrm | None) -> None:
    crm_par = f"{reg.statecode}/{reg.statuscode}" if reg else None
    logger.warning("sync: divergência em %s (%s; local=%s crm=%s)", sid, motivo, local, crm_par)
    audit.registrar_sistema(categoria="negocio", tipo="solicitacao_divergencia_crm", severidade="aviso",
                            origem="sincronizar_solicitacoes", contact_id=contact_id,
                            detalhes={"solicitacao_id": sid, "motivo": motivo, "status_local": local,
                                      "situacao_crm": crm_par})


_ABERTOS = list(rotulos.NAO_TERMINAIS)


def aplicar_registro(sid: str, reg: RegistroCrm, agora: datetime) -> tuple[bool, list[tuple[str, str, str, str]]]:
    """Aplica UM registro do CRM ao pedido `sid`. Devolve (transitou, transições).
    Sempre grava o par visto e `crm_consultado_em`; só transita se o par MUDOU."""
    transicoes: list[tuple[str, str, str, str]] = []
    pendencia: tuple[str, str | None] | None = None
    with _sessao() as db:
        r = db.execute(text(
            "SELECT id, contact_id, status, crm_entidade, crm_protocolo, crm_estado, crm_status "
            "FROM solicitacao WHERE id = :id AND crm_id IS NOT NULL FOR UPDATE"
        ), {"id": sid}).first()
        if r is None:
            return False, []
        local, cid = str(r.status), str(r.contact_id)
        mudou = (reg.statecode, reg.statuscode) != (r.crm_estado, r.crm_status)
        if mudou:
            alvo, conhecido = mapear_crm(str(r.crm_entidade), reg.statecode, reg.statuscode)
            if (alvo is None and (reg.statecode, reg.statuscode) == (0, 1) and r.crm_estado is not None
                    and (r.crm_estado, r.crm_status) != (0, 1)):
                # 0/1 só é "nada" na criação; voltando de outro estado (ex.: a Central saiu de
                # "Aguardando detalhes"), o atendimento retomou.
                alvo = "em_atendimento"
            if local in rotulos.TERMINAIS:
                if alvo is not None and alvo != local:
                    pendencia = ("terminal_local_prevalece", local)
            elif alvo is None:
                if not conhecido:
                    pendencia = ("codigo_crm_nao_mapeado", local)
            elif alvo != local:
                passos = _caminho(local, alvo)
                if not passos:
                    pendencia = ("transicao_nao_prevista", local)
                for passo in passos:
                    mensagem = (mensagem_pendente_crm(r.crm_protocolo, reg.statuscode)
                                if passo == "pendente_associado" else None)
                    res = maquina.transitar(db, solicitacao_id=sid, para=passo, ator="apm", origem="crm",
                                            agora=agora, mensagem=mensagem)
                    transicoes.append((res.solicitacao_id, res.contact_id, res.de, res.para))
        db.execute(text(
            "UPDATE solicitacao SET crm_estado = :est, crm_status = :sts, crm_consultado_em = :agora "
            "WHERE id = :id"), {"est": reg.statecode, "sts": reg.statuscode, "agora": agora, "id": sid})
    if pendencia is not None:
        _divergencia(sid, cid, pendencia[0], pendencia[1], reg)
    return bool(transicoes), transicoes


def _marcar_consultado(ids: Sequence[str], agora: datetime) -> None:
    if not ids:
        return
    with _sessao() as db:
        db.execute(text("UPDATE solicitacao SET crm_consultado_em = :agora WHERE id IN :ids")
                   .bindparams(bindparam("ids", expanding=True)), {"agora": agora, "ids": list(ids)})


def contatos_a_consultar(agora: datetime, cadencia_h: int, lote: int) -> list[str]:
    """Contatos com pedido no CRM, não terminal, cuja consulta mais antiga passou da cadência."""
    params: dict[str, Any] = {"limite": agora - timedelta(hours=cadencia_h), "lote": int(lote),
                              "abertos": _ABERTOS}
    sql = ("SELECT contact_id, MIN(COALESCE(crm_consultado_em, '1970-01-01')) AS mais_antiga FROM solicitacao "
           "WHERE crm_id IS NOT NULL AND status IN :abertos" + _filtro_contatos(params) +
           " GROUP BY contact_id HAVING mais_antiga < :limite ORDER BY mais_antiga, contact_id LIMIT :lote")
    with _sessao() as db:
        return [str(linha.contact_id) for linha in db.execute(_consulta(sql, params), params)]


def _abertos_do_contato(contact_id: str) -> list[Any]:
    with _sessao() as db:
        return list(db.execute(_consulta(
            "SELECT id, status FROM solicitacao WHERE contact_id = :c AND crm_id IS NOT NULL AND status IN :abertos",
            {"abertos": _ABERTOS}), {"c": contact_id, "abertos": _ABERTOS}))


def linhas_lidas_hoje(agora: datetime) -> int:
    """Linhas do CRM já lidas hoje (dia de São Paulo) pela sincronização: a cota do hub conta linhas."""
    local = agora.replace(tzinfo=timezone.utc).astimezone(FUSO)
    meia_noite = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    with _sessao() as db:
        total = db.execute(text(
            "SELECT COALESCE(SUM(itens_lidos), 0) FROM job_execucao WHERE job = 'sincronizar_solicitacoes' "
            "AND iniciado_em >= :desde AND modo = 'aplicar'"), {"desde": meia_noite}).scalar()
    return int(total or 0)


def sincronizar_solicitacoes(ctx: Contexto, *, hub: ClienteHub | None = None) -> None:
    s = get_settings()
    contatos = contatos_a_consultar(ctx.agora, s.jobs_sync_cadencia_h, s.jobs_lote)
    if not ctx.aplicar:
        logger.info("sync (simulação): consultaria %d contato(s) no CRM (cadência %d h)", len(contatos),
                    s.jobs_sync_cadencia_h)
        return
    if not contatos:
        return
    teto = s.jobs_sync_linhas_dia
    ja_lidas = linhas_lidas_hoje(ctx.agora)
    hub = hub or obter_hub()
    for indice, cid in enumerate(contatos):
        if ctx.parar():
            return
        if ja_lidas + ctx.lidos + s.jobs_sync_limite > teto:
            ctx.erro_sistemico = f"teto diário de linhas do CRM ({teto}) atingido"
            logger.warning("sync: teto diário de %d linhas atingido — %d contato(s) ficam para amanhã", teto,
                           len(contatos) - indice)
            return
        if indice and ctx.esperar(PAUSA_SYNC_S):
            return
        abertos = _abertos_do_contato(cid)
        if not abertos:
            continue
        try:
            registros = hub.solicitacao_listar(cid, s.jobs_sync_limite)
            ctx.lidos += len(registros)
            por_id = {reg.registro_id: reg for reg in registros}
            faltando = [a for a in abertos if str(a.id) not in por_id]
            if faltando and len(registros) >= s.jobs_sync_limite and s.jobs_sync_limite < LIMITE_AMPLIADO:
                ampliado = hub.solicitacao_listar(cid, LIMITE_AMPLIADO)
                ctx.lidos += len(ampliado)
                por_id.update({reg.registro_id: reg for reg in ampliado})
        except HubError as exc:
            if exc.codigo != "nao_encontrado":
                falha = classificar_hub(exc)
                ctx.erro_sistemico = f"hub: {falha.codigo}"
                logger.warning("sync: rodada interrompida (%s)", falha.codigo)
                return
            # O contato não existe mais no CRM (excluído ou mesclado): é uma resposta definitiva
            # sobre ELE, não uma falha do hub. Sem isto, o contato — sempre o de consulta mais
            # antiga — pararia a rodada de todos a cada ciclo. Os pedidos dele viram divergência
            # `nao_encontrada_no_crm` e são marcados como consultados.
            ctx.erros += 1
            logger.warning("sync: contato de %d pedido(s) aberto(s) não existe mais no CRM", len(abertos))
            por_id = {}
        nao_achados: list[str] = []
        for aberto in abertos:
            ctx.pulso()
            reg = por_id.get(str(aberto.id))
            if reg is None:
                nao_achados.append(str(aberto.id))
                _divergencia(str(aberto.id), cid, "nao_encontrada_no_crm", str(aberto.status), None)
                continue
            try:
                transitou, transicoes = aplicar_registro(str(aberto.id), reg, ctx.agora)
            except (maquina.TransicaoInvalida, maquina.SolicitacaoNaoEncontrada):
                ctx.erros += 1
                _divergencia(str(aberto.id), cid, "transicao_recusada", str(aberto.status), reg)
                _marcar_consultado([str(aberto.id)], ctx.agora)
                continue
            if transitou:
                ctx.gravados += 1
            _registrar_uso(transicoes, "apm")
        _marcar_consultado(nao_achados, ctx.agora)


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
