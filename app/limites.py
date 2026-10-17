"""Limite de taxa em memória, por processo (janela deslizante).

Complementa o `limit_req` do vhost, que limita por IP: aqui o limite é por
associado (`sub`), o que o nginx não enxerga. Por processo — com 2 workers o
teto efetivo é até 2× o configurado, aceitável para o propósito (conter
abuso, não contabilizar). Memória limitada: chaves antigas são podadas.
"""

from __future__ import annotations

import threading
import time
from collections import deque

_MAX_CHAVES = 10_000


class LimiteJanela:
    def __init__(self, maximo: int, janela_s: float) -> None:
        if maximo < 1 or janela_s <= 0:
            raise ValueError("limite inválido")
        self.maximo = maximo
        self.janela_s = janela_s
        self._eventos: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def permitir(self, chave: str) -> bool:
        agora = time.monotonic()
        limite = agora - self.janela_s
        with self._lock:
            fila = self._eventos.get(chave)
            if fila is None:
                if len(self._eventos) >= _MAX_CHAVES:
                    self._podar(limite)
                fila = self._eventos[chave] = deque()
            while fila and fila[0] <= limite:
                fila.popleft()
            if len(fila) >= self.maximo:
                return False
            fila.append(agora)
            return True

    def _podar(self, limite: float) -> None:
        for chave in [c for c, f in self._eventos.items() if not f or f[-1] <= limite]:
            del self._eventos[chave]
        if len(self._eventos) >= _MAX_CHAVES:  # ainda cheio: descarta os mais antigos
            for chave in sorted(self._eventos, key=lambda c: self._eventos[c][-1])[: _MAX_CHAVES // 10]:
                del self._eventos[chave]
