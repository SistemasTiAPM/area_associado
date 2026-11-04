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
                 detalhes: list[dict[str, str]] | None = None, retry_after: int | None = None) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.status = status
        self.mensagem = mensagem
        self.detalhes = detalhes
        # 429: segundos até a próxima chamada valer a pena (Retry-After do hub, 1..60).
        self.retry_after = retry_after


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


# Solicitações no CRM (docs/CONTRATO-HUB.md "Solicitações"; ADR-0023). O hub cria
# `incident` (ocorrência) ou `opportunity` (oportunidade) com o `registro_id` da área
# como chave primária, e lista por contato. Devolve `statecode`/`statuscode` crus: quem
# normaliza é a área (`app/jobs/solicitacoes.py`).
ENTIDADES_CRM = frozenset({"ocorrencia", "oportunidade"})
_RE_UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_RE_TIPO_CRM = re.compile(r"^[a-z0-9_]{2,50}$")
_RE_PROTOCOLO = re.compile(r"^[A-Z]{2,5}-[0-9]{3,10}-[A-Z0-9]{3,10}$")
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,7})?(Z|[+-]\d{2}:\d{2})$")
LISTAR_LIMITE_MAX = 50


@dataclass(frozen=True)
class PedidoCrm:
    """Entrada de `solicitacao.criar`. Texto já formatado e medido pela área
    (`app/dominio/solicitacoes/crm.py`); canal e origem o hub deriva da conta."""

    contact_id: str
    registro_id: str
    entidade: str
    tipo: str
    titulo: str
    descricao: str
    assunto_id: str | None
    time_id: str

    def argumentos(self) -> dict[str, Any]:
        if (_guid(self.contact_id) != self.contact_id or not _RE_UUID4.match(self.registro_id)
                or self.entidade not in ENTIDADES_CRM or not _RE_TIPO_CRM.match(self.tipo)
                or _guid(self.time_id) != self.time_id
                or (self.entidade == "ocorrencia") != (self.assunto_id is not None)
                or (self.assunto_id is not None and _guid(self.assunto_id) != self.assunto_id)):
            raise ValueError("pedido ao CRM fora do contrato")
        return {"contact_id": self.contact_id, "registro_id": self.registro_id, "entidade": self.entidade,
                "tipo": self.tipo, "titulo": self.titulo, "descricao": self.descricao,
                "assunto_id": self.assunto_id, "time_id": self.time_id}


@dataclass(frozen=True)
class CriacaoCrm:
    """Saída de `solicitacao.criar`. `criada=False`: o registro já existia (repetição)."""

    registro_id: str
    entidade: str
    criada: bool
    protocolo: str | None
    statecode: int
    statuscode: int


@dataclass(frozen=True)
class RegistroCrm:
    """Uma linha de `solicitacao.listar`, sem `titulo`/`descricao` (a área não guarda
    texto do CRM). `canal` NULL = aberto pela Central, não pela área."""

    registro_id: str
    entidade: str
    protocolo: str | None
    statecode: int
    statuscode: int
    canal: int | None
    criado_em: str | None
    atualizado_em: str | None


def _codigo_crm(valor: Any) -> int | None:
    numero = _inteiro(valor)
    return numero if numero is not None and 0 <= numero <= 4_294_967_295 else None


def _protocolo(valor: Any) -> str | None:
    texto = valor.strip().upper() if isinstance(valor, str) else ""
    return texto if _RE_PROTOCOLO.match(texto) else None


def _iso(valor: Any) -> str | None:
    return valor if isinstance(valor, str) and _RE_ISO.match(valor) else None


def criacao_de_linha(linha: dict[str, Any], pedido: PedidoCrm) -> CriacaoCrm | None:
    """None = resposta fora do contrato (o chamador trata como resultado incerto e
    repete: `criar` é idempotente pelo `registro_id`)."""
    rid = _guid(linha.get("registro_id"))
    estado, status, criada = _codigo_crm(linha.get("statecode")), _codigo_crm(linha.get("statuscode")), \
        linha.get("criada")
    entidade = linha.get("entidade", pedido.entidade)
    if (rid != pedido.registro_id or entidade != pedido.entidade or estado is None or status is None
            or not isinstance(criada, bool)):
        return None
    protocolo = _protocolo(linha.get("protocolo"))
    if pedido.entidade == "ocorrencia" and protocolo is None:
        return None  # toda ocorrência tem ticketnumber; sem ele, algo mudou no hub
    return CriacaoCrm(rid, pedido.entidade, criada, protocolo if pedido.entidade == "ocorrencia" else None,
                      estado, status)


def registro_de_linha(linha: dict[str, Any]) -> RegistroCrm | None:
    """None = linha fora do contrato (descartada pelo chamador, com log)."""
    rid = _guid(linha.get("registro_id"))
    entidade = linha.get("entidade")
    estado, status = _codigo_crm(linha.get("statecode")), _codigo_crm(linha.get("statuscode"))
    if rid is None or entidade not in ENTIDADES_CRM or estado is None or status is None:
        return None
    canal = linha.get("canal")
    return RegistroCrm(rid, entidade, _protocolo(linha.get("protocolo")) if entidade == "ocorrencia" else None,
                       estado, status, _codigo_crm(canal) if canal is not None else None,
                       _iso(linha.get("criado_em")), _iso(linha.get("atualizado_em")))


