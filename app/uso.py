"""Eventos de uso — analytics da Minha APM (ADR-0012, REQUISITOS §8, spec v2 §11.2).

Spec: "cada resgate vira dado" → `{associadoId, acao, entidade, id, timestamp}`.
Aqui: `evento_uso(contact_id, sub_hash, acao, entidade, entidade_id, origem,
request_id, detalhes, ocorrido_em)`, append-only por privilégio.

Garantias:
- `acao` só do catálogo fechado `CATALOGO`; entidade e origem conferidas.
- `detalhes` **tipados por ação**: cada chave tem um validador (inteiro com
  teto, enumeração, slug, lista curta). Nenhum texto livre, nenhum valor
  monetário (o termo de busca, por exemplo, nunca é gravado). Para a origem
  `ui` (vem do navegador) só entram as chaves declaradas; para as demais,
  as chaves declaradas são validadas e, em ação sem esquema, vale só o
  filtro de chaves proibidas (`audit._PROIBIDAS`). A identidade vem SEMPRE
  da sessão, nunca do corpo.
- Parâmetros de campanha (`utm_*`, gatilho `A01..A20`) chegam dentro de
  `detalhes.campanha`/`detalhes.gatilho` e passam pelo mesmo catálogo fechado
  usado pela SPA (`frontend/src/lib/campanha.ts`, TI-11).
- Transação PRÓPRIA (nunca a sessão da rota: `audit.registrar` comita a sessão
  recebida e acoplaria as duas). Chamar depois do commit do negócio.
- Nunca lança. Toda falha vai para o log e para o contador `falhas()`,
  exposto em `/db-health`.

Propriedades comuns da spec (categoria, fase, especialidade, regional, tempo de
casa) NÃO entram por linha: são dimensões por junção com `associado_perfil` na
data do evento (minimização; levantamento §6.2).

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .audit import _PROIBIDAS, hash_sub

logger = logging.getLogger("area_associado.uso")

ORIGENS = ("servidor", "ui", "job", "publico")
LOTE_MAX = 20
_DETALHES_MAX = 2000
_LISTA_MAX = 16

_RE_ENTIDADE_ID = re.compile(r"^[A-Za-z0-9_/.:-]{1,64}$")
_RE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_RE_CAMPO = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_RE_ROTA = re.compile(r"^/area(/[a-z0-9-]{1,32}){0,3}$")
_RE_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_RE_COMPETENCIA = re.compile(r"^20[0-9]{2}-(0[1-9]|1[0-2])$")
_RE_DATA = re.compile(r"^20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
_RE_VERSAO = re.compile(r"^[a-z0-9][a-z0-9._-]{0,15}$")
# Catálogo fechado de campanha (TI-11): utm_* só letras/dígitos/`-_` até 32
# (minúsculas: a SPA normaliza antes); gatilho da régua A01..A20 (spec §12.2).
RE_UTM = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
RE_GATILHO = re.compile(r"^A(0[1-9]|1[0-9]|20)$")
# Mesmo padrão do CHECK de sql/004: barra CPF (com ou sem pontuação) em
# `detalhes` ANTES do banco — senão o CHECK recusaria o lote inteiro.
_RE_CPF = re.compile(r"(^|[^0-9a-fA-F])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9a-fA-F]|$)")

Validador = Callable[[Any], Any]


def _inteiro(valor: Any, maximo: int = 1_000_000, minimo: int = 0) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        return None
    return valor


def _int_ate(maximo: int, minimo: int = 0) -> Validador:
    return lambda valor: _inteiro(valor, maximo, minimo)


def _numero(maximo: float, casas: int = 3) -> Validador:
    """Métrica numérica não negativa com teto (Web Vitals); arredondada."""

    def validar(valor: Any) -> float | None:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        if valor != valor or not 0 <= valor <= maximo:  # NaN ou fora da faixa
            return None
        return round(float(valor), casas)

    return validar


def _regex(padrao: re.Pattern[str]) -> Validador:
    def validar(valor: Any) -> str | None:
        return valor if isinstance(valor, str) and padrao.match(valor) else None

    return validar


def _enum(*valores: str) -> Validador:
    permitidos = frozenset(valores)

    def validar(valor: Any) -> str | None:
        return valor if isinstance(valor, str) and valor in permitidos else None

    return validar


def _lista(item: Validador, maximo: int = _LISTA_MAX) -> Validador:
    """Lista curta de itens válidos e distintos; vazia ou inválida → None."""

    def validar(valor: Any) -> list[Any] | None:
        if not isinstance(valor, list) or len(valor) > maximo:
            return None
        limpos: list[Any] = []
        for bruto in valor:
            limpo = item(bruto)
            if limpo is None or limpo in limpos:
                return None
            limpos.append(limpo)
        return limpos or None

    return validar


def _objeto(**campos: Validador) -> Validador:
    """Sub-objeto com chaves fechadas; cada chave validada; vazio → None."""

    def validar(valor: Any) -> dict[str, Any] | None:
        if not isinstance(valor, dict):
            return None
        limpo: dict[str, Any] = {}
        for chave, validador in campos.items():
            v = validador(valor.get(chave))
            if v is not None:
                limpo[chave] = v
        return limpo or None

    return validar


_INT = _int_ate(1_000_000)
_SLUG = _regex(_RE_SLUG)
_CAMPO = _regex(_RE_CAMPO)
_ROTA = _regex(_RE_ROTA)
_HEX16 = _regex(_RE_HEX16)
_COMPETENCIA = _regex(_RE_COMPETENCIA)
_DATA = _regex(_RE_DATA)
_VERSAO = _regex(_RE_VERSAO)
_UTM = _regex(RE_UTM)
_GATILHO = _regex(RE_GATILHO)
_CAMPANHA = _objeto(origem=_UTM, meio=_UTM, campanha=_UTM, gatilho=_GATILHO)

# Enumerações da spec v2 (fechadas; valor fora delas é descartado).
ESTADOS_ELEGIBILIDADE = ("disponivel", "ativo", "libera_em", "nao_disponivel_categoria", "suspenso",
                         "indisponivel_regiao")  # §8.1, 6 estados
STATUS_SOLICITACAO = ("criada", "enviada", "em_atendimento", "pendente_associado", "concluida_positiva",
                      "concluida_negativa", "cancelada")  # §8.5 (sem_retorno é marcador, não status)
BLOCOS_HOME = ("boas_vindas", "proximo_passo", "pendencia", "recomendados", "meu_valor", "agenda", "radar",
               "destaque_editorial", "comunidade")  # §7.2, 9 blocos
_ESTADO = _enum(*ESTADOS_ELEGIBILIDADE)
_STATUS = _enum(*STATUS_SOLICITACAO)
_BLOCO = _enum(*BLOCOS_HOME)
_DISPOSITIVO = _enum("mobile", "desktop", "pwa")
_FORMA_PAGAMENTO = _enum("pdf", "linha_digitavel", "pix")


@dataclass(frozen=True)
class Acao:
    entidades: frozenset[str]
    origens: frozenset[str]
    # chave de `detalhes` → validador (devolve o valor limpo ou None).
    detalhes: dict[str, Validador] = field(default_factory=dict)


def _a(entidades: str, origens: str, **detalhes: Validador) -> Acao:
    return Acao(frozenset(entidades.split()), frozenset(origens.split()), detalhes)


# REQUISITOS §8 e levantamento §6.2 — ação nova = linha nova aqui, na tabela do
# documento e, se for de `ui`, em `AcaoUi` (frontend/src/lib/analytics.ts);
# o teste tests/test_espelho_front.py falha se os dois divergirem.
CATALOGO: dict[str, Acao] = {
    # --- acesso e navegação
    "acesso_primeiro": _a("associado", "servidor", dias_desde_filiacao=_int_ate(40_000)),
    "pagina_ver": _a("rota", "ui", blocos=_lista(_BLOCO, len(BLOCOS_HOME)), segmento=_SLUG, disp=_DISPOSITIVO,
                     gatilho=_GATILHO, campanha=_CAMPANHA),
    "home_bloco_clicar": _a("home_bloco", "ui", bloco=_BLOCO, posicao=_int_ate(64), item=_SLUG),
    "busca_global": _a("rota", "ui", resultados=_INT, tamanho=_INT),
    "filtro_aplicar": _a("beneficio noticia", "ui", filtro=_SLUG),
    "categoria_abrir": _a("beneficio_categoria", "ui"),
    # --- benefícios
    "beneficio_ativar": _a("beneficio", "servidor"),
    "beneficio_desativar": _a("beneficio", "servidor"),
    "beneficio_gerenciar": _a("beneficio", "ui"),
    "beneficio_abrir": _a("beneficio", "ui", origem=_enum("home", "catalogo", "busca", "email", "trilha"),
                          estado=_ESTADO),
    "recomendacao_dispensar": _a("beneficio", "servidor", motivo=_enum("nao_interessa", "ja_tenho", "depois", "outro")),
    "carencia_vencer": _a("beneficio", "job", liberado_em=_DATA),
    "totalpass_abrir": _a("beneficio", "ui"),
    "plantoes_abrir": _a("beneficio", "ui"),
    "clube_oferta_usar": _a("oferta", "ui"),
    # --- uso e valor (sem valores em reais: ficam em `uso_valor`)
    "uso_registrar": _a("uso_valor", "servidor job",
                        fonte=_enum("solicitacao", "importacao", "api", "clube", "evento", "manual"),
                        nivel=_int_ate(4, 1)),
    # --- conteúdo e eventos
    "noticia_abrir": _a("noticia", "ui", tema=_SLUG),
    "noticia_salvar": _a("noticia", "servidor"),
    "noticia_dessalvar": _a("noticia", "servidor"),
    "tema_seguir": _a("tema", "servidor"),
    "tema_deixar": _a("tema", "servidor"),
    "evento_inscrever": _a("evento", "servidor"),
    "congresso_garantir_vaga": _a("evento", "servidor"),
    "congresso_programacao_abrir": _a("evento", "ui"),
    "comunidade_entrar": _a("comunidade", "servidor"),
    "comunidade_abrir": _a("comunidade", "ui"),
    "programa_saber_mais": _a("comunidade", "ui"),
    "rede_entrar": _a("comunidade", "servidor"),
    # --- solicitações (§8.5)
    "solicitacao_criar": _a("solicitacao", "servidor"),
    "solicitacao_cancelar": _a("solicitacao", "servidor"),
    "solicitacao_responder": _a("solicitacao", "servidor"),
    # Mensagem do associado na conversa com a Central (ADR-0024); sem o texto.
    "solicitacao_mensagem_enviar": _a("solicitacao", "servidor"),
    "solicitacao_status_alterado": _a("solicitacao", "servidor job", de=_STATUS, para=_STATUS,
                                      origem=_enum("sistema", "parceiro", "importacao", "associado", "apm")),
    "solicitacao_avaliar": _a("solicitacao", "servidor", nota=_int_ate(10)),
    # `insatisfacao_servico` é o código do contrato da Onda 2 (POST /ajuda/cancelamento);
    # `insatisfacao` fica aceito para não descartar emissor antigo.
    "cancelamento_pedir": _a("associado", "servidor", motivo=_enum("nao_uso", "preco", "mudanca",
                                                                   "insatisfacao_servico", "insatisfacao", "outro")),
    # --- trilha, perfil, privacidade
    "onboarding_passo_concluir": _a("onboarding_passo", "servidor"),
    "perfil_contato_atualizar": _a("associado_perfil", "servidor"),
    "perfil_foto_atualizar": _a("associado_perfil", "servidor"),
    "perfil_declarado_atualizar": _a("perfil_declarado", "servidor", campos=_lista(_CAMPO)),
    "consentimento_alterar": _a("consentimento", "servidor", finalidade=_SLUG,
                                canal=_enum("email", "whatsapp", "sms", "push", "telefone"),
                                valor=_enum("concedido", "retirado"), versao=_VERSAO),
    # Direitos do titular (LGPD, ADR-0025): só o fato; o conteúdo nunca.
    "dados_exportar": _a("associado", "servidor"),
    "exclusao_pedir": _a("associado", "servidor"),
    # --- carteirinha
    "carteirinha_compartilhar": _a("carteirinha", "servidor"),
    "carteirinha_baixar": _a("carteirinha", "servidor", formato=_enum("png", "pdf")),
    "carteirinha_verificar": _a("carteirinha", "publico", resultado=_enum("ativo", "inativo", "nao_confirmado")),
    "wallet_adicionar": _a("carteirinha", "ui"),
    # --- financeiro (sem valores; competência AAAA-MM)
    "fatura_segunda_via": _a("fatura", "servidor", competencia=_COMPETENCIA, forma=_FORMA_PAGAMENTO),
    "pagamento_confirmar": _a("fatura", "job", competencia=_COMPETENCIA, forma=_FORMA_PAGAMENTO),
    # --- notificações e ajuda
    "notificacao_criar": _a("notificacao", "job", tipo=_SLUG),
    "notificacao_abrir": _a("notificacao", "ui", tipo=_SLUG),
    "central_whatsapp_abrir": _a("central", "ui"),
    "ajuda_contatar": _a("central", "ui", canal=_enum("whatsapp", "telefone", "formulario"),
                         # + `beneficio` e `eventos`: assuntos do formulário da Ajuda (contrato da Onda 2).
                         assunto=_enum("beneficios", "beneficio", "solicitacao", "financeiro", "cadastro",
                                       "carteirinha", "cancelamento", "eventos", "outro")),
    # --- qualidade (RUM próprio, TI-67): métricas numéricas; nunca stack nem mensagem
    "erro_exibido": _a("rota", "ui", codigo=_SLUG, request_id=_HEX16, rota=_ROTA),
    "vitais_web": _a("rota", "ui", lcp=_numero(60_000, 1), inp=_numero(60_000, 1), cls=_numero(10, 3), rota=_ROTA),
    "erro_js": _a("rota", "ui", tipo=_SLUG, rota=_ROTA),
}

ACOES_UI: frozenset[str] = frozenset(nome for nome, a in CATALOGO.items() if "ui" in a.origens)


@dataclass(frozen=True)
class Evento:
    acao: str
    entidade: str
    entidade_id: str | None = None
    detalhes: dict[str, Any] | None = None


_falhas = 0
_falhas_lock = threading.Lock()


def falhas() -> int:
    with _falhas_lock:
        return _falhas


def _contar_falha() -> None:
    global _falhas
    with _falhas_lock:
        _falhas += 1


def _detalhes_tipados(acao: Acao, brutos: dict[str, Any], *, nome: str, origem: str) -> dict[str, Any]:
    limpos: dict[str, Any] = {}
    for chave, validador in acao.detalhes.items():
        if chave not in brutos:
            continue
        valor = validador(brutos.get(chave))
        if valor is None:
            # Valor fora do tipo: só a chave cai (o evento vale), com rastro no log.
            logger.warning("uso: detalhe descartado acao=%.48s origem=%s chave=%.32s", nome, origem, chave)
            continue
        limpos[chave] = valor
    return limpos


def _validar(evento: Evento, origem: str) -> tuple[str | None, str | None]:
    """Devolve (entidade_id limpo, detalhes JSON) ou levanta ValueError."""
    acao = CATALOGO.get(evento.acao)
    if acao is None:
        raise ValueError("acao_desconhecida")
    if origem not in ORIGENS or origem not in acao.origens:
        raise ValueError("origem_invalida")
    if evento.entidade not in acao.entidades:
        raise ValueError("entidade_invalida")
    entidade_id = evento.entidade_id
    if entidade_id is not None and not _RE_ENTIDADE_ID.match(entidade_id):
        raise ValueError("entidade_id_invalido")

    brutos = evento.detalhes if isinstance(evento.detalhes, dict) else {}
    detalhes: dict[str, Any] = {}
    if origem == "ui" or acao.detalhes:
        # Esquema declarado (ou vindo do navegador): só chaves tipadas.
        detalhes = _detalhes_tipados(acao, brutos, nome=evento.acao, origem=origem)
    elif brutos:
        detalhes = {k: v for k, v in brutos.items() if isinstance(k, str) and k.lower() not in _PROIBIDAS}
    dump = json.dumps(detalhes, ensure_ascii=False, default=str) if detalhes else None
    if dump is not None and _RE_CPF.search(dump):
        raise ValueError("detalhes_com_cpf")
    if dump is not None and len(dump) > _DETALHES_MAX:
        dump = json.dumps({"truncado": True})
    return entidade_id, dump


_SQL = text(
    "INSERT INTO evento_uso (contact_id, sub_hash, acao, entidade, entidade_id, origem, request_id, detalhes) "
    "VALUES (:contact_id, :sub_hash, :acao, :entidade, :entidade_id, :origem, :request_id, :detalhes)"
)


def _gravar(linhas: list[dict[str, Any]]) -> None:
    from .database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        db.execute(_SQL, linhas)


def registrar_lote(
    eventos: Iterable[Evento],
    *,
    contact_id: str | None,
    sub: str | None,
    origem: str,
    request_id: str | None,
) -> tuple[int, int]:
    """Grava os eventos válidos numa transação. Devolve (gravados, descartados). Nunca lança."""
    linhas: list[dict[str, Any]] = []
    descartados = 0
    sub_hash = hash_sub(sub)
    for evento in eventos:
        try:
            entidade_id, detalhes = _validar(evento, origem)
        except ValueError as exc:
            descartados += 1
            logger.warning("uso: evento descartado (%s): acao=%.48s", exc, evento.acao)
            continue
        linhas.append({
            "contact_id": contact_id, "sub_hash": sub_hash, "acao": evento.acao, "entidade": evento.entidade,
            "entidade_id": entidade_id, "origem": origem, "request_id": request_id, "detalhes": detalhes,
        })
    if not linhas:
        return 0, descartados
    try:
        _gravar(linhas)
    except SQLAlchemyError as exc:
        _contar_falha()
        logger.error("uso: falha ao gravar %d evento(s): %s", len(linhas), type(exc).__name__)
        return 0, descartados + len(linhas)
    return len(linhas), descartados


def registrar(
    acao: str,
    entidade: str,
    entidade_id: str | None = None,
    *,
    contact_id: str | None,
    sub: str | None,
    origem: str = "servidor",
    request_id: str | None = None,
    detalhes: dict[str, Any] | None = None,
) -> bool:
    gravados, _ = registrar_lote(
        [Evento(acao, entidade, entidade_id, detalhes)],
        contact_id=contact_id, sub=sub, origem=origem, request_id=request_id,
    )
    return gravados == 1
