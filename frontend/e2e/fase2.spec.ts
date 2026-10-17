import { expect, test, type Page } from '@playwright/test';

/** Fase 2a — perfil, e-mail com código, foto e carteirinha contra o container real (hub/SMTP stub). */

const TOKEN = process.env.E2E_STUB_TOKEN ?? '';

// JPEG 64×64 mínimo válido, gerado no teste (sem arquivo binário no repositório).
async function jpeg(page: Page): Promise<Buffer> {
  const b64 = await page.evaluate(async () => {
    const tela = document.createElement('canvas');
    tela.width = 300;
    tela.height = 200;
    const ctx = tela.getContext('2d');
    if (!ctx) throw new Error('canvas');
    ctx.fillStyle = '#0e8f78';
    ctx.fillRect(0, 0, 300, 200);
    return tela.toDataURL('image/jpeg', 0.9).split(',')[1] ?? '';
  });
  return Buffer.from(b64, 'base64');
}

async function vigiarCsp(page: Page): Promise<string[]> {
  const violacoes: string[] = [];
  page.on('console', (msg) => {
    if (/Content Security Policy/i.test(msg.text())) violacoes.push(msg.text());
  });
  return violacoes;
}

async function entrar(page: Page, destino = '/area/perfil') {
  await page.goto(destino);
  await page.getByLabel('Token de construção').fill(TOKEN);
  await page.getByLabel('Nome').fill('TELMA NOGUEIRA');
  await page.getByLabel('E-mail').fill('telma@example.org');
  await page.getByLabel('CPF (apenas para a máscara)').fill(String(Date.now()).slice(-11).padStart(11, '7'));
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

test('perfil: contato, troca de e-mail com código e foto no avatar', async ({ page }) => {
  const violacoes = await vigiarCsp(page);
  await entrar(page);
  await expect(page.getByRole('heading', { level: 1, name: 'Meu perfil' })).toBeVisible();
  await expect(page.getByText('TELMA NOGUEIRA', { exact: true })).toBeVisible();

  // Contato
  const celular = page.getByLabel('Celular');
  await celular.fill('21988887777');
  await page.getByRole('button', { name: 'Salvar alterações' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Dados atualizados' })).toBeVisible();
  await expect(celular).toHaveValue('(21) 98888-7777');

  // E-mail com código (SMTP stub devolve o código em construção)
  await page.getByRole('button', { name: 'Alterar e-mail' }).click();
  await page.getByLabel('Novo e-mail').fill('nova.telma@example.org');
  await page.getByRole('button', { name: 'Enviar código' }).click();
  const aviso = page.getByText(/o código é \d{6}/);
  await expect(aviso).toBeVisible();
  const codigo = ((await aviso.textContent()) ?? '').match(/\d{6}/)?.[0] ?? '';
  await page.getByLabel('Código').fill(codigo);
  await page.getByRole('button', { name: 'Confirmar' }).click();
  await expect(page.getByText('nova.telma@example.org', { exact: true })).toBeVisible();

  // Foto → avatar do header passa a ser imagem
  await page.locator('input[type="file"]').setInputFiles({ name: 'eu.jpg', mimeType: 'image/jpeg', buffer: await jpeg(page) });
  await expect(page.getByRole('status').filter({ hasText: 'Foto atualizada' })).toBeVisible();
  const avatar = page.locator('header .avatar img');
  await expect(avatar).toBeVisible();
  expect(await avatar.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(128);
  await page.getByRole('button', { name: 'Remover foto' }).click();
  await expect(page.locator('header .avatar img')).toHaveCount(0);
  expect(violacoes).toEqual([]);
});

test('carteirinha: QR e verificação pública sem sessão', async ({ page, browser }) => {
  const violacoes = await vigiarCsp(page);
  await entrar(page, '/area/carteirinha');
  const cartao = page.getByRole('figure', { name: /Carteirinha digital de TELMA NOGUEIRA/ });
  await expect(cartao).toBeVisible();
  await expect(cartao.getByText(/CRM-SP \d+ · na APM desde 2014/)).toBeVisible();
  const qr = cartao.getByRole('img', { name: /QR code/ });
  await expect.poll(() => qr.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);

  const url = await page.evaluate(async () => {
    const r = await fetch('/api/v1/carteirinha');
    return ((await r.json()) as { url_verificacao: string }).url_verificacao;
  });
  const caminho = new URL(url).pathname;
  const anonimo = await browser.newContext();
  const publica = await anonimo.newPage();
  const resposta = await publica.goto(caminho);
  expect(resposta?.status()).toBe(200);
  expect(resposta?.headers()['x-robots-tag']).toBe('noindex, nofollow');
  await expect(publica.getByRole('heading', { name: 'TELMA NOGUEIRA' })).toBeVisible();
  await expect(publica.getByText('Ativo')).toBeVisible();
  expect((await publica.goto('/verificar/AAAAAAAAAAAAAAAAAAAA'))?.status()).toBe(404);
  await anonimo.close();
  expect(violacoes).toEqual([]);
});
