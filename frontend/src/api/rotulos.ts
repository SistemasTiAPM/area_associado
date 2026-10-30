import type { AssuntoFormulario, MotivoCancelamento } from './ajuda';

/**
 * Códigos fechados do contrato da Onda 2 (espelho de app/dominio/solicitacoes/rotulos.py)
 * e os rótulos que a SPA mostra. Rótulos: proposta até P-44 (DEC-35), voz §3.3.
 */

/** Assunto do formulário da Central (`POST /ajuda/formulario`; RF-AJ-03). */
export const ROTULOS_ASSUNTO: Readonly<Record<AssuntoFormulario, string>> = {
  beneficio: 'Dúvida sobre benefício',
  cadastro: 'Cadastro',
  financeiro: 'Financeiro',
  eventos: 'Eventos',
  outro: 'Outro assunto',
};

export const ASSUNTOS: readonly AssuntoFormulario[] = ['beneficio', 'cadastro', 'financeiro', 'eventos', 'outro'];

/**
 * `ajuda_contatar.detalhes.assunto` aceita outro catálogo (app/uso.py): o que não
 * tem par vai como `outro` (o validador descartaria valor fora da lista).
 */
export const ASSUNTO_ANALYTICS: Readonly<Record<AssuntoFormulario, string>> = {
  beneficio: 'beneficios',
  cadastro: 'cadastro',
  financeiro: 'financeiro',
  eventos: 'outro',
  outro: 'outro',
};

/** Finalidade da `declaracao_associado` (RF-FI-04): a AMB tem carência de 1 mês de filiação. */
export type FinalidadeDeclaracao = 'amb_prova_titulo' | 'geral';

export const ROTULOS_FINALIDADE: Readonly<Record<FinalidadeDeclaracao, string>> = {
  geral: 'Declaração de associado',
  amb_prova_titulo: 'AMB para prova de título',
};

/** Motivos do cancelamento da associação (spec v2 P14; RF-AJ-04), na ordem da spec. */
export const ROTULOS_MOTIVO: Readonly<Record<MotivoCancelamento, string>> = {
  nao_uso: 'Não uso os benefícios',
  preco: 'Preço',
  mudanca: 'Mudança de cidade ou de fase',
  insatisfacao_servico: 'Insatisfação com um serviço',
  outro: 'Outro',
};

export const MOTIVOS: readonly MotivoCancelamento[] = ['nao_uso', 'preco', 'mudanca', 'insatisfacao_servico', 'outro'];
