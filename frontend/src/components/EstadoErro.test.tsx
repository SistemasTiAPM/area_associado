import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { EstadoErro } from './EstadoErro';

describe('EstadoErro', () => {
  it('é role=alert com título, mensagem e request_id para a Central', () => {
    render(<EstadoErro mensagem="Confira a internet e tente novamente." requestId="0123456789abcdef" />);
    const alerta = screen.getByRole('alert');
    expect(alerta).toHaveTextContent('Não conseguimos carregar esta parte agora');
    expect(alerta).toHaveTextContent('Confira a internet e tente novamente.');
    expect(screen.getByText('0123456789abcdef').tagName).toBe('CODE');
    expect(screen.getByText(/Código para a Central de Relacionamento/)).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull(); // sem callback, sem botão
  });

  it('"Tentar novamente" chama o callback e fica desabilitado enquanto ocupado', async () => {
    const usuario = userEvent.setup();
    const tentar = vi.fn();
    const { rerender } = render(<EstadoErro mensagem="x" aoTentarNovamente={tentar} />);
    await usuario.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(tentar).toHaveBeenCalledOnce();
    rerender(<EstadoErro mensagem="x" aoTentarNovamente={tentar} ocupado />);
    const botao = screen.getByRole('button', { name: 'Tentar novamente' });
    expect(botao).toBeDisabled();
    expect(botao).toHaveAttribute('aria-busy', 'true');
  });

  it('sem request_id não mostra a linha do código; título e rótulo personalizáveis', () => {
    render(<EstadoErro titulo="Este recurso não está disponível" mensagem="Fale com a Central." requestId={null} aoTentarNovamente={() => {}} rotuloBotao="Recarregar" />);
    expect(screen.queryByText(/Código para a Central/)).toBeNull();
    expect(screen.getByRole('heading', { level: 2, name: 'Este recurso não está disponível' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recarregar' })).toBeInTheDocument();
  });
});
