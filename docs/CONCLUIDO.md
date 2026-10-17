# Concluído — Minha APM

Registro do que já foi feito, do mais recente para o mais antigo. Cada entrada diz o quê, onde
está e qual a evidência. Itens que saem de [PENDENCIAS.md](PENDENCIAS.md) entram aqui com a
data de conclusão e o ID original.

---

## 2026-10-17 — Fase 2a: perfil e carteirinha na área (código)

Implantação no ambiente de construção pendente (P-23). Dados reais de contato e foto dependem
da Fase 2b no mcp_hub (P-28): até lá `HUB_MODE=stub`. A carteirinha já usa dados reais do CRM
pelo escopo `carteirinha` do Login APM.

**Entregue**
- **Identidade:** escopo `carteirinha` pedido por padrão; tipo, situação, CRM, UF, nº de contato
  e filiação lidos do userinfo; `auth_time` do IdP na sessão para o step-up.
- **Perfil** (`/area/perfil`, tela nova): cadastro somente leitura; contato e endereço com
  validação (DDD, celular, CEP, UF) gravados só depois do CRM confirmar; cache com degradação
  "desatualizado" quando o hub cai.
- **Troca de e-mail** com login recente no IdP e código de 6 dígitos no novo endereço, com aviso
  ao endereço antigo (ADR-0015).
- **Foto:** upload lido só depois de sessão, CSRF e limites; tipo pelos bytes mágicos; teto de
  pixels contra bomba de descompressão; recodificação sem metadados; 512 px para o CRM e
  miniatura de 128 px no avatar; remoção.
- **Carteirinha** (`/area/carteirinha`): cartão da spec, QR em SVG servido como imagem,
  Compartilhar com cópia do link (validade omitida, LA-04). **Verificação pública**
  `/verificar/{token}` com nome, situação e "verificado em", `noindex` e limite de 2 r/s.
- **Integrações:** cliente do mcp_hub (`app/integracoes/hub.py`) e simulado (`hub_stub.py`),
  envio de e-mail por SMTP/STARTTLS (`app/integracoes/email.py`), contrato em `docs/CONTRATO-HUB.md`.
- **Banco:** `sql/006_associado_perfil`, `sql/007_email_verificacao` (UPDATE por tabela); allowlist
  do `db_check` atualizada.
- **Infra:** Pillow 13.0.0 e segno 1.6.6; vhost com `client_max_body_size 6m` só na rota da foto e
  zona `area_verificar`.

**Pendências resolvidas**
- **P-20** cadastro sem tipo ou situação: recusa o login com 403 `persona_incompleta` (ADR-0016).

**Evidências (2026-10-17)**

| Verificação | Resultado |
|---|---|
| pytest com MySQL 8.4 real (migrações 000–007) | 135 passaram |
| pytest sem banco | 125 passaram, 10 de integração pulados |
| Vitest | 42 passaram |
| Playwright e2e na imagem real `read_only`, 1440 e 390 px | 20 de 20 |
| Lighthouse em Perfil e Carteirinha, autenticado | acessibilidade 100 e boas práticas 100 nas duas |
| axe (WCAG 2.1 AA) em Início, Benefícios, Carteirinha e Perfil | 0 violações |
| Varredura de CPF em `evento_log`, `evento_uso` e `associado_perfil` | 0 ocorrências |
| `db_check` (3 grants de UPDATE por tabela) e `csp_check` | conforme / conforme |
| `nginx -t` do vhost | sintaxe ok |

## 2026-10-17 — Fase 1: fundação da Minha APM (código)

Implantação no ambiente de construção pendente: P-23 (migrações no RDS, `SESSION_ENC_KEYS`,
rebuild, vhost). O container de construção segue com o esqueleto anterior até lá.

**Entregue**
- **SPA React 18 + Vite 8 + TypeScript** em `frontend/`: shell da spec (sidebar 248 px, header
  com busca, drawer acessível, bottom-nav de 5 abas, botão "Central APM", toast único, faixa do
  stub), 11 rotas reais em `/area/*` (sem `localStorage`), tokens da spec em
  `src/styles/tokens.css`, ícones SVG próprios, movimento com `prefers-reduced-motion` e
  `ANIMATIONS`. Páginas das fases 2 a 8 como "em construção".
- **Backend:** `app/sessao.py` (cookie cifrado Fernet, ADR-0011), `app/csrf.py` (header
  `X-CSRF-Token` + `Sec-Fetch-Site`/`Origin` + `Content-Type`), `app/spa.py`, `app/flags.py`,
  `app/uso.py` (catálogo fechado de 36 ações), `app/api/v1/{sessao,uso}.py`, contrato único de
  erro (`app/api/erros.py`), 401 JSON na API, CSP final com `CSP_IMG_HOSTS`,
  `Cross-Origin-Opener-Policy`, `immutable` só para assets 200, login stub com persona,
  registro de acesso em `associado`.
