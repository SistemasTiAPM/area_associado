import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Tabs } from './Tabs';

const ABAS = [
  { id: '2026', rotulo: '2026', conteudo: <p>Extrato de 2026</p> },
  { id: '2025', rotulo: '2025', conteudo: <p>Extrato de 2025</p> },
  { id: 'anteriores', rotulo: 'Anteriores', conteudo: <p>Antes de 2025</p> },
];

describe('Tabs (APG, ativação automática)', () => {
  it('tablist rotulada, só a aba ativa na ordem de Tab, painel ligado à aba', () => {
    render(<Tabs abas={ABAS} rotulo="Período do extrato" />);
    expect(screen.getByRole('tablist', { name: 'Período do extrato' })).toBeInTheDocument();
    const abas = screen.getAllByRole('tab');
    expect(abas.map((a) => a.getAttribute('aria-selected'))).toEqual(['true', 'false', 'false']);
    expect(abas.map((a) => a.tabIndex)).toEqual([0, -1, -1]);
    const painel = screen.getByRole('tabpanel', { name: '2026' });
    expect(painel.id).toBe(abas[0]?.getAttribute('aria-controls'));
    expect(painel).toHaveAttribute('tabindex', '0');
    expect(screen.getByText('Extrato de 2026')).toBeInTheDocument();
    expect(screen.queryByText('Extrato de 2025')).toBeNull();
  });

  it('clique e setas trocam a aba e o painel; Home/End vão às pontas', async () => {
    const usuario = userEvent.setup();
    const aoMudar = vi.fn();
    render(<Tabs abas={ABAS} rotulo="Período" abaInicial="2025" aoMudar={aoMudar} />);
    expect(screen.getByText('Extrato de 2025')).toBeInTheDocument();
    await usuario.click(screen.getByRole('tab', { name: 'Anteriores' }));
    expect(screen.getByText('Antes de 2025')).toBeInTheDocument();
    expect(aoMudar).toHaveBeenLastCalledWith('anteriores');
    await usuario.keyboard('{ArrowRight}'); // circular: volta à primeira
    expect(screen.getByRole('tab', { name: '2026' })).toHaveFocus();
    expect(screen.getByText('Extrato de 2026')).toBeInTheDocument();
    await usuario.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Anteriores' })).toHaveFocus();
    await usuario.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: '2026' })).toHaveAttribute('aria-selected', 'true');
    await usuario.keyboard('{End}');
    expect(screen.getByRole('tab', { name: 'Anteriores' })).toHaveAttribute('aria-selected', 'true');
  });

  it('modo controlado obedece à prop `ativa`', async () => {
    const usuario = userEvent.setup();
    function Controlado() {
      const [ativa, setAtiva] = useState('2026');
      return <Tabs abas={ABAS} rotulo="Período" ativa={ativa} aoMudar={(id) => setAtiva(id === 'anteriores' ? '2025' : id)} />;
    }
    render(<Controlado />);
    await usuario.click(screen.getByRole('tab', { name: 'Anteriores' }));
    expect(screen.getByRole('tab', { name: '2025' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Extrato de 2025')).toBeInTheDocument();
  });

  it('sem abas não renderiza nada', () => {
    const { container } = render(<Tabs abas={[]} rotulo="Vazio" />);
    expect(container).toBeEmptyDOMElement();
  });
});
