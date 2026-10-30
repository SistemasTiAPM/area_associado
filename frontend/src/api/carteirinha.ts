import { api } from './client';

/** `GET /api/v1/carteirinha` (RF-CA). Validade omitida até P-10. */
export interface Carteirinha {
  nome: string | null;
  crm: string | null;
  crm_uf: string | null;
  /** Número de associado exibido no cartão (RF-CA-07). */
  num_contato: string | null;
  tipo_associado: string | null;
  status_associativo: string | null;
  membro_desde: string | null;
  verificado_em: string | null;
  /** Filiação cancelada (RF-CA-08, TI-45): sem QR, sem compartilhar, sem downloads. */
  revogada: boolean;
  /** Nulos quando `revogada`. */
  url_verificacao: string | null;
  qr: string | null;
}

/** Downloads gerados no servidor (RF-CA-07, TI-46): mesma origem, `attachment`, `no-store`. */
export const URL_CARTEIRINHA_IMAGEM = '/api/v1/carteirinha/imagem.png';
export const URL_CARTEIRINHA_PDF = '/api/v1/carteirinha/documento.pdf';

export const obterCarteirinha = () => api<Carteirinha>('/carteirinha');
export const compartilharCarteirinha = () => api<{ url: string }>('/carteirinha/compartilhar', { metodo: 'POST', corpo: {} });
