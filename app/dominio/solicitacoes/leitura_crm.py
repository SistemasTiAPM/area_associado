"""O que o associado vê das suas solicitações com a paridade ligada (ADR-0024, regra D-14).

Fusão, por `id == registro_id`, de:
- as linhas da área (`solicitacao`): o que ele abriu pela Minha APM, inclusive o que ainda
  não chegou ao CRM e os tipos que não vão para lá;
- as linhas do CRM (`solicitacao.listar`, conta WEB, só leitura): tudo o que ele abriu por
  autoatendimento — App APM ou Minha APM — em qualquer estado.

Quando o registro está no CRM, o par `statecode/statuscode` ao vivo decide situação e
rótulo (os do App, `situacao_crm`); sem a linha do CRM (hub fora, registro antigo fora da
página), vale o último par gravado pelo job (`crm_estado/crm_status`). O que ainda não
chegou ao CRM mantém os rótulos da spec v2.

Regras de dados:
- registro do App NÃO ganha linha na área; a `descricao` dele fica em trânsito (nunca em
  banco, log ou `evento_log`) e só aparece no detalhe;
- GET não muda a máquina local: transições, notificações e o contador do menu continuam
  com o job de sincronização. A única escrita daqui é `solicitacao_leitura.visto_em`;
- hub indisponível → a lista sai só com o que é da área e `parcial=True`; o detalhe de um
  registro que só existe no CRM vira 503 (`FonteIndisponivel`), nunca 404 enganoso;
- isolamento: toda leitura é do `contact_id` da sessão; o hub filtra pelo mesmo contato.

Cache por contato em memória de processo (`HUB_LISTA_TTL`): a cota PII do hub conta LINHAS
e a tela relê a lista a cada navegação. Falha fica em cache por 15 s.

Bloqueante (HTTP ao hub e SQL): chamar de rota async via `run_in_threadpool`. Nenhuma
chamada ao hub acontece com transação aberta.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...config import get_settings
from ...integracoes.hub import CANAL_APP, CANAL_MINHA_APM, HubError, RegistroCrm, obter_hub
from ..ajuda import contato_resumo
from . import catalogo_crm, parametros, rotulos, servico, situacao_crm
from .maquina import SolicitacaoNaoEncontrada

logger = logging.getLogger("area_associado.solicitacoes.leitura_crm")

LOCAIS_MAX = 200           # linhas da área por associado na lista fundida
TTL_FALHA_S = 15.0
_CACHE_MAX = 5_000
CANAIS_AUTOATENDIMENTO = frozenset({CANAL_APP, CANAL_MINHA_APM})
ROTULO_SEM_TIPO = "Atendimento da APM"  # registro sem tipo reconhecido (texto do App)
CODIGO_SEM_TIPO = "atendimento"


class FonteIndisponivel(Exception):
    """503: o CRM não respondeu e a resposta depende dele."""

    def __init__(self, codigo: str = "fonte_indisponivel", retry_after: int | None = None) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.retry_after = retry_after


@dataclass(frozen=True)
class Leitura:
    registros: dict[str, RegistroCrm]
    completa: bool  # False = o hub não respondeu (lista parcial)
    lida_em: datetime  # UTC ingênuo — quando o hub respondeu (ou falhou); base do bloqueio local


@dataclass(frozen=True)
class Pai:
    """O registro pai de uma conversa, como a área o enxerga agora."""

    registro_id: str
    entidade: str | None      # None = ainda não está no CRM
    slug: str | None
    responde: str
    pode_enviar: bool
    motivo: str | None        # aguardando_envio | encerrada | nao_permitida | None
    # Carimbo da última mensagem segundo a LISTA do hub; None = o registro não veio na lista
    # (hub fora, registro antigo) — a conversa não pode ser servida do cache.
    ultima_interacao_em: str | None = None
    na_lista: bool = False


_lock = threading.Lock()
_cache: dict[str, tuple[float, Leitura]] = {}


def redefinir() -> None:
    """Testes: esquece o cache."""
    with _lock:
        _cache.clear()


def invalidar(contact_id: str) -> None:
    with _lock:
        _cache.pop(contact_id, None)


def registros_do_contato(contact_id: str) -> Leitura:
    """Registros de autoatendimento do contato no CRM, com cache curto. Nunca lança."""
    agora = time.monotonic()
    with _lock:
        guardado = _cache.get(contact_id)
        if guardado is not None and guardado[0] > agora:
            return guardado[1]
    s = get_settings()
    try:
        linhas = obter_hub().solicitacao_listar(contact_id, s.hub_lista_limite)
        # Só autoatendimento (o hub já filtra; conferido de novo): canal App ou Minha APM.
        leitura = Leitura({r.registro_id: r for r in linhas if r.canal in CANAIS_AUTOATENDIMENTO}, True,
                          servico._agora())
        ttl = float(s.hub_lista_ttl)
    except (HubError, ValueError) as exc:
        logger.warning("solicitações: lista do CRM indisponível (%s); só os pedidos da área",
                       getattr(exc, "codigo", type(exc).__name__))
        leitura, ttl = Leitura({}, False, servico._agora()), TTL_FALHA_S
    with _lock:
        if len(_cache) >= _CACHE_MAX:
            for chave in [c for c, (expira, _) in _cache.items() if expira <= agora]:
                del _cache[chave]
            if len(_cache) >= _CACHE_MAX:
                _cache.clear()
        _cache[contact_id] = (agora + ttl, leitura)
    return leitura


# ----------------------------------------------------------------- apoio
_RE_FRACAO_LONGA = re.compile(r"\.(\d{6})\d+")


def _dt(iso: str | None) -> datetime | None:
    """ISO 8601 do hub → UTC ingênuo (como a área guarda). None se não for data.
    O Dataverse manda até 7 casas de fração; o excedente a 6 é cortado."""
    if not iso:
        return None
    try:
        valor = datetime.fromisoformat(_RE_FRACAO_LONGA.sub(r".\1", iso.replace("Z", "+00:00")))
    except ValueError:
        return None
    if valor.tzinfo is not None:
        valor = valor.astimezone(timezone.utc).replace(tzinfo=None)
    return valor


def _iso(valor: datetime | None) -> str | None:
    if valor is None:
        return None
    return valor.replace(tzinfo=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canal(reg: RegistroCrm | None) -> str:
    return "app" if reg is not None and reg.canal == CANAL_APP else "minha_apm"


def _nova_resposta(reg: RegistroCrm | None, visto: datetime | None) -> bool:
    if reg is None or reg.ultima_interacao_autor != "central":
        return False
    quando = _dt(reg.ultima_interacao_em)
    return quando is not None and (visto is None or quando > visto)


_EXTRAS_VAZIOS: dict[str, Any] = {
    "situacao": None, "canal": "minha_apm", "responde": None, "pode_enviar_mensagem": False,
    "nova_resposta": False,
}


def _sobrepor(item: dict[str, Any], linha: Any, reg: RegistroCrm | None, visto: datetime | None,
              bloqueado: bool = False) -> dict[str, Any]:
    """Acrescenta ao `Resumo` da área o que vem do CRM (situação e rótulo do App, conversa)."""
    slug = catalogo_crm.slug_crm(linha.tipo_servico)
    destino = catalogo_crm.destino(linha.tipo_servico, linha.beneficio_id)
    entidade = linha.crm_entidade or (destino.entidade if destino else None)
    responde = catalogo_crm.responde(slug, entidade)
    item.update(_EXTRAS_VAZIOS)
    item["responde"] = responde
    if linha.crm_id is None:
        return item
    estado, status = (reg.statecode, reg.statuscode) if reg is not None else (linha.crm_estado, linha.crm_status)
    sit = situacao_crm.situacao(entidade, estado, status)
    terminal_local = linha.status in rotulos.TERMINAIS
    if terminal_local and sit not in situacao_crm.ENCERRADAS:
        # Encerrado na área (APM/backoffice) antes do CRM: o estado local prevalece.
        item["situacao"] = "cancelada" if linha.status == "cancelada" else "concluida"
    else:
        item["situacao"] = sit
        item["rotulo_status"] = situacao_crm.rotulo(
            sit, entidade, reg.ultima_interacao_autor if reg is not None else None)
    item["pode_enviar_mensagem"] = (situacao_crm.aberta(sit) and not terminal_local and not bloqueado
                                    and catalogo_crm.aceita_mensagem(slug))
    item["nova_resposta"] = _nova_resposta(reg, visto)
    if reg is not None:
        if reg.protocolo and not item.get("protocolo"):
            item["protocolo"] = reg.protocolo
        mais_recente = max((d for d in (_dt(reg.atualizado_em), _dt(reg.ultima_interacao_em),
                                        linha.atualizada_em) if d is not None), default=None)
        item["atualizada_em"] = _iso(mais_recente) or item["atualizada_em"]
    return item


def _do_crm(reg: RegistroCrm, contato: dict[str, str] | None, visto: datetime | None,
            bloqueado: bool = False) -> dict[str, Any] | None:
    """`Resumo` de um registro que só existe no CRM (aberto pelo App)."""
    criado = _dt(reg.criado_em) or _dt(reg.atualizado_em)
    if criado is None:
        logger.warning("solicitações: registro do CRM sem data (descartado da lista)")
        return None
    atualizado = max(d for d in (criado, _dt(reg.atualizado_em), _dt(reg.ultima_interacao_em)) if d is not None)
    responde = catalogo_crm.responde(reg.tipo, reg.entidade)
    sit = situacao_crm.situacao(reg.entidade, reg.statecode, reg.statuscode)
    return {
        "id": reg.registro_id,
        "tipo": {"codigo": reg.tipo if catalogo_crm.rotulo(reg.tipo) else CODIGO_SEM_TIPO,
                 "rotulo": catalogo_crm.rotulo(reg.tipo) or ROTULO_SEM_TIPO},
        "beneficio": None,
        "status": situacao_crm.status_equivalente(sit),
        "rotulo_status": situacao_crm.rotulo(sit, reg.entidade, reg.ultima_interacao_autor),
        "aguardando_parceiro": False,
        "prazo_em": None,
        "contato": contato,
        "criada_em": _iso(criado),
        "atualizada_em": _iso(atualizado),
        "protocolo": reg.protocolo,
        "na_central": True,
        "pode_cancelar": False,
        "pode_responder": False,
        "pode_avaliar": False,
        "situacao": sit,
        "canal": _canal(reg),
        "responde": responde,
        "pode_enviar_mensagem": (situacao_crm.aberta(sit) and not bloqueado
                                 and catalogo_crm.aceita_mensagem(reg.tipo)),
        "nova_resposta": _nova_resposta(reg, visto),
    }


def _encerrada(item: dict[str, Any]) -> bool:
    if item["situacao"] is not None:
        return item["situacao"] in situacao_crm.ENCERRADAS
    return item["status"] in rotulos.TERMINAIS


_SQL_LOCAIS = "SELECT {colunas}, crm_entidade, crm_estado, crm_status FROM solicitacao WHERE contact_id = :c"


def _bloqueados(db: Any, contact_id: str, leitura: Leitura) -> set[str]:
    """Registros abertos em que o associado não pode escrever (texto "encerrada pela Central").

    Quem manda é a coluna `pode_enviar_mensagem` da lista do hub (adendo de 2026-11-13): a
    Central pode bloquear e desbloquear. O que a área aprendeu sozinha — envio que voltou 403
    `interacao_nao_permitida` — só vale enquanto o hub não disse nada mais novo: lista
    indisponível, registro fora dela, coluna ausente, ou falha posterior à leitura (a lista
    fica até `HUB_LISTA_TTL` em cache). `proxima_em` de mensagem `falhou` é a hora da falha.
    Sem a `sql/016`, só a coluna."""
    bloqueados = {rid for rid, reg in leitura.registros.items() if reg.pode_enviar_mensagem is False}
    falhas = db.execute(text(
        "SELECT registro_id, MAX(proxima_em) AS falhou_em FROM solicitacao_mensagem "
        "WHERE contact_id = :c AND status = 'falhou' AND erro_codigo = 'interacao_nao_permitida' "
        "GROUP BY registro_id"
    ), {"c": contact_id}).all()
    for falha in falhas:
        reg = leitura.registros.get(str(falha.registro_id))
        if (reg is None or reg.pode_enviar_mensagem is None or falha.falhou_em is None
                or falha.falhou_em > leitura.lida_em):
            bloqueados.add(str(falha.registro_id))
    return bloqueados


def _vistos(db: Any, contact_id: str) -> dict[str, datetime]:
    linhas = db.execute(text("SELECT registro_id, visto_em FROM solicitacao_leitura WHERE contact_id = :c"),
                        {"c": contact_id}).all()
    return {str(r.registro_id): r.visto_em for r in linhas}


# --------------------------------------------------------------- leitura
def listar(contact_id: str, *, situacao: str | None = None) -> tuple[list[dict[str, Any]], bool]:
    """(itens, parcial). Sem paginação: até `LOCAIS_MAX` da área + a página do CRM,
    por última atualização (desc). `situacao`: `andamento`, `encerradas` ou None."""
    leitura = registros_do_contato(contact_id)  # antes da transação
    contato = contato_resumo()
    agora = servico._agora()
    with servico._sessao() as db:
        locais = db.execute(text(_SQL_LOCAIS.format(colunas=servico._colunas())
                                 + " ORDER BY atualizada_em DESC, id DESC LIMIT :n"),
                            {"c": contact_id, "n": LOCAIS_MAX}).all()
        prazo_avaliacao = parametros.inteiro(db, "avaliacao_prazo_dias")
        vistos = _vistos(db, contact_id)
        bloqueados = _bloqueados(db, contact_id, leitura)
    itens: list[dict[str, Any]] = []
    ids_locais: set[str] = set()
    for linha in locais:
        sid = str(linha.id)
        ids_locais.add(sid)
        base = servico.resumo(linha, contato=contato, prazo_avaliacao_dias=prazo_avaliacao, agora=agora)
        itens.append(_sobrepor(base, linha, leitura.registros.get(sid), vistos.get(sid), sid in bloqueados))
    for rid, reg in leitura.registros.items():
        if rid not in ids_locais:
            item = _do_crm(reg, contato, vistos.get(rid), rid in bloqueados)
            if item is not None:
                itens.append(item)
    if situacao is not None:
        quer_encerradas = situacao == "encerradas"
        itens = [i for i in itens if _encerrada(i) == quer_encerradas]
    itens.sort(key=lambda i: (i["atualizada_em"], i["id"]), reverse=True)
    return itens, not leitura.completa


def _linha_local(db: Any, contact_id: str, sid: str) -> Any:
    return db.execute(text(_SQL_LOCAIS.format(colunas=servico._colunas()) + " AND id = :s"),
                      {"c": contact_id, "s": sid}).first()


def detalhe(contact_id: str, solicitacao_id: str) -> dict[str, Any]:
    sid = servico.validar_id(solicitacao_id)
    leitura = registros_do_contato(contact_id)
    contato = contato_resumo()
    reg = leitura.registros.get(sid)
    with servico._sessao() as db:
        linha = _linha_local(db, contact_id, sid)
        visto = _vistos(db, contact_id).get(sid)
        bloqueado = sid in _bloqueados(db, contact_id, leitura)
        if linha is not None:
            base = servico._detalhe(db, contact_id, sid, contato=contato, agora=servico._agora())
            return _sobrepor(base, linha, reg, visto, bloqueado)
    if reg is None:
        if not leitura.completa:
            raise FonteIndisponivel()
        raise SolicitacaoNaoEncontrada()
    item = _do_crm(reg, contato, visto, bloqueado)
    if item is None:
        raise SolicitacaoNaoEncontrada()
    item["campos"] = {"mensagem": reg.descricao} if reg.descricao else {}
    item["linha_do_tempo"] = []
    item["avaliacao"] = None
    return item


def pai(contact_id: str, solicitacao_id: str) -> Pai:
    """O pai de uma conversa. `SolicitacaoNaoEncontrada` se não for do associado;
    `FonteIndisponivel` se só o CRM saberia dizer e ele não respondeu.

    A caixa de envio só existe em situação ABERTA, com tipo do catálogo comum, em registro
    de autoatendimento e que a Central não bloqueou (regra do hub, retorno de 2026-11-13)."""
    sid = servico.validar_id(solicitacao_id)
    leitura = registros_do_contato(contact_id)
    reg = leitura.registros.get(sid)
    with servico._sessao() as db:
        linha = _linha_local(db, contact_id, sid)
        bloqueado = sid in _bloqueados(db, contact_id, leitura)
    ultima = reg.ultima_interacao_em if reg is not None else None
    na_lista = reg is not None

    def resposta(entidade: str | None, slug: str | None, responde: str, motivo: str | None) -> Pai:
        return Pai(sid, entidade, slug, responde, motivo is None, motivo, ultima, na_lista)

    if linha is not None:
        slug = catalogo_crm.slug_crm(linha.tipo_servico)
        destino = catalogo_crm.destino(linha.tipo_servico, linha.beneficio_id)
        entidade = linha.crm_entidade or (destino.entidade if destino else None)
        responde = catalogo_crm.responde(slug, entidade)
        terminal = linha.status in rotulos.TERMINAIS
        if linha.crm_id is None:
            return resposta(None, slug, responde, "encerrada" if terminal else "aguardando_envio")
        estado, status = (reg.statecode, reg.statuscode) if reg is not None else (linha.crm_estado, linha.crm_status)
        sit = situacao_crm.situacao(str(linha.crm_entidade), estado, status)
        if terminal or not situacao_crm.aberta(sit):
            return resposta(str(linha.crm_entidade), slug, responde, "encerrada")
        if bloqueado or not catalogo_crm.aceita_mensagem(slug):
            return resposta(str(linha.crm_entidade), slug, responde, "nao_permitida")
        return resposta(str(linha.crm_entidade), slug, responde, None)
    if reg is None:
        if not leitura.completa:
            raise FonteIndisponivel()
        raise SolicitacaoNaoEncontrada()
    responde = catalogo_crm.responde(reg.tipo, reg.entidade)
    if not situacao_crm.aberta(situacao_crm.situacao(reg.entidade, reg.statecode, reg.statuscode)):
        return resposta(reg.entidade, reg.tipo, responde, "encerrada")
    if bloqueado or not catalogo_crm.aceita_mensagem(reg.tipo):
        return resposta(reg.entidade, reg.tipo, responde, "nao_permitida")
    return resposta(reg.entidade, reg.tipo, responde, None)


def aberto_no_crm(contact_id: str, slug: str | None) -> bool:
    """Já existe registro ABERTO deste tipo no CRM (aberto pelo App ou pela área)? Melhor
    esforço: sem resposta do hub, não bloqueia (a unicidade local continua valendo)."""
    if slug is None:
        return False
    leitura = registros_do_contato(contact_id)
    return any(r.tipo == slug and situacao_crm.aberta(situacao_crm.situacao(r.entidade, r.statecode, r.statuscode))
               for r in leitura.registros.values())


def marcar_visto(contact_id: str, registro_id: str) -> None:
    """O associado abriu a conversa: apaga o selo "Nova resposta". Nunca lança."""
    try:
        with servico._sessao() as db:
            db.execute(text(
                "INSERT INTO solicitacao_leitura (contact_id, registro_id, visto_em) VALUES (:c, :r, :agora) "
                "ON DUPLICATE KEY UPDATE visto_em = :agora"
            ), {"c": contact_id, "r": registro_id, "agora": servico._agora()})
    except SQLAlchemyError as exc:
        logger.error("solicitações: marcação de leitura falhou (%s)", type(exc).__name__)
