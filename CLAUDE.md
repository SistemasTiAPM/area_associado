# MEMÓRIA DO TECHLEAD: PROJETO area_associado

> **Minha APM — Área do Associado da APM** (`minha.apm.org.br`). Serviço web conteinerizado,
> exposto via `nginx_porteiro` na rede Docker `rede_publica`. **Não tem login próprio**: é um
> *Relying Party* OIDC do `login_associado` (`https://login.apm.org.br`), com um modo interino
> (`AUTH_MODE=stub`) para construir telas antes da virada de chave (`docs/CUTOVER.md`).
> Interface: **SPA React (Vite) servida pelo FastAPI**. Dados do CRM e do ERP **só via `mcp_hub`**;
> conteúdo do site WordPress via **cache local** alimentado por job. Schema **exclusivo**
> (`area_associado`) no RDS `mysql-producao`, com **TLS verificado** e **UPDATE só por tabela**.

**Documentos que governam o projeto**
- `docs/SPEC-minha-apm.md` — estrutura, texto e comportamento da área do associado; o **visual**
  (cor, fonte, forma, movimento) segue os mockups da agência (ADR-0017). Em conflito com
  segurança, vence a Sentinela (regra 13).
- `docs/REQUISITOS-minha-apm.md` — requisitos RF/RNF, integrações, modelo de dados, máquina de
  estados das solicitações, eventos de uso, perfil editável, flags, lacunas.
- `docs/adr/` — decisões de arquitetura (ADR-0001..0014). Mudança de decisão = ADR nova.
- `docs/PENDENCIAS.md` e `docs/CONCLUIDO.md` — **toda entrega atualiza os dois**: item resolvido
  sai de PENDENCIAS e entra em CONCLUIDO com data e evidência; descoberta nova entra em PENDENCIAS.

---

## Sessão 1: STACK DE TECNOLOGIA

Legenda: **[atual]** já implementado · **[alvo Fase N]** decidido e planejado, ainda não existe.

