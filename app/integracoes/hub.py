"""Cliente do mcp_hub (ADR-0002) — único caminho da área até o CRM/ERP.

Contrato das ferramentas: docs/CONTRATO-HUB.md. Transporte REST do hub:
`POST {base}/oauth/token` (client_credentials, `client_secret_basic`) e
`POST {base}/api/v1/ferramentas/{nome}` com `{"argumentos": {...}}`; sucesso
= `{"colunas", "linhas", ...}`, erro = `{"erro", "mensagem", "detalhes"?}`.

Regras (CLAUDE.md 4, 5, 16, 17):
- token de serviço SÓ em memória de processo (nunca sessão, banco ou log);
- timeout explícito, sem seguir redirecionamento, sem logar corpo do hub;
- 401 → renova o token uma vez; demais falhas viram `HubError` tipado;
- defesa em profundidade da ADR-0014: chave `cpf` em qualquer linha devolvida
  é descartada e registrada como anomalia.

Bloqueante (httpx síncrono): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..config import get_settings

logger = logging.getLogger("area_associado.hub")

_ESCOPOS = "ferramentas:ler ferramentas:escrever"
_RE_FERRAMENTA = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_CORPO_MAX = 2 * 1024 * 1024  # foto 512x512 em base64 cabe com folga


class HubError(Exception):
    """Falha do hub com código estável. `status` é o HTTP a devolver à SPA."""

    def __init__(self, codigo: str, status: int = 503, mensagem: str | None = None,
                 detalhes: list[dict[str, str]] | None = None) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.status = status
        self.mensagem = mensagem
        self.detalhes = detalhes


@dataclass
class Endereco:
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    uf: str | None = None
    cep: str | None = None

    def como_dict(self) -> dict[str, str | None]:
        return dict(self.__dict__)


@dataclass
class PerfilCrm:
    """Campos de `associado.perfil_consultar` (docs/CONTRATO-HUB.md). Sem CPF."""

    nome: str | None = None
    email: str | None = None
    celular: str | None = None
    telefone: str | None = None
    telefone2: str | None = None
    endereco: Endereco | None = None
    num_contato: str | None = None
    crm: str | None = None
    crm_uf: str | None = None
    tipo_associado: str | None = None
    status_associativo: str | None = None
    data_filiacao: str | None = None
    tem_foto: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


class ClienteHub(Protocol):
    def perfil_consultar(self, contact_id: str) -> PerfilCrm | None: ...
    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]: ...
    def foto_obter(self, contact_id: str) -> bytes | None: ...
    def foto_atualizar(self, contact_id: str, jpeg: bytes | None) -> None: ...


def _texto(valor: Any, limite: int) -> str | None:
    if valor is None:
        return None
    valor = " ".join(str(valor).split())
    return valor[:limite] or None


def perfil_de_linha(linha: dict[str, Any]) -> PerfilCrm:
    end = linha.get("endereco")
    endereco = None
    if isinstance(end, dict):
        endereco = Endereco(**{k: _texto(end.get(k), 120) for k in Endereco.__dataclass_fields__})
    uf = _texto(linha.get("crm_uf"), 2)
    return PerfilCrm(
        nome=_texto(linha.get("nome"), 160),
        email=_texto(linha.get("email"), 254),
        celular=_texto(linha.get("celular"), 20),
        telefone=_texto(linha.get("telefone"), 20),
        telefone2=_texto(linha.get("telefone2"), 20),
        endereco=endereco,
        num_contato=_texto(linha.get("num_contato"), 20),
        crm=_texto(linha.get("crm"), 20),
        crm_uf=uf.upper() if uf else None,
        tipo_associado=_texto(linha.get("tipo_associado"), 40),
        status_associativo=_texto(linha.get("status_associativo"), 40),
        data_filiacao=_texto(linha.get("data_filiacao"), 10),
        tem_foto=bool(linha.get("tem_foto")),
    )


class ClienteHubReal:
    def __init__(self, transporte: httpx.BaseTransport | None = None) -> None:
        self._transporte = transporte  # testes: httpx.MockTransport
        s = get_settings()
        self._base = s.effective_hub_base_url
        self._host = s.hub_public_host
        self._client_id = s.hub_client_id
        self._segredo = s.hub_client_secret or ""
        self._timeout = httpx.Timeout(s.hub_timeout, connect=min(5.0, s.hub_timeout))
        self._lock = threading.Lock()
        self._token: tuple[str, float] | None = None

    # ------------------------------------------------------------- token
    def _http(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, follow_redirects=False, headers={"Host": self._host},
                            transport=self._transporte)

    def _obter_token(self, renovar: bool = False) -> str:
        with self._lock:
            if not renovar and self._token and self._token[1] > time.monotonic():
                return self._token[0]
        basic = base64.b64encode(f"{self._client_id}:{self._segredo}".encode()).decode()
        try:
            with self._http() as cliente:
                r = cliente.post(f"{self._base}/oauth/token",
                                 data={"grant_type": "client_credentials", "scope": _ESCOPOS},
                                 headers={"Authorization": f"Basic {basic}", "Accept": "application/json"})
        except httpx.HTTPError as exc:
            logger.error("hub: token indisponível (%s)", type(exc).__name__)
            raise HubError("fonte_indisponivel") from exc
        if r.status_code != 200:
            logger.error("hub: emissão de token recusada (HTTP %s)", r.status_code)
            raise HubError("fonte_indisponivel")
        try:
            corpo = r.json()
            token = str(corpo["access_token"])
            validade = max(30, int(corpo.get("expires_in", 300)) - 30)
        except (ValueError, KeyError, TypeError) as exc:
            raise HubError("fonte_indisponivel") from exc
        with self._lock:
            self._token = (token, time.monotonic() + validade)
        return token

    # ------------------------------------------------------------ chamada
    def chamar(self, ferramenta: str, argumentos: dict[str, Any]) -> list[dict[str, Any]]:
        if not _RE_FERRAMENTA.match(ferramenta):
            raise ValueError("nome de ferramenta inválido")
        for tentativa in (1, 2):
            token = self._obter_token(renovar=tentativa == 2)
            try:
                with self._http() as cliente:
                    r = cliente.post(f"{self._base}/api/v1/ferramentas/{ferramenta}",
                                     json={"argumentos": argumentos},
                                     headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            except httpx.HTTPError as exc:
                logger.error("hub: %s falhou (%s)", ferramenta, type(exc).__name__)
                raise HubError("fonte_indisponivel") from exc
            if r.status_code == 401 and tentativa == 1:
                continue
            return self._interpretar(ferramenta, r)
        raise HubError("fonte_indisponivel")  # pragma: no cover - laço sempre retorna

    def _interpretar(self, ferramenta: str, r: httpx.Response) -> list[dict[str, Any]]:
        if len(r.content) > _CORPO_MAX:
            logger.error("hub: resposta de %s grande demais (%d bytes)", ferramenta, len(r.content))
            raise HubError("fonte_indisponivel")
        try:
            corpo = r.json()
        except ValueError:
            corpo = {}
        if r.status_code == 200 and isinstance(corpo, dict) and isinstance(corpo.get("linhas"), list):
            linhas = [linha for linha in corpo["linhas"] if isinstance(linha, dict)]
            for linha in linhas:
                if "cpf" in linha:  # ADR-0014: nunca deveria vir; descarta e avisa
                    linha.pop("cpf", None)
                    logger.error("hub: %s devolveu chave 'cpf' (descartada) — revisar contrato", ferramenta)
            return linhas
        codigo = corpo.get("erro") if isinstance(corpo, dict) else None
        logger.warning("hub: %s respondeu HTTP %s (%s)", ferramenta, r.status_code, codigo)
        if r.status_code == 400:
            detalhes = corpo.get("detalhes") if isinstance(corpo.get("detalhes"), list) else None
            raise HubError("entrada_invalida", 400, detalhes=detalhes)
        if r.status_code == 429:
            raise HubError("limite_taxa", 429)
        if r.status_code == 404 and codigo == "nao_encontrado":
            raise HubError("nao_encontrado", 404)
        # 401/403/404 de ferramenta/5xx: problema de integração, não do associado.
        raise HubError("fonte_indisponivel")

    # ------------------------------------------------------ ferramentas
    def perfil_consultar(self, contact_id: str) -> PerfilCrm | None:
        linhas = self.chamar("associado.perfil_consultar", {"contact_id": contact_id})
        return perfil_de_linha(linhas[0]) if linhas else None

    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]:
        linhas = self.chamar("associado.contato_atualizar", {"contact_id": contact_id, **campos})
        alterados = linhas[0].get("campos_alterados") if linhas else None
        return [str(c) for c in alterados] if isinstance(alterados, list) else list(campos)

    def foto_obter(self, contact_id: str) -> bytes | None:
        linhas = self.chamar("associado.foto_obter", {"contact_id": contact_id})
        dado = linhas[0].get("imagem_jpeg_b64") if linhas else None
        if not isinstance(dado, str) or not dado:
            return None
        try:
            return base64.b64decode(dado, validate=True)
        except ValueError as exc:
            raise HubError("fonte_indisponivel") from exc

    def foto_atualizar(self, contact_id: str, jpeg: bytes | None) -> None:
        b64 = base64.b64encode(jpeg).decode("ascii") if jpeg else None
        self.chamar("associado.foto_atualizar", {"contact_id": contact_id, "imagem_jpeg_b64": b64})


_instancia: ClienteHub | None = None
_instancia_lock = threading.Lock()


def obter_hub() -> ClienteHub:
    global _instancia
    with _instancia_lock:
        if _instancia is None:
            if get_settings().hub_mode == "real":
                _instancia = ClienteHubReal()
            else:
                from .hub_stub import ClienteHubStub

                _instancia = ClienteHubStub()
        return _instancia


def redefinir_hub(cliente: ClienteHub | None = None) -> None:
    """Testes: injeta um cliente (ou limpa para recriar pelo Settings)."""
    global _instancia
    with _instancia_lock:
        _instancia = cliente
