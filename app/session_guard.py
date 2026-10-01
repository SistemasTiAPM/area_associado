"""Identidade na sessão e guarda das rotas autenticadas.

O cookie (assinado pelo SessionMiddleware) carrega só o necessário para
renderizar a área e encerrar a sessão no IdP: `sub`, `cid`, `nome`, `email`,
`cpf_mask`, `auth_at`, `amr`, `idt`. CPF completo, access token e refresh
token nunca entram aqui.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import Request
from starlette.responses import RedirectResponse

from .config import get_settings
from .oidc import AssociadoClaims

SESSION_SUB = "sub"
SESSION_PENDING = "oidc"
_NEXT_MAX = 512
_DEFAULT_NEXT = "/area"


class LoginRequired(Exception):
    """Capturada em main.py: vira 303 para /auth/login?next=..."""

    def __init__(self, next_path: str) -> None:
        super().__init__("login required")
        self.next_path = next_path


@dataclass(frozen=True)
class Associado:
    sub: str
    contact_id: str | None
    nome: str | None
    email: str | None
    cpf_mask: str | None
    auth_at: int
    amr: tuple[str, ...]

    @property
    def is_stub(self) -> bool:
        return "stub" in self.amr


def safe_next(raw: object) -> str:
    """Só caminho relativo deste site: começa com `/`, não com `//`, sem `\\`,
    sem esquema e com tamanho limitado. Qualquer outra coisa cai em /area."""
    if not isinstance(raw, str) or not raw or len(raw) > _NEXT_MAX:
        return _DEFAULT_NEXT
    if not raw.startswith("/") or raw.startswith("//") or "\\" in raw or ":" in raw.split("?", 1)[0]:
        return _DEFAULT_NEXT
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in raw):
        return _DEFAULT_NEXT
    if raw.startswith("/auth/"):
        return _DEFAULT_NEXT
    return raw


def store_identity(request: Request, claims: AssociadoClaims, *, amr: list[str] | None = None) -> None:
    """Substitui a sessão inteira (fixation): só o CSRF é regenerado depois."""
    request.session.clear()
    request.session.update(
        {
            SESSION_SUB: claims.sub,
            "cid": claims.contact_id,
            "nome": claims.nome,
            "email": claims.email,
            "cpf_mask": claims.cpf_mask,
            "auth_at": int(time.time()),
            "amr": list(amr if amr is not None else claims.amr),
            "idt": claims.id_token or None,
        }
    )


def current_associado(request: Request) -> Associado | None:
    s = get_settings()
    sess = request.session
    sub = sess.get(SESSION_SUB)
    auth_at = sess.get("auth_at")
    if not isinstance(sub, str) or not sub or not isinstance(auth_at, int):
        return None
    if time.time() - auth_at > s.session_absolute_max:
        sess.clear()
        return None
    amr = sess.get("amr")
    return Associado(
        sub=sub,
        contact_id=sess.get("cid") if isinstance(sess.get("cid"), str) else None,
        nome=sess.get("nome") if isinstance(sess.get("nome"), str) else None,
        email=sess.get("email") if isinstance(sess.get("email"), str) else None,
        cpf_mask=sess.get("cpf_mask") if isinstance(sess.get("cpf_mask"), str) else None,
        auth_at=auth_at,
        amr=tuple(a for a in amr if isinstance(a, str)) if isinstance(amr, list) else (),
    )


def require_associado(request: Request) -> Associado:
    """Dependência FastAPI das rotas autenticadas."""
    associado = current_associado(request)
    if associado is None:
        raise LoginRequired(safe_next(request.url.path))
    return associado


def login_redirect(next_path: str) -> RedirectResponse:
    return RedirectResponse(f"/auth/login?next={quote(safe_next(next_path), safe='/')}", status_code=303)
