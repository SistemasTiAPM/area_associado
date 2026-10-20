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
| area_associado | `141326b` | Domínio `minha.apm.org.br` e ambiente de construção público (Fases 1, 2a e 2b no ar) |
| area_associado | este commit | Entrada pelo Login APM (`AUTH_MODE=oidc`), fim do login de construção, faixa de dados de demonstração |

**Estado verificado:** área com 144 testes de backend (MySQL real) e 44 de front; hub com 156
testes, migrações 000–005 ensaiadas em MySQL 8.4 e ponta a ponta hub + área sem Dataverse.
Nenhum CPF gravado; na trilha de escrita do hub, nenhum valor em claro.

**No ar:** `https://minha.apm.org.br`, entrada pelo Login APM; hub e SMTP ainda simulados (faixa
de demonstração para todo logado).

**Ainda não feito:** implantação do hub novo (P-02); credencial e papel de
escrita no CRM (P-05); mapear flows de `contact` antes de liberar a escrita (P-29); SMTP real
(P-27). Próximo passo e responsáveis em [PENDENCIAS.md](PENDENCIAS.md), seção "Onde paramos".

---

## 2026-10-20 — Sair leva direto ao Login APM

Pedido do usuário: depois de Sair, voltar ao formulário do Login APM, e não à página de entrada.
Decisão (opção A, só na área): o IdP só aceita o `post_logout_redirect_uri` registrado (`/`), então
o logout grava na sessão uma marca de uso único (`pos_logout`, com horário). Quando o IdP devolve o
associado para `/`, a raiz consome a marca e redireciona para `/auth/login?next=/area`; com a
sessão do IdP encerrada, aparece o formulário. Sem marca, ou com a marca vencida (5 min), `/`
mostra a página de entrada. Nenhuma mudança no IdP.

**Evidências (2026-10-20)**

| Verificação | Resultado |
|---|---|
| pytest (`test_logout_…` com a volta ao login uma vez só; `test_marca_de_logout_vencida_mostra_a_entrada`) | 139 passaram (11 de MySQL pulados) |
| Playwright e2e, 1440 e 390 px (Sair termina em `/auth/login?next=/area`) | 20 de 20 |

---

## 2026-10-20 — Área logada no visual dos mockups da agência (ADR-0017) e corrida do cookie de sessão

Pedido do usuário: a área logada deve seguir os mockups da agência. Decisões: o mockup passa a ser a
referência visual (ADR-0017; CLAUDE.md, regra 13); opção A, ou seja, só o visual das telas que já
existem, sem telas novas e sem dados inventados; menu com ícone + nome.

**Entregue — 🎨 Vitrine**
- **Fonte:** `@fontsource/sora` 5.3.0 no lugar de `@fontsource/figtree` (SPA e landing; OFL em
  `app/static/fonts/OFL-sora.txt`).
- **`tokens.css`:** paleta do mockup com variantes `-texto` medidas para AA (P-22), vidro,
  gradientes, raios. **`base.css`:** fundo com campos de cor estáticos, `.vidro`, botões em
  pílula, tags. **`shell.css`:** trilho de vidro (264 px) com ícone + nome, ativo em gradiente,
  "Meu perfil" com avatar no rodapé; cabeçalho em degradê com máscara (sobretítulo, h1 da rota,
  chamada editorial por rota em `rotas.ts`, busca de vidro, chip do perfil); drawer, nav inferior
  em pílula flutuante, FAB e toast de vidro. **`motion.css`:** 520 ms com intervalo de 90 ms.
- **Início:** hero navy com "Olá, {nome}", tipo · situação da sessão e atalhos para Carteirinha e
  Perfil; nada de valor, agenda ou recomendação sem fonte. **Carteirinha:** cartão em gradiente,
  painel "Sempre com você" (só ações que existem) e 3 cards de uso com texto neutro.
  **Perfil:** duas colunas, card de identidade (foto, nome, CRM, tipo e situação, troca de foto) e
  as seções existentes em vidro.
- Sem sino de notificações, count-up, filtro SVG de refração nem fundo sorteado por JS (ADR-0017).
- Landing `/` alinhada (Sora, paleta, campos de cor).

