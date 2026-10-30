import { expect, test, type Page } from '@playwright/test';
import { auditarAxe, ehMobile, semRolagemHorizontal, vigiarCsp } from './apoio';

/**
 * Onda 2 / Fase 3 — P14 (Ajuda), P05 (Minhas solicitações) e downloads da carteirinha
 * contra o container real (AUTH_MODE=stub, hub/SMTP stub, migrações 010–014 aplicadas).
 * Cada teste entra com um CPF próprio: associado novo, sem colidir com a unicidade por
 * tipo/finalidade nem com o teto diário de `outro` entre os projetos (viewports).
 */

const TOKEN = process.env.E2E_STUB_TOKEN ?? '';

async function entrarNovo(page: Page, destino: string) {
  expect(TOKEN, 'defina E2E_STUB_TOKEN').not.toBe('');
  await page.goto(destino);
  await expect(page).toHaveURL(/\/auth\/login\?next=/);
  await page.getByLabel('Token de construção').fill(TOKEN);
  await page.getByLabel('Nome').fill('TELMA NOGUEIRA');
  await page.getByLabel('E-mail').fill('telma@example.org');
  await page.getByLabel('Tipo de associado (persona)').selectOption('Efetivo');
  const cpf = `${Date.now()}${Math.floor(Math.random() * 10)}`.slice(-11).padStart(11, '7');
  await page.getByLabel('CPF (apenas para a máscara)').fill(cpf);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/** Os recursos da Onda 2 precisam estar prontos no servidor (migrações aplicadas). */
async function exigirRecursos(page: Page) {
  const sessao = (await (await page.request.get('/api/v1/sessao')).json()) as { recursos?: Record<string, boolean> };
  expect(sessao.recursos, 'aplique sql/010..014 no banco de teste').toEqual({ solicitacoes: true, ajuda: true });
}

async function criarDuvida(page: Page, mensagem: string) {
  await page.getByRole('button', { name: /Enviar dúvida/ }).click();
  const painel = page.getByRole('region', { name: 'Escrever para a Central' });
  await expect(page.getByRole('heading', { name: 'Escrever para a Central' })).toBeFocused();
  await painel.getByLabel('Mensagem').fill(mensagem);
  await painel.getByRole('button', { name: 'Enviar mensagem' }).click();
  await expect(page.getByRole('heading', { name: 'Recebemos sua mensagem' })).toBeVisible();
}

test('P14: FAQ (some quando vazia), canais da Central, dúvida vira solicitação em P05 e declaração', async ({ page }, info) => {
  const violacoes = await vigiarCsp(page);
  await entrarNovo(page, '/area/ajuda');
  await exigirRecursos(page);
  await expect(page.getByRole('heading', { level: 1, name: 'Ajuda' })).toBeVisible();

  // FAQ: bloco vazio não aparece (spec v2 §3.2); com perguntas publicadas, aparece com busca.
  const faq = (await (await page.request.get('/api/v1/ajuda/faq')).json()) as { itens: unknown[] };
  await expect(page.getByRole('heading', { name: 'Pedidos comuns' })).toBeVisible();
  await expect(page.getByText(/Carregando as perguntas/)).toHaveCount(0);
  if (faq.itens.length === 0) {
    await expect(page.getByRole('heading', { name: 'Perguntas frequentes' })).toHaveCount(0);
  } else {
    await expect(page.getByLabel('Buscar nas perguntas frequentes')).toBeVisible();
  }

  // Canais: o que vier de GET /ajuda/contato; o formulário existe sempre.
  const contato = (await (await page.request.get('/api/v1/ajuda/contato')).json()) as {
    whatsapp: { url: string } | null;
    telefone: { uri: string } | null;
  };
  const central = page.getByRole('region', { name: 'Fale com a Central de Relacionamento' });
  await expect(central.getByRole('button', { name: 'Escrever para a Central' })).toBeVisible();
  if (contato.whatsapp) await expect(central.getByRole('link', { name: /Conversar pelo WhatsApp/ })).toHaveAttribute('target', '_blank');
  if (contato.telefone) await expect(central.getByRole('link', { name: 'Ligar para a Central' })).toHaveAttribute('href', /^tel:\+?\d{8,15}$/);

  // Dúvida → solicitação `outro` → aparece em Minhas solicitações.
  const mensagem = `Dúvida e2e ${info.project.name} ${Date.now()}`;
  await criarDuvida(page, mensagem);
  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);

  // Declaração de associado (persona efetiva desde 2014: elegível).
  await page.getByRole('button', { name: /Solicitar declaração/ }).first().click();
  const declaracao = page.getByRole('region', { name: 'Pedir uma declaração' });
  await declaracao.getByLabel(/Declaração de associado/).check();
  await declaracao.getByRole('button', { name: 'Solicitar declaração' }).click();
  await expect(page.getByRole('heading', { name: 'Recebemos seu pedido de declaração' })).toBeVisible();
  if (ehMobile(info.project.name)) {
    const caixa = await page.getByRole('link', { name: 'Acompanhar a solicitação' }).boundingBox();
    expect(caixa?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(await auditarAxe(page)).toEqual([]);

  await page.getByRole('link', { name: 'Acompanhar a solicitação' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Declaração de associado' })).toBeVisible();
  await page.getByRole('link', { name: /Voltar para Minhas solicitações/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Minhas solicitações' })).toBeVisible();
  const lista = page.getByRole('list', { name: 'Solicitações em andamento' });
  await expect(lista.getByRole('link', { name: /Outro assunto/ })).toBeVisible();
  await expect(lista.getByRole('link', { name: /Declaração de associado/ })).toBeVisible();
  await expect(lista.getByText('Recebida pela APM').first()).toBeVisible();
  expect(violacoes).toEqual([]);
});

test('P05: lista, detalhe com linha do tempo e cancelamento com confirmação', async ({ page }, info) => {
  const violacoes = await vigiarCsp(page);
  await entrarNovo(page, '/area/ajuda');
  await exigirRecursos(page);
  await criarDuvida(page, `Cancelar e2e ${info.project.name} ${Date.now()}`);
  await page.getByRole('link', { name: 'Acompanhar a solicitação' }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Outro assunto' })).toBeVisible();
  const linha = page.getByRole('list', { name: 'Linha do tempo da solicitação' });
  await expect(linha.locator('li[aria-current="step"]')).toHaveCount(1);
  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);

  await page.getByRole('button', { name: 'Cancelar solicitação' }).click();
  const dialogo = page.getByRole('alertdialog', { name: 'Cancelar esta solicitação?' });
  await expect(dialogo).toBeVisible();
  expect(await auditarAxe(page)).toEqual([]);
  await dialogo.getByLabel('Motivo (opcional)').fill('Resolvi por outro canal');
  await dialogo.getByRole('button', { name: 'Cancelar solicitação' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Solicitação cancelada' })).toBeVisible();
  await expect(page.locator('.status-solicitacao').first()).toHaveText('Cancelada');
  await expect(page.getByRole('button', { name: 'Cancelar solicitação' })).toHaveCount(0);

  await page.goto('/area/solicitacoes');
  await page.getByRole('tab', { name: 'Encerradas' }).click();
  await expect(page.getByRole('list', { name: 'Solicitações encerradas' }).getByText('Cancelada').first()).toBeVisible();
  expect(await auditarAxe(page)).toEqual([]);
  expect(violacoes).toEqual([]);
});

test('carteirinha: número de associado e downloads PNG e PDF de mesma origem', async ({ page }) => {
  const violacoes = await vigiarCsp(page);
  await entrarNovo(page, '/area/carteirinha');
  const cartao = page.getByRole('figure', { name: /Carteirinha digital de TELMA NOGUEIRA/ });
  await expect(cartao).toBeVisible();
  await expect(cartao.getByText(/^Associado nº \S+$/)).toBeVisible();

  const imagem = page.getByRole('link', { name: 'Baixar imagem' });
  const pdf = page.getByRole('link', { name: 'Baixar PDF' });
  await expect(imagem).toHaveAttribute('download', '');
  await expect(pdf).toHaveAttribute('download', '');

  const [baixado] = await Promise.all([page.waitForEvent('download'), imagem.click()]);
  expect(baixado.suggestedFilename()).toMatch(/\.png$/);

  const respostaPng = await page.request.get('/api/v1/carteirinha/imagem.png');
  expect(respostaPng.status()).toBe(200);
  expect(respostaPng.headers()['content-type']).toMatch(/^image\/png/);
  expect(respostaPng.headers()['content-disposition']).toMatch(/^attachment/);
  expect(respostaPng.headers()['cache-control']).toMatch(/no-store/);

  const respostaPdf = await page.request.get('/api/v1/carteirinha/documento.pdf');
  expect(respostaPdf.status()).toBe(200);
  expect(respostaPdf.headers()['content-type']).toMatch(/^application\/pdf/);
  expect(respostaPdf.headers()['content-disposition']).toMatch(/^attachment/);
  expect((await respostaPdf.body()).subarray(0, 5).toString('latin1')).toBe('%PDF-');

  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);
  expect(violacoes).toEqual([]);
});
