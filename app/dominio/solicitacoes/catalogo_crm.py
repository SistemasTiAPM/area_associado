"""Catálogo de tipos de solicitação no CRM — o MESMO do App APM (ADR-0023, ADR-0024).

Fonte: contrato do mcp_hub de 2026-11-13 (`docs/CONTRATO-HUB.md` "Solicitações", §2). O slug
vai gravado no CRM (`alf_tipo_solicitacao`) e decide se o registro aceita mensagens: slug
diferente do App = registro sem conversa e relatório divergente. **Mudar este catálogo só
junto com o App**, combinado pelo William.

Três papéis:
- `TIPOS_CRM`: os tipos do catálogo comum (slug, entidade, grupo, assunto, time, produto,
  rótulo de tela, ordem e carência iguais aos do App). `seguros` é legado: reconhecido na
  listagem e na conversa, nunca ofertado para abertura.
- `destino(tipo_servico)`: para onde vai um pedido da área. Os tipos novos usam o próprio
  slug; os tipos antigos da área que não existem no App são traduzidos — `outro` → `outros`,
  `alteracao_cadastro` → `alteracao_cadastral`, e os demais (declaração, cancelamento da
  associação etc.) → `outros` (decisão do William em 2026-11-13). Sem destino (`None`) = o
  pedido fica na área (`crm_sync='retido'`): `exclusao_dados` (LGPD) e pedido de benefício.
- `responde(slug, entidade)`: quem fala com o associado na conversa (texto de tela).

GUIDs lidos do tenant pelo hub; ele só confere que existem (inexistente → 404, que a área
trata como `catalogo_crm_invalido`). Nunca um time técnico nem regional. O `nome` do produto
no CRM ("PREV - SEGURO CARRO") nunca vai ao associado: o rótulo é o desta tabela.
"""

from __future__ import annotations

from dataclasses import dataclass

# Times (`team`).
TIME_CENTRAL = "312dcfcf-0714-e911-a952-000d3ac1be86"
TIME_DEFESA = "810c580c-c8cc-ed11-a7c6-000d3ac16b52"
TIME_SEGUROS = "7bb27bfb-0714-e911-a952-000d3ac1be86"
TIME_APOSENTADORIA = "9b92ec59-c106-ed11-82e5-000d3ac16b52"
TIME_CONTABILIDADE = "66665b46-d8e5-e811-a979-000d3ac1b2cd"
TIME_DESPACHANTE = "4d111e0f-7e1e-ed11-b83d-000d3ac16b52"
TIME_FACILITIES = "3afbea3a-7d1e-ed11-b83d-000d3ac16b52"
# Assuntos (`subject`).
ASSUNTO_ATUALIZACAO_CADASTRAL = "e2d19f07-29e1-e811-a974-000d3ac1b8d2"
ASSUNTO_ATENDIMENTO_APM = "64fb455c-c4e1-e811-a974-000d3ac1b8d2"
ASSUNTO_SEGUNDA_VIA = "710f6a32-29e1-e811-a974-000d3ac1b8d2"
ASSUNTO_DEFESA = "774db512-2bfb-ed11-8f6e-000d3ac16b52"

GRUPOS: dict[str, str] = {"seguros": "Seguros"}

# Quem responde ao associado (texto de tela, igual ao App).
RESPONDE_CENTRAL = "central"  # "Central de Relacionamento"
RESPONDE_APM = "apm"          # "Equipe APM"
_ATENDIMENTO_GERAL = frozenset({"alteracao_cadastral", "duvida", "segunda_via_boleto", "outros"})


@dataclass(frozen=True)
class TipoCrm:
    slug: str
    rotulo: str
    entidade: str           # ocorrencia | oportunidade
    assunto_id: str | None  # obrigatório em ocorrência, None em oportunidade
    time_id: str
    produto_id: str | None  # só em oportunidade
    ordem: int
    grupo: str | None = None
    carencia_meses: int = 0
    ofertavel: bool = True