**Entregue — 🛡️ Sentinela (defeito encontrado no e2e)**
- **Corrida do cookie de sessão:** o middleware (`app/sessao.py`) reemitia o cookie em toda
  resposta, inclusive em `/static/`, a partir da sessão lida no começo da requisição; e o CSRF só
  nascia na primeira leitura de `/api/v1/sessao`. Uma fonte baixada em paralelo podia sobrescrever
  o cookie sem o token, e o PUT seguinte dava 403 ("Sua sessão foi atualizada"), assim como o Sair
  ("Sessão expirada"). Em tese, também podia recriar uma sessão logo depois do logout. O defeito
  existia em produção; a fonte nova o tornou mais frequente.
- Correção: `/static/` não lê nem reemite o cookie (`_PREFIXO_SEM_SESSAO`), e o CSRF nasce no login
  (`store_identity`). Testes novos reproduzem a corrida sem depender de tempo (falham sem a
  correção): `test_csrf_nasce_no_login_e_static_nao_reemite_cookie` e
  `test_static_nao_le_nem_reemite_o_cookie`.
- e2e: o teste de axe passa a medir depois do fim das animações (antes, media o texto ainda
  semitransparente); a largura do trilho passa de 248 para 264.

**Pendências:** P-22 atualizada (pares da paleta nova); P-38 ampliada (fotos dos cards); novas
P-39 (mockups versionados em `docs/mockups/`) e P-40 (`react-router` 6 com 2 avisos moderados,
anteriores a esta entrega).

**Evidências (2026-10-20)**

| Verificação | Resultado |
|---|---|
| `npm run check` (typecheck, ESLint com regras de CSP, Vitest) | 46 testes passaram, sem alteração nos testes de unidade |
| pytest na imagem, sem banco | 138 passaram (11 de MySQL pulados) |
| pytest com MySQL 8.4 descartável (`sql/000`–`007`, TLS 1.3) | 149 passaram |
| Playwright e2e na imagem `read_only`, 1440 e 390 px, depois da correção da sessão | 9 rodadas: 7 com 20/20; as 2 primeiras após o rebuild com 1 falha cada, mais lentas (2,1–2,3 min contra 1,3) e sem causa identificada (o relatório foi limpo pela rodada seguinte) |
| `evento_log` dessas 9 rodadas | 18 `csrf_recusado`, todos em `/api/v1/uso` por token: exatamente os 2 propositais por rodada; nenhuma recusa indevida, nenhum outro erro |
| axe WCAG 2.1 AA (Início, Benefícios, Carteirinha, Perfil) e violações de CSP | 0 / 0 |
| Capturas 1440 e 390 px (Início, Carteirinha, Perfil, "em construção") | aprovadas pelo usuário para publicação, sem as imagens do pacote de mockups (P-38) |

---

## 2026-10-20 — Página de entrada da Minha APM (tela "Login" do mockup)

Pedido do usuário: dos mockups da agência (`*.dc.html`), só a tela de login entra agora. Decisões
do usuário: a tela vira a **landing de `/` na área**, sem campos, porque a área é RP e não coleta
credenciais (regras 5 e 6). Fica a regra do Login APM (CPF + senha, sem "Manter conectado"). Sem
as imagens do mockup, usamos o logo existente e um hero em gradiente.

**Entregue**
- **`GET /`** (`app/main.py`): sem sessão, renderiza `entrada.html` com `Cache-Control: no-store`;
  com sessão, mantém o `303 → /area`. OIDC, `/auth/*` e sessão não mudaram. A raiz deixa de fazer
  SSO silencioso direto (um clique a mais). Pós-logout cai na landing.
- **`app/templates/entrada.html`** + **`app/static/entrada.css`**: layout do mockup (hero navy à
  esquerda, painel à direita, coluna única abaixo de 900 px). Botão "Entrar com o Login APM"
  (`/auth/login?next=/area`), "Primeiro acesso" (`{issuer}/cadastro`) e "Esqueci a senha"
  (`{issuer}/recuperar-senha`). Sem JS, sem estilo inline, sem `<form>`/`<input>`. A animação de
  entrada fica desligada em `prefers-reduced-motion`.
- **Adaptações do mockup:** Sora (Google Fonts) virou Figtree self-hosted
  (`app/static/fonts/figtree-*.woff2`, OFL em `OFL-figtree.txt`). Paleta do mockup virou tokens
  da spec (cópia comentada de `frontend/src/styles/tokens.css`). Filtro SVG `#lg-refract` e fundo
  sorteado por JS viraram CSS estático. Stats reduzidos a "95 anos" (LA-14; o resto em P-38).
  A nota de privacidade foi reescrita sem prometer um ajuste no Perfil que não existe.
