"""Execução de UM job com trava, rastro e heartbeat (ADR-0019 itens 3–5).

Ordem de `Executor.executar(job)`:

1. prontidão: sem `job_execucao` (sql/011) nenhum job roda — sem rastro não há
   execução (fail-closed); tabela/coluna que o job exige ausente → pulado com
   log (`Job.pronto`, que usa `app/prontidao.py` / a conferência da sql/014);
2. trava `SELECT GET_LOCK('area_job_<nome>', 0)` numa conexão dedicada, que fica
   aberta até o fim (a trava é da sessão MySQL e cai junto com ela se o
   processo morrer) — dois containers por engano nunca rodam o mesmo job;
3. com a trava: fecha como `abortado` a linha que ficou `executando` (queda
   anterior) e abre a linha nova em `job_execucao`;
4. roda o job com um `Contexto` (modo, contagens, posição, parada, pulso);
5. fecha a linha (`ok`, `erro` ou `abortado`) e solta a trava.

Falhas de um job nunca derrubam o laço. Três falhas SEGUIDAS do mesmo job →
`evento_log` severidade `erro` (`job_falhas_seguidas`), repetido a cada 20 —
é o que o `scripts/alertas.sh` vigia.

Logs: nunca `str(exc)` de driver/HTTP/SMTP (podem ecoar SQL com parâmetros,
URL ou corpo de terceiro) — só tipo + código (`politica.resumo_erro`) e os
quadros da pilha sem a mensagem.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import socket
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .. import audit
from ..config import get_settings
from .agenda import Quando
from .politica import resumo_erro

logger = logging.getLogger("area_associado.jobs")

_RE_NOME = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
_RE_HOST = re.compile(r"[^A-Za-z0-9._-]")
FALHAS_PARA_ALERTA = 3
REPETIR_ALERTA_A_CADA = 20


def agora_utc() -> datetime:
    """UTC ingênuo, como as colunas DATETIME(6) do schema."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class Job:
    nome: str
    quando: Quando
    executar: Callable[[Contexto], None]
    # None = pronto; texto = motivo para pular esta rodada (tabela/coluna ausente).
    pronto: Callable[[], str | None] = lambda: None
    # True = escrita no CRM / e-mail: só age com JOBS_APLICAR=1 (o job decide o que simular).
    efeito_externo: bool = False
    descricao: str = ""

    def __post_init__(self) -> None:
        if not _RE_NOME.match(self.nome):
            raise ValueError(f"nome de job inválido: {self.nome!r}")


@dataclass
class Contexto:
    job: str
    aplicar: bool
    agora: datetime
    posicao_anterior: str | None = None
    evento_parar: threading.Event = field(default_factory=threading.Event)
    batimento: Batimento | None = None
    lidos: int = 0
    gravados: int = 0
    erros: int = 0
    posicao: str | None = None
    erro_sistemico: str | None = None
    interrompido: bool = False

    def parar(self) -> bool:
        """True = SIGTERM recebido: o job deve parar entre um item e outro."""
        if self.evento_parar.is_set():
            self.interrompido = True
        return self.interrompido

    def pulso(self) -> None:
        if self.batimento is not None:
            self.batimento.bater()

    def esperar(self, segundos: float) -> bool:
        """Pausa interrompível (cota do hub). True = mandaram parar."""
        self.pulso()
        if segundos > 0 and self.evento_parar.wait(segundos):
            self.interrompido = True
        return self.parar()


class Batimento:
    """Heartbeat em arquivo (HEALTHCHECK do compose lê a idade). Escrita atômica,
    no máximo a cada `intervalo_min` segundos; falha de disco só loga uma vez."""

    def __init__(self, caminho: str, intervalo_min: float = 5.0, relogio: Callable[[], float] = time.monotonic):
        self.caminho = Path(caminho)
        self._intervalo = intervalo_min
        self._relogio = relogio
        self._ultimo: float | None = None
        self._avisou = False

    def bater(self, forcar: bool = False) -> None:
        agora = self._relogio()
        if not forcar and self._ultimo is not None and agora - self._ultimo < self._intervalo:
            return
        temporario = self.caminho.with_name(self.caminho.name + ".tmp")
        try:
            temporario.write_text(f"{agora_utc().isoformat()}Z\n", encoding="ascii")
            os.replace(temporario, self.caminho)
            self._ultimo = agora
            self._avisou = False
        except OSError as exc:
            if not self._avisou:
                logger.error("heartbeat: não gravou %s (%s)", self.caminho, type(exc).__name__)
                self._avisou = True


def identidade_processo() -> tuple[str, str]:
    """(host, versao_app) para `job_execucao`. Versão = hash curto do código em
    `app/` (determinístico por build; não depende de variável de ambiente)."""
    host = _RE_HOST.sub("-", socket.gethostname() or "desconhecido")[:64] or "desconhecido"
    raiz = Path(__file__).resolve().parent.parent
    h = hashlib.sha256()
    try:
        for arquivo in sorted(raiz.rglob("*.py")):
            h.update(arquivo.relative_to(raiz).as_posix().encode())
            h.update(arquivo.read_bytes())
        versao = f"src-{h.hexdigest()[:12]}"
    except OSError:
        versao = "src-desconhecida"
    return host, versao


