import { api } from './client';
import type { TamanhoFonte } from './tipos';

/** P13 Perfil e privacidade (ADR-0025 e ADR-0026). Catálogos vêm do servidor: a SPA não os repete. */
export interface OpcaoPreferencia {
  valor: string;
  rotulo: string;
}

export type CampoPerfil = 'tratamento' | 'atuacao' | 'temas' | 'frequencia';

/** `GET|PUT /api/v1/perfil/preferencias` [F:`perfil_preferencias`]. */
export interface Preferencias {
  tratamento: string | null;
  atuacao: string[];
  temas: string[];
  /** Só os canais que existem (regra 19); hoje, só e-mail — por isso a tela ainda não pergunta. */
  canal_preferido: string | null;
  frequencia: string | null;
  fonte: TamanhoFonte;
  atualizado_em: string | null;
  /** Campos do perfil ainda sem resposta (base do "Complete seu perfil"). */
  faltam: CampoPerfil[];
  opcoes: Record<'atuacao' | 'temas' | 'canal_preferido' | 'frequencia' | 'fonte', OpcaoPreferencia[]>;
}

export type CamposPreferencias = Partial<Pick<Preferencias, 'tratamento' | 'atuacao' | 'temas' | 'canal_preferido' | 'frequencia' | 'fonte'>>;

/** Perfil progressivo: uma pergunta por visita. */
export interface Pergunta {
  chave: CampoPerfil;
  titulo: string;
  ajuda: string;
  tipo: 'texto' | 'multipla' | 'unica';
  opcoes: OpcaoPreferencia[];
  maximo: number | null;
}

export interface HistoricoConsentimento {
  valor: 'concedido' | 'retirado';
  versao: string;
  origem: string;
  registrado_em: string | null;
}

/** `GET|PUT /api/v1/perfil/consentimentos` [F:`lgpd_consentimentos`]. */
export interface Consentimento {
  finalidade: string;
  canal: string;
  titulo: string;
  texto: string;
  /** Versão vigente do texto: volta no PUT (409 `versao_desatualizada` se mudou). */
  versao: string;
  concedido: boolean;
  versao_registrada: string | null;
  registrado_em: string | null;
  texto_mudou: boolean;
  historico: HistoricoConsentimento[];
}

export interface PedidoTitular {
  protocolo: string;
  tipo: 'exportacao' | 'exclusao';
  status: 'registrado' | 'em_analise' | 'concluido' | 'recusado' | 'cancelado';
  criado_em: string | null;
  concluido_em: string | null;
  solicitacao_id: string | null;
}

/** `GET /api/v1/perfil/dados/pedidos` [F:`lgpd_consentimentos`]. */
export interface PedidosTitular {
  itens: PedidoTitular[];
  exportacao_disponivel_em: string | null;
  exclusao_aberta: PedidoTitular | null;
  exige_reautenticacao: boolean;
}

export interface ExclusaoPedida {
  protocolo: string;
  solicitacao_id: string;
  registrado_em: string | null;
}

export const PALAVRA_CONFIRMACAO = 'EXCLUIR';

export const obterPreferencias = () => api<Preferencias>('/perfil/preferencias');
export const salvarPreferencias = (campos: CamposPreferencias) =>
  api<Preferencias>('/perfil/preferencias', { metodo: 'PUT', corpo: campos });

export const obterPergunta = () => api<{ pergunta: Pergunta | null }>('/perfil/pergunta');
export const responderPergunta = (chave: CampoPerfil, resposta: string | string[]) =>
  api<Preferencias>(`/perfil/pergunta/${chave}`, { metodo: 'POST', corpo: { resposta } });
export const pularPergunta = (chave: CampoPerfil) =>
  api<Preferencias>(`/perfil/pergunta/${chave}`, { metodo: 'POST', corpo: { pular: true } });

export const listarConsentimentos = () => api<{ itens: Consentimento[] }>('/perfil/consentimentos');
export const decidirConsentimento = (item: Pick<Consentimento, 'finalidade' | 'canal' | 'versao'>, concedido: boolean) =>
  api<Consentimento>('/perfil/consentimentos', {
    metodo: 'PUT',
    corpo: { finalidade: item.finalidade, canal: item.canal, versao: item.versao, concedido },
  });

export const listarPedidosTitular = () => api<PedidosTitular>('/perfil/dados/pedidos');
/** O arquivo vem no corpo (JSON); o servidor também manda `Content-Disposition`, mas quem salva é a SPA. */
export const exportarDados = () => api<Record<string, unknown>>('/perfil/dados/exportar', { metodo: 'POST' });
export const pedirExclusao = (confirmacao: string, chaveIdempotencia: string) =>
  api<ExclusaoPedida>('/perfil/dados/exclusao', {
    metodo: 'POST',
    corpo: { confirmacao, chave_idempotencia: chaveIdempotencia },
  });
