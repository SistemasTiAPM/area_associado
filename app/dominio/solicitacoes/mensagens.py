"""Conversa do associado com a Central em uma solicitação (ADR-0024).

Leitura: `solicitacao.interacoes_listar` pela conta WEB (só leitura) + as mensagens do
associado que ainda estão na outbox da área (`enviando`) ou que falharam. A cota do hub
conta 1 linha por MENSAGEM devolvida: a área pede `HUB_CONVERSA_LIMITE` (20) e guarda a
conversa em memória de processo (`HUB_CONVERSA_TTL`), relendo do hub só quando o
`ultima_interacao_em` da lista muda, quando uma mensagem da área acabou de ser publicada ou
quando o associado pede "Atualizar". O cache é só memória (nunca banco nem log), limitado
em tamanho e tempo.
Escrita: o processo web NÃO escreve no CRM. `enviar` grava a mensagem na outbox
`solicitacao_mensagem` (o `id` é o `interacao_id`, idempotente) e o job
`enviar_mensagens` publica com `solicitacao.interagir`. O texto fica na área só até a
confirmação do hub; o texto das mensagens do CRM nunca é gravado nem logado.

Limites (somados aos do hub, que conta App + Minha APM: 10/h e 40/dia por associado):
- 1 mensagem a cada `INTERVALO_MIN_S` (30 s, como o App);
- `LIMITE_HORA` e `LIMITE_DIA` contados na outbox da área. As mensagens que o associado
  mandou pelo App não entram nesta conta: se o hub recusar (429 `limite_titular`), o job
  reagenda para depois do `Retry-After` e a tela mostra a mensagem como "enviando".

Bloqueante (HTTP ao hub e SQL): chamar de rota async via `run_in_threadpool`. Nenhuma
chamada ao hub acontece com transação aberta.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ...config import get_settings
from ...integracoes.hub import HubError, InteracaoCrm, obter_hub
from .. import limites_negocio
from . import leitura_crm, schemas, servico
from .leitura_crm import FonteIndisponivel
from .maquina import TransicaoInvalida

logger = logging.getLogger("area_associado.solicitacoes.mensagens")

INTERVALO_MIN_S = 30
LIMITE_HORA = 10
LIMITE_DIA = 40
_ER_DUPLICADO = 1062

MENSAGEM_ENCERRADA = "Esta solicitação foi encerrada. Abra uma nova solicitação para falar com a APM."
MENSAGEM_AGUARDANDO_ENVIO = ("Sua solicitação ainda está sendo encaminhada. Em instantes você poderá "
                             "enviar mensagens por aqui.")
MENSAGEM_NAO_PERMITIDA = "Esta solicitação não recebe mensagens por aqui."


class MensagemNaoPermitida(Exception):
    """403 `mensagem_nao_permitida`."""


class LimiteMensagens(Exception):
    """429 `limite_mensagens` com `Retry-After`."""

    def __init__(self, retry_after: int, mensagem: str) -> None:
        super().__init__("limite_mensagens")
        self.retry_after = max(1, int(retry_after))
        self.mensagem = mensagem


@dataclass(frozen=True)
class Envio:
    mensagem: dict[str, Any]
    criada: bool  # False = repetição da mesma chave de idempotência
    registro_id: str


# (contact_id, registro_id) → (ultima_interacao_em da lista, expira em, mensagens do hub)
_CACHE_MAX = 500
_cache_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[str | None, float, list[InteracaoCrm]]] = {}


def redefinir() -> None:
    """Testes: esquece as conversas em memória."""
    with _cache_lock:
        _cache.clear()


def _do_cache(chave: tuple[str, str], ultima: str | None) -> list[InteracaoCrm] | None:
    with _cache_lock:
        guardado = _cache.get(chave)
        if guardado is None or guardado[1] <= time.monotonic() or guardado[0] != ultima:
            return None
        return guardado[2]


def _guardar(chave: tuple[str, str], ultima: str | None, mensagens: list[InteracaoCrm]) -> None:
    agora = time.monotonic()
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            for antiga in [c for c, (_, expira, _m) in _cache.items() if expira <= agora]:
                del _cache[antiga]
            if len(_cache) >= _CACHE_MAX:
                _cache.clear()
        _cache[chave] = (ultima, agora + get_settings().hub_conversa_ttl, mensagens)


def _do_hub(contact_id: str, pai: leitura_crm.Pai, publicadas: set[str]) -> list[InteracaoCrm]:
    """Conversa no CRM, do cache quando nada mudou. `publicadas`: ids que o job acabou de
    confirmar — se o cache não os tem, está velho mesmo que a lista ainda não saiba."""
    chave = (contact_id, pai.registro_id)
    if pai.na_lista:
        guardadas = _do_cache(chave, pai.ultima_interacao_em)
        if guardadas is not None and publicadas <= {m.interacao_id for m in guardadas}:
            return guardadas
    try:
        mensagens = obter_hub().solicitacao_interacoes_listar(contact_id, pai.registro_id, str(pai.entidade),
                                                              get_settings().hub_conversa_limite)
    except HubError as exc:
        codigo = "mensagens_indisponiveis" if exc.codigo == "interacao_desabilitada" else "fonte_indisponivel"
        raise FonteIndisponivel(codigo, exc.retry_after) from exc
    if pai.na_lista:
        _guardar(chave, pai.ultima_interacao_em, mensagens)
    return mensagens


def _publica(mid: str, autor: str, texto: str | None, quando: str | None, estado: str) -> dict[str, Any]:
    return {"id": mid, "autor": autor, "texto": texto or "", "quando": quando, "estado": estado}


JANELA_PUBLICADAS_MIN = 15


def _locais(db: Any, contact_id: str, registro_id: str, agora: datetime) -> tuple[list[Any], set[str]]:
    """(mensagens do associado ainda na área — na fila, em nova tentativa ou falhas —,
    ids publicados pelo job nos últimos minutos)."""
    linhas = db.execute(text(
        "SELECT id, texto, status, criada_em FROM solicitacao_mensagem "
        "WHERE contact_id = :c AND registro_id = :r AND ((status <> 'enviada' AND texto IS NOT NULL) "
        " OR (status = 'enviada' AND enviada_em >= :desde)) ORDER BY criada_em, id"
    ), {"c": contact_id, "r": registro_id, "desde": agora - timedelta(minutes=JANELA_PUBLICADAS_MIN)}).all()
    return ([r for r in linhas if r.status != "enviada"], {str(r.id) for r in linhas if r.status == "enviada"})


def listar(contact_id: str, solicitacao_id: str, *, atualizar: bool = False) -> dict[str, Any]:
    """Conversa em ordem cronológica. Marca a conversa como vista. `atualizar=True` (botão
    da tela) relê a lista do contato no hub antes de decidir se a conversa mudou."""
    if atualizar:
        leitura_crm.invalidar(contact_id)
    pai = leitura_crm.pai(contact_id, solicitacao_id)
    with servico._sessao() as db:
        locais, publicadas = _locais(db, contact_id, pai.registro_id, servico._agora())
    do_crm: list[InteracaoCrm] = _do_hub(contact_id, pai, publicadas) if pai.entidade is not None else []
    no_crm = {m.interacao_id for m in do_crm}
    mensagens = [_publica(m.interacao_id, "voce" if m.autor == "associado" else "central", m.texto,
                          m.criado_em, "enviada") for m in do_crm]
    for linha in locais:
        if str(linha.id) in no_crm:
            continue  # o hub já tem; o job ainda não confirmou na outbox
        mensagens.append(_publica(str(linha.id), "voce", linha.texto, servico._iso(linha.criada_em),
                                  "falhou" if linha.status == "falhou" else "enviando"))
    leitura_crm.marcar_visto(contact_id, pai.registro_id)
    return {
        "mensagens": mensagens,
        "pode_enviar": pai.pode_enviar,
        "motivo_bloqueio": pai.motivo,
        "responde": pai.responde,
        "truncado": len(do_crm) >= get_settings().hub_conversa_limite,
    }


def _exigir_limites(db: Any, contact_id: str, agora: datetime) -> None:
    linha = db.execute(text(
        "SELECT MAX(criada_em) AS ultima, "
        " SUM(criada_em >= :hora) AS na_hora, MIN(CASE WHEN criada_em >= :hora THEN criada_em END) AS primeira_hora, "
        " COUNT(*) AS no_dia, MIN(criada_em) AS primeira_dia "
        "FROM solicitacao_mensagem WHERE contact_id = :c AND criada_em >= :dia AND status <> 'falhou'"
    ), {"c": contact_id, "hora": agora - timedelta(hours=1), "dia": agora - timedelta(hours=24)}).first()
    if linha is None or linha.ultima is None:
        return
    desde_ultima = (agora - linha.ultima).total_seconds()
    if desde_ultima < INTERVALO_MIN_S:
        raise LimiteMensagens(math.ceil(INTERVALO_MIN_S - desde_ultima),
                              "Aguarde alguns segundos antes de enviar outra mensagem.")
    if int(linha.no_dia or 0) >= LIMITE_DIA:
        espera = (linha.primeira_dia + timedelta(hours=24) - agora).total_seconds()
        raise LimiteMensagens(math.ceil(espera), "Você atingiu o limite de mensagens de hoje. Tente de novo amanhã.")
    if int(linha.na_hora or 0) >= LIMITE_HORA:
        espera = (linha.primeira_hora + timedelta(hours=1) - agora).total_seconds()
        raise LimiteMensagens(math.ceil(espera),
                              "Você atingiu o limite de mensagens por hora. Tente de novo mais tarde.")


def _existente(db: Any, mid: str) -> Any:
    return db.execute(text(
        "SELECT id, contact_id, registro_id, texto, status, criada_em FROM solicitacao_mensagem WHERE id = :id"
    ), {"id": mid}).first()


def _repeticao(existente: Any, contact_id: str, registro_id: str) -> Envio:
    if str(existente.contact_id) != contact_id or str(existente.registro_id) != registro_id:
        raise TransicaoInvalida("estado_invalido", "Esta chave já foi usada em outra mensagem. Recarregue a página.")
    estado = {"enviada": "enviada", "falhou": "falhou"}.get(str(existente.status), "enviando")
    return Envio(_publica(str(existente.id), "voce", existente.texto, servico._iso(existente.criada_em), estado),
                 False, registro_id)


def enviar(contact_id: str, solicitacao_id: str, *, texto: str, chave_idempotencia: str,
           request_id: str | None = None) -> Envio:
    """Grava a mensagem na outbox (202). Levanta `schemas.EntradaInvalida`,
    `SolicitacaoNaoEncontrada`, `FonteIndisponivel`, `TransicaoInvalida`
    (`solicitacao_encerrada`, `aguardando_envio`), `MensagemNaoPermitida` ou `LimiteMensagens`."""
    chave = chave_idempotencia.lower()
    if not servico._RE_CURSOR_ID.match(chave):  # UUID v4: vira o `interacao_id` no hub
        raise schemas.EntradaInvalida([{"campo": "chave_idempotencia", "mensagem": "deve ser um UUID v4"}])
    try:
        limpo = schemas.texto_livre(texto, minimo=schemas.MENSAGEM_CONVERSA_MIN,
                                    maximo=schemas.MENSAGEM_CONVERSA_MAX, multilinha=True, utf16=True)
    except ValueError as exc:
        raise schemas.EntradaInvalida([{"campo": "texto", "mensagem": str(exc)[:120]}]) from exc
    pai = leitura_crm.pai(contact_id, solicitacao_id)  # hub (cache) antes da transação
    agora = servico._agora()
    with servico._sessao() as db:
        limites_negocio.bloquear_associado(db, contact_id)  # serializa os envios do associado
        existente = _existente(db, chave)
        if existente is not None:
            return _repeticao(existente, contact_id, pai.registro_id)
        if not pai.pode_enviar or pai.entidade is None:
            if pai.motivo == "aguardando_envio":
                raise TransicaoInvalida("aguardando_envio", MENSAGEM_AGUARDANDO_ENVIO)
            if pai.motivo == "nao_permitida":
                raise MensagemNaoPermitida()
            raise TransicaoInvalida("solicitacao_encerrada", MENSAGEM_ENCERRADA)
        _exigir_limites(db, contact_id, agora)
        try:
            with db.begin_nested():
                db.execute(text(
                    "INSERT INTO solicitacao_mensagem (id, contact_id, registro_id, entidade, texto, status, "
                    " tentativas, proxima_em, criada_em, request_id) "
                    "VALUES (:id, :c, :r, :ent, :texto, 'pendente', 0, :agora, :agora, :rid)"
                ), {"id": chave, "c": contact_id, "r": pai.registro_id, "ent": pai.entidade, "texto": limpo,
                    "agora": agora, "rid": request_id})
        except IntegrityError as exc:
            orig = getattr(exc, "orig", None)
            if not (getattr(orig, "args", None) and orig.args[0] == _ER_DUPLICADO):
                raise
            existente = _existente(db, chave)  # corrida sem a linha de `associado`
            if existente is None:
                raise
            return _repeticao(existente, contact_id, pai.registro_id)
    return Envio(_publica(chave, "voce", limpo, servico._iso(agora), "enviando"), True, pai.registro_id)
