/** Contrato de `GET /api/v1/sessao` (RF-AU-03). Sem CPF, e-mail, sub ou contact_id. */
export interface Sessao {
  associado: {
    nome: string;
    nome_exibicao: string;
    iniciais: string;
    tipo: string | null;
    status: string | null;
    tem_foto: boolean;
  };
  csrf: string;
  rota_inicial: string;
  flags: Record<ChaveFlag, boolean>;
  config: {
    whatsapp: string;
    show_whatsapp: boolean;
    animations: boolean;
  };
  stub: boolean;
  solicitacoes_aguardando: number;
  expira_em: string;
}

/** REQUISITOS §10 — espelho de app/flags.py:FLAGS_CONHECIDAS. */
export type ChaveFlag =
  | 'mensalidade_zero'
  | 'fatura_valor'
  | 'patrocinio'
  | 'clube_economia'
  | 'comunidade_posts'
  | 'wallet'
  | 'erp_financeiro'
  | 'totalpass';

/** Corpo de erro único da API (REQUISITOS §3.0). */
export interface CorpoErro {
  erro: string;
  mensagem: string;
  request_id: string | null;
  detalhes?: { campo: string; mensagem: string }[];
}