def _ocorrencia(slug: str, rotulo: str, assunto: str, ordem: int, *, time: str = TIME_CENTRAL,
                carencia: int = 0) -> TipoCrm:
    return TipoCrm(slug, rotulo, "ocorrencia", assunto, time, None, ordem, carencia_meses=carencia)


def _oportunidade(slug: str, rotulo: str, time: str, produto: str | None, ordem: int, *,
                  grupo: str | None = None, carencia: int = 0, ofertavel: bool = True) -> TipoCrm:
    return TipoCrm(slug, rotulo, "oportunidade", None, time, produto, ordem, grupo, carencia, ofertavel)


TIPOS_CRM: dict[str, TipoCrm] = {t.slug: t for t in (
    _oportunidade("planos_de_saude", "Planos de Saúde", TIME_SEGUROS,
                  "217ad212-6d88-e911-a968-000d3ac1b6c7", 10),
    _oportunidade("seguro_vida", "Seguro de Vida", TIME_SEGUROS,
                  "51fff108-6e88-e911-a968-000d3ac1b6c7", 20, grupo="seguros"),
    _oportunidade("seguro_vida_dit", "Seguro de Vida – DIT adicional", TIME_SEGUROS,
                  "6e87d9fe-87e9-eb11-bacb-0022483785cc", 21, grupo="seguros"),
    _oportunidade("seguro_carro", "Seguro Auto", TIME_SEGUROS,
                  "c0fce926-6e88-e911-a968-000d3ac1b6c7", 22, grupo="seguros"),
    _oportunidade("seguro_residencial", "Seguro Residencial", TIME_SEGUROS,
                  "d26d429c-5ef5-eb11-94ef-002248370ae9", 23, grupo="seguros"),
    _oportunidade("seguro_viagem", "Seguro Viagem", TIME_SEGUROS,
                  "b8cfc64a-6e88-e911-a968-000d3ac1b6c7", 24, grupo="seguros"),
    _oportunidade("seguro_pet", "Seguro Pet", TIME_SEGUROS,
                  "f200d262-6e88-e911-a968-000d3ac1b6c7", 25, grupo="seguros"),
    _oportunidade("seguro_responsabilidade_civil", "Seguro de Responsabilidade Civil", TIME_SEGUROS,
                  "3edf4a52-6a14-ef11-9f89-6045bd3ae7ae", 26, grupo="seguros"),
    _oportunidade("seguros", "Seguros", TIME_SEGUROS, None, 29, ofertavel=False),  # legado
    _ocorrencia("defesa_profissional", "Defesa Profissional", ASSUNTO_DEFESA, 40, time=TIME_DEFESA,
                carencia=3),
    _oportunidade("assessoria_aposentadoria", "Assessoria para Aposentadoria", TIME_APOSENTADORIA,
                  "11bcef28-8625-e911-a963-000d3ac1b38b", 50, carencia=3),
    _oportunidade("contabilidade", "Contabilidade", TIME_CONTABILIDADE,
                  "cb0f0d4d-8625-e911-a963-000d3ac1b38b", 60, carencia=2),
    _oportunidade("despachante", "Despachante", TIME_DESPACHANTE,
                  "f6fdd73e-8525-e911-a963-000d3ac1b38b", 70, carencia=2),
    _oportunidade("apm_facilities", "APM Facilities", TIME_FACILITIES,
                  "27ad3e28-53f5-eb11-94ef-002248370ae9", 80),
    _ocorrencia("alteracao_cadastral", "Alteração cadastral", ASSUNTO_ATUALIZACAO_CADASTRAL, 100),
    _ocorrencia("duvida", "Dúvidas e perguntas", ASSUNTO_ATENDIMENTO_APM, 110),
    _ocorrencia("segunda_via_boleto", "Segunda via de boleto", ASSUNTO_SEGUNDA_VIA, 120),
    _ocorrencia("outros", "Outros assuntos", ASSUNTO_ATENDIMENTO_APM, 130),
)}

