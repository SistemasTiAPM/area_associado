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
  /** Linha editorial sob o título no cabeçalho (texto do mockup da agência, ADR-0017). */
  chamada?: string;
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
  { id: 'home', caminho: '', titulo: 'Início', chamada: 'O que faz sentido para você hoje?', icone: 'inicio', rotuloInferior: 'Início' },
  { id: 'ben', caminho: 'beneficios', titulo: 'Meus benefícios', chamada: 'Valor que acompanha sua vida dentro e fora do consultório.', icone: 'sacola', rotuloInferior: 'Benefícios' },
  { id: 'clube', caminho: 'clube', titulo: 'Clube de vantagens', chamada: 'Descontos e cashback para usar toda semana.', icone: 'presente', rotuloInferior: 'Clube' },
  { id: 'news', caminho: 'noticias', titulo: 'Notícias e ciência', chamada: 'Conhecimento que conversa com a sua prática.', icone: 'jornal', rotuloInferior: 'Notícias' },
  { id: 'fatura', caminho: 'fatura', titulo: 'Fatura de valor', chamada: 'O valor que a sua associação devolve para você.', icone: 'recibo', flag: 'fatura_valor' },
  { id: 'com', caminho: 'comunidade', titulo: 'Comunidade', chamada: 'Sua comunidade profissional, com propósito.', icone: 'pessoas' },
  { id: 'evt', caminho: 'eventos', titulo: 'Congresso e eventos', chamada: 'Onde a profissão se encontra, aprende e avança junto.', icone: 'calendario' },
  { id: 'card', caminho: 'carteirinha', titulo: 'Carteirinha digital', chamada: 'Sua identificação APM, sempre no bolso.', icone: 'cartao', rotuloInferior: 'Carteirinha' },
  { id: 'perfil', caminho: 'perfil', titulo: 'Meu perfil', chamada: 'Seus dados de contato e de cadastro na APM.', icone: 'usuario' },
  { id: 'solicitacoes', caminho: 'solicitacoes', titulo: 'Minhas solicitações', chamada: 'Acompanhe cada protocolo em um só lugar.', icone: 'caixa' },
  {
    id: 'onb',
    caminho: 'onboarding',
    titulo: 'Onboarding acadêmico',
    chamada: 'Primeiros passos na sua associação.',
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