| Camada | Tecnologia | Observações |
|--------|-----------|-------------|
| **Linguagem** | Python 3.12 (`python:3.12-slim`) | Mesma base do `login_associado` e do `mcp_hub`. [atual] |
| **Backend** | FastAPI 0.115 + Gunicorn 23 / workers Uvicorn | 2 workers, bind `0.0.0.0:8000`, `--timeout 60`. [atual] API JSON em `/api/v1` [atual: `sessao`, `uso`; demais recursos nas fases 2–8]. |
| **Frontend** | **React 18 + Vite 8 + TypeScript 5.9** em `frontend/`, build em estágio Node (`node:24-bookworm-slim`, npm 11) do Dockerfile, saída em `app/static/spa/` | [atual] **Sem Node em runtime.** O estágio Node roda `npm run check` (typecheck, ESLint com as regras de CSP, Vitest) antes do build. Sem biblioteca de UI e sem Tailwind: componentes próprios + `tokens.css`. Visual dos mockups da agência (ADR-0017): fontes Sora e JetBrains Mono self-hosted (OFL), cards de vidro, trilho em pílula. Ícones SVG próprios. React Router `basename="/area"` com URLs reais (sem `localStorage` de rota). ADR-0001. |
| **Páginas Jinja2** | `/` (`entrada`), `/auth/*`, `stub_login` (só testes), `erro`, `/verificar/{token}` | [atual] Só as páginas fora da SPA. `/` é a landing de entrada (tela "Login" do mockup da agência, sem campos: botão para `/auth/login`, cadastro e recuperação no IdP), com Sora e a paleta do mockup em `entrada.css`, sem JS. `boot.js` removido. Demais páginas no visual antigo (Neo Sans) até P-24. |
| **Autenticação** | OIDC Authorization Code + PKCE S256, client **confidencial** (`client_secret_basic`) | [atual] `app/oidc.py` com `httpx` + `pyjwt` (RS256 fixo, `iss`/`aud`/`nonce`/`exp`/`auth_time` obrigatórios). **Sem refresh token**: sessão própria; expirou → SSO silencioso no IdP. [atual] Escopo `carteirinha` (tipo, situação, CRM, UF, filiação); sem tipo ou situação o login é recusado (ADR-0016). O client do IdP precisa permitir o escopo (P-09). |
| **Back-channel IdP** | `http://login_associado:8000` na `rede_publica`, header `Host: login.apm.org.br` | [atual] Evita hairpin via Cloudflare e a zona `oauth_token` (3 r/s) do edge. `iss` continua `https://login.apm.org.br`. |
| **Sessão** | Cookie `SessionMiddleware`, `same_site=lax`, Secure fora de `development` | [atual] **cifrado e autenticado** (`app/sessao.py`, Fernet/MultiFernet; `SESSION_ENC_KEYS` obrigatória em produção), nome `__Host-area` (`area_sessao` só em development) — ADR-0011. Conteúdo: `sub, cid, nome, email, cpf_mask, auth_at, idp_at, amr, idt, csrf, tipo, status` (`idp_at` = `auth_time` do IdP, base do step-up). **CPF completo, access e refresh token nunca.** O CSRF nasce no login (`store_identity`) e `/static/` não lê nem reemite o cookie (corrida de 2026-10-20). |
| **CSRF** | [atual] Form field `csrf` (`/auth/*`); na API, `X-CSRF-Token` + `Sec-Fetch-Site: same-origin` (ou `Origin` = `PUBLIC_BASE_URL`) + `Content-Type` JSON/multipart | `app/csrf.py` (`exigir_csrf`). Token entregue em `GET /api/v1/sessao`. Recusa vai para `evento_log` (`csrf_recusado`). |
| **Integração D365** | **`mcp_hub`** (`http://mcp_hub:8000`, `Host: mcp.apm.org.br`), OAuth `client_credentials` com `ferramentas:ler ferramentas:escrever`, REST `/api/v1/ferramentas/{nome}` | [atual] `app/integracoes/hub.py` + simulado `hub_stub.py`; contrato em `docs/CONTRATO-HUB.md`, implementado no hub na Fase 2b (`SistemasTiAPM/mcp_hub` `8bb3c43`; provisão P-02, P-05, P-29). Leitura **e escrita** no CRM só pelo hub; ERP só leitura. Token do hub só em memória de processo. Timeouts `HUB_TIMEOUT` (leitura) e `HUB_TIMEOUT_ESCRITA` (30 s). `HUB_MODE=real\|stub` (stub proibido em produção). Smoke: `scripts/check_hub.py`. ADR-0002. |
| **Site WordPress** | MySQL `portal_apm` (Locaweb), usuário somente leitura próprio | [alvo Fase 5] `app/integracoes/portal_wp.py`, **só no serviço de jobs**; o processo web nunca conecta na Locaweb. Cache em `noticia_cache`/`evento_cache`. ADR-0006, P-07. |
| **Jobs** | Serviço `area-associado-jobs`, mesma imagem, `python -m app.jobs`, 256M | [alvo Fase 3] Sincronização do portal, outbox de solicitações para o CRM, status de volta, cache de perfil. Rastro em `job_execucao`. |
| **Imagens** | Pillow 13 (foto de perfil), segno (QR em SVG) | [atual] Em memória, magic bytes, `MAX_IMAGE_PIXELS`, 512×512 para o CRM (`entityimage`), miniatura 128×128 local. ADR-0005. |
| **E-mail** | SMTP com STARTTLS (`app/integracoes/email.py`), `SMTP_MODE=real\|stub` | [atual] Código de troca de e-mail e aviso ao endereço antigo (ADR-0015). Stub proibido em produção; credencial própria pendente (P-27). |
| **ORM / Driver** | SQLAlchemy 2.0 + PyMySQL 1.1 | [atual] `ssl_ca=/etc/ssl/rds/global-bundle.pem`, `ssl_verify_cert`, `ssl_verify_identity`. Bundle baixado no `Dockerfile`. |
| **Banco** | MySQL 8.4 (RDS `mysql-producao`), schema `area_associado`, usuário `apm_area` (`REQUIRE SSL`) | [atual] `SELECT, INSERT, EXECUTE` no schema. [alvo] **`UPDATE` concedido tabela a tabela** na migração que a cria, com justificativa; **DELETE nunca**; trilhas append-only. Migrações em `sql/NNN_*.sql`, aplicadas pelo operador (`docs/PROVISIONAMENTO.md`). ADR-0004. |
| **Auditoria** | `evento_log` (append-only), `app/audit.py` | [atual] HMAC de `sub`/IP/UA com `LOG_HASH_KEY`; `request_id` ecoado em `X-Request-Id`. CHECK recusa segredo/CPF em `detalhes`. |
| **Analytics** | `evento_uso` (append-only), `app/uso.py` | [atual] Catálogo fechado de ações, transação própria, nunca derruba a resposta, sempre loga falha. ADR-0012. |
| **Feature flags** | Tabela `feature_flag` + `FLAGS_FORCAR_DESLIGADAS` | [atual] Banco fora ou tabela ausente = todas desligadas. Nascem desligadas. Patrocínio, Mensalidade Zero e Fatura de valor forçadas desligadas até existir fonte (P-12). ADR-0007. |
| **Infra** | Docker Compose, `read_only`, tmpfs `/tmp`, `cap_drop ALL`, `no-new-privileges`, 400M, uid 10001 | [atual] Sem porta publicada. Vhost em `deploy/nginx_porteiro/area_associado.conf.example`. Host sem `buildx`: construir com `DOCKER_BUILDKIT=0` (P-26). |

