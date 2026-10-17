# ADR-0013: CSP sem inline no SPA

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0001, ADR-0006

## Contexto

A CSP atual, aplicada pelo middleware de cabeçalhos em `app/main.py:152-183`, é
`default-src 'self'; script-src 'self' 'nonce-…'; style-src 'self'; img-src 'self' data:;
font-src 'self'`, com nonce por requisição e **nenhum** `unsafe-inline`. Essa política é um dos
controles centrais do `CLAUDE.md` ("zero CDN", único script `boot.js`).

A spec "Minha APM" foi desenhada com práticas comuns em React que **violam** essa política:
atributos `style=""` dinâmicos (largura de barras de progresso, cor por categoria de notícia,
cor de fundo do avatar com iniciais) e imagens de notícias/eventos servidas por hosts de
terceiros (`www.apm.org.br`, CDN de mídia do WordPress). O Vite, por padrão, **não** injeta
script inline no `index.html` (só `<script type="module" src>` e `<link rel="stylesheet">`),
mas plugins e o modo *legacy* podem injetar; precisa ser verificado a cada build.

Com a SPA (ADR-0001), o SPA ganha `fetch` para a própria origem (`connect-src`), o formulário
de logout posta para o IdP (`form-action`) e a área não deve ser embutida em iframe.

## Decisão

1. CSP final, emitida pelo mesmo middleware para **todas** as respostas HTML (Jinja e SPA):

   ```
   default-src 'self';
   script-src 'self' 'nonce-<por requisição>';
   style-src 'self';
   img-src 'self' data: <CSP_IMG_HOSTS>;
   font-src 'self';
   connect-src 'self';
   frame-ancestors 'none';
   base-uri 'self';
   form-action 'self' https://login.apm.org.br;
   object-src 'none';
   manifest-src 'self'
   ```

   **Sem `unsafe-inline`, sem `unsafe-eval`, sem `strict-dynamic`** em nenhuma diretiva.
2. `CSP_IMG_HOSTS` em `Settings` (lista; padrão `https://www.apm.org.br`), validada no boot
   (só origens `https://` sem path, sem curinga de esquema). A **mesma lista** é usada pelo
   job do portal (ADR-0006) para aceitar ou recusar `imagem_url`, de modo que o cache nunca
   contenha imagem que a CSP bloquearia.
3. **Estilos dinâmicos sem inline**:
   - estados discretos (categoria, tamanho, variante) por **classes** (`.cat-ciencia`,
     `.barra--75`), definidas no CSS compilado;
   - valores contínuos (percentual de barra, cor derivada de hash) por **custom properties
     definidas via CSSOM**: `el.style.setProperty('--progresso', '72%')` no `useEffect`/`ref`,
     consumidas por `width: var(--progresso)` no CSS. O React **não** usa a prop `style={{}}`
     (o `style` serializado como atributo é bloqueado pela CSP; a mutação via CSSOM não é).
     Regra de lint `react/forbid-dom-props` com `style` proibido e `no-inline-styles`.
4. O `index.html` da SPA é entregue por `app/spa.py` com o `nonce` da requisição injetado no
   `<script type="module">` de entrada; o Vite é configurado com `build.modulePreload.polyfill
   = false` e sem plugin `legacy`, e `html.cspNonce` apontando para o placeholder substituído
   no servidor. Nenhum `<style>` inline é emitido (`build.cssCodeSplit` com `cssInjectedByJs`
   **desligado**).
5. Verificação:
   - `scripts/csp_check.py` analisa `app/static/spa/index.html` e todos os `.js` gerados, e
     **falha** se encontrar `<script>` sem `src`, `<style>`, atributos `on*=`, `style=`,
     `javascript:` ou `eval(`/`new Function(`; roda no build da imagem.
   - e2e (Playwright) instala listener `document.addEventListener('securitypolicyviolation',
     ...)` em todas as páginas e **falha o teste em qualquer violação**, além de validar o
     cabeçalho em cada resposta HTML.
   - `Content-Security-Policy-Report-Only` **não** é usado: a política é aplicada desde o
     primeiro deploy.
6. `img-src data:` permanece apenas para o favicon/avatar gerados; a miniatura de foto
   (ADR-0005) é servida de `'self'`.

## Consequências

### Positivas
- XSS no SPA não consegue executar script nem exfiltrar via `connect-src` para fora da origem.
- Clickjacking bloqueado por `frame-ancestors 'none'` (substitui `X-Frame-Options`).
- A disciplina de classes/custom properties mantém os estilos auditáveis no CSS compilado.
- Imagens de terceiros ficam sob uma única allowlist compartilhada entre CSP e job.

### Negativas / riscos
- Bibliotecas que injetam `<style>` em runtime (muitas de UI) ficam **inviáveis** — coerente
  com a decisão de não usar biblioteca de UI (ADR-0001), mas restringe escolhas futuras.
- Desenvolvedores precisam aprender o padrão CSSOM para valores contínuos; lint e `csp_check`
  são a guarda.
- Uma imagem de notícia fora de `CSP_IMG_HOSTS` aparece como placeholder; adicionar host
  exige mudança de configuração e restart.
- `form-action` fixa o IdP; mudança de domínio do `login_associado` exige ajuste aqui.

### Obrigações decorrentes
- `Settings.CSP_IMG_HOSTS` com validador; middleware em `app/main.py` lê de `Settings`.
- `scripts/csp_check.py` no `Dockerfile` após o `vite build` (build falha em violação).
- ESLint no `frontend/`: `react/forbid-dom-props` (`style`), proibição de
  `dangerouslySetInnerHTML`.
- Testes e2e com `securitypolicyviolation` em cada uma das 9 telas e nos fluxos de login/logout.
- Vhost: nenhum cabeçalho CSP adicionado pelo porteiro (evita política dupla); apenas
  `X-Content-Type-Options` e `Referrer-Policy`, como hoje.
- Atualizar `CLAUDE.md` (Sessão 1 "Frontend") com a política final.

## Alternativas descartadas

- **`'unsafe-inline'` em `style-src`.** Abre injeção de CSS (exfiltração por seletores de
  atributo, *UI redressing*) e contraria o princípio "zero inline" do projeto; o custo de usar
  classes e CSSOM é baixo.
- **Proxy de imagens na própria origem.** Permitiria `img-src 'self'` puro, mas o container é
  `read_only` sem disco para cache e passaria a buscar conteúdo externo na requisição do
  associado (SSRF e latência). A allowlist de hosts resolve com risco menor.
