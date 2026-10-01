# MEMÓRIA DO TECHLEAD: PROJETO area_associado

> **Área do Associado da APM** (`associado.apm.org.br`). Serviço web conteinerizado, exposto
> via `nginx_porteiro` na rede Docker `rede_publica`. **Não tem login próprio**: é um
> *Relying Party* OIDC do `login_associado` (`https://login.apm.org.br`), com um modo interino
> (`AUTH_MODE=stub`) para construir telas antes da virada de chave (`docs/CUTOVER.md`).
> Schema de banco **novo e exclusivo** (`area_associado`) no RDS `mysql-producao`, com **TLS
> verificado** e usuário **append-only** por privilégio.

---

## Sessão 1: STACK DE TECNOLOGIA

| Camada | Tecnologia | Observações |
|--------|-----------|-------------|
| **Linguagem** | Python 3.12 (`python:3.12-slim`) | Mesma base do `login_associado`. |
| **Backend** | FastAPI 0.115 + Gunicorn 23 / workers Uvicorn | 2 workers, bind `0.0.0.0:8000`, `--timeout 60`. |
| **Frontend** | Jinja2 SSR, CSS/fontes/ícones locais em `app/static/` | **Zero CDN**; único script é `boot.js`. CSP `script-src 'self' 'nonce-…'`, `style-src 'self'`. |
| **Autenticação** | OIDC Authorization Code + PKCE S256, client **confidencial** (`client_secret_basic`) | `app/oidc.py` com `httpx` + `pyjwt` (RS256 fixo, `iss`/`aud`/`nonce`/`exp`/`auth_time` obrigatórios). **Sem refresh token** por decisão: sessão própria; expirou → SSO silencioso no IdP. |
| **Back-channel** | `http://login_associado:8000` na `rede_publica`, header `Host: login.apm.org.br` | Evita hairpin via Cloudflare e a zona `oauth_token` (3 r/s) do edge. `iss` continua `https://login.apm.org.br`. Override: `OIDC_BACKCHANNEL_BASE_URL`. |
| **Sessão** | Cookie assinado (`SessionMiddleware`/itsdangerous), `same_site=lax`, Secure fora de `development` | Conteúdo: `sub, cid, nome, email, cpf_mask, auth_at, amr, idt, csrf`. **CPF completo, access e refresh token nunca.** Teto absoluto `SESSION_ABSOLUTE_MAX`. |
| **ORM / Driver** | SQLAlchemy 2.0 + PyMySQL 1.1 | `ssl_ca=/etc/ssl/rds/global-bundle.pem`, `ssl_verify_cert`, `ssl_verify_identity`. Bundle baixado no `Dockerfile`. |
| **Banco** | MySQL 8.4 (RDS `mysql-producao`), schema `area_associado`, usuário `apm_area` (`REQUIRE SSL`) | Grants: `SELECT, INSERT, EXECUTE` no schema. **Sem UPDATE/DELETE/DDL.** Migrações em `sql/NNN_*.sql`, aplicadas pelo operador (`docs/PROVISIONAMENTO.md`). |
| **Auditoria** | `evento_log` (append-only por privilégio), `app/audit.py` | HMAC de `sub`/IP/UA com `LOG_HASH_KEY`; `request_id` ecoado em `X-Request-Id`. CHECK na tabela recusa segredo/CPF em `detalhes`. |
| **Infra** | Docker Compose, `read_only`, tmpfs `/tmp`, `cap_drop ALL`, `no-new-privileges`, 400M, uid 10001 | Sem porta publicada. Vhost em `deploy/nginx_porteiro/area_associado.conf.example`. |

### Estrutura
```
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
deploy/nginx_porteiro/  docs/{PROVISIONAMENTO,CUTOVER}.md
```

**Fase de construção (01/10/2026 → virada):** sem DNS, sem acesso público; equipe entra por
túnel SSH ao porteiro e usa o login stub — regras em `docs/ACESSO-CONSTRUCAO.md`. A virada
(`docs/CUTOVER.md`) revoga essas regras.

Endpoints: `GET /`, `GET /auth/login[?next=&reauth=1]`, `POST /auth/login` (só stub),
`GET /auth/callback`, `GET /area`, `POST /auth/logout` (CSRF → `/oauth/logout` do IdP),
`GET /health`; internos (403 no edge): `GET /db-health`, `GET /auth-health`.

---

## Sessão 2: REGRAS DE ARQUITETURA E NEGÓCIO

1. **Zero segredos no código.** Tudo via `config.Settings` (`.env`, fora do git e da imagem).
   Proibido `os.getenv` fora de `config.py`. Cópia do `.env` no Secrets Manager `prod/area-associado/env`.
2. **SQL sempre parametrizado; identificadores validados** (`_safe_identifier` em `audit.py`).
   Sem DDL em runtime: estrutura muda por `sql/NNN_*.sql` aplicado pelo operador.
