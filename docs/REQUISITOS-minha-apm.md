# Requisitos — Minha APM (área do associado)

## 0. Controle do documento

| Item | Valor |
|---|---|
| Versão | 0.1 (rascunho para revisão técnica e de negócio) |
| Data | 2026-10-17 |
| Autores | Sistemas TI (William) · Claude Code (Sentinela, Atlas, Maestro, Vitrine, Estivador, Integrador) |
| Fontes | `docs/SPEC-minha-apm.md` (spec de interface, 2026-10-01, Comunicação Encantada / Sistemas TI) · plano aprovado da Fase 0 (decisões D-01..D-14, arquitetura alvo, pendências P-01..P-17, fases 1..8) · levantamento de 2026-10-16 (spec, esqueleto `area_associado`, projetos irmãos `mcp_hub`, `login_associado`, `appapm`, `totalpass`, `apm-parceiros`, `app_facial_recognition`, `nginx-proxy`) · código atual em `app/` |
| Documentos irmãos | `docs/PENDENCIAS.md` (P-xx), `docs/CONCLUIDO.md`, `docs/adr/` (ADR-0001..0014), `docs/CUTOVER.md`, `docs/PROVISIONAMENTO.md` |

**Regra de precedência.** A spec (`docs/SPEC-minha-apm.md`) vence em layout, cor, texto e
comportamento de UI. As regras de segurança (Sentinela, `CLAUDE.md` Sessão 2) vencem em qualquer
conflito, inclusive contra a spec. Decisões D-xx registradas em ADR vencem a spec quando a
alteram explicitamente (ex.: D-01 substitui `localStorage mapm.page` por URL real). Textos
marcados como **(proposta)** não existem na spec e dependem de validação (seção 11).

**Decisões**

| # | Tema | Decisão (resumo) | Status | ADR |
|---|---|---|---|---|
| D-01 | Front-end | SPA React + Vite + TS, build em estágio Node, servida como estático pelo FastAPI; URLs reais em `/area/*` | Aceita | [0001](adr/0001-spa-react-vite-servida-pelo-fastapi.md) |
| D-02 | D365 leitura | Via `mcp_hub` (REST `/api/v1/ferramentas/{nome}`, `client_credentials`) | Aceita | [0002](adr/0002-d365-via-mcp-hub-leitura-e-escrita.md) |
| D-03 | D365 escrita | Extensão do `mcp_hub` com ferramentas de escrita tipadas; a área nunca fala com o Dataverse | Aceita | [0002](adr/0002-d365-via-mcp-hub-leitura-e-escrita.md) |
| D-04 | Solicitações | MySQL próprio (`solicitacao` + `solicitacao_evento`) + espelho no CRM via hub; status sincronizado por job | Aceita | [0003](adr/0003-solicitacoes-mysql-proprio-com-espelho-crm.md) |
| D-05 | Grants | `UPDATE` por tabela de domínio (allowlist); trilhas append-only; `DELETE` nunca | Aceita | [0004](adr/0004-grant-update-por-tabela-sem-delete.md) |
| D-06 | Foto de perfil | `contact.entityimage` no CRM via hub, redimensionada no servidor (Pillow) | Aceita | [0005](adr/0005-foto-de-perfil-entityimage-redimensionada.md) |
| D-07 | Site WordPress | Leitura direta do MySQL `portal_apm` só por job, usuário RO novo, TLS se suportado, cache local | Aceita | [0006](adr/0006-site-wordpress-leitura-direta-com-cache-local.md) |
| D-08 | Mensalidade Zero / patrocínio / Fatura de valor | Feature flags desligadas até definição de negócio; UI existe oculta | Aceita | [0007](adr/0007-feature-flags-para-patrocinio-e-fatura.md) |
| D-09 | TotalPass | Adesão lida do CRM via hub (`totalpass.adesao_consultar`) + deep-link `https://totalpass.apm.org.br` | Aceita | [0008](adr/0008-totalpass-leitura-via-hub-e-deep-link.md) |
| D-10 | Parceiros | Sob demanda, fora de escopo | Aceita | [0009](adr/0009-parceiros-fora-de-escopo.md) |
| — | ERP F&O | Somente leitura via hub, após parecer de licença (P-08), atrás de flag | Aceita | [0010](adr/0010-erp-somente-leitura-pos-parecer.md) |
| D-11 | Cookie de sessão | Cifrado e autenticado (Fernet/MultiFernet), nome `__Host-area` fora de `development` | Aceita (2026-10-17) | [0011](adr/0011-cookie-de-sessao-cifrado.md) |
| D-12 | Analytics | Tabela própria `evento_uso`, gravada em transação própria, nunca derruba a resposta | Aceita | [0012](adr/0012-analytics-evento-uso-transacao-propria.md) |
| D-13 | CSP | Sem `'unsafe-inline'` em `script-src`/`style-src` no SPA; estilos dinâmicos por classe + custom properties via CSSOM | Aceita | [0013](adr/0013-csp-sem-inline-no-spa.md) |
| D-14 | Chave de integração | `contact_id` (GUID do contact) é a chave de integração; CPF nunca | Aceita | [0014](adr/0014-chave-de-integracao-contact-id-nunca-cpf.md) |

> A ADR-0010 registra a decisão do usuário sobre o ERP (levantamento de 2026-10-16), que não tem
> número D-xx próprio no plano; os números D-11..D-14 seguem a numeração do plano e mapeiam para
> ADR-0011..0014.

---

## 1. Visão e escopo

### 1.1 Objetivo e tese

Substituir o esqueleto atual (`/area` em Jinja2, `app/main.py:295`) pela **Minha APM**: SPA
autenticada em que o associado descobre, ativa e usa benefícios, acompanha notícias, eventos e
comunidades, mantém seus dados cadastrais e foto, acompanha suas solicitações à APM e porta a
carteirinha digital verificável.

Tese do produto (spec, "Visão geral"): **todo resgate acontece dentro da Minha APM**. Cada ação
relevante vira registro (`evento_uso`, seção 8) desde a primeira versão, porque a Fatura de valor
e o relatório para patrocinadores dependem desse histórico — mesmo enquanto as telas que o
consomem estão atrás de flag (D-08).

Restrições estruturais herdadas do esqueleto e mantidas: RP OIDC do `login_associado` sem login
próprio; schema exclusivo `area_associado` com TLS verificado; usuário de banco sem `DELETE`;
container `read_only`, não-root, sem porta publicada; fail-closed em autenticação e identidade.

### 1.2 Personas

A persona é a combinação `alf_tipo_associado` × `alf_status_associativo` do contact no CRM. A área
recebe ambos como **rótulos** (não códigos) pelo escopo `carteirinha` do userinfo
(`login_associado/app/userinfo.py:61-68`, claims `tipo_associado` e `associado`); a tradução
código↔rótulo abaixo é a referência do CRM.

| `alf_tipo_associado` | Rótulo | Rota inicial | Observações |
|---|---|---|---|
| 100000000 | Acadêmico | `/area/onboarding` enquanto o onboarding não estiver concluído (RF-ON-01); depois `/area` | Sem CRM médico (LA-20); tratamento sem "Dr./Dra." (LA-19); persona "João" da spec |
| 100000001 | Aspirante | `/area` | — |
| 100000002 | Efetivo | `/area` | Persona "Dra. Telma" da spec |
| 100000003 / 100000004 | Correspondente (dois códigos; rótulos exatos a confirmar no CRM) | `/area` | — |

| `alf_status_associativo` | Rótulo | Chega à área? |
|---|---|---|
| 1 | Inativo | Não |
| 2 | Ativo | **Sim**, se a última `sol_associacao` estiver Ativa (`100000001`) |
| 3 | Pendente | Não |
| 4 | Inconsistente | Não |

**Gate do IdP.** O `login_associado` só emite tokens para `alf_status_associativo == 2` com a
última `sol_associacao == 100000001`. Na prática toda sessão da área é de associado Ativo; a área
**não reimplementa** o gate, mas: (a) o teto absoluto de sessão (`SESSION_ABSOLUTE_MAX`, 12 h,
`app/session_guard.py:88`) força reavaliação no IdP; (b) a verificação pública da carteirinha
(RF-CA-03) reflete o status do cache de perfil (≤ 24 h), não o da sessão. Regras que a spec ou o
levantamento condicionam a status 3 (ex.: elegibilidade TotalPass "2 ou 3") são, na área,
equivalentes a status 2.

"Residente" (citado na spec) não existe como tipo no CRM e personas "sem patrocínio" não estão
modeladas: LA-16.

**Rota inicial.** Ao entrar em `/area` (raiz) após o login, `GET /api/v1/sessao` devolve
`rota_inicial`: `/area/onboarding` se `tipo == Acadêmico` e não há `onboarding_progresso` com o
passo `finalizar` (RF-ON-11); senão `/area`. Deep links (`/area/eventos`, etc.) são respeitados e
não sofrem redirecionamento de persona.

### 1.3 Fora de escopo nesta versão

- Regras de negócio do patrocínio, cálculo de cashback e catálogo real de parceiros (fora de escopo
  na própria spec); integração com o sistema de parceiros (D-10).
- Mensalidade Zero, Fatura de valor, economia do clube e textos de patrocínio **visíveis**: a UI é
  construída, mas fica atrás de flags desligadas até P-12 (D-08).
- Wallet Apple/Google (flag `wallet`, Fase 8, P-13).
- Posts de comunidade ("CONVERSAS EM DESTAQUE"): sem fonte; flag `comunidade_posts` desligada.
- Qualquer escrita no ERP; leitura do ERP só após P-08.
- Inscrição efetiva em eventos no site/sistema de eventos (a área registra interesse local até
  LA-06/LA-07).
- Busca de especialistas na rede de encaminhamento (LA-22), remoção de foto (LA-15), anexos em
  solicitações, notificações por e-mail/push, backoffice próprio (o atendimento acontece no CRM).
- Rastreamento do resgate efetivo no `clubapm.com.br` (LA-17): a área registra apenas o clique.
- App mobile nativo (`appapm`) e site institucional: só são fontes ou destinos de link.

---

## 2. Decisões de arquitetura

| # | Resumo de uma linha | ADR |
|---|---|---|
| D-01 | SPA React 18 + Vite + TS em `frontend/`, build multi-stage, servida em `/static/spa/`; `GET /area/{path}` devolve `index.html` com `require_associado`; sem Node em runtime; fontes self-hosted. | [0001](adr/0001-spa-react-vite-servida-pelo-fastapi.md) |
| D-02 | Leitura do D365 só pelo `mcp_hub` (REST, `client_credentials`, token em memória de processo), cliente em `app/integracoes/hub.py`. | [0002](adr/0002-d365-via-mcp-hub-leitura-e-escrita.md) |
| D-03 | Escrita no CRM só por ferramentas tipadas novas do hub (contato, foto, solicitação), com escopo `ferramentas:escrever` e auditoria de escrita no hub. | [0002](adr/0002-d365-via-mcp-hub-leitura-e-escrita.md) |
| D-04 | Solicitações nascem no MySQL próprio (fonte da verdade do pedido) e são espelhadas no CRM por outbox; o status volta do CRM por job. | [0003](adr/0003-solicitacoes-mysql-proprio-com-espelho-crm.md) |
| D-05 | `GRANT UPDATE` só nas tabelas da allowlist; `DELETE` nunca; remoção lógica por coluna; `scripts/db_check.py` falha fora da allowlist. | [0004](adr/0004-grant-update-por-tabela-sem-delete.md) |
| D-06 | Foto de perfil vive em `contact.entityimage` (512×512 JPEG); a área guarda só miniatura 128×128 em `associado_perfil`. | [0005](adr/0005-foto-de-perfil-entityimage-redimensionada.md) |
| D-07 | Conteúdo do site (`portal_apm`) entra só pelo job `sincronizar_portal` em cache local; o processo web nunca toca a Locaweb. | [0006](adr/0006-site-wordpress-leitura-direta-com-cache-local.md) |
| D-08 | `mensalidade_zero`, `fatura_valor`, `patrocinio`, `clube_economia` (e demais flags da seção 10) nascem desligadas; UI oculta + API `404 recurso_desligado`. | [0007](adr/0007-feature-flags-para-patrocinio-e-fatura.md) |
| D-09 | TotalPass: adesão lida pelo hub por `contact_id` (P-04), ativação por deep-link para `https://totalpass.apm.org.br`. | [0008](adr/0008-totalpass-leitura-via-hub-e-deep-link.md) |
| D-10 | Integração com parceiros fora de escopo; entra sob demanda com plano próprio. | [0009](adr/0009-parceiros-fora-de-escopo.md) |
| ERP | F&O somente leitura via hub (`financeiro.*`), atrás de `erp_financeiro`, após parecer de licença (P-08). | [0010](adr/0010-erp-somente-leitura-pos-parecer.md) |
| D-11 | Cookie de sessão cifrado + assinado, `__Host-area`; conteúdo deixa de ser legível em base64 (antes `idt` era legível). Aceita e implementada na Fase 1. | [0011](adr/0011-cookie-de-sessao-cifrado.md) |
| D-12 | `app/uso.py:registrar` grava `evento_uso` com `session_scope()` próprio, nunca lança; não reaproveita a sessão da rota (o `audit.registrar` faz `commit` na sessão recebida, `app/audit.py:125`). | [0012](adr/0012-analytics-evento-uso-transacao-propria.md) |
| D-13 | CSP final sem inline; E2E falha em `securitypolicyviolation`; `scripts/csp_check.py`. | [0013](adr/0013-csp-sem-inline-no-spa.md) |
| D-14 | Toda chave entre sistemas é `contact_id`; CPF não sai do IdP/hub, não é parâmetro de ferramenta chamada pela área, não é coluna, não é log. | [0014](adr/0014-chave-de-integracao-contact-id-nunca-cpf.md) |

---

## 3. Requisitos funcionais por tela

### 3.0 Convenções

**Formato de cada RF.** Descrição · Fonte de dados · Endpoint · Evento de uso (`acao`, seção 8) ·
UI (estados, rótulos e toasts — literais da spec entre aspas) · Flag · Fase · Aceite.
Endpoints sem prefixo são relativos a `/api/v1`. `[C]` = exige CSRF (RF-AU-05).
`pagina_ver` é emitido em toda troca de rota (RF-SH-01) e não é repetido em cada RF.

**Mapa de rotas (D-01: URL real substitui `localStorage mapm.page`).**

| Rota | id na spec | Título (h1 e sidebar) | Bottom-nav | Fase |
|---|---|---|---|---|
| `/area` | `home` | Início | sim ("Início") | 4 |
| `/area/beneficios` | `ben` | Meus benefícios | sim ("Benefícios") | 4 |
| `/area/clube` | `clube` | Clube de vantagens | sim ("Clube") | 6 |
| `/area/noticias` | `news` | Notícias e ciência | sim ("Notícias") | 5 |
| `/area/fatura` | `fatura` | Fatura de valor | não | 8 (flag) |
| `/area/comunidade` | `com` | Comunidade | não | 6 |
| `/area/eventos` | `evt` | Congresso e eventos | não | 5 |
| `/area/carteirinha` | `card` | Carteirinha digital | sim ("Carteirinha") | 2 |
| `/area/onboarding` | `onb` | Onboarding acadêmico | não | 6 |
| `/area/perfil` | — (nova) | Meu perfil **(proposta)** | não | 2 |
| `/area/solicitacoes` | — (nova) | Minhas solicitações **(proposta)** | não | 3 |

**Contrato de erro da API** (todas as rotas `/api/`): corpo `{"erro", "mensagem", "request_id",
"detalhes"?}`; códigos `400 entrada_invalida`, `401 nao_autenticado`, `403 csrf_invalido |
nao_permitido`, `404 nao_encontrado | recurso_desligado`, `409 estado_invalido`, `413`, `415`,
`429 limite_taxa`, `503 fonte_indisponivel`. A SPA exibe `mensagem` em toast (RF-SH-09).

---

### 3.1 Shell (SH)

**RF-SH-01 — Roteamento por URL real**
- **Descrição:** SPA com React Router; 11 rotas da tabela 3.0 em `/area/*`. `GET /area/{path:path}` serve `index.html` (`app/spa.py`) com `require_associado` e `Cache-Control: no-store`. Troca de rota rola para o topo. Rota desconhecida em `/area/*` → tela "não encontrada" dentro do shell. Rodapé "Rascunho de interface (wireframe navegável) · Comunicação Encantada para a APM · fotos e dados ilustrativos" **não** é implementado.
- **Fonte:** — · **Endpoint:** `GET /area/{path}` (HTML) · **Evento:** `pagina_ver` (ui, `entidade=rota`) · **Flag:** rota `/area/fatura` sob `fatura_valor` · **Fase:** 1
- **UI:** `<title>` = título da rota + " · Minha APM"; foco movido para o h1 na troca de rota (a11y).
- **Aceite:** todas as rotas abrem pelo menu, pelo bottom-nav e por recarga (substitui o critério "rota persistida" da spec); nenhum uso de `localStorage`; voltar/avançar do navegador funcionam.

**RF-SH-02 — Sidebar desktop**
- **Descrição:** sidebar 248 px sticky, navy, logotipo "APM" + legenda, "Minha APM / área do associado", nav vertical na ordem do mapa de rotas (Início … Carteirinha), seguida de **Meu perfil** e **Minhas solicitações** (proposta), e por último "Onboarding acadêmico" separado (`margin-top:14px`, `#7fdcc4` inativo). Rodapé: bloco "Mensalidade Zero / patrocínio ativo · 2026" e botão "Sair" (RF-AU-07).
- **Fonte:** `GET /sessao` (tipo, flags) · **Endpoint:** — · **Evento:** — · **Flag:** item Fatura oculto sem `fatura_valor`; bloco Mensalidade Zero oculto sem `mensalidade_zero` · **Fase:** 1
- **UI:** ativo fundo `--green-600` peso 700; item "Onboarding acadêmico" visível só para tipo Acadêmico (LA-21). Item "Minhas solicitações" mostra contador de solicitações em `aguardando_associado` (RF-SO-07).
- **Aceite:** em 1440 px a sidebar tem 248 px; item ativo corresponde à rota; nenhum item aponta para tela com flag desligada.

**RF-SH-03 — Header**
- **Descrição:** sticky, h1 com o título da rota, busca (RF-SH-04), pill "Mensalidade Zero ativa" (≥ 1100 px), avatar 40 px com iniciais (ou miniatura da foto, RF-PE-06) que leva a `/area/carteirinha`.
- **Fonte:** `GET /sessao` (nome, iniciais, `tem_foto`) · **Endpoint:** `GET /perfil/foto` (miniatura) · **Evento:** — · **Flag:** pill sob `mensalidade_zero` · **Fase:** 1 (foto na 2)
- **UI:** iniciais = primeira letra do primeiro e do último nome do `name` do IdP; cores da spec (`#f2d9c7`/`#8a4b2a`) para todos até haver regra por pessoa.
- **Aceite:** pill ausente com flag desligada; avatar navega para a carteirinha; sem foto exibe iniciais sem requisição quebrada.

**RF-SH-04 — Busca global**
- **Descrição:** campo com placeholder "Buscar benefício, parceiro, evento..." e botão × quando há texto. Em rota ≠ `ben`/`news`: digitar redireciona para `/area/beneficios` com filtro "Tudo" e categoria limpa. Em `ben`: filtra benefícios por título, descrição e grupo. Em `news`: filtra notícias por título e metadados. Limpar mantém a rota. Termo refletido em `?q=` (permite recarga).
- **Fonte:** dados já carregados de `GET /beneficios` / `GET /noticias` (filtragem no cliente, normalizada sem acento e sem caixa) · **Endpoint:** — · **Evento:** `busca_global` (ui; `detalhes`: rota, número de resultados, tamanho do termo — **o termo não é registrado**) · **Flag:** — · **Fase:** 4 (`ben`), 5 (`news`)
- **UI:** debounce 200 ms; ver RF-BE-04 para "Resultados para “{q}”".
- **Aceite:** critério da spec "Digitar no header fora de `ben`/`news` leva a `ben` com resultados filtrados; limpar filtros restaura os 4 grupos".

