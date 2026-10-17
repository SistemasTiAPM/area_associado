import { api, enviarFormulario } from './client';

export interface Endereco {
  logradouro: string;
  numero: string;
  complemento: string | null;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
}

/** `GET /api/v1/perfil` (RF-PE). Sem CPF por contrato (ADR-0014). */
export interface Perfil {
  nome: string | null;
  email: string | null;
  celular: string | null;
  telefone: string | null;
  telefone2: string | null;
  endereco: Endereco | null;
  num_contato: string | null;
  crm: string | null;
  crm_uf: string | null;
  tipo_associado: string | null;
  status_associativo: string | null;
  data_filiacao: string | null;
  tem_foto: boolean;
  foto_versao: string | null;
  atualizado_em: string | null;
  desatualizado: boolean;
  email_exige_reautenticacao: boolean;
}

export type CamposContato = Partial<{
  celular: string;
  telefone: string | null;
  telefone2: string | null;
  endereco: Endereco;
}>;

export interface PedidoCodigo {
  enviado_para: string;
  expira_em: string;
  codigo_teste?: string;
}

export const obterPerfil = () => api<Perfil>('/perfil');
export const atualizarContato = (campos: CamposContato) => api<Perfil>('/perfil/contato', { metodo: 'PUT', corpo: campos });
export const iniciarTrocaEmail = (email: string) => api<PedidoCodigo>('/perfil/email', { metodo: 'POST', corpo: { email } });
export const confirmarTrocaEmail = (email: string, codigo: string) =>
  api<Perfil>('/perfil/email/confirmar', { metodo: 'POST', corpo: { email, codigo } });
export const removerFoto = () => api<{ tem_foto: boolean; foto_versao: null }>('/perfil/foto', { metodo: 'DELETE' });

export function enviarFoto(arquivo: File) {
  const formulario = new FormData();
  formulario.append('foto', arquivo);
  return enviarFormulario<{ tem_foto: boolean; foto_versao: string }>('/perfil/foto', formulario);
}

export function urlFoto(versao: string): string {
  return `/api/v1/perfil/foto?v=${encodeURIComponent(versao)}`;
}

/** Step-up: volta ao Login APM pedindo a senha de novo e retorna ao perfil. */
export function urlReautenticacao(): string {
  return `/auth/login?reauth=1&next=${encodeURIComponent('/area/perfil')}`;
}
