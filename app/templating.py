"""Instância única do Jinja2 (autoescape ligado) para as páginas fora da SPA."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .config import get_settings

BASE_DIR = Path(__file__).resolve().parent
_VERSIONED_STATIC = ("style.css", "fonts.css")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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
templates.env.globals["auth_mode"] = _s.auth_mode
templates.env.globals["app_env"] = _s.app_env
templates.env.globals["issuer"] = _s.effective_issuer
