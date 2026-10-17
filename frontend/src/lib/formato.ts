/** Formatos pt-BR (RNF-14) e fuso de exibição (RNF-15). */

export const FUSO_EXIBICAO = 'America/Sao_Paulo';

const moedaInteira = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});
const moedaCentavos = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

/** "R$ 1.240" quando inteiro; "R$ 12,50" quando há centavos. */
export function moeda(valor: number): string {
  if (!Number.isFinite(valor)) return '—';
  return Number.isInteger(valor) ? moedaInteira.format(valor) : moedaCentavos.format(valor);
}

const mes = new Intl.DateTimeFormat('pt-BR', { month: 'short', timeZone: FUSO_EXIBICAO });
const dia = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', timeZone: FUSO_EXIBICAO });
const data = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: FUSO_EXIBICAO });

/** "SET", "OUT", "JUL" — blocos de data da spec. */
export function mesCurto(d: Date): string {
  return mes.format(d).replace('.', '').slice(0, 3).toUpperCase();
}

export function diaDoMes(d: Date): string {
  return dia.format(d);
}

/** "26/09/2026". */
export function dataBR(d: Date): string {
  return data.format(d);
}
