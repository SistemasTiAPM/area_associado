"""Modelos de RESPOSTA da API v1 (TI-07): dão forma ao OpenAPI exportado em
`docs/api/openapi.json` sem mudar o JSON que a SPA já recebe.

`extra="forbid"`: se uma rota devolver chave fora do modelo, a serialização
falha no teste em vez de a chave sumir em silêncio do contrato.
Nada aqui carrega CPF, `sub`, `contact_id` ou token (REQUISITOS §3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...flags import FLAGS_CONHECIDAS


class _Resposta(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ sessão
class AssociadoSessao(_Resposta):
    nome: str
    nome_exibicao: str
    iniciais: str
    tipo: str | None
    status: str | None
    tem_foto: bool
    foto_versao: str | None


class ConfigInterface(_Resposta):
    whatsapp: str
    show_whatsapp: bool
    animations: bool


class RecursosSessao(_Resposta):
    """Prontidão das migrações da Onda 2 (`app/prontidao.py`): false = a SPA mostra "em construção"."""

    solicitacoes: bool
    ajuda: bool
    privacidade: bool = Field(description="`sql/017` aplicada (P13: preferências, consentimentos, dados).")


class PreferenciasSessao(_Resposta):
    """O que o shell precisa antes de qualquer tela (flag `perfil_preferencias`; senão, o padrão)."""

    fonte: Literal["padrao", "grande", "maior"]
    tratamento: str | None = Field(description="Como prefere ser chamado; null = saudação neutra com o primeiro nome.")


class SessaoResposta(_Resposta):
    """`GET /api/v1/sessao` — sem CPF, e-mail, `sub` ou `contact_id`."""

    associado: AssociadoSessao
    csrf: str
    rota_inicial: str
    flags: dict[str, bool] = Field(description=f"Chaves: {', '.join(FLAGS_CONHECIDAS)}.")
    config: ConfigInterface
    stub: bool
    dados_demonstracao: bool
    recursos: RecursosSessao
    solicitacoes_aguardando: int = Field(description="Solicitações em `pendente_associado` (0 sem o recurso).")
    preferencias: PreferenciasSessao
    expira_em: str


# ------------------------------------------------------------------- uso
class UsoResposta(_Resposta):
    gravados: int
    descartados: int


# ---------------------------------------------------------------- perfil
class PerfilResposta(_Resposta):
    nome: str | None
    email: str | None
    celular: str | None
    telefone: str | None
    telefone2: str | None
    endereco: dict[str, str | None] | None
    num_contato: str | None
    crm: str | None
    crm_uf: str | None
    tipo_associado: str | None
    status_associativo: str | None
    data_filiacao: str | None
    tem_foto: bool
    foto_versao: str | None
    edicao_disponivel: bool
    endereco_disponivel: bool
    atualizado_em: str | None
    desatualizado: bool
    email_exige_reautenticacao: bool
    celular_exige_reautenticacao: bool = Field(
        description="Só com CELULAR_EXIGE_REAUTH: trocar o celular pede senha recente no Login APM (TI-09)."
    )


class TrocaEmailIniciada(_Resposta):
    enviado_para: str = Field(description="E-mail mascarado.")
    expira_em: str | None
    codigo_teste: str | None = Field(None, description="Só fora de produção com SMTP_MODE=stub.")


class FotoResposta(_Resposta):
    tem_foto: bool
    foto_versao: str | None


# ------------------------------------------- perfil e privacidade (P13)
class Opcao(_Resposta):
    valor: str
    rotulo: str


class OpcoesPreferencias(_Resposta):
    atuacao: list[Opcao]
    temas: list[Opcao]
    canal_preferido: list[Opcao]
    frequencia: list[Opcao]
    fonte: list[Opcao]


class PreferenciasResposta(_Resposta):
    """Perfil declarado (ADR-0026; REQUISITOS §9.1). Listas vazias e `null` = ainda não respondido."""

    tratamento: str | None
    atuacao: list[str]
    temas: list[str]
    canal_preferido: str | None
    frequencia: str | None
    fonte: Literal["padrao", "grande", "maior"]
    atualizado_em: str | None
    faltam: list[str] = Field(description="Campos do perfil ainda sem resposta (base do \"Complete seu perfil\").")
    opcoes: OpcoesPreferencias


class PerguntaPerfil(_Resposta):
    chave: str
    titulo: str
    ajuda: str
    tipo: Literal["texto", "multipla", "unica"]
    opcoes: list[Opcao]
    maximo: int | None


class PerguntaResposta(_Resposta):
    pergunta: PerguntaPerfil | None = Field(description="null = nada a perguntar nesta visita.")


class ConsentimentoHistorico(_Resposta):
    valor: Literal["concedido", "retirado"]
    versao: str
    origem: str
    registrado_em: str | None


class ConsentimentoItem(_Resposta):
    finalidade: str
    canal: str
    titulo: str
    texto: str
    versao: str = Field(description="Versão vigente do texto; devolver no PUT.")
    concedido: bool
    versao_registrada: str | None
    registrado_em: str | None
    texto_mudou: bool = Field(description="Concedido sobre uma versão anterior do texto.")
    historico: list[ConsentimentoHistorico]


class ConsentimentosResposta(_Resposta):
    itens: list[ConsentimentoItem]


class PedidoTitular(_Resposta):
    protocolo: str
    tipo: Literal["exportacao", "exclusao"]
    status: Literal["registrado", "em_analise", "concluido", "recusado", "cancelado"]
    criado_em: str | None
    concluido_em: str | None
    solicitacao_id: str | None


class PedidosTitularResposta(_Resposta):
    itens: list[PedidoTitular]
    exportacao_disponivel_em: str | None = Field(description="null = já pode baixar os dados.")
    exclusao_aberta: PedidoTitular | None
    exige_reautenticacao: bool = Field(description="Baixar e pedir exclusão pedem senha recente no Login APM.")


class ExclusaoResposta(_Resposta):
    protocolo: str
    solicitacao_id: str
    registrado_em: str | None


# ----------------------------------------------------------- carteirinha
class CarteirinhaResposta(_Resposta):
    nome: str | None
    crm: str | None
    crm_uf: str | None
    num_contato: str | None
    tipo_associado: str | None
    status_associativo: str | None
    membro_desde: str | None
    verificado_em: str | None
    # TI-45/46: revogada (filiação cancelada no CRM) ⇒ sem QR nem URL de verificação.
    revogada: bool
    url_verificacao: str | None
    qr: str | None


class UrlResposta(_Resposta):
    url: str
