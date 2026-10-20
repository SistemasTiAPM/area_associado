import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/**
 * Critérios de aceite da Fase 1 (REQUISITOS RF-SH-*, RF-AU-*, RNF-01/10/13/20)
 * contra o container real em modo stub.
 */

const TOKEN = process.env.E2E_STUB_TOKEN ?? '';

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
] as const;

/** Coleta violações de CSP antes de qualquer script da página (RNF-01). */
async function vigiarCsp(page: Page): Promise<string[]> {
  const violacoes: string[] = [];
  await page.exposeFunction('__registrarViolacaoCsp', (v: string) => violacoes.push(v));
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      (window as unknown as { __registrarViolacaoCsp: (v: string) => void }).__registrarViolacaoCsp(
        `${e.violatedDirective} ${e.blockedURI}`,
      );
    });
  });
  page.on('console', (msg) => {
    if (/Content Security Policy/i.test(msg.text())) violacoes.push(msg.text());
  });
  return violacoes;
}

async function entrar(page: Page, tipo = 'Efetivo', destino = '/area') {
  expect(TOKEN, 'defina E2E_STUB_TOKEN').not.toBe('');
  await page.goto(destino);
  await expect(page).toHaveURL(/\/auth\/login\?next=/);
  await page.getByLabel('Token de construção').fill(TOKEN);
  await page.getByLabel('Nome').fill('TELMA NOGUEIRA');
  await page.getByLabel('E-mail').fill('telma@example.org');
  await page.getByLabel('Tipo de associado (persona)').selectOption(tipo);
  await page.getByLabel('CPF (apenas para a máscara)').fill('12345678901');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

async function semRolagemHorizontal(page: Page) {
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1] ?? 0);
}

test('login stub → saudação, 9 rotas pelo URL com recarga, sem violação de CSP', async ({ page }) => {
  const violacoes = await vigiarCsp(page);
  await entrar(page);
  await expect(page.getByText('Telma', { exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Ambiente de construção' })).toBeVisible();

  for (const [caminho, titulo] of ROTAS) {
    await page.goto(caminho);
    await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible();
    await expect(page).toHaveTitle(`${titulo} · Minha APM`);
    await semRolagemHorizontal(page);
  }
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: 'Minhas solicitações' })).toBeVisible();
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
    // Busca em linha inteira e conteúdo com reserva para a bottom-nav (spec, 390 px).
    const busca = await page.getByRole('search').boundingBox();
    expect(busca?.width ?? 0).toBeGreaterThan(340);
    await semRolagemHorizontal(page);
  }
});

test('acessibilidade (axe) sem violações em Início, Benefícios e Carteirinha', async ({ page }) => {
  await entrar(page);
  for (const caminho of ['/area', '/area/beneficios', '/area/carteirinha', '/area/perfil']) {
    await page.goto(caminho);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByText(/Carregando/)).toHaveCount(0);
    // Mede o estado final: no meio da entrada (opacidade < 1) o contraste calculado cai.
    await page.waitForFunction(() => document.getAnimations().every((a) => a.playState === 'finished'));
    const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
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
  // Depois do Sair, direto para o login (no stub, o formulário de construção).
  await expect(page).toHaveURL(/\/auth\/login\?next=(%2F|\/)area$/);
  const status = await page.evaluate(async () => (await fetch('/api/v1/sessao')).status);
  expect(status).toBe(401);
  await page.goto('/area/perfil');
  await expect(page).toHaveURL(/\/auth\/login\?next=%2Farea%2Fperfil|\/auth\/login\?next=\/area\/perfil/);
});