**RF-SH-05 — Drawer mobile**
- **Descrição:** < 900 px a sidebar vira drawer 280 px (máx. 86vw), `z-index 41`, botão × 44×44, scrim `rgba(6,30,46,.5)` que fecha ao toque; mesmo conteúdo da sidebar (incluindo Perfil, Solicitações e "Sair").
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** idem RF-SH-02 · **Fase:** 1
- **UI:** `role="dialog"`, `aria-modal="true"`, foco preso, Esc fecha, foco devolvido ao hambúrguer; fecha ao navegar.
- **Aceite:** em 390 px o hambúrguer abre o drawer com scrim; Esc e toque no scrim fecham; axe-core sem violações.

**RF-SH-06 — Bottom-nav**
- **Descrição:** < 900 px, fixo na base, 5 abas: Início, Benefícios, Clube, Notícias, Carteirinha; ícone 21 px + label; ativo `--green-600`, inativo `--ink-400`. Conteúdo com padding inferior 150 px; FAB em `bottom 84px`; toast em `bottom 140px`.
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** `aria-current="page"` na aba ativa; alvos ≥ 44 px.
- **Aceite:** critério da spec para 390 px (5 abas, busca em linha inteira, padding inferior).

**RF-SH-07 — Toast**
- **Descrição:** componente único, centralizado na base (`bottom 32px` desktop), fundo `--ink-900`, ícone check, auto-dismiss 2,6 s; uma mensagem por vez (nova substitui a anterior). Variante de erro (proposta: ícone de alerta, mesma posição) para RF-SH-09.
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** região `aria-live="polite"` (erros: `role="alert"`); animação 280 ms (RF-SH-10).
- **Aceite:** dois toasts em sequência exibem apenas o último; leitor de tela anuncia o texto.

**RF-SH-08 — Botão flutuante "Central APM" (WhatsApp)**
- **Descrição:** link fixo canto inferior direito, `#1faa59`, ícone chat + "Central APM", `https://wa.me/<WHATSAPP_CENTRAL>?text=<mensagem>` em nova aba com `rel="noopener noreferrer"`. Número padrão `551131886200`; exibição controlada por `SHOW_WHATSAPP`; ambos em `Settings`, entregues por `GET /sessao`.
- **Fonte:** `config.Settings` · **Endpoint:** `GET /sessao` · **Evento:** `central_whatsapp_abrir` (ui) · **Flag:** `SHOW_WHATSAPP` (config, não `feature_flag`) · **Fase:** 1
- **UI:** mensagem pré-preenchida não definida na spec (LA-18).
- **Aceite:** link com número da configuração, nova aba, `noopener`; oculto com `SHOW_WHATSAPP=0`.

**RF-SH-09 — Carregamento, erro e indisponibilidade**
- **Descrição:** toda tela mostra esqueleto de carregamento com proporções fixas (sem layout shift). Falha de chamada vira toast de erro com a `mensagem` da API — **nunca silenciosa**. `503 fonte_indisponivel` afeta só os blocos que dependem da fonte (ex.: perfil via hub), não o shell. `401 nao_autenticado` → navegação para `/auth/login?next=<rota atual>` (RF-AU-08). `403 csrf_invalido` → renova o token via `GET /sessao` e pede nova tentativa ao usuário (não reenvia sozinho).
- **Fonte:** — · **Endpoint:** todos · **Evento:** `erro_exibido` (ui; `detalhes.codigo`, `request_id`) · **Flag:** — · **Fase:** 1
- **UI:** mensagens por código (propostas, LA-25): `fonte_indisponivel` "Não foi possível carregar agora. Tente novamente em instantes."; `limite_taxa` "Muitas tentativas em pouco tempo. Aguarde um instante."; `csrf_invalido` "Sua sessão foi atualizada. Tente de novo."; falha de rede "Sem conexão. Verifique a internet e tente novamente."
- **Aceite:** com o hub em stub de falha, `/area/perfil` mostra o erro e as demais rotas seguem funcionais; nenhum `catch` vazio no código do front (lint).

**RF-SH-10 — Animações e movimento**
- **Descrição:** entrada de página (fade + `translateY(14px)`, 420 ms, stagger 60 ms, máx. 6), entrada de cards em filtro (fade + `translateY(8px) scale(.985)`, 320 ms, stagger 28 ms, máx. 12), toast 280 ms, drawer 300 ms/scrim 250 ms, easing `cubic-bezier(.2,.8,.2,1)`, hover de card `translateY(-3px)`.
- **Fonte:** `GET /sessao` (`animations`) · **Endpoint:** — · **Evento:** — · **Flag:** `ANIMATIONS` (config) · **Fase:** 1
- **UI:** tudo desligado com `prefers-reduced-motion: reduce` **ou** `animations=false`.
- **Aceite:** nenhuma animação roda com reduced-motion (critério da spec); Playwright verifica `getAnimations().length == 0`.

**RF-SH-11 — Feature flags na UI**
- **Descrição:** `GET /sessao` entrega o mapa de flags efetivas (`feature_flag` + `FLAGS_FORCAR_DESLIGADAS`, cache 60 s). Componente ou bloco sob flag desligada não é renderizado (nem placeholder); rota inteira sob flag desligada cai em "não encontrada".
- **Fonte:** `feature_flag` · **Endpoint:** `GET /sessao` · **Evento:** — · **Flag:** todas (seção 10) · **Fase:** 1
- **UI:** sem texto de "em breve".
- **Aceite:** com todas as flags desligadas não há referência visível a Mensalidade Zero, patrocínio, fatura, economia do clube, posts, Wallet, ERP ou TotalPass.

**RF-SH-12 — Links externos**
- **Descrição:** `clubapm.com.br`, `apm.org.br`, `totalpass.apm.org.br`, `wa.me` e links de conteúdo do site abrem em nova aba com `rel="noopener noreferrer"`; URLs externas vêm de seed/config/cache validados (esquema `https`, host em allowlist por tipo).
- **Fonte:** seeds, `Settings`, `noticia_cache`/`evento_cache` · **Endpoint:** — · **Evento:** o da ação específica · **Flag:** — · **Fase:** 1
- **UI:** ícone de link externo opcional (Vitrine).
- **Aceite:** teste unitário de componente rejeita `javascript:`/`http:`; todos os `<a target=_blank>` têm `noopener`.

**RF-SH-13 — Layout responsivo**
- **Descrição:** breakpoints < 900 px (drawer + bottom-nav), ≥ 1100 px (pill no header), ≥ 1180 px (duas colunas, aside 300–330 px); conteúdo `max-width 1320px`, padding `28px 32px 40px` (desktop) e `18px 16px 150px` (mobile); grids da spec ("Grids").
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** tokens CSS da "Fundação visual"; nenhum hex solto em componente.
- **Aceite:** sem rolagem horizontal de 390 a 1440 px (Playwright mede `scrollWidth`); critério de 1440 px da spec.

---

### 3.2 Início (HO) — `/area`

**RF-HO-01 — Saudação**
- **Descrição:** "Olá, **{nome de exibição}** — bom te ver por aqui." (15 px, `--ink-700`).
- **Fonte:** `name`/`given_name` do IdP (sessão) + `alf_sexo` e tipo do perfil · **Endpoint:** `GET /sessao` · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** nome de exibição = primeiro nome; prefixo "Dr."/"Dra." conforme LA-19 (padrão até decisão: sem prefixo).
- **Aceite:** nome nunca vazio (fallback "associado(a)" proibido; sem nome → "Olá — bom te ver por aqui."); escapado (sem HTML).

**RF-HO-02 — Card Mensalidade Zero**
- **Descrição:** card gradiente com "MENSALIDADE ZERO", badge "● ativa", "100% coberta", barra segmentada, legendas "R$ 28 você · 40%", "R$ 42 patrocínio · 60%", "total R$ 70" e nota "O patrocínio do Banco parceiro cobre 60% da sua anuidade. Você só vê o valor, nunca a fatura."
- **Fonte:** P-12 (patrocínio) + ERP para valores (P-08) · **Endpoint:** `GET /sessao` (bloco `mensalidade`, só com flag) · **Evento:** — · **Flag:** `mensalidade_zero` · **Fase:** 8
- **UI:** inconsistência "100% coberta" × 40/60 em LA-10; nunca exibir dado do patrocinador além do valor coberto.
- **Aceite:** com flag desligada o card não existe e a linha de dois cards vira um card (ou nenhum) sem buraco no grid.

**RF-HO-03 — Card Fatura de valor**
- **Descrição:** "Fatura de valor · 2026", pill "↗ 7× o que você pagou", total (ex. "R$ 2.480"), "já aproveitados em benefícios · você pagou R$ 336 no ano", 3 barras (largura proporcional ao maior valor da escala) e link "ver extrato completo →" para `/area/fatura`.
- **Fonte:** cálculo próprio sobre `beneficio_ativacao` (RF-FA-01) + valor pago via ERP (RF-FA-05) · **Endpoint:** `GET /fatura` (resumo) · **Evento:** — · **Flag:** `fatura_valor` (valor pago também `erp_financeiro`) · **Fase:** 8
- **UI:** barras agregam por grupo de benefício (LA-01); múltiplo omitido se valor pago indisponível.
- **Aceite:** com flag desligada o card não existe; com flag ligada e ERP desligado, a frase "você pagou …" e a pill somem.

**RF-HO-04 — Banner do Congresso**
- **Descrição:** bloco de data âmbar ("26 / SET"), label "CONGRESSO APM 2026 · INSCRIÇÕES ABERTAS", título "Medicina, IA e gestão: o consultório do futuro", texto "Três dias, cinco trilhas — IA, gestão, comercial, marketing e ciência. Vaga com condição de associado e certificado.", CTA "Garantir minha vaga" → "Vaga garantida ✓" (segundo clique abre `/area/eventos`), link "ver programação →" (site, nova aba).
- **Fonte:** `evento_cache` (evento marcado como Congresso) + `evento_inscricao` · **Endpoint:** `GET /eventos`, `POST /eventos/congresso/garantir-vaga [C]` · **Evento:** `congresso_garantir_vaga` (servidor), `congresso_programacao_abrir` (ui) · **Flag:** — · **Fase:** 5
- **UI:** estado compartilhado com RF-EV-02; banner oculto se não houver Congresso futuro no cache (o Congresso 2026 de 26–28/09 já ocorreu em relação a esta versão — LA-07); toast ao garantir não definido (LA-02).
- **Aceite:** garantir na home reflete em `/area/eventos` e vice-versa, também após recarga; segundo clique navega.

**RF-HO-05 — "RECOMENDADOS PARA A SUA SITUAÇÃO"**
- **Descrição:** 3 `BenefitCard` (no protótipo: Coworking médico, Escriba de IA, Antecipação de recebíveis).
- **Fonte:** `beneficio` (seleção editorial por tipo de associado no seed, LA-26) + `beneficio_ativacao` · **Endpoint:** `GET /beneficios` · **Evento:** os de RF-BE-07/08/09 · **Flag:** — · **Fase:** 4
- **UI:** mesmo comportamento de card de RF-BE-07..09.
- **Aceite:** ativar aqui reflete em `/area/beneficios` sem recarga.

**RF-HO-06 — "DESTAQUES PARA VOCÊ" (Terapia online e Clube)**
- **Descrição:** Terapia online (tag `patrocinado`, "a partir de R$ 50", "Conhecer" → `/area/beneficios?categoria=<saude>`); Clube de vantagens (tag "oferta da semana", "cashback ativo", "Ver ofertas" → `/area/clube`).
- **Fonte:** seed `beneficio` / catálogo editorial · **Endpoint:** `GET /beneficios` · **Evento:** `categoria_abrir` (ui) / `pagina_ver` · **Flag:** tag `patrocinado` sob `patrocinio`; meta "cashback ativo" sob `clube_economia` · **Fase:** 4
- **UI:** literais acima.
- **Aceite:** "Conhecer" abre benefícios com o chip de categoria removível ativo.

**RF-HO-07 — Diagnóstico de marketing**
- **Descrição:** card Marketing médico (tag `novo`, "diagnóstico grátis", "Saber mais") cria solicitação `diagnostico_marketing` (seção 7).
- **Fonte:** `solicitacao` · **Endpoint:** `POST /solicitacoes [C]` (`tipo=diagnostico_marketing`) · **Evento:** `solicitacao_criar` (servidor, `entidade=diagnostico_marketing`) · **Flag:** — · **Fase:** 4 (depende da Fase 3)
- **UI:** toast "Diagnóstico solicitado. A equipe entra em contato."; clique repetido com solicitação não terminal do mesmo tipo devolve a existente e repete o toast.
- **Aceite:** uma linha em `solicitacao` + `solicitacao_evento` + `evento_uso`; aparece em `/area/solicitacoes` como "Recebida".

**RF-HO-08 — "SEUS BENEFÍCIOS POR CATEGORIA"**
- **Descrição:** subtítulo "Todos fazem parte do seu **Clube de benefícios APM**." e 8 tiles (Tecnologia e IA, Consultório e prática, Saúde mental e bem-estar, Finanças e proteção, Educação e carreira, Defesa e jurídico, Comunidade → `/area/comunidade`, Vida e lazer → `/area/clube`), com contagem de benefícios por categoria.
- **Fonte:** `beneficio_categoria` + contagem sobre `beneficio` ativo no catálogo · **Endpoint:** `GET /beneficios` · **Evento:** `categoria_abrir` (ui) · **Flag:** — · **Fase:** 4
- **UI:** hover da spec; vocabulário de categorias em LA-01.
- **Aceite:** tile de benefício abre `/area/beneficios?categoria=<slug>` com chip removível; contagem = itens exibidos no destino.

**RF-HO-09 — "COMO FUNCIONA"**
- **Descrição:** painel "Tudo acontece dentro da Minha APM", 4 passos (Descobre / Ativa aqui / Usa / Vira valor e dado) e rodapé "Cada resgate registrado prova, em número, quanto a APM economiza para você — e sustenta o patrocínio que mantém a sua mensalidade zero."
- **Fonte:** estático · **Endpoint:** — · **Evento:** — · **Flag:** com `mensalidade_zero` desligada o rodapé termina em "…quanto a APM economiza para você." (proposta, LA-10) · **Fase:** 4
- **UI:** literais acima.
- **Aceite:** texto do rodapé varia com a flag.

**RF-HO-10 — Aside "Notícias e ciência"**
- **Descrição:** card com link "ver todas" → `/area/noticias`, chips Tudo/Notícias/Ciência e até 5 itens (thumb 62×54, tag de tipo, título, fonte).
- **Fonte:** `noticia_cache` filtrado pelos temas seguidos · **Endpoint:** `GET /noticias?limite=5` · **Evento:** `filtro_aplicar` (ui), `noticia_abrir` (ui) · **Flag:** — · **Fase:** 5
- **UI:** chips com `aria-pressed`; sem itens → bloco mostra "Nenhum conteúdo neste tema ainda.".
- **Aceite:** no máximo 5 itens; clique abre a matéria no site em nova aba.

**RF-HO-11 — "Publique o seu trabalho"**
- **Descrição:** box mint com "61% dos associados usam as redes para divulgar o que produzem. Submeta seu estudo à revista da APM." e botão teal "Submeter trabalho" que cria solicitação `submeter_trabalho`. Componente compartilhado com RF-NE-07.
- **Fonte:** `solicitacao` · **Endpoint:** `POST /solicitacoes [C]` (`tipo=submeter_trabalho`) · **Evento:** `solicitacao_criar` (servidor) · **Flag:** — · **Fase:** 5
- **UI:** toast sem texto na spec (LA-02; proposta "Recebemos seu interesse em publicar. A equipe da revista entra em contato."). "61%" é texto editorial (LA-14).
- **Aceite:** idem RF-HO-07.

---

### 3.3 Meus benefícios (BE) — `/area/beneficios`

**RF-BE-01 — Hero**
- **Descrição:** label "CLUBE DE BENEFÍCIOS APM", h2 "Tudo o que a sua associação faz por você", 3 estatísticas (aproveitados no ano · cashback no mês · benefícios ativos), selo "MEMBRO", borda superior âmbar.
- **Fonte:** aproveitados: RF-FA-01; cashback: clube (sem fonte); ativos: contagem de `beneficio_ativacao` ativas do associado · **Endpoint:** `GET /beneficios` (campo `ativos`), `GET /fatura` (com flag) · **Evento:** — · **Flag:** "aproveitados" sob `fatura_valor`; "cashback no mês" sob `clube_economia` · **Fase:** 4
- **UI:** "40+ benefícios ativos" é mock; exibir o número real (LA-14).
- **Aceite:** ativar/desativar um benefício altera o contador sem recarga (critério da spec).

**RF-BE-02 — Chips de filtro**
- **Descrição:** chips Tudo / Patrocinados / Novos / Ativos (ativo = fundo navy). Patrocinados = `tag=patrocinado`; Novos = `tag=novo`; Ativos = ativação ativa do associado. Filtro em `?filtro=`.
- **Fonte:** `GET /beneficios` · **Endpoint:** — · **Evento:** `filtro_aplicar` (ui) · **Flag:** chip "Patrocinados" sob `patrocinio` · **Fase:** 4
- **UI:** `aria-pressed`; entrada de cards animada (RF-SH-10).
- **Aceite:** cada chip produz o subconjunto correto (teste com seed).

**RF-BE-03 — Chip de categoria removível**
- **Descrição:** quando a navegação vem de um tile (`?categoria=<slug>`), exibe chip removível com o nome da categoria; remover limpa só a categoria.
- **Fonte:** `beneficio_categoria` · **Endpoint:** — · **Evento:** `filtro_aplicar` (ui) · **Flag:** — · **Fase:** 4
- **UI:** chip com botão × rotulado "Remover filtro {categoria}" (a11y, proposta).
- **Aceite:** slug inválido é ignorado (lista completa), sem erro.

**RF-BE-04 — Resultado de busca**
- **Descrição:** com `q`, exibe "Resultados para “{q}”" e filtra por título, descrição e grupo (RF-SH-04).
- **Fonte:** cliente · **Endpoint:** — · **Evento:** `busca_global` · **Flag:** — · **Fase:** 4
- **UI:** `{q}` escapado.
- **Aceite:** busca sem acento encontra título acentuado.

**RF-BE-05 — Grupos por categoria**
- **Descrição:** h3 em caixa alta por grupo (TECNOLOGIA E IA; CONSULTÓRIO E FINANÇAS; SAÚDE, BEM-ESTAR E PROTEÇÃO; EDUCAÇÃO E CARREIRA), cada um com grid `BenefitCard`. Grupos vazios não aparecem.
- **Fonte:** `beneficio` + `beneficio_categoria` (campo de grupo) · **Endpoint:** `GET /beneficios` · **Evento:** — · **Flag:** — · **Fase:** 4
- **UI:** card `patrocinado` com borda `#efc76b` (com `patrocinio`; sem a flag, borda transparente e sem tag — LA-28).
- **Aceite:** "Limpar filtros" restaura os 4 grupos (critério da spec).