### Estrutura

```
[atual — até a Fase 1]
app/
  main.py          # middlewares (request_id, CSP/headers, cache), handlers HTML×JSON, /auth/*, probes
  config.py        # Settings + validadores (stub, TLS, SESSION_ENC_KEYS, CSP_IMG_HOSTS, flags, WhatsApp)
  database.py      # engine com TLS verificado, session_scope, get_session, tls_status
  oidc.py          # RP: PKCE, authorize_url, exchange_code, JwksCache, validate_id_token, userinfo
  session_guard.py # Associado (+tipo/status), require_associado, safe_next, store_identity
  sessao.py        # cookie de sessão cifrado (Fernet/MultiFernet)
  csrf.py          # token de formulário + exigir_csrf da API
  spa.py           # GET /area[/{caminho}] → index.html da SPA (exige sessão, no-store)
  flags.py         # feature flags efetivas (tabela − forçadas; falha = desligadas)
  uso.py           # evento_uso: catálogo fechado, transação própria, nunca lança
  limites.py       # limite de taxa por associado (janela deslizante, por processo)
  audit.py         # evento_log (INSERT only, nunca lança) + registrar_isolado
  templating.py    # instância única do Jinja2 (páginas fora da SPA)
  publico.py       # GET /verificar/{token} (verificação pública da carteirinha)
  api/erros.py     # contrato único de erro {erro, mensagem, request_id, detalhes?}
  api/v1/          # sessao, uso, perfil (contato, e-mail, foto), carteirinha (dados, QR, compartilhar), deps
  dominio/         # associado (acesso + pós-login), perfil (cache), foto (Pillow), carteirinha (token, QR),
                   # email_verificacao (código HMAC)
  integracoes/     # hub.py (cliente mcp_hub), hub_stub.py, email.py (SMTP)
  templates/       # entrada (landing de /), base, erro, stub_login (com persona; só testes), verificar
  static/          # entrada.css (+ Sora em fonts/), style.css, fonts.css (Neo Sans), logo, favicons; spa/ = build (gitignored)
frontend/          # Vite + React + TS: src/{styles,api,shell,components,pages,state,lib,test}, e2e/ (Playwright)
scripts/           # db_check.py (TLS, grants, allowlist de UPDATE), check_oidc.py, csp_check.py, check_hub.py
sql/               # 000–002 base; 003 feature_flag, 004 evento_uso, 005 associado, 006 associado_perfil,
                   # 007 email_verificacao (UPDATE só em 005, 006, 007)
tests/             # unidades sem rede/banco + integração com MySQL real (marcador `mysql`, TESTE_DB_*)
deploy/nginx_porteiro/
docs/              # SPEC, REQUISITOS, PENDENCIAS, CONCLUIDO, adr/, PROVISIONAMENTO, CUTOVER, ACESSO-CONSTRUCAO

[alvo — fases 2 a 8, ver docs/REQUISITOS-minha-apm.md]
app/
  api/v1/          # solicitacoes, beneficios, noticias, eventos, comunidade, onboarding, clube, ...
  dominio/         # solicitacoes, beneficios, noticias, eventos, ... (regras + SQL, sem HTTP)
  integracoes/     # portal_wp.py, portal_wp_stub.py
  jobs/            # agendador e jobs (portal, outbox de solicitações, sync de status, perfis)
sql/008..012       # solicitacao, beneficios, conteudo_portal, comunidade/onboarding, job_execucao
scripts/           # + check_portal_wp.py
```

