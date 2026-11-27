"""Instância única do Jinja2 (autoescape ligado) para as páginas fora da SPA."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.templating import Jinja2Templates

from .config import get_settings

BASE_DIR = Path(__file__).resolve().parent
# Tudo o que as páginas referenciam com ?v= entra no hash: essas URLs saem com
# `immutable` por um ano (main.py), então arquivo fora da lista ficaria preso no
# cache do navegador e da Cloudflare depois de trocado — foi o caso do logo.
_VERSIONED_STATIC = (
    "style.css", "fonts.css", "entrada.css",
    "logo-apm.png", "favicon-32.png", "favicon-192.png", "apple-touch-icon.png",
)

# Idade da APM nos textos institucionais: fundação em 29/11/1930, e o ano vira no
# aniversário pelo relógio de São Paulo. Calculada a cada render, não no import —
# os workers vivem dias. Mesma regra do login_associado (app/main.py).
_APM_FUNDACAO = date(1930, 11, 29)
try:
    _TZ_APM: timezone | ZoneInfo = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:  # imagem sem tzdata: Brasília não tem horário de verão
    _TZ_APM = timezone(timedelta(hours=-3))

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _apm_anos() -> int:
    hoje = datetime.now(_TZ_APM).date()
    antes_do_aniversario = (hoje.month, hoje.day) < (_APM_FUNDACAO.month, _APM_FUNDACAO.day)
    return hoje.year - _APM_FUNDACAO.year - int(antes_do_aniversario)


def _static_version() -> str:
    digest = hashlib.md5(usedforsecurity=False)
    for nome in _VERSIONED_STATIC:
        caminho = BASE_DIR / "static" / nome
        digest.update(nome.encode("utf-8"))
        if caminho.is_file():
            digest.update(caminho.read_bytes())
    return digest.hexdigest()[:8]


_s = get_settings()
templates.env.globals["static_v"] = _static_version()
templates.env.globals["apm_anos"] = _apm_anos
templates.env.globals["auth_mode"] = _s.auth_mode
templates.env.globals["app_env"] = _s.app_env
templates.env.globals["issuer"] = _s.effective_issuer