**RF-BE-06 — Estado vazio**
- **Descrição:** card "Nenhum benefício encontrado" / "Tente outro termo ou fale com a Central de Relacionamento." + botão "Limpar filtros" (zera chip, categoria e `q`).
- **Fonte:** — · **Endpoint:** — · **Evento:** `filtro_aplicar` (ui, `detalhes.limpar=true`) · **Flag:** — · **Fase:** 4
- **UI:** literais acima.
- **Aceite:** busca sem resultado mostra o card; botão restaura a lista.

**RF-BE-07 — Ativar benefício**
- **Descrição:** CTA "Ativar" registra ativação; CTA passa a "Gerenciar", tag passa a `ativo` (ou mantém `patrocinado`), contador do hero incrementa. Idempotente: ativar já ativo devolve 200 com o estado atual.
- **Fonte:** `beneficio_ativacao` · **Endpoint:** `POST /beneficios/{slug}/ativar [C]` · **Evento:** `beneficio_ativar` (servidor) · **Flag:** — · **Fase:** 4
- **UI:** toast "{título} ativado"; botão desabilitado durante a requisição; falha → toast de erro e estado revertido.
- **Aceite:** critério da spec "Ativar um benefício muda o CTA para 'Gerenciar', a tag para `ativo`, incrementa o contador do hero e dispara o toast"; estado persiste após recarga e em outro dispositivo.

**RF-BE-08 — Gerenciar / desativar**
- **Descrição:** destino de "Gerenciar" não definido na spec (LA-03). Padrão adotado: abre diálogo do benefício com "Acessar" (link do benefício, nova aba) e "Desativar" (proposta). Desativar marca a ativação como inativa (sem `DELETE`).
- **Fonte:** `beneficio_ativacao` · **Endpoint:** `POST /beneficios/{slug}/desativar [C]` · **Evento:** `beneficio_gerenciar` (ui), `beneficio_desativar` (servidor) · **Flag:** — · **Fase:** 4
- **UI:** toast de desativação proposto "{título} desativado" (LA-02); diálogo com `role="dialog"`, foco preso, Esc.
- **Aceite:** desativar volta o CTA para "Ativar", a tag ao estado original e decrementa o contador; histórico preservado (linha atualizada, nunca removida).

**RF-BE-09 — Abrir benefício (CTA que não ativa)**
- **Descrição:** CTAs diferentes de "Ativar" ("Conhecer", "Acessar", etc.) abrem o link do benefício (seed) em nova aba.
- **Fonte:** `beneficio.url_acesso` (seed) · **Endpoint:** — · **Evento:** `beneficio_abrir` (ui) · **Flag:** — · **Fase:** 4
- **UI:** toast "Abrindo {título}…".
- **Aceite:** benefício sem URL não exibe CTA de abertura (seed validado em migração).

**RF-BE-10 — TotalPass**
- **Descrição:** card TotalPass mostra `ativo`/"Gerenciar" quando a adesão no CRM está ativa (`dxc_adesao_totalpass`, via hub por `contact_id`); senão "Ativar" abre `https://totalpass.apm.org.br` em nova aba. A adesão real acontece no TotalPass; a área não grava adesão no CRM.
- **Fonte:** hub `totalpass.adesao_consultar` (cache em memória 10 min por `contact_id`) · **Endpoint:** `GET /beneficios` (campo `totalpass` no item) · **Evento:** `totalpass_abrir` (ui) · **Flag:** `totalpass` · **Fase:** 4 (dados reais após P-02/P-04)
- **UI:** hub indisponível → card exibido sem estado de adesão (CTA "Ativar"), sem toast de erro (degradação silenciosa só aqui, registrada em log/`evento_log` severidade aviso).
- **Aceite:** elegibilidade = status Ativo (na prática toda sessão); com flag desligada o card não aparece.

---

### 3.4 Clube de vantagens (CL) — `/area/clube`

**RF-CL-01 — Voltar**
- **Descrição:** link "‹ voltar para o início" → `/area`.
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 6
- **UI:** `TextLink`.
- **Aceite:** navega para `/area`.

**RF-CL-02 — Hero**
- **Descrição:** label "CLUBE DE VANTAGENS APM", h2 "Vantagens e descontos para usar todo dia", estatísticas "economizados em 2026", "cashback → mensalidade" e "30 mil parceiros".
- **Fonte:** economia/cashback: sem fonte (Clube Certo); "30 mil parceiros": catálogo editorial · **Endpoint:** `GET /clube` · **Evento:** — · **Flag:** economia e cashback sob `clube_economia` · **Fase:** 6
- **UI:** com flag desligada só "30 mil parceiros" (LA-14).
- **Aceite:** nenhum valor monetário mock exibido com flag desligada.

**RF-CL-03 — Oferta da semana**
- **Descrição:** placeholder "foto da oferta", label "★ OFERTA DA SEMANA · TERMINA EM {n} DIAS", h3 (ex.: "30% no iFood + 5% de cashback"), "Uma nova oferta em destaque toda semana, escolhida para o seu perfil.", link-botão "Usar agora" → `https://clubapm.com.br` (nova aba).
- **Fonte:** catálogo editorial em código (`app/dominio/catalogo.py`) com validade; conteúdo por P-11 · **Endpoint:** `GET /clube` · **Evento:** `clube_oferta_usar` (ui, `entidade=oferta_semana`) · **Flag:** — · **Fase:** 6
- **UI:** `{n}` = dias até a validade em America/Sao_Paulo; oferta vencida → bloco oculto.
- **Aceite:** sem oferta vigente o bloco não aparece; link com `noopener`.

**RF-CL-04 — Grupos de ofertas**
- **Descrição:** "PARA USAR TODA SEMANA" (Farmácias, Mercado e delivery, Combustível, Telemedicina, Cinema) e "RECOMENDADO PARA VOCÊ" (Viagens, Eletrônicos, Casa e decoração, Moda e esporte); `OfferCard` com ícone, tag de desconto, título, descrição e "Usar" → `clubapm.com.br`.
- **Fonte:** catálogo editorial · **Endpoint:** `GET /clube` · **Evento:** `clube_oferta_usar` (ui, `entidade_id=<slug>`) · **Flag:** tags com "cashback" sob `clube_economia` · **Fase:** 6
- **UI:** literais da spec.
- **Aceite:** 9 ofertas do protótipo no seed inicial; "Usar" abre nova aba e registra o evento antes (`keepalive`).

**RF-CL-05 — Aside do clube**
- **Descrição:** "Sua economia no clube" (este mês · em 2026 · cashback vira crédito · na sua mensalidade); "Por que usar por aqui" ("Todo resgate acontece dentro da Minha APM. Por isso ele entra na sua fatura de valor e o cashback abate a sua mensalidade, automaticamente."); "Tecnologia do clube" ("Marca APM, infraestrutura Clube Certo · 30 mil parceiros nacionais e regionais.").
- **Fonte:** sem fonte para economia; textos estáticos · **Endpoint:** `GET /clube` · **Evento:** — · **Flag:** "Sua economia no clube" e "Por que usar por aqui" sob `clube_economia` (a afirmação não é verdadeira sem registro do resgate — LA-17) · **Fase:** 6
- **UI:** "Tecnologia do clube" sempre visível.
- **Aceite:** com flag desligada apenas "Tecnologia do clube" aparece.

---

### 3.5 Notícias e ciência (NE) — `/area/noticias`

**RF-NE-01 — Hero**
- **Descrição:** label "PERSONALIZADO PARA VOCÊ", h2 "Notícias e ciência", texto "Notícias, notas, acontecimentos, trabalhos e publicações científicas, filtrados pelos temas que você escolhe seguir."; indicadores "{n} temas seguidos", "atualizado hoje", "{n} salvos".
- **Fonte:** `associado_tema`, `noticia_salva`, `job_execucao` (última execução ok de `sincronizar_portal`) · **Endpoint:** `GET /noticias`, `GET /temas` · **Evento:** — · **Flag:** — · **Fase:** 5
- **UI:** "atualizado hoje" se a última sincronização bem-sucedida for de hoje (America/Sao_Paulo); senão "atualizado em DD/MM" (proposta, LA-23).
- **Aceite:** contadores mudam sem recarga ao seguir tema ou salvar.

**RF-NE-02 — Chips de tema**
- **Descrição:** "Todos" + temas seguidos. Padrão para quem nunca configurou: Cardiologia, IA na saúde, Gestão & carreira, Defesa profissional, Saúde mental.
- **Fonte:** `tema` (seed), `associado_tema` · **Endpoint:** `GET /temas` · **Evento:** `filtro_aplicar` (ui) · **Flag:** — · **Fase:** 5
- **UI:** `aria-pressed`.
- **Aceite:** associado sem linha em `associado_tema` vê os 5 padrões; o padrão não é gravado até a primeira alteração.

**RF-NE-03 — Lista de artigos**
- **Descrição:** cards horizontais (thumb 84 px mobile / 128 px desktop, "imagem" mono quando sem imagem, tag de tipo colorida, h4, meta "fonte · data · tema", marcador). Clique no card abre a matéria no site (nova aba). Paginação por cursor (`?cursor=`, 20 por página) com carregamento incremental.
- **Fonte:** `noticia_cache` (job `sincronizar_portal`, D-07) · **Endpoint:** `GET /noticias?tema=&q=&cursor=` · **Evento:** `noticia_abrir` (ui) · **Flag:** — · **Fase:** 5
- **UI:** estado vazio "Nenhum conteúdo neste tema ainda."; imagens `loading="lazy"` com proporção fixa; imagem fora de `CSP_IMG_HOSTS` vira placeholder no job. Mapeamento de tipo (ciência/publicação/notícia/evento/nota) em LA-23.
- **Aceite:** Locaweb fora do ar não afeta a tela (serve do cache); nenhuma requisição do navegador ao host do WordPress além de imagens permitidas.

**RF-NE-04 — Salvar / dessalvar**
- **Descrição:** marcador alterna salvo; fundo `#e2f3ee`/texto `--green-600` quando salvo. Dessalvar é remoção lógica.
- **Fonte:** `noticia_salva` · **Endpoint:** `POST /noticias/{id}/salvar [C]`, `DELETE /noticias/{id}/salvar [C]` · **Evento:** `noticia_salvar` / `noticia_dessalvar` (servidor) · **Flag:** — · **Fase:** 5
- **UI:** toast "Salvo para depois" ao salvar; dessalvar sem toast (spec silente); `aria-pressed` no marcador; alvo ≥ 44 px.
- **Aceite:** estado persiste após recarga; `DELETE` HTTP mapeia para `UPDATE` (o usuário de banco não tem `DELETE`).

**RF-NE-05 — "Personalize o seu radar" (seguir tema)**
- **Descrição:** texto + botões "+ Oncologia", "+ Pediatria", "+ Telemedicina" (sugestões = temas do seed ainda não seguidos, até 3). Seguir grava a lista completa.
- **Fonte:** `tema`, `associado_tema` · **Endpoint:** `PUT /temas [C]` · **Evento:** `tema_seguir` (servidor); `tema_deixar` reservado (LA-30) · **Flag:** — · **Fase:** 5
- **UI:** toast "Agora você segue X"; botão some da sugestão e o tema entra nos chips.
- **Aceite:** tema inexistente → `400 entrada_invalida`; limite de 20 temas seguidos.

**RF-NE-06 — "Salvos para depois"**
- **Descrição:** lista curta (título abreviado e tipo) dos salvos, mais recentes primeiro.
- **Fonte:** `noticia_salva` × `noticia_cache` · **Endpoint:** `GET /noticias?salvos=1` · **Evento:** `noticia_abrir` (ui) · **Flag:** — · **Fase:** 5
- **UI:** vazio "Toque no marcador de um conteúdo para salvar."
- **Aceite:** notícia removida do site continua listada enquanto houver cache (marcada inativa pelo job, sem link quebrado: some da lista).

**RF-NE-07 — "Publique o seu trabalho" (aside)**
- **Descrição:** mesmo componente e comportamento de RF-HO-11.
- **Fonte / Endpoint / Evento / Flag / UI / Aceite:** idem RF-HO-11 · **Fase:** 5

---

### 3.6 Fatura de valor (FA) — `/area/fatura` (flag `fatura_valor`)

**RF-FA-01 — Card "Sua fatura de valor"**
- **Descrição:** h3 "Sua fatura de valor", subtítulo "{período} · economia comprovada item a item", total à direita e linhas (ícone, título, descrição, valor) — no protótipo: Coworking médico, Escriba de IA, Terapia subsidiada, Defesa profissional e seguros, Cursos e congresso.
- **Fonte:** cálculo sobre `beneficio_ativacao` × valor de referência do benefício (regra de valor por P-12) · **Endpoint:** `GET /fatura` · **Evento:** — · **Flag:** `fatura_valor` · **Fase:** 8
- **UI:** período × "no ano" em LA-11; moeda sem centavos quando inteiro.
- **Aceite:** soma das linhas = total; flag desligada → `404 recurso_desligado` e rota "não encontrada".

**RF-FA-02 — "Baixar PDF da fatura"**
- **Descrição:** gera PDF no servidor (sem dado do patrocinador; sem CPF) e entrega como download.
- **Fonte:** idem RF-FA-01 · **Endpoint:** `GET /fatura/pdf` (`Content-Disposition: attachment`, `no-store`) · **Evento:** `fatura_pdf_baixar` (servidor) · **Flag:** `fatura_valor` · **Fase:** 8
- **UI:** toast "PDF da fatura gerado".
- **Aceite:** PDF gerado em `run_in_threadpool`, ≤ 2 s p95; nome do arquivo sem dado pessoal.

**RF-FA-03 — Card "Carteirinha digital"**
- **Descrição:** "Seu selo de associado APM, sempre no bolso e verificável pelo paciente." + botão "+ Adicionar à Wallet" que navega para `/area/carteirinha` (não aciona a Wallet).
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** `fatura_valor` (tela) · **Fase:** 8
- **UI:** literais da spec.
- **Aceite:** navega para a carteirinha.

**RF-FA-04 — Comportamento com flag desligada**
- **Descrição:** sem item de menu, sem link "ver extrato completo →", `/area/fatura` mostra "não encontrada"; `GET /fatura` e `GET /fatura/pdf` respondem `404 recurso_desligado`.
- **Fonte:** `feature_flag` · **Endpoint:** `GET /fatura[/pdf]` · **Evento:** — · **Flag:** `fatura_valor` · **Fase:** 1 (comportamento) / 8 (conteúdo)
- **UI:** —
- **Aceite:** teste de API com flag desligada e com `FLAGS_FORCAR_DESLIGADAS=fatura_valor` sobrepondo a tabela.

**RF-FA-05 — Valor pago no ano (ERP)**
- **Descrição:** valor pago pelo associado no ano (frase "você pagou R$ {x} no ano" e múltiplo "↗ {n}× o que você pagou") lido do ERP pelo hub (`financeiro.*`, resolução de CPF dentro do hub a partir do `contact_id`).
- **Fonte:** ERP F&O via hub (`CustTransactions`) · **Endpoint:** `GET /financeiro/faturas` (agregado) · **Evento:** — · **Flag:** `erp_financeiro` · **Fase:** 7
- **UI:** indisponível → frase omitida, sem erro visível.
- **Aceite:** nenhuma chamada da área ao ERP com CPF; flag desligada → `404 recurso_desligado`.

---

### 3.7 Comunidade (CO) — `/area/comunidade`

**RF-CO-01 — "SUAS COMUNIDADES" — entrar**
- **Descrição:** 4 cards (Mulheres na Medicina; Cardiologia · sua especialidade; Jovens médicos e residentes; Embaixadores acadêmicos). Botão "Entrar" registra adesão, vira "Abrir" (fundo `#1faa59`, ícone chat) e abre `https://wa.me/<numero>?text=Olá! Quero acessar o grupo {nome} da APM.` em nova aba.
- **Fonte:** `comunidade` (seed, com número/link por comunidade — P-11), `comunidade_adesao` · **Endpoint:** `GET /comunidades`, `POST /comunidades/{slug}/entrar [C]` · **Evento:** `comunidade_entrar` (servidor) · **Flag:** — · **Fase:** 6
- **UI:** "● ativa agora" só se o seed marcar `live` (sem fonte real; LA-14); descrição com contagem só se o seed tiver contagem (LA-14). `wa.me` abre conversa 1:1, não grupo (LA-09). "Cardiologia · sua especialidade" depende de especialidade no perfil — sem fonte; exibir "Cardiologia" sem o sufixo (proposta, LA-14).
- **Aceite:** estado "Abrir" persiste após recarga; o nome no texto do `wa.me` é URL-encoded.

**RF-CO-02 — Abrir comunidade já ingressada**
- **Descrição:** "Abrir" abre o mesmo destino `wa.me` sem nova escrita.
- **Fonte:** `comunidade` · **Endpoint:** — · **Evento:** `comunidade_abrir` (ui) · **Flag:** — · **Fase:** 6
- **UI:** botão verde WhatsApp.
- **Aceite:** nenhuma requisição de escrita no segundo clique.

**RF-CO-03 — Embaixadores acadêmicos ("Saber mais")**
- **Descrição:** card de programa (descrição "64 faculdades · leva a APM para dentro do campus") com "Saber mais".
- **Fonte:** seed `comunidade` (tipo programa, URL institucional) · **Endpoint:** — · **Evento:** `programa_saber_mais` (ui) · **Flag:** — · **Fase:** 6
- **UI:** toast sem texto na spec (LA-02); padrão: abre a página do programa em nova aba com toast "Abrindo Embaixadores acadêmicos…" (padrão "Abrindo {título}…").
- **Aceite:** sem URL no seed o botão não aparece.

**RF-CO-04 — "CONVERSAS EM DESTAQUE"**
- **Descrição:** 3 posts (avatar com iniciais, nome, "{n} respostas · há {t}", texto).
- **Fonte:** inexistente · **Endpoint:** — · **Evento:** — · **Flag:** `comunidade_posts` (desligada) · **Fase:** fora desta versão
- **UI:** seção inteira oculta.
- **Aceite:** com a flag desligada a seção e seu h3 não existem no DOM (LA-13).

**RF-CO-05 — Rede de encaminhamento**
- **Descrição:** card com "Indique e receba pacientes entre associados. {n} médicos já estão na rede da sua região.", campo "Buscar especialista por área..." e botão "Entrar na rede" → "Você está na rede ✓". Entrar registra adesão ao programa `rede`.
- **Fonte:** `comunidade` (slug `rede`, tipo programa), `comunidade_adesao` · **Endpoint:** `POST /comunidades/rede/entrar [C]` · **Evento:** `rede_entrar` (servidor) · **Flag:** — · **Fase:** 6
- **UI:** "320 médicos" é mock; exibir contagem real de adesões ao programa se ≥ limiar definido pelo negócio, senão omitir a frase numérica (LA-14). Campo de busca **não exibido** (sem fonte, LA-22). Sem toast na spec (LA-02).
- **Aceite:** estado confirmado `SecondaryButton` (`#e2f3ee`) persiste após recarga.

**RF-CO-06 — Mentoria titular ↔ jovem**
- **Descrição:** botões "Quero um mentor" e "Quero ser mentor" criam solicitações `mentoria_pedir` e `mentoria_oferecer`.
- **Fonte:** `solicitacao` · **Endpoint:** `POST /solicitacoes [C]` · **Evento:** `solicitacao_criar` (servidor) · **Flag:** — · **Fase:** 6
- **UI:** toasts sem texto na spec (LA-02; propostas "Pedido de mentoria recebido. Acompanhe em Minhas solicitações." / "Obrigado! Recebemos seu interesse em ser mentor.").
- **Aceite:** uma solicitação não terminal por tipo; clique repetido devolve a existente.