- `app/templating.py`: `entrada.css` no `static_v`. Vhost e Dockerfile sem mudança (`location /`
  já tem `limit_req`).
- Docs: CLAUDE.md (endpoints, páginas Jinja, estrutura), ACESSO-CONSTRUCAO (entrada), P-24 restrito
  a stub/erro/verificar, P-38 nova.

**Evidências (2026-10-20)**

| Verificação | Resultado |
|---|---|
| pytest na imagem (`test_raiz_mostra_a_entrada_ou_vai_para_a_area`, `test_entrada_serve_css_e_fontes_locais`, logout, CSP) | 136 passaram (11 de MySQL pulados) |
| `scripts/csp_check.py` contra container local | `/` 200 `csp=ok`; resultado conforme |
| Playwright 1440 e 390 px | 0 violações de CSP, 0 erros de console, axe WCAG 2.1 AA sem violações, Figtree carregada, foco visível no 1º Tab; clique no botão leva a `/auth/login` |

---

## 2026-10-20 — Entrada pelo Login APM, sem tela de login própria

Pedido do usuário: a tela de login da área foi remodelada no Login APM, então a área deixa de
ter login próprio e integra com ele. Decisões: qualquer associado entra; a agência usa contatos
de teste no CRM (P-37); `/` vai direto ao Login APM.

**Entregue**
- **IdP** (`login_associado`, `update_client_uris --apply` + UPDATE do `audience`): client
  `area-associado` com `redirect_uri` `https://minha.apm.org.br/auth/callback`, post-logout
  `https://minha.apm.org.br/` e `audience` `https://minha.apm.org.br`. Era o último lugar onde o
  domínio antigo aparecia (o `audience` só entra no access token, que a área descarta).
- **`.env`** (backup `.env.bak-20261020-oidc`): `AUTH_MODE=oidc`, `OIDC_SCOPES` com `carteirinha`,
  **`DEV_STUB_TOKEN` removido** (o token compartilhado com a agência deixou de valer).
- **`GET /`**: sem sessão → `303 /auth/login?next=/area` (→ Login APM, SSO silencioso se já
  logado no IdP); com sessão → `/area`. `home.html` removido. Logout continua encerrando no IdP
  (`/oauth/logout`), que devolve para `/` e, portanto, ao Login APM.
- **Faixa de demonstração:** `GET /api/v1/sessao` ganhou `dados_demonstracao` (verdadeiro com
  `HUB_MODE=stub` ou `SMTP_MODE=stub`); o shell mostra "Ambiente em construção: celular,
  endereço e foto são de demonstração e não vão para o seu cadastro na APM." A faixa de
  `AUTH_MODE=stub` continua só no modo stub (testes).
- Docs: ACESSO-CONSTRUCAO reescrito (entrada pelo Login APM, contas de teste, o que é real e o
  que é demonstração), CUTOVER (pré-requisitos 3, 4 e 6 feitos; passo único só com `APP_ENV`,
  `HUB_MODE` e `SMTP_MODE`), CLAUDE.md e README.

**Pendências resolvidas**
- **P-35** URIs e `audience` do client no IdP.

**Evidências (2026-10-20)**

| Verificação | Resultado |
|---|---|
| pytest (rota `/`, `dados_demonstracao`, CSP) | 135 passaram (11 de MySQL pulados) |
| Build da imagem (`npm run check`) | 46 testes do front passaram (faixa de demonstração, sem faixa no modo normal) |
| `check_oidc` no container | OK: issuer, back-channel, `redirect_uri` novo, escopos com `carteirinha`, JWKS |
| Pela internet: `/` | 303 → `/auth/login?next=/area` → 302 → `login.apm.org.br/oauth/authorize` com `redirect_uri=https://minha.apm.org.br/auth/callback`, escopo `carteirinha`, PKCE S256; o IdP aceita (cai no formulário de login, sem erro) |
| Login ponta a ponta (Playwright, usuário de teste do CRM) | `/` → formulário do Login APM ("Você está entrando em Área do Associado") → senha → `/area` com nome, tipo Efetivo, status Ativo; sessão sem CPF e `stub=false`; faixa de demonstração visível; carteirinha com dados do CRM (UF, status); perfil sem CPF; Sair → IdP → Login APM; `/api/v1/sessao` 401 depois; zero violações de CSP |
| `evento_log` | `login_ok` com `amr=["pwd"]` e `logout`, só HMAC |

