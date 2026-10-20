"""Cookie de sessão cifrado (ADR-0011): opaco, à prova de adulteração, com teto de tamanho."""

import base64
import json
import time

import pytest
from cryptography.fernet import Fernet

from app.sessao import COOKIE_MAX_BYTES, SessaoCifradaMiddleware, construir_cifrador, derivar_chave

# id_token real do IdP tem ~900–1300 caracteres; usamos o pior caso folgado.
_IDT = "eyJ" + "a" * 1500
_PIOR_CASO = {
    "sub": "f" * 64,
    "cid": "6b1f3c1e-4f3a-5d2b-9c7e-a5e0c0de57b0",
    "nome": "N" * 160,
    "email": "e" * 254,
    "cpf_mask": "***.456.789-**",
    "auth_at": int(time.time()),
    "amr": ["pwd", "otp"],
    "idt": _IDT,
    "tipo": "Correspondente no Exterior",
    "status": "Inconsistente",
    "csrf": "c" * 43,
}


def _middleware(chaves=None, max_age=60):
    return SessaoCifradaMiddleware(
        app=None, cifrador=construir_cifrador(chaves or [], "s" * 48),
        cookie_name="__Host-area", max_age=max_age, https_only=True,
    )


def test_ida_e_volta():
    m = _middleware()
    assert m._ler(m.cifrar(_PIOR_CASO)) == _PIOR_CASO


def test_conteudo_opaco_nao_decodifica_em_base64():
    m = _middleware()
    valor = m.cifrar(_PIOR_CASO)
    assert "Correspondente" not in valor and "cpf_mask" not in valor
    bruto = base64.urlsafe_b64decode(valor + "==")
    with pytest.raises((ValueError, UnicodeDecodeError)):
        json.loads(bruto)


def test_adulteracao_invalida_a_sessao():
    m = _middleware()
    valor = m.cifrar({"sub": "x"})
    adulterado = valor[:-5] + ("A" if valor[-5] != "A" else "B") + valor[-4:]
    assert m._ler(adulterado) is None
    assert m._ler("lixo") is None
    assert m._ler("x" * 9000) is None


def test_sessao_vencida_nao_e_aceita(monkeypatch):
    m = _middleware(max_age=10)
    valor = m.cifrar({"sub": "x"})
    agora = time.time()
    monkeypatch.setattr(time, "time", lambda: agora + 11)
    assert m._ler(valor) is None


def test_rotacao_chave_antiga_ainda_decifra():
    antiga, nova = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    valor_antigo = _middleware([antiga]).cifrar({"sub": "x"})
    assert _middleware([nova, antiga])._ler(valor_antigo) == {"sub": "x"}
    assert _middleware([nova])._ler(valor_antigo) is None


def test_chave_derivada_e_deterministica_e_separada_por_dominio():
    assert derivar_chave("s" * 48) == derivar_chave("s" * 48)
    assert derivar_chave("s" * 48) != derivar_chave("t" * 48)
    Fernet(derivar_chave("s" * 48).encode())  # formato válido


def test_cookie_no_pior_caso_cabe_no_limite():
    m = _middleware()
    cookie = f"__Host-area={m.cifrar(_PIOR_CASO)}; Max-Age=28800; {m._flags}"
    assert len(cookie) < COOKIE_MAX_BYTES, len(cookie)


def _rodar(m: SessaoCifradaMiddleware, caminho: str, cookie: str) -> tuple[dict, list[bytes]]:
    """Executa o middleware ASGI sobre um app que só registra a sessão recebida."""
    import asyncio

    vista: dict = {}
    enviados: list[dict] = []

    async def app(scope, receive, send):
        vista.update(scope["session"])
        scope["session"]["tocada"] = True  # mesmo alterada, não pode virar cookie em /static/
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        enviados.append(message)

    m.app = app
    scope = {"type": "http", "method": "GET", "path": caminho, "headers": [(b"cookie", f"__Host-area={cookie}".encode())]}
    asyncio.run(m(scope, receive, send))
    cabecalhos = [v for k, v in enviados[0]["headers"] if k.lower() == b"set-cookie"]
    return vista, cabecalhos


def test_static_nao_le_nem_reemite_o_cookie():
    m = _middleware()
    cookie = m.cifrar({"sub": "x", "csrf": "t"})
    vista, cabecalhos = _rodar(m, "/static/spa/assets/sora-latin-400-normal.woff2", cookie)
    assert vista == {} and cabecalhos == []
    vista, cabecalhos = _rodar(m, "/api/v1/sessao", cookie)
    assert vista == {"sub": "x", "csrf": "t"} and len(cabecalhos) == 1
