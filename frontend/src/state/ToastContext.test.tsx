import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { DURACAO_TOAST_MS, ToastProvider, useToast } from './ToastContext';

let api: ReturnType<typeof useToast>;
function Captura() {
  api = useToast();
  return null;
}

describe('toast (RF-SH-07)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('uma mensagem por vez: a nova substitui a anterior; some em 2,6 s', () => {
    render(
      <ToastProvider>
        <Captura />
      </ToastProvider>,
    );
    act(() => api.mostrar('Primeira'));
    act(() => api.mostrar('Segunda'));
    expect(screen.queryByText('Primeira')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent('Segunda');
    act(() => vi.advanceTimersByTime(DURACAO_TOAST_MS));
    expect(screen.queryByText('Segunda')).toBeNull();
  });

  it('erro vai para a região de alerta com a mensagem da API', () => {
    render(
      <ToastProvider>
        <Captura />
      </ToastProvider>,
    );
    act(() => api.mostrarErro(new ApiError(503, 'fonte_indisponivel', 'Não foi possível carregar agora.')));
    expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível carregar agora.');
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });
});