**RF-CO-07 — "Próximos encontros"**
- **Descrição:** até 2 próximos encontros (bloco de data, título, "online · 19h" / "presencial · sede APM").
- **Fonte:** `evento_cache` filtrado por categorias mapeadas às comunidades no seed (proposta) · **Endpoint:** `GET /eventos?contexto=comunidade` · **Evento:** — · **Flag:** — · **Fase:** 6
- **UI:** sem eventos futuros → bloco oculto.
- **Aceite:** datas no fuso America/Sao_Paulo; meses em 3 letras caixa alta.

---

### 3.8 Congresso e eventos (EV) — `/area/eventos`

**RF-EV-01 — Hero do Congresso**
- **Descrição:** label, h2 "Medicina, IA e gestão: o consultório do futuro", texto "O maior encontro da APM ganha cinco trilhas e patrocínio âncora. Ciência de ponta, gestão e tecnologia no mesmo palco.", chips "26 a 28 de setembro", "São Paulo · híbrido", "certificado incluso", link "ver programação completa →" (`apm.org.br`, nova aba), contador "{n} dias para o congresso".
- **Fonte:** `evento_cache` (Congresso) + catálogo editorial para textos fixos · **Endpoint:** `GET /eventos` · **Evento:** `congresso_programacao_abrir` (ui) · **Flag:** — · **Fase:** 5
- **UI:** `{n}` em dias civis America/Sao_Paulo; contador oculto quando `n ≤ 0`; hero oculto sem Congresso futuro (LA-07).
- **Aceite:** contador correto na virada de dia em São Paulo (teste com relógio fixo).

**RF-EV-02 — Garantir vaga no Congresso**
- **Descrição:** CTA "Garantir minha vaga" → "Vaga garantida ✓", mesmo estado de RF-HO-04. Registra `evento_inscricao` do Congresso. Segundo clique: em `/area/eventos`, rola até a agenda/programação (na home, navega para cá).
- **Fonte:** `evento_inscricao` · **Endpoint:** `POST /eventos/congresso/garantir-vaga [C]` · **Evento:** `congresso_garantir_vaga` (servidor) · **Flag:** — · **Fase:** 5
- **UI:** onde a inscrição acontece de fato em LA-07; toast em LA-02.
- **Aceite:** idempotente; estado igual na home e em eventos.

**RF-EV-03 — "TRILHAS DO CONGRESSO"**
- **Descrição:** 5 cards: IA na medicina; Gestão de consultório; Comercial e captação; Marketing médico; Atualização científica (descrições da spec).
- **Fonte:** catálogo editorial · **Endpoint:** `GET /eventos` (bloco `congresso.trilhas`) · **Evento:** — · **Flag:** — · **Fase:** 5
- **UI:** literais da spec.
- **Aceite:** oculto junto com o hero quando não há Congresso.

**RF-EV-04 — "AGENDA DE EVENTOS"**
- **Descrição:** lista em card único; linhas com bloco de data (dia/mês), título, descrição, tag Online (mint) ou Presencial (azul), botão "Inscrever". Próximos eventos ordenados por data.
- **Fonte:** `evento_cache` (post type `evento`, taxonomia `categoria_do_evento`, metas `data`/`data_do_webinar`/`hora`/`hora_do_webinar`/`local`/`link_externo`/`este_evento_e_um_webinar`) · **Endpoint:** `GET /eventos` · **Evento:** — · **Flag:** — · **Fase:** 5
- **UI:** Online = `este_evento_e_um_webinar` verdadeiro; primeira linha sem divisor. Sem eventos: "Nenhum evento agendado no momento." (proposta, LA-25).
- **Aceite:** eventos passados não aparecem; meses "JUL", "AGO" etc.

**RF-EV-05 — Inscrever em evento**
- **Descrição:** "Inscrever" → "Inscrito ✓" registra `evento_inscricao` (interesse local; LA-06).
- **Fonte:** `evento_inscricao` · **Endpoint:** `POST /eventos/{id}/inscrever [C]` · **Evento:** `evento_inscrever` (servidor) · **Flag:** — · **Fase:** 5
- **UI:** toast "Inscrição confirmada: {título}"; se o evento tiver `link_externo`, padrão adotado até LA-06: abrir o link em nova aba após o registro.
- **Aceite:** idempotente; estado persiste; evento inexistente/encerrado → `404 nao_encontrado`/`409 estado_invalido`.

---

### 3.9 Carteirinha digital (CA) — `/area/carteirinha`

**RF-CA-01 — Cartão**
- **Descrição:** card navy com logotipo, selo "MEMBRO", nome completo, "CRM-{UF} {número} · associad{a|o} desde {ano}", "válida até {MM/AAAA}" e QR (RF-CA-02).
- **Fonte:** claims `carteirinha` (P-09) e cache `associado_perfil` (`sol_st_numerocrm`, `alf_uf_crm`, `alf_data_filiacao`, `alf_sexo`) · **Endpoint:** `GET /carteirinha` · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** gênero de "associada/associado" por `alf_sexo` (LA-19; desconhecido → "associado(a)" proibido, usar "na APM desde {ano}" — proposta); sem CRM (acadêmico) a linha mostra só "na APM desde {ano}" (LA-20); "válida até" **omitido** até LA-04.
- **Aceite:** nenhum CPF no payload; hub indisponível sem cache → `503 fonte_indisponivel` com toast; com cache ≤ 24 h, exibe o cache.

**RF-CA-02 — QR de verificação**
- **Descrição:** QR (SVG gerado no cliente, sem biblioteca externa em CDN) com `https://associado.apm.org.br/verificar/{token}`; `token` = base32 de HMAC-SHA256(`CARTEIRINHA_HMAC_KEY`, `contact_id`) truncado a 20 caracteres, chave própria em `Settings` distinta de `SECRET_KEY` (ADR-0014), persistido em `associado.carteirinha_token` com índice único para busca.
- **Fonte:** `associado` · **Endpoint:** `GET /carteirinha` (campo `url_verificacao`) · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** 64×64 branco, com texto alternativo "QR code de verificação da carteirinha" (proposta).
- **Aceite:** token não revela `contact_id`; rotação da chave invalida todos os QRs (documentado em `docs/CUTOVER.md`/runbook).

**RF-CA-03 — Verificação pública `/verificar/{token}`**
- **Descrição:** página HTML pública (Jinja2 `verificar.html`, sem SPA) que mostra **apenas** nome, status e validade (enquanto LA-04 aberta: status + "verificado em DD/MM/AAAA HH:MM"). Token desconhecido → página "Carteirinha não encontrada" (proposta) com 404.
- **Fonte:** `associado` + `associado_perfil` (status); cache > 24 h → tenta hub; hub fora → página "Verificação indisponível no momento" com 503 (fail-closed: nunca "Ativo" a partir de cache vencido) · **Endpoint:** `GET /verificar/{token}` · **Evento:** `carteirinha_verificar` (publico, `contact_id` do titular; sem dado do visitante) · **Flag:** — · **Fase:** 2
- **UI:** `X-Robots-Tag: noindex`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.
- **Aceite:** vhost `limit_req` 2 r/s; resposta idêntica em tempo para token inexistente e válido (sem oráculo de enumeração além do status HTTP); nenhum CRM, CPF, e-mail, foto ou data de nascimento na página.

**RF-CA-04 — Compartilhar**
- **Descrição:** "Compartilhar" obtém a URL de verificação e copia para a área de transferência (Web Share API em mobile quando disponível).
- **Fonte:** `associado` · **Endpoint:** `POST /carteirinha/compartilhar [C]` · **Evento:** `carteirinha_compartilhar` (servidor) · **Flag:** — · **Fase:** 2
- **UI:** toast "Link de verificação copiado"; falha do clipboard → toast "Não foi possível copiar o link." (proposta) e URL exibida em campo selecionável.
- **Aceite:** URL copiada = URL do QR.

**RF-CA-05 — Adicionar à Wallet**
- **Descrição:** "+ Adicionar à Wallet" gera passe Apple/Google.
- **Fonte:** P-13 · **Endpoint:** a definir no plano da Fase 8 · **Evento:** `wallet_adicionar` (ui) · **Flag:** `wallet` · **Fase:** 8
- **UI:** com flag desligada o botão não existe; toast sem texto na spec (LA-02).
- **Aceite:** flag desligada → sem botão.

**RF-CA-06 — Texto lateral**
- **Descrição:** h2 "Sua carteirinha digital", texto "Apresente em parceiros, eventos e no consultório. O QR code permite que qualquer pessoa confirme que você é associad{a|o} APM."
- **Fonte:** `alf_sexo` · **Endpoint:** `GET /carteirinha` · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** concordância por LA-19.
- **Aceite:** literal da spec com concordância aplicada.

---

### 3.10 Onboarding acadêmico (ON) — `/area/onboarding`

**RF-ON-01 — Acesso e rota inicial**
- **Descrição:** rota visível e acessível para tipo Acadêmico; rota inicial (seção 1.2) enquanto não houver passo `finalizar` concluído. Outros tipos que acessem a URL veem "não encontrada" (LA-21).
- **Fonte:** sessão (`tipo`), `onboarding_progresso` · **Endpoint:** `GET /sessao` (`rota_inicial`), `GET /onboarding` · **Evento:** — · **Flag:** — · **Fase:** 6
- **UI:** —
- **Aceite:** acadêmico novo cai em `/area/onboarding` ao entrar em `/area`; após finalizar, cai em `/area`; deep link não é desviado.

**RF-ON-02 — Hero**
- **Descrição:** avatar com iniciais (56 px), label "BEM-VINDO À APM", h2 "Olá, {primeiro nome}. A sua jornada começa aqui.", texto "Você é acadêmico de Medicina, e a sua associação é 100% patrocinada. Vamos ativar os seus primeiros benefícios — leva 5 minutos.", chips "mensalidade R$ 0 · patrocinada", "R$ {soma}+ em benefícios/ano", "trilha de 90 dias".
- **Fonte:** sessão; soma dos `valor_anual` do seed `onboarding_passo` · **Endpoint:** `GET /onboarding` · **Evento:** — · **Flag:** trecho ", e a sua associação é 100% patrocinada" e chip "mensalidade R$ 0 · patrocinada" sob `mensalidade_zero` (sem a flag: "Você é acadêmico de Medicina. Vamos ativar os seus primeiros benefícios — leva 5 minutos." — proposta, LA-10) · **Fase:** 6
- **UI:** "R$ 1.500+" × "R$ 2.490" em LA-12; padrão: valor calculado do seed.
- **Aceite:** texto muda com a flag; valor do chip igual à soma do seed.

**RF-ON-03 — Card de progresso**
- **Descrição:** percentual grande, "Sua ativação", "**{feitos}** de {total} passos · {R$ desbloqueados} desbloqueados" e barra de progresso.
- **Fonte:** `onboarding_passo`, `onboarding_progresso` · **Endpoint:** `GET /onboarding` · **Evento:** — · **Flag:** — · **Fase:** 6
- **UI:** desbloqueados = soma de `valor_anual` dos passos concluídos; `ProgressBar` com `role="progressbar"` e `aria-valuenow`.
- **Aceite:** concluir um passo atualiza percentual, contagem e valor sem recarga.

**RF-ON-04 — Trilha de ativação**
- **Descrição:** "SUA TRILHA DE ATIVAÇÃO · PRIMEIROS 90 DIAS" com 6 `StepCard`: Complete seu perfil (Concluir), Ative a TotalPass (R$ 1.200/ano, Ativar), Whitebook e Portal MBE (R$ 300/ano, Acessar), Entre na comunidade (Entrar), Garanta vaga no Congresso (R$ 690/ano, Garantir), Peça um mentor (Pedir).
- **Fonte:** `onboarding_passo` (seed), `onboarding_progresso` · **Endpoint:** `GET /onboarding` · **Evento:** — · **Flag:** — · **Fase:** 6
- **UI:** concluído: fundo mint, borda `#bfe4d8`, tag "feito", meta "concluído", sem botão; pendente: tag âmbar "● R$ X/ano" quando há valor, meta "passo N". "Complete seu perfil" vem concluído por padrão (gravado no primeiro `GET /onboarding`).
- **Aceite:** primeiro acesso já mostra 1 de 6.

**RF-ON-05 — Concluir passo**
- **Descrição:** cada CTA executa a ação do passo e, em caso de sucesso, conclui o passo (append em `onboarding_progresso`; repetição é idempotente).
- **Fonte:** `onboarding_progresso` · **Endpoint:** `POST /onboarding/passos/{slug}/concluir [C]` · **Evento:** `onboarding_passo_concluir` (servidor) · **Flag:** — · **Fase:** 6
- **UI:** card vira estado concluído com animação de entrada.
- **Aceite:** slug inexistente → `404`; concluir duas vezes não duplica.

**RF-ON-06 — Ações dos passos**
- **Descrição:** Ative a TotalPass → deep-link TotalPass (RF-BE-10) e conclui; Whitebook e Portal MBE → abre link do benefício (RF-BE-09) e conclui; Entre na comunidade → navega para `/area/comunidade` e conclui quando houver `comunidade_adesao` (verificado no `GET /onboarding`); Garanta vaga no Congresso → RF-EV-02 e conclui; Peça um mentor → solicitação `mentoria_pedir` (RF-CO-06) e conclui. "Complete seu perfil" pendente (se algum dia for desmarcado no seed) → navega para `/area/perfil`.
- **Fonte:** idem RFs referenciados · **Endpoint:** os dos RFs referenciados + RF-ON-05 · **Evento:** `totalpass_abrir`, `beneficio_abrir`, `congresso_garantir_vaga`, `solicitacao_criar`, `onboarding_passo_concluir` · **Flag:** passo TotalPass oculto sem `totalpass` · **Fase:** 6
- **UI:** toasts dos RFs referenciados.
- **Aceite:** cada passo, ao ser concluído pela ação, aparece concluído após recarga.

**RF-ON-07 — "O QUE A SUA MENSALIDADE COBRE"**
- **Descrição:** TotalPass · academias e bem-estar R$ 1.200/ano · Portal MBE, biblioteca e cursos IESAPM R$ 300/ano · Congresso e eventos (acadêmico) R$ 690/ano · Clube de benefícios e seguros R$ 300/ano; "Valor para você ≈ R$ {soma}/ano"; "O que você paga: R$ 0 · o patrocinador cobre".
- **Fonte:** catálogo editorial (coberturas) · **Endpoint:** `GET /onboarding` · **Evento:** — · **Flag:** `mensalidade_zero` · **Fase:** 8
- **UI:** soma calculada (LA-12).
- **Aceite:** flag desligada → seção ausente.

**RF-ON-08 — Banco de plantões e vagas**
- **Descrição:** `BenefitCard` "Banco de plantões e vagas" (tag `novo`, meta "340 vagas hoje") com CTA que abre o destino do banco de plantões.
- **Fonte:** seed `beneficio` (URL de destino — LA-24) · **Endpoint:** — · **Evento:** `plantoes_abrir` (ui) · **Flag:** — · **Fase:** 6
- **UI:** toast "Abrindo {título}…"; contagem "340 vagas hoje" omitida até haver fonte (LA-14/LA-24).
- **Aceite:** sem URL definida o card não aparece.

**RF-ON-09 — Pedir Cartão APM**
- **Descrição:** `BenefitCard` "Cartão APM com cashback" (meta "sem anuidade", tag `patrocinado`) com CTA que cria solicitação `cartao_apm`.
- **Fonte:** `solicitacao` · **Endpoint:** `POST /solicitacoes [C]` · **Evento:** `solicitacao_criar` (servidor) · **Flag:** tag `patrocinado` sob `patrocinio` · **Fase:** 6
- **UI:** rótulo do CTA não definido na spec (padrão do seed: "Pedir" — proposta); toast proposto "Pedido do Cartão APM recebido. Acompanhe em Minhas solicitações." (LA-02).
- **Aceite:** uma solicitação não terminal por associado.

**RF-ON-10 — "VOCÊ NÃO ESTÁ SOZINHO"**
- **Descrição:** Comunidade de jovens médicos (→ `/area/comunidade`), Mentoria com titulares (→ `/area/comunidade`), Congresso APM (→ `/area/eventos`; "grátis para acadêmico").
- **Fonte:** catálogo editorial · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 6
- **UI:** "920 membros", "210 mentores" omitidos até haver contagem real (LA-14); card do Congresso oculto sem Congresso futuro.
- **Aceite:** navegação correta.

**RF-ON-11 — "Ir para a Minha APM →"**
- **Descrição:** conclui o passo especial `finalizar` (critério de "onboarding concluído", LA-21) e navega para `/area`.
- **Fonte:** `onboarding_progresso` · **Endpoint:** `POST /onboarding/passos/finalizar/concluir [C]` · **Evento:** `onboarding_passo_concluir` (`entidade_id=finalizar`) · **Flag:** — · **Fase:** 6
- **UI:** falha → toast de erro e permanece.
- **Aceite:** após o clique, novo login cai em `/area`.

---

### 3.11 Perfil (PE) — `/area/perfil` (tela nova, sem layout na spec)

Layout: composto por componentes da spec (`HeroPanel` compacto com avatar 56 px, cards brancos,
`PrimaryButton`/`SecondaryButton`, `Toast`); textos são **propostas** (LA-25).

**RF-PE-01 — Visualizar dados**
- **Descrição:** exibe nome completo, CRM/UF, tipo, status, data de filiação, e-mail, celular, telefones, endereço, data de nascimento e sexo, agrupados (Identificação · Contato · Endereço). CPF nunca. Mostra "Dados atualizados em DD/MM/AAAA HH:MM" (cache).
- **Fonte:** CRM `contact` via hub `associado.consultar` por `contact_id` (P-04); cache `associado_perfil` 24 h; renovação sob demanda pelo botão "Atualizar dados" (limite 1/5 min) · **Endpoint:** `GET /perfil` · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** campos "nunca" (seção 9) em modo somente leitura com texto "Para corrigir, fale com a Central de Relacionamento." e link para o FAB.
- **Aceite:** payload sem CPF (teste de contrato varre chaves e valores com regex de CPF); cache > 24 h dispara renovação assíncrona.

**RF-PE-02 — Editar dados de contato (direto)**
- **Descrição:** edição dos campos de regime "direto" (seção 9) com validação no cliente e no servidor; envio parcial (só campos alterados); escrita no CRM via hub `associado.contato_atualizar` (allowlist); cache atualizado após 200 do hub.
- **Fonte:** CRM via hub (escrita) · **Endpoint:** `PUT /perfil/contato [C]` · **Evento:** `perfil_contato_atualizar` (servidor; `detalhes.campos` = nomes, nunca valores) · **Flag:** — · **Fase:** 2
- **UI:** toast "Dados atualizados." (proposta); erros por campo inline; hub fora → `503` e toast, formulário preserva o que foi digitado.
- **Aceite:** campo fora da allowlist → `400 entrada_invalida`; 11ª edição na hora → `429 limite_taxa`; `evento_log` registra só nomes de campos.

**RF-PE-03 — Pedir alteração com aprovação**
- **Descrição:** campos de regime "com aprovação" (nome, sobrenome, data de nascimento, sexo) abrem formulário "Pedir alteração" que cria solicitação `alteracao_cadastro` com `{campo: novo_valor}` validado; enquanto houver solicitação não terminal para o campo, ele mostra "Alteração em análise" (proposta) com link para a solicitação.
- **Fonte:** `solicitacao` · **Endpoint:** `POST /solicitacoes [C]` (`tipo=alteracao_cadastro`) · **Evento:** `solicitacao_criar` · **Flag:** — · **Fase:** 3
- **UI:** toast "Pedido de alteração enviado. Acompanhe em Minhas solicitações." (proposta).
- **Aceite:** segundo pedido para o mesmo campo com outro aberto → `409 estado_invalido`; ao concluir no CRM, o cache do perfil é invalidado pelo job.

