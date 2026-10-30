import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Skeleton } from './Skeleton';

describe('Skeleton', () => {
  it('é role=status ocupado, com rótulo só para leitor de tela e formas decorativas', () => {
    const { container } = render(<Skeleton variante="card" rotulo="Carregando benefícios…" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveTextContent('Carregando benefícios…');
    expect(container.querySelector('.skeleton__formas')).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelectorAll('.skeleton__forma')).toHaveLength(3);
  });

  it('texto e lista respeitam a quantidade, dentro de 1..12', () => {
    const { container, rerender } = render(<Skeleton variante="texto" quantidade={5} />);
    expect(container.querySelectorAll('.skeleton__forma--linha')).toHaveLength(5);
    expect(container.querySelectorAll('.skeleton__forma--curta')).toHaveLength(1);
    rerender(<Skeleton variante="lista" quantidade={40} />);
    expect(container.querySelectorAll('.skeleton__item')).toHaveLength(12);
    rerender(<Skeleton variante="lista" quantidade={0} />);
    expect(container.querySelectorAll('.skeleton__item')).toHaveLength(1);
  });

  it('rótulo padrão e classe por variante', () => {
    const { container } = render(<Skeleton />);
    expect(screen.getByRole('status')).toHaveTextContent('Carregando…');
    expect(container.firstChild).toHaveClass('skeleton--bloco');
  });
});
