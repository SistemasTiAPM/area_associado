import type { NomeIcone } from './components/Icon';
import type { ChaveFlag, Sessao } from './api/tipos';

/**
 * Mapa de rotas (REQUISITOS §3.0; ADR-0001: URL real, sem localStorage).
 * `caminho` é relativo ao basename `/area` do React Router.
 * Ordem = ordem da sidebar (RF-SH-02).
 */
export interface Rota {
  id: string;
  caminho: string;
  titulo: string;
  icone: NomeIcone;
  /** Rótulo na bottom-nav mobile; ausente = não aparece lá. */
  rotuloInferior?: string;
  /** Rota inteira some (menu e URL) com a flag desligada (RF-SH-11). */
  flag?: ChaveFlag;
  /** Só para este tipo de associado (rótulo do CRM). */
  somenteTipo?: string;
  /** Separada visualmente na sidebar (spec: "Onboarding acadêmico"). */
  separada?: boolean;
}

export const ROTAS: readonly Rota[] = [
  { id: 'home', caminho: '', titulo: 'Início', icone: 'inicio', rotuloInferior: 'Início' },
  { id: 'ben', caminho: 'beneficios', titulo: 'Meus benefícios', icone: 'sacola', rotuloInferior: 'Benefícios' },
  { id: 'clube', caminho: 'clube', titulo: 'Clube de vantagens', icone: 'presente', rotuloInferior: 'Clube' },
  { id: 'news', caminho: 'noticias', titulo: 'Notícias e ciência', icone: 'jornal', rotuloInferior: 'Notícias' },
  { id: 'fatura', caminho: 'fatura', titulo: 'Fatura de valor', icone: 'recibo', flag: 'fatura_valor' },
  { id: 'com', caminho: 'comunidade', titulo: 'Comunidade', icone: 'pessoas' },
  { id: 'evt', caminho: 'eventos', titulo: 'Congresso e eventos', icone: 'calendario' },
  { id: 'card', caminho: 'carteirinha', titulo: 'Carteirinha digital', icone: 'cartao', rotuloInferior: 'Carteirinha' },
  { id: 'perfil', caminho: 'perfil', titulo: 'Meu perfil', icone: 'usuario' },
  { id: 'solicitacoes', caminho: 'solicitacoes', titulo: 'Minhas solicitações', icone: 'caixa' },
  {
    id: 'onb',
    caminho: 'onboarding',
    titulo: 'Onboarding acadêmico',
    icone: 'estrela',
    somenteTipo: 'Acadêmico',
    separada: true,
  },
];

export const ORDEM_INFERIOR: readonly string[] = ['home', 'ben', 'clube', 'news', 'card'];

export const TITULO_NAO_ENCONTRADA = 'Página não encontrada';

export function rotaVisivel(rota: Rota, sessao: Sessao): boolean {
  if (rota.flag && !sessao.flags[rota.flag]) return false;
  if (rota.somenteTipo && sessao.associado.tipo !== rota.somenteTipo) return false;
  return true;
}

export function destino(rota: Rota): string {
  return `/${rota.caminho}`;
}

/** Rota correspondente a um pathname do React Router (já sem o basename). */
export function rotaDoCaminho(pathname: string): Rota | undefined {
  const limpo = pathname.replace(/\/+$/, '').replace(/^\//, '');
  return ROTAS.find((r) => r.caminho === limpo);
}
