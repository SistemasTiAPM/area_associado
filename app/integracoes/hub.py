"""Cliente do mcp_hub (ADR-0002) — único caminho da área até o CRM/ERP.

Contrato das ferramentas: docs/CONTRATO-HUB.md. Transporte REST do hub:
`POST {base}/oauth/token` (client_credentials, `client_secret_basic`) e
`POST {base}/api/v1/ferramentas/{nome}` com `{"argumentos": {...}}`; sucesso
= `{"colunas", "linhas", ...}`, erro = `{"erro", "mensagem", "detalhes"?}`.

Regras (CLAUDE.md 4, 5, 16, 17):
- token de serviço SÓ em memória de processo (nunca sessão, banco ou log);
- timeout explícito, sem seguir redirecionamento, sem logar corpo do hub;
- 401 → renova o token uma vez; demais falhas viram `HubError` tipado;
- escopo do token conforme `HUB_ESCRITA_HABILITADA`: desligada, pede só
  `ferramentas:ler` (o hub responde `invalid_scope` a quem pede escopo que a
  conta não tem) e nenhuma escrita sai daqui, nem o pedido de token;
- escrita com timeout próprio (`HUB_TIMEOUT_ESCRITA`), maior que o do hub
  (25 s), para a área não desistir antes de o hub saber o resultado;
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

_ESCOPO_LER = "ferramentas:ler"
_ESCOPO_ESCREVER = "ferramentas:escrever"
_RE_FERRAMENTA = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_RE_UF = re.compile(r"^[A-Z]{2}$")
_RE_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
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


def escopos_do_token() -> str:
    s = get_settings()
    return f"{_ESCOPO_LER} {_ESCOPO_ESCREVER}" if s.hub_escrita_habilitada else _ESCOPO_LER


def exigir_escrita_habilitada() -> None:
    """Barreira antes de qualquer escrita no CRM (real ou simulado)."""
    if not get_settings().hub_escrita_habilitada:
        raise HubError("edicao_desligada", 404)


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
    # O hub só lê/grava endereço com a flag ligada E a Metadata confirmando os
    # campos (CONTRATO-HUB). Ausente na resposta = indisponível (fail-closed).
    endereco_disponivel: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


SITUACOES_NORMALIZADAS = frozenset({"ativo", "suspenso", "cancelado", "outro"})


@dataclass
class SituacaoCrm:
    """Campos de `associado.situacao` (docs/CONTRATO-HUB.md). Sem CPF, sem nome, sem contato.

    `situacao_normalizada` é o enum fechado do hub (`ativo|suspenso|cancelado|outro`); valor
    fora do enum vira `outro` aqui (fail-closed — nunca "ativo" por engano). `statecode` é o
    estado do REGISTRO no CRM (0 ativo, 1 inativo): quem decide acesso confere os dois.
    """

    contact_id: str | None = None
    status_associativo: str | None = None
    status_associativo_codigo: int | None = None
    situacao_normalizada: str = "outro"
    tipo_associado: str | None = None
    data_filiacao: str | None = None
    statecode: int | None = None
    associacao_status: str | None = None
    associacao_status_codigo: int | None = None
    associacao_data: str | None = None

    @property
    def ativa(self) -> bool:
        """Associado ativo com registro ativo no CRM — a única combinação que vale "ativo"."""
        return self.situacao_normalizada == "ativo" and self.statecode == 0


# Solicitações (Onda 5, P-06 — docs/CONTRATO-HUB.md "Solicitações"). O hub mapeia a `task`
# do CRM para estas situações; a área traduz para os status dela (REQUISITOS §7.5).
SITUACOES_TASK = frozenset({"nao_iniciada", "em_andamento", "aguardando_associado", "concluida", "nao_seguiu",
                            "cancelada"})
_RE_UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_RE_CURSOR = re.compile(r"^[A-Za-z0-9_.:+=/-]{1,200}$")
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$")


@dataclass(frozen=True)
class AlteracaoCrm:
    """Uma linha de `solicitacao.alteracoes_consultar`, já validada (ids, enum, cursor)."""

    solicitacao_id: str
    crm_id: str
    contact_id: str
    situacao: str
    mensagem_publica: str | None
    modificado_em: str
    cursor: str


def alteracao_de_linha(linha: dict[str, Any]) -> AlteracaoCrm | None:
    """None = linha fora do contrato (descartada pelo chamador com log, nunca aplicada)."""
    sid = linha.get("solicitacao_id")
    sid = sid.strip().lower() if isinstance(sid, str) else ""
    crm_id, cid = _guid(linha.get("crm_id")), _guid(linha.get("contact_id"))
    situacao, cursor, modificado = linha.get("situacao"), linha.get("cursor"), linha.get("modificado_em")
    if (not _RE_UUID4.match(sid) or crm_id is None or cid is None or situacao not in SITUACOES_TASK
            or not isinstance(cursor, str) or not _RE_CURSOR.match(cursor)
            or not isinstance(modificado, str) or not _RE_ISO.match(modificado)):
        return None
    mensagem = linha.get("mensagem_publica")
    if mensagem is not None and not isinstance(mensagem, str):
        return None
    return AlteracaoCrm(sid, crm_id, cid, situacao, mensagem, modificado, cursor)


class ClienteHub(Protocol):
    def perfil_consultar(self, contact_id: str) -> PerfilCrm | None: ...
    def situacao_consultar(self, contact_id: str) -> SituacaoCrm | None: ...
    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]: ...
    def foto_obter(self, contact_id: str) -> bytes | None: ...
    def foto_atualizar(self, contact_id: str, jpeg: bytes | None) -> None: ...
    def solicitacao_espelhar(self, dados: dict[str, Any]) -> str: ...
    def solicitacao_status_atualizar(self, dados: dict[str, Any]) -> None: ...
    def solicitacao_alteracoes_consultar(self, cursor: str | None, limite: int) -> list[dict[str, Any]]: ...


def _texto(valor: Any, limite: int) -> str | None:
    if valor is None:
        return None
    valor = " ".join(str(valor).split())
    return valor[:limite] or None


def _uf(valor: Any) -> str | None:
    """Só sigla de 2 letras; qualquer outra coisa vira None — nunca um corte ("Sã")."""
    texto = _texto(valor, 40)
    return texto.upper() if texto and _RE_UF.match(texto.upper()) else None


def _guid(valor: Any) -> str | None:
    """GUID do Dataverse em minúsculas, ou None (nunca um texto livre do hub como identificador)."""
    texto = valor.strip().lower() if isinstance(valor, str) else ""
    return texto if _RE_GUID.match(texto) else None


def _inteiro(valor: Any) -> int | None:
    """Código de option set: int (ou string numérica do gateway). bool e lixo viram None."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().lstrip("-").isdigit():
        return int(valor.strip())
    return None