Credenciais do usuário de teste não estão em arquivo nenhum. A verificação de "11 dígitos" na
sessão apontou o número do WhatsApp da Central (`config.whatsapp`), não CPF.

---

## 2026-10-19 — `minha.apm.org.br` no ar (construção pública)

O DNS `minha.apm.org.br` (proxied) foi criado pelo usuário, e o domínio passou a ser o definitivo
da área, no lugar de `associado.apm.org.br`. O ambiente foi aberto ao público para a agência de
marketing acompanhar o progresso: qualquer um vê a página inicial e a tela de login de
construção; só entra quem tem o `DEV_STUB_TOKEN`. Atrás do login não há dado real (hub e SMTP
simulados).

**Entregue**
- **Contenção:** antes do vhost novo, o nome caía no `default_server` da 443 do porteiro e abria o
  **Sistema de Parceiros** (`apm_parceiros.conf`). Resolvido com o vhost próprio; a causa geral
  virou P-34.
- **Domínio:** `associado.apm.org.br` → `minha.apm.org.br` em config, `.env.example`, vhost, testes,
  CUTOVER, ACESSO-CONSTRUCAO (reescrito: sem túnel, acesso público com token), CLAUDE.md, README,
  REQUISITOS e ADRs.
- **Vhost público** (`deploy/nginx_porteiro/area_associado.conf.example` → `sites-enabled/`, backup
  `area_associado.conf.bak-dominio-20261019`): sem allowlist, `X-Robots-Tag: noindex, nofollow`,
  403 nos probes internos, `limit_req` por rota, foto com 6 MB só na rota dela.
- **RDS:** `sql/003`–`007` aplicadas e registradas em `schema_migrations` com sha256.
- **`.env`** (backup `.env.bak-20261019-dominio`, 600): `PUBLIC_BASE_URL`, `SESSION_ENC_KEYS` e
  `CARTEIRINHA_HMAC_KEY` novas, `HUB_MODE=stub` e `SMTP_MODE=stub` explícitos. Nenhum valor exibido.
- **Imagem** reconstruída (`DOCKER_BUILDKIT=0`) com as Fases 1, 2a e 2b; container recriado.

**Pendências resolvidas**
- **P-23** implantação das Fases 1 e 2a no ambiente de construção.
- **P-09** escopo `carteirinha` no client do IdP: o registro (`update_client_uris --show`) já o
  permite. Os URIs do client ainda são os antigos (P-35).

**Evidências (2026-10-19)**

| Verificação | Resultado |
|---|---|
| pytest da área com o domínio novo | 133 passaram (11 de MySQL pulados; a suíte com MySQL passou antes da troca) |
| Build da imagem (`npm run check` + Vitest) | 44 testes do front passaram; build ok |
| `db_check` no container contra o RDS | conforme; TLS 1.3; UPDATE só em `associado`, `associado_perfil`, `email_verificacao` |
| `nginx -t` + reload do porteiro | ok, sem `emerg`/`alert` |
| Pela internet: `/`, `/auth/login`, `/health` | 200; `/area` 303 para o login; `/db-health`, `/auth-health`, `/docs` 403; `X-Robots-Tag` em todas |
| Pela internet: jornada do login stub | login 303 → `/area` 200 (SPA, CSP sem inline) → sessão, perfil (sem CPF), carteirinha, verificação pública e QR 200; POST sem CSRF 403; logout 303 |
| Cabeçalhos pela Cloudflare (user-agent de navegador) | CSP com nonce, XFO DENY, nosniff, `no-referrer`, `no-store`, `X-Request-Id` |
| Outros sites do porteiro | parceiros, login, formulario, totalpass 200; app 302 (inalterados) |

Observação: o `scripts/csp_check.py` pela URL pública recebe 403 da **Cloudflare** (bloqueio do
user-agent `Python-urllib`). Não é a aplicação; o mesmo conjunto de cabeçalhos foi conferido
com curl.

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