- **Banco:** `sql/003_feature_flag`, `sql/004_evento_uso`, `sql/005_associado` (UPDATE só em
  `associado`); `scripts/db_check.py` com allowlist de UPDATE (ADR-0004); `scripts/csp_check.py`.
- **Infra:** Dockerfile multi-stage (estágio `node:24` roda typecheck, lint e testes antes do
  build; imagem final sem Node), `.dockerignore`/`.gitignore`, vhost com zonas `area_api` e
  `area_static`, `.env.example` com as variáveis novas.

**Pendências resolvidas**
- **P-14** fontes Figtree/JetBrains Mono: `@fontsource` (OFL, `frontend/LICENSES.md`), só
  latin/latin-ext, `font-display: swap`, servidas como arquivo (sem `data:`).
- **P-17** cookie cifrado: ADR-0011 aceita e implementada.
- **P-18** defeito `html.js .alert { display:none }`: `boot.js` e a regra removidos; faixa do
  stub e erros voltam a aparecer.

**Evidências (2026-10-17)**

| Verificação | Resultado |
|---|---|
| pytest (backend, também dentro da imagem final) | 88 passaram |
| Vitest (front) | 36 passaram |
| Playwright e2e na imagem real, `read_only`, 1440 e 390 px | 16 de 16 |
| axe (WCAG 2.1 AA) em Início, Benefícios e Carteirinha | 0 violações |
| Lighthouse acessibilidade nas mesmas 3 rotas, autenticado | 100, 100, 100 |
| Violações de CSP durante o e2e | 0 |
| Migrações 000–005 num MySQL 8.4.11 descartável, como `apm_area` via TLS 1.3 | aplicadas; DELETE e UPDATE fora da allowlist recusados (1142); CHECKs recusam CPF e GUID inválido (3819) |
| `db_check` / `csp_check` contra as instâncias de teste | conforme / conforme |
| `nginx -t` do vhost (nginx 1.31.0, includes reais do porteiro) | sintaxe ok |
| Bundle inicial | JS 60 kB gz, CSS 4 kB gz (meta RNF-12: 250 kB) |

**Descobertas registradas:** P-22 (7 pares de cor da spec abaixo de AA; variantes `-texto`
criadas), P-23, P-24, P-25, P-26.

## 2026-10-17 — Fase 0: documentação de base

- **Requisitos consolidados** em [REQUISITOS-minha-apm.md](REQUISITOS-minha-apm.md): requisitos
  funcionais por tela (inclui as telas novas Perfil e Minhas solicitações), não funcionais,
  integrações por fonte, modelo de dados lógico, máquina de estados das solicitações, catálogo de
  eventos de uso, campos editáveis do perfil, feature flags, lacunas da spec e rastreabilidade.
- **14 ADRs** em [adr/](adr/), uma por decisão D-01..D-14, com índice em [adr/README.md](adr/README.md).
  A ADR-0011 (cookie cifrado) fica como Proposta até P-17.
- **Backlog** em [PENDENCIAS.md](PENDENCIAS.md) com dono, prioridade e fase bloqueada, mais o
  roteiro das fases 1 a 8.
- **CLAUDE.md** atualizado com a stack nova (SPA React + Vite, mcp_hub, cache do site, jobs), as
  regras 13 a 21, o subagente Integrador e o fast-path do front.
- **README.md** com a seção de documentação e o mapa dos novos docs.

## 2026-10-16 — Levantamento de requisitos e decisões de arquitetura

- **Levantamento** com três frentes de exploração:
  - spec × esqueleto: inventário de 24 ações, contrato de dados por fonte, 19 conflitos entre a
    spec e as regras do projeto, lacunas;
  - Dynamics 365: integrações existentes nos projetos irmãos, autenticação, entidades e campos do
    CRM e do F&O, identidade cruzada, módulos reutilizáveis (`mcp_hub/app/connectors/`);
  - TotalPass, site WordPress, IdP e infraestrutura comum.
- **Decisões do usuário** D-01..D-10: SPA React + Vite; D365 via mcp_hub para leitura e escrita;
  solicitações em MySQL próprio com espelho no CRM; UPDATE por tabela sem DELETE; foto em
  `contact.entityimage`; site WordPress lido direto do MySQL `portal_apm` com cache local; flags
  desligadas para patrocínio e fatura de valor; TotalPass via hub e deep-link; parceiros sob demanda.
- **Recomendações técnicas** D-11..D-14 (Sentinela): cookie cifrado, `evento_uso` em transação
  própria, CSP sem inline, `contact_id` como chave de integração.
