import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { definirCsrf } from '../api/client';
import { respostaJson } from '../test/utilidades';
import { _reiniciarAnalytics, enviarFila, eventosDescartados, registrarUso } from './analytics';

describe('analytics de UI (REQUISITOS §8)', () => {
  beforeEach(() => {
    _reiniciarAnalytics();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    definirCsrf(null);
    vi.unstubAllGlobals();
  });

  it('agrupa e envia com CSRF depois do atraso', async () => {
    definirCsrf('tok');
    const f = vi.fn(async () => respostaJson({ gravados: 2, descartados: 0 }, 202));
    vi.stubGlobal('fetch', f);
    registrarUso({ acao: 'pagina_ver', entidade: 'rota', entidade_id: '/area' });
    registrarUso({ acao: 'central_whatsapp_abrir', entidade: 'central' });
    expect(f).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(3000);
    expect(f).toHaveBeenCalledOnce();
    const init = (f.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('tok');
    expect(JSON.parse(String(init.body)).eventos).toHaveLength(2);
  });

  it('lote cheio (20) sai na hora; keepalive no envio de saída', async () => {
    definirCsrf('tok');
    const f = vi.fn(async () => respostaJson({}, 202));
    vi.stubGlobal('fetch', f);
    for (let i = 0; i < 20; i += 1) registrarUso({ acao: 'pagina_ver', entidade: 'rota' });
    expect(f).toHaveBeenCalledOnce();
    registrarUso({ acao: 'pagina_ver', entidade: 'rota' });
    enviarFila(true);
    expect((f.mock.calls[1] as unknown as [string, RequestInit])[1].keepalive).toBe(true);
  });

  it('sem token CSRF ou com falha de rede descarta sem lançar', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))));
    registrarUso({ acao: 'pagina_ver', entidade: 'rota' });
    enviarFila();
    expect(eventosDescartados()).toBe(1);
    definirCsrf('tok');
    registrarUso({ acao: 'pagina_ver', entidade: 'rota' });
    enviarFila();
    await vi.runAllTimersAsync();
    expect(eventosDescartados()).toBe(2);
  });
});
