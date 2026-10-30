import type { ResumoSolicitacao, Solicitacao } from '../api/solicitacoes';

/** Fábricas de dados do contrato da Onda 2 (docs/PLANO-EXECUCAO.md) para os testes de tela. */

export const ID_SOLICITACAO = '0f8c2a8e-4b1d-4c55-9d2e-1a2b3c4d5e6f';

export function resumo(parcial: Partial<ResumoSolicitacao> = {}): ResumoSolicitacao {
  return {
    id: ID_SOLICITACAO,
    tipo: { codigo: 'outro', rotulo: 'Outro assunto' },
    beneficio: null,
    status: 'criada',
    rotulo_status: 'Recebida pela APM',
    aguardando_parceiro: false,
    prazo_em: null,
    contato: null,
    criada_em: '2026-10-20T13:00:00Z',
    atualizada_em: '2026-10-21T15:30:00Z',
    pode_cancelar: true,
    pode_responder: false,
    pode_avaliar: false,
    ...parcial,
  };
}

export function solicitacao(parcial: Partial<Solicitacao> = {}): Solicitacao {
  return {
    ...resumo(parcial),
    campos: { assunto: 'Dúvida sobre benefício', mensagem: 'Como uso o desconto na escola de idiomas?', categoria: 'beneficio' },
    linha_do_tempo: [
      { quando: '2026-10-20T13:00:00Z', status: 'criada', rotulo: 'Recebida pela APM', ator: 'voce', mensagem: null },
    ],
    avaliacao: null,
    ...parcial,
  };
}