def situacao_de_linha(linha: dict[str, Any]) -> SituacaoCrm:
    normalizada = linha.get("situacao_normalizada")
    if normalizada not in SITUACOES_NORMALIZADAS:
        if normalizada is not None:
            logger.warning("hub: situacao_normalizada fora do enum (tratada como 'outro') — revisar contrato")
        normalizada = "outro"
    return SituacaoCrm(
        contact_id=_guid(linha.get("contact_id")),
        status_associativo=_texto(linha.get("status_associativo"), 40),
        status_associativo_codigo=_inteiro(linha.get("status_associativo_codigo")),
        situacao_normalizada=normalizada,
        tipo_associado=_texto(linha.get("tipo_associado"), 40),
        data_filiacao=_texto(linha.get("data_filiacao"), 10),
        statecode=_inteiro(linha.get("statecode")),
        associacao_status=_texto(linha.get("associacao_status"), 40),
        associacao_status_codigo=_inteiro(linha.get("associacao_status_codigo")),
        associacao_data=_texto(linha.get("associacao_data"), 10),
    )


def perfil_de_linha(linha: dict[str, Any]) -> PerfilCrm:
    disponivel = linha.get("endereco_disponivel") is True
    end = linha.get("endereco")
    endereco = None
    if disponivel and isinstance(end, dict):
        endereco = Endereco(**{k: _texto(end.get(k), 120) for k in Endereco.__dataclass_fields__})
        endereco.uf = _uf(end.get("uf"))
    return PerfilCrm(
        nome=_texto(linha.get("nome"), 160),
        email=_texto(linha.get("email"), 254),
        celular=_texto(linha.get("celular"), 20),
        telefone=_texto(linha.get("telefone"), 20),
        telefone2=_texto(linha.get("telefone2"), 20),
        endereco=endereco,
        num_contato=_texto(linha.get("num_contato"), 20),
        crm=_texto(linha.get("crm"), 20),
        crm_uf=_uf(linha.get("crm_uf")),
        tipo_associado=_texto(linha.get("tipo_associado"), 40),
        status_associativo=_texto(linha.get("status_associativo"), 40),
        data_filiacao=_texto(linha.get("data_filiacao"), 10),
        tem_foto=bool(linha.get("tem_foto")),
        endereco_disponivel=disponivel,
    )