**Fase de construção (01/10/2026 → virada):** desde 19/10 **pública em `https://minha.apm.org.br`**
(a agência acompanha o progresso), com `noindex`; desde 20/10 **entrada pelo Login APM**
(`AUTH_MODE=oidc`, qualquer associado; agência com contatos de teste, P-37). Hub e SMTP simulados:
nome, situação e CRM são reais, contato/endereço/foto são de demonstração e a sessão informa
`dados_demonstracao` (faixa no shell). `AUTH_MODE=stub` existe só para testes. Regras em
`docs/ACESSO-CONSTRUCAO.md`. A virada (`docs/CUTOVER.md`) = `APP_ENV=production` com hub e SMTP
reais (P-02, P-05, P-27, P-29) e P-01 (certificado de origem).

**Endpoints [atual]:** `GET /` (landing de entrada sem sessão, `no-store`; com sessão 303 → `/area`), `GET /auth/login[?next=&reauth=1]`, `POST /auth/login` (só stub),
`GET /auth/callback`, `GET /area` e `GET /area/{caminho}` (SPA, exige sessão), `GET /api/v1/sessao`,
`POST /api/v1/uso` (CSRF), `GET /api/v1/perfil`, `PUT /api/v1/perfil/contato`, `POST /api/v1/perfil/email`
e `/perfil/email/confirmar`, `GET|POST|DELETE /api/v1/perfil/foto`, `GET /api/v1/carteirinha`,
`GET /api/v1/carteirinha/qr.svg`, `POST /api/v1/carteirinha/compartilhar`, `GET /verificar/{token}`
(público: só nome, situação e "verificado em"), `POST /auth/logout` (CSRF → `/oauth/logout` do IdP), `GET /health`;
internos (403 no edge): `GET /db-health` (inclui `uso_falhas` e presença da SPA), `GET /auth-health`.
Erro único da API `{"erro", "mensagem", "request_id", "detalhes"?}`; sem sessão em `/api/` → 401
JSON, nunca 303.

**Endpoints [alvo]:** demais recursos de `/api/v1` (contrato em `docs/REQUISITOS-minha-apm.md`).

---

## Sessão 2: REGRAS DE ARQUITETURA E NEGÓCIO

1. **Zero segredos no código.** Tudo via `config.Settings` (`.env`, fora do git e da imagem).
   Proibido `os.getenv` fora de `config.py`. Cópia do `.env` no Secrets Manager `prod/area-associado/env`.
   No front, nenhum segredo nem URL de serviço interno: o browser só fala com a própria origem.
2. **SQL sempre parametrizado; identificadores validados** (`_safe_identifier` em `audit.py`).
   Sem DDL em runtime: estrutura muda por `sql/NNN_*.sql` aplicado pelo operador.
3. **id_token sempre validado por `validate_id_token`**: `algorithms=["RS256"]`, `iss`, `aud=client_id`,
   `azp`, `nonce` (tempo constante), `exp`/`iat`/`auth_time` obrigatórios, `kid` do JWKS com refetch único.
   Nunca `jwt.decode(..., options={"verify_signature": False})` em caminho de produção.
4. **Tokens fora da sessão e do banco.** Access/refresh token do IdP nunca na sessão nem no banco;
   o access token morre no callback (após o userinfo). O token de serviço do `mcp_hub` vive **só
   em memória de processo**, nunca em sessão, banco ou log. Se um dia a área precisar de token
   contínuo do IdP, nasce `associado_sessao` com grant próprio — decisão explícita, via ADR.
5. **Fail-closed.** `userinfo` 503 → sem sessão, página 503. `sub` do userinfo ≠ `sub` do id_token →
   recusa. JWKS indisponível → recusa. Nenhum caminho abre sessão com identidade parcial.
   Hub indisponível → 503 `fonte_indisponivel` na tela que depende dele; nada é gravado
   localmente como se o CRM tivesse aceitado.
6. **`AUTH_MODE=stub` jamais em produção.** O validador do `Settings` é a lei: com `APP_ENV=production`
   o container não sobe. Stub exige `DEV_STUB_TOKEN` (≥32), grava `amr=["stub"]` e exibe faixa.
   O mesmo vale para `HUB_MODE=stub` e `WP_MODE=stub`.
7. **`same_site="lax"`, não `strict`**: o callback é navegação cross-site; `strict` quebra o login
   com `state_mismatch` silencioso.
