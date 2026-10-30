# Padrão de teste por tela (TI-69)

Toda tela nova da SPA (`src/pages/<Tela>.tsx`) entra com **dois** blocos de teste, nesta ordem:

1. `src/pages/<Tela>.test.tsx` (Vitest + Testing Library) — quatro estados + eventos emitidos.
2. Um bloco em `e2e/<fase>.spec.ts` (Playwright, contra o container `AUTH_MODE=stub`) — CSP,
   axe WCAG 2.2 AA e os três viewports.

Regras que o teste precisa provar (CLAUDE.md 13, 15, 19, 20; spec v2 §3.3, §14):

- Nenhum número, valor ou recomendação sem fonte chega ao associado (regra 19): o estado
  **vazio** não inventa conteúdo e não diz "em breve".
- O estado de **erro** mostra o que aconteceu, o que fazer e o `request_id` (`EstadoErro`),
  e emite `erro_exibido` (via `useToast().mostrarErro` ou `registrarUso`).
- O estado **carregando** é anunciado (`role=status`, `aria-busy`: `Skeleton` ou `.carregando`).
- O estado de **sucesso** usa os primitivos (`SeloEstado`, `Dialogo`, `Accordion`, `Tabs`,
  `BarraProgresso`, `RadioGroup`/`CheckboxGroup`, `ImagemSegura`) — nunca cor sozinha,
  nunca `style` inline (o lint falha), nunca `<a target>` fora de `LinkExterno`.
- Cada ação registrada em `evento_uso` é uma entrada do catálogo (`AcaoUi` em `lib/analytics.ts`
  = `ACOES_UI` em `app/uso.py`); o teste confere o corpo enviado para `/api/v1/uso`.
- Texto na voz §3.3: sem exclamação, botão com verbo, "associado efetivo" (nunca "pagante").

## 1. Vitest — `src/pages/<Tela>.test.tsx`

```tsx
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { _reiniciarAnalytics, enviarFila } from '../lib/analytics';
import { fabricarSessao, montarApp, respostaJson } from '../test/utilidades';
// Tipo da resposta da API desta tela (contrato em docs/REQUISITOS §<n>; espelho de app/api/v1/<recurso>.py).
import type { <Recurso> } from '../api/<recurso>';

const ROTA = '/<caminho>';
const API = '/api/v1/<recurso>';

function <recurso>(parcial: Partial<<Recurso>> = {}): <Recurso> {
  return { /* todos os campos do contrato com valores plausíveis */ ...parcial };
}

const corpoUso = (chamadas: { url: string; init: RequestInit | undefined }[]) =>
  chamadas
    .filter((c) => c.url === '/api/v1/uso')
    .flatMap((c) => (JSON.parse(String(c.init?.body)) as { eventos: unknown[] }).eventos);

describe('<Título da tela> (P<nn>; RF-<XX>)', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('carregando: anuncia o estado e não mostra conteúdo', async () => {
    montarApp(ROTA, fabricarSessao(), (url) => (url === API ? new Promise(() => {}) as never : undefined));
    expect(await screen.findByRole('status', { busy: true })).toBeInTheDocument();
    expect(screen.queryByRole('list')).toBeNull();
  });

  it('vazio: estado sem inventar conteúdo nem "em breve"', async () => {
    montarApp(ROTA, fabricarSessao(), (url) => (url === API ? respostaJson({ itens: [] }) : undefined));
    expect(await screen.findByText(/<texto do estado vazio>/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/em breve/i);
  });

  it('erro: mensagem, request_id, tentar novamente e evento erro_exibido', async () => {
    const usuario = userEvent.setup();
    let tentativas = 0;
    const { chamadas } = montarApp(ROTA, fabricarSessao(), (url) => {
      if (url !== API) return undefined;
      tentativas += 1;
      return tentativas === 1
        ? respostaJson({ erro: 'fonte_indisponivel', mensagem: 'Não conseguimos consultar agora. Tente de novo em instantes.', request_id: 'req-1' }, 503)
        : respostaJson(<recurso>());
    });
    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('Não conseguimos consultar agora');
    expect(within(alerta).getByText('req-1')).toBeInTheDocument();
    await usuario.click(within(alerta).getByRole('button', { name: 'Tentar novamente' }));
    await waitFor(() => expect(tentativas).toBe(2));
    enviarFila(true);
    expect(corpoUso(chamadas)).toContainEqual(expect.objectContaining({ acao: 'erro_exibido' }));
  });

  it('sucesso: renderiza os dados e emite o evento da ação principal com CSRF', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp(ROTA, fabricarSessao(), (url) => (url === API ? respostaJson(<recurso>()) : undefined));
    expect(await screen.findByRole('heading', { level: 1, name: '<Título>' })).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: '<Verbo> …' }));
    enviarFila(true);
    expect(corpoUso(chamadas)).toContainEqual({ acao: '<acao_do_catalogo>', entidade: '<entidade>', entidade_id: '<id>' });
    const envio = chamadas.find((c) => c.url === '/api/v1/uso');
    expect((envio?.init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('token-csrf-teste');
  });

  it('flag desligada: rota vira "Página não encontrada" (regra 19)', async () => {
    // só para telas sob flag
    montarApp(ROTA, fabricarSessao({ flags: { <chave_flag>: false } }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument();
  });
});
```

