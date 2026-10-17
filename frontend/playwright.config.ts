import { defineConfig, devices } from '@playwright/test';

/**
 * E2E contra o container real (imagem de produção, AUTH_MODE=stub, banco de
 * teste). Variáveis:
 *   E2E_BASE_URL    — padrão http://127.0.0.1:18000
 *   E2E_STUB_TOKEN  — DEV_STUB_TOKEN do container de teste (obrigatória)
 * Viewports da spec: 1440 px (desktop) e 390 px (mobile).
 */
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
  projects: [
    { name: 'desktop-1440', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    {
      name: 'mobile-390',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
});