8. **Trilhas são só INSERT** (privilégio): `evento_log`, `evento_uso`, `solicitacao_evento`,
   `onboarding_progresso`. Chaves `token/id_token/access_token/refresh_token/client_secret/cpf/
   senha/password/authorization` nunca entram em `detalhes` (filtro + CHECK). Identidade em
   `evento_log` só como HMAC. Auditoria nunca derruba a resposta ao associado.
9. **TLS verificado no RDS.** `DB_SSL_VERIFY=0` só fora de produção. Bundle ausente → falha no boot.
10. **`next` só por `safe_next`**: caminho relativo, sem `//`, `\`, esquema, controle ou `/auth/`.
11. **Menor privilégio na infra**: não-root, porta > 1024, `read_only`, sem `ports:`. Rota nova
    interna → `return 403` no vhost. Rota pública nova → `limit_req` no vhost.
12. **Separação por módulo.** Rota não fala HTTP com IdP, hub ou portal nem escreve SQL: delega a
    `oidc.py`, `integracoes/`, `dominio/`, `audit.py`, `uso.py`. Chamadas bloqueantes nas rotas
    vão por `run_in_threadpool`.
13. **O mockup vence no visual, a spec no comportamento, a Sentinela em segurança.** Cor,
    tipografia, forma e movimento seguem os mockups da agência (ADR-0017, `tokens.css`); estrutura,
    texto e comportamento seguem `docs/SPEC-minha-apm.md`. Se um dos dois pedir algo inseguro (CDN,
    inline, JS de enfeite, dado em `localStorage`, imagem de host não listado) ou mostrar número sem
    fonte, vale a regra de segurança/dados e a divergência é registrada em `docs/PENDENCIAS.md`.
14. **UPDATE só por GRANT de tabela; DELETE nunca.** Tabela mutável recebe `GRANT UPDATE` na própria
    migração, com comentário de justificativa (molde `apm-parceiros/sql/008`). Desfazer = coluna de
    estado (`status`, `desativado_em`, `removida_em`). `scripts/db_check.py` falha se houver UPDATE
    ou DELETE no nível do schema, UPDATE fora da allowlist `TABELAS_COM_UPDATE` ou DELETE em
    qualquer tabela.
15. **CSP sem inline.** `script-src 'self'` (+ nonce só nas páginas Jinja), `style-src 'self'`, sem
    `unsafe-inline`. Estilo dinâmico por classe ou custom property via CSSOM. `img-src` só `'self'`,
    `data:` e `CSP_IMG_HOSTS`. O e2e falha em qualquer `securitypolicyviolation`. ADR-0013.
16. **Integração só em `app/integracoes/`.** Cliente com timeout explícito, erro tipado, sem seguir
    redirect, sem logar corpo de resposta de terceiro.
17. **CPF nunca entra na área.** Chave do associado em tabelas e APIs é `contact_id` (+ `sub_hash`
    para correlação). O hub resolve `contact_id → CPF` quando a fonte exige. ADR-0014.
18. **Locaweb só pelo job.** O processo web nunca abre conexão com `portal_apm`; serve do cache local.
19. **Feature flag desligada = API 404 `recurso_desligado` + UI oculta.** Flags nascem desligadas;
    nenhum valor ilustrativo da spec chega ao associado como se fosse real.
20. **`evento_uso` em transação própria.** `uso.registrar` abre `session_scope()` próprio, roda depois
    do commit do negócio, nunca lança e sempre loga a falha. Ação nova = entrada nova no catálogo.
21. **Escrita no CRM só pelo `mcp_hub`**, por ferramenta tipada com allowlist de campos. A área
    nunca fala com Dataverse ou F&O. O ERP é somente leitura e só aparece com a flag
    `erp_financeiro`, após o parecer de licença (P-08). Endereço só quando o hub diz
    `endereco_disponivel`: senão a tela mostra o aviso e o PUT responde 409
    `endereco_indisponivel` sem gravar nada do pedido. Escrita sem resposta do hub = resultado
    incerto: nada muda no cache, a próxima leitura traz o que o CRM tem.
22. **Operação que troca canal de segurança exige step-up.** Troca de e-mail: `auth_time` do IdP
    (`idp_at`) a no máximo `REAUTH_MAX_IDADE` + código no novo endereço (ADR-0015). Nunca usar
    `auth_at` (login na área), que o SSO silencioso renova sem senha.
23. **Upload só depois de sessão, CSRF e limite.** Nada de `UploadFile` como parâmetro (o FastAPI
    leria o corpo antes das dependências): ler `request.form(max_files=1)` dentro da rota. Tipo pelos
    bytes mágicos, teto de bytes e pixels, recodificação do zero (sem metadados).

---

## Sessão 3: O FLUXO DE SUBAGENTES

| Subagente | Função | Atua em |
|-----------|--------|---------|
| **🛡️ Sentinela (AppSec / OIDC)** | Regras 1, 3–8, 10, 13, 15, 17. Revisa tudo que toque sessão, callback, validação de token, CSRF, CSP, cabeçalhos, `safe_next`, upload de foto, rota pública. | `app/oidc.py`, `app/session_guard.py`, `app/sessao.py`, `app/csrf.py`, `app/config.py`, middlewares em `app/main.py` |
| **🗄️ Atlas (DBA)** | Regras 2, 8, 9, 14, 20. Schema, grants por tabela e allowlist de UPDATE, migrações com sha256, TLS do driver, trilhas. | `app/database.py`, `app/audit.py`, `app/uso.py`, `app/dominio/` (SQL), `sql/`, `scripts/db_check.py`, `docs/PROVISIONAMENTO.md` |
| **⚙️ Maestro (Backend)** | Rotas, dependências, contrato da API, mapas código→mensagem/HTTP, `lifespan`, `run_in_threadpool`, flags. | `app/main.py`, `app/api/`, `app/spa.py`, `app/flags.py` |
| **🔌 Integrador** | Regras 4, 5, 16, 18, 21. Cliente do `mcp_hub`, leitura do portal WordPress, jobs, contratos com o hub (e a extensão de escrita no repositório do hub). | `app/integracoes/`, `app/jobs/`, `scripts/check_hub.py`, `scripts/check_portal_wp.py` |
| **🎨 Vitrine (Frontend)** | SPA React, tokens, componentes da spec, a11y, movimento, toasts; templates Jinja remanescentes; zero inline/CDN. | `frontend/`, `app/templates/`, `app/static/` |
| **📦 Estivador (DevOps)** | Dockerfile multi-stage (Node + Python), compose (web + jobs), vhost do porteiro, scripts de verificação, cutover. | `Dockerfile`, `docker-compose.yml`, `deploy/`, `scripts/`, `docs/CUTOVER.md` |

---

## Sessão 4: COMPORTAMENTO DE ORQUESTRAÇÃO

1. **Análise + plano** antes de código, nomeando subagentes, arquivos e impactos de segurança.
2. **Aprovação explícita** antes de criar/editar qualquer arquivo. Ambíguo → perguntar.
3. **Execução por persona**, anunciando quem atua em cada trecho.
4. **Síntese final**: o que cada subagente entregou, riscos residuais, próximos passos, e
   `docs/PENDENCIAS.md` + `docs/CONCLUIDO.md` atualizados.

**Fast-path** (executa direto e anuncia ao final): texto/CSS/comentário/doc; componente React
ou página da SPA que **não** toque `frontend/src/api/`, sessão, CSRF ou dependências do
`package.json`; escopo isolado, sem tocar autenticação/sessão (`oidc.py`, `session_guard.py`,
`sessao.py`, `csrf.py`, `config.py`, middlewares), banco (`database.py`, `audit.py`, `uso.py`,
`dominio/`, `sql/`), API (`app/api/`), integrações e jobs (`integracoes/`, `jobs/`), segredos/`.env`,
dependências (Python ou npm), container/rede ou vhost.
**Sempre exigem plano + aprovação:** qualquer alteração nesses domínios, mesmo que pareça pequena.

Invariantes: código pronto para produção (erros, bordas, segurança, desempenho); em conflito,
**Sentinela tem precedência**; mudança fora do escopo aprovado exige novo plano.

---
*Criado em 2026-10-01. Revisado em 2026-10-17 (Fase 0 da Minha APM: stack SPA, mcp_hub, jobs,
regras 13–21, Integrador; Fase 1: fundação implementada, marcadores [atual]; Fase 2a: perfil, carteirinha, regras 22–23). Revisado em 2026-10-19 (Fase 2b: hub implementado, regra 21 com o endereço e a escrita incerta). Revisado em 2026-10-20 (landing de entrada; visual dos mockups da agência, ADR-0017, regra 13). Atualizar ao mudar stack, fronteiras de módulo ou regras de segurança.*
