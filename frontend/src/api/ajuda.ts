import { api } from './client';
import type { Solicitacao } from './solicitacoes';

/** Ajuda e atendimento (P14; RF-AJ-01..05; contrato da Onda 2 em docs/PLANO-EXECUCAO.md). */

export interface CategoriaFaq {
  codigo: string;
  rotulo: string;
}

export interface ItemFaq {
  /** Inteiro no servidor (`ItemFaq.id`); a SPA só usa como chave. */
  id: number | string;
  pergunta: string;
  resposta: string;
  /** `codigo` de uma das `categorias`. */
  categoria: string;
}

export interface RespostaFaq {
  categorias: CategoriaFaq[];
  itens: ItemFaq[];
  /** Códigos de categoria sugeridos quando a busca não encontra nada. */
  sugestoes: string[];
}

/** Canais da Central (RF-AJ-02); `null` = canal sem configuração, o bloco dele some. */
export interface ContatoCentral {
  whatsapp: { exibicao: string; url: string } | null;
  telefone: { exibicao: string; uri: string } | null;
  horario: string | null;
}

export type AssuntoFormulario = 'beneficio' | 'cadastro' | 'financeiro' | 'eventos' | 'outro';

export type MotivoCancelamento = 'nao_uso' | 'preco' | 'mudanca' | 'insatisfacao_servico' | 'outro';

export const BUSCA_FAQ_MAX = 80;
export const MENSAGEM_MAX = 2000;
export const COMENTARIO_CANCELAMENTO_MAX = 500;

export function buscarFaq(filtro: { q?: string; categoria?: string | null }, sinal?: AbortSignal) {
  const consulta = new URLSearchParams();
  const q = filtro.q?.trim().slice(0, BUSCA_FAQ_MAX);
  if (q) consulta.set('q', q);
  if (filtro.categoria) consulta.set('categoria', filtro.categoria);
  const sufixo = consulta.toString();
  return api<RespostaFaq>(`/ajuda/faq${sufixo ? `?${sufixo}` : ''}`, sinal ? { sinal } : {});
}

export const obterContatoCentral = (sinal?: AbortSignal) => api<ContatoCentral>('/ajuda/contato', sinal ? { sinal } : {});

export const enviarFormularioCentral = (pedido: { assunto: AssuntoFormulario; mensagem: string; chave_idempotencia: string }) =>
  api<Solicitacao>('/ajuda/formulario', { metodo: 'POST', corpo: { ...pedido, mensagem: pedido.mensagem.trim() } });

export function pedirCancelamento(pedido: {
  motivo: MotivoCancelamento;
  quer_conversa: boolean;
  comentario: string;
  chave_idempotencia: string;
}) {
  const comentario = pedido.comentario.trim();
  const corpo = {
    motivo: pedido.motivo,
    quer_conversa: pedido.quer_conversa,
    chave_idempotencia: pedido.chave_idempotencia,
    ...(comentario ? { comentario } : {}),
  };
  return api<Solicitacao>('/ajuda/cancelamento', { metodo: 'POST', corpo });
}

/** Step-up do cancelamento (RF-AU-11): volta ao Login APM pedindo a senha e retorna à Ajuda. */
export function urlReautenticacaoAjuda(): string {
  return `/auth/login?reauth=1&next=${encodeURIComponent('/area/ajuda')}`;
}
