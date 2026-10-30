"""Ponto de entrada do serviço de jobs (ADR-0019; runbook docs/JOBS.md).

    python -m app.jobs                    # laço in-process (o que o compose roda)
    python -m app.jobs --listar           # tabela de jobs, agenda e próxima execução
    python -m app.jobs --uma-vez NOME     # roda UM job agora (trava + job_execucao), sai
    python -m app.jobs --estado [--json]  # rastro: última ok, parado, erros em 24 h

Laço: um job por vez, na ordem de vencimento; SIGTERM/SIGINT param entre um
item e outro (a linha fica `abortado`); heartbeat em `JOBS_HEARTBEAT` a cada
volta e a cada item (HEALTHCHECK do compose lê a idade do arquivo).

Saída de `--uma-vez`: 0 ok · 1 erro/abortado · 3 pulado/ocupado · 2 uso errado.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from ..config import get_settings
from .agenda import Agenda
from .base import Batimento, Executor

logger = logging.getLogger("area_associado.jobs")


def _configurar_log() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for ruidoso in ("httpx", "httpcore"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def _quando_local(epoch: float) -> str:
    from .agenda import fuso_local

    return datetime.fromtimestamp(epoch, fuso_local()).strftime("%Y-%m-%d %H:%M:%S %Z")


def _anunciar(agenda: Agenda) -> None:
    from .registro import jobs

    s = get_settings()
    logger.info("jobs: modo=%s hub=%s escrita_hub=%s smtp=%s hub_client_id=%s central_email=%s",
                "APLICAR" if s.jobs_aplicar else "SIMULAR (dry-run)", s.hub_mode, s.hub_escrita_habilitada,
                s.smtp_mode, s.hub_client_id, "definido" if s.central_email else "ausente")
    for job in jobs():
        logger.info("jobs: %-26s %-36s próxima %s%s", job.nome, job.quando.descricao,
                    _quando_local(agenda.proxima[job.nome]), " [efeito externo]" if job.efeito_externo else "")


def _conferir_banco() -> None:
    from ..database import tls_status

    try:
        st = tls_status()
        logger.info("jobs: RDS ok — usuário=%s tls=%s %s", st.get("current_user"), st.get("Ssl_version") or "-",
                    st.get("Ssl_cipher") or "SEM CIFRA")
    except (SQLAlchemyError, FileNotFoundError) as exc:
        logger.error("jobs: banco indisponível no início (%s); o laço segue e tenta a cada rodada",
                     type(exc).__name__)


def laco(executor: Executor, agenda: Agenda, por_nome: dict, evento: threading.Event, batimento: Batimento) -> None:
    while not evento.is_set():
        batimento.bater()
        for nome in agenda.vencidos():
            if evento.is_set():
                break
            executor.executar(por_nome[nome])
            agenda.reagendar(nome)
        evento.wait(agenda.espera())


def _laco_principal() -> int:
    from .registro import por_nome

    s = get_settings()
    evento = threading.Event()

    def _sinal(numero, _quadro):  # noqa: ANN001
        logger.info("jobs: sinal %s recebido — parando entre um item e outro", signal.Signals(numero).name)
        evento.set()

    signal.signal(signal.SIGTERM, _sinal)
    signal.signal(signal.SIGINT, _sinal)
    batimento = Batimento(s.jobs_heartbeat)
    batimento.bater(forcar=True)
    registro = por_nome()
    agenda = Agenda((n, j.quando) for n, j in registro.items())
    _conferir_banco()
    _anunciar(agenda)
    laco(Executor(evento_parar=evento, batimento=batimento), agenda, registro, evento, batimento)
    logger.info("jobs: encerrado")
    return 0


def _listar() -> int:
    from .registro import jobs

    agenda = Agenda((j.nome, j.quando) for j in jobs())
    for job in jobs():
        print(f"{job.nome:26} {job.quando.descricao:36} próxima {_quando_local(agenda.proxima[job.nome])}"
              f"{'  [efeito externo]' if job.efeito_externo else ''}\n    {job.descricao}")
    return 0


def _uma_vez(nome: str) -> int:
    from .registro import por_nome

    registro = por_nome()
    if nome not in registro:
        print(f"job desconhecido: {nome!r} (use --listar)", file=sys.stderr)
        return 2
    evento = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: evento.set())
    signal.signal(signal.SIGINT, lambda *_: evento.set())
    status = Executor(evento_parar=evento, batimento=Batimento(get_settings().jobs_heartbeat)).executar(registro[nome])
    print(f"{nome}: {status}")
    return {"ok": 0, "erro": 1, "abortado": 1}.get(status, 3)


def _estado(como_json: bool) -> int:
    from .rastro import estado

    try:
        dados = estado(datetime.now(timezone.utc).replace(tzinfo=None))
    except SQLAlchemyError as exc:
        print(json.dumps({"erro": type(exc).__name__}) if como_json else f"erro: {type(exc).__name__}")
        return 1
    if como_json:
        print(json.dumps(dados, ensure_ascii=False))
        return 0
    if not dados["tabela"]:
        print("job_execucao ausente (sql/011 não aplicada)")
        return 0
    print(f"serviço ativo nas últimas 24 h: {'sim' if dados['ativo'] else 'não'}")
    if dados.get("eventos_erro_24h"):
        print("evento_log (erro, 24 h): " + ", ".join(f"{k}={v}" for k, v in sorted(dados["eventos_erro_24h"].items())))
    for j in dados["jobs"]:
        print(f"{j['job']:26} última ok {j['ultima_ok'] or '—':22} {'PARADO' if j['parado'] else 'em dia':7} "
              f"erros24h={j['erros_24h']} abortados24h={j['abortados_24h']} execuções24h={j['execucoes_24h']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.jobs", description="Serviço de jobs da Minha APM")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--listar", action="store_true", help="lista os jobs e a próxima execução")
    grupo.add_argument("--uma-vez", metavar="NOME", help="roda um job uma vez e sai")
    grupo.add_argument("--estado", action="store_true", help="rastro de job_execucao (alertas)")
    parser.add_argument("--json", action="store_true", help="com --estado: saída JSON")
    args = parser.parse_args(argv)
    _configurar_log()
    if args.listar:
        return _listar()
    if args.uma_vez:
        return _uma_vez(args.uma_vez)
    if args.estado:
        return _estado(args.json)
    return _laco_principal()


if __name__ == "__main__":
    sys.exit(main())
