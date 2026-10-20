"""Sessão em cookie **cifrado e autenticado** (ADR-0011).

Substitui o `SessionMiddleware` do Starlette, que só assina (itsdangerous): lá o
conteúdo — nome, e-mail, CPF mascarado e o id_token — fica legível em base64 por
quem tiver o cookie. Aqui o JSON da sessão vai dentro de um token Fernet
(AES-128-CBC + HMAC-SHA256, com carimbo de tempo), então o cookie é opaco e
qualquer alteração invalida a sessão inteira.

Comportamento preservado do Starlette:
- o cookie é reemitido em toda resposta com sessão não vazia → expiração
  deslizante de `max_age` (o carimbo do Fernet é renovado a cada emissão);
- sessão esvaziada → cookie apagado;
- `/static/` fica de fora: arquivos não leem nem mudam a sessão, e reemitir o
  cookie neles abria corrida (a resposta de uma fonte baixada em paralelo
  sobrescrevia o cookie com a sessão lida antes, perdendo o que a API acabara
  de gravar, ou recriando uma sessão recém-encerrada pelo logout);
- cookie inválido, adulterado ou vencido → sessão vazia, sem erro ao usuário.

Rotação de chave: `SESSION_ENC_KEYS` aceita várias chaves; a primeira cifra e
todas decifram (MultiFernet). Sem chave configurada (só fora de produção, o
validador de `Settings` garante), deriva-se uma de `SECRET_KEY` por HKDF.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("area_associado.sessao")

# Navegadores descartam em silêncio cookies acima de ~4096 bytes (nome +
# valor + atributos). Acima deste teto o cookie não é emitido e o erro é
# registrado — melhor que uma sessão que some sem explicação.
COOKIE_MAX_BYTES = 4000
# Cookie recebido maior que isto nem é decifrado (não é nosso, ou é abuso).
_ENTRADA_MAX_BYTES = 8192
_HKDF_INFO = b"area_associado/sessao/v1"


def derivar_chave(secret_key: str) -> str:
    """Chave Fernet determinística a partir de SECRET_KEY (separação de domínio por `info`)."""
    bruto = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        secret_key.encode("utf-8")
    )
    return base64.urlsafe_b64encode(bruto).decode("ascii")


def construir_cifrador(chaves: list[str], secret_key: str) -> MultiFernet:
    lista = chaves or [derivar_chave(secret_key)]
    return MultiFernet([Fernet(k.encode("ascii")) for k in lista])


# Arquivos estáticos: sem leitura nem reemissão do cookie (ver docstring do módulo).
_PREFIXO_SEM_SESSAO = "/static/"


class SessaoCifradaMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        cifrador: MultiFernet,
        cookie_name: str,
        max_age: int,
        https_only: bool,
        same_site: str = "lax",
    ) -> None:
        if same_site not in ("lax", "strict", "none"):
            raise ValueError("same_site inválido")
        self.app = app
        self.cifrador = cifrador
        self.cookie_name = cookie_name
        self.max_age = max_age
        flags = f"path=/; httponly; samesite={same_site}"
        if https_only:
            flags += "; secure"
        self._flags = flags

    # ------------------------------------------------------------------ #
    def _ler(self, bruto: str) -> dict[str, Any] | None:
        if len(bruto) > _ENTRADA_MAX_BYTES:
            return None
        try:
            dados = self.cifrador.decrypt(bruto.encode("ascii"), ttl=self.max_age)
            sessao = json.loads(dados)
        except (InvalidToken, UnicodeEncodeError, ValueError):
            return None
        return sessao if isinstance(sessao, dict) else None

    def cifrar(self, sessao: dict[str, Any]) -> str:
        dados = json.dumps(sessao, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return self.cifrador.encrypt(dados).decode("ascii")

    # ------------------------------------------------------------------ #
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if scope.get("path", "").startswith(_PREFIXO_SEM_SESSAO):
            scope["session"] = {}  # vazia e descartada: o cookie não é lido nem reemitido
            await self.app(scope, receive, send)
            return

        conexao = HTTPConnection(scope)
        bruto = conexao.cookies.get(self.cookie_name)
        sessao = self._ler(bruto) if bruto else None
        havia_cookie = bruto is not None
        scope["session"] = sessao or {}

        async def enviar(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if scope["session"]:
                    valor = self.cifrar(scope["session"])
                    cookie = f"{self.cookie_name}={valor}; Max-Age={self.max_age}; {self._flags}"
                    if len(cookie) > COOKIE_MAX_BYTES:
                        logger.error("sessão excede %d bytes (%d); cookie não emitido", COOKIE_MAX_BYTES, len(cookie))
                    else:
                        headers.append("Set-Cookie", cookie)
                elif havia_cookie:
                    headers.append(
                        "Set-Cookie",
                        f"{self.cookie_name}=; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; {self._flags}",
                    )
            await send(message)

        await self.app(scope, receive, enviar)
