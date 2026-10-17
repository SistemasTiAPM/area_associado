import { describe, expect, it } from 'vitest';
import { dataBR, diaDoMes, mesCurto, moeda } from './formato';

const NBSP = ' ';

describe('formatos pt-BR (RNF-14/15)', () => {
  it('moeda sem centavos quando inteira, com ponto de milhar', () => {
    expect(moeda(1240)).toBe(`R$${NBSP}1.240`);
    expect(moeda(2480)).toBe(`R$${NBSP}2.480`);
    expect(moeda(12.5)).toBe(`R$${NBSP}12,50`);
    expect(moeda(Number.NaN)).toBe('—');
  });

  it('mês em 3 letras maiúsculas sem ponto, no fuso de São Paulo', () => {
    // 26/09/2026 01:00 UTC ainda é 25/09 em São Paulo: o fuso de exibição manda.
    expect(mesCurto(new Date('2026-09-26T12:00:00Z'))).toBe('SET');
    expect(mesCurto(new Date('2026-07-12T12:00:00Z'))).toBe('JUL');
    expect(diaDoMes(new Date('2026-09-26T01:00:00Z'))).toBe('25');
    expect(dataBR(new Date('2026-09-26T12:00:00Z'))).toBe('26/09/2026');
  });
});