**RF-PE-04 — Campos nunca editáveis**
- **Descrição:** CPF (não exibido), CRM, UF do CRM, status, tipo, número de contato e data de filiação são somente leitura em qualquer caminho (UI, API, hub).
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** sem controle de edição.
- **Aceite:** tentativa via API → `400 entrada_invalida`; allowlist do hub recusa os mesmos campos (defesa em profundidade).

**RF-PE-05 — Enviar foto**
- **Descrição:** seleção de arquivo (JPEG/PNG/WebP, ≤ 5 MB), recorte quadrado no cliente (UI de recorte própria, sem lib externa em CDN), envio multipart; servidor valida por magic bytes, `MAX_IMAGE_PIXELS` 25 MP, aplica EXIF transpose, remove metadados, recorta quadrado central (defensivo), gera 512×512 JPEG q85 → hub `associado.foto_atualizar` (`entityimage`) e 128×128 → `associado_perfil.foto_miniatura` (ETag nova). Tudo em `run_in_threadpool`.
- **Fonte:** CRM via hub + `associado_perfil` · **Endpoint:** `POST /perfil/foto [C]` · **Evento:** `perfil_foto_atualizar` (servidor) · **Flag:** — · **Fase:** 2
- **UI:** toast "Foto atualizada." (proposta); erros: `413` "A foto deve ter até 5 MB.", `415` "Envie uma imagem JPEG, PNG ou WebP." (propostas).
- **Aceite:** arquivo com extensão `.jpg` e conteúdo não-imagem → `415`; bomba de descompressão rejeitada sem estourar memória do worker; 6º upload na hora → `429`; vhost `client_max_body_size 6m` no location da foto.

**RF-PE-06 — Exibir foto**
- **Descrição:** miniatura servida pela área (header, perfil, carteirinha se aplicável) com `ETag` e `Cache-Control: private, no-cache`; sem foto → iniciais.
- **Fonte:** `associado_perfil.foto_miniatura` · **Endpoint:** `GET /perfil/foto` · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** `<img>` com proporção fixa e `alt` vazio (decorativa ao lado do nome).
- **Aceite:** `If-None-Match` → `304`; só o dono obtém a própria foto (sem parâmetro de id).

**RF-PE-07 — Remover foto**
- **Descrição:** não implementado nesta versão (LA-15); nenhum botão "Remover".
- **Fonte / Endpoint / Evento / Flag:** — · **Fase:** —
- **UI:** —
- **Aceite:** ausência do controle.

**RF-PE-08 — Indisponibilidade do hub**
- **Descrição:** hub fora: leitura usa cache (qualquer idade, com a data visível) e mostra aviso "Não foi possível atualizar seus dados agora. Exibindo a última versão." (proposta); sem cache → `503 fonte_indisponivel`. Escritas (contato, foto) sempre falham fechadas com `503`.
- **Fonte:** `associado_perfil` · **Endpoint:** `GET /perfil`, `PUT /perfil/contato`, `POST /perfil/foto` · **Evento:** `erro_exibido` · **Flag:** — · **Fase:** 2
- **UI:** aviso não bloqueante.
- **Aceite:** teste com `HUB_MODE=stub` em falha cobre leitura com/sem cache e escrita.

**RF-PE-09 — Sair**
- **Descrição:** botão "Sair" também no perfil (mesmo comportamento de RF-AU-07).
- **Fonte / Endpoint / Evento:** RF-AU-07 · **Flag:** — · **Fase:** 2
- **UI:** `SecondaryButton`.
- **Aceite:** idem RF-AU-07.

---

### 3.12 Minhas solicitações (SO) — `/area/solicitacoes` (tela nova)

**RF-SO-01 — Lista**
- **Descrição:** lista das solicitações do associado, ordenadas por última atualização (desc), com tipo (rótulo pt-BR), status pt-BR (seção 7), data de abertura e última atualização; abas "Em andamento" (não terminais) e "Encerradas" (proposta). Paginação por cursor (20).
- **Fonte:** `solicitacao` · **Endpoint:** `GET /solicitacoes?situacao=&cursor=` · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** vazio "Você ainda não fez nenhuma solicitação." (proposta); status com `Tag`: Recebida (cinza), Em análise (azul), Aguardando você (âmbar), Concluída (mint), Não aprovada (rose), Cancelada (cinza).
- **Aceite:** só as do próprio `contact_id`; nenhum campo `crm_*` no payload.

**RF-SO-02 — Detalhe e linha do tempo**
- **Descrição:** detalhe com tipo, dados enviados (sem campos internos), status atual e linha do tempo de `solicitacao_evento` (data/hora, transição em pt-BR, ator "Você"/"Equipe APM", mensagem pública quando houver).
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `GET /solicitacoes/{uuid}` · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** datas em America/Sao_Paulo.
- **Aceite:** `uuid` de outro associado → `404 nao_encontrado` (não 403, sem oráculo).

**RF-SO-03 — Criar**
- **Descrição:** criação a partir das ações das telas (RF-HO-07, RF-HO-11, RF-CO-06, RF-ON-09, RF-PE-03) e, nesta tela, botão "Nova solicitação" (proposta) para o tipo `outro` (assunto + mensagem). Idempotência por `chave_idempotencia` (UUID gerado no cliente) e por regra de unicidade por tipo (seção 7).
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `POST /solicitacoes [C]` · **Evento:** `solicitacao_criar` · **Flag:** — · **Fase:** 3
- **UI:** toast "Solicitação enviada." para `outro` (proposta).
- **Aceite:** reenvio com a mesma chave devolve a mesma solicitação (200) sem nova linha; espelho no CRM criado pelo job em ≤ 2 min com hub disponível.

**RF-SO-04 — Cancelar**
- **Descrição:** disponível em `aberta` e `aguardando_associado`; confirmação em diálogo ("Cancelar esta solicitação?" — proposta).
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `POST /solicitacoes/{uuid}/cancelar [C]` · **Evento:** `solicitacao_cancelar` · **Flag:** — · **Fase:** 3
- **UI:** toast "Solicitação cancelada." (proposta); `409` → toast "Esta solicitação mudou de situação. Atualizamos a página." (proposta) e recarrega o detalhe.
- **Aceite:** transição condicional (`UPDATE … WHERE status IN (…)`); concorrência com o job resulta em exatamente um vencedor.

**RF-SO-05 — Responder**
- **Descrição:** em `aguardando_associado`, campo de resposta (texto 1–2000 caracteres) devolve para `em_analise`.
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `POST /solicitacoes/{uuid}/responder [C]` · **Evento:** `solicitacao_responder` · **Flag:** — · **Fase:** 3
- **UI:** toast "Resposta enviada." (proposta).
- **Aceite:** resposta fora de `aguardando_associado` → `409 estado_invalido`; texto entra em `solicitacao_evento` e é espelhado no CRM.

**RF-SO-06 — Sincronização com o CRM invisível ao associado**
- **Descrição:** `crm_id`, `crm_sync`, tentativas e erros de espelho nunca aparecem na UI nem na API; o associado vê só o status de negócio. Falha definitiva de espelho gera alerta operacional (seção 7), não mensagem ao associado.
- **Fonte:** `solicitacao` · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** —
- **Aceite:** teste de contrato garante ausência de chaves `crm_*` em todas as respostas.

**RF-SO-07 — Destaque de pendência**
- **Descrição:** contador de solicitações em `aguardando_associado` no item "Minhas solicitações" da sidebar/drawer.
- **Fonte:** `solicitacao` · **Endpoint:** `GET /sessao` (campo `solicitacoes_aguardando`) · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** badge com `aria-label` "{n} solicitações aguardando você" (proposta).
- **Aceite:** contador zera após responder ou cancelar.

---

### 3.13 Autenticação e sessão (AU)

