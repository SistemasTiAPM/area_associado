"""Carteirinha digital e verificação pública (RF-CA, ADR-0014; TI-45, DEC-09).

Token público = base32(HMAC-SHA256(CARTEIRINHA_HMAC_KEY, contact_id))[:20]
(100 bits): estável por associado, não revela o `contact_id` e só é
resolvido por igualdade na coluna indexada `associado.carteirinha_token`.

A página pública mostra SÓ nome e situação ("verificado em"), sem categoria
(DEC-36). Situação, por ordem de preferência (RF-CA-08):

1. `carteirinha_revogada_em` preenchida → "sem validade" (resultado
   `inativo`), sem motivo e sem nome.
2. Leitura do hub (`associado.situacao`) com menos de `VERIFICACAO_CACHE_TTL`;
   vencida, a verificação consulta o hub de novo, com LIMITE GLOBAL por
   processo (`VERIFICACAO_HUB_POR_MINUTO`) para a rota pública nunca esgotar
   a cota da conta no hub (P-41).
3. Hub fora, sem grant, contato inexistente ou limite estourado →
   comportamento anterior: a informação mais recente entre a última leitura
   do hub e o cache de perfil, desde que tenha no máximo `PERFIL_CACHE_TTL`;
   mais velha que isso não é afirmada ("não confirmada no momento", RNF-04).

`atualizar_situacao` é a única escrita de situação/revogação e é reutilizada
pelo job noturno de situação (frente C). Sem a migração `sql/014` aplicada,
tudo funciona como antes (colunas conferidas no information_schema).

Bloqueante (SQL e hub síncrono): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import segno
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..config import get_settings
from ..integracoes.hub import ClienteHub, HubError, SituacaoCrm, obter_hub
from ..limites import LimiteJanela

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("area_associado.carteirinha")

_RE_TOKEN = re.compile(r"^[A-Z2-7]{20}$")
_RE_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Resultados gravados em `evento_uso.detalhes.resultado` de `carteirinha_verificar`.
ATIVO, INATIVO, NAO_CONFIRMADO = "ativo", "inativo", "nao_confirmado"
SITUACAO_NAO_CONFIRMADA = "não confirmada no momento"
SITUACAO_SEM_VALIDADE = "Sem validade"
# Rótulo público por situação efetiva (o rótulo do CRM muda com idioma/edição;
# o enum não). `outro` cobre pendente, registro desativado e o que o hub não mapeia.
_ROTULO_SITUACAO = {"ativo": "Ativo", "suspenso": "Suspenso", "cancelado": "Cancelado", "outro": "Não ativo"}

_COLUNAS_014 = ("carteirinha_revogada_em", "situacao_consultada_em", "situacao_normalizada")
_COLUNAS_014_TTL_AUSENTE = 60.0


def token_para(contact_id: str) -> str:
    mac = hmac.new(get_settings().effective_carteirinha_key, contact_id.encode("utf-8"), hashlib.sha256).digest()
    return base64.b32encode(mac).decode("ascii")[:20]


def url_verificacao(token: str) -> str:
    return f"{get_settings().effective_public_base_url}/verificar/{token}"


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


def _agora() -> datetime:
    """UTC ingênuo — mesma convenção das colunas DATETIME(6) do schema."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def garantir_token(contact_id: str) -> str | None:
    """Grava o token no login (idempotente). Nunca lança."""
    token = token_para(contact_id)
    try:
        with _sessao() as db:
            db.execute(text("UPDATE associado SET carteirinha_token = :t WHERE contact_id = :c "
                            "AND (carteirinha_token IS NULL OR carteirinha_token <> :t)"),
                       {"t": token, "c": contact_id})
    except SQLAlchemyError as exc:
        logger.error("carteirinha: gravação do token falhou (%s)", type(exc).__name__)
        return None
    return token


# --------------------------------------------------------------------------- #
# Migração sql/014 presente?                                                   #
# --------------------------------------------------------------------------- #
_colunas_lock = threading.Lock()
_colunas_estado: tuple[bool, float] | None = None  # (presentes, expira_em monotônico)


def colunas_revogacao_presentes() -> bool:
    """`sql/014` aplicada? Presença fica em cache para sempre (coluna não some);
    ausência ou falha de leitura, por 60 s — o operador aplica com o web no ar."""
    global _colunas_estado
    agora = time.monotonic()
    with _colunas_lock:
        if _colunas_estado is not None and (_colunas_estado[0] or _colunas_estado[1] > agora):
            return _colunas_estado[0]
    try:
        with _sessao() as db:
            total = db.execute(text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'associado' AND COLUMN_NAME IN (:a, :b, :c)"
            ), dict(zip("abc", _COLUNAS_014))).scalar()
        presentes = int(total or 0) == len(_COLUNAS_014)
    except SQLAlchemyError as exc:
        logger.error("carteirinha: conferência da sql/014 falhou (%s)", type(exc).__name__)
        presentes = False
    if not presentes:
        logger.info("carteirinha: sql/014 ausente — verificação sem consulta ao hub")
    with _colunas_lock:
        _colunas_estado = (presentes, agora + _COLUNAS_014_TTL_AUSENTE)
    return presentes


