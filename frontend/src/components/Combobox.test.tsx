import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Combobox, type OpcaoCombobox } from './Combobox';

const TODAS: OpcaoCombobox[] = [
  { id: 'b1', rotulo: 'Escola de idiomas', tipo: 'Benefício' },
  { id: 'e1', rotulo: 'Congresso Paulista', tipo: 'Evento' },
  { id: 'b2', rotulo: 'Hotel Fazenda APM', tipo: 'Benefício' },
];

function Harness({ aoEscolher = vi.fn() }: { aoEscolher?: (o: OpcaoCombobox) => void }) {
  const [valor, setValor] = useState('');
  const opcoes = valor ? TODAS.filter((o) => o.rotulo.toLowerCase().includes(valor.toLowerCase())) : [];
  return <Combobox id="busca" rotulo="Buscar" valor={valor} aoMudar={setValor} opcoes={opcoes} aoEscolher={aoEscolher} />;
}

describe('Combobox (APG, autocomplete=list)', () => {
  it('fechado até digitar; aberto expõe listbox, opções e contagem em aria-live', async () => {
    const usuario = userEvent.setup();
    render(<Harness />);
    const campo = screen.getByRole('combobox', { name: 'Buscar' });
    expect(campo).toHaveAttribute('aria-expanded', 'false');
    expect(campo).toHaveAttribute('aria-autocomplete', 'list');
    expect(screen.queryByRole('listbox')).toBeNull();
    await usuario.type(campo, 'a');
    expect(campo).toHaveAttribute('aria-expanded', 'true');
    const lista = screen.getByRole('listbox', { name: 'Sugestões para Buscar' });
    expect(lista.id).toBe(campo.getAttribute('aria-controls'));
    expect(within(lista).getAllByRole('option')).toHaveLength(3);
    expect(screen.getByRole('status')).toHaveTextContent('3 sugestões');
    await usuario.type(campo, 'bc');
    expect(screen.getByRole('status')).toHaveTextContent('Nenhuma sugestão');
  });

  it('setas movem aria-activedescendant, Enter escolhe, Esc fecha e depois limpa', async () => {
    const usuario = userEvent.setup();
    const aoEscolher = vi.fn();
    render(<Harness aoEscolher={aoEscolher} />);
    const campo = screen.getByRole('combobox', { name: 'Buscar' });
    await usuario.type(campo, 'o');
    expect(campo).not.toHaveAttribute('aria-activedescendant');
    await usuario.keyboard('{ArrowDown}');
    const opcoes = screen.getAllByRole('option');
    expect(campo).toHaveAttribute('aria-activedescendant', opcoes[0]?.id);
    expect(opcoes[0]).toHaveAttribute('aria-selected', 'true');
    await usuario.keyboard('{ArrowDown}{ArrowDown}');
    expect(campo).toHaveAttribute('aria-activedescendant', opcoes[2]?.id);
    await usuario.keyboard('{ArrowDown}'); // circular
    expect(campo).toHaveAttribute('aria-activedescendant', opcoes[0]?.id);
    await usuario.keyboard('{End}');
    await usuario.keyboard('{Enter}');
    expect(aoEscolher).toHaveBeenCalledWith(expect.objectContaining({ id: 'b2' }));
    expect(campo).toHaveAttribute('aria-expanded', 'false');
    await usuario.keyboard('{ArrowDown}'); // reabre
    expect(campo).toHaveAttribute('aria-expanded', 'true');
    await usuario.keyboard('{Escape}');
    expect(campo).toHaveAttribute('aria-expanded', 'false');
    expect(campo).toHaveValue('o');
    await usuario.keyboard('{Escape}');
    expect(campo).toHaveValue('');
  });

  it('clique na opção escolhe; botão limpar zera e devolve o foco ao campo', async () => {
    const usuario = userEvent.setup();
    const aoEscolher = vi.fn();
    render(<Harness aoEscolher={aoEscolher} />);
    const campo = screen.getByRole('combobox', { name: 'Buscar' });
    await usuario.type(campo, 'Congresso');
    await usuario.click(screen.getByRole('option', { name: /Congresso Paulista/ }));
    expect(aoEscolher).toHaveBeenCalledWith(expect.objectContaining({ id: 'e1' }));
    await usuario.click(screen.getByRole('button', { name: 'Limpar busca' }));
    expect(campo).toHaveValue('');
    expect(campo).toHaveFocus();
    expect(screen.queryByRole('button', { name: 'Limpar busca' })).toBeNull();
  });

  it('Enter sem opção realçada não escolhe nada (deixa o formulário seguir)', async () => {
    const usuario = userEvent.setup();
    const aoEscolher = vi.fn();
    render(<Harness aoEscolher={aoEscolher} />);
    await usuario.type(screen.getByRole('combobox'), 'o{Enter}');
    expect(aoEscolher).not.toHaveBeenCalled();
  });
});
