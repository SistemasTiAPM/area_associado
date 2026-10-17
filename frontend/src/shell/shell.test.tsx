import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { _reiniciarAnalytics, enviarFila } from '../lib/analytics';
import { fabricarSessao, montarApp } from '../test/utilidades';

describe('shell da Minha APM', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('carrega a sessão, saúda pelo nome e mostra o título da rota no h1', async () => {
    montarApp('/');
    expect(await screen.findByText('Telma')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Início' })).toBeInTheDocument();
  });

  it('flags desligadas escondem Fatura (menu e rota) e o bloco Mensalidade Zero', async () => {
    montarApp('/fatura');
    const menu = await screen.findByRole('navigation', { name: 'Menu principal' });
    expect(within(menu).queryByRole('link', { name: /Fatura de valor/ })).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument();
    expect(screen.queryByText('Mensalidade Zero ativa')).toBeNull();
    expect(screen.queryByText(/patrocínio ativo/)).toBeNull();
  });

  it('flag ligada mostra a Fatura no menu e a pill no header', async () => {
    montarApp('/fatura', fabricarSessao({ flags: { fatura_valor: true, mensalidade_zero: true } }));
    const menu = await screen.findByRole('navigation', { name: 'Menu principal' });
    expect(within(menu).getByRole('link', { name: /Fatura de valor/ })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByText('Mensalidade Zero ativa')).toBeInTheDocument();
  });

  it('Onboarding acadêmico só aparece para o tipo Acadêmico', async () => {
    const { unmount } = montarApp('/');
    const menu = await screen.findByRole('navigation', { name: 'Menu principal' });
    expect(within(menu).queryByRole('link', { name: /Onboarding/ })).toBeNull();
    unmount();
    montarApp('/', fabricarSessao({ associado: { tipo: 'Acadêmico' } }));
    const menu2 = await screen.findByRole('navigation', { name: 'Menu principal' });
    expect(within(menu2).getByRole('link', { name: /Onboarding acadêmico/ })).toBeInTheDocument();
  });

  it('bottom-nav tem as 5 abas da spec', async () => {
    montarApp('/');
    const nav = await screen.findByRole('navigation', { name: 'Atalhos' });
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Início',
      'Benefícios',
      'Clube',
      'Notícias',
      'Carteirinha',
    ]);
  });

  it('botão da Central abre wa.me em nova aba com noopener', async () => {
    montarApp('/');
    const link = await screen.findByRole('link', { name: /Central APM/ });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/551131886200\?text=/);
  });

  it('SHOW_WHATSAPP=0 esconde a Central', async () => {
    montarApp('/', fabricarSessao({ config: { show_whatsapp: false } }));
    await screen.findByText('Telma');
    expect(screen.queryByRole('link', { name: /Central APM/ })).toBeNull();
  });

  it('logout é formulário POST com o token CSRF da sessão', async () => {
    const { container } = montarApp('/');
    await screen.findByText('Telma');
    const formulario = container.querySelector('aside form') as HTMLFormElement;
    expect(formulario.method).toBe('post');
    expect(formulario.getAttribute('action')).toBe('/auth/logout');
    expect((formulario.elements.namedItem('csrf') as HTMLInputElement).value).toBe('token-csrf-teste');
  });

  it('faixa de construção aparece só no modo stub', async () => {
    montarApp('/', fabricarSessao({ stub: true }));
    expect(await screen.findByText(/Ambiente de construção/)).toBeInTheDocument();
  });

  it('drawer: abre pelo hambúrguer, fecha com Esc e devolve o foco', async () => {
    const usuario = userEvent.setup();
    montarApp('/');
    const hamburguer = await screen.findByRole('button', { name: 'Abrir menu' });
    await usuario.click(hamburguer);
    expect(hamburguer).toHaveAttribute('aria-expanded', 'true');
    const dialogo = screen.getByRole('dialog', { name: 'Menu' });
    expect(dialogo).toHaveClass('drawer--aberto');
    expect(within(dialogo).getByRole('button', { name: 'Fechar menu' })).toHaveFocus();
    await act(async () => {
      await usuario.keyboard('{Escape}');
    });
    expect(dialogo).not.toHaveClass('drawer--aberto');
    expect(hamburguer).toHaveFocus();
  });

  it('registra pagina_ver no analytics', async () => {
    const { chamadas } = montarApp('/beneficios');
    await screen.findByRole('heading', { level: 1, name: 'Meus benefícios' });
    enviarFila(true); // o que o pagehide faria
    const envio = chamadas.find((c) => c.url === '/api/v1/uso');
    expect(envio).toBeDefined();
    expect(envio?.init?.keepalive).toBe(true);
    expect(JSON.parse(String(envio?.init?.body)).eventos).toContainEqual({
      acao: 'pagina_ver',
      entidade: 'rota',
      entidade_id: '/area/beneficios',
    });
  });
});