def redefinir_cache_colunas() -> None:
    """Testes."""
    global _colunas_estado
    with _colunas_lock:
        _colunas_estado = None


# --------------------------------------------------------------------------- #
# Situação no hub (TI-45) — reutilizável pelo job noturno                      #
# --------------------------------------------------------------------------- #
def situacao_efetiva(sit: SituacaoCrm) -> str:
    """Enum gravado em `associado.situacao_normalizada`: `ativo` só quando
    `SituacaoCrm.ativa` (associado ativo E registro ativo no CRM)."""
    if sit.situacao_normalizada == "ativo":
        return "ativo" if sit.ativa else "outro"
    return sit.situacao_normalizada if sit.situacao_normalizada in _ROTULO_SITUACAO else "outro"


_SQL_GRAVAR_SITUACAO = text(
    "UPDATE associado SET situacao_normalizada = :n, situacao_consultada_em = :agora, "
    "carteirinha_revogada_em = CASE "
    " WHEN :n = 'cancelado' THEN COALESCE(carteirinha_revogada_em, :agora) "
    " WHEN :n = 'ativo' THEN NULL "
    " ELSE carteirinha_revogada_em END "
    "WHERE contact_id = :c"
)


def atualizar_situacao(sess: Session | None, contact_id: str, *, hub: ClienteHub) -> SituacaoCrm | None:
    """Consulta `associado.situacao` no hub e grava o cache curto e a revogação.

    - `sess`: sessão do chamador (o job grava na própria transação e decide o
      commit; erro de SQL propaga) ou `None` (transação própria; erro de SQL é
      logado e a leitura do hub continua sendo devolvida).
    - Grava `situacao_normalizada` (enum efetivo, `situacao_efetiva`) e
      `situacao_consultada_em`; `cancelado` preenche `carteirinha_revogada_em`
      (mantém a data original), `ativo` a limpa (reativação confirmada pelo CRM);
      `suspenso`/`outro` não mexem na revogação.
    - Devolve a leitura do hub, ou `None` sem gravar nada quando o hub falha
      (`HubError`: fora do ar, sem grant, limite de taxa), o contato não existe
      no CRM ou a resposta é de outro contato (fail-closed). Nunca lança
      `HubError`; `ValueError` para `contact_id` malformado.
    - Não aplica limite de taxa: quem chama a partir de rota pública limita
      antes (`resolver`); o job dosa o próprio lote.
    """
    cid = contact_id.lower() if isinstance(contact_id, str) else ""
    if not _RE_GUID.match(cid):
        raise ValueError("contact_id inválido")
    try:
        sit = hub.situacao_consultar(cid)
    except HubError as exc:
        logger.warning("carteirinha: situação no hub indisponível (%s/%s)", exc.codigo, exc.status)
        return None
    if sit is None:
        logger.warning("carteirinha: contato inexistente no CRM ao consultar a situação")
        return None
    if sit.contact_id is not None and sit.contact_id != cid:
        logger.error("carteirinha: hub devolveu situação de outro contato — descartada (revisar contrato)")
        return None
    parametros = {"n": situacao_efetiva(sit), "agora": _agora(), "c": cid}
    if sess is not None:
        sess.execute(_SQL_GRAVAR_SITUACAO, parametros)
        return sit
    try:
        with _sessao() as db:
            db.execute(_SQL_GRAVAR_SITUACAO, parametros)
    except SQLAlchemyError as exc:
        logger.error("carteirinha: gravação da situação falhou (%s)", type(exc).__name__)
    return sit


_limite_lock = threading.Lock()
_limite_hub: LimiteJanela | None = None


def _limite_global() -> LimiteJanela:
    global _limite_hub
    with _limite_lock:
        if _limite_hub is None:
            _limite_hub = LimiteJanela(get_settings().verificacao_hub_por_minuto, 60.0)
        return _limite_hub


def redefinir_limite(limite: LimiteJanela | None = None) -> None:
    """Testes: injeta um limite (ou recria pelo Settings na próxima verificação)."""
    global _limite_hub
    with _limite_lock:
        _limite_hub = limite


def _consultar_hub_da_verificacao(contact_id: str, hub: ClienteHub | None) -> SituacaoCrm | None:
    if not _limite_global().permitir("verificar"):
        logger.warning("verificar: limite global de consultas ao hub atingido — usando o cache")
        return None
    try:
        return atualizar_situacao(None, contact_id, hub=hub or obter_hub())
    except Exception as exc:  # noqa: BLE001 — a página pública nunca quebra pela integração
        logger.error("verificar: consulta de situação falhou (%s)", type(exc).__name__)
        return None


