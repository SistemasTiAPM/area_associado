import { api } from './client';

/** `GET /api/v1/carteirinha` (RF-CA). Validade omitida até P-10. */
export interface Carteirinha {
  nome: string | null;
  crm: string | null;
  crm_uf: string | null;
  num_contato: string | null;
  tipo_associado: string | null;
  status_associativo: string | null;
  membro_desde: string | null;
  verificado_em: string | null;
  url_verificacao: string;
  qr: string;
}

export const obterCarteirinha = () => api<Carteirinha>('/carteirinha');
export const compartilharCarteirinha = () => api<{ url: string }>('/carteirinha/compartilhar', { metodo: 'POST', corpo: {} });
