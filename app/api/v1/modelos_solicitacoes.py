"""Modelos de RESPOSTA de solicitações e ajuda (Onda 2; contrato do PLANO-EXECUCAO).

Mesmo padrão de `modelos.py`: `extra="forbid"` faz a serialização falhar no
teste se uma rota devolver chave fora do contrato. Nada aqui carrega
`contact_id`, `sub`, CPF, e-mail ou `crm_*` (RF-SO-06, ADR-0014); o teste de
contrato varre as respostas reais atrás dessas chaves.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StatusSolicitacao = Literal["criada", "enviada", "em_atendimento", "pendente_associado", "concluida_positiva",
                            "concluida_negativa", "cancelada"]
AtorPublico = Literal["voce", "equipe_apm", "parceiro", "sistema"]


class _Resposta(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TipoSolicitacao(_Resposta):
    codigo: str = Field(description="`tipo_servico` (ou `beneficio` quando nasce do catálogo).")
    rotulo: str


class BeneficioRef(_Resposta):
    slug: str
    titulo: str


class ContatoSolicitacao(_Resposta):
    canal: Literal["whatsapp", "telefone"]
    texto: str


class SolicitacaoResumo(_Resposta):
    id: str
    tipo: TipoSolicitacao
    beneficio: BeneficioRef | None = Field(description="Catálogo como dado só na Fase 4: hoje sempre null.")
    status: StatusSolicitacao
    rotulo_status: str
    aguardando_parceiro: bool = Field(description="Marcador sem retorno (A05): a APM já está cobrando.")
    prazo_em: str | None = Field(description="AAAA-MM-DD (America/Sao_Paulo); null sem envio ou se encerrada.")
    contato: ContatoSolicitacao | None
    criada_em: str
    atualizada_em: str
    pode_cancelar: bool
    pode_responder: bool
    pode_avaliar: bool


class ItemLinhaDoTempo(_Resposta):
    quando: str
    status: StatusSolicitacao
    rotulo: str
    ator: AtorPublico
    mensagem: str | None = Field(description="Só a mensagem pública; justificativa interna nunca sai.")


class Avaliacao(_Resposta):
    nota: int = Field(ge=0, le=10)
    comentario: str | None
    avaliada_em: str


class Solicitacao(SolicitacaoResumo):
    campos: dict[str, Any] = Field(description="Só os campos permitidos do tipo, como o associado enviou.")
    linha_do_tempo: list[ItemLinhaDoTempo]
    avaliacao: Avaliacao | None


class ListaSolicitacoes(_Resposta):
    itens: list[SolicitacaoResumo]
    proximo_cursor: str | None


# ------------------------------------------------------------------- ajuda
class CategoriaFaq(_Resposta):
    codigo: str
    rotulo: str


class ItemFaq(_Resposta):
    id: int
    pergunta: str
    resposta: str
    categoria: str


class FaqResposta(_Resposta):
    categorias: list[CategoriaFaq]
    itens: list[ItemFaq]
    sugestoes: list[str] = Field(description="Códigos de categoria sugeridos quando a busca não encontra nada.")


class CanalWhatsapp(_Resposta):
    exibicao: str
    url: str


class CanalTelefone(_Resposta):
    exibicao: str
    uri: str


class ContatoCentral(_Resposta):
    """Bloco vazio (null) = a SPA não mostra o canal."""

    whatsapp: CanalWhatsapp | None
    telefone: CanalTelefone | None
    horario: str | None
