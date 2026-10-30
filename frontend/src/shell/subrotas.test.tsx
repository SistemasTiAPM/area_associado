import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { _reiniciarAnalytics, enviarFila } from '../lib/analytics';
import { caminhoParaAnalytics, resolverCaminho } from '../rotas';
import { montarApp } from '../test/utilidades';
import { useDefinirTituloPagina } from './TituloPagina';

/**
 * TI-23: sub-rotas no shell. A página "em construção" é substituída por uma
 * que, em sub-rota, define o h1 pelo contexto — como farão P04/P05 (Fase 4/3).
 */
vi.mock('../pages/EmConstrucao', () => ({
  EmConstrucao: ({ titulo, parametro }: { titulo: string; parametro?: string }) => {
    useDefinirTituloPagina(parametro ? `Detalhe de ${parametro}` : null);
    return <p>{parametro ? `conteúdo de ${parametro}` : titulo}</p>;
  },
}));

const UUID = '123e4567-e89b-12d3-a456-426614174000';

describe('resolverCaminho / caminhoParaAnalytics', () => {
  it('casa rota exata, sub-rota só onde é permitida e recusa segmentos malformados', () => {
    expect(resolverCaminho('/beneficios')?.rota.id).toBe('ben');
    expect(resolverCaminho('/beneficios/escola-de-idiomas')).toMatchObject({ rota: { id: 'ben' }, parametro: 'escola-de-idiomas' });
    expect(resolverCaminho(`/solicitacoes/${UUID}/`)).toMatchObject({ rota: { id: 'solicitacoes' }, parametro: UUID });
    expect(resolverCaminho('/eventos/42')).toMatchObject({ rota: { id: 'evt' }, parametro: '42' });
    expect(resolverCaminho('/perfil/qualquer')).toBeUndefined(); // sem subRota
    expect(resolverCaminho('/beneficios/a/b')).toBeUndefined(); // só um segmento
    expect(resolverCaminho('/beneficios/..')).toBeUndefined();
    expect(resolverCaminho('/beneficios/-x')).toBeUndefined();
    expect(resolverCaminho(`/beneficios/${'a'.repeat(129)}`)).toBeUndefined();
    expect(resolverCaminho('/')).toMatchObject({ rota: { id: 'home' } });
  });

  it('analytics: slug de catálogo truncado a 32, protocolo pessoal omitido, desconhecida como antes', () => {
    expect(caminhoParaAnalytics('/')).toBe('/area');
    expect(caminhoParaAnalytics('/beneficios')).toBe('/area/beneficios');
    expect(caminhoParaAnalytics(`/beneficios/${'escola-de-idiomas-'.repeat(3)}`)).toBe(`/area/beneficios/${'escola-de-idiomas-'.repeat(3).slice(0, 32)}`);
    expect(caminhoParaAnalytics(`/solicitacoes/${UUID}`)).toBe('/area/solicitacoes/_');
    expect(caminhoParaAnalytics('/eventos/42')).toBe('/area/eventos/42');
    expect(caminhoParaAnalytics('/nao-existe')).toBe('/area/nao-existe');
    expect(caminhoParaAnalytics(`/x/${'y'.repeat(200)}`).length).toBeLessThanOrEqual(64);
  });
});

describe('shell com sub-rotas (TI-23)', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('/beneficios/{slug} não é "página não encontrada"; a página define o h1 e o <title>', async () => {
    montarApp('/beneficios/escola-de-idiomas');
    expect(await screen.findByText('conteúdo de escola-de-idiomas')).toBeInTheDocument();
    // O h1 muda num segundo commit (efeito da página → estado do shell): esperar.
    expect(await screen.findByRole('heading', { level: 1, name: 'Detalhe de escola-de-idiomas' })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe('Detalhe de escola-de-idiomas · Minha APM'));
    expect(screen.queryByText('Página não encontrada')).toBeNull();
  });

  it('sem título da página, o h1 é o da rota; sub-rota em rota sem suporte cai em não encontrada', async () => {
    const { unmount } = montarApp('/beneficios');
    expect(await screen.findByRole('heading', { level: 1, name: 'Meus benefícios' })).toBeInTheDocument();
    unmount();
    montarApp('/perfil/abc');
    expect(await screen.findByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument();
  });

  it('pagina_ver: slug de catálogo vai truncado; protocolo pessoal vai como "_"', async () => {
    const { chamadas, unmount } = montarApp(`/solicitacoes/${UUID}`);
    await screen.findByRole('heading', { level: 1, name: `Detalhe de ${UUID}` });
    enviarFila(true);
    const corpo = JSON.parse(String(chamadas.find((c) => c.url === '/api/v1/uso')?.init?.body));
    expect(corpo.eventos).toContainEqual({ acao: 'pagina_ver', entidade: 'rota', entidade_id: '/area/solicitacoes/_' });
    expect(JSON.stringify(corpo)).not.toContain(UUID);
    unmount();
    _reiniciarAnalytics();
    const segunda = montarApp('/eventos/congresso-paulista-2026');
    await screen.findByRole('heading', { level: 1, name: 'Detalhe de congresso-paulista-2026' });
    enviarFila(true);
    const corpo2 = JSON.parse(String(segunda.chamadas.find((c) => c.url === '/api/v1/uso')?.init?.body));
    expect(corpo2.eventos).toContainEqual({ acao: 'pagina_ver', entidade: 'rota', entidade_id: '/area/eventos/congresso-paulista-2026' });
  });
});