- **Plano de arquitetura** por fases, aprovado. Evidência: `/home/ubuntu/.claude/plans/resilient-strolling-rossum.md`.

## 2026-10-01 — Repositório GitHub e deploy key

- Remoto `origin` em `git@github-area-associado:SistemasTiAPM/area_associado.git`
  (<https://github.com/SistemasTiAPM/area_associado>), branch `main` rastreando `origin/main`.
- Deploy key ed25519 exclusiva (`~/.ssh/id_ed25519_area_associado`, fingerprint
  `SHA256:av8tq8PaJS2sPVeZAZExLuD2MWJDC9l2NnLAaj0BlmA`) com write access, alias
  `github-area-associado` com `IdentitiesOnly yes` em `~/.ssh/config`.
- Evidência: `ssh -T git@github-area-associado` autentica como `SistemasTiAPM/area_associado`;
  primeiro push de `0607974`.

## 2026-10-01 — Spec de interface importada

- [SPEC-minha-apm.md](SPEC-minha-apm.md): protótipo navegável da Comunicação Encantada, 9 telas,
  tokens visuais, 21 componentes, contrato de dados e critérios de aceite.

## 2026-10-01 — Estrutura inicial (commit `0607974`)

- **RP OIDC** do `login_associado` (`app/oidc.py`): Authorization Code + PKCE S256, client
  confidencial `client_secret_basic`, `validate_id_token` com RS256 fixo, `iss`/`aud`/`azp`/`nonce`
  em tempo constante, `exp`/`iat`/`auth_time` obrigatórios, JWKS com refetch único por `kid`,
  userinfo fail-closed (503 → sem sessão; `sub` divergente → recusa).
- **Back-channel** pela rede Docker (`http://login_associado:8000` com `Host: login.apm.org.br`),
  sem hairpin pela Cloudflare.
- **Sessão** em cookie assinado (`same_site=lax`, teto absoluto), sem CPF completo e sem tokens;
  `safe_next` contra open redirect (`app/session_guard.py`).
- **Login stub** de construção (`AUTH_MODE=stub`), proibido em produção pelo validador do
  `Settings`, com `DEV_STUB_TOKEN` ≥ 32 e `amr=["stub"]`.
- **Banco:** schema `area_associado` e usuário `apm_area` com `REQUIRE SSL` e grants
  `SELECT, INSERT, EXECUTE` (`sql/000`); `schema_migrations` com sha256 (`sql/001`); `evento_log`
  append-only com CHECK contra segredo e CPF em `detalhes` (`sql/002`); TLS verificado no driver
  com o bundle do RDS.
- **Auditoria** (`app/audit.py`): HMAC de `sub`/IP/UA, filtro de chaves proibidas, nunca derruba
  a resposta.
- **Cabeçalhos:** CSP com nonce, `X-Frame-Options`, `nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, HSTS em produção, `X-Request-Id`.
- **Scripts:** `scripts/db_check.py` (usuário, TLS, grants) e `scripts/check_oidc.py`
  (discovery, JWKS, client).
- **Testes:** `tests/test_config.py`, `tests/test_guard.py`, `tests/test_oidc.py` com IdP e JWKS
  mockados, sem rede.
- **Infra:** Dockerfile `python:3.12-slim` com uid 10001; compose `read_only`, tmpfs `/tmp`,
  `cap_drop ALL`, `no-new-privileges`, 400M, sem `ports:`; vhost de exemplo para o
  `nginx_porteiro` com zonas `area_publico` e `area_auth` e 403 nas rotas internas.
- **Docs:** [PROVISIONAMENTO.md](PROVISIONAMENTO.md), [CUTOVER.md](CUTOVER.md),
  [ACESSO-CONSTRUCAO.md](ACESSO-CONSTRUCAO.md).

---

## Contexto externo relevante (outros projetos)

Não são entregas deste repositório, mas condicionam o trabalho aqui.

- **2026-10-16** — `mcp_hub` criado em `/home/ubuntu/mcp_hub` (catálogo de leitura sobre CRM, ERP,
  TotalPass, filiação e parceiros; REST `/api/v1/ferramentas`; OAuth `client_credentials`).
  Ainda **não provisionado** (P-02).
- **2026-10-14** — client `portal-mbe` registrado no IdP; o app registration do Dataverse que vazou
  no git do portal é compartilhado com o appapm e tem rotação pendente (fora deste projeto).
- **2026-09-10** — senha do usuário `portal_apm` rotacionada no appapm; o grant continua aberto a
  qualquer origem e sem TLS (P-07).
- **2026-09-09** — `apm_totalpass` migrado da Locaweb para o RDS `mysql-producao`.
