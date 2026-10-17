# ADR-0001: SPA React + Vite servida pelo FastAPI

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0013

## Contexto

A especificação da nova interface "Minha APM" (`docs/SPEC-minha-apm.md`, 9 telas e 21
componentes) foi escrita presumindo uma *single-page application* em React: os componentes são
descritos como arquivos `.tsx`, há um cliente `api.ts`, um diretório `mocks/` com dados de
desenvolvimento e a navegação entre telas é persistida em `localStorage` sob a chave `mapm.page`.
As interações (filtros instantâneos, salvar/dessalvar, barras de progresso, troca de tema,
onboarding em passos) foram desenhadas para um estado de cliente reativo.

O esqueleto atual do projeto é Jinja2 SSR (`app/templates/`), com a política "zero CDN" registrada
no `CLAUDE.md`: CSP `script-src 'self' 'nonce-…'`, `style-src 'self'`, e um único script
(`app/static/boot.js`). O container roda `python:3.12-slim`, `read_only`, sem Node em runtime, e
é publicado apenas pelo `nginx_porteiro` na `rede_publica`.

Reescrever a spec inteira em templates servidor-side exigiria reinterpretar cada interação como
*round-trip* HTTP ou como JavaScript modular escrito à mão, perdendo a fidelidade ao desenho e
duplicando trabalho já feito na spec. Por outro lado, adotar React não pode relaxar a CSP, trazer
CDN, nem introduzir um processo Node em produção.

## Decisão

1. O front-end "Minha APM" é uma SPA em **React 18 + Vite + TypeScript**, no diretório
   `frontend/` do repositório.
2. O `Dockerfile` passa a ser *multi-stage*: um estágio `node:22-bookworm-slim` (arm64, mesma
   arquitetura do host) executa `npm ci` e `vite build`; o estágio final `python:3.12-slim` recebe
   apenas o resultado via `COPY --from=frontend /build/dist app/static/spa/`. **Nenhum binário
   Node existe na imagem de runtime.**
3. Sem biblioteca de UI e sem Tailwind: os 21 componentes são próprios e os tokens visuais vivem em
   `frontend/src/tokens.css` (custom properties), consumidos por CSS modules/arquivos `.css`
   compilados pelo Vite em folhas externas.
4. Fontes **Figtree** e **JetBrains Mono** são *self-hosted* em woff2 (licença OFL, pendência
   P-14 para o registro das fontes e licenças) com `font-display: swap`. Ícones são SVG inline
   próprios, componentizados; nenhuma *icon font* nem pacote externo de ícones.
5. Roteamento com **React Router** e `basename="/area"`, com URLs reais por tela
   (`/area/beneficios`, `/area/solicitacoes/{id}`, ...). A chave `localStorage['mapm.page']` da
   spec é descartada: a rota é a URL.
6. Novo módulo `app/spa.py` registra `GET /area/{path:path}` protegido por `require_associado`
   e devolve `index.html` com `Cache-Control: no-store`. Os assets gerados pelo Vite têm hash no
   nome e são servidos de `/static/spa/assets/` com `Cache-Control: public, max-age=31536000,
   immutable`.
7. Permanecem em Jinja2 as páginas que não pertencem à SPA: `/` (landing), `/auth/*`
   (login, callback, logout, stub), `/erro` e `/verificar/{token}` (carteirinha pública).
8. O `index.html` da SPA é renderizado com o `nonce` por requisição injetado na tag `<script>`
   de entrada; o Vite é configurado para **não** emitir scripts nem estilos inline
   (ver ADR-0013).

## Consequências

### Positivas
- A spec é implementada como foi desenhada; componentes, estados e interações mapeiam 1:1.
- Build reprodutível (`package-lock.json`, `npm ci`) e artefato estático auditável em
  `app/static/spa/`.
- A superfície de runtime não muda: continua um processo Python, `read_only`, sem porta publicada.
- Assets imutáveis com hash reduzem carga no porteiro e no container.

### Negativas / riscos
- Segunda toolchain (Node) no build; dependências npm precisam de auditoria (`npm audit`) e
  *pinning* no CI.
- Tempo de build da imagem aumenta; mitigado com cache de camadas do `npm ci`.
- SPA exige que toda rota de API retorne JSON e erros consistentes; o fluxo de sessão expirada
  precisa redirecionar ao `/auth/login?next=` sem perder a rota atual.
- Sem *server-side rendering* da área: primeiro *paint* depende do bundle (mitigado por
  code-splitting por tela).

### Obrigações decorrentes
- Atualizar o `CLAUDE.md` (Sessão 1, "Frontend") registrando a SPA e o estágio Node do build.
- P-14: inventariar fontes OFL e guardar as licenças em `frontend/public/fonts/LICENSE-*.txt`.
- Teste de integração: `GET /area/qualquer` sem sessão → 302 para `/auth/login?next=/area/qualquer`.
- Teste de build: imagem final não contém `node` nem `npm` (`scripts/image_check.sh`).
- `scripts/csp_check.py` (ADR-0013) deve passar sobre o `index.html` gerado.
- Vhost do porteiro: `location /static/spa/` com `expires max`; `location /area/` com
  `limit_req` como rota pública.

## Alternativas descartadas

- **Manter Jinja2 SSR + JavaScript modular próprio.** Mais aderente ao `CLAUDE.md` atual, mas
  obrigaria reescrever a spec inteira em templates e reimplementar à mão o estado reativo de
  filtros, onboarding e salvamentos, perdendo a fidelidade de interações e o trabalho já investido
  na spec.
- **HTMX.** Reduziria JavaScript, mas introduz um terceiro vendorizado e um padrão de
  interação novo na APM, sem cobrir componentes com estado rico (barras, abas, formulários
  multi-passo) sem JS adicional.
