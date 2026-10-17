# MEMÓRIA DO TECHLEAD: PROJETO area_associado

> **Minha APM — Área do Associado da APM** (`associado.apm.org.br`). Serviço web conteinerizado,
> exposto via `nginx_porteiro` na rede Docker `rede_publica`. **Não tem login próprio**: é um
> *Relying Party* OIDC do `login_associado` (`https://login.apm.org.br`), com um modo interino
> (`AUTH_MODE=stub`) para construir telas antes da virada de chave (`docs/CUTOVER.md`).
> Interface: **SPA React (Vite) servida pelo FastAPI**. Dados do CRM e do ERP **só via `mcp_hub`**;
> conteúdo do site WordPress via **cache local** alimentado por job. Schema **exclusivo**
> (`area_associado`) no RDS `mysql-producao`, com **TLS verificado** e **UPDATE só por tabela**.

**Documentos que governam o projeto**
- `docs/SPEC-minha-apm.md` — a interface da área do associado segue esta spec; **em dúvida de
  layout, cor, texto ou comportamento de UI, a spec vence**. Em conflito com segurança, vence a
  Sentinela (regra 13).
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
| **Backend** | FastAPI 0.115 + Gunicorn 23 / workers Uvicorn | 2 workers, bind `0.0.0.0:8000`, `--timeout 60`. [atual] API JSON em `/api/v1` [alvo Fase 1]. |
| **Frontend** | **React 18 + Vite + TypeScript** em `frontend/`, build em estágio Node (`node:22-bookworm-slim`) do Dockerfile, saída em `app/static/spa/` | [alvo Fase 1] **Sem Node em runtime.** Sem biblioteca de UI e sem Tailwind: componentes próprios + `tokens.css`. Fontes Figtree e JetBrains Mono self-hosted (OFL). Ícones SVG próprios. React Router `basename="/area"` com URLs reais (sem `localStorage` de rota). ADR-0001. |
| **Páginas Jinja2** | `/` (landing), `/auth/*`, `stub_login`, `erro`, `/verificar/{token}` | [atual, parcial] Restam só as páginas fora da SPA. `boot.js` e `fonts.css` Neo Sans saem na Fase 1. |
| **Autenticação** | OIDC Authorization Code + PKCE S256, client **confidencial** (`client_secret_basic`) | [atual] `app/oidc.py` com `httpx` + `pyjwt` (RS256 fixo, `iss`/`aud`/`nonce`/`exp`/`auth_time` obrigatórios). **Sem refresh token**: sessão própria; expirou → SSO silencioso no IdP. Escopo `carteirinha` [alvo Fase 2, P-09]. |
| **Back-channel IdP** | `http://login_associado:8000` na `rede_publica`, header `Host: login.apm.org.br` | [atual] Evita hairpin via Cloudflare e a zona `oauth_token` (3 r/s) do edge. `iss` continua `https://login.apm.org.br`. |
| **Sessão** | Cookie `SessionMiddleware`, `same_site=lax`, Secure fora de `development` | [atual] assinado. [alvo Fase 1] **assinado e cifrado** (`app/sessao.py`, Fernet), nome `__Host-area` — ADR-0011, P-17. Conteúdo: `sub, cid, nome, email, cpf_mask, auth_at, amr, idt, csrf` + `tipo, status` [alvo]. **CPF completo, access e refresh token nunca.** |
| **CSRF** | Form field `csrf` [atual]; header `X-CSRF-Token` + checagem de `Origin`/`Sec-Fetch-Site` em todo método não seguro de `/api/` [alvo Fase 1] | `app/csrf.py`. Token entregue em `GET /api/v1/sessao`. |
| **Integração D365** | **`mcp_hub`** (`http://mcp_hub:8000`, `Host: mcp.apm.org.br`), OAuth `client_credentials`, REST `/api/v1/ferramentas/{nome}` | [alvo Fase 2] `app/integracoes/hub.py`. Leitura **e escrita** no CRM só pelo hub; ERP só leitura. Token do hub só em memória de processo. `HUB_MODE=real\|stub` (stub proibido em produção). ADR-0002, P-02..P-05. |
| **Site WordPress** | MySQL `portal_apm` (Locaweb), usuário somente leitura próprio | [alvo Fase 5] `app/integracoes/portal_wp.py`, **só no serviço de jobs**; o processo web nunca conecta na Locaweb. Cache em `noticia_cache`/`evento_cache`. ADR-0006, P-07. |
| **Jobs** | Serviço `area-associado-jobs`, mesma imagem, `python -m app.jobs`, 256M | [alvo Fase 3] Sincronização do portal, outbox de solicitações para o CRM, status de volta, cache de perfil. Rastro em `job_execucao`. |
| **Imagens** | Pillow (foto de perfil) | [alvo Fase 2] Em memória, magic bytes, `MAX_IMAGE_PIXELS`, 512×512 para o CRM (`entityimage`), miniatura 128×128 local. ADR-0005. |
| **ORM / Driver** | SQLAlchemy 2.0 + PyMySQL 1.1 | [atual] `ssl_ca=/etc/ssl/rds/global-bundle.pem`, `ssl_verify_cert`, `ssl_verify_identity`. Bundle baixado no `Dockerfile`. |
| **Banco** | MySQL 8.4 (RDS `mysql-producao`), schema `area_associado`, usuário `apm_area` (`REQUIRE SSL`) | [atual] `SELECT, INSERT, EXECUTE` no schema. [alvo] **`UPDATE` concedido tabela a tabela** na migração que a cria, com justificativa; **DELETE nunca**; trilhas append-only. Migrações em `sql/NNN_*.sql`, aplicadas pelo operador (`docs/PROVISIONAMENTO.md`). ADR-0004. |
| **Auditoria** | `evento_log` (append-only), `app/audit.py` | [atual] HMAC de `sub`/IP/UA com `LOG_HASH_KEY`; `request_id` ecoado em `X-Request-Id`. CHECK recusa segredo/CPF em `detalhes`. |
| **Analytics** | `evento_uso` (append-only), `app/uso.py` | [alvo Fase 1] Catálogo fechado de ações, transação própria, nunca derruba a resposta, sempre loga falha. ADR-0012. |
| **Feature flags** | Tabela `feature_flag` + `FLAGS_FORCAR_DESLIGADAS` | [alvo Fase 1] Nascem desligadas. Patrocínio, Mensalidade Zero e Fatura de valor forçadas desligadas até existir fonte (P-12). ADR-0007. |
| **Infra** | Docker Compose, `read_only`, tmpfs `/tmp`, `cap_drop ALL`, `no-new-privileges`, 400M, uid 10001 | [atual] Sem porta publicada. Vhost em `deploy/nginx_porteiro/area_associado.conf.example`. |

