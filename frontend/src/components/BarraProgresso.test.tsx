import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BarraProgresso, fracaoProgresso } from './BarraProgresso';

describe('BarraProgresso (CSSOM, ADR-0013)', () => {
  it('expõe role=progressbar com min/max/now e o texto visível', () => {
    render(<BarraProgresso valor={3} max={8} rotulo="Trilha de ativação" />);
    const barra = screen.getByRole('progressbar', { name: 'Trilha de ativação' });
    expect(barra).toHaveAttribute('aria-valuemin', '0');
    expect(barra).toHaveAttribute('aria-valuemax', '8');
    expect(barra).toHaveAttribute('aria-valuenow', '3');
    expect(barra).toHaveAttribute('aria-valuetext', '3 de 8');
    expect(screen.getByText('3 de 8')).toBeInTheDocument();
  });

  it('define a fração via custom property, sem atributo style inline no JSX', () => {
    const { rerender } = render(<BarraProgresso valor={25} rotulo="Perfil" />);
    const barra = screen.getByRole('progressbar');
    expect(barra.style.getPropertyValue('--progresso')).toBe('0.2500');
    expect(barra.getAttribute('style') ?? '').toMatch(/^--progresso: 0\.2500;?$/); // só a custom property, via CSSOM
    rerender(<BarraProgresso valor={150} rotulo="Perfil" />);
    expect(barra.style.getPropertyValue('--progresso')).toBe('1.0000');
    expect(barra).toHaveAttribute('aria-valuenow', '100');
  });

  it('limita a 0..max e tolera valores inválidos', () => {
    expect(fracaoProgresso(-5, 10)).toBe(0);
    expect(fracaoProgresso(15, 10)).toBe(1);
    expect(fracaoProgresso(5, 0)).toBe(0);
    expect(fracaoProgresso(Number.NaN, 10)).toBe(0);
    expect(fracaoProgresso(2, 8)).toBe(0.25);
  });

  it('texto personalizado e texto oculto', () => {
    const { rerender } = render(<BarraProgresso valor={2} max={4} rotulo="Trilha" texto="2 de 4 passos concluídos" />);
    expect(screen.getByText('2 de 4 passos concluídos')).toBeInTheDocument();
    rerender(<BarraProgresso valor={2} max={4} rotulo="Trilha" texto={null} />);
    expect(screen.queryByText(/de 4/)).toBeNull();
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuetext');
  });
});
