"""Rótulos pt-BR das solicitações (REQUISITOS §7.1 e §7.4; spec v2 §8.5).

Textos da spec como PROPOSTA até a P-44 (DEC-35): mudar um rótulo é mudar só
aqui. Status e códigos nunca mudam (são contrato com a SPA e com o banco).
"""

from __future__ import annotations

from . import catalogo_crm

STATUS: tuple[str, ...] = ("criada", "enviada", "em_atendimento", "pendente_associado",
                           "concluida_positiva", "concluida_negativa", "cancelada")
TERMINAIS: frozenset[str] = frozenset({"concluida_positiva", "concluida_negativa", "cancelada"})
NAO_TERMINAIS: tuple[str, ...] = tuple(s for s in STATUS if s not in TERMINAIS)
CONCLUIDAS: frozenset[str] = frozenset({"concluida_positiva", "concluida_negativa"})

# Os 7 rótulos ao associado (RF-SO-08).
_ROTULO_STATUS: dict[str, str] = {
    "criada": "Recebida pela APM",
    "enviada": "Enviada ao parceiro",
    "em_atendimento": "Em atendimento",
    "pendente_associado": "O parceiro precisa de algo seu",
    "concluida_positiva": "Concluída",
    "concluida_negativa": "Não seguiu",
    "cancelada": "Cancelada",
}
# Tipo de ativação 3 (serviço da própria APM): só `enviada` muda (contrato da Onda 2).
_ROTULO_STATUS_TIPO3: dict[str, str] = {
    "enviada": "Encaminhada à equipe",
}
ROTULO_MARCADOR = "Aguardando o parceiro, a APM já está cobrando"
# Mensagem pública de `pendente_associado` vindo do CRM, que não manda texto
# (ADR-0023; decisão de 2026-11-04). O job acrescenta o protocolo.
MENSAGEM_PENDENTE_CRM = ("A Central de Relacionamento precisa de mais informações sobre este pedido e vai "
                         "falar com você pelos contatos do seu cadastro.")
# `pendente_associado` porque a Central respondeu na conversa (statuscode 100000002, ADR-0024).
MENSAGEM_RESPOSTA_NA_CONVERSA = "Há uma nova mensagem para você na conversa desta solicitação."
# Cancelamento pelo sistema quando o CRM recusa o produto do tipo (422 `produto_inativo`).
MENSAGEM_SERVICO_INDISPONIVEL = "Este serviço não está disponível no momento."

ROTULO_TIPO: dict[str, str] = {
    "alteracao_cadastro": "Alteração de cadastro",
    "diagnostico_marketing": "Diagnóstico de marketing",
    "submeter_trabalho": "Publicação na revista",
    "mentoria_pedir": "Quero um mentor",
    "mentoria_oferecer": "Quero ser mentor",
    "cartao_apm": "Cartão APM",
    "outro": "Outro assunto",
    "declaracao_associado": "Declaração de associado",
    "cancelamento_associacao": "Cancelamento da associação",
    "exclusao_dados": "Exclusão de dados",
    "beneficio": "Benefício",
    # Tipos do catálogo comum com o App APM (ADR-0024): o rótulo é o do catálogo.
    **{slug: catalogo_crm.TIPOS_CRM[slug].rotulo for slug in sorted(catalogo_crm.TIPOS_NOVOS)},
}

# Ator no log → quem o associado vê na linha do tempo (contrato da API).
ATOR_PUBLICO: dict[str, str] = {
    "associado": "voce",
    "apm": "equipe_apm",
    "parceiro": "parceiro",
    "sistema": "sistema",
    "importacao": "sistema",
}

# Assunto do formulário da Ajuda (RF-AJ-03) → assunto gravado na solicitação `outro`.
ASSUNTO_FORMULARIO: dict[str, str] = {
    "beneficio": "Dúvida sobre benefício",
    "cadastro": "Cadastro",
    "financeiro": "Financeiro",
    "eventos": "Eventos",
    "outro": "Outro assunto",
}

FINALIDADE_DECLARACAO: dict[str, str] = {
    "amb_prova_titulo": "AMB — prova de título de especialista",
    "geral": "Comprovação de vínculo com a APM",
}

MOTIVO_CANCELAMENTO: dict[str, str] = {
    "nao_uso": "Não uso os benefícios",
    "preco": "Preço",
    "mudanca": "Mudança de cidade ou de fase",
    "insatisfacao_servico": "Insatisfação com o serviço",
    "outro": "Outro motivo",
}

CAMPO_CADASTRO: dict[str, str] = {
    "nome": "Nome",
    "sobrenome": "Sobrenome",
    "data_nascimento": "Data de nascimento",
    "sexo": "Sexo",
}

SEXO: dict[str, str] = {
    "feminino": "Feminino",
    "masculino": "Masculino",
    "outro": "Outro",
    "prefiro_nao_informar": "Prefiro não informar",
}


def rotulo_status(status: str, tipo_ativacao: int | None = None) -> str:
    if tipo_ativacao == 3 and status in _ROTULO_STATUS_TIPO3:
        return _ROTULO_STATUS_TIPO3[status]
    return _ROTULO_STATUS[status]


def rotulo_marcador() -> str:
    return ROTULO_MARCADOR


def rotulo_tipo(tipo_servico: str | None) -> str:
    return ROTULO_TIPO.get(tipo_servico or "beneficio", ROTULO_TIPO["beneficio"])


def rotulo_evento(evento: str, para_status: str, tipo_ativacao: int | None) -> str:
    """Rótulo de um item da linha do tempo."""
    if evento in ("sem_retorno", "sem_retorno_2"):
        return rotulo_marcador()
    if evento == "avaliacao":
        return "Avaliação registrada"
    return rotulo_status(para_status, tipo_ativacao)