Para sub-rota (`/beneficios/{slug}`): a página recebe `parametro` (`PropsPagina` em `App.tsx`) e
define o `h1` com `useDefinirTituloPagina(nome)`; o teste confere `document.title` e que o
`pagina_ver` enviado tem o id truncado (catálogo) ou `_` (dado pessoal) — ver `shell/subrotas.test.tsx`.

## 2. Playwright — bloco em `e2e/<fase>.spec.ts`

O arquivo roda nos projetos `desktop-1440`, `mobile-390` e `mobile-360` (e `webkit-iphone` com
`E2E_WEBKIT=1`). Importe de `./apoio`, nunca de outro `*.spec.ts`.

```ts
import { expect, test } from '@playwright/test';
import { auditarAxe, ehMobile, entrar, semRolagemHorizontal, vigiarCsp } from './apoio';

test('<tela>: fluxo principal sem violação de CSP, axe WCAG 2.2 AA, reflow', async ({ page }, info) => {
  const violacoes = await vigiarCsp(page);
  await entrar(page, 'Efetivo', '/area/<caminho>');
  await expect(page.getByRole('heading', { level: 1, name: '<Título>' })).toBeVisible();

  // fluxo principal (dados do hub/SMTP stub: determinísticos)
  await page.getByRole('button', { name: '<Verbo> …' }).click();
  await expect(page.getByRole('status').filter({ hasText: '<confirmação>' })).toBeVisible();

  // estado final auditado (espera animações e "Carregando" sumirem)
  expect(await auditarAxe(page)).toEqual([]);
  await semRolagemHorizontal(page);
  if (ehMobile(info.project.name)) {
    // alvos ≥ 44 px no controle principal da tela (spec v2 §14)
    const caixa = await page.getByRole('button', { name: '<Verbo> …' }).boundingBox();
    expect(caixa?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(violacoes).toEqual([]);
});
```

## 3. Antes de abrir o PR

- `npm run check` (typecheck + lint com as regras de CSP + Vitest) no container Node 24 — README §Testes.
- `E2E_STUB_TOKEN=… npx playwright test` contra o container `AUTH_MODE=stub` em `127.0.0.1:18000`.
- A ação nova está no catálogo dos dois lados (`AcaoUi` e `ACOES_UI`) e o teste do backend passa.
- `docs/CONCLUIDO.md` e `docs/PENDENCIAS.md` atualizados; o TI-nn do levantamento marcado.
