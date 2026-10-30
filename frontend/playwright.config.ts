import { defineConfig, devices, type Project } from '@playwright/test';

/**
 * E2E contra o container real (imagem de produção, AUTH_MODE=stub, banco de
 * teste). Variáveis:
 *   E2E_BASE_URL    — padrão http://127.0.0.1:18000
 *   E2E_STUB_TOKEN  — DEV_STUB_TOKEN do container de teste (obrigatória)
 *   E2E_WEBKIT=1    — liga o projeto `webkit-iphone` (Safari iOS, spec v2 §14)
 * Viewports da spec v2 §14: 1440 px (desktop), 390 px e 360 px (celular mínimo).
 */
const projetos: Project[] = [
  { name: 'desktop-1440', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
  {
    name: 'mobile-390',
    use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
  },
  {
    name: 'mobile-360',
    use: { ...devices['Desktop Chrome'], viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true },
  },
];

// WebKit exige `npx playwright install --with-deps webkit` no host de e2e (bibliotecas
// de sistema que o host atual não tem — TI-63/Estivador). Fica fora por padrão para o
// `npm run e2e` não falhar onde só o Chromium está instalado; ligue com E2E_WEBKIT=1.
if (process.env.E2E_WEBKIT === '1') {
  projetos.push({ name: 'webkit-iphone', use: { ...devices['iPhone 13'] } });
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:18000',
    trace: 'retain-on-failure',
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
  },
  projects: projetos,
});
