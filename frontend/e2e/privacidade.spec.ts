import { expect, test, type Page } from '@playwright/test';
import { auditarAxe, semRolagemHorizontal, vigiarCsp } from './apoio';

/**
 * P13 Perfil e privacidade (ADR-0025 e ADR-0026) contra o container real (AUTH_MODE=stub,
 * migrações 000–017). Precisa das flags ligadas no banco de TESTE:
 *   UPDATE feature_flag SET ligada = 1 WHERE chave IN ('perfil_preferencias', 'lgpd_consentimentos');
 * Sem elas os cenários "ligada" são pulados e o cenário "desligada" roda (regra 19).
 *
 * A anonimização em si é do operador (`scripts/anonimizar_titular.sql`) e é ensaiada com
 * MySQL real em `tests/test_privacidade_integracao.py`; aqui o roteiro vai até o pedido.
 */

const TOKEN = process.env.E2E_STUB_TOKEN ?? '';
const ROTAS_P13 = ['/api/v1/perfil/preferencias', '/api/v1/perfil/pergunta', '/api/v1/perfil/consentimentos',
  '/api/v1/perfil/dados/pedidos'];

async function entrarNovo(page: Page, destino = '/area/perfil') {
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

async function flags(page: Page): Promise<{ preferencias: boolean; lgpd: boolean }> {
  const sessao = (await (await page.request.get('/api/v1/sessao')).json()) as {
    flags?: Record<string, boolean>;
    recursos?: Record<string, boolean>;
  };
  expect(sessao.recursos, 'aplique sql/017 no banco de teste').toMatchObject({ privacidade: true });
  return { preferencias: sessao.flags?.perfil_preferencias === true, lgpd: sessao.flags?.lgpd_consentimentos === true };
}

test('flags desligadas: perfil de sempre e rotas de P13 em 404 recurso_desligado', async ({ page }) => {
  await entrarNovo(page);
  const f = await flags(page);
  test.skip(f.preferencias || f.lgpd, 'as flags de P13 estão ligadas neste banco');
  await expect(page.getByRole('heading', { level: 1, name: 'Meu perfil' })).toBeVisible();
  for (const titulo of ['Sobre você', 'Tamanho do texto', 'Autorizações', 'Seus dados']) {
    await expect(page.getByRole('heading', { name: titulo })).toHaveCount(0);
  }
  for (const rota of ROTAS_P13) {
    const r = await page.request.get(rota);
    expect(r.status(), rota).toBe(404);
    expect(((await r.json()) as { erro: string }).erro).toBe('recurso_desligado');
  }
});

test('preferências: pergunta por visita, tratamento na saudação e tamanho do texto sem quebrar a tela', async ({ page }) => {
  const violacoes = await vigiarCsp(page);
  await entrarNovo(page);
  const f = await flags(page);
  test.skip(!f.preferencias, 'ligue perfil_preferencias no banco de teste');
  await expect(page.getByRole('heading', { level: 1, name: 'Perfil e privacidade' })).toBeVisible();

  // Complete seu perfil: a primeira pergunta é o tratamento; respondida, o bloco some nesta visita.
  const bloco = page.locator('section', { has: page.getByRole('heading', { name: 'Complete seu perfil' }) });
  await bloco.getByLabel('Como prefere ser chamado?').fill('Dra. Telma');
  await bloco.getByRole('button', { name: 'Salvar resposta' }).click();
  await expect(page.getByRole('heading', { name: 'Complete seu perfil' })).toHaveCount(0);
  const sobre = page.locator('section', { has: page.getByRole('heading', { name: 'Sobre você' }) });
  await expect(sobre.getByLabel('Como prefere ser chamado')).toHaveValue('Dra. Telma');

  // O resto do perfil pelo formulário; só o que mudou é enviado.
  await sobre.getByLabel('Hospital').check();
  await sobre.getByLabel('Tecnologia e IA').check();
  await sobre.getByLabel('Só o essencial').check();
  const [envio] = await Promise.all([
    page.waitForRequest((r) => r.url().endsWith('/api/v1/perfil/preferencias') && r.method() === 'PUT'),
    sobre.getByRole('button', { name: 'Salvar preferências' }).click(),
  ]);
  expect(envio.postDataJSON()).toEqual({ atuacao: ['hospital'], temas: ['tecnologia_ia'], frequencia: 'minima' });
  await expect(page.getByRole('status').filter({ hasText: 'Preferências salvas' })).toBeVisible();

  // Tamanho do texto: atributo no <html>, texto maior de fato, sem rolagem horizontal.
  const base = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
  await page.getByRole('group', { name: 'Tamanho do texto' }).getByRole('button', { name: 'Maior' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-fonte', 'maior');
  const maior = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
  expect(maior).toBeCloseTo(base * 1.25, 1);
  await semRolagemHorizontal(page);
  expect(await auditarAxe(page)).toEqual([]);

  // Vale para a área inteira e sobrevive à recarga (vem do servidor, não do navegador).
  await page.goto('/area');
  await expect(page.locator('html')).toHaveAttribute('data-fonte', 'maior');
  await expect(page.getByRole('heading', { name: /^Olá, Dra\. Telma\./ })).toBeVisible();
  await semRolagemHorizontal(page);
  expect(await auditarAxe(page)).toEqual([]);
  for (const rota of ['/area/carteirinha', '/area/solicitacoes', '/area/ajuda']) {
    await page.goto(rota);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await semRolagemHorizontal(page);
  }

  // Volta ao padrão para não deixar o atributo no perfil de teste.
  await page.goto('/area/perfil');
  await page.getByRole('group', { name: 'Tamanho do texto' }).getByRole('button', { name: 'Padrão' }).click();
  await expect(page.locator('html')).not.toHaveAttribute('data-fonte', /.+/);
  expect(violacoes).toEqual([]);
});

test('privacidade: autorização com histórico, baixar os dados e pedir exclusão com confirmação', async ({ page }) => {
  const violacoes = await vigiarCsp(page);
  await entrarNovo(page);
  const f = await flags(page);
  test.skip(!f.lgpd, 'ligue lgpd_consentimentos no banco de teste');

  // Autorização: concede, retira, e o histórico guarda as duas decisões.
  const autorizacoes = page.locator('section', { has: page.getByRole('heading', { name: 'Autorizações' }) });
  await expect(autorizacoes.getByText('Ofertas de parceiros por e-mail')).toBeVisible();
  await expect(autorizacoes.getByText(/WhatsApp/)).toHaveCount(0); // canal ainda não existe (regra 19)
  const caixa = autorizacoes.getByRole('checkbox', { name: 'Autorizo' });
  // A caixa só muda depois de o servidor registrar (nada "otimista"): clique, não `check()`.
  await caixa.click();
  await expect(page.getByRole('status').filter({ hasText: 'Autorização registrada' })).toBeVisible();
  await expect(caixa).toBeChecked();
  await caixa.click();
  await expect(page.getByRole('status').filter({ hasText: 'Autorização retirada' })).toBeVisible();
  await expect(caixa).not.toBeChecked();
  await autorizacoes.getByText('Histórico').click();
  await expect(autorizacoes.locator('.consentimento__linhas li')).toHaveCount(2);

  // Baixar meus dados: um arquivo JSON; em seguida o botão fica indisponível por 7 dias.
  const dados = page.locator('section', { has: page.getByRole('heading', { name: 'Seus dados' }) });
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    dados.getByRole('button', { name: 'Baixar meus dados' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^minha-apm-dados-\d{8}\.json$/);
  const fluxo = await download.createReadStream();
  const pedacos: Buffer[] = [];
  for await (const pedaco of fluxo) pedacos.push(pedaco as Buffer);
  const arquivo = JSON.parse(Buffer.concat(pedacos).toString('utf-8')) as Record<string, unknown>;
  expect(arquivo.formato).toBe('minha-apm-dados/1');
  expect((arquivo.cadastro as { nome: string }).nome).toBe('TELMA NOGUEIRA');
  expect((arquivo.consentimentos as unknown[]).length).toBe(2);
  expect(JSON.stringify(arquivo)).not.toMatch(/"cpf"|contact_id|sub_hash/);
  await expect(dados.getByText(/Um novo arquivo fica disponível em/)).toBeVisible();
  await expect(dados.getByRole('button', { name: 'Baixar meus dados' })).toBeDisabled();

  // Pedir exclusão: só com a palavra digitada; vira protocolo e solicitação acompanhável.
  await dados.getByRole('button', { name: 'Pedir exclusão' }).click();
  const dialogo = page.getByRole('alertdialog', { name: 'Pedir a exclusão dos meus dados' });
  await expect(dialogo.getByRole('button', { name: 'Pedir exclusão' })).toBeDisabled();
  expect(await auditarAxe(page)).toEqual([]);
  await dialogo.getByLabel('Para confirmar, digite EXCLUIR').fill('EXCLUIR');
  await dialogo.getByRole('button', { name: 'Pedir exclusão' }).click();
  await expect(dialogo).toHaveCount(0);
  await expect(dados.locator('.protocolo')).toHaveText(/^LGPD-\d{8}-[A-Z2-7]{6}$/);
  await semRolagemHorizontal(page);
  expect(await auditarAxe(page)).toEqual([]);

  // O pedido não apaga nada: a pessoa acompanha e pode desistir em Solicitações.
  await dados.getByRole('link', { name: 'Acompanhar ou desistir do pedido' }).click();
  await expect(page).toHaveURL(/\/area\/solicitacoes\/[0-9a-f-]{36}$/);
  await expect(page.getByText('Exclusão de dados').first()).toBeVisible();
  expect(violacoes).toEqual([]);
});
