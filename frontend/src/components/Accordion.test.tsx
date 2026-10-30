import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Accordion } from './Accordion';

const ITENS = [
  { id: 'regras', titulo: 'Regras de uso', conteudo: <p>Carência de 1 mês.</p> },
  { id: 'como', titulo: 'Como funciona', conteudo: <p>Nós cuidamos do envio ao parceiro.</p> },
  { id: 'faq', titulo: 'Perguntas frequentes', conteudo: <p>Vale para dependentes.</p> },
];

describe('Accordion (APG)', () => {
  it('cabeçalhos são botões com aria-expanded e controlam regiões rotuladas', () => {
    render(<Accordion itens={ITENS} abertosIniciais={['regras']} />);
    const botao = screen.getByRole('button', { name: 'Regras de uso' });
    expect(botao).toHaveAttribute('aria-expanded', 'true');
    const regiao = screen.getByRole('region', { name: 'Regras de uso' });
    expect(regiao.id).toBe(botao.getAttribute('aria-controls'));
    expect(screen.getByText('Carência de 1 mês.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Como funciona' })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Nós cuidamos do envio ao parceiro.')).not.toBeVisible();
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(3);
  });

  it('um por vez: abrir o segundo fecha o primeiro; clicar de novo fecha', async () => {
    const usuario = userEvent.setup();
    const aoAlternar = vi.fn();
    render(<Accordion itens={ITENS} abertosIniciais={['regras']} aoAlternar={aoAlternar} />);
    await usuario.click(screen.getByRole('button', { name: 'Como funciona' }));
    expect(screen.getByRole('button', { name: 'Como funciona' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Regras de uso' })).toHaveAttribute('aria-expanded', 'false');
    expect(aoAlternar).toHaveBeenLastCalledWith('como', true);
    await usuario.click(screen.getByRole('button', { name: 'Como funciona' }));
    expect(screen.getByRole('button', { name: 'Como funciona' })).toHaveAttribute('aria-expanded', 'false');
    expect(aoAlternar).toHaveBeenLastCalledWith('como', false);
  });

  it('permitirMultiplos mantém os dois abertos', async () => {
    const usuario = userEvent.setup();
    render(<Accordion itens={ITENS} permitirMultiplos abertosIniciais={['regras']} />);
    await usuario.click(screen.getByRole('button', { name: 'Perguntas frequentes' }));
    expect(screen.getByRole('button', { name: 'Regras de uso' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Perguntas frequentes' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('setas, Home e End movem o foco entre cabeçalhos (circular)', async () => {
    const usuario = userEvent.setup();
    render(<Accordion itens={ITENS} nivel={2} />);
    const [a, b, c] = screen.getAllByRole('button');
    a?.focus();
    await usuario.keyboard('{ArrowDown}');
    expect(b).toHaveFocus();
    await usuario.keyboard('{End}');
    expect(c).toHaveFocus();
    await usuario.keyboard('{ArrowDown}');
    expect(a).toHaveFocus();
    await usuario.keyboard('{ArrowUp}');
    expect(c).toHaveFocus();
    await usuario.keyboard('{Home}');
    expect(a).toHaveFocus();
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(3);
  });
});