# --------------------------------------------------------------------------- #
# Verificação pública                                                          #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Verificacao:
    nome: str
    situacao: str
    verificado_em: datetime | None
    contact_id: str
    resultado: str = NAO_CONFIRMADO  # ativo | inativo | nao_confirmado
    revogada: bool = False


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).casefold().strip()


def _resultado_do_rotulo(rotulo: str) -> str:
    return ATIVO if _sem_acento(rotulo) == "ativo" else INATIVO


def _resolver_legado(token: str) -> Verificacao | None:
    """Sem `sql/014`: só o cache de perfil (comportamento da Fase 2)."""
    with _sessao() as db:
        r = db.execute(text(
            "SELECT a.contact_id, p.nome, p.status_associativo, p.atualizado_em FROM associado a "
            "JOIN associado_perfil p ON p.contact_id = a.contact_id WHERE a.carteirinha_token = :t"
        ), {"t": token}).first()
    if r is None or not r.nome:
        return None
    return _decidir(r.nome, r.contact_id, revogada=False, situacao=None, situacao_em=None,
                    perfil_status=r.status_associativo, perfil_em=r.atualizado_em, agora=_agora())


def _decidir(nome: str, contact_id: str, *, revogada: bool, situacao: str | None, situacao_em: datetime | None,
             perfil_status: str | None, perfil_em: datetime | None, agora: datetime) -> Verificacao:
    if revogada:
        return Verificacao(nome, SITUACAO_SEM_VALIDADE, None, contact_id, INATIVO, revogada=True)
    validade = agora - timedelta(seconds=get_settings().perfil_cache_ttl)
    candidatos: list[tuple[datetime, str, str]] = []
    if situacao in _ROTULO_SITUACAO and situacao_em is not None and situacao_em >= validade:
        candidatos.append((situacao_em, _ROTULO_SITUACAO[situacao], ATIVO if situacao == "ativo" else INATIVO))
    if perfil_status and perfil_em is not None and perfil_em >= validade:
        candidatos.append((perfil_em, perfil_status, _resultado_do_rotulo(perfil_status)))
    if not candidatos:
        return Verificacao(nome, SITUACAO_NAO_CONFIRMADA, None, contact_id, NAO_CONFIRMADO)
    quando, rotulo, resultado = max(candidatos, key=lambda c: c[0])
    return Verificacao(nome, rotulo, quando, contact_id, resultado)


def resolver(token: str, *, hub: ClienteHub | None = None) -> Verificacao | None:
    """Resolve o token público. `None` = inexistente (mesma resposta que token inválido).
    Erro de SQL na leitura propaga (a rota responde 503); o hub nunca derruba a verificação."""
    if not _RE_TOKEN.match(token):
        return None
    if not colunas_revogacao_presentes():
        return _resolver_legado(token)
    with _sessao() as db:
        r = db.execute(text(
            "SELECT a.contact_id, a.carteirinha_revogada_em, a.situacao_normalizada, a.situacao_consultada_em, "
            "p.nome, p.status_associativo, p.atualizado_em FROM associado a "
            "JOIN associado_perfil p ON p.contact_id = a.contact_id WHERE a.carteirinha_token = :t"
        ), {"t": token}).first()
    if r is None or not r.nome:
        return None
    agora = _agora()
    revogada = r.carteirinha_revogada_em is not None
    situacao, situacao_em = r.situacao_normalizada, r.situacao_consultada_em
    ttl = timedelta(seconds=get_settings().verificacao_cache_ttl)
    if situacao_em is None or situacao_em < agora - ttl:
        lida = _consultar_hub_da_verificacao(r.contact_id, hub)
        if lida is not None:
            situacao, situacao_em = situacao_efetiva(lida), agora
            # Mesma regra do UPDATE de `atualizar_situacao`.
            revogada = situacao == "cancelado" or (revogada and situacao != "ativo")
    return _decidir(r.nome, r.contact_id, revogada=revogada, situacao=situacao, situacao_em=situacao_em,
                    perfil_status=r.status_associativo, perfil_em=r.atualizado_em, agora=agora)


def revogada(contact_id: str) -> bool:
    """Carteirinha do associado revogada? Sem `sql/014`, nunca. Erro de SQL propaga."""
    if not colunas_revogacao_presentes():
        return False
    with _sessao() as db:
        valor: Any = db.execute(text("SELECT carteirinha_revogada_em FROM associado WHERE contact_id = :c"),
                                {"c": contact_id}).scalar()
    return valor is not None


def qr_svg(url: str) -> bytes:
    """QR em SVG puro (sem script, sem estilo inline) — servido como imagem."""
    buffer = io.BytesIO()
    segno.make(url, error="m", micro=False).save(
        buffer, kind="svg", scale=4, border=2, dark="#13233a", light="#ffffff", xmldecl=False,
        title="QR de verificação da carteirinha APM",
    )
    return buffer.getvalue()
