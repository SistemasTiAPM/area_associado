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
  /**
   * Aceita um segmento a mais (`/beneficios/{slug}`, `/solicitacoes/{uuid}`, `/eventos/{id}`).
   * `publica`: o identificador é de catálogo (slug) e pode ir ao analytics, truncado.
   * `pessoal`: o identificador aponta para um dado do associado (protocolo) e é omitido
   * do analytics (regra 17: nada pessoal em `evento_uso`).
   */
  subRota?: 'publica' | 'pessoal';
}

export const ROTAS: readonly Rota[] = [
  { id: 'home', caminho: '', titulo: 'Início', chamada: 'O que faz sentido para você hoje?', icone: 'inicio', rotuloInferior: 'Início' },
  { id: 'ben', caminho: 'beneficios', titulo: 'Meus benefícios', chamada: 'Valor que acompanha sua vida dentro e fora do consultório.', icone: 'sacola', rotuloInferior: 'Benefícios', subRota: 'publica' },
  { id: 'clube', caminho: 'clube', titulo: 'Clube de vantagens', chamada: 'Descontos e vantagens para usar toda semana.', icone: 'presente', rotuloInferior: 'Clube' },
  { id: 'news', caminho: 'noticias', titulo: 'Notícias e ciência', chamada: 'Conhecimento que conversa com a sua prática.', icone: 'jornal', rotuloInferior: 'Notícias' },
  // Título "Meu valor" (spec v2 §3.1); a chave da flag e o caminho ficam até a Onda 2 (DEC-24).
  { id: 'fatura', caminho: 'fatura', titulo: 'Meu valor', chamada: 'O valor que a sua associação devolve para você.', icone: 'recibo', flag: 'fatura_valor' },
  { id: 'com', caminho: 'comunidade', titulo: 'Comunidade', chamada: 'Sua comunidade profissional, com propósito.', icone: 'pessoas' },
  { id: 'evt', caminho: 'eventos', titulo: 'Congresso e eventos', chamada: 'Onde a profissão se encontra, aprende e avança junto.', icone: 'calendario', subRota: 'publica' },
  { id: 'card', caminho: 'carteirinha', titulo: 'Carteirinha digital', chamada: 'Sua identificação APM, sempre no bolso.', icone: 'cartao', rotuloInferior: 'Carteirinha' },
  { id: 'perfil', caminho: 'perfil', titulo: 'Meu perfil', chamada: 'Seus dados de contato e de cadastro na APM.', icone: 'usuario' },
  { id: 'solicitacoes', caminho: 'solicitacoes', titulo: 'Minhas solicitações', chamada: 'Acompanhe cada protocolo em um só lugar.', icone: 'caixa', subRota: 'pessoal' },
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

/** Segmento de sub-rota aceito: slug, uuid ou id numérico; nada de barra, ponto ou espaço. */
const SEGMENTO_SUB_ROTA = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const TAMANHO_ID_ANALYTICS = 32;
export const MARCADOR_ID_OMITIDO = '_';

export function rotaVisivel(rota: Rota, sessao: Sessao): boolean {
  if (rota.flag && !sessao.flags[rota.flag]) return false;
  if (rota.somenteTipo && sessao.associado.tipo !== rota.somenteTipo) return false;
  return true;
}

export function destino(rota: Rota): string {
  return `/${rota.caminho}`;
}

export interface CaminhoResolvido {
  rota: Rota;
  /** Segundo segmento (`{slug}`, `{uuid}`, `{id}`) quando a rota aceita sub-rota. */
  parametro?: string;
}

/**
 * Resolve um pathname do React Router (já sem o basename) para a rota e o
 * parâmetro de sub-rota. Casa por prefixo só nas rotas com `subRota` e só com
 * um segmento adicional bem formado; o resto é "página não encontrada".
 */
export function resolverCaminho(pathname: string): CaminhoResolvido | undefined {
  const limpo = pathname.replace(/\/+$/, '').replace(/^\/+/, '');
  const exata = ROTAS.find((r) => r.caminho === limpo);
  if (exata) return { rota: exata };
  const corte = limpo.indexOf('/');
  if (corte <= 0) return undefined;
  const primeiro = limpo.slice(0, corte);
  const resto = limpo.slice(corte + 1);
  if (!SEGMENTO_SUB_ROTA.test(resto)) return undefined;
  const rota = ROTAS.find((r) => r.subRota !== undefined && r.caminho === primeiro);
  return rota ? { rota, parametro: resto } : undefined;
}

/** Rota correspondente a um pathname (atalho de `resolverCaminho`). */
export function rotaDoCaminho(pathname: string): Rota | undefined {
  return resolverCaminho(pathname)?.rota;
}

/**
 * Identificador da rota para `pagina_ver` (`entidade_id`, ≤ 64 caracteres):
 * `/area/{caminho}` e, em sub-rota, o parâmetro truncado quando é de catálogo
 * ou substituído por `_` quando aponta para um dado do associado.
 */
export function caminhoParaAnalytics(pathname: string): string {
  const resolvido = resolverCaminho(pathname);
  if (!resolvido) {
    const limpo = pathname.replace(/\/+$/, '').replace(/^\/+/, '');
    return `/area${limpo ? `/${limpo}` : ''}`.slice(0, 64);
  }
  const base = `/area${resolvido.rota.caminho ? `/${resolvido.rota.caminho}` : ''}`;
  if (resolvido.parametro === undefined) return base;
  const id =
    resolvido.rota.subRota === 'pessoal' ? MARCADOR_ID_OMITIDO : resolvido.parametro.slice(0, TAMANHO_ID_ANALYTICS);
  return `${base}/${id}`;
}