# --------------------------------------------------------------- rastro (SQL)
_rastro_lock = threading.Lock()
_rastro_presente: tuple[bool, float] | None = None  # (presente, expira_em monotônico)
_TTL_AUSENTE = 60.0


def rastro_presente() -> bool:
    """`job_execucao` existe? Presença fica em cache para sempre (tabela não some);
    ausência por 60 s (o operador aplica a sql/011 com o serviço no ar)."""
    global _rastro_presente
    agora = time.monotonic()
    with _rastro_lock:
        if _rastro_presente is not None and (_rastro_presente[0] or _rastro_presente[1] > agora):
            return _rastro_presente[0]
    from ..database import session_scope

    with session_scope() as db:
        presente = bool(db.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'job_execucao'")).scalar())
    with _rastro_lock:
        _rastro_presente = (presente, agora + _TTL_AUSENTE)
    return presente


def redefinir_cache_rastro() -> None:
    """Testes."""
    global _rastro_presente
    with _rastro_lock:
        _rastro_presente = None


_SQL_ORFAS = text(
    "UPDATE job_execucao SET status = 'abortado', terminado_em = GREATEST(:agora, iniciado_em), "
    " erro_resumo = 'execucao interrompida: processo parou' "
    "WHERE job = :job AND status = 'executando'"
)
_SQL_ABRIR = text(
    "INSERT INTO job_execucao (job, iniciado_em, status, modo, host, versao_app) "
    "VALUES (:job, :agora, 'executando', :modo, :host, :versao)"
)
_SQL_POSICAO = text(
    "SELECT posicao FROM job_execucao WHERE status = 'ok' AND job = :job AND modo = 'aplicar' "
    "AND posicao IS NOT NULL ORDER BY iniciado_em DESC, id DESC LIMIT 1"
)
_SQL_FECHAR = text(
    "UPDATE job_execucao SET status = :status, terminado_em = GREATEST(:agora, iniciado_em), "
    " itens_lidos = :lidos, itens_gravados = :gravados, itens_erro = :erros, erro_resumo = :resumo, "
    " posicao = :posicao "
    "WHERE id = :id AND status = 'executando'"
)
_LIMITE_CONTAGEM = 4_294_967_295
_RE_POSICAO = re.compile(r"^[A-Za-z0-9_.:+=/-]{1,200}$")


def abrir_execucao(job: str, *, aplicar: bool, host: str, versao: str, agora: datetime) -> tuple[int, str | None]:
    from ..database import session_scope

    with session_scope() as db:
        orfas = db.execute(_SQL_ORFAS, {"agora": agora, "job": job}).rowcount
        if orfas:
            logger.warning("job %s: %d execução(ões) anterior(es) fechada(s) como abortado", job, orfas)
        novo = db.execute(_SQL_ABRIR, {"job": job, "agora": agora, "modo": "aplicar" if aplicar else "simular",
                                       "host": host, "versao": versao})
        posicao = db.execute(_SQL_POSICAO, {"job": job}).scalar()
        return int(novo.lastrowid), (str(posicao) if posicao else None)


def fechar_execucao(execucao_id: int, *, status: str, ctx: Contexto, resumo: str | None, agora: datetime) -> None:
    from ..database import session_scope

    posicao = ctx.posicao if status == "ok" and ctx.aplicar else None
    if posicao is not None and not _RE_POSICAO.match(posicao):
        logger.error("job %s: posição fora do formato — não gravada", ctx.job)
        posicao = None
    with session_scope() as db:
        db.execute(_SQL_FECHAR, {
            "status": status, "agora": agora, "id": execucao_id, "resumo": resumo[:500] if resumo else None,
            "lidos": min(ctx.lidos, _LIMITE_CONTAGEM), "gravados": min(ctx.gravados, _LIMITE_CONTAGEM),
            "erros": min(ctx.erros, _LIMITE_CONTAGEM), "posicao": posicao,
        })


def _pilha(exc: BaseException) -> str:
    """Quadros da pilha SEM a mensagem da exceção (que pode trazer SQL/parâmetros)."""
    return "".join(traceback.format_tb(exc.__traceback__))[-4000:]


# ---------------------------------------------------------------- executor
class Executor:
    def __init__(self, *, evento_parar: threading.Event | None = None, batimento: Batimento | None = None,
                 relogio_utc: Callable[[], datetime] = agora_utc) -> None:
        self.evento_parar = evento_parar or threading.Event()
        self.batimento = batimento
        self._agora = relogio_utc
        self.falhas: dict[str, int] = {}
        self.host, self.versao = identidade_processo()
        self._avisos_rastro = 0.0

    def _registrar_resultado(self, job: Job, status: str, resumo: str | None) -> None:
        if status == "erro":
            n = self.falhas.get(job.nome, 0) + 1
            self.falhas[job.nome] = n
            if n == FALHAS_PARA_ALERTA or (n > FALHAS_PARA_ALERTA and n % REPETIR_ALERTA_A_CADA == 0):
                logger.error("job %s: %d falhas seguidas", job.nome, n)
                audit.registrar_sistema(categoria="erro", tipo="job_falhas_seguidas", severidade="erro",
                                        origem=job.nome,
                                        detalhes={"job": job.nome, "falhas": n, "erro": (resumo or "")[:200]})
        elif status == "ok":
            anteriores = self.falhas.pop(job.nome, 0)
            if anteriores >= FALHAS_PARA_ALERTA:
                logger.warning("job %s: recuperado depois de %d falhas", job.nome, anteriores)
                audit.registrar_sistema(categoria="erro", tipo="job_recuperado", severidade="aviso",
                                        origem=job.nome, detalhes={"job": job.nome, "falhas": anteriores})

    def executar(self, job: Job) -> str:
        """Roda `job` uma vez. Devolve `ok`, `erro`, `abortado`, `pulado` ou `ocupado`. Nunca lança."""
        status, resumo = self._executar(job)
        if status in ("ok", "erro", "abortado"):
            self._registrar_resultado(job, status, resumo)
        if self.batimento is not None:
            self.batimento.bater(forcar=True)
        return status

    def _executar(self, job: Job) -> tuple[str, str | None]:
        aplicar = bool(get_settings().jobs_aplicar)
        try:
            if not rastro_presente():
                if time.monotonic() >= self._avisos_rastro:
                    logger.warning("jobs: sql/011 (job_execucao) ausente — nenhum job executa até ser aplicada")
                    self._avisos_rastro = time.monotonic() + 3600
                return "pulado", None
            motivo = job.pronto()
        except SQLAlchemyError as exc:
            resumo = resumo_erro(exc, contexto="prontidao")
            logger.error("job %s: prontidão indisponível (%s)", job.nome, resumo)
            return "erro", resumo
        if motivo:
            logger.info("job %s: pulado — %s", job.nome, motivo)
            return "pulado", None

        from ..database import engine

        trava = f"area_job_{job.nome}"
        try:
            conexao = engine.connect()
        except SQLAlchemyError as exc:
            resumo = resumo_erro(exc, contexto="conexao")
            logger.error("job %s: banco indisponível (%s)", job.nome, resumo)
            return "erro", resumo
        try:
            try:
                obtida = conexao.execute(text("SELECT GET_LOCK(:n, 0)"), {"n": trava}).scalar()
                conexao.commit()  # a trava é da sessão; não segura snapshot durante o job
            except SQLAlchemyError as exc:
                resumo = resumo_erro(exc, contexto="trava")
                logger.error("job %s: GET_LOCK falhou (%s)", job.nome, resumo)
                return "erro", resumo
            if obtida != 1:
                logger.info("job %s: em execução em outro processo (trava %s ocupada) — pulado", job.nome, trava)
                return "ocupado", None
            try:
                return self._com_trava(job, aplicar)
            finally:
                try:
                    conexao.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": trava})
                    conexao.commit()
                except SQLAlchemyError as exc:  # conexão caiu: a trava caiu junto
                    logger.warning("job %s: RELEASE_LOCK falhou (%s)", job.nome, type(exc).__name__)
        finally:
            conexao.close()

    def _com_trava(self, job: Job, aplicar: bool) -> tuple[str, str | None]:
        inicio = self._agora()
        try:
            execucao_id, posicao = abrir_execucao(job.nome, aplicar=aplicar, host=self.host, versao=self.versao,
                                                  agora=inicio)
        except SQLAlchemyError as exc:
            resumo = resumo_erro(exc, contexto="abrir")
            logger.error("job %s: não abriu job_execucao (%s)", job.nome, resumo)
            return "erro", resumo
        ctx = Contexto(job=job.nome, aplicar=aplicar, agora=inicio, posicao_anterior=posicao,
                       evento_parar=self.evento_parar, batimento=self.batimento, posicao=posicao)
        status, resumo = "ok", None
        relogio = time.monotonic()
        try:
            job.executar(ctx)
            if ctx.erro_sistemico:
                status, resumo = "erro", ctx.erro_sistemico
            elif ctx.interrompido:
                status, resumo = "abortado", "interrompido: sinal de parada"
        except Exception as exc:  # noqa: BLE001 — falha de um job nunca derruba o laço
            status, resumo = "erro", resumo_erro(exc)
            logger.error("job %s: falhou (%s)\n%s", job.nome, resumo, _pilha(exc))
        duracao = time.monotonic() - relogio
        try:
            fechar_execucao(execucao_id, status=status, ctx=ctx, resumo=resumo, agora=self._agora())
        except SQLAlchemyError as exc:
            logger.error("job %s: não fechou job_execucao %d (%s) — a próxima execução fecha como abortado",
                         job.nome, execucao_id, resumo_erro(exc))
        nivel = logging.INFO if status == "ok" else logging.WARNING
        logger.log(nivel, "job %s: %s em %.1fs (modo=%s lidos=%d gravados=%d erros=%d)%s", job.nome, status,
                   duracao, "aplicar" if aplicar else "simular", ctx.lidos, ctx.gravados, ctx.erros,
                   f" — {resumo}" if resumo else "")
        return status, resumo