# Tipos que a tela "Nova solicitação" oferece (`tipo_servico` local = slug do CRM). Os dois
# que a área já abria por formulário próprio seguem com o nome local e não entram aqui:
# `alteracao_cadastral` (a área usa `alteracao_cadastro`, com campo e justificativa) e
# `outros` (a área usa `outro`, pelo formulário da Ajuda).
TIPOS_NOVOS: frozenset[str] = frozenset(
    slug for slug, t in TIPOS_CRM.items() if t.ofertavel and slug not in ("alteracao_cadastral", "outros"))

# `tipo_servico` antigo da área → slug do catálogo comum. None = não vai ao CRM.
_LOCAL_PARA_CRM: dict[str, str | None] = {
    "outro": "outros",
    "alteracao_cadastro": "alteracao_cadastral",
    "declaracao_associado": "outros",
    "cancelamento_associacao": "outros",
    "cartao_apm": "outros",
    "diagnostico_marketing": "outros",
    "submeter_trabalho": "outros",
    "mentoria_pedir": "outros",
    "mentoria_oferecer": "outros",
    "exclusao_dados": None,
}


@dataclass(frozen=True)
class DestinoCrm:
    entidade: str
    assunto_id: str | None
    time_id: str
    tipo: str               # slug gravado no CRM
    produto_id: str | None = None


def slug_crm(tipo_servico: str | None) -> str | None:
    """Slug do catálogo comum para um `tipo_servico` da área, ou None (não vai ao CRM).
    Tipo desconhecido = None (fail-closed: nada sai para o CRM sem estar nesta tabela)."""
    if tipo_servico is None:
        return None
    if tipo_servico in _LOCAL_PARA_CRM:
        return _LOCAL_PARA_CRM[tipo_servico]
    return tipo_servico if tipo_servico in TIPOS_NOVOS else None


def destino(tipo_servico: str | None, beneficio_id: str | None = None) -> DestinoCrm | None:
    """Destino do pedido no CRM, ou None (fica só na área)."""
    if beneficio_id is not None:
        return None
    slug = slug_crm(tipo_servico)
    if slug is None:
        return None
    tipo = TIPOS_CRM[slug]
    return DestinoCrm(tipo.entidade, tipo.assunto_id, tipo.time_id, tipo.slug, tipo.produto_id)


def traduzido(tipo_servico: str | None) -> bool:
    """True quando o slug gravado no CRM difere do tipo da área (o título leva o rótulo real)."""
    return tipo_servico in _LOCAL_PARA_CRM


def ofertaveis() -> list[TipoCrm]:
    """Tipos da tela "Nova solicitação", na ordem do App."""
    return sorted((TIPOS_CRM[s] for s in TIPOS_NOVOS), key=lambda t: t.ordem)


def aceita_mensagem(slug: str | None) -> bool:
    """Todo tipo do catálogo comum aceita mensagem do associado (inclusive o legado)."""
    return slug in TIPOS_CRM


def rotulo(slug: str | None) -> str | None:
    tipo = TIPOS_CRM.get(slug) if slug else None
    return tipo.rotulo if tipo else None


def responde(slug: str | None, entidade: str | None) -> str:
    """Quem responde na conversa: a Central nos quatro tipos de atendimento geral e em
    ocorrência de tipo desconhecido; a Equipe APM em defesa profissional, em toda
    oportunidade e em entidade desconhecida (regra do App)."""
    if slug in _ATENDIMENTO_GERAL:
        return RESPONDE_CENTRAL
    if slug is None and entidade == "ocorrencia":
        return RESPONDE_CENTRAL
    if slug not in TIPOS_CRM and entidade == "ocorrencia":
        return RESPONDE_CENTRAL
    return RESPONDE_APM


def produto_ids() -> list[str]:
    """Produtos dos tipos ofertáveis (entrada de `solicitacao.produtos`)."""
    return sorted({t.produto_id for t in ofertaveis() if t.produto_id})
