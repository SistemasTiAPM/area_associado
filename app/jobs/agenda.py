"""Agenda in-process: "próxima execução" por job (ADR-0019 item 2).

- Periódico: primeira execução espalhada nos primeiros segundos (jitter
  inicial, para os jobs não dispararem juntos a cada boot) e, depois de cada
  execução, `fim + intervalo ± 10%` (teto de 30 s de jitter). Contar do FIM
  impede que um job lento se acumule.
- Diário: na hora local (`America/Sao_Paulo`, igual ao `TZ` do compose) com
  até 2 min de jitter; boot depois da hora = amanhã.
- Um job por vez: `vencidos()` devolve os atrasados em ordem de vencimento.

Relógio e sorteio injetáveis (testes sem `sleep`). Tempo em epoch (float).
"""

from __future__ import annotations

import logging
import random
import time as _time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from datetime import time as dtime

logger = logging.getLogger("area_associado.jobs.agenda")

JITTER_FRACAO = 0.10
JITTER_MAX_S = 30.0
JITTER_INICIAL_MAX_S = 20.0
JITTER_DIARIO_MAX_S = 120.0


def fuso_local():
    """`America/Sao_Paulo`; sem tzdata na imagem, UTC−3 fixo (sem horário de verão desde 2019)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/Sao_Paulo")
    except Exception:  # noqa: BLE001 — ZoneInfoNotFoundError/ImportError: cai no fixo
        logger.warning("agenda: tzdata ausente; usando UTC-3 fixo")
        return timezone(timedelta(hours=-3), "BRT")


@dataclass(frozen=True)
class Quando:
    """Exatamente um dos dois: `intervalo_s` (periódico) ou `horario` (diário, hora local)."""

    intervalo_s: float | None = None
    horario: dtime | None = None

    def __post_init__(self) -> None:
        if (self.intervalo_s is None) == (self.horario is None):
            raise ValueError("Quando: informe intervalo_s OU horario")
        if self.intervalo_s is not None and self.intervalo_s <= 0:
            raise ValueError("intervalo_s deve ser positivo")

    @property
    def descricao(self) -> str:
        if self.intervalo_s is not None:
            s = int(self.intervalo_s)
            return f"a cada {s // 60} min" if s % 60 == 0 else f"a cada {s} s"
        assert self.horario is not None
        return f"diário {self.horario.strftime('%H:%M')} (America/Sao_Paulo)"

    @property
    def atraso_maximo_s(self) -> float:
        """Idade máxima da última execução ok antes de o job ser considerado parado (alertas)."""
        if self.intervalo_s is not None:
            return max(3 * self.intervalo_s, 15 * 60.0)
        return 26 * 3600.0


class Agenda:
    def __init__(self, quandos: Iterable[tuple[str, Quando]], *, relogio: Callable[[], float] = _time.time,
                 sorteio: Callable[[], float] = random.random, fuso=None) -> None:
        self._quando = dict(quandos)
        if not self._quando:
            raise ValueError("agenda vazia")
        self._relogio = relogio
        self._sorteio = sorteio
        self._fuso = fuso or fuso_local()
        agora = relogio()
        self.proxima: dict[str, float] = {}
        for nome, q in self._quando.items():
            if q.intervalo_s is not None:
                self.proxima[nome] = agora + self._sorteio() * min(JITTER_INICIAL_MAX_S, q.intervalo_s)
            else:
                self.proxima[nome] = self._proximo_horario(q, agora)

    def _proximo_horario(self, q: Quando, depois_de: float) -> float:
        assert q.horario is not None
        local = datetime.fromtimestamp(depois_de, self._fuso)
        alvo = local.replace(hour=q.horario.hour, minute=q.horario.minute, second=0, microsecond=0)
        if alvo.timestamp() <= depois_de:
            alvo = (alvo + timedelta(days=1)).replace(hour=q.horario.hour, minute=q.horario.minute)
        return alvo.timestamp() + self._sorteio() * JITTER_DIARIO_MAX_S

    def reagendar(self, nome: str, fim: float | None = None) -> float:
        """Depois de uma execução (com sucesso ou não)."""
        q = self._quando[nome]
        fim = self._relogio() if fim is None else fim
        if q.intervalo_s is not None:
            amplitude = min(JITTER_FRACAO * q.intervalo_s, JITTER_MAX_S)
            self.proxima[nome] = fim + q.intervalo_s + (self._sorteio() * 2 - 1) * amplitude
        else:
            self.proxima[nome] = self._proximo_horario(q, fim)
        return self.proxima[nome]

    def vencidos(self, agora: float | None = None) -> list[str]:
        agora = self._relogio() if agora is None else agora
        return sorted((n for n, t in self.proxima.items() if t <= agora), key=lambda n: (self.proxima[n], n))

    def espera(self, agora: float | None = None, teto: float = 15.0) -> float:
        """Segundos até o próximo vencimento, com teto (o laço acorda para o heartbeat)."""
        agora = self._relogio() if agora is None else agora
        return max(0.0, min(teto, min(self.proxima.values()) - agora))
