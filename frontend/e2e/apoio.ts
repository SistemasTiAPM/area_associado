import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';

/**
 * Apoio compartilhado dos specs e2e (não é spec: o Playwright só coleta `*.spec.ts`).
 * Login stub, vigia de CSP, reflow e auditoria axe WCAG 2.2 AA (TI-63).
 */

const TOKEN = process.env.E2E_STUB_TOKEN ?? '';

/** Coleta violações de CSP antes de qualquer script da página (RNF-01). */
export async function vigiarCsp(page: Page): Promise<string[]> {
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

export async function entrar(page: Page, tipo = 'Efetivo', destino = '/area') {
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

export async function semRolagemHorizontal(page: Page) {
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1] ?? 0);
}

/** Tags do axe: WCAG 2.0/2.1/2.2 A e AA (spec v2 §14 pede 2.2 AA). */
export const TAGS_AXE = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'];

/** Espera o estado final da tela (sem "Carregando", animações terminadas) e roda o axe. */
export async function auditarAxe(page: Page): Promise<string[]> {
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByText(/Carregando/)).toHaveCount(0);
  // Mede o estado final: no meio da entrada (opacidade < 1) o contraste calculado cai.
  await page.waitForFunction(() => document.getAnimations().every((a) => a.playState === 'finished'));
  const resultado = await new AxeBuilder({ page }).withTags(TAGS_AXE).analyze();
  return resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}

export const ehMobile = (nome: string) => nome.startsWith('mobile-') || nome.startsWith('webkit-');
