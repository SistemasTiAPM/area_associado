"""Destino no CRM de cada tipo de solicitação (ADR-0023).

Tabela fixa: `tipo_servico` → entidade, assunto e time do CRM. GUIDs lidos do tenant
pelo mcp_hub em 2026-11-04 (`mcp_hub/docs/CATALOGO-CRM-SOLICITACOES.md`); o hub só
confere que existem. Mudar o destino de um tipo é mudar uma linha aqui (deploy) até o
catálogo virar dado (RNF-29, Fase 4/backoffice).

Decisão de 2026-11-04 (William): todo tipo de hoje vira **ocorrência** da **Central de
Relacionamento**; `alteracao_cadastro` → assunto "Atualização Cadastral - Pessoa Física";
os demais → "Atendimento APM" até a Central escolher (candidatos registrados abaixo).
Sem destino (`None`) = o pedido fica na área (`crm_sync='retido'` + aviso):
`exclusao_dados` (LGPD, DEC-06 da Onda 3) e pedido de benefício (Fase 4).

Nunca um time técnico (`apmhom`, `MCP Hub (integrações)`, `COBAIA`) nem regional.
"""

from __future__ import annotations

from dataclasses import dataclass

# Time proprietário de toda ocorrência de autoatendimento.
TIME_CENTRAL = "312dcfcf-0714-e911-a952-000d3ac1be86"
# Assuntos (`subject`).
ASSUNTO_ATUALIZACAO_CADASTRAL = "e2d19f07-29e1-e811-a974-000d3ac1b8d2"
ASSUNTO_ATENDIMENTO_APM = "64fb455c-c4e1-e811-a974-000d3ac1b8d2"
# Candidatos para a Central decidir (não usados ainda):
#   Declarações            61712384-29e1-e811-a974-000d3ac1b8d2
#   Cancelamento associativo 1e1b984c-29e1-e811-a974-000d3ac1b8d2
#   Carteirinha Associativa 8915d413-29e1-e811-a974-000d3ac1b8d2


@dataclass(frozen=True)
class DestinoCrm:
    entidade: str          # ocorrencia | oportunidade
    assunto_id: str | None  # obrigatório em ocorrência, None em oportunidade
    time_id: str


_OCORRENCIA_GERAL = DestinoCrm("ocorrencia", ASSUNTO_ATENDIMENTO_APM, TIME_CENTRAL)

CATALOGO: dict[str, DestinoCrm | None] = {
    "alteracao_cadastro": DestinoCrm("ocorrencia", ASSUNTO_ATUALIZACAO_CADASTRAL, TIME_CENTRAL),
    "outro": _OCORRENCIA_GERAL,
    "declaracao_associado": _OCORRENCIA_GERAL,
    "cancelamento_associacao": _OCORRENCIA_GERAL,
    "cartao_apm": _OCORRENCIA_GERAL,
    "diagnostico_marketing": _OCORRENCIA_GERAL,
    "submeter_trabalho": _OCORRENCIA_GERAL,
    "mentoria_pedir": _OCORRENCIA_GERAL,
    "mentoria_oferecer": _OCORRENCIA_GERAL,
    "exclusao_dados": None,
}


def destino(tipo_servico: str | None, beneficio_id: str | None = None) -> DestinoCrm | None:
    """Destino do pedido no CRM, ou None (fica só na área). Tipo desconhecido = None
    (fail-closed: nada sai para o CRM sem estar nesta tabela)."""
    if beneficio_id is not None or tipo_servico is None:
        return None
    return CATALOGO.get(tipo_servico)
