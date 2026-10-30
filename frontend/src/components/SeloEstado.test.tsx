import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ESTADOS_SELO, SeloEstado, textoSelo } from './SeloEstado';

describe('SeloEstado (spec v2 §8.1 e §3.2)', () => {
  it.each(ESTADOS_SELO)('%s sempre tem texto visível e ícone (nunca só cor)', (estado) => {
    const { container } = render(<SeloEstado estado={estado} />);
    const selo = container.querySelector('.selo-estado');
    expect(selo).toHaveClass(`selo-estado--${estado}`);
    expect(selo?.textContent?.trim().length).toBeGreaterThan(0);
    expect(selo?.querySelector('svg.icone')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByText(textoSelo(estado))).toBeInTheDocument();
  });

  it('cobre os seis estados de elegibilidade mais novo e patrocinado', () => {
    expect(ESTADOS_SELO).toHaveLength(8);
    expect(ESTADOS_SELO).toEqual(expect.arrayContaining(['disponivel', 'ativo', 'libera_em', 'exclusivo', 'suspenso', 'indisponivel_regiao']));
  });

  it('"libera em" mostra a data em pt-BR e cai para "após a carência" sem data', () => {
    render(<SeloEstado estado="libera_em" liberaEm={new Date('2026-12-15T12:00:00Z')} />);
    expect(screen.getByText('Libera em 15/12/2026')).toBeInTheDocument();
    expect(textoSelo('libera_em')).toBe('Libera após a carência');
    expect(textoSelo('libera_em', { liberaEm: new Date('inválida') })).toBe('Libera após a carência');
  });

  it('exclusivo usa a categoria da spec por padrão e aceita outra', () => {
    expect(textoSelo('exclusivo')).toBe('Exclusivo para associado efetivo');
    expect(textoSelo('exclusivo', { categoria: 'aspirante' })).toBe('Exclusivo para aspirante');
    expect(textoSelo('exclusivo', { categoria: '   ' })).toBe('Exclusivo para associado efetivo');
  });

  it('voz §3.3: nenhum texto com exclamação nem "pagante"', () => {
    for (const estado of ESTADOS_SELO) {
      const texto = textoSelo(estado);
      expect(texto).not.toMatch(/!/);
      expect(texto.toLowerCase()).not.toContain('pagante');
    }
  });
});
