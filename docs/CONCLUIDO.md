# Concluído — Minha APM

Registro do que já foi feito, do mais recente para o mais antigo. Cada entrada diz o quê, onde
está e qual a evidência. Itens que saem de [PENDENCIAS.md](PENDENCIAS.md) entram aqui com a
data de conclusão e o ID original.

## 📍 Ponto de parada — 2026-10-19

| Repositório | Commit | Entrega |
|---|---|---|
| area_associado | `0607974` | Estrutura inicial (RP OIDC, sessão, auditoria, banco base) |
| area_associado | `1ab497b` | Fase 0 — requisitos, ADRs 0001–0014, pendências e concluídos |
| area_associado | `55674bd` | Fase 1 — fundação da Minha APM |
| area_associado | `061d7dc` | Fase 2a — perfil, e-mail por código, foto, carteirinha, ADRs 0015–0016 |
| mcp_hub | `365a531`..`8bb3c43` | Fase 2b — escrita cercada no CRM e as 4 ferramentas da Minha APM (7 commits) |
| area_associado | `fe97d8f` + docs | Fase 2b na área — contrato, 409 do endereço, UF, `check_hub` |

**Estado verificado:** área com 144 testes de backend (MySQL real) e 44 de front; hub com 156
testes, migrações 000–005 ensaiadas em MySQL 8.4 e ponta a ponta hub + área sem Dataverse.
Nenhum CPF gravado; na trilha de escrita do hub, nenhum valor em claro.

**Ainda não feito:** implantação da área (P-23) e do hub novo (P-02); credencial e papel de
escrita no CRM (P-05); mapear flows de `contact` antes de liberar a escrita (P-29); SMTP real
(P-27). Próximo passo e responsáveis em [PENDENCIAS.md](PENDENCIAS.md), seção "Onde paramos".

---

## 2026-10-19 — Fase 2b: mcp_hub com perfil, contato e foto no CRM (código)

Dois repositórios. Provisão real pendente: P-02 (hub no RDS), P-05 (credencial e papel de
escrita) e, antes de liberar a escrita, P-29 (flows de `contact`). Até lá a área segue com
`HUB_MODE=stub`.

**Entregue no `mcp_hub`** (`SistemasTiAPM/mcp_hub`, `365a531`..`8bb3c43`, regra 1 reescrita)
- **Modelo de escrita** (`365a531`): `EfeitoFerramenta`, `TipoTitular`; o registro recusa escrita
  fora de REST, exportável, com coluna pessoal, sem titular `contact_id`, com `max_linhas ≠ 1` ou
  timeout acima de 30 s. Política: escrita só com **grant exato** (`associado.*` e `*` não liberam).
- **Escopos OAuth e taxa por conta** (`af1662c`, `sql/004`): `ferramentas:ler`/`ferramentas:escrever`
  por conta; o token só leva o que a conta tem; a cada chamada o escopo é intersectado com a
  conta atual (revoga em até 30 s); `chamadas_por_minuto` por conta (1–6000); painel com os dois.
- **Trilha de escrita** (`e1e9df9`, `sql/005`): `auditoria_escrita` com intenção **bloqueante antes**
  do PATCH e resultado depois (`ok`, `erro`, `indeterminado`), só nomes de campos + HMAC dos
  valores, imagem como bytes + sha256; `auditoria_titular_contato`; CHECK de argumentos ampliado
  (contato, telefones, e-mail, endereço, imagem, nome). Painel: auditoria por `contact_id` e
  página `/admin/escritas`. Transporte e escopo checados logo após o catálogo.
- **Conectores** (`84bc998`): `contato_por_id` sem `sol_st_cpf`; foto (`entityimage/$value?size=full`);
  Metadata do endereço (flag `CRM_ENDERECO_HABILITADO`, padrão falso, + 7 atributos de texto
  atualizáveis); conector **`dataverse_escrita`** com credencial própria (client_id diferente do de
  leitura), allowlist, `If-Match: *`, 1 retry em 401/429/503, resposta do CRM nunca repassada,
  envio sem resposta = `EscritaIndeterminada`. `check_conectores` prova o papel de cada credencial.