3. **id_token sempre validado por `validate_id_token`**: `algorithms=["RS256"]`, `iss`, `aud=client_id`,
   `azp`, `nonce` (tempo constante), `exp`/`iat`/`auth_time` obrigatórios, `kid` do JWKS com refetch único.
   Nunca `jwt.decode(..., options={"verify_signature": False})` em caminho de produção.
4. **Access/refresh token nunca na sessão nem no banco.** O access token morre no callback
   (após o userinfo). Se um dia a área precisar chamar API com token contínuo, nasce uma tabela
   `associado_sessao` com `GRANT UPDATE, DELETE` só nela — decisão explícita, não deriva.
5. **Fail-closed.** `userinfo` 503 → sem sessão, página 503. `sub` do userinfo ≠ `sub` do id_token →
   recusa. JWKS indisponível → recusa. Nenhum caminho abre sessão com identidade parcial.
6. **`AUTH_MODE=stub` jamais em produção.** O validador do `Settings` é a lei: com `APP_ENV=production`
   o container não sobe. Stub exige `DEV_STUB_TOKEN` (≥32), grava `amr=["stub"]` e exibe faixa.
7. **`same_site="lax"`, não `strict`**: o callback é navegação cross-site; `strict` quebra o login
   com `state_mismatch` silencioso.
8. **`evento_log` é só INSERT** (privilégio). Chaves `token/id_token/access_token/refresh_token/
   client_secret/cpf/senha/password/authorization` nunca entram em `detalhes` (filtro + CHECK).
   Identidade só como HMAC. Auditoria nunca derruba a resposta ao associado.
9. **TLS verificado no RDS.** `DB_SSL_VERIFY=0` só fora de produção. Bundle ausente → falha no boot.
10. **`next` só por `safe_next`**: caminho relativo, sem `//`, `\`, esquema, controle ou `/auth/`.
11. **Menor privilégio na infra**: não-root, porta > 1024, `read_only`, sem `ports:`. Rota nova
    interna → `return 403` no vhost. Rota pública nova → `limit_req` no vhost.
12. **Separação por módulo.** Rota não fala HTTP com o IdP nem SQL: delega a `oidc.py`/`audit.py`.
    Chamadas bloqueantes nas rotas vão por `run_in_threadpool`.

---

## Sessão 3: O FLUXO DE SUBAGENTES

| Subagente | Função | Atua em |
|-----------|--------|---------|
| **🛡️ Sentinela (AppSec / OIDC)** | Regras 1, 3–8, 10. Revisa tudo que toque sessão, callback, validação de token, CSRF, cabeçalhos, `safe_next`. | `app/oidc.py`, `app/session_guard.py`, `app/config.py`, middlewares em `app/main.py` |
| **🗄️ Atlas (DBA)** | Regras 2, 8, 9. Schema, grants por tabela, migrações com sha256, TLS do driver, `evento_log`. | `app/database.py`, `app/audit.py`, `sql/`, `docs/PROVISIONAMENTO.md` |
| **⚙️ Maestro (Backend)** | Rotas, dependências, mapas código→mensagem/HTTP, `lifespan`, `run_in_threadpool`. | `app/main.py` |
| **🎨 Vitrine (Frontend)** | Templates e CSS, autoescape, CSRF nos forms, zero inline/CDN. | `app/templates/`, `app/static/` |
| **📦 Estivador (DevOps)** | Dockerfile, compose, vhost do porteiro, scripts de verificação, cutover. | `Dockerfile`, `docker-compose.yml`, `deploy/`, `scripts/`, `docs/CUTOVER.md` |

---

## Sessão 4: COMPORTAMENTO DE ORQUESTRAÇÃO

1. **Análise + plano** antes de código, nomeando subagentes, arquivos e impactos de segurança.
2. **Aprovação explícita** antes de criar/editar qualquer arquivo. Ambíguo → perguntar.
3. **Execução por persona**, anunciando quem atua em cada trecho.
4. **Síntese final**: o que cada subagente entregou, riscos residuais, próximos passos.

**Fast-path** (executa direto e anuncia ao final): texto/CSS/comentário/doc, escopo isolado, sem
tocar autenticação/sessão (`oidc.py`, `session_guard.py`, `config.py`, middlewares), banco
(`database.py`, `audit.py`, `sql/`), segredos/`.env`, dependências, container/rede ou vhost.
**Sempre exigem plano + aprovação:** qualquer alteração nesses domínios, mesmo que pareça pequena.

Invariantes: código pronto para produção (erros, bordas, segurança, desempenho); em conflito,
**Sentinela tem precedência**; mudança fora do escopo aprovado exige novo plano.

---
*Criado em 2026-10-01. Atualizar ao mudar stack, fronteiras de módulo ou regras de segurança.*
