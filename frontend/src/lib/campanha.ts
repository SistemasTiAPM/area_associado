/**
 * Parâmetros de campanha (TI-11; spec v2 §12.3 "todo link com UTM e código do
 * gatilho"). Lidos UMA vez no boot (`capturarCampanha()` em main.tsx), validados
 * contra um catálogo fechado, removidos da URL (`history.replaceState`) e
 * guardados só em memória de módulo até serem anexados ao próximo `pagina_ver`
 * por `analytics.ts`.
 *
 * Regras de segurança:
 * - os valores NUNCA viram destino de navegação nem são renderizados;
 * - nada vai para localStorage/sessionStorage (RNF-21): recarregar a página
 *   sem a query perde a campanha, e tudo bem;
 * - o servidor (`app/uso.py`) valida de novo com o mesmo catálogo.
 */

export interface Campanha {
  origem?: string;
  meio?: string;
  campanha?: string;
  gatilho?: string;
}

/** utm_*: letras, dígitos, `-` e `_`, até 32; comparado em minúsculas (mesmo regex de app/uso.py). */
const RE_UTM = /^[a-z0-9][a-z0-9_-]{0,31}$/;
/** Gatilho da régua de comunicação: A01..A20 (spec §12.2). */
const RE_GATILHO = /^A(0[1-9]|1[0-9]|20)$/;

const PARAMETROS: ReadonlyArray<readonly [chaveQuery: string, chave: keyof Campanha]> = [
  ['utm_source', 'origem'],
  ['utm_medium', 'meio'],
  ['utm_campaign', 'campanha'],
  ['g', 'gatilho'],
];

let capturada: Campanha | null = null;
let jaCapturou = false;

function validarUtm(bruto: string | null): string | undefined {
  if (bruto === null) return undefined;
  const valor = bruto.trim().toLowerCase();
  return RE_UTM.test(valor) ? valor : undefined;
}

function validarGatilho(bruto: string | null): string | undefined {
  if (bruto === null) return undefined;
  const valor = bruto.trim().toUpperCase();
  return RE_GATILHO.test(valor) ? valor : undefined;
}

/** Extrai e valida a campanha de uma query; exportada para teste. Sem efeito colateral. */
export function lerCampanha(search: string): Campanha | null {
  let parametros: URLSearchParams;
  try {
    parametros = new URLSearchParams(search);
  } catch {
    return null;
  }
  const resultado: Campanha = {};
  for (const [chaveQuery, chave] of PARAMETROS) {
    const valor = chave === 'gatilho' ? validarGatilho(parametros.get(chaveQuery)) : validarUtm(parametros.get(chaveQuery));
    if (valor !== undefined) resultado[chave] = valor;
  }
  return Object.keys(resultado).length > 0 ? resultado : null;
}

/** Remove da URL os parâmetros de campanha (válidos ou não), sem recarregar nem navegar. */
function limparUrl(): void {
  try {
    const url = new URL(window.location.href);
    let mudou = false;
    for (const [chaveQuery] of PARAMETROS) {
      if (url.searchParams.has(chaveQuery)) {
        url.searchParams.delete(chaveQuery);
        mudou = true;
      }
    }
    if (mudou) window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
  } catch {
    // URL ou history indisponíveis (ambiente sem janela): nada a limpar.
  }
}

/**
 * Lê a campanha da URL atual uma única vez por carga da página. Chamadas
 * seguintes não releem a URL (o replaceState já a limpou).
 */
export function capturarCampanha(): Campanha | null {
  if (jaCapturou) return capturada;
  jaCapturou = true;
  capturada = typeof window === 'undefined' ? null : lerCampanha(window.location.search);
  limparUrl();
  return capturada;
}

/** Entrega a campanha capturada UMA vez (para o próximo `pagina_ver`) e a esquece. */
export function consumirCampanha(): Campanha | null {
  const atual = capturarCampanha();
  capturada = null;
  return atual;
}

/** Só para testes. */
export function _reiniciarCampanha(): void {
  capturada = null;
  jaCapturou = false;
}