**RF-AU-01 — Rotas da área exigem sessão**
- **Descrição:** `GET /area` e `GET /area/{path}` sem sessão → `303 /auth/login?next=<caminho>` via `safe_next` (comportamento existente: `app/main.py:189`, `app/session_guard.py:103`).
- **Fonte:** sessão · **Endpoint:** `GET /area/{path}` · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** —
- **Aceite:** `next` com `//`, `\`, esquema ou `/auth/` cai em `/area` (testes existentes de `safe_next` mantidos).

**RF-AU-02 — API sem sessão**
- **Descrição:** qualquer `/api/*` sem sessão → `401 {"erro":"nao_autenticado"}` (nunca 303); `LoginRequired` passa a distinguir prefixo `/api/`.
- **Fonte:** sessão · **Endpoint:** `/api/v1/*` · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** RF-AU-08.
- **Aceite:** teste: `fetch` sem cookie recebe 401 JSON.

**RF-AU-03 — `GET /api/v1/sessao`**
- **Descrição:** devolve: nome de exibição, iniciais, `tipo`, `status`, `tem_foto`, `csrf`, `rota_inicial`, `flags`, `config` (`whatsapp`, `show_whatsapp`, `animations`), `stub` (bool), `solicitacoes_aguardando`. Nunca CPF, `cpf_mask`, e-mail completo, `sub` ou `contact_id`.
- **Fonte:** sessão + `feature_flag` + `solicitacao` · **Endpoint:** `GET /sessao` · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** primeira chamada da SPA; falha → tela de erro do shell com "Tentar novamente".
- **Aceite:** `Cache-Control: no-store`; teste de contrato de chaves proibidas.

**RF-AU-04 — Rota inicial por persona**
- **Descrição:** regra da seção 1.2; aplicada só na entrada em `/area` (raiz) logo após o login (marca `rota_inicial_aplicada` na sessão).
- **Fonte:** sessão (`tipo`), `onboarding_progresso` · **Endpoint:** `GET /sessao` · **Evento:** — · **Flag:** — · **Fase:** 6 (regra), 1 (campo)
- **UI:** `navigate(replace)`.
- **Aceite:** acadêmico sem `finalizar` → `/area/onboarding`; demais → `/area`; segunda visita a `/area` na mesma sessão não redireciona.

**RF-AU-05 — CSRF da API**
- **Descrição:** todo método não seguro em `/api/` exige `X-CSRF-Token` igual a `session["csrf"]` (tempo constante, como `app/main.py:104`), `Origin == PUBLIC_BASE_URL` (ou `Sec-Fetch-Site: same-origin` quando `Origin` ausente) e `Content-Type` `application/json` ou `multipart/form-data`.
- **Fonte:** sessão · **Endpoint:** todos `[C]` · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** RF-SH-09.
- **Aceite:** falta/erro de qualquer condição → `403 csrf_invalido` (ou `415`), registrado em `evento_log` categoria `seguranca`.

**RF-AU-06 — Cookie de sessão**
- **Descrição:** `SessionMiddleware` `same_site=lax` (regra 7), Secure fora de `development`, conteúdo atual (`sub, cid, nome, email, cpf_mask, auth_at, amr, idt, csrf`) + `tipo` e `status` (rótulos curtos); cifrado e com nome `__Host-area` se D-11 for confirmada (P-17); teto absoluto `SESSION_ABSOLUTE_MAX`.
- **Fonte:** IdP · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** —
- **Aceite:** cookie < 4 kB no pior caso (nome 160, e-mail 254, `idt` real) — teste de tamanho; com D-11, conteúdo não decodificável em base64.

**RF-AU-07 — Logout**
- **Descrição:** botão "Sair" (texto não existe na spec — proposta, LA-25) na sidebar, no drawer e no perfil; `<form method="post" action="/auth/logout">` com `csrf` de `GET /sessao`; servidor limpa a sessão e redireciona ao `/oauth/logout` do IdP com `id_token_hint` (comportamento existente, `app/main.py:302-320`).
- **Fonte:** sessão · **Endpoint:** `POST /auth/logout` · **Evento:** — (registrado em `evento_log` `logout`) · **Flag:** — · **Fase:** 1
- **UI:** navegação top-level (não `fetch`), para o redirect ao IdP funcionar sob `form-action`.
- **Aceite:** após sair, `/area` exige login completo (sem SSO silencioso); E2E cobre o fluxo.

**RF-AU-08 — Expiração durante o uso**
- **Descrição:** 401 em qualquer chamada → SPA navega para `/auth/login?next=<rota atual>`; o IdP pode reautenticar por SSO silencioso e devolver à mesma rota.
- **Fonte:** — · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** sem toast (navegação imediata); formulários com dado digitado (perfil, resposta) alertam antes de sair (proposta).
- **Aceite:** E2E com cookie expirado retorna à mesma rota após login.

**RF-AU-09 — Login e callback (existentes)**
- **Descrição:** Authorization Code + PKCE S256, `validate_id_token` (`app/oidc.py:264`), userinfo fail-closed (`app/oidc.py:307`, 503 → sem sessão), mensagens por código (`app/main.py:79`). Escopos passam a incluir `carteirinha` (P-09; hoje `openid profile email cpf`, `app/config.py:67`). `tipo` e `status` gravados na sessão a partir de `tipo_associado` e `associado`.
- **Fonte:** IdP · **Endpoint:** `GET /auth/login`, `GET /auth/callback` · **Evento:** — (`evento_log` `login_ok`/`login_falha`) · **Flag:** — · **Fase:** 1 (escopo na 2)
- **UI:** página `erro.html` existente.
- **Aceite:** testes existentes de `tests/` seguem verdes; userinfo sem `tipo_associado` ou `associado` → login recusado com 403 `persona_incompleta` (decidido em 2026-10-17, ADR-0016).

**RF-AU-10 — Modo stub**
- **Descrição:** `AUTH_MODE=stub` só fora de produção (`app/config.py:152-156`); faixa de aviso visível também na SPA; formulário stub ganha campo de tipo para testar personas. Corrige o defeito `app/static/style.css:323` (`html.js .alert { display: none; }` esconde a faixa stub).
- **Fonte:** `Settings` · **Endpoint:** `GET|POST /auth/login` · **Evento:** — · **Flag:** — · **Fase:** 1
- **UI:** faixa com texto existente do `stub_login.html`/`base.html`.
- **Aceite:** `APP_ENV=production` + stub não sobe; faixa visível com JS ativo.

---

## 4. Requisitos não funcionais

| ID | Área | Requisito | Verificação |
|---|---|---|---|
| RNF-01 | Segurança · CSP | `default-src 'self'; script-src 'self' 'nonce-…'; style-src 'self'; img-src 'self' data: <CSP_IMG_HOSTS>; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://login.apm.org.br; object-src 'none'`. Sem `'unsafe-inline'`/`'unsafe-eval'`; estilos dinâmicos por classes e custom properties via CSSOM (D-13). Demais cabeçalhos de `app/main.py:167-181` mantidos. | `scripts/csp_check.py`; E2E falha em `securitypolicyviolation` |
| RNF-02 | Segurança · CSRF | RF-AU-05 em toda escrita `/api/`; formulários HTML (`/auth/*`) mantêm token de form. | testes de API |
| RNF-03 | Segurança · cookie | RF-AU-06; nada de token de acesso/refresh, CPF completo ou dado de perfil além do listado. | teste de tamanho e de conteúdo |
| RNF-04 | Segurança · fail-closed | Identidade parcial nunca abre sessão; escrita no CRM nunca é "otimista" (só confirma após 200 do hub); verificação pública nunca afirma status a partir de cache > 24 h; flag desconhecida = desligada. | testes de falha com stubs |
| RNF-05 | Segurança · limites | Vhost: `/api/` 20 r/s burst 40; `/verificar/` 2 r/s; `client_max_body_size 6m` só no location da foto (demais `/api/` 64k). App: edição de contato 10/h, upload de foto 5/h, renovação de perfil 1/5 min, por `contact_id` → `429 limite_taxa`. Zonas existentes `area_publico`/`area_auth` mantidas. | `nginx -t`; testes de limite |
| RNF-06 | Segurança · entrada | Pydantic com `extra="forbid"` em todos os corpos; tamanhos máximos explícitos; erro único (3.0); SQL parametrizado (regra 2). | testes de contrato |
| RNF-07 | Segurança · segredos e modos | Novos segredos (`HUB_CLIENT_SECRET`, `CARTEIRINHA_HMAC_KEY`, credencial RO do WordPress, chave de cifra da sessão) só em `Settings`/`.env`/Secrets Manager; `HUB_MODE=stub` e `WP_MODE=stub` proibidos com `APP_ENV=production` (validador derruba o boot). | testes de `config` |
| RNF-08 | Banco | TLS verificado (regra 9); grants da seção 6; `scripts/db_check.py` falha com `UPDATE` fora da allowlist ou qualquer `DELETE`; migrações `sql/003..010` com sha256 em `schema_migrations`. | `db_check.py` |
| RNF-09 | Upload | RF-PE-05: magic bytes, 25 MP, EXIF transpose, sem metadados, processamento em memória e em threadpool, nada em disco além de `/tmp` tmpfs. | testes com arquivos maliciosos |
| RNF-10 | Acessibilidade | WCAG 2.1 AA em todos os pares de cor (verificar `#9fb7c8` sobre navy e `#6b7a8d` sobre branco em texto pequeno); foco visível; `aria-pressed` em chips e marcadores; `aria-live="polite"` no toast; drawer e diálogos com `role="dialog"`, foco preso, Esc; alvos de toque ≥ 44 px; navegação completa por teclado. | axe-core no E2E |
| RNF-11 | Acessibilidade · métrica | Lighthouse acessibilidade ≥ 90 em `/area`, `/area/beneficios`, `/area/carteirinha` (e meta não bloqueante nas demais). | Lighthouse CI |
| RNF-12 | Desempenho | Bundle JS inicial ≤ 250 kB gzip (rotas pesadas por `lazy()`); fontes Figtree/JetBrains Mono self-hosted woff2, subset latin/latin-ext, `font-display: swap` (P-14); ícones SVG inline; imagens `loading="lazy"` com proporção fixa (CLS < 0,1); assets com hash `immutable`; API local p95 ≤ 300 ms, dependente de hub p95 ≤ 1,5 s (timeout 10 s). | `vite build --report`; Lighthouse |
| RNF-13 | Movimento | Tempos e easing da spec (RF-SH-10); desligados com `prefers-reduced-motion: reduce` e com `animations=false`. | E2E |
| RNF-14 | pt-BR · formatos | Moeda `Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'})` sem centavos quando inteiro (`R$ 1.240`); meses de 3 letras em caixa alta nos blocos de data (SET, OUT, JUL); datas `DD/MM/AAAA`; textos em pt-BR, tom da spec. | testes unitários de formatadores |
| RNF-15 | Fuso | Banco e API em UTC (ISO 8601 com `Z`); exibição e cálculos de "dias para", "hoje", "esta semana" em America/Sao_Paulo (tzdata na imagem). | testes com relógio fixo |
| RNF-16 | Privacidade / LGPD | CPF nunca na área (sessão só `cpf_mask`; API, banco, logs e `evento_uso` sem CPF — D-14); QR público só nome, status e validade; o associado nunca vê dado do patrocinador além do valor coberto; minimização: perfil em cache só com campos exibidos; `evento_uso` sem texto livre do usuário (termo de busca não é gravado); retenção por P-15. | teste de varredura de CPF em respostas e logs |
| RNF-17 | Observabilidade | `request_id` em toda resposta (`X-Request-Id`) e no corpo de erro; `evento_log` para segurança/erros; `evento_uso` para analytics (seção 8) em transação própria (D-12; `audit.registrar` comita a sessão recebida, `app/audit.py:125`); `job_execucao` por execução de job (início, fim, itens, erro); contador de falhas de `evento_uso` em `/db-health`; erros ao usuário sempre como toast amigável. | testes + inspeção de `/db-health` |
| RNF-18 | Resiliência | Conteúdo do site servido só do cache local (Locaweb fora não afeta o web); perfil em cache 24 h; TotalPass em cache 10 min; hub fora → `503 fonte_indisponivel` apenas nos endpoints que dependem dele (perfil, carteirinha sem cache, foto, escrita); solicitações aceitas com hub fora (outbox). | testes com stubs em falha |
| RNF-19 | Capacidade | Web: 400M, 2 workers Gunicorn/Uvicorn, `--timeout 60`; jobs em serviço separado `area-associado-jobs` (mesma imagem, 256M); Pillow limitado a 1 processamento por worker simultâneo (semáforo). | teste de carga leve + `docker stats` |
| RNF-20 | Compatibilidade | Navegadores evergreen (duas últimas versões de Chrome, Edge, Firefox, Safari/iOS Safari); 390 a 1440 px sem rolagem horizontal. | Playwright 390/1440 |
| RNF-21 | Persistência local | Nenhum dado do associado em `localStorage`/`sessionStorage`/IndexedDB; estado de domínio só no backend (spec, "Persistência local", com D-01). | lint + revisão |
| RNF-22 | Cache HTTP | `index.html` e `/api/*` com `no-store`; `/verificar/*` `no-store` + `noindex`; foto `private, no-cache` + ETag; assets da SPA `immutable`. | testes de cabeçalho |

---

## 5. Integrações por fonte

### 5.1 IdP — `login_associado` (`https://login.apm.org.br`)

- **Lemos:** id_token (`iss`, `sub` = HMAC do CPF, `aud`/`azp` = `area-associado`, `iat`, `exp`, `auth_time`, `amr` = `["pwd"]`, `nonce`, `contact_id` — `login_associado/app/oauth_service.py:319-330`); userinfo por escopo (`login_associado/app/userinfo.py:50-55`):

  | Escopo | Claims | Observação |
  |---|---|---|
  | `openid` | `sub`, `contact_id` | sempre |
  | `profile` | `name`, `given_name`, `family_name` | `name` = `fullname` ou first+last |
  | `email` | `email` | sem `email_verified` (cadastro por operador) |
  | `cpf` | `cpf` (11 dígitos) | só se HMAC = `sub`; a área guarda só `cpf_mask` (`app/oidc.py:336`) |
  | `carteirinha` (**a acrescentar**, P-09) | `num_contato`, `crm`, `crm_uf` (rótulo), `tipo_associado` (rótulo), `associado` (rótulo do status), `data_filiacao` (`AAAA-MM-DD` em São Paulo) | rótulos, não códigos; não há claim de validade nem de patrocínio |

- **Escrevemos:** nada.
- **Chave:** `sub` (sessão) e `contact_id` (integração).
- **Frequência:** a cada login (teto 12 h); back-channel `http://login_associado:8000` com `Host: login.apm.org.br`.
- **Falha e degradação:** fail-closed (regra 5): userinfo 503, JWKS indisponível, `sub` divergente → sem sessão, página de erro com `request_id`.
- **Pendência:** P-09 (`OIDC_SCOPES`, `scripts/check_oidc.py`, `docs/CUTOVER.md:20` registra hoje `openid profile email cpf`). Avaliar remover o escopo `cpf` quando `cpf_mask` deixar de ser exibido (minimização).

### 5.2 `mcp_hub` — leitura

- **Lemos:** `associado.consultar` (perfil do contact: nome, e-mail, telefones, endereço, nascimento, sexo, CRM/UF, tipo, status, filiação, foto se exposta), `totalpass.adesao_consultar` (adesão em `dxc_adesao_totalpass`), `financeiro.faturas_associado` (Fase 7, flag `erp_financeiro`).
- **Chave:** `contact_id` — exige P-04 (hoje as duas primeiras pedem CPF); a área nunca envia CPF.
- **Transporte:** `POST http://mcp_hub:8000/oauth/token` (`Host: mcp.apm.org.br`, `client_secret_basic`, escopo `ferramentas:ler`), token em memória de processo com lock, 1 renovação em 401; `POST /api/v1/ferramentas/{nome}`; timeout 10 s; `run_in_threadpool`; `HubError` tipado. Settings: `HUB_BASE_URL`, `HUB_PUBLIC_HOST`, `HUB_CLIENT_ID`, `HUB_CLIENT_SECRET`, `HUB_MODE=real|stub`.
- **Frequência:** perfil sob demanda com cache 24 h (+ job `atualizar_perfis` diário); TotalPass por exibição com cache 10 min.
- **Cotas:** hoje 500 PII/dia e 60/min por principal — inviável para app; P-03 (override por conta).
- **Falha e degradação:** RNF-18; perfil com cache; TotalPass sem estado; ERP omitido.
- **Pendências:** P-02 (provisionar hub e conta `area-associado` com `modo_pii=completo`), P-03, P-04.

### 5.3 `mcp_hub` — escrita (extensão, plano próprio no repositório do hub)

- **Ferramentas novas:** `associado.contato_atualizar` (PATCH `contact` com allowlist = campos de regime direto da seção 9, `If-Match: *`), `associado.foto_atualizar` (PUT `entityimage`, JPEG 512×512), `solicitacao.espelhar` (cria registro CRM, devolve `crm_id`), `solicitacao.status_atualizar` (cancelamento/resposta do associado), `solicitacao.alteracoes_consultar` (registros alterados desde um cursor, para o sync de volta).
- **Pré-requisitos no hub:** `Ferramenta.efeito = leitura|escrita` e escrita só por REST; escopos `ferramentas:ler|escrever` por conta de serviço (claim `scope`); auditoria de intenção bloqueante antes e `auditoria_escrita` (INSERT-only) depois; taxa separada para escrita; conector `dataverse_escrita.py` com credencial própria.
- **Chave:** `contact_id`; para solicitações, `uuid` da área como chave de correlação + `crm_id`.
- **Frequência:** contato/foto síncronos à ação do associado; espelho por job (1 min); sync de volta (5 min).
- **Falha e degradação:** contato/foto → `503` ao associado (nada gravado no cache); solicitações → outbox com backoff (seção 7).
- **Pendência:** P-05 (app registration de escrita no Entra, application user, security role mínima: contact write restrito, task create/write).

### 5.4 CRM Dataverse (D365) — entidades tocadas (sempre via hub)

| Entidade | Leitura | Escrita | Observação |
|---|---|---|---|
| `contact` | perfil, carteirinha, status, foto | campos de regime direto; `entityimage` | nenhum projeto escreve hoje em `contact`; padrão de escrita robusta em `app_facial_recognition/api/services/DynamicsLeadService.php` (PATCH `If-Match: *`, retry único) |
| `task` (proposta, P-06) | status das solicitações | criação (regarding contact) e atualização | alternativa: entidade custom; mapeamento de `statecode/statuscode` na seção 7 |
| `dxc_adesao_totalpass` | adesão TotalPass | — | via `totalpass.adesao_consultar` |
| `sol_associacao` | — (lida pelo IdP no gate) | — | última associação Ativa = `100000001` |

- **Limite:** 6.000 requisições / 5 min por usuário de aplicação (compartilhado com o hub) — perfil em cache, sync incremental por cursor.
- **Flows:** disparam em create; criar `task` pode acionar flows existentes (e-mails, atribuições) — verificar em P-06 antes da Fase 3.
- **Paginação:** `dataverse.py` do hub só faz GET e não segue `@odata.nextLink` — corrigir na extensão para `solicitacao.alteracoes_consultar`.

### 5.5 ERP Dynamics 365 F&O — somente leitura

- **Lemos:** faturas/lançamentos do associado (`CustTransactions`) para "valor pago no ano" e, futuramente, mensalidade (RF-FA-05, RF-HO-02).
- **Chave:** o ERP só localiza cliente por CPF (`CustomersV3.BrazilianCNPJOrCPF`); a resolução `contact_id → CPF → cliente` acontece **dentro do hub**; a área envia só `contact_id`.
- **Frequência:** sob demanda com cache curto (a definir no plano da Fase 7).
- **Falha e degradação:** dado omitido na UI; nunca bloqueia outra tela.
- **Pendência:** P-08 (parecer de licença/multiplexação, `totalpass/docs/RUNBOOK_ERP_FO.md:205-211`); flag `erp_financeiro`.

### 5.6 WordPress `portal_apm` (Locaweb)

- **Lemos (só o job `sincronizar_portal`):** `pw_portal_posts`, `pw_portal_postmeta`, `pw_portal_term_relationships`, `pw_portal_term_taxonomy`, `pw_portal_terms`, `pw_portal_yoast_indexable` (6 tabelas). Post types: `evento` (taxonomia `categoria_do_evento`; metas `data`, `data_do_webinar`, `hora`, `hora_do_webinar`, `local`, `link_externo`, `youtube`, `este_evento_e_um_webinar`), posts de notícia (post type e taxonomia de tema a confirmar em P-07), banners (Congresso). Queries de referência: `appapm/src/includes/{eventos,banners,regionais}_portal_service.php`.
- **Escrevemos:** nada.
- **Chave:** `ID` do post → `noticia_cache.portal_id` / `evento_cache.portal_id`.
- **Frequência:** a cada 15 min; upsert por `portal_id` + `post_modified`; itens despublicados marcados inativos (sem `DELETE`).
- **Segurança:** usuário novo somente leitura (SELECT nas 6 tabelas), rotação e revogação de `portal_apm@%` (credencial vazada, grant aberto), TLS se a Locaweb suportar (senão: ADR-0006 registra o risco aceito), host de imagens validado contra `CSP_IMG_HOSTS` (fora → placeholder), HTML do conteúdo **não** é renderizado na SPA (só título, resumo em texto puro e link).
- **Falha e degradação:** job falha → `job_execucao` com erro, cache anterior continua servido, "atualizado em DD/MM" (RF-NE-01).
- **Pendências:** P-07, P-16 (appapm migrar para o usuário RO).

### 5.7 TotalPass

- **Lemos:** adesão via hub (5.2). Elegibilidade: status 2 ou 3 (na área, efetivamente 2 — seção 1.2).
- **Escrevemos:** nada; ativação por deep-link `https://totalpass.apm.org.br` (nova aba).
- **Chave:** `contact_id` (P-04).
- **Frequência:** cache 10 min por `contact_id` em memória de processo.
- **Falha e degradação:** RF-BE-10.
- **Flag:** `totalpass`.

### 5.8 WhatsApp e Clube

- **WhatsApp:** `https://wa.me/<numero>?text=<mensagem URL-encoded>`; Central APM com número de `Settings` (padrão `551131886200`, `SHOW_WHATSAPP`); comunidades com número/link por comunidade no seed (P-11). `wa.me` abre conversa 1:1 com o número, não entra em grupo (LA-09). Nenhuma API do WhatsApp é chamada; nada é lido.
- **Clube:** `https://clubapm.com.br` (Clube Certo, marca APM), nova aba, `noopener`; nenhuma integração de dados (economia/cashback sem fonte — `clube_economia`).
- **Registro:** só o clique (`central_whatsapp_abrir`, `comunidade_abrir`, `clube_oferta_usar`).
- **Falha:** não se aplica (link).

---

## 6. Modelo de dados lógico

Convenções: chave de associado `contact_id CHAR(36)` (D-14), `sub_hash CHAR(64)` quando
necessário (HMAC com `LOG_HASH_KEY`), datas `DATETIME(6)` UTC, JSON com `CHECK` que recusa chaves
proibidas (mesma lista de `app/audit.py:29`), remoção lógica por coluna (sem `DELETE`).

| Entidade | Descrição | Dono da verdade | Tabela física | Grant | Fase |
|---|---|---|---|---|---|
| Migração | controle de `sql/NNN` com sha256 | operador | `schema_migrations` (existente, `sql/001`) | SELECT | existente |
| Trilha de segurança | eventos de login, logout, CSRF, erros | área | `evento_log` (existente, `sql/002`) | INSERT | existente |
| Feature flag | chave, ligada, descrição | área (operador) | `feature_flag` (`sql/003`) | SELECT | 1 |
| Evento de uso | analytics (seção 8) | área | `evento_uso` (`sql/004`) | INSERT | 1 |
| Associado | `contact_id`, `sub_hash`, primeiro/último acesso, token de verificação da carteirinha | IdP/CRM (identidade); área (token) | `associado` (`sql/005`) | SELECT, INSERT, UPDATE | 1–2 |
| Perfil | cache dos campos de `contact` exibidos + `foto_miniatura` (128×128) + ETag + `atualizado_em` | CRM `contact` | `associado_perfil` (`sql/006`) | SELECT, INSERT, UPDATE | 2 |
| Verificação de e-mail | pedido de troca: HMAC do e-mail novo e do código, validade, tentativas | área | `email_verificacao` (`sql/007`) | SELECT, INSERT, UPDATE | 2 |
| Foto | 512×512 em `entityimage` | CRM | (CRM) + `associado_perfil.foto_miniatura` | — | 2 |
| Carteirinha | derivada de perfil + regra de validade (LA-04) | CRM | — (derivada) | — | 2 |
| Solicitação | tipo, dados, status, `uuid`, `chave_idempotencia`, `crm_id`, `crm_sync`, tentativas, próxima tentativa | área (pedido); CRM (andamento) | `solicitacao` (`sql/008`) | SELECT, INSERT, UPDATE | 3 |
| Evento de solicitação | linha do tempo (transição, ator, mensagem pública) | área | `solicitacao_evento` (`sql/008`) | SELECT, INSERT | 3 |
| Categoria | 8 categorias (tiles) + grupo de exibição (4) + cores/ícone/destino | área (seed editorial) | `beneficio_categoria` (`sql/009`) | SELECT | 4 |
| Benefício | catálogo (19 itens no seed inicial): slug, categoria, ícone, título, descrição, meta, CTA, tag, URL, valor de referência | área (seed editorial, negócio) | `beneficio` (`sql/009`) | SELECT | 4 |
| Ativação de benefício | associado × benefício, ativo, ativado/desativado em | área | `beneficio_ativacao` (`sql/009`) | SELECT, INSERT, UPDATE | 4 |
| Adesão TotalPass | adesão no CRM | CRM `dxc_adesao_totalpass` | — (cache em memória 10 min) | — | 4 |
| Notícia | cache de posts do site | WordPress | `noticia_cache` (`sql/010`) | SELECT, INSERT, UPDATE | 5 |
| Evento | cache de eventos do site (inclui Congresso) | WordPress | `evento_cache` (`sql/010`) | SELECT, INSERT, UPDATE | 5 |
| Tema | temas disponíveis | área (seed) | `tema` (`sql/010`) | SELECT | 5 |
| Tema seguido | associado × tema, ativo | área | `associado_tema` (`sql/010`) | SELECT, INSERT, UPDATE | 5 |
| Notícia salva | associado × notícia, ativo | área | `noticia_salva` (`sql/010`) | SELECT, INSERT, UPDATE | 5 |
| Inscrição em evento | associado × evento (inclui Congresso), ativo | área (interesse; LA-06) | `evento_inscricao` (`sql/010`) | SELECT, INSERT, UPDATE | 5 |
| Comunidade / programa | comunidades e programas (`rede`, embaixadores), link `wa.me`, contagens opcionais | área (seed, comunicação) | `comunidade` (`sql/011`) | SELECT | 6 |
| Adesão a comunidade | associado × comunidade/programa, ativo | área | `comunidade_adesao` (`sql/011`) | SELECT, INSERT, UPDATE | 6 |
| Passo de onboarding | 6 passos + `finalizar`, valor anual, CTA | área (seed) | `onboarding_passo` (`sql/011`) | SELECT | 6 |
| Progresso de onboarding | associado × passo concluído (append) | área | `onboarding_progresso` (`sql/011`) | SELECT, INSERT | 6 |
| Conteúdo editorial | oferta da semana, ofertas do clube, trilhas do Congresso, coberturas | comunicação (P-11) | — (`app/dominio/catalogo.py`, versionado) | — | 5–6 |
| Execução de job | job, início, fim, status, itens, erro resumido | área | `job_execucao` (`sql/012`) | SELECT, INSERT, UPDATE | 3 |
| Post de comunidade | — | sem fonte | — | — | fora (flag) |
| Mensalidade / patrocínio | valores e patrocinador | negócio/ERP (P-12) | — | — | 8 |
| Fatura de valor | derivada de `beneficio_ativacao` × valor | área (cálculo) | — (derivada) | — | 8 |
| Fatura financeira | lançamentos do associado | ERP | — (sem persistência) | — | 7 |

Allowlist de `UPDATE` (`scripts/db_check.py: TABELAS_COM_UPDATE`): `associado`, `associado_perfil`,
`solicitacao`, `beneficio_ativacao`, `noticia_cache`, `evento_cache`, `associado_tema`,
`noticia_salva`, `evento_inscricao`, `comunidade_adesao`, `job_execucao`, `email_verificacao`. `DELETE`: nenhuma tabela.

---

## 7. Solicitações — máquina de estados

### 7.1 Estados

| Estado (interno) | Rótulo ao associado | Terminal |
|---|---|---|
| `aberta` | Recebida | não |
| `em_analise` | Em análise | não |
| `aguardando_associado` | Aguardando você | não |
| `concluida` | Concluída | sim |
| `recusada` | Não aprovada | sim |
| `cancelada` | Cancelada | sim |

### 7.2 Diagrama

```
                (associado: POST /solicitacoes)
                              │
                              ▼
   ┌──────────────────────  aberta  ──────────────────────┐
   │ cancelar (associado)     │ (CRM: em atendimento)      │
   │                          ▼                            │
   │                     em_analise ───(CRM)──▶ concluida  │
   │                       │    ▲    └──(CRM)──▶ recusada  │
   │          (CRM: pede   │    │ responder                │
   │           retorno)    ▼    │ (associado)              │
   │               aguardando_associado                    │
   │                       │ cancelar (associado)          │
   ▼                       ▼                               │
 cancelada ◀───────────────┘                               │
```

### 7.3 Transições

| De | Para | Ator | Gatilho | Efeitos |
|---|---|---|---|---|
| — | `aberta` | associado | `POST /solicitacoes` | `INSERT solicitacao` (`crm_sync=pendente`) + `INSERT solicitacao_evento` (`criada`) na mesma transação; depois `uso.registrar(solicitacao_criar)`; job `espelhar_solicitacoes` cria no CRM |
| `aberta` | `em_analise` | sistema (CRM) | sync de volta detecta registro em atendimento | `UPDATE` condicional + `INSERT solicitacao_evento`; `solicitacao_status_alterado` |
| `aberta` | `cancelada` | associado | `POST …/cancelar` | `UPDATE` condicional + evento; `crm_sync=pendente` (propaga via `solicitacao.status_atualizar`); `solicitacao_cancelar` |
| `em_analise` | `aguardando_associado` | sistema (CRM) | atendente pede retorno (mensagem pública obrigatória) | `UPDATE` + evento com mensagem; contador em `GET /sessao`; `solicitacao_status_alterado` |
| `em_analise` | `concluida` | sistema (CRM) | atendimento encerrado com sucesso | `UPDATE` + evento; para `alteracao_cadastro`, invalida `associado_perfil` (renovação no próximo acesso ou pelo job) |
| `em_analise` | `recusada` | sistema (CRM) | atendimento encerrado sem aprovação (motivo público recomendado) | `UPDATE` + evento |
| `aguardando_associado` | `em_analise` | associado | `POST …/responder` | `UPDATE` + evento com texto; `crm_sync=pendente` (resposta espelhada); `solicitacao_responder` |
| `aguardando_associado` | `cancelada` | associado | `POST …/cancelar` | idem cancelamento |

Qualquer outra transição é inválida. Estados terminais não mudam.

### 7.4 Tipos fechados

| Tipo | Rótulo (proposta) | Origem | Campos obrigatórios | Opcionais | Unicidade |
|---|---|---|---|---|---|
| `alteracao_cadastro` | Alteração de cadastro | RF-PE-03 | `alteracoes` (`{campo: novo_valor}`, campos ∈ regime "com aprovação", ≥ 1) | `justificativa` (≤ 500) | 1 não terminal por campo |
| `diagnostico_marketing` | Diagnóstico de marketing | RF-HO-07 | — (clique único) | — | 1 não terminal |
| `submeter_trabalho` | Publicação na revista | RF-HO-11, RF-NE-07 | — (clique único, LA-02) | `titulo` (≤ 200) | 1 não terminal |
| `mentoria_pedir` | Quero um mentor | RF-CO-06, RF-ON-06 | — | `area_interesse` (≤ 120) | 1 não terminal |
| `mentoria_oferecer` | Quero ser mentor | RF-CO-06 | — | `area_interesse` (≤ 120) | 1 não terminal |
| `cartao_apm` | Cartão APM | RF-ON-09 | — | — | 1 não terminal |
| `outro` | Outro assunto | RF-SO-03 | `assunto` (1–120), `mensagem` (1–2000) | — | sem limite (taxa 5/dia) |

Dados de contato não são copiados para a solicitação: o atendente os vê no contact (regarding).

### 7.5 Espelho no CRM

- **Outbox:** `solicitacao.crm_sync ∈ {pendente, ok, erro, falhou}`, `crm_tentativas`, `crm_proxima_tentativa`. Job `espelhar_solicitacoes` (1 min) processa `pendente`/`erro` vencidos: sem `crm_id` → `solicitacao.espelhar`; com `crm_id` → `solicitacao.status_atualizar` (cancelamento/resposta).
- **Backoff:** exponencial 1, 2, 4, 8, 16, 32, 60, 60, 60, 60 min; após **10 tentativas** → `falhou`, `evento_log` severidade `erro` e `job_execucao` com contagem; reprocessamento manual pelo operador (`UPDATE crm_sync='pendente'`, documentado em `docs/JOBS.md`).
- **Idempotência do espelho:** o `uuid` da área vai como chave de correlação; `solicitacao.espelhar` deve devolver o registro existente se o `uuid` já existir (reenvio após timeout não duplica).
- **Sync de volta:** job `sincronizar_solicitacoes` (5 min) chama `solicitacao.alteracoes_consultar` com cursor (`modifiedon`) e aplica transições válidas; transição inválida (ex.: CRM concluiu algo cancelado localmente) não é aplicada — estado terminal local prevalece, divergência vai a `evento_log` (aviso) e o cancelamento é reenviado.
- **Mapeamento proposto para `task` (P-06):** `statecode=0`/status "Não iniciado" → `aberta`; "Em andamento" → `em_analise`; "Aguardando outra pessoa" → `aguardando_associado`; `statecode=1` (Concluída) → `concluida`; `statecode=2` (Cancelada) pelo atendente → `recusada`. Mensagem pública: campo dedicado a definir em P-06 (nunca a descrição interna da task).

### 7.6 Regras

- Só o dono vê e age: toda consulta filtra por `contact_id` da sessão; `uuid` de outro → `404`.
- Transição concorrente: `UPDATE … SET status=:novo WHERE uuid=:u AND contact_id=:c AND status IN (:origens)`; 0 linhas → `409 estado_invalido`.
- `UPDATE solicitacao` + `INSERT solicitacao_evento` sempre na mesma transação; `evento_uso` depois, em transação própria.
- Criação idempotente: `chave_idempotencia` única por `contact_id`; tipos de clique único devolvem a solicitação não terminal existente (200).
- Nenhum dado proibido (`app/audit.py:29`) em `dados`/`mensagem`; texto livre limitado e sem HTML.

---

## 8. Catálogo de eventos de uso (analytics)

Registro: `{contact_id, acao, entidade, entidade_id, origem, request_id, criado_em (UTC), detalhes}`
em `evento_uso` (spec: `{associadoId, acao, entidade, id, timestamp}`). `acao` validada contra
catálogo fechado em `app/uso.py`; ação desconhecida é descartada com log. Eventos de origem `ui`
chegam em lote por `POST /api/v1/uso [C]` (`keepalive`, máx. 20 por lote, 60 lotes/min por
sessão); o servidor ignora `contact_id` vindo do cliente e usa o da sessão.

| # | `acao` | `entidade` | Quando dispara | Origem | RF |
|---|---|---|---|---|---|
| 1 | `pagina_ver` | `rota` | troca de rota na SPA | ui | SH-01 |
| 2 | `busca_global` | `rota` | busca com ≥ 2 caracteres após debounce (sem o termo) | ui | SH-04, BE-04 |
| 3 | `filtro_aplicar` | `beneficio`/`noticia` | chip de filtro, tema, categoria ou "Limpar filtros" | ui | BE-02, BE-03, BE-06, NE-02, HO-10 |
| 4 | `categoria_abrir` | `beneficio_categoria` | clique em tile ou "Conhecer" | ui | HO-06, HO-08 |
| 5 | `beneficio_ativar` | `beneficio` | ativação gravada | servidor | BE-07 |
| 6 | `beneficio_desativar` | `beneficio` | desativação gravada | servidor | BE-08 |
| 7 | `beneficio_gerenciar` | `beneficio` | abertura do diálogo "Gerenciar" | ui | BE-08 |
| 8 | `beneficio_abrir` | `beneficio` | CTA que abre link do benefício | ui | BE-09, ON-06 |
| 9 | `totalpass_abrir` | `beneficio` | deep-link TotalPass | ui | BE-10, ON-06 |
| 10 | `plantoes_abrir` | `beneficio` | abertura do banco de plantões | ui | ON-08 |
| 11 | `clube_oferta_usar` | `oferta` | "Usar agora" / "Usar" | ui | CL-03, CL-04 |
| 12 | `noticia_abrir` | `noticia` | abertura de matéria | ui | NE-03, NE-06, HO-10 |
| 13 | `noticia_salvar` | `noticia` | salvar gravado | servidor | NE-04 |
| 14 | `noticia_dessalvar` | `noticia` | dessalvar gravado | servidor | NE-04 |
| 15 | `tema_seguir` | `tema` | tema adicionado em `PUT /temas` | servidor | NE-05 |
| 16 | `tema_deixar` | `tema` | tema removido em `PUT /temas` (reservado, LA-30) | servidor | NE-05 |
| 17 | `evento_inscrever` | `evento` | inscrição gravada | servidor | EV-05 |
| 18 | `congresso_garantir_vaga` | `evento` | vaga do Congresso gravada | servidor | HO-04, EV-02, ON-06 |
| 19 | `congresso_programacao_abrir` | `evento` | "ver programação →" / "ver programação completa →" | ui | HO-04, EV-01 |
| 20 | `comunidade_entrar` | `comunidade` | adesão gravada | servidor | CO-01 |
| 21 | `comunidade_abrir` | `comunidade` | "Abrir" (`wa.me`) | ui | CO-02 |
| 22 | `programa_saber_mais` | `comunidade` | "Saber mais" de programa | ui | CO-03 |
| 23 | `rede_entrar` | `comunidade` | adesão à rede gravada | servidor | CO-05 |
| 24 | `solicitacao_criar` | `solicitacao` (`detalhes.tipo`) | solicitação criada | servidor | HO-07, HO-11, NE-07, CO-06, ON-09, PE-03, SO-03 |
| 25 | `solicitacao_cancelar` | `solicitacao` | cancelamento pelo associado | servidor | SO-04 |
| 26 | `solicitacao_responder` | `solicitacao` | resposta do associado | servidor | SO-05 |
| 27 | `solicitacao_status_alterado` | `solicitacao` | transição aplicada pelo sync do CRM | servidor (job) | seção 7 |
| 28 | `onboarding_passo_concluir` | `onboarding_passo` | passo concluído (inclui `finalizar`) | servidor | ON-05, ON-06, ON-11 |
| 29 | `perfil_contato_atualizar` | `associado_perfil` (`detalhes.campos`) | edição direta confirmada pelo hub | servidor | PE-02 |
| 30 | `perfil_foto_atualizar` | `associado_perfil` | foto confirmada pelo hub | servidor | PE-05 |
| 31 | `carteirinha_compartilhar` | `carteirinha` | link de verificação gerado | servidor | CA-04 |
| 32 | `carteirinha_verificar` | `carteirinha` | página pública aberta com token válido | publico | CA-03 |
| 33 | `wallet_adicionar` | `carteirinha` | "+ Adicionar à Wallet" (flag) | ui | CA-05 |
| 34 | `fatura_pdf_baixar` | `fatura` | PDF gerado (flag) | servidor | FA-02 |
| 35 | `central_whatsapp_abrir` | `central` | clique no FAB | ui | SH-08 |
| 36 | `erro_exibido` | `rota` (`detalhes.codigo`, `request_id`) | toast de erro exibido | ui | SH-09, PE-08 |

---

## 9. Perfil — campos editáveis

| Campo CRM (`contact`) | Rótulo (proposta) | Regime | Validação (cliente e servidor) | Observação |
|---|---|---|---|---|
| `mobilephone` | Celular | direto | só dígitos após normalização; DDD válido (11–99, lista ANATEL); 9 dígitos iniciando em 9 | gravado no formato já usado no CRM (confirmar em P-05) |
| `telephone1` | Telefone | direto | DDD válido + 8 ou 9 dígitos; vazio permitido | — |
| `telephone2` | Telefone alternativo | direto | idem | — |
| `emailaddress1` | E-mail | **direto com código no novo endereço + login recente no IdP** (decidido em 2026-10-17, ADR-0015) | ≤ 254, sintaxe estrita, minúsculas; código de 6 dígitos, 10 min, 5 tentativas, 60 s entre envios, 5/h | aviso de troca enviado ao e-mail antigo |
| `address1_postalcode` | CEP | direto | 8 dígitos | preenchimento automático de endereço por CEP fora de escopo |
| `address1_line1` | Logradouro | direto | 1–250, sem caracteres de controle | semântica de `line1/2/3` a confirmar com o CRM (P-05) |
| `address1_line2` | Número | direto | 1–20 | idem |
| `address1_line3` | Complemento | direto | 0–250 | idem |
| `address1_city` | Cidade | direto | 1–80 | — |
| `address1_stateorprovince` | UF | direto | sigla de UF válida (27) | — |
| `entityimage` | Foto | direto (endpoint próprio) | RF-PE-05 | 512×512 JPEG no CRM; miniatura local |
| `firstname` | Nome | com aprovação | 2–80, letras (com acento), espaço, `'` e `-` | via `alteracao_cadastro` |
| `lastname` | Sobrenome | com aprovação | idem | via `alteracao_cadastro` |
| `birthdate` | Data de nascimento | com aprovação | data válida; idade entre 16 e 110 anos (America/Sao_Paulo) | via `alteracao_cadastro` |
| `alf_sexo` | Sexo | com aprovação | valor do option set do CRM (rótulos lidos do hub) | via `alteracao_cadastro`; também define concordância (LA-19) |
| `sol_st_cpf` | CPF | nunca | — | nunca exibido nem trafegado na área |
| `sol_st_numerocrm` | CRM | nunca | — | exibido |
| `alf_uf_crm` | UF do CRM | nunca | — | exibido |
| `alf_status_associativo` | Situação | nunca | — | exibido como rótulo |
| `alf_tipo_associado` | Categoria | nunca | — | exibido como rótulo |
| `alf_num_contato` | Número de associado | nunca | — | exibido |
| `alf_data_filiacao` | Associado desde | nunca | — | exibido (ano/data) |

**Regras gerais.** Regime "direto": limite 10 edições/h por associado; auditoria (`evento_log` e
`evento_uso`) registra só os **nomes** dos campos; allowlist idêntica na área e no hub (dupla
checagem); cache atualizado só após confirmação do hub. Regime "com aprovação": nunca escreve no
CRM pela área; cria solicitação (seção 7). Regime "nunca": rejeitado em qualquer endpoint.

**Foto.** Multipart, ≤ 5 MB, JPEG/PNG/WebP por magic bytes, `MAX_IMAGE_PIXELS` 25 MP, EXIF
transpose, metadados removidos, recorte quadrado, 512×512 JPEG q85 para o CRM, 128×128 para
`associado_perfil.foto_miniatura` com ETag; processamento em memória e em `run_in_threadpool`;
5 uploads/h; vhost `client_max_body_size 6m` no location da foto. Remoção não suportada (LA-15).

---

## 10. Feature flags

Fonte: `feature_flag` + `FLAGS_FORCAR_DESLIGADAS` (CSV em `Settings`, vence a tabela); cache 60 s;
entregues em `GET /sessao`. Flag ausente ou desconhecida = desligada.

| Chave | Padrão | O que oculta na UI | Resposta da API | Pendência que libera |
|---|---|---|---|---|
| `mensalidade_zero` | desligada | card Mensalidade Zero (HO-02), pill do header, bloco do rodapé da sidebar, trecho do rodapé "Como funciona", trecho do hero e chip do onboarding, seção "O QUE A SUA MENSALIDADE COBRE" | bloco `mensalidade` ausente de `GET /sessao`/`GET /onboarding` | P-12 |
| `fatura_valor` | desligada | rota `/area/fatura`, item de menu, card da home (HO-03), estatística "aproveitados" do hero de benefícios | `GET /fatura`, `GET /fatura/pdf` → `404 recurso_desligado` | P-12 |
| `patrocinio` | desligada | tag `patrocinado`, borda âmbar, chip "Patrocinados" | campo `patrocinado` omitido em `GET /beneficios` | P-12 (LA-28) |
| `clube_economia` | desligada | estatísticas de economia/cashback (hero do clube e de benefícios), "Sua economia no clube", "Por que usar por aqui", meta "cashback ativo" | campos de economia omitidos em `GET /clube` | fonte do Clube Certo (sem P-xx; abrir) |
| `comunidade_posts` | desligada | "CONVERSAS EM DESTAQUE" | sem endpoint | LA-13 (P-10/P-11) |
| `wallet` | desligada | "+ Adicionar à Wallet" na carteirinha | endpoint da Fase 8 → `404 recurso_desligado` | P-13 |
| `erp_financeiro` | desligada | "você pagou … no ano" e múltiplo "↗ n×" | `GET /financeiro/faturas` → `404 recurso_desligado` | P-08 |
| `totalpass` | desligada | card TotalPass em benefícios e passo do onboarding | campo `totalpass` omitido em `GET /beneficios` | P-02, P-04 |

Configurações (não são flags de produto, ficam em `Settings`): `WHATSAPP_CENTRAL` (padrão
`551131886200`), `SHOW_WHATSAPP`, `ANIMATIONS`.

---

## 11. Lacunas e ambiguidades

Cada lacuna tem uma **proposta padrão** já refletida nos RFs; a implementação segue a proposta até
decisão do dono.

| ID | Lacuna | Impacto | Proposta padrão adotada | Dono | Pendência |
|---|---|---|---|---|---|
| LA-01 | Três vocabulários de categoria: grupos de benefícios (4: TECNOLOGIA E IA; CONSULTÓRIO E FINANÇAS; SAÚDE, BEM-ESTAR E PROTEÇÃO; EDUCAÇÃO E CARREIRA), tiles da home (8: Tecnologia e IA, Consultório e prática, Saúde mental e bem-estar, Finanças e proteção, Educação e carreira, Defesa e jurídico, Comunidade, Vida e lazer) e barras da fatura (Consultório, Tecnologia e IA, Saúde e bem-estar) | filtro por tile, contagens e agregação da fatura inconsistentes | categoria (8) é atributo do benefício; grupo (4) é agrupamento de categorias: Tecnologia e IA → TECNOLOGIA E IA; Consultório e prática e Finanças e proteção → CONSULTÓRIO E FINANÇAS; Saúde mental e bem-estar e Defesa e jurídico → SAÚDE, BEM-ESTAR E PROTEÇÃO; Educação e carreira → EDUCAÇÃO E CARREIRA; barras da fatura usam o grupo | negócio | P-10 |
| LA-02 | Toasts sem texto: submeter trabalho, Wallet, mentoria (pedir e oferecer), embaixadores, rede de encaminhamento, garantir vaga no Congresso, desativar benefício, pedir Cartão APM | feedback inconsistente; risco de prometer o que não acontece | propostas: "Recebemos seu interesse em publicar. A equipe da revista entra em contato." · "Carteirinha adicionada à Wallet." · "Pedido de mentoria recebido. Acompanhe em Minhas solicitações." · "Obrigado! Recebemos seu interesse em ser mentor." · "Abrindo Embaixadores acadêmicos…" · rede: sem toast (rótulo "Você está na rede ✓" basta) · Congresso: sem toast até LA-07 · "{título} desativado" · "Pedido do Cartão APM recebido. Acompanhe em Minhas solicitações." | comunicação | P-10 |
| LA-03 | Destino de "Gerenciar" | sem forma de desativar ou acessar benefício ativo | diálogo com "Acessar" e "Desativar" (RF-BE-08) | negócio | P-10 |
| LA-04 | Regra de validade da carteirinha ("válida até 12/2026"); não há claim nem campo conhecido | carteirinha e verificação pública podem afirmar validade falsa | omitir "válida até" no cartão; verificação mostra status + "verificado em" | negócio / CRM | P-10, P-09 · **Decidido (2026-10-17): omitir a validade até regra do negócio; mostrar situação e "verificado em".** |
| LA-05 | E-mail editável direto × com verificação de posse | e-mail é canal de segurança do IdP; troca sem verificação permite sequestro de notificações | direto (plano), com auditoria e limite; reavaliar verificação por código antes da Fase 2 com Sentinela | negócio / Sentinela | P-10 · **Decidido (2026-10-17): direto com código no novo e-mail + reautenticação recente (ADR-0015).** |
| LA-06 | "Inscrever" em evento: interesse local × inscrição real no site/sistema de eventos | associado pode acreditar estar inscrito sem estar | registra interesse local e abre `link_externo` do evento quando existir; toast da spec mantido | negócio | P-10, P-07 |
| LA-07 | "Garantir minha vaga" no Congresso: onde a inscrição acontece de fato; Congresso 2026 (26–28/09) já ocorreu | promessa de vaga sem inscrição; banner desatualizado | registra interesse; banner/hero só com Congresso futuro no cache; CTA abre a página de inscrição do site quando houver link | negócio | P-10 |
| LA-08 | Entidade do CRM para solicitações (`task` × custom), mapeamento de status e campo de mensagem pública; flows em create | bloqueia espelho (Fase 3) | `task` regarding contact, mapeamento da seção 7.5 | CRM / negócio | P-06 |
| LA-09 | Número da Central e links por comunidade; `wa.me` abre chat 1:1, não grupo | "Entrar" não leva ao grupo; atendimento manual | `wa.me` para número de atendimento por comunidade com a mensagem da spec; se a comunicação fornecer convites de grupo (`chat.whatsapp.com`), trocar o destino no seed | comunicação | P-11 |
| LA-10 | Mensalidade Zero inconsistente: "100% coberta" × barra 40%/60% ("R$ 28 você · 40%", "R$ 42 patrocínio · 60%") | dado financeiro contraditório ao associado | flag `mensalidade_zero` desligada; textos que citam patrocínio têm variante sem patrocínio (RF-HO-09, RF-ON-02) | negócio | P-12 |
| LA-11 | Período da fatura ("janeiro a junho de 2026") × "você pagou R$ 336 no ano" | múltiplo "7×" compara períodos diferentes | quando ligada, período = ano civil corrente até hoje em ambos | negócio | P-12 |
| LA-12 | "R$ 1.500+ em benefícios/ano" × "Valor para você ≈ R$ 2.490/ano" × soma dos passos | números divergentes na mesma tela | valores calculados dos seeds (passos e coberturas) | negócio / comunicação | P-12, P-10 |
| LA-13 | Posts de comunidade ("CONVERSAS EM DESTAQUE") sem fonte | seção sem dado real; moderação e LGPD | flag `comunidade_posts` desligada | comunicação | P-11 |
| LA-14 | Contagens apresentadas como reais: "40+ benefícios", "320 médicos", "210 mentores", "1.240/380/920 membros", "64 faculdades", "340 vagas hoje", "30 mil parceiros", "61% dos associados", "● ativa agora", "sua especialidade" | números falsos ao associado | só exibe contagem com fonte (ativações reais, adesões reais) ou texto editorial aprovado no seed; sem fonte → omitir o número | negócio / comunicação | P-10, P-11 |
| LA-15 | Remover foto de perfil | associado não consegue apagar a foto (LGPD: direito de eliminação via Central) | não implementado; remoção pela Central; avaliar ferramenta `associado.foto_remover` no hub | negócio / Sentinela | P-10 |
| LA-16 | Personas "residente" (sem tipo no CRM) e "sem patrocínio" (spec só cobre patrocinado) | textos e rota inicial errados para parte da base | persona = tipo do CRM; sem flag de patrocínio, nenhum texto de patrocínio | negócio / CRM | P-10, P-12 |
| LA-17 | "Todo resgate acontece dentro da Minha APM", mas o resgate do clube ocorre em `clubapm.com.br` sem retorno | fatura de valor e economia do clube sem dado; afirmação falsa | registra só o clique; textos que afirmam o contrário ficam sob `clube_economia` | negócio | P-12 |
| LA-18 | Mensagem pré-preenchida da Central APM não definida | atendimento sem contexto | "Olá! Sou associado(a) da APM e preciso de ajuda." (proposta) — sem dado pessoal na URL | comunicação | P-11 |
| LA-19 | Tratamento "Dr./Dra." e concordância ("associada/associado") | saudação e carteirinha com gênero errado | sem prefixo na saudação; concordância por `alf_sexo`; desconhecido → construções neutras ("na APM desde") | comunicação | P-10 · **Fase 2a: carteirinha usa "na APM desde {ano}"; saudação sem prefixo.** |
| LA-20 | Acadêmico sem CRM: linha "CRM-SP 000000" | carteirinha com campo vazio | linha mostra só "na APM desde {ano}" | negócio | P-10 |
| LA-21 | Item "Onboarding acadêmico" exibido a todos no protótipo; critério de "onboarding concluído" | não acadêmicos veem trilha que não se aplica; rota inicial indefinida | item visível só a Acadêmico; concluído = passo `finalizar` ("Ir para a Minha APM →") | negócio | P-10 |
| LA-22 | Busca "Buscar especialista por área..." da rede de encaminhamento sem fonte | campo que não funciona | campo oculto | negócio | P-10 |
| LA-23 | Tipos de notícia (ciência/publicação/notícia/evento/nota), fontes além do site (Portal MBE, revista APM, IESAPM) e "atualizado hoje" | tags e filtros "Notícias/Ciência" sem regra | tipo derivado de categoria do WordPress por tabela de mapeamento no seed; só o site nesta versão; "atualizado em DD/MM" quando não for hoje | comunicação | P-07, P-10, P-21 |
| LA-24 | Banco de plantões: destino e "340 vagas hoje" | card sem destino | card oculto até URL definida; contagem omitida | negócio | P-10 |
| LA-25 | Textos das telas novas (Perfil, Minhas solicitações), do botão "Sair", mensagens de erro e estados vazios novos | tom e terminologia fora da spec | propostas marcadas nos RFs | comunicação | P-10 |
| LA-26 | "RECOMENDADOS PARA A SUA SITUAÇÃO": regra de recomendação | recomendação arbitrária | seleção editorial por tipo de associado no seed | negócio | P-10 |
| LA-27 | Elegibilidade TotalPass "status 2 ou 3" × gate do IdP (só status 2 entra) | regra morta para status 3 | elegível = sessão válida; registrar no ADR-0008 | negócio | P-10 |
| LA-28 | Tag `patrocinado` em benefícios (patrocínio de parceiro) × flag `patrocinio` | perda de fidelidade visual ou exposição de patrocínio indefinido | tag, borda e chip sob `patrocinio` | negócio | P-12 |
| LA-29 | Userinfo sem `tipo_associado`/`associado` (CRM incompleto) | persona indefinida | recusar login (fail-closed) ou sessão sem persona → decisão Sentinela antes da Fase 1 (RF-AU-09) | Sentinela | P-20 · **Decidido (2026-10-17): recusa o login (ADR-0016).** |
| LA-30 | Deixar de seguir tema: spec só adiciona | lista de temas só cresce | API suporta (`PUT /temas`); UI de remoção a definir (ex.: chip com ×) | comunicação | P-10 |

---

## 12. Rastreabilidade

| RF | Tela (seção da spec) | Endpoint | Tabela(s) | Evento de uso | Fase |
|---|---|---|---|---|---|
| RF-SH-01 | Estrutura · Mapa de rotas | `GET /area/{path}` | — | `pagina_ver` | 1 |
| RF-SH-02 | Estrutura · Shell desktop (Sidebar) | `GET /sessao` | `feature_flag` | — | 1 |
| RF-SH-03 | Estrutura · Shell desktop (Header) | `GET /sessao`, `GET /perfil/foto` | `associado_perfil` | — | 1 |
| RF-SH-04 | Estrutura · Busca global | — | — | `busca_global` | 4/5 |
| RF-SH-05 | Estrutura · Shell mobile (Drawer) | — | — | — | 1 |
| RF-SH-06 | Estrutura · Shell mobile (Bottom-nav) | — | — | — | 1 |
| RF-SH-07 | Componentes · Toast | — | — | — | 1 |
| RF-SH-08 | Componentes · WhatsAppFab | `GET /sessao` | — | `central_whatsapp_abrir` | 1 |
| RF-SH-09 | RNF · Observabilidade | todos | — | `erro_exibido` | 1 |
| RF-SH-10 | Fundação visual · movimento | `GET /sessao` | — | — | 1 |
| RF-SH-11 | — (D-08) | `GET /sessao` | `feature_flag` | — | 1 |
| RF-SH-12 | RNF · Links externos | — | — | (da ação) | 1 |
| RF-SH-13 | Estrutura · breakpoints · Grids | — | — | — | 1 |
| RF-HO-01 | Telas §1 item 1 | `GET /sessao` | — | — | 1 |
| RF-HO-02 | Telas §1 item 2 (Mensalidade Zero) | `GET /sessao` | — | — | 8 |
| RF-HO-03 | Telas §1 item 2 (Fatura de valor) | `GET /fatura` | `beneficio_ativacao` | — | 8 |
| RF-HO-04 | Telas §1 item 3 | `GET /eventos`, `POST /eventos/congresso/garantir-vaga` | `evento_cache`, `evento_inscricao` | `congresso_garantir_vaga`, `congresso_programacao_abrir` | 5 |
| RF-HO-05 | Telas §1 item 4 | `GET /beneficios` | `beneficio`, `beneficio_ativacao` | (BE-07..09) | 4 |
| RF-HO-06 | Telas §1 item 5 | `GET /beneficios` | `beneficio` | `categoria_abrir` | 4 |
| RF-HO-07 | Telas §1 item 5 (Marketing médico) | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 4 |
| RF-HO-08 | Telas §1 item 6 | `GET /beneficios` | `beneficio_categoria`, `beneficio` | `categoria_abrir` | 4 |
| RF-HO-09 | Telas §1 item 7 | — | — | — | 4 |
| RF-HO-10 | Telas §1 item 8 | `GET /noticias` | `noticia_cache`, `associado_tema` | `filtro_aplicar`, `noticia_abrir` | 5 |
| RF-HO-11 | Telas §1 item 8 (Publique) | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 5 |
| RF-BE-01 | Telas §2 item 1 | `GET /beneficios`, `GET /fatura` | `beneficio_ativacao` | — | 4 |
| RF-BE-02 | Telas §2 item 2 | — | — | `filtro_aplicar` | 4 |
| RF-BE-03 | Telas §2 item 2 | — | `beneficio_categoria` | `filtro_aplicar` | 4 |
| RF-BE-04 | Telas §2 item 2 · Busca global | — | — | `busca_global` | 4 |
| RF-BE-05 | Telas §2 item 3 | `GET /beneficios` | `beneficio`, `beneficio_categoria` | — | 4 |
| RF-BE-06 | Telas §2 item 4 | — | — | `filtro_aplicar` | 4 |
| RF-BE-07 | Componentes · BenefitCard | `POST /beneficios/{slug}/ativar` | `beneficio_ativacao` | `beneficio_ativar` | 4 |
| RF-BE-08 | Componentes · BenefitCard ("Gerenciar") | `POST /beneficios/{slug}/desativar` | `beneficio_ativacao` | `beneficio_gerenciar`, `beneficio_desativar` | 4 |
| RF-BE-09 | Componentes · BenefitCard (outros CTAs) | — | `beneficio` | `beneficio_abrir` | 4 |
| RF-BE-10 | Telas §9 item 3 · Dados (TotalPass) | `GET /beneficios` | — (hub) | `totalpass_abrir` | 4 |
| RF-CL-01 | Telas §3 item 1 | — | — | — | 6 |
| RF-CL-02 | Telas §3 item 2 | `GET /clube` | — | — | 6 |
| RF-CL-03 | Telas §3 item 3 | `GET /clube` | — (catálogo) | `clube_oferta_usar` | 6 |
| RF-CL-04 | Telas §3 item 4 · OfferCard | `GET /clube` | — (catálogo) | `clube_oferta_usar` | 6 |
| RF-CL-05 | Telas §3 item 5 | `GET /clube` | — | — | 6 |
| RF-NE-01 | Telas §4 item 1 | `GET /noticias`, `GET /temas` | `associado_tema`, `noticia_salva`, `job_execucao` | — | 5 |
| RF-NE-02 | Telas §4 item 2 | `GET /temas` | `tema`, `associado_tema` | `filtro_aplicar` | 5 |
| RF-NE-03 | Telas §4 item 3 · NewsItem | `GET /noticias` | `noticia_cache` | `noticia_abrir` | 5 |
| RF-NE-04 | Telas §4 item 3 · NewsItem | `POST /noticias/{id}/salvar`, `DELETE /noticias/{id}/salvar` | `noticia_salva` | `noticia_salvar`, `noticia_dessalvar` | 5 |
| RF-NE-05 | Telas §4 item 4 (radar) | `PUT /temas` | `associado_tema` | `tema_seguir`, `tema_deixar` | 5 |
| RF-NE-06 | Telas §4 item 4 (salvos) | `GET /noticias?salvos=1` | `noticia_salva`, `noticia_cache` | `noticia_abrir` | 5 |
| RF-NE-07 | Telas §4 item 4 (Publique) | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 5 |
| RF-FA-01 | Telas §5 item 1 | `GET /fatura` | `beneficio_ativacao`, `beneficio` | — | 8 |
| RF-FA-02 | Telas §5 item 1 (PDF) | `GET /fatura/pdf` | `beneficio_ativacao` | `fatura_pdf_baixar` | 8 |
| RF-FA-03 | Telas §5 item 2 | — | — | — | 8 |
| RF-FA-04 | — (D-08) | `GET /fatura[/pdf]` | `feature_flag` | — | 1/8 |
| RF-FA-05 | Dados · Mensalidade/FaturaDeValor | `GET /financeiro/faturas` | — (ERP via hub) | — | 7 |
| RF-CO-01 | Telas §6 item 1 · CommunityCard | `GET /comunidades`, `POST /comunidades/{slug}/entrar` | `comunidade`, `comunidade_adesao` | `comunidade_entrar` | 6 |
| RF-CO-02 | Telas §6 item 1 ("Abrir") | — | `comunidade` | `comunidade_abrir` | 6 |
| RF-CO-03 | Telas §6 item 1 (Embaixadores) | — | `comunidade` | `programa_saber_mais` | 6 |
| RF-CO-04 | Telas §6 item 2 | — | — | — | fora (flag) |
| RF-CO-05 | Telas §6 item 3 (Rede) | `POST /comunidades/rede/entrar` | `comunidade`, `comunidade_adesao` | `rede_entrar` | 6 |
| RF-CO-06 | Telas §6 item 3 (Mentoria) | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 6 |
| RF-CO-07 | Telas §6 item 3 (Próximos encontros) | `GET /eventos?contexto=comunidade` | `evento_cache`, `comunidade` | — | 6 |
| RF-EV-01 | Telas §7 item 1 | `GET /eventos` | `evento_cache` | `congresso_programacao_abrir` | 5 |
| RF-EV-02 | Telas §7 item 1 (CTA) | `POST /eventos/congresso/garantir-vaga` | `evento_inscricao` | `congresso_garantir_vaga` | 5 |
| RF-EV-03 | Telas §7 item 2 | `GET /eventos` | — (catálogo) | — | 5 |
| RF-EV-04 | Telas §7 item 3 · AgendaRow | `GET /eventos` | `evento_cache` | — | 5 |
| RF-EV-05 | Telas §7 item 3 ("Inscrever") | `POST /eventos/{id}/inscrever` | `evento_inscricao` | `evento_inscrever` | 5 |
| RF-CA-01 | Telas §8 · DigitalCard | `GET /carteirinha` | `associado_perfil` | — | 2 |
| RF-CA-02 | Telas §8 · DigitalCard (QR) | `GET /carteirinha` | `associado` | — | 2 |
| RF-CA-03 | RNF · Privacidade (verificação pública) | `GET /verificar/{token}` | `associado`, `associado_perfil` | `carteirinha_verificar` | 2 |
| RF-CA-04 | Telas §8 ("Compartilhar") | `POST /carteirinha/compartilhar` | `associado` | `carteirinha_compartilhar` | 2 |
| RF-CA-05 | Telas §8 ("+ Adicionar à Wallet") | (Fase 8) | — | `wallet_adicionar` | 8 |
| RF-CA-06 | Telas §8 (texto lateral) | `GET /carteirinha` | `associado_perfil` | — | 2 |
| RF-ON-01 | RNF · Autenticação (rota inicial) | `GET /sessao`, `GET /onboarding` | `onboarding_progresso` | — | 6 |
| RF-ON-02 | Telas §9 item 1 | `GET /onboarding` | `onboarding_passo` | — | 6 |
| RF-ON-03 | Telas §9 item 2 | `GET /onboarding` | `onboarding_passo`, `onboarding_progresso` | — | 6 |
| RF-ON-04 | Telas §9 item 3 · StepCard | `GET /onboarding` | `onboarding_passo`, `onboarding_progresso` | — | 6 |
| RF-ON-05 | Telas §9 item 3 · Dados (Onboarding) | `POST /onboarding/passos/{slug}/concluir` | `onboarding_progresso` | `onboarding_passo_concluir` | 6 |
| RF-ON-06 | Telas §9 item 3 (ações) | RFs referenciados | `beneficio_ativacao`, `evento_inscricao`, `solicitacao`, `comunidade_adesao`, `onboarding_progresso` | `totalpass_abrir`, `beneficio_abrir`, `congresso_garantir_vaga`, `solicitacao_criar`, `onboarding_passo_concluir` | 6 |
| RF-ON-07 | Telas §9 item 4 | `GET /onboarding` | — (catálogo) | — | 8 |
| RF-ON-08 | Telas §9 item 5 (Banco de plantões) | — | `beneficio` | `plantoes_abrir` | 6 |
| RF-ON-09 | Telas §9 item 5 (Cartão APM) | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 6 |
| RF-ON-10 | Telas §9 item 6 | — | — (catálogo) | — | 6 |
| RF-ON-11 | Telas §9 item 7 | `POST /onboarding/passos/finalizar/concluir` | `onboarding_progresso` | `onboarding_passo_concluir` | 6 |
| RF-PE-01 | — (tela nova) · Dados (Associado) | `GET /perfil` | `associado_perfil` | — | 2 |
| RF-PE-02 | — (tela nova) | `PUT /perfil/contato` | `associado_perfil` | `perfil_contato_atualizar` | 2 |
| RF-PE-03 | — (tela nova) | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 3 |
| RF-PE-04 | — (tela nova) | — | — | — | 2 |
| RF-PE-05 | — (tela nova) | `POST /perfil/foto` | `associado_perfil` | `perfil_foto_atualizar` | 2 |
| RF-PE-06 | Componentes · Avatar | `GET /perfil/foto` | `associado_perfil` | — | 2 |
| RF-PE-07 | — (lacuna) | — | — | — | — |
| RF-PE-08 | RNF · Observabilidade | `GET /perfil`, `PUT /perfil/contato`, `POST /perfil/foto` | `associado_perfil` | `erro_exibido` | 2 |
| RF-PE-09 | — (tela nova) | `POST /auth/logout` | — | — | 2 |
| RF-SO-01 | — (tela nova) | `GET /solicitacoes` | `solicitacao` | — | 3 |
| RF-SO-02 | — (tela nova) | `GET /solicitacoes/{uuid}` | `solicitacao`, `solicitacao_evento` | — | 3 |
| RF-SO-03 | Dados · Ações da UI que precisam de backend | `POST /solicitacoes` | `solicitacao`, `solicitacao_evento` | `solicitacao_criar` | 3 |
| RF-SO-04 | — (tela nova) | `POST /solicitacoes/{uuid}/cancelar` | `solicitacao`, `solicitacao_evento` | `solicitacao_cancelar` | 3 |
| RF-SO-05 | — (tela nova) | `POST /solicitacoes/{uuid}/responder` | `solicitacao`, `solicitacao_evento` | `solicitacao_responder` | 3 |
| RF-SO-06 | — (D-04) | — | `solicitacao` | — | 3 |
| RF-SO-07 | — (tela nova) | `GET /sessao` | `solicitacao` | — | 3 |
| RF-AU-01 | RNF · Autenticação | `GET /area/{path}` | — | — | 1 |
| RF-AU-02 | RNF · Autenticação | `/api/v1/*` | — | — | 1 |
| RF-AU-03 | RNF · Autenticação · Dados (Configuracao) | `GET /sessao` | `feature_flag`, `solicitacao` | — | 1 |
| RF-AU-04 | RNF · Autenticação (rota inicial) | `GET /sessao` | `onboarding_progresso` | — | 1/6 |
| RF-AU-05 | — (Sentinela) | todos `[C]` | `evento_log` | — | 1 |
| RF-AU-06 | — (Sentinela, D-11) | — | — | — | 1 |
| RF-AU-07 | — (obrigatório, ausente na spec) | `POST /auth/logout` | `evento_log` | — | 1 |
| RF-AU-08 | RNF · Autenticação | — | — | — | 1 |
| RF-AU-09 | RNF · Autenticação | `GET /auth/login`, `GET /auth/callback` | `evento_log` | — | 1/2 |
| RF-AU-10 | — (CLAUDE.md regra 6) | `GET /auth/login`, `POST /auth/login` | `evento_log` | — | 1 |