class ClienteHubReal:
    def __init__(self, transporte: httpx.BaseTransport | None = None) -> None:
        self._transporte = transporte  # testes: httpx.MockTransport
        s = get_settings()
        self._base = s.effective_hub_base_url
        self._host = s.hub_public_host
        self._client_id = s.hub_client_id
        self._segredo = s.hub_client_secret or ""
        self._escopos = escopos_do_token()
        self._timeout = httpx.Timeout(s.hub_timeout, connect=min(5.0, s.hub_timeout))
        self._timeout_escrita = httpx.Timeout(s.hub_timeout_escrita, connect=min(5.0, s.hub_timeout))
        self._lock = threading.Lock()
        self._token: tuple[str, float] | None = None

    # ------------------------------------------------------------- token
    def _http(self, timeout: httpx.Timeout | None = None) -> httpx.Client:
        return httpx.Client(timeout=timeout or self._timeout, follow_redirects=False, headers={"Host": self._host},
                            transport=self._transporte)

    def _obter_token(self, renovar: bool = False) -> str:
        with self._lock:
            if not renovar and self._token and self._token[1] > time.monotonic():
                return self._token[0]
        basic = base64.b64encode(f"{self._client_id}:{self._segredo}".encode()).decode()
        try:
            with self._http() as cliente:
                r = cliente.post(f"{self._base}/oauth/token",
                                 data={"grant_type": "client_credentials", "scope": self._escopos},
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
    def chamar(self, ferramenta: str, argumentos: dict[str, Any], *, escrita: bool = False) -> list[dict[str, Any]]:
        if not _RE_FERRAMENTA.match(ferramenta):
            raise ValueError("nome de ferramenta inválido")
        if escrita:
            exigir_escrita_habilitada()
        for tentativa in (1, 2):
            token = self._obter_token(renovar=tentativa == 2)
            try:
                with self._http(self._timeout_escrita if escrita else None) as cliente:
                    r = cliente.post(f"{self._base}/api/v1/ferramentas/{ferramenta}",
                                     json={"argumentos": argumentos},
                                     headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            except httpx.HTTPError as exc:
                if escrita and not isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                    # Enviada sem resposta: o hub pode ter gravado. Nada muda no cache;
                    # a próxima leitura traz o que o CRM tem.
                    logger.error("hub: %s sem resposta (%s) — resultado incerto", ferramenta, type(exc).__name__)
                else:
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
        if r.status_code == 409 and codigo == "endereco_indisponivel":
            raise HubError("endereco_indisponivel", 409)
        if r.status_code == 504 and codigo in ("escrita_indeterminada", "tempo_esgotado"):
            logger.error("hub: %s sem confirmação do CRM (%s) — resultado incerto", ferramenta, codigo)
        # 401/403/404 de ferramenta/5xx: problema de integração, não do associado.
        raise HubError("fonte_indisponivel")

    # ------------------------------------------------------ ferramentas
    def perfil_consultar(self, contact_id: str) -> PerfilCrm | None:
        linhas = self.chamar("associado.perfil_consultar", {"contact_id": contact_id})
        return perfil_de_linha(linhas[0]) if linhas else None

    def situacao_consultar(self, contact_id: str) -> SituacaoCrm | None:
        """`associado.situacao` por contact_id: 1 linha sem dado de contato; None = inexistente no CRM."""
        linhas = self.chamar("associado.situacao", {"contact_id": contact_id})
        return situacao_de_linha(linhas[0]) if linhas else None

    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]:
        linhas = self.chamar("associado.contato_atualizar", {"contact_id": contact_id, **campos}, escrita=True)
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
        self.chamar("associado.foto_atualizar", {"contact_id": contact_id, "imagem_jpeg_b64": b64}, escrita=True)

    # ------------------------------------- solicitações (Onda 5, P-06)
    # Ferramentas ainda inexistentes no hub: até a P-06, o hub responde 404
    # genérico → `HubError("fonte_indisponivel")`, e o job registra e recua.
    def solicitacao_espelhar(self, dados: dict[str, Any]) -> str:
        """Cria (ou devolve, pela `solicitacao_id`) a `task` regarding contact. Devolve o `crm_id`."""
        linhas = self.chamar("solicitacao.espelhar", dados, escrita=True)
        crm_id = _guid(linhas[0].get("crm_id")) if linhas else None
        if crm_id is None:
            logger.error("hub: solicitacao.espelhar sem crm_id válido — resultado incerto (repete, idempotente)")
            raise HubError("fonte_indisponivel")
        return crm_id

    def solicitacao_status_atualizar(self, dados: dict[str, Any]) -> None:
        self.chamar("solicitacao.status_atualizar", dados, escrita=True)

    def solicitacao_alteracoes_consultar(self, cursor: str | None, limite: int) -> list[dict[str, Any]]:
        """Linhas cruas (o job valida cada uma com `alteracao_de_linha`)."""
        return self.chamar("solicitacao.alteracoes_consultar", {"cursor": cursor, "limite": int(limite)})


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