### Estrutura

```
[atual]
app/
  main.py          # rotas, middlewares (sessão, request_id, CSP/headers), handler de LoginRequired
  config.py        # Settings + validadores (stub×production, DB_SSL_VERIFY×production, segredos)
  database.py      # engine com TLS verificado, session_scope, get_session, tls_status
  oidc.py          # RP: PKCE, authorize_url, exchange_code, JwksCache, validate_id_token, userinfo
  session_guard.py # Associado, require_associado, safe_next, store_identity
  audit.py         # evento_log (INSERT only, nunca lança)
  templates/       # base, home, area, erro, stub_login
  static/          # style.css, fonts.css, fonts/, logo, favicons, boot.js
scripts/           # db_check.py (TLS/usuário/grants), check_oidc.py (discovery/JWKS/client)
sql/               # 000 schema+usuário, 001 schema_migrations, 002 evento_log
tests/             # config, guard, oidc (JWKS/IdP mockados — nunca toca rede)
deploy/nginx_porteiro/
docs/              # SPEC, REQUISITOS, PENDENCIAS, CONCLUIDO, adr/, PROVISIONAMENTO, CUTOVER, ACESSO-CONSTRUCAO

[alvo — fases 1 a 8, ver docs/REQUISITOS-minha-apm.md]
frontend/          # Vite + React + TS: src/{styles,api,shell,components,pages,state,lib}, public/fonts, e2e/
app/
  sessao.py spa.py csrf.py uso.py flags.py
  api/v1/          # um módulo por recurso (sessao, perfil, carteirinha, solicitacoes, beneficios, ...)
  dominio/         # regras puras + SQL parametrizado, sem HTTP
  integracoes/     # hub.py, hub_stub.py, portal_wp.py, portal_wp_stub.py
  jobs/            # agendador e jobs (portal, outbox de solicitações, sync de status, perfis)
sql/003..010       # feature_flag, evento_uso, associado/perfil, solicitacao, beneficios, conteudo_portal, comunidade/onboarding, job_execucao
scripts/           # + check_hub.py, check_portal_wp.py, csp_check.py; db_check.py com allowlist de UPDATE
```

**Fase de construção (01/10/2026 → virada):** sem DNS, sem acesso público; equipe entra por
túnel SSH ao porteiro e usa o login stub — regras em `docs/ACESSO-CONSTRUCAO.md`. A virada
(`docs/CUTOVER.md`) revoga essas regras. Bloqueio atual da virada: P-01 (certificado de origem).

**Endpoints [atual]:** `GET /`, `GET /auth/login[?next=&reauth=1]`, `POST /auth/login` (só stub),
`GET /auth/callback`, `GET /area`, `POST /auth/logout` (CSRF → `/oauth/logout` do IdP),
`GET /health`; internos (403 no edge): `GET /db-health`, `GET /auth-health`.

**Endpoints [alvo]:** `GET /area/{path}` (SPA, exige sessão), `/api/v1/*` (JSON, cookie, CSRF por
header; contrato em `docs/REQUISITOS-minha-apm.md`), `GET /verificar/{token}` (público, HTML,
só nome/status/validade). Erro único `{"erro", "mensagem", "request_id", "detalhes"?}`; sem sessão
em `/api/` → 401 JSON, nunca 303.

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
13. **A spec vence em UI; a Sentinela vence em segurança.** Layout, cor, texto e comportamento
    seguem `docs/SPEC-minha-apm.md`. Se a spec pedir algo inseguro (CDN, inline, dado em
    `localStorage`, imagem de host não listado), vale a regra de segurança e a divergência é
    registrada em `docs/PENDENCIAS.md`.
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
    `erp_financeiro`, após o parecer de licença (P-08).

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
regras 13–21, Integrador). Atualizar ao mudar stack, fronteiras de módulo ou regras de segurança.*
