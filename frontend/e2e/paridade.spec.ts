import { expect, test, type Page } from '@playwright/test';
import { auditarAxe, semRolagemHorizontal, vigiarCsp } from './apoio';

/**
 * Paridade com o App APM (ADR-0024) contra o container real (AUTH_MODE=stub, hub simulado,
 * migrações 000–016). Precisa da flag ligada no banco de teste:
 *   UPDATE feature_flag SET ligada = 1 WHERE chave = 'solicitacoes_crm';
 * Sem ela os testes são pulados (a flag nasce desligada, regra 19).
 *
 * O hub simulado vive na memória de cada processo: o que o serviço de jobs "cria no CRM" não
 * aparece para o processo web. Por isso este roteiro vai até onde o web sozinho chega — catálogo
 * (com o grupo Seguros), abertura, lista e detalhe do pedido ainda não espelhado. Lista dos dois
 * canais e conversa são cobertas com MySQL real em `tests/test_paridade_integracao.py`, na tela em
 * `src/pages/Paridade.test.tsx` e, com o hub real, no ensaio de `docs/JOBS.md` §4c.
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

async function paridadeLigada(page: Page): Promise<boolean> {
  const sessao = (await (await page.request.get('/api/v1/sessao')).json()) as {
    flags?: Record<string, boolean>;
    recursos?: Record<string, boolean>;
  };
  expect(sessao.recursos, 'aplique sql/010..016 no banco de teste').toMatchObject({ solicitacoes: true });
  return sessao.flags?.solicitacoes_crm === true;
}

test('flag desligada: sem "Nova solicitação" e rotas novas em 404 recurso_desligado', async ({ page }) => {
  await entrarNovo(page, '/area/solicitacoes');
  test.skip(await paridadeLigada(page), 'a flag solicitacoes_crm está ligada neste banco');
  await expect(page.getByRole('link', { name: 'Nova solicitação' })).toHaveCount(0);
  const tipos = await page.request.get('/api/v1/solicitacoes/tipos');
  expect(tipos.status()).toBe(404);
  expect(((await tipos.json()) as { erro: string }).erro).toBe('recurso_desligado');
  await page.goto('/area/solicitacoes/nova');
  await expect(page.getByText('Não encontramos esta página')).toBeVisible();
});

test('Nova solicitação: catálogo com Seguros, abertura de Seguro Auto, lista e detalhe', async ({ page }, info) => {
  const violacoes = await vigiarCsp(page);
  await entrarNovo(page, '/area/solicitacoes');
  test.skip(!(await paridadeLigada(page)), "ligue a flag: UPDATE feature_flag SET ligada = 1 WHERE chave = 'solicitacoes_crm'");

  await page.getByRole('link', { name: 'Nova solicitação' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Nova solicitação' })).toBeVisible();
  const tipos = page.getByRole('list', { name: 'Tipos de solicitação' });
  await expect(tipos.getByRole('button', { name: 'Planos de Saúde' })).toBeVisible();
  await expect(tipos.getByRole('button', { name: 'Dúvidas e perguntas' })).toBeVisible();
  const grupo = tipos.getByRole('button', { name: 'Seguros', exact: true });
  await expect(grupo).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('button', { name: 'Seguro Auto' })).toHaveCount(0);
  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);

  await grupo.click();
  await expect(grupo).toHaveAttribute('aria-expanded', 'true');
  expect(await auditarAxe(page)).toEqual([]);
  await page.getByRole('button', { name: 'Seguro Auto' }).click();
  await expect(page.getByRole('heading', { name: 'Seguro Auto' })).toBeFocused();
  await expect(page.getByText('Quem responde: Equipe APM.')).toBeVisible();

  await page.getByRole('button', { name: 'Enviar solicitação' }).click();
  await expect(page.getByText(/pelo menos 10 caracteres/)).toBeVisible();
  await page.getByLabel('Conte o que você precisa').fill(`Cotação e2e ${info.project.name} ${Date.now()} para o meu carro.`);
  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);
  await page.getByRole('button', { name: 'Enviar solicitação' }).click();
  await expect(page.getByRole('heading', { name: 'Recebemos sua solicitação' })).toBeVisible();

  await page.getByRole('link', { name: 'Acompanhar esta solicitação' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Seguro Auto' })).toBeVisible();
  // Ainda não chegou ao CRM: rótulo da spec v2 e nenhuma conversa.
  await expect(page.locator('.status-solicitacao').first()).toHaveText('Recebida pela APM');
  await expect(page.getByRole('heading', { name: 'Conversa' })).toHaveCount(0);
  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);

  await page.goto('/area/solicitacoes');
  const lista = page.getByRole('list', { name: 'Solicitações em andamento' });
  await expect(lista.getByRole('link', { name: /Seguro Auto/ }).first()).toBeVisible();
  expect(await auditarAxe(page)).toEqual([]);

  // Um pedido aberto por tipo: a segunda tentativa é recusada com a mensagem do servidor.
  await page.goto('/area/solicitacoes/nova');
  await page.getByRole('button', { name: 'Seguros', exact: true }).click();
  await page.getByRole('button', { name: 'Seguro Auto' }).click();
  await page.getByLabel('Conte o que você precisa').fill('Segunda cotação para o mesmo carro, por engano.');
  await page.getByRole('button', { name: 'Enviar solicitação' }).click();
  await expect(page.getByRole('alert').filter({ hasText: /em andamento/ })).toBeVisible();
  expect(violacoes).toEqual([]);
});
