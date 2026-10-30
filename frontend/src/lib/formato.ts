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

const dataHora = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: FUSO_EXIBICAO,
});

/** "26/09/2026 às 14:05" no fuso de exibição (RNF-15). */
export function dataHoraBR(d: Date): string {
  const partes = Object.fromEntries(dataHora.formatToParts(d).map((p) => [p.type, p.value]));
  return `${partes.day}/${partes.month}/${partes.year} às ${partes.hour}:${partes.minute}`;
}

/** Data ISO (data-hora ou AAAA-MM-DD) da API → `Date`, ou `null` se inválida. AAAA-MM-DD vira meio-dia UTC (o dia não muda no fuso). */
export function dataDaApi(valor: string | null | undefined): Date | null {
  if (!valor) return null;
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(valor) ? `${valor}T12:00:00Z` : valor);
  return Number.isFinite(d.getTime()) ? d : null;
}
