# Concluído — Minha APM

Registro do que já foi feito, do mais recente para o mais antigo. Cada entrada diz o quê, onde
está e qual a evidência. Itens que saem de [PENDENCIAS.md](PENDENCIAS.md) entram aqui com a
data de conclusão e o ID original.

---

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
