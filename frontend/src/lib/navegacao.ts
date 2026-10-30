import { useCallback } from 'react';
import { useNavigate, type NavigateFunction, type NavigateOptions } from 'react-router';
import { resolverCaminho } from '../rotas';

/**
 * Navegação interna segura (TI-10 / P-40; DEC-28). Todo destino de navegação que
 * não seja literal passa por `destinoSeguro()`, que só aceita caminho relativo ao
 * basename `/area` de uma rota conhecida (`rotas.ts`):
 *
 * - começa com uma única `/` (nada de `//host`, esquema `x:` ou caminho relativo);
 * - sem `\` (o navegador trata `/\host` como `//host`: GHSA-wrjc-x8rr-h8h6), sem
 *   caractere de controle ou espaço, sem `//`, sem `%` (nada codificado) e sem
 *   segmento `.`/`..` no caminho;
 * - o caminho resolve para uma rota de `ROTAS` (com sub-rota bem formada);
 * - consulta e fragmento só com caracteres de URL comuns, sem controle.
 *
 * O ESLint proíbe `useNavigate` e `<Link to={variável}>` fora deste módulo, de
 * `components/LinkInterno.tsx` e do shell (`eslint.config.js`).
 */

const TAMANHO_MAX = 512;
/** Controle C0, espaço, DEL, C1 e separadores de linha Unicode: nunca num destino cru. */
function temControle(texto: string): boolean {
  for (let i = 0; i < texto.length; i += 1) {
    const c = texto.charCodeAt(i);
    if (c <= 0x20 || (c >= 0x7f && c <= 0x9f) || c === 0x2028 || c === 0x2029) return true;
  }
  return false;
}
const CAMINHO = /^\/[A-Za-z0-9/_-]*$/;
const CONSULTA = /^[A-Za-z0-9\-._~%!$&'()*+,;=:@/?]*$/;

/**
 * Devolve o destino normalizado (`/solicitacoes/abc?x=1`) ou `null` quando ele não
 * é uma rota interna conhecida. Puro e sem efeito colateral.
 */
export function destinoSeguro(bruto: unknown): string | null {
  if (typeof bruto !== 'string' || bruto.length === 0 || bruto.length > TAMANHO_MAX) return null;
  if (temControle(bruto) || bruto.includes('\\')) return null;
  if (!bruto.startsWith('/') || bruto.startsWith('//')) return null;

  const fimCaminho = bruto.search(/[?#]/);
  const caminho = fimCaminho === -1 ? bruto : bruto.slice(0, fimCaminho);
  const resto = fimCaminho === -1 ? '' : bruto.slice(fimCaminho);

  // Caminho só com caracteres de rota: sem `%`, então nada codificado (`%5C`, `%2F`) passa.
  if (!CAMINHO.test(caminho) || caminho.includes('//')) return null;
  if (caminho.split('/').some((segmento) => segmento === '.' || segmento === '..')) return null;
  if (resolverCaminho(caminho) === undefined) return null;

  if (resto) {
    const corte = resto.indexOf('#');
    const consulta = corte === -1 ? resto : resto.slice(0, corte);
    const fragmento = corte === -1 ? '' : resto.slice(corte + 1);
    if (consulta && (!consulta.startsWith('?') || !CONSULTA.test(consulta.slice(1)))) return null;
    if (fragmento && !CONSULTA.test(fragmento)) return null;
  }
  return bruto;
}

/**
 * Navega só para destino aprovado por `destinoSeguro`; recusa sem navegar (e
 * avisa no console, erro de programação) quando não é. Devolve se navegou.
 */
export function navegarSeguro(navegar: NavigateFunction, destino: unknown, opcoes?: NavigateOptions): boolean {
  const seguro = destinoSeguro(destino);
  if (seguro === null) {
    console.error('Navegação recusada: destino fora das rotas da Minha APM.');
    return false;
  }
  void navegar(seguro, opcoes);
  return true;
}

/** Hook de navegação programática: `const navegar = useNavegarSeguro(); navegar('/solicitacoes/' + id)`. */
export function useNavegarSeguro(): (destino: unknown, opcoes?: NavigateOptions) => boolean {
  const navegar = useNavigate();
  return useCallback((destino: unknown, opcoes?: NavigateOptions) => navegarSeguro(navegar, destino, opcoes), [navegar]);
}
