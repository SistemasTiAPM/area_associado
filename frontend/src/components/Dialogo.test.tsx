import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Dialogo } from './Dialogo';

function Harness({ destrutivo = false, aoConfirmar = () => {} }: { destrutivo?: boolean; aoConfirmar?: () => void }) {
  const [aberto, setAberto] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setAberto(true)}>
        Abrir
      </button>
      <Dialogo
        aberto={aberto}
        titulo="Cancelar a solicitação"
        descricao="Nós avisamos o parceiro e encerramos o protocolo."
        aoFechar={() => setAberto(false)}
        destrutivo={destrutivo}
        acoes={
          <>
            <button type="button" className="botao botao--secundario" onClick={() => setAberto(false)}>
              Manter
            </button>
            <button type="button" className={`botao ${destrutivo ? 'botao--destrutivo' : 'botao--primario'}`} onClick={aoConfirmar}>
              Cancelar solicitação
            </button>
          </>
        }
      >
        <p>Conteúdo</p>
      </Dialogo>
    </>
  );
}

describe('Dialogo (modal acessível)', () => {
  it('fechado não existe no DOM; aberto é role=dialog rotulado pelo título e descrito pela descrição', async () => {
    const usuario = userEvent.setup();
    render(<Harness />);
    expect(screen.queryByRole('dialog')).toBeNull();
    await usuario.click(screen.getByRole('button', { name: 'Abrir' }));
    const dialogo = screen.getByRole('dialog', { name: 'Cancelar a solicitação' });
    expect(dialogo).toHaveAttribute('aria-modal', 'true');
    expect(dialogo).toHaveAccessibleDescription('Nós avisamos o parceiro e encerramos o protocolo.');
    expect(document.documentElement).toHaveClass('rolagem-travada');
  });

  it('prende o foco: primeiro foco no Fechar, Tab circula, Esc fecha e devolve o foco a quem abriu', async () => {
    const usuario = userEvent.setup();
    render(<Harness />);
    const abrir = screen.getByRole('button', { name: 'Abrir' });
    await usuario.click(abrir);
    expect(screen.getByRole('button', { name: 'Fechar' })).toHaveFocus();
    await usuario.tab();
    expect(screen.getByRole('button', { name: 'Manter' })).toHaveFocus();
    await usuario.tab();
    expect(screen.getByRole('button', { name: 'Cancelar solicitação' })).toHaveFocus();
    await usuario.tab(); // volta ao início do diálogo, nunca sai para a página
    expect(screen.getByRole('button', { name: 'Fechar' })).toHaveFocus();
    await usuario.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Cancelar solicitação' })).toHaveFocus();
    await act(async () => {
      await usuario.keyboard('{Escape}');
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(abrir).toHaveFocus();
    expect(document.documentElement).not.toHaveClass('rolagem-travada');
  });

  it('clique no scrim fecha; clique dentro não fecha', async () => {
    const usuario = userEvent.setup();
    const { container } = render(<Harness />);
    await usuario.click(screen.getByRole('button', { name: 'Abrir' }));
    await usuario.click(screen.getByText('Conteúdo'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await usuario.click(container.querySelector('.scrim') as HTMLElement);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('variante destrutiva é alertdialog e a ação destrutiva não recebe o foco inicial', async () => {
    const usuario = userEvent.setup();
    const confirmar = vi.fn();
    render(<Harness destrutivo aoConfirmar={confirmar} />);
    await usuario.click(screen.getByRole('button', { name: 'Abrir' }));
    const dialogo = screen.getByRole('alertdialog', { name: 'Cancelar a solicitação' });
    expect(dialogo).toHaveClass('dialogo--destrutivo');
    expect(screen.getByRole('button', { name: 'Cancelar solicitação' })).not.toHaveFocus();
    await usuario.click(screen.getByRole('button', { name: 'Cancelar solicitação' }));
    expect(confirmar).toHaveBeenCalledOnce();
  });
});
