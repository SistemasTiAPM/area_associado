import { expect, test } from '@playwright/test';
import { auditarAxe, ehMobile, entrar, semRolagemHorizontal, vigiarCsp } from './apoio';

/**
 * Critérios de aceite da Fase 1 (REQUISITOS RF-SH-*, RF-AU-*, RNF-01/10/13/20)
 * contra o container real em modo stub.
 */

const ROTAS = [
  ['/area', 'Início'],
  ['/area/beneficios', 'Meus benefícios'],
  ['/area/clube', 'Clube de vantagens'],
  ['/area/noticias', 'Notícias e ciência'],
  ['/area/comunidade', 'Comunidade'],
  ['/area/eventos', 'Congresso e eventos'],
  ['/area/carteirinha', 'Carteirinha digital'],
  ['/area/perfil', 'Meu perfil'],
  ['/area/solicitacoes', 'Minhas solicitações'],
  ['/area/ajuda', 'Ajuda'],
] as const;

test('login stub → saudação, 10 rotas pelo URL com recarga, sem violação de CSP', async ({ page }) => {
  const violacoes = await vigiarCsp(page);
  await entrar(page);
  await expect(page.getByText('Telma', { exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Ambiente de construção' })).toBeVisible();

  // Com as flags de P13 ligadas no banco de teste, o perfil vira "Perfil e privacidade" (ADR-0026).
  const sessao = (await (await page.request.get('/api/v1/sessao')).json()) as { flags?: Record<string, boolean> };
  const comP13 = sessao.flags?.perfil_preferencias === true || sessao.flags?.lgpd_consentimentos === true;
  for (const [caminho, tituloDaRota] of ROTAS) {
    const titulo = caminho === '/area/perfil' && comP13 ? 'Perfil e privacidade' : tituloDaRota;
    await page.goto(caminho);
    await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible();
    await expect(page).toHaveTitle(`${titulo} · Minha APM`);
    await semRolagemHorizontal(page);
  }
  await page.reload();
  const [, ultimoTitulo] = ROTAS[ROTAS.length - 1];
  await expect(page.getByRole('heading', { level: 1, name: ultimoTitulo })).toBeVisible();
  expect(violacoes).toEqual([]);
});

test('flags desligadas e persona: Fatura e Onboarding indisponíveis para Efetivo', async ({ page }) => {
  await entrar(page);
  await page.goto('/area/fatura');
  await expect(page.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeVisible();
  await page.goto('/area/onboarding');
  await expect(page.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeVisible();
  await expect(page.getByText('Mensalidade Zero ativa')).toHaveCount(0);
});

test('Acadêmico vê o Onboarding acadêmico', async ({ page }) => {
  await entrar(page, 'Acadêmico');
  await page.goto('/area/onboarding');
  await expect(page.getByRole('heading', { level: 1, name: 'Onboarding acadêmico' })).toBeVisible();
});

test('navegação pelo menu (desktop) ou drawer + bottom-nav (mobile)', async ({ page }, info) => {
  await entrar(page);
  if (info.project.name === 'desktop-1440') {
    const sidebar = page.getByRole('navigation', { name: 'Menu principal', exact: true });
    await expect(sidebar).toBeVisible();
    expect(await page.locator('aside.sidebar').evaluate((el) => el.getBoundingClientRect().width)).toBe(264);
    await sidebar.getByRole('link', { name: 'Comunidade' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Comunidade' })).toBeFocused();
    await expect(page.getByRole('button', { name: 'Abrir menu' })).toBeHidden();
    await expect(page.getByRole('navigation', { name: 'Atalhos' })).toBeHidden();
  } else {
    await expect(page.locator('aside.sidebar')).toBeHidden();
    const abas = page.getByRole('navigation', { name: 'Atalhos' });
    await expect(abas.getByRole('link')).toHaveCount(5);
    await abas.getByRole('link', { name: 'Clube' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Clube de vantagens' })).toBeVisible();
    await expect(abas.getByRole('link', { name: 'Clube' })).toHaveAttribute('aria-current', 'page');

    const hamburguer = page.getByRole('button', { name: 'Abrir menu' });
    await hamburguer.click();
    const drawer = page.getByRole('dialog', { name: 'Menu' });
    await expect(drawer).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(drawer).toBeHidden();
    await expect(hamburguer).toBeFocused();

    await hamburguer.click();
    await drawer.getByRole('link', { name: 'Congresso e eventos' }).click();
    await expect(drawer).toBeHidden();
    await expect(page.getByRole('heading', { level: 1, name: 'Congresso e eventos' })).toBeVisible();
    // Busca em linha inteira (ocupa a largura útil: viewport − margens do shell e do cabeçalho).
    const busca = await page.getByRole('search').boundingBox();
    const largura = page.viewportSize()?.width ?? 390;
    expect(busca?.width ?? 0).toBeGreaterThan(largura - 60);
    await semRolagemHorizontal(page);
  }
});

test('acessibilidade (axe, WCAG 2.2 AA) sem violações em todas as rotas, inclusive não encontrada', async ({ page }) => {
  await entrar(page);
  for (const [caminho] of [...ROTAS, ['/area/nao-existe', 'Página não encontrada']] as const) {
    await page.goto(caminho);
    expect(await auditarAxe(page), caminho).toEqual([]);
  }
});

test('mobile: Tab chega ao último controle do conteúdo sem ficar sob a barra inferior (WCAG 2.2 2.4.11)', async ({ page }, info) => {
  test.skip(!ehMobile(info.project.name), 'barra inferior só existe abaixo de 900 px');
  await entrar(page, 'Efetivo', '/area/perfil');
  await expect(page.getByText(/Carregando/)).toHaveCount(0);
  await page.waitForFunction(() => document.getAnimations().every((a) => a.playState === 'finished'));
  const barra = await page.getByRole('navigation', { name: 'Atalhos' }).boundingBox();
  expect(barra).not.toBeNull();

  // Tab a partir do h1 até o foco sair do <main>; em cada passo o elemento focado
  // precisa estar inteiro acima da barra inferior fixa (scroll-padding-bottom).
  // Os controles do cabeçalho (busca, perfil) vêm antes do <main> na ordem do DOM: o laço
  // ignora o foco fora do conteúdo até entrar nele e só para quando sai depois de ter entrado.
  await page.getByRole('heading', { level: 1 }).focus();
  let dentro = 0;
  let entrou = false;
  for (let i = 0; i < 80; i += 1) {
    await page.keyboard.press('Tab');
    const foco = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || !document.getElementById('conteudo')?.contains(el)) return null;
      const r = el.getBoundingClientRect();
      return { bottom: r.bottom, top: r.top, inner: window.innerHeight, tag: el.tagName, texto: (el.textContent ?? '').trim().slice(0, 40) };
    });
    if (foco === null) {
      if (entrou) break;
      continue;
    }
    entrou = true;
    dentro += 1;
    expect(foco.bottom, `${foco.tag} "${foco.texto}" ficou sob a barra inferior`).toBeLessThanOrEqual((barra?.y ?? 0) + 1);
    expect(foco.top).toBeGreaterThanOrEqual(0);
  }
  expect(dentro, 'o Tab precisa percorrer controles dentro do conteúdo').toBeGreaterThan(3);
});

test('reflow em celular: nenhuma rota rola na horizontal, nem com o drawer aberto', async ({ page }, info) => {
  test.skip(!ehMobile(info.project.name), 'reflow é critério do celular (spec v2 §14, 360 px)');
  await entrar(page);
  for (const [caminho] of ROTAS) {
    await page.goto(caminho);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await semRolagemHorizontal(page);
  }
  await page.getByRole('button', { name: 'Abrir menu' }).click();
  await expect(page.getByRole('dialog', { name: 'Menu' })).toBeVisible();
  await semRolagemHorizontal(page);
  // Alvos mínimos de 44 px nos controles da barra inferior e nos botões (spec v2 §14).
  for (const aba of await page.getByRole('navigation', { name: 'Atalhos' }).getByRole('link').all()) {
    const caixa = await aba.boundingBox();
    expect(caixa?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
});

test('reduced-motion desliga todas as animações', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await entrar(page);
  await page.goto('/area/beneficios');
  await expect(page.getByRole('heading', { level: 1, name: 'Meus benefícios' })).toBeVisible();
  expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
});

test('analytics grava pagina_ver; CSRF recusa POST sem token', async ({ page }) => {
  await entrar(page);
  // Navegação completa dispara pagehide na página anterior (envio keepalive,
  // sem corpo legível pelo Playwright). Espera-se o envio do temporizador (3 s)
  // da página NOVA, registrado só depois do goto.
  await page.goto('/area/noticias');
  const resposta = await page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/uso') && r.request().method() === 'POST' && !r.request().postData()?.includes('"/area"}'),
    { timeout: 10_000 },
  );
  expect(resposta.status()).toBe(202);
  // O cliente de analytics não lê o corpo (dispare e esqueça), e o Chromium
  // não o retém para o Playwright: valida-se o envio. A gravação em
  // evento_uso é verificada no banco de teste (docs/CONCLUIDO.md, Fase 1).
  expect(resposta.request().postData()).toContain('"entidade_id":"/area/noticias"');

  const semToken = await page.evaluate(async () => {
    const r = await fetch('/api/v1/uso', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ eventos: [{ acao: 'pagina_ver', entidade: 'rota' }] }),
    });
    return [r.status, ((await r.json()) as { erro: string }).erro];
  });
  expect(semToken).toEqual([403, 'csrf_invalido']);
});

test('Central APM abre wa.me em nova aba; Sair encerra a sessão', async ({ page }) => {
  await entrar(page);
  const central = page.getByRole('link', { name: /Central APM/ });
  await expect(central).toHaveAttribute('href', /^https:\/\/wa\.me\/551131886200\?text=/);
  await expect(central).toHaveAttribute('rel', 'noopener noreferrer');

  const abrirSair = page.getByRole('button', { name: 'Abrir menu' });
  if (await abrirSair.isVisible()) await abrirSair.click();
  await page.getByRole('button', { name: 'Sair' }).filter({ visible: true }).click();
  // Depois do Sair, direto para o login (no OIDC, o formulário do Login APM; no stub, o de construção).
  await expect(page).toHaveURL(/\/auth\/login\?next=(%2F|\/)area$/);
  const status = await page.evaluate(async () => (await fetch('/api/v1/sessao')).status);
  expect(status).toBe(401);
  await page.goto('/area/perfil');
  await expect(page).toHaveURL(/\/auth\/login\?next=%2Farea%2Fperfil|\/auth\/login\?next=\/area\/perfil/);
});
