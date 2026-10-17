import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { respostaJson } from '../test/utilidades';
import { ApiError, MENSAGEM_SEM_CONEXAO, aoCsrfInvalido, api, definirCsrf, urlLogin } from './client';

describe('cliente da API', () => {
  const assign = vi.fn();

  beforeEach(() => {
    definirCsrf('tok-123');
    vi.stubGlobal('location', { ...window.location, assign, pathname: '/area/perfil', search: '?x=1' });
  });

  afterEach(() => {
    definirCsrf(null);
    aoCsrfInvalido(null);
    vi.unstubAllGlobals();
  });

  it('envia X-CSRF-Token e JSON em método não seguro, e nunca segue redirecionamento', async () => {
    const f = vi.fn(async () => respostaJson({ ok: true }));
    vi.stubGlobal('fetch', f);
    await api('/uso', { metodo: 'POST', corpo: { a: 1 } });
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    const cab = init.headers as Record<string, string>;
    expect(url).toBe('/api/v1/uso');
    expect(cab['X-CSRF-Token']).toBe('tok-123');
    expect(cab['Content-Type']).toBe('application/json');
    expect(init.redirect).toBe('error');
    expect(init.credentials).toBe('same-origin');
    expect(init.body).toBe('{"a":1}');
  });

  it('não envia token CSRF em GET', async () => {
    const f = vi.fn(async () => respostaJson({}));
    vi.stubGlobal('fetch', f);
    await api('/sessao');
    const init = (f.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined();
  });

  it('401 navega para o login com next = rota atual', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respostaJson({ erro: 'nao_autenticado', mensagem: 'x', request_id: null }, 401)));
    await expect(api('/sessao')).rejects.toBeInstanceOf(ApiError);
    expect(assign).toHaveBeenCalledWith('/auth/login?next=%2Farea%2Fperfil%3Fx%3D1');
    expect(urlLogin()).toBe('/auth/login?next=%2Farea%2Fperfil%3Fx%3D1');
  });

  it('erro da API vira ApiError com código, mensagem e request_id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => respostaJson({ erro: 'fonte_indisponivel', mensagem: 'Fora.', request_id: 'abc' }, 503)),
    );
    const erro = await api('/perfil').catch((e: unknown) => e);
    expect(erro).toMatchObject({ status: 503, erro: 'fonte_indisponivel', message: 'Fora.', requestId: 'abc' });
  });

  it('corpo não JSON vira mensagem padrão sem quebrar', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>502</html>', { status: 502 })));
    const erro = await api('/perfil').catch((e: unknown) => e);
    expect(erro).toMatchObject({ status: 502, erro: 'erro_interno' });
  });

  it('falha de rede vira sem_conexao', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    const erro = await api('/perfil').catch((e: unknown) => e);
    expect(erro).toMatchObject({ status: 0, erro: 'sem_conexao', message: MENSAGEM_SEM_CONEXAO });
  });

  it('403 csrf_invalido avisa o ouvinte (renovação) e propaga o erro', async () => {
    const ouvinte = vi.fn();
    aoCsrfInvalido(ouvinte);
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => respostaJson({ erro: 'csrf_invalido', mensagem: 'Tente de novo.', request_id: null }, 403)),
    );
    await expect(api('/uso', { metodo: 'POST', corpo: {} })).rejects.toMatchObject({ erro: 'csrf_invalido' });
    expect(ouvinte).toHaveBeenCalledOnce();
  });
});