- **Ferramentas** (`e57f313`): `associado.perfil_consultar`, `contato_atualizar`, `foto_obter`,
  `foto_atualizar`, só REST, titular `contact_id`; UF sempre sigla; CEP gravado só com dígitos;
  409 `endereco_indisponivel` antes de qualquer PATCH; foto JPEG 512×512 ≤ 256 KiB conferida pelo
  SOF; teto de corpo por ferramenta (512 KiB só na foto e só com o escopo de escrita).
- **Docs** (`5ae7e72`): CLAUDE.md, ARQUITETURA, RUNBOOK (ordem obrigatória da provisão, desligar a
  escrita em emergência, LGPD por CPF e por contact_id), checklist de ferramenta de escrita.
- **Correções encontradas no caminho:** `scripts/db_check.py` contava qualquer erro como recusa
  (o UPDATE de prova em `auditoria_titular` dava 1054 e escondia um UPDATE concedido); agora só
  1142 vale. Negação 404 devolvia o motivo real em `erro` (permitia enumerar o catálogo); agora
  é sempre `ferramenta_inexistente` (`8bb3c43`).

**Entregue na área** (`fe97d8f`)
- `docs/CONTRATO-HUB.md` reescrito com o implementado (endereço no padrão do lead, erros 409/413/504).
- `hub.py`: UF só em sigla (antes "São Paulo" virava "SÃ"); `endereco_disponivel` fail-closed;
  409; `HUB_TIMEOUT_ESCRITA` (30 s, acima dos 25 s do hub).
- Perfil: sem disponibilidade, a tela mostra só o aviso e o endereço nunca é enviado; PUT com
  endereço sabidamente indisponível → 409 sem chamar o hub; e-mail novo limitado a 100.
- `scripts/check_hub.py`: token com os dois escopos e perfil de um contact_id de teste, sem
  imprimir valores; "sem cpf" lido da resposta crua.

**Pendências resolvidas**
- **P-28** extensão do mcp_hub (em código; provisão em P-02/P-05).
- **P-03** taxa e cota por conta de serviço (em código: `chamadas_por_minuto` novo, `cota_pii_diaria` já existia por conta).
- **P-04** parcial: `contato_por_id` e as 4 ferramentas por `contact_id` (segue aberta para as demais).

**Evidências (2026-10-19)**

| Verificação | Resultado |
|---|---|
| pytest do hub na imagem (`tests/` com MockTransport para Entra/Dataverse) | 156 passaram |
| Ensaio MySQL 8.4 descartável: hub `sql/000`–`005` com linhas antes de 004/005 | ok; `apm_mcp_hub` com INSERT nas trilhas novas e 1142 em UPDATE/DELETE; 3819 nos CHECKs novos (fase, campos, HMAC, argumentos com `contact_id`/imagem, escopos vazios, taxa 0) |
| ALTER do CHECK com linha antiga violadora | falhou inteiro (3819), CHECK antigo mantido; reaplicado depois de tratar a linha |
| `db_check` do hub contra o ensaio | OK; com UPDATE concedido em `auditoria_titular` acusa `UPDATE PERMITIDO` (antes passava) |
| Trilha real no ensaio (`registrar_intencao`/`chamada`/`resultado`) | argumentos só com HMAC; titular por contato gravado; intenção sem resultado aparece `indeterminado` |
| Ponta a ponta: hub real + MySQL, sem Dataverse | token com os 2 escopos; conta só-leitura pedindo escrever → `invalid_scope` (evento `token_escopo_negado`); `contato_atualizar` → 503 `fonte_nao_configurada` com intenção + resultado `erro` + titular; curinga sem escopo → 404 `ferramenta_inexistente`; foto 600 KiB e leitura 600 KiB → 413; `/mcp` `tools/list` sem nenhuma ferramenta da área; log do hub sem segredo, contact_id ou telefone |
| `scripts/check_hub.py` da área contra esse hub | token ok; perfil 503 `fonte_nao_configurada` (esperado sem credencial do CRM) |
| pytest da área com MySQL 8.4 real (000–007) | 144 passaram |
| Vitest + typecheck + ESLint + build do front | 44 passaram; build ok |

Não verificado aqui (fica para a provisão): Dataverse real, papel de escrita, foto no CRM
(P-30), campos do endereço (P-31). O e2e Playwright não foi rodado nesta fase (mudança de UI
restrita ao bloco do endereço, coberta no Vitest). Observação aberta: P-33.

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