class ClienteHub(Protocol):
    def perfil_consultar(self, contact_id: str) -> PerfilCrm | None: ...
    def situacao_consultar(self, contact_id: str) -> SituacaoCrm | None: ...
    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]: ...
    def foto_obter(self, contact_id: str) -> bytes | None: ...
    def foto_atualizar(self, contact_id: str, jpeg: bytes | None) -> None: ...
    def solicitacao_criar(self, pedido: PedidoCrm) -> CriacaoCrm: ...
    def solicitacao_listar(self, contact_id: str, limite: int) -> list[RegistroCrm]: ...


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
        # 429 do hub (CRM limitado ou cota da conta): ninguém neste processo chama
        # de novo antes do Retry-After — nem gasta a cota nem martela o CRM.
        self._pausa_ate = 0.0

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
        with self._lock:
            restante = self._pausa_ate - time.monotonic()
        if restante > 0:
            raise HubError("limite_taxa", 429, retry_after=max(1, int(restante + 0.999)))
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
            espera = _retry_after(r.headers.get("Retry-After"))
            with self._lock:
                self._pausa_ate = max(self._pausa_ate, time.monotonic() + espera)
            raise HubError("limite_taxa", 429, retry_after=espera)
        if r.status_code == 404 and codigo == "nao_encontrado":
            alvo = _alvo_nao_encontrado(corpo)
            if alvo in ("assunto_id", "time_id"):
                # Catálogo da área aponta para assunto/time que não existe no CRM:
                # erro de configuração, não do pedido (o job para a rodada).
                logger.error("hub: %s recusou o catálogo (%s inexistente no CRM)", ferramenta, alvo)
                raise HubError("catalogo_crm_invalido", 503, detalhes=[{"campo": alvo}])
            raise HubError("nao_encontrado", 404)
        if r.status_code == 409 and codigo == "endereco_indisponivel":
            raise HubError("endereco_indisponivel", 409)
        if r.status_code == 409 and codigo == "conflito":
            raise HubError("conflito", 409)
        if r.status_code == 403 and codigo == "canal_nao_configurado":
            logger.error("hub: conta sem canal de solicitação no hub (CRM_SOLICITACAO_CONTAS)")
            raise HubError("canal_nao_configurado", 503)
        if r.status_code == 504 and codigo in ("escrita_indeterminada", "tempo_esgotado"):
            logger.error("hub: %s sem confirmação do CRM (%s) — resultado incerto", ferramenta, codigo)
            raise HubError("escrita_indeterminada", 504)
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

    # ------------------------------------------ solicitações (ADR-0023)
    def solicitacao_criar(self, pedido: PedidoCrm) -> CriacaoCrm:
        """Cria (ou devolve, pelo `registro_id`) a ocorrência/oportunidade. Resposta fora
        do contrato = resultado incerto: `escrita_indeterminada` (repetir é seguro)."""
        linhas = self.chamar("solicitacao.criar", pedido.argumentos(), escrita=True)
        criacao = criacao_de_linha(linhas[0], pedido) if len(linhas) == 1 else None
        if criacao is None:
            logger.error("hub: solicitacao.criar com resposta fora do contrato — resultado incerto (repete)")
            raise HubError("escrita_indeterminada", 504)
        return criacao

    def solicitacao_listar(self, contact_id: str, limite: int) -> list[RegistroCrm]:
        """Registros do contato, mais recentes primeiro. Linha fora do contrato é
        descartada com log (nunca aplicada)."""
        if _guid(contact_id) != contact_id:
            raise ValueError("contact_id inválido")
        limite = max(1, min(int(limite), LISTAR_LIMITE_MAX))
        linhas = self.chamar("solicitacao.listar", {"contact_id": contact_id, "limite": limite})
        registros = [registro_de_linha(linha) for linha in linhas]
        if any(r is None for r in registros):
            logger.error("hub: solicitacao.listar devolveu %d linha(s) fora do contrato (descartadas)",
                         sum(r is None for r in registros))
        return [r for r in registros if r is not None]


def _retry_after(valor: str | None) -> int:
    """Segundos do Retry-After (só a forma numérica), entre 1 e 60; ausente ou
    inválido = 60 (o teto que o hub usa para a cota da conta)."""
    try:
        return max(1, min(60, int(str(valor).strip())))
    except (TypeError, ValueError):
        return 60


def _alvo_nao_encontrado(corpo: Any) -> str | None:
    """Qual entrada o hub não achou: `detalhes[].campo` quando vier; senão a
    mensagem fixa do hub ("Contato/Assunto/Time não encontrado no CRM.")."""
    if not isinstance(corpo, dict):
        return None
    detalhes = corpo.get("detalhes")
    if isinstance(detalhes, list):
        for item in detalhes:
            campo = item.get("campo") if isinstance(item, dict) else None
            if campo in ("contact_id", "assunto_id", "time_id"):
                return campo
    mensagem = corpo.get("mensagem")
    if isinstance(mensagem, str):
        inicio = mensagem.strip().lower()
        for prefixo, campo in (("assunto", "assunto_id"), ("time", "time_id"), ("contato", "contact_id")):
            if inicio.startswith(prefixo):
                return campo
    return None


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
