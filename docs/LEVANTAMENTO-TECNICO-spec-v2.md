# Levantamento técnico — especificação funcional v2 da Minha APM

| Item | Valor |
|---|---|
| Data | 2026-10-29 |
| Fonte analisada | [`spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md`](spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md) (transcrição do PDF "Minha APM · especificação funcional para a TI · v2 · 30/09/2026", APM × Comunicação Encantada, 34 p.) |
| Comparado com | `REQUISITOS-minha-apm.md` v0.1 (17/10), ADRs 0001–0017, código em `a2af85e` (fases 0, 1, 2a, 2b no ar), repositórios irmãos `login_associado`, `mcp_hub`, `totalpass`, `apm-parceiros`, `appapm`, `app_facial_recognition`, `nginx-proxy` |
| Autores | Sistemas TI (William) · Claude Code (Sentinela, Atlas, Maestro, Integrador, Vitrine, Estivador) — análises brutas por persona em [`spec-v2/personas/`](spec-v2/personas/README.md) |
| Índice de identificadores | [`spec-v2/INDICE-IDS.md`](spec-v2/INDICE-IDS.md) |
| Ordem de execução | [`PLANO-EXECUCAO.md`](PLANO-EXECUCAO.md) (7 ondas, do mais fácil ao mais problemático; 30/10). **Ondas 1 e 2 executadas em 30/10** — TI marcados ✅ em §12. |
| Como usar | §12 (**TI**: o que a TI faz sem esperar ninguém) e §13 (**EXT**: o que depende de terceiro, com dono e o que fazer enquanto isso) são as listas operacionais. §3–§9 explicam cada item. §10–§11 são o que precisa de decisão. §15 cruza tudo. |

## 0. Resumo executivo

**Em uma frase:** a spec v2 pede um produto bem maior do que o REQUISITOS v0.1 previa; a fundação (OIDC,
sessão, hub, perfil, carteirinha) está pronta e sólida, **nada do núcleo funcional existe ainda** (catálogo,
elegibilidade, solicitações, valor, comunicação, jobs, backoffice), e a maior parte do que falta é TI pura:
das 92 tarefas, 43 podem começar hoje e só 32 esperam terceiro para a versão real (todas têm versão com stub).

| Medida | Valor |
|---|---|
| Itens da spec analisados | 17 páginas + 13 módulos + 6 tipos + 8 status + 9 blocos + 28 eventos + 20 gatilhos + 13 integrações + 14 indicadores + 14 RNF |
| Estado hoje (páginas) | ✅ 1 (P07) · 🟡 3 (P01 no IdP, P02 casca, P13 metade) · ⬜ 9 · ⛔ 2 (P08, P17) · 🔒 2 (P15, P16) |
| Tarefas TI | **92** (43 começam hoje; 17 esperam só decisão; 32 esperam terceiro para a versão real) |
| Dependências externas | **38** (24 pendências novas P-42..P-65; 14 já existiam) |
| Divergências spec × decisões/ADRs | **46** (nenhuma reabre decisão do usuário) |
| Decisões pendentes | **36** (6 bloqueiam o plano da Fase 3: DEC-01, 02, 13, 22, 28, 29) |

**As cinco decisões que destravam mais trabalho:** DEC-01 (8 status já na `sql/008`), DEC-03 (onde vive o
backoffice e quem tem UPDATE no catálogo), DEC-05 (canal do CSV com CPF resolvido no hub), DEC-14/15
(elegibilidade sem ERP e base da carência) e DEC-29 (agendador dos jobs). **As cinco dependências externas
que mais travam:** P-48 catálogo validado com valores de referência (gate F0), P-58 "novo sistema de cadastro
e cobrança" (segunda via, avisos), P-56 atributos do contato (nascimento, especialidade, regional), P-46
contrato com o RD e P-54 jurídico (consentimentos, prazos, exclusão). **Três itens sem código e urgentes:**
P-01 (certificado de origem vencido), P-36 (`.env` sem cópia atual) e um monitor externo (P-61).

**Ordem recomendada:** (1) hoje: TI-70..73, 75 (infra), TI-02, 03, 05, 06, 07, 12, 13 (base), TI-61..63, 65,
68, 69 (front fast-path), TI-47, 51 (hub) e abrir todas as EXT em PENDENCIAS (feito). (2) Decidir DEC-01, 02,
13, 22, 28, 29 e planejar a **Fase 3 ampliada** (§12.2) com jobs, P14, outbox produzida e carteirinha em
tempo quase real. (3) Fase 3b (P13 LGPD) em paralelo com as respostas do jurídico. (4) Decidir DEC-03/05/
14/15/16 e planejar a Fase 4 com catálogo como dado, elegibilidade, home em blocos e Meu valor v1
(antecipado da 8). (5) Backoffice por ADR própria assim que DEC-03 e P-65 saírem. Divergências com a spec
(§10) vão à agência como registro, não como mudança.

## 1. Método e legenda

- Cada item da spec (página, módulo, regra, evento, gatilho, integração, RNF) recebeu: **o que a
  spec pede**, **o que existe hoje** (com `arquivo:linha`), **o que falta por camada** (SQL ·
  dominio · API · integrações+jobs · frontend · infra), **persona**, **fase da spec** e **fase do
  roteiro** (`PENDENCIAS.md`), e um estado:

| Estado | Significado |
|---|---|
| ✅ pronto | implementado e no ar; pode ter ajuste pequeno |
| 🟡 parcial | existe parte; o resto é TI |
| ⬜ a construir | nada existe; é TI |
| ⛔ bloqueado por terceiro | só avança com entrega externa (há EXT-nn) |
| ⚠️ divergência | a spec contraria decisão do usuário/ADR (há DIV-nn); registra-se, não se reabre |
| 🔒 fase > F1 | a própria spec coloca depois (F2/F3) ou condiciona a contrato |

- Identificadores criados aqui: **TI-nn** tarefa que a TI executa sem terceiro (coluna "repo":
  `area` = este repositório, `hub` = `mcp_hub`, `idp` = `login_associado`, `infra` = host/porteiro/
  AWS/Cloudflare); **EXT-nn** dependência externa (dono, artefato exato, o que destrava, o que
  fazer enquanto espera, P-xx); **DIV-nn** divergência spec × decisão nossa; **DEC-nn** decisão
  pendente de negócio/arquitetura. Tamanho: P (≤ 1 dia), M (2–5 dias), G (> 1 semana).
- Decisões já tomadas pelo usuário **não foram reabertas** (lista na skill `spec-minha-apm`):
  divergências viram DIV-nn com recomendação, só isso.
- Cada persona analisou o seu recorte (síntese em §14); os fatos de código vêm do inventário de
  29/10 (API, domínio, integrações, `sql/`, flags, catálogo de `evento_uso`, `Settings`, SPA,
  testes, deploy) e dos repositórios irmãos.

## 2. Reconciliação de fases e gate de fundação

### 2.1 F0–F3 da spec × fases 1–8 do roteiro

| Spec | O que inclui (§5.2, §15.2) | Nosso roteiro | Situação |
|---|---|---|---|
| **F0** gate de fundação | base conciliada com identificador canônico; fonte de autenticação e situação comprovada; catálogo inicial com regras e carências validadas; contrato de dados e medição por parceiro; destino dos eventos, acessos e critérios de LGPD | Fase 0 (docs) + o que 1–2b provaram | **parcial** — ver 2.2 |
| **F1** escopo protegido | P01, P02, P03/P04, P05, P06 v1, P09, P13/P14, backoffice B01–B06, B12, B13; P07/P08 condicionais ao gate técnico | 1, 2a, 2b (feitas: shell, sessão, perfil, carteirinha) + 3 (solicitações) + 4 (benefícios) + **backoffice (sem fase)** + **P06 v1, P14 (sem fase)** | em andamento; o roteiro precisa absorver backoffice, P06 v1, P14 e o motor de elegibilidade |
| **F2** comportamento e integrações | tipos 4–6, P10, P11, P12 completa, P15, clube integrado (CLU-01..03), wallet, recomendação v2, A07–A15, A19, A20, Qualicorp, eventos/IESAPM, WordPress/MBE, WhatsApp/SMS | 5 (notícias/eventos), 6 (clube/comunidade/onboarding), 7 (ERP), 8 (wallet) | não iniciadas |
| **F3** | P16 comunidade (DIR/COM/MEN/ENC), P17 patrocínio e cartão, CON-01 congresso nativo | 6 (comunidade) e 8 (patrocínio) | não iniciadas; P17 só com contrato |

Leitura: o roteiro atual **termina a F1 da spec na Fase 4**, mas faltam no roteiro quatro blocos
que a spec coloca na F1: **backoffice B01–B06/B12/B13**, **P06 Meu valor v1** (proteção incluída +
solicitações concluídas + importações, hoje "fase 8 atrás de flag"), **P14 Ajuda/cancelamento** e o
**motor de elegibilidade/carências** (§8.1–8.4). As listas de §12 marcam onde cada um entra.

### 2.2 Checklist do gate F0 (§15.1) com o estado real

| Item do gate | Estado | Evidência / o que falta |
|---|---|---|
| Base conciliada com identificador canônico | 🟡 | O identificador canônico existe e é usado: `contact_id` do Dataverse (ADR-0014; `associado.contact_id`, hub por `contact_id`). "Base conciliada" (contagem e categorias, §15.5) é do negócio/CRM: **DEC** (duplicidade de CPF é ferramenta do hub `associado.duplicidade_cpf`). |
| Fonte de autenticação e situação do associado comprovada | ✅ | OIDC com `login_associado` em produção desde 20/10; escopo `carteirinha` entrega tipo, situação, CRM, UF, filiação; sem tipo/situação o login é recusado (ADR-0016). Situação ao vivo na validação pública (`app/dominio/carteirinha.py`). |
| Catálogo inicial com regras e carências validadas | ⛔ | Nada: carências (§8.2), matriz benefício × categoria (§8.3), dias de atraso (§8.4), carência do clube e valores de referência são do negócio (Benefícios, Financeiro, Jurídico). A TI pode construir o motor e as tabelas (**TI**) sem a lista; publicar o catálogo não. |
| Contrato de dados e medição para cada parceiro | ⛔ | Nenhum parceiro tem contrato técnico (ADR-0009). O layout do CSV (§13.3) existe na spec: o importador é TI; os arquivos e o canal são do parceiro/Benefícios. |
| Destino dos eventos, acessos e critérios de LGPD | 🟡 | Eventos têm destino próprio (`evento_uso`, ADR-0012, append-only, pseudonimizado por `contact_id`/`sub_hash`). Falta: decisão F0-06 (ferramenta externa de analytics ou só a tabela), acesso aos painéis (quem vê o quê = backoffice B12), consentimentos versionados e direitos do titular (P13), retenção (P-15, "prazo definido pelo jurídico"). |

### 2.3 Escopo protegido da F1 × o que já existe

| Item F1 | Existe | Falta (resumo; detalhe em §3/§4) |
|---|---|---|
| P01 Acesso | ✅ via IdP | data de nascimento, SMS, "meus dados mudaram", evento `acesso_primeiro` (ver §3.1) |
| P02 Início | 🟡 saudação + atalhos | 9 blocos com regras, recomendação v1, pendência, próximo passo |
| P03/P04 Benefícios e página do benefício | ⬜ | catálogo, elegibilidade, 6 estados, detalhe, tipos 1–3 |
| P05 Minhas solicitações | ⬜ (ADR-0003 desenhada) | 8 status, vínculo com benefício/parceiro, prazo, avaliação |
| P06 Meu valor v1 | ⬜ (flag `fatura_valor` forçada desligada) | proteção incluída, concluídas, importações, "como calculamos" |
| P07 Carteirinha | ✅ | baixar imagem/PDF, revogação explícita, wallet (F2) |
| P08 Financeiro | ⛔ | fonte de cobrança (F&O via hub só tem faturas; sem boleto/Pix); parecer P-08 |
| P09 Clube | ⬜ (ADR-0009 link) | vitrine curada, oferta da semana, encaminhamento rastreado |
| P13/P14 Perfil e Ajuda | 🟡 / ⬜ | preferências, consentimentos, LGPD; FAQ, cancelamento |
| B01–B06, B12, B13 | ⬜ | decisão de arquitetura (DEC) + tudo |

## 3. Páginas do associado P01–P17

Formato de cada item: **Spec pede** · **Existe hoje** · **Falta por camada** · **Estado** · **Fase spec /
roteiro** · **IDs** (TI/EXT/DIV/DEC desta análise).

### 3.1 P01 · Acesso

- **Spec pede:** CPF + senha + "continuar conectado"; primeiro acesso com CPF **e data de nascimento**, código no e-mail **ou celular** mascarado; "esqueci a senha"; "meus dados mudaram" (pedido à Central com prazo); não associado → filiação; ex-associado vê página de retorno; a tela não confirma CPF antes de o nascimento conferir; limite por CPF e por rede (ACE-05); eventos `login`, `acesso_primeiro`.
- **Existe hoje:** tudo vive no IdP `login_associado` (decisão: sem login próprio). CPF + senha, lockout 5/900 s por CPF, OTP de 6 dígitos **só por e-mail**, recuperação de senha, rate limit por IP no nginx e na Cloudflare, `prompt=login`/`max_age` honrados. Na área: RP OIDC + PKCE (`app/oidc.py`), sessão 8 h/12 h, step-up por `idp_at`, `evento_log` `login_ok/login_falha/logout`, `associado.primeiro_acesso_em` sem evento.
- **Falta:** IdP: nascimento no primeiro acesso (anti-enumeração: hoje a triagem distingue "fora do CRM → filiação" só pelo CPF), "continuar conectado", "meus dados mudaram", página de retorno do ex-associado (hoje → Central), canal celular (WhatsApp/SMS não existem), limite "por rede" além de IP. Área: emitir `acesso_primeiro` em `registrar_acesso`.
- **Estado:** 🟡 (núcleo ✅ no IdP) · ⚠️ DIV-01, DIV-02, DIV-03.
- **Fase:** F1 ACE-01..05 / fases 1–2 feitas; backlog do IdP sem fase.
- **IDs:** TI-05, TI-83 · EXT-19 (nascimento no CRM), EXT-35 (canal celular) · DEC-11, DEC-12.

### 3.2 P02 · Início

- **Spec pede:** saudação com tratamento e categoria, atalho da carteirinha, busca, 9 blocos com regra de exibição (§7.2), bloco vazio some, ≤ 1 patrocinado nos 4 primeiros, "como funciona" no 1.º acesso, pendência financeira no topo, destaque editorial ADM-05; eventos `home_vista`, `home_bloco_clicado`, `recomendacao_dispensada`.
- **Existe hoje:** `frontend/src/pages/Inicio.tsx` com saudação, selo tipo·situação e 2 atalhos; nenhum endpoint de home; `GET /sessao` só identidade/flags; eventos `pagina_ver`, `categoria_abrir`.
- **Falta:** SQL `destaque_editorial`, `recomendacao_dispensa`, `recomendacao_exposicao` · domínio `inicio.py`, `recomendacao.py`, `elegibilidade.py`, `valor.py`, `trilha.py`, `preferencias.py` · API `GET /inicio` (só blocos com conteúdo, ordem do servidor), `POST /recomendacoes/{slug}/dispensar` · ações `home_bloco_clicar`, `recomendacao_dispensar`, `home_vista` com `blocos` · frontend `BlocoHome` + cards 1–7, "por que estou vendo isto", skeleton/erro por bloco · fontes do bloco 1: pagamento (⛔ ERP), documentação pendente (⛔ CRM), `pendente_associado` (✓ local), carência ≤ 7 d (✓), renovação ≤ 30 d (⛔).
- **Estado:** 🟡 casca · ⬜ motor · ⛔ pendência financeira e renovação.
- **Fase:** F1 HOM-01 (F2 REC-01/CLU-03/NEWS-01) / Fase 4.
- **IDs:** TI-29, TI-30, TI-33, TI-34, TI-40, TI-43, TI-04 · EXT-10, EXT-11, EXT-19, EXT-05 · DEC-21, DEC-26 · DIV-36.

### 3.3 P03 · Benefícios

- **Spec pede:** resumo (ativos, disponíveis, valor no ano), filtros Todos/Disponíveis para mim/Ativos/Novos, 8 categorias, busca, card com condição em uma linha + selo + botão; ordem disponíveis → ativos → "libera em"; "exclusivo para associado efetivo"; busca sem resultado sugere categorias e registra o termo; eventos `busca`, `beneficio_visto`.
- **Existe hoje:** rota `beneficios` em "em construção"; `CampoBusca` leva a `/beneficios?q=` e não filtra; classes `.tag`; REQUISITOS RF-BE-01..10 com seed de 19 itens previsto em `sql/009`; ações `filtro_aplicar`, `categoria_abrir`, `beneficio_abrir` sem emissor.
- **Falta:** SQL catálogo como dado (TI-29) · domínio elegibilidade (6 estados) · API `GET /beneficios?filtro=&categoria=&q=` com `estado`, `libera_em`, `motivo`, resumo · `beneficio_abrir` com `origem`/`estado` · termo sem resultado em tabela própria sem identidade · frontend `BarraResumo` (some sem fonte), `FiltroChips`, `GradeCategorias`, `CardBeneficio`, vazio, 503.
- **Estado:** ⬜ · ⚠️ DIV-14 (termo), DIV-18 (catálogo).
- **Fase:** F1 CAT-02/03 / Fase 4.
- **IDs:** TI-29, TI-30, TI-31, TI-37, TI-38 · EXT-10, EXT-05 · DEC-34, DEC-35.

### 3.4 P04 · Página do benefício e ativação

- **Spec pede:** rota de detalhe (nome, parceiro, frase, condição × referência, "como funciona" ≤ 4 passos, situação com data, botão por tipo 1–6, FAQ, contato, regras, "quanto já aproveitou", relacionados); tipos 1–5 sem cupom manual; confirmação com prazo e próximo passo; `beneficio_visto`, `solicitacao_criada`.
- **Existe hoje:** nada — nem sub-rota (`rotas.ts:63-66` casa só caminho exato: `/area/beneficios/x` dá "Página não encontrada"); REQUISITOS trata ativação como toggle (RF-BE-07/08). Sem mockup conhecido.
- **Falta:** SQL `beneficio_faq`/`beneficio_passo`, `url_acesso` validada + `parceiro.host` · domínio `ativacao.py` com estratégia por tipo (tabela em §5.5) · API `GET /beneficios/{slug}`, `POST .../ativar` (corpo/resposta por tipo; `409 nao_elegivel {estado, libera_em}`), redirecionador `GET /api/v1/ir/{slug}` · frontend sub-rotas no shell, `SeloEstado`, `BotaoAtivacao`, `Dialogo`, `Accordion`.
- **Estado:** ⬜ · ⚠️ DIV-08 (tipo 2 "envia dados", acesso único), DIV-26.
- **Fase:** F1 CAT-05/SOL-01 (tipos 1–3), F2 (4–6) / Fase 4 (+ Fase 3 para o tipo 3).
- **IDs:** TI-23, TI-29, TI-31, TI-32, TI-39, TI-24 · EXT-02, EXT-10, EXT-12 · DEC-04.

### 3.5 P05 · Minhas solicitações

- **Spec pede:** lista (benefício, data, status, prazo, contato), linha do tempo, cancelar enquanto o parceiro não atendeu, avaliar 0–10, 7 rótulos de status (8 internos, §8.5), log imutável com conteúdo enviado, mudança manual com justificativa; `solicitacao_status`.
- **Existe hoje:** só desenho (ADR-0003 com 6 estados; REQUISITOS §7; RF-SO-01..07), 4 ações no catálogo sem emissor, `solicitacoes_aguardando` fixo em 0, `solicitacao` na allowlist de UPDATE sem migração. Sem mockup conhecido.
- **Falta:** SQL `sql/008` (TI-14) · domínio máquina de transições + schemas por tipo · API 6 rotas + contador real · jobs espelho/sync/`sem_retorno` · frontend lista, detalhe (sub-rota), `LinhaDoTempo`, `StatusSolicitacao`, `Avaliacao`.
- **Estado:** ⬜ (pode começar hoje) · ⛔ espelho real (P-06) · ⚠️ DIV-15, DIV-16, DIV-24.
- **Fase:** F1 SOL-04 / **Fase 3 (próxima)**.
- **IDs:** TI-14, TI-15, TI-16, TI-17, TI-21, TI-23, TI-50 · EXT-20, EXT-02, EXT-05 · DEC-01, DEC-02, DEC-22.

### 3.6 P06 · Meu valor

- **Spec pede:** período, total pago (cobrança), economia comprovada item a item com fonte, proteção incluída separada, total e relação, por categoria, "como calculamos" sempre visível, potencial rotulado, PDF; "N vezes" só com contribuição > 0 e comprovado + proteção > pago; < 3 meses = "o que a sua associação cobre"; `meu_valor_visto`, `uso_registrado`. Nome: "Meu valor"/"Extrato de valor", não "Fatura de valor".
- **Existe hoje:** rota `fatura` sob flag `fatura_valor` **forçada desligada** (P-12), título "Fatura de valor"; RF-FA-01..05 na fase 8; `formato.ts` formata moeda. Mockup parcial (`financeiro` do rascunho).
- **Falta:** SQL `valor_referencia` (aprovado, versionado), `uso_valor` (append-only, níveis 1–4), `vw_meu_valor_ano` · domínio `valor.py` (só nível 4 soma; proteção proporcional; modos relação/valor entregue/o que cobre) · API `GET /valor?periodo=`, `GET /valor/pdf` · frontend `SeletorPeriodo`, `Extrato`, `ComoCalculamos`, `ValorPotencial`, renomear rota `/area/meu-valor` · total pago = hub `financeiro.*` (⛔ P-04/P-08) só para "N vezes".
- **Estado:** ⬜ (comprovado via solicitações concluídas + importações + proteção é viável sem ERP) · ⛔ "N vezes" · ⚠️ DIV-23.
- **Fase:** F1 VAL-01 / hoje fase 8 → **antecipar estrutura para a Fase 4**.
- **IDs:** TI-35, TI-36, TI-41, TI-54 · EXT-10 (valores de referência aprovados), EXT-17, EXT-24 · DEC-23.

### 3.7 P07 · Carteirinha digital e validação pública

- **Spec pede:** nome, categoria, número de associado, "desde", situação, QR; baixar imagem/PDF; wallet (F2); validação pública sem dados pessoais; **situação consultada na leitura**; cancelamento revoga; `carteirinha_aberta`, `carteirinha_validada`.
- **Existe hoje:** ✅ `GET /carteirinha`, `qr.svg`, `compartilhar`, `/verificar/{token}` (token HMAC base32, 404 uniforme, `noindex`, zona 2 r/s), eventos `carteirinha_compartilhar/verificar`, wallet sob flag. **Lacunas:** `resolver` lê o cache local (`associado_perfil.status_associativo`, renovado só quando o próprio associado abre o Perfil): cancelado pode aparecer "Ativo" por até 24 h e depois "não confirmada" para sempre; `num_contato` chega na API mas não é renderizado; sem download.
- **Falta:** domínio: `associado.situacao(contact_id)` no hub com cache curto + limite global + fallback, `carteirinha_revogada_em`, resultado em `detalhes` · jobs: situação noturna · API `GET /carteirinha/imagem.png|pdf`, `revogada` · frontend número no cartão, botões de download, estado revogada.
- **Estado:** ✅ núcleo · 🟡 revogação/download · ⚠️ DIV-13, DIV-07, DIV-45.
- **Fase:** F1 condicionada CAR-01..03 (gate técnico ≈ passado) / Fase 2a feita; complemento na Fase 3 (jobs).
- **IDs:** TI-45, TI-46, TI-47 · EXT-25 (cota) · DEC-09, DEC-36.

### 3.8 P08 · Financeiro

- **Spec pede:** situação no topo, valor/forma, mensalidades do ano com status, segunda via (PDF, linha digitável, Pix), histórico, declarações (AMB com carência 1 mês), recorrente em cartão (F2); cobrança fora → aviso + Central; `financeiro_segunda_via`, `pagamento_confirmado`.
- **Existe hoje:** só flag `erp_financeiro` (desligada), ação `fatura_pdf_baixar`, ADR-0010 (ERP só leitura após parecer). Hub `financeiro.faturas_associado` **por CPF**, `CustTransactions`: vencimento, valor, liquidado, saldo, forma; **sem boleto, linha digitável, Pix ou PDF**; sem regra de "situação". Sem mockup.
- **Falta:** hub `financeiro.situacao_consultar` + `faturas_listar` por `contact_id` (TI-49) · área `GET /financeiro` (404 `recurso_desligado` até ligar), tela com "cobrança indisponível → Central" · declarações = solicitação tipo 3 `declaracao_associado` com carência AMB (viável já) · segunda via/Pix: **fonte inexistente** · `pagamento_confirmar` por job de sync.
- **Estado:** ⛔ (P-04, P-08, fonte de 2ª via) · ⬜ declarações.
- **Fase:** F1 condicionada INT-02/FIN-01/03 / Fase 7.
- **IDs:** TI-49, TI-57, TI-20 · EXT-17, EXT-24 · DEC-14, DEC-17 · DIV-31.

### 3.9 P09 · Clube de vantagens

- **Spec pede:** 30–40 ofertas curadas, oferta da semana, categorias, economia no ano (quando houver resgate), "ver todas"; F1 encaminhamento rastreado sem SSO; F2 resgate nasce na área e devolve economia.
- **Existe hoje:** allowlist `clubapm.com.br`, ação `clube_oferta_usar`, flag `clube_economia`; ADR-0009 (seed `oferta_clube`, `PARCEIROS_HOSTS`) ainda não implementada; rota em construção; chamada promete "cashback" (P17).
- **Falta:** SQL `oferta_clube` (+ curadoria B10 F2) · API `GET /clube`, `POST /clube/ofertas/{id}/abrir` (rastreio no servidor) · frontend página.
- **Estado:** ⬜ (F1 trivial com seed) · 🔒 F2 sem ADR própria.
- **Fase:** F1 link / F2 CLU-01..03 / Fase 6.
- **IDs:** TI-88, TI-32, TI-61 · EXT-13 (fornecedor), P-11 · DEC-10 (SSO via IdP).

### 3.10 P10 · Eventos e congresso

- **Spec pede:** agenda filtrável (especialidade, região, formato), página do evento, inscrição com preço por perfil, minhas inscrições, certificados, aulas gravadas, congresso em destaque; carência 3 meses; inscrição parte da área **"com CPF já preenchido"**.
- **Existe hoje:** RF-EV-01..05 sobre `evento_cache` do WordPress (ADR-0006), interesse local; ações sem emissor; nada de código/jobs. Mockup `eventos` sem página do evento.
- **Falta:** `sql/012` caches + `evento_inscricao` · job `sincronizar_portal` · API `/eventos`, `/eventos/{id}`, `/inscrever` (tipo 5 = interesse até F0-01), `/inscricoes` · carência pelo motor · frontend lista/filtros/`CardEvento`/`ImagemSegura`.
- **Estado:** ⬜ · ⛔ plataformas/IESAPM (F0-01), P-07/P-21 · ⚠️ DIV-28 (CPF no deep link: não fazer).
- **Fase:** F2 EVE-01/02, F3 CON-01 / Fase 5.
- **IDs:** TI-56, TI-87 · EXT-13, EXT-34 · DIV-28.

### 3.11 P11 · Notícias e ciência

- **Spec pede:** conteúdo por temas seguidos e especialidade, filtros, seguir temas, salvar, submeter trabalho; fontes WordPress, Portal MBE, biblioteca.
- **Existe hoje:** RF-NE-01..07, ações `noticia_*`/`tema_*` sem emissor, allowlist de UPDATE prevista; `portal_wp.py` **não existe**. Mockups `ciencia`/`defesa`.
- **Falta:** `sql/012`, job único que fala com a Locaweb, API `/noticias`, `/temas`, salvar/seguir, `conteudo_lido` com tempo · frontend `ChipTema`, lista, `ImagemSegura` · MBE/biblioteca sem fonte.
- **Estado:** ⬜ · ⛔ P-07, P-21; MBE/biblioteca.
- **Fase:** F2 NEWS-01 / Fase 5.
- **IDs:** TI-56, TI-87 · EXT-34, EXT-13 · DIV-29 (API do WP × MySQL direto: ADR-0006 mantida).

### 3.12 P12 · Trilha de ativação (90 dias)

- **Spec pede:** todo novo associado e todo acadêmico; progresso começa no passo "perfil"; 5–6 passos por categoria; o que libera e data de carência; **passo concluído por evento real**; some ao terminar ou no dia 90; F1 = bloco de 3 passos na home.
- **Existe hoje:** rota `onboarding` só para Acadêmico, em construção; RF-ON-01..11 com `POST .../concluir` por clique; mockup `onboarding` com "mensalidade R$ 0 patrocinada" (proibido sem P17).
- **Falta:** SQL `trilha_passo` por categoria + `trilha_progresso` append-only · domínio `trilha.avaliar` chamado após `uso.registrar` · API `GET /trilha` (sem `concluir`) · frontend `BarraProgresso`, `PassoTrilha`, bloco na home, visibilidade por tempo de casa.
- **Estado:** ⬜ · ⚠️ DIV-22.
- **Fase:** F1 bloco (HOM-01) / F2 TRI-01 / Fase 6 (bloco pode vir na 4).
- **IDs:** TI-43, TI-40 · EXT-10 · DEC-21.

### 3.13 P13 · Perfil, preferências e privacidade

- **Spec pede:** cadastro (contato vai ao cadastro), tratamento, especialidades/área de atuação, região e temas, canais preferidos (e-mail, WhatsApp, SMS) e frequência, **consentimentos por finalidade com histórico**, **baixar meus dados e pedir exclusão**; perfil progressivo (1 pergunta por visita no bloco 3).
- **Existe hoje:** ✅ cadastro, contato (via hub, escrita desligada), e-mail por código + step-up, foto; minimização (HMAC, `contact_id`, CHECKs). **Nada** de preferências, consentimento, exportação, exclusão, canais.
- **Falta:** SQL `consentimento_texto` + `consentimento` (append-only), `preferencia_canal`, `perfil_declarado`, `pergunta_perfil`, `titular_pedido`, colunas `anonimizado_em` · domínio `consentimento.py`, `preferencias.py`, `titular.py` · API preferências, pergunta, consentimentos (versão obrigatória), exportação (step-up, 1/7 d), exclusão (pedido + anonimização por job, sem DELETE) · frontend seções novas, título "Perfil e privacidade" · zona `limit_req` própria.
- **Estado:** ✅ cadastro · ⬜ preferências/LGPD · ⛔ textos e prazos do jurídico; especialidade/regional do CRM.
- **Fase:** F1 PER-02/03 / proposta **Fase 3b** (logo após solicitações).
- **IDs:** TI-25, TI-26, TI-27, TI-28, TI-09, TI-48 · EXT-16, EXT-19, EXT-35 · DEC-06, DEC-26, DEC-27 · DIV-05.

### 3.14 P14 · Ajuda e atendimento

- **Spec pede:** FAQ editável com busca; Central por WhatsApp/telefone/formulário com horário; pedidos comuns; **cancelamento** acessível, motivo em lista curta, conversa opcional, vai à Central e dispara fluxo 6 (A16); `ajuda_contato`, `cancelamento_pedido`.
- **Existe hoje:** só o FAB WhatsApp (`wa.me`, mensagem com exclamação) e `central_whatsapp_abrir`. Sem rota, sem FAQ, sem mockup.
- **Falta:** SQL `faq` · API `GET /ajuda/faq?q=`, `GET /ajuda/contato`, `POST /ajuda/formulario` (= solicitação `outro`), `POST /ajuda/cancelamento` (= solicitação `cancelamento_associacao`, motivo ENUM, step-up + confirmação por e-mail, 1 pedido aberto; nunca altera o CRM) · outbox A16 · frontend rota `ajuda`, `BuscaFaq`, `Accordion`, canais (`tel:` na allowlist), `FormularioCancelamento`.
- **Estado:** ⬜ (viável localmente; fluxo 6 no RD é externo).
- **Fase:** F1 AJU-01/02 / sem fase → **Fase 3** (são dois tipos de solicitação).
- **IDs:** TI-20, TI-22, TI-09 · EXT-05 (FAQ ≥ 20, motivos), EXT-08 (fluxo 6), EXT-33 · DIV-27.

### 3.15 P15 · Notificações

- **Spec pede:** ícone com contagem, tipos, lida/não lida, atalho a preferências; "aviso no app" em A03/A04/A15; `notificacao`.
- **Existe hoje:** nada, por decisão ("sem sino até existir fonte", ADR-0017).
- **Falta:** tabela `notificacao` (UPDATE só `lida_em`), produzida pelos mesmos eventos da outbox; API `/notificacoes`; `notificacoes_nao_lidas` em `/sessao`; flag `notificacoes`; sino só com aceite visual; Web Push só com consentimento/SW/ADR.
- **Estado:** 🔒 F2 · ⬜ · ⚠️ DIV-10.
- **Fase:** F2 NOT-02 / sem fase.
- **IDs:** TI-18 (produção já na Fase 3), TI-85, TI-91 · EXT-02 · DEC-08.

### 3.16 P16 · Comunidade

- **Spec pede:** diretório de especialistas e grupos moderados primeiro; mentoria depois; rede de encaminhamento só com parecer jurídico sobre dados de saúde. F3.
- **Existe hoje:** rota `comunidade` visível no menu (em construção), flag `comunidade_posts`, ações sem emissor; RF-CO-01..07 (wa.me 1:1, LA-09). Mockup `relacionamento` (confirmar).
- **Falta:** tudo; e a rota não deveria estar no menu antes de F3.
- **Estado:** 🔒 F3 · ⬜ · ⚠️ DIV-44.
- **Fase:** F3 DIR-01, COM-01, MEN-01, ENC-01 / Fase 6.
- **IDs:** TI-89, TI-60 · EXT-18, P-11 · DEC-24.

### 3.17 P17 · Mensalidade patrocinada e cartão

- **Spec pede:** só com contrato (patrocinador e banco), parecer jurídico e critérios de mensuração; nasce desligada; o associado vê quanto o patrocínio cobre; patrocinador só agregado.
- **Existe hoje:** pill e bloco "Mensalidade Zero" sob flag `mensalidade_zero` (forçada desligada, P-12), texto fixo "· 2026".
- **Falta:** nada até contrato; ao ligar, dado real no lugar do texto.
- **Estado:** 🔒 F3 · ⛔ contrato.
- **Fase:** F3 MZ-01/CARD-01 / Fase 8.
- **IDs:** — · EXT-37 (P-12).

## 4. Backoffice B01–B13, perfis e 2FA (escopo novo)

A spec coloca o backoffice na F1 (B01–B06, B12, B13) com 8 perfis, verificação em duas etapas em todo
acesso, log imutável de ações e "registro de acesso a dados pessoais". O `REQUISITOS` v0.1 o declara
fora de escopo ("atendimento no CRM"). **Decisão do usuário (29/10): levantar como escopo novo; onde
vive fica como DEC-03.** Nada abaixo decide a hospedagem; tudo lista o que a área tem de guardar ou
expor para que algum backoffice exista.

### 4.1 Princípios que valem para qualquer opção (Sentinela)

- A identidade do staff **nunca** é o `login_associado` (IdP de associados por CPF): usar o IdP
  corporativo da APM (Entra ID, grupos → perfis, MFA) ou o portal do `mcp_hub` (que já tem usuários,
  grupos, `permissao` nega-por-padrão, `modo_pii`, cota e auditoria por titular).
- Nunca dentro da área com a sessão do associado: superfície de `minha.apm.org.br` e cookie
  `__Host-` não se misturam com staff (um XSS na área viraria backoffice).
- Sessão de staff curta (≤ 8 h absoluta, 30 min de inatividade), cookie `__Host-` próprio, CSP sem
  inline igual à da área, `limit_req` próprio, allowlist de IP/VPN e Cloudflare Access na frente.
- **Usuário de banco próprio** (`apm_area_bo`) com UPDATE nas tabelas de catálogo/configuração e
  **sem** UPDATE nas tabelas do associado; `apm_area` (web) continua só leitura do catálogo;
  `db_check.py` valida os dois (TI-03).
- Trilhas append-only: `backoffice_auditoria` (valor anterior/novo, justificativa), `acesso_dado_pessoal`
  (cada visualização da visão 360: quem, qual `contact_id`, quais campos). Perfis Diretoria e Regional
  sem PII individual (agregados k ≥ 20); Parceiro (PAR-01) só as próprias solicitações, nunca CPF.
- B02 "busca por CPF" só no hub (grants/PII); na área, por nome, número ou `contact_id` (DIV-11).

### 4.2 Módulo a módulo

| Módulo | Fase | Dados na área (tabelas) | Operações / API interna (`/api/interno/v1`, token de serviço, nunca a sessão do associado) | Depende de | Estado |
|---|---|---|---|---|---|
| B01 Painel do dia | F1 | `solicitacao` (`sem_retorno_desde`), `importacao`, `titular_pedido`, `comunicacao_evento` (erro), `job_execucao`, `fila_ligacao` | `GET /painel/dia` (agregados) | Fase 3 (TI-14, TI-17, TI-18) | ⬜ |
| B02 Visão 360 | F1 | `associado*`, `solicitacao`, `beneficio_ativacao`, `uso_valor`, `consentimento`, `comunicacao_*` | `GET /associados/{contact_id}` (local + hub `associado.visao_360`, sensível) + registro `acesso_dado_pessoal` | grant do hub; DEC-03 | ⬜/⛔ |
| B03 Benefícios | F1 | `beneficio` (ficha completa: elegibilidade, tipo, prazo, selos, FAQ, vigência, afinidade), `beneficio_versao` (histórico), `valor_referencia` (aprovação do Financeiro) | CRUD rascunho → aprovação → publicação agendada; prévia "ver como associado" | TI-29; `apm_area_bo` | ⬜ |
| B04 Parceiros e contratos | F1 | `parceiro` (código APM `PAR017`, requisito técnico api/relatorio/portal, prazo de retorno, vigência, contatos sem CPF, documentos = referência) | CRUD | DEC-03; `apm-parceiros` é outro sistema (cadastro mínimo próprio, chave de conciliação com o CSV) | ⬜ |
| B05 Solicitações e leads | F1 | `solicitacao*` | fila com filtros, `POST .../status` com **justificativa obrigatória** (`origem=backoffice`, usuário no evento), reenviar, exportar CSV; leads fora da área (DEC-19) | TI-14, TI-15 | ⬜ |
| B06 Importações | F1 | `importacao`, `importacao_linha` (**sem CPF**) → `uso_valor` | upload (canal DEC-05) → hub resolve CPF → prévia por linha → confirmar → devolução de erros | TI-51, TI-54, DEC-05 | ⬜/⛔ |
| B07 Home e conteúdo | F1→F2 | `destaque_editorial`, `faq`, `trilha_passo`, `texto_sistema` (estados vazios/erro editáveis) | CRUD com vigência | TI-29, TI-20, TI-43 | ⬜ |
| B08 Segmentos | F1→F2 | `segmento` (regras), `beneficio_afinidade` | CRUD + prévia (`inicio.montar` com perfil alvo) | TI-33, TI-34 | ⬜ |
| B09 Comunicação | log F1 / completo F2 | `comunicacao_evento`, `comunicacao_envio`, `comunicacao_supressao`, `notificacao`, consentimentos | `GET /comunicacao?gatilho=&status=` | TI-18, TI-53 | ⬜ |
| B10 Clube · B11 Eventos | F2 | curadoria, agenda | — | F2 | 🔒 |
| B12 Painéis e relatórios | v1 F1 | views `vw_ind_01..14`, `base_ativa_mensal`, `vw_qualidade_parceiro_mes` (k ≥ 20 nos recortes) | consultas agregadas; exportação só agregada; usuário `apm_area_painel` só `SELECT` nas views | TI-44, DEC-16 | ⬜ |
| B13 Configurações e LGPD | F1 | `parametro`, carências (em `beneficio`), `valor_referencia`, `consentimento_texto`, `titular_pedido`, `feature_flag`, `usuario_interno`, `backoffice_auditoria` | CRUD com justificativa; fila LGPD (exportação/exclusão) | TI-25, TI-29; hoje `feature_flag` só por operador | ⬜ |
| Perfis + 2FA (§9.1) | F1 | `usuario_interno` (sem senha; identidade externa), perfil ENUM(8) | — | DEC-03, EXT-36 | ⛔ decisão |

### 4.3 Caminho sem backoffice (enquanto DEC-03 não sai)

Operador por SQL com `beneficio_versao`/`backoffice_auditoria` alimentados por script administrativo
(como `feature_flag` hoje); fila de ligações entregue à Central por CSV interno ou view no portal do
hub (TI-59); importação do plano B indisponível (ou operador copia o arquivo para o volume dos jobs,
DEC-05); status manual de solicitação só pelo CRM (`task`, P-06). Isso **não** atende "editável sem
desenvolvedor" (§3 item 8) e fica registrado como limitação da F1 até a decisão.

**IDs:** TI-03, TI-58, TI-59, TI-80, TI-81, TI-90 · EXT-36, EXT-31, EXT-22 · DEC-03, DEC-05, DEC-16 ·
DIV-11, DIV-17.

---

## 5. Motor de regras

### 5.1 Elegibilidade (§8.1) — 6 estados

Disponível = categoria permitida ∧ filiação ≥ carência ∧ situação financeira permite ∧ região atendida
∧ vigente. Estados: Disponível · Ativo · Libera em N dias · Não disponível para a categoria · Suspenso ·
Indisponível na região.

| Insumo | Fonte hoje | Falta |
|---|---|---|
| categoria | `associado_perfil.tipo_associado` (rótulo do CRM) | código fechado + de-para (EXT-11; TI-92) |
| data de filiação | `associado_perfil.data_filiacao` ✓ | histórico de categorias (hub por CPF, P-04) só se a carência reiniciar (DEC-15: não) |
| situação financeira | nada (hub por CPF, P-04/P-08) | `financeiro.situacao_consultar(contact_id)` + cache mínimo `associado_financeiro` (situação, dias) · até lá `financeiro=None` ⇒ permite e "Suspenso" não ocorre (DEC-14, documentado em "como calculamos") |
| região | `crm_uf` (UF do CRM) — não é regional/distrital | atributo do contato via hub (EXT-19, TI-48) · até lá ignorada |
| vigência, carência, categorias permitidas, regional | catálogo (inexistente) | `beneficio` com `vigencia_*`, `carencia_meses`, `exige_adimplencia`, `regional`; `beneficio_categoria_associado` (TI-29) |
| ativo | `beneficio_ativacao` (prevista) | TI-29 |

Implementação: `app/dominio/elegibilidade.py` **pura** (`avaliar(perfil, beneficio, ativacoes, financeiro,
hoje) → Elegibilidade(estado, libera_em, motivo, acao_sugerida)`), ordem vigência → categoria → região →
financeiro → carência → ativo, testada por tabela; API devolve `estado` + `libera_em` em `/beneficios`
e `/beneficios/{slug}`; `409 nao_elegivel` na ativação. **IDs:** TI-30, TI-29, TI-48, TI-49 · EXT-10,
EXT-11, EXT-19 · DEC-14, DEC-15 · DIV-31.

### 5.2 Carências (§8.2), matriz (§8.3) e parâmetros (§8.4, B13)

- Carência é **atributo do benefício** (`beneficio.carencia_meses`, 0–12), editável no backoffice, com
  histórico em `beneficio_versao`; lista do regulamento de 01/03/2024 entra como seed **só depois de
  validada** (EXT-10); carência do Clube pendente (EXT-11). `libera_em = data_filiacao + carencia_meses`
  (DEC-15; `parametro.carencia_reinicia_por_categoria=false` para trocar sem deploy).
- Matriz `beneficio_categoria_associado` nasce "todos permitidos" (hoje só o tempo de filiação
  diferencia) para a regra entrar por configuração quando a presidência decidir.
- `parametro(chave, valor, tipo)` (dias de atraso que suspendem, prazo de retorno padrão, prazo de
  avaliação, dias de dispensa) com leitura em cache como `flags.py`; UPDATE só pelo usuário do backoffice
  (ou operador por SQL até DEC-03).
- Job diário `carencia_vencida` (A03): `evento_uso carencia_vencer` + outbox + notificação + bloco
  Pendência (≤ 7 d). **IDs:** TI-29, TI-42 · EXT-10, EXT-11 · DEC-15.

### 5.3 Tipos de ativação 1–6 (§6 P04) — estratégia por tipo

| Tipo | Botão (proposta) | Grava | Responde | Hoje | Estado |
|---|---|---|---|---|---|
| Tipo 1 · Acesso direto | `POST /beneficios/{slug}/ativar` → elegibilidade → upsert `beneficio_ativacao` → `url_acesso` pelo redirecionador `GET /api/v1/ir/{slug}` (302 só do seed; allowlist no servidor) | `beneficio_ativacao`, `beneficio_acessar` (servidor), nível 2 | `200 {estado, url_acesso, proximo_passo}` | RF-BE-07/09 planejados; TotalPass por ADR-0008 (hub por CPF, P-04) | ⬜ · "acesso único"/código pessoal só com ADR por parceiro (DIV-08) |
| Tipo 2 · Encaminhamento ao parceiro | cria `solicitacao` (`beneficio_id`, `parceiro_id`, `tipo_ativacao=2`, `canal_envio` do parceiro: `relatorio`/`email` na F1, `api`/`portal` F2); **nenhuma chamada HTTP a parceiro** (ADR-0009); dados do associado não vão no corpo | `solicitacao` + evento + outbox CRM + A04 | `201 {id, status: criada, prazo, proximo_passo}` | fora de escopo (ADR-0009) | ⬜ local viável (DEC-04) · ⛔ integração por parceiro (EXT-12) |
| Tipo 3 · Serviço da APM | `solicitacao` de `tipo_servico` (os 7 atuais + `declaracao_associado`, `cancelamento_associacao`, `exclusao_dados`) com responsável/prazo da ficha, `canal_envio=crm` | idem | `201` | ADR-0003 desenhada | ⬜ Fase 3 |
| Tipo 4 · Reserva | `GET .../disponibilidade` + `POST .../reservar` → `solicitacao(tipo_ativacao=4)` + período | `solicitacao`, `reserva` | `201` / `409 indisponivel` | nada | ⛔ fonte de disponibilidade (Hotel Fazenda/Residencial) · flag `reservas` 🔒 F2 |
| Tipo 5 · Inscrição | `POST /eventos/{id}/inscrever` com `perfil_preco` pela categoria; F1 = interesse local; carência 3 m pelo motor | `evento_inscricao` + `evento_inscrever` | `201 {status: interesse\|inscrito, preco}` | ação catalogada | 🟡 interesse · ⛔ real (F0-01, EXT-13) · flag `inscricoes` |
| Tipo 6 · Resgate no clube | `POST /clube/ofertas/{id}/abrir` registra e devolve `url_externa` (seed, allowlist) | `clube_oferta_usar`; F2 `uso_valor(fonte=clube)` | `200 {url_externa}` | só clique | 🟡 · 🔒 retorno de economia só com integração (EXT-13) |

Regra comum: tipos 1–5 não aceitam dado pessoal no corpo (vem do cache do perfil); resposta sempre com
`prazo` e `proximo_passo`; negado → `409 nao_elegivel {estado, libera_em}`. Flags novas por tipo (2, 4,
5, 6) conforme §14 da spec (TI-13). **IDs:** TI-31, TI-32, TI-24, TI-13 · EXT-12, EXT-13 · DEC-04, DEC-10 ·
DIV-08, DIV-26.

### 5.4 Máquina de estados da solicitação (§8.5) — 8 status

| Spec | Rótulo ao associado | Hoje (ADR-0003 / REQ §7) | Proposta | Terminal |
|---|---|---|---|---|
| `criada` | Recebida pela APM | `aberta` | `criada` | não |
| `enviada` | Enviada ao parceiro | — (`crm_sync=ok`, técnico e invisível) | status de negócio promovido pelo job quando o canal confirma (`crm` ⇒ espelho ok; `relatorio`/`email` ⇒ operador marca; `api`/`portal` ⇒ ack). Rótulo por `tipo_ativacao` (tipo 3: "Encaminhada à equipe"). Falha de espelho continua invisível | não |
| `em_atendimento` | Em atendimento | `em_analise` | `em_atendimento` | não |
| `pendente_associado` | O parceiro precisa de algo seu | `aguardando_associado` | `pendente_associado` | não |
| `concluida_positiva` | Concluída | `concluida` | `concluida_positiva` | sim |
| `concluida_negativa` | Não seguiu | `recusada` | `concluida_negativa` | sim |
| `cancelada` | Cancelada | `cancelada` (só associado) | associado **ou** APM com justificativa | sim |
| `sem_retorno` | Aguardando o parceiro (a APM já está cobrando) | — | **coluna-marcador** `sem_retorno_desde` posta por job, limpa em qualquer transição; não é status | — |

Transições (ator · origem): `—→criada` (associado · ui) · `criada→enviada` (sistema · job | apm · backoffice) ·
`criada|enviada→em_atendimento` (parceiro/apm · crm/backoffice/api/portal) · `em_atendimento→pendente_associado`
(mensagem pública obrigatória) · `pendente_associado→em_atendimento` (associado responde) ·
`enviada|em_atendimento→concluida_*` (parceiro/importação/apm; resultado com valor ⇒ `uso_valor` nível 3) ·
`criada|enviada|pendente_associado→cancelada` (associado; **nunca** a partir de `em_atendimento`) · qualquer
não terminal → `cancelada` (apm, justificativa) · terminal → `409 estado_invalido`. Marcador: `enviada_em +
prazo_retorno_dias < agora` ⇒ `sem_retorno_desde` + A05; 2.º vencimento ⇒ fila de ligações. Avaliação 0–10
em colunas da solicitação, 1 vez, prazo `parametro.avaliacao_prazo_dias` (30). Cada transição = UPDATE
condicional (`WHERE status = :de`) + INSERT em `solicitacao_evento` na mesma transação (ADR-0003 mantida),
depois `evento_uso`, outbox e espelho. "Conteúdo enviado" no log = lista de campos + sha256 do payload +
destino/canal, nunca o payload (DEC-02). Colunas novas: `beneficio_id`, `parceiro_id`, `tipo_ativacao`,
`tipo_servico`, `canal_envio`, `prazo_retorno_dias`, `enviada_em`, `sem_retorno_desde`, `responsavel`,
`resultado JSON`, `avaliacao_*`, `cancel_motivo`, `chave_idempotencia`. Mapeamento `task` do CRM continua
(P-06 precisa distinguir "não seguiu" de "cancelada pela APM"). Sem dado legado: os nomes da spec entram já
na `sql/008` (adenda à ADR-0003). **IDs:** TI-14, TI-15, TI-16, TI-17, TI-50 · EXT-20 · DEC-01, DEC-02, DEC-22 ·
DIV-15, DIV-16, DIV-24.

### 5.5 Cálculo do valor (§8.6) e níveis de evidência (§11.2.1)

- `valor_referencia` (append-only: valor, base anual/por uso, fonte, data, `aprovado_por`, `aprovado_em`,
  vigência, `revisao_prevista_em`; vigente = última aprovada ≤ hoje) e `uso_valor` (append-only: contact,
  benefício, parceiro, solicitação/importação de origem, data, `modalidade` ENUM(economia_uso,
  desconto_parceiro, servico_apm, protecao_incluida, estimado), `nivel_evidencia` 1–4, valores, `fonte`,
  `validado_em`; estorno e validação do Financeiro = linha nova apontando a original; CHECK
  `economia = referencia − pago`; nível 4 exige `validado_em`).
- Nível por origem: 1 = `evento_uso` (visto); 2 = `solicitacao` criada/`beneficio_ativacao`; 3 =
  concluída positiva ou importação sem validação; 4 = `uso_valor` validado. **Só nível 4 soma ao
  comprovado.** Proteção incluída = `valor_anual × meses ativos / 12`, bloco separado. Estimado nunca
  soma. "N vezes" = (comprovado + proteção) ÷ total pago, só se total pago > 0 e numerador > pago;
  total pago 0 ⇒ "valor entregue" + composição do patrocínio; < 3 meses ⇒ "o que cobre".
- `beneficio.modalidade_mensuracao` ENUM(api_acesso_unico, relatorio_padrao, encaminhamento_sem_retorno)
  e `vw_qualidade_parceiro_mes` (completude, duplicidade, atraso, sem associação, conciliação).
- Guardas: flag `fatura_valor` só liga com `valor_referencia` aprovada; número sem fonte não chega ao
  associado (regra 19). **IDs:** TI-35, TI-36, TI-44, TI-54 · EXT-10, EXT-17, EXT-24 · DEC-23 · DIV-23.

### 5.6 Recomendação v1 (§7.3) e blocos da home (§7.2)

- `beneficio_afinidade(beneficio_id, segmento, pontos 0–3)` (B08), `recomendacao_dispensa` (60 d, append),
  `recomendacao_exposicao` (rotação: 3 semanas sem interação perde prioridade; UPDATE), sinais de
  `evento_uso` (`beneficio_abrir` 30 d sem ativação +2), carência vencida 30 d +2, novo +1, tema/área +1,
  patrocinado +1 (≤ 1 nos 4 primeiros; vale 0 enquanto `patrocinio` forçada desligada); exclusões: ativo,
  dispensado, não disponível; desempate por valor de referência; ≤ 2 por categoria; "por que estou vendo
  isto" = `motivos[]`. Função pura `recomendacao.pontuar(candidatos, sinais)`.
- Fase de carreira exige nascimento → o hub entrega só a **faixa** derivada (EXT-19, TI-48); até lá,
  afinidade por categoria.
- `inicio.montar(perfil)` monta os 9 blocos com fonte própria, omite vazios, ordem fixa do servidor;
  `destaque_editorial` (ADM-05) com `UNIQUE (segmento, vigência)` garante "um por vez". **IDs:** TI-33,
  TI-34, TI-40, TI-29 · EXT-10, EXT-19, EXT-09.

---

## 6. Dados e analytics

### 6.1 Modelo de dados §11.1 → tabelas (resumo; coluna a coluna em [`spec-v2/personas/atlas.md`](spec-v2/personas/atlas.md) e no futuro REQUISITOS v0.2)

Convenções mantidas: `contact_id CHAR(36)` com CHECK, `sub_hash` onde houver guarda longa, `DATETIME(6)`
UTC, JSON com CHECK anti-CPF/segredo, remoção lógica, `GRANT UPDATE` na própria migração com
justificativa (ADR-0004). Numeração abaixo é **reserva**; o número definitivo é o da migração aprovada.

| Migração | Tabelas | UPDATE? | Append-only | Fase spec / roteiro |
|---|---|---|---|---|
| `sql/008` | `solicitacao` (8 status, vínculos, prazo, marcador, avaliação, idempotência), `solicitacao_evento` (atores/origens/justificativa/conteúdo enviado = campos + sha256) | sim / não | — / sim | F1 / **Fase 3** |
| `sql/009` | `job_execucao` (CHECK regex em `job`, anti-segredo em `erro_resumo`) | sim | não | F1 / Fase 3 |
| `sql/0NN` (cedo) | `evento_uso`, `evento_log` → PK `(id, ocorrido_em)` + `PARTITION BY RANGE` mensal (expurgo por `DROP PARTITION` administrativo, sem DELETE) | — | — | F0 / **agora** (TI-02) |
| `sql/010` | `parceiro`, `beneficio_categoria`, `beneficio` (+ `beneficio_versao`, `beneficio_faq`), `beneficio_categoria_associado`, `beneficio_afinidade`, `beneficio_ativacao`, `recomendacao_dispensa`, `recomendacao_exposicao`, `parametro`, `associado_categoria_hist`, `ALTER associado_perfil` (+ `faixa_carreira`, `especialidade_cod`, `regional_cod`, `nome_social`, `isento_remido`), `perfil_declarado`, `destaque_editorial`, `faq`, `texto_sistema` | catálogo/config: só `apm_area_bo` (DEC-03); ativação/dispensa/perfil: `apm_area` | versão, dispensa, hist: sim | F1 / Fase 4 (FAQ/textos: Fase 3) |
| `sql/011` | `valor_referencia`, `uso_valor`, `importacao`, `importacao_linha` (**sem CPF**, único `(parceiro_id, id_externo)`), `vw_meu_valor_ano` | importação: status/contagens | sim | F1 / Fase 4 (antecipada) |
| `sql/012` | `noticia_cache`, `evento_cache`, `tema`, `associado_tema`, `noticia_salva`, `evento_inscricao` | cache e desfazer (REQ §6) | não | F2 / Fase 5 |
| `sql/013` | `consentimento_texto`, `consentimento` (append; `vw_consentimento_atual`), `preferencia_canal`, `pergunta_perfil`, `titular_pedido`, colunas `anonimizado_em` | preferência/pedido | consentimento: sim | F1 / Fase 3b |
| `sql/014` | `comunicacao_evento` (outbox; único `(gatilho, contact_id, referencia_id)`), `comunicacao_envio` (particionar), `comunicacao_supressao`, `notificacao` (UPDATE só `lida_em`) | outbox/notificação | envio/supressão: sim | F1 log / Fase 3 (produção) |
| `sql/016` | `trilha_passo` (por categoria), `trilha_progresso` (append), `comunidade*`, `oferta_clube` | — | progresso: sim | F1 bloco / Fase 4–6 |
| `sql/017` | `usuario_interno` (sem senha), `backoffice_auditoria`, `acesso_dado_pessoal` | usuário | trilhas: sim | F1 / ⛔ DEC-03 |
| `sql/018` | `associado_financeiro` (cache mínimo: situação, dias; **sem valores**) | cache | não | F1 cond. / Fase 7 |
| `sql/019` | `score_engajamento` (PK `(contact_id, data)`, particionada), `score_pesos` | — | sim | F2 |
| `sql/020` | `base_ativa_mensal` (denominadores por categoria/regional, via job) | — | sim | F1 B12 |
| `sql/021` | views `vw_ind_01..14`, `vw_qualidade_parceiro_mes`; usuário `apm_area_painel` só `SELECT` nas views; k ≥ 20 nos recortes | — | — | F1 B12 |

Tabelas que **não** devem existir na área: CPF em qualquer forma (ADR-0014), senha de usuário interno,
payload de mensagem (vive no RD), dado de saúde, valores/mensalidades do associado além do cache de
situação (vêm do hub na hora), `lead` com CPF (DEC-19). **IDs:** TI-02, TI-03, TI-14, TI-25, TI-29, TI-35,
TI-44, TI-54, TI-56, TI-80, TI-86 · DIV-18, DIV-19, DIV-20.

### 6.2 Eventos de uso: 28 da spec × 36 de `app/uso.py` — catálogo unificado

Princípio: **manter os nomes já em código** (renomear quebra 8 emissores e 47 testes do front por ganho
cosmético); o nome da spec entra como coluna em REQ §8 e nas views. Propriedades comuns (categoria, fase,
especialidade, regional, tempo de casa) **não** vão em cada linha: são dimensões por junção com
`associado_perfil`/`associado_categoria_hist` na data do evento (minimização, ADR-0012). Só o que não é
derivável entra em `detalhes` (tipado, sem texto livre, sem valor monetário). Mecânica inalterada (catálogo
fechado, identidade da sessão, lote ≤ 20, transação própria, nunca lança, CHECK anti-CPF).

| Spec | Atual | Proposta | `detalhes` | Origem |
|---|---|---|---|---|
| acesso_primeiro | — | **acrescentar** `acesso_primeiro` em `registrar_acesso` (upsert insere) | `dias_desde_filiacao`; método vem do IdP (DEC-12) | servidor |
| login | `evento_log` login_ok/falha | manter em `evento_log` (ADR-0012); indicador 1/14 lê de lá | — | — |
| home_vista | pagina_ver(rota=/area) | manter + `blocos[]` (enum) e `segmento` | | ui |
| home_bloco_clicado | — | **acrescentar** `home_bloco_clicar` | `bloco`, `posicao`, `item` | ui |
| busca | busca_global | manter sem termo (RNF-16); termo só em `busca_sem_resultado` **sem identidade**, normalizado ≤ 48 (DEC-34) | `resultados`, `tamanho` | ui |
| beneficio_visto | beneficio_abrir | manter como "página aberta" + `origem` ENUM(home, catalogo, busca, email, trilha) e `estado` (6); CTA externo vira `beneficio_acessar` | | ui / servidor |
| recomendacao_dispensada | — | **acrescentar** `recomendacao_dispensar` | `motivo` | servidor |
| solicitacao_criada | solicitacao_criar | manter + `tipo_ativacao`, `beneficio` | | servidor |
| solicitacao_status | solicitacao_status_alterado | manter; origem `servidor` e `job`; `de`, `para`, `origem` ENUM | | servidor, job |
| uso_registrado | — | **acrescentar** `uso_registrar` (`entidade_id` = `uso_valor.id`; **sem valores**) | `fonte`, `nivel` | servidor, job |
| carencia_vencida | — | **acrescentar** `carencia_vencer` | `liberado_em` | job |
| carteirinha_aberta | pagina_ver(carteirinha) | manter (derivar) | | ui |
| carteirinha_validada | carteirinha_verificar | manter + `resultado` ENUM(ativo, inativo, nao_confirmado) | | publico |
| financeiro_segunda_via | — (`fatura_pdf_baixar` sem emissor) | **unificar** em `fatura_segunda_via` com `forma` ENUM(pdf, linha_digitavel, pix); retirar `fatura_pdf_baixar` | `competencia` | servidor |
| pagamento_confirmado | — | **acrescentar** `pagamento_confirmar` (job de sync; sem valor) | `competencia`, `forma` | job |
| meu_valor_visto | pagina_ver(meu-valor) | manter + `periodo`; valor exibido é derivável | | ui |
| clube_acesso | clube_oferta_usar | manter + `origem` | | ui/servidor |
| clube_resgate | — | **acrescentar** `clube_resgatar` (F2) | | job |
| evento_inscricao | evento_inscrever, congresso_garantir_vaga | manter + `perfil_preco` | | servidor |
| evento_presenca | — | **acrescentar** `evento_presenca_registrar` (F2) | `tipo` | job |
| conteudo_lido | noticia_abrir | manter + `tema`; `noticia_ler_tempo` opcional (`segundos` ≤ 3600, no `pagehide`) | | ui |
| tema_seguido | tema_seguir, tema_deixar | manter | | servidor |
| trilha_passo | onboarding_passo_concluir | manter + `dia_jornada`; emitido pelo servidor por evento real | | servidor |
| perfil_atualizado | perfil_contato/foto_atualizar | manter + `perfil_declarado_atualizar` (`campos[]` nomes, nunca valores) | | servidor |
| consentimento | — | **acrescentar** `consentimento_alterar` | `finalidade`, `canal`, `valor`, `versao` | servidor |
| notificacao | — | **acrescentar** `notificacao_abrir` (ui) e `notificacao_criar` (job) (F2) | `tipo` | ui, job |
| ajuda_contato | central_whatsapp_abrir | manter + `ajuda_contatar` com `canal`, `assunto` (migrar emissor) | | ui |
| cancelamento_pedido | — | **acrescentar** `cancelamento_pedir` | `motivo` ENUM | servidor |
| — | — | **acrescentar** `solicitacao_avaliar` (A06), `vitais_web` (LCP/INP/CLS) e `erro_js` (RUM próprio, TI-67) | `nota`; métricas numéricas tipadas | servidor; ui |

`dispositivo` → classe grossa (mobile/desktop/pwa) derivada no servidor do UA (nunca o UA); UTM/código
do gatilho → `detalhes.gatilho` validado contra catálogo fechado (TI-11). Teste obrigatório `AcaoUi` (front)
= `ACOES_UI` (servidor). **IDs:** TI-04, TI-05, TI-11, TI-67 · DEC-34 · DIV-14.

### 6.3 Indicadores 1–14 (§11.3): fonte do numerador e do denominador

| # | Indicador | Numerador | Denominador | Hoje |
|---|---|---|---|---|
| 1 | Associados com acesso | `associado.ultimo_acesso_em` / `evento_log login_ok` | base ativa (CRM) | 🟡 numerador ✓; denominador = `base_ativa_mensal` por job (EXT-25) |
| 2 | Ativação em 30 d | `uso_valor` nível ≥ 3 ou solicitação concluída ≤ 30 d de `data_filiacao` | novos do mês (CRM) | ⬜ |
| 3 | Benefícios em uso 90 d | `COUNT(DISTINCT beneficio_id)` nível ≥ 3 | ativos | ⬜ |
| 4 | Valor entregue | `vw_meu_valor_ano` | total pago (cobrança) | ⛔ P-08 |
| 5 | Rastro | `solicitacao` terminal | criadas | ⬜ Fase 3 |
| 6 | Prazo do parceiro | mediana `enviada_em` → 1.º retorno por parceiro (view com `ROW_NUMBER`) | — | ⬜ Fase 3 |
| 7 | Conversão por parceiro | `concluida_positiva` | solicitações do parceiro | ⬜ |
| 8 | Novos com origem | hub `filiacao.resumo_periodo` | — | ⛔ fora da área (painel lê do hub) |
| 9 | Taxa de conversão | `associado_categoria_hist` + leads | — | ⛔ histórico por CPF (P-04); leads fora (DEC-19) |
| 10 | Pessoas comunicadas | `comunicacao_envio` (entregue/aberto/clicado via RD) | base ativa | ⬜ §7 |
| 11 | Renovação × uso | renovação (cobrança) × `uso_valor` por coorte | — | ⛔ "renovação" sem fonte (EXT-24) |
| 12 | Cancelamento precoce | `cancelamento_pedir` ≤ 90 d | novos | ⬜ P14 |
| 13 | Motivo "não utiliza" | `motivo` | cancelamentos | ⬜ |
| 14 | Saúde técnica | `login_falha`, `erro_exibido`, `erro_js`, `vitais_web`, uptime externo | — | 🟡 |

Painéis §11.5: views por migração com k ≥ 20 nos recortes a terceiro/regional, usuário `apm_area_painel`,
ferramenta por DEC-16 (nunca script de terceiro na SPA: CSP). Score §11.4: `score_engajamento` diário,
pesos versionados, componente "comunicação" depende de retorno do RD (F2, DEC-18). **IDs:** TI-44, TI-86,
TI-75 · EXT-09, EXT-25, EXT-24 · DEC-16 · DIV-32.

### 6.4 LGPD e governança (§11.6)

- ✅ pseudonimização (`contact_id`/`sub_hash`, HMAC em `evento_log`, CHECK anti-CPF), minimização
  estrutural, `/sessao` sem PII, `localStorage` proibido por lint.
- ⬜ consentimento versionado por finalidade/canal (append-only), direitos do titular (exportar: síncrono
  com dados da área + step-up; excluir: pedido com protocolo + anonimização por coluna de estado por job,
  **sem DELETE**; `evento_log` fica por obrigação legal), registro de acesso a dado pessoal (padrão
  `acesso_dado_pessoal` em `evento_log`), agregados k ≥ 20 (função única), allowlist de campos por tipo de
  solicitação e `beneficio.sigiloso` (`dados={}`; nunca dado de saúde), faixa de carreira derivada (nunca
  nascimento), retenção por tabela com partição mensal + `docs/RETENCAO.md`.
- ⛔ prazos de guarda, textos e base legal, procedimento de exclusão (EXT-16).
- **IDs:** TI-25, TI-26, TI-28, TI-15, TI-90, TI-02 · EXT-16 · DEC-06 · DIV-05.

---

## 7. Comunicação (§12): gatilhos A01–A20, RD Station e transacionais

**Arquitetura (DEC-18):** a área **emite** campos e eventos (outbox `comunicacao_evento` produzida na
mesma transação do negócio, consumida por job `outbox_rd`); a régua, o limite de 2 msg/semana e o
horário 8h–20h vivem no RD (a área não conhece envios de outros sistemas); a área aplica só
**supressão** por campos (`cf_apm_suprimir_ofertas`, `cf_apm_cancelamento_pedido`, benefício solicitado
há 14 d) e grava consentimento local (descadastro = `PATCH contacts/email:{email}` síncrono com fallback
no outbox e **nunca mais enfileira** para o canal). Transacionais (A04, A05 aviso ao associado, A06,
códigos) saem pelo SMTP da área (P-27), nunca marketing (SMTP corporativo ~30/min). Chave no RD =
`cf_apm_contactid` (e-mail muda; CPF nunca). UTM + `g=A0n` nos links de volta, lidos uma vez pela SPA
(TI-11). **Reaproveitável:** OAuth2 (refresh → access com cache e margem), classificação de resposta,
outbox com revalidação do fato e `GET_LOCK` já existem no `totalpass` e no `app_facial_recognition`;
campos `cf_apm_*` já existem no RD (planilha de 29/10).

| ID | Gatilho | Fase | Fonte do evento | Canal | Pré-requisito externo | Estado |
|---|---|---|---|---|---|---|
| A01 | Filiação confirmada | F1 | cadastro (sem aviso) → job `diff_cadastro` no cache de perfil (`status_associativo` → Ativo) | RD-evento + RD-campo | EXT-24 (aviso) ou TI-47/TI-55 (varredura); cota EXT-25 | ⬜ (DEC-20) |
| A02 | 1.º acesso não feito (3 d) | F1 | A01 sem `associado.primeiro_acesso_em` | RD-evento (WhatsApp/SMS pelo RD) | A01; canal no RD (EXT-35) | ⬜ |
| A03 | Carência vencida | F1 | área: job diário `data_filiacao` × catálogo | app (bloco Pendência) + RD-evento | catálogo validado (EXT-10) | ⬜ TI-42 |
| A04 | Solicitação criada | F1 | área (`→criada`) | **SMTP** + notificação (+ evento ao RD) | P-27 | ⬜ TI-19 |
| A05 | Sem retorno no prazo | F1 | área: job `marcar_sem_retorno` | SMTP interno (B01) + aviso ao associado | prazo por parceiro (EXT-10) | ⬜ TI-17 |
| A06 | Concluída → "como foi?" | F1 | área (`→concluida_*`) | SMTP com link HMAC → `POST .../avaliar` | — | ⬜ TI-19 |
| A07 | Visto 2× sem ativar (14 d) | F2 | `evento_uso` | RD-evento | — | 🔒 |
| A08 | Resumo mensal | F2 (F1 proteção) | job dia 1 (Meu valor) | RD-campo + RD-evento (e-mail sai do RD) | fórmula aprovada (EXT-10) | 🔒 |
| A09 | Mensalidade vencida (3 d) | F1 | **cobrança**: job `faturas_vencidas` via hub | RD-evento + `cf_apm_data_inadimplencia`; supressão local | P-04, P-08, cota (EXT-17, EXT-25); 2.ª via inexistente | ⛔ |
| A10 | Renovação 60/30/7 d | F2 | cobrança — "renovação" sem fonte | RD + fila de ligações | EXT-24 | ⛔ |
| A11 | Sem acesso e sem uso 90 d | F2 | `ultimo_acesso_em` + `evento_uso` | RD-evento | — | 🔒 TI-55 |
| A12 | Score < 30 | F2 | job score; componente "comunicação" exige retorno do RD | fila de ligações + `cf_apm_score` | export diário do RD (DEC-18) | 🔒 |
| A13 | Mudança de categoria | F2 | `diff_cadastro` (tipo anterior × atual) | RD-evento + `cf_apm_categoria` | TI-47 | 🔒 TI-55 |
| A14 | Evento da especialidade/região | F2 | job WP × temas × regional | RD-evento | especialidade/regional (EXT-19); P-07/P-21 | 🔒 |
| A15 | Novo benefício com afinidade alta | F2 | publicação × matriz | app + resumo | matriz (B08) | 🔒 |
| A16 | Pedido de cancelamento | F1 | área (P14) | RD-evento (fluxo 6) + espelho CRM + SMTP à Central | P-06 | ⬜ TI-20 |
| A17 | Interesse de não associado | F1 | parceiro (CSV) / formulário / evento | RD-evento (fluxo 1) — o formulário de filiação já cobre | lead sem CPF na área (DEC-19) | 🟡 fora da área |
| A18 | Aniversário / Dia do Médico | F1 | RD (`birthdate` padrão) | RD | sincronia CRM→RD (EXT-08) | ✅ fora da área |
| A19 | Documentação pendente (7 d) | F2 | cadastro/formulário (`aguardando_biometria`) | RD-evento | status no `contact` (EXT-19) | 🔒 |
| A20 | Trilha parada (7 d) | F2 | `trilha_progresso` | RD-evento + app | — | 🔒 |

**Tabelas:** `comunicacao_evento` (gatilho ENUM A01..A20, contact, referência, canal sugerido,
`enviar_apos`, status pendente/enviado/suprimido/erro/falhou, tentativas, `rd_evento_id`; único
`(gatilho, contact_id, referencia_id)`), `comunicacao_envio` (append; entregue/aberto/clicado por retorno
do RD ou UTM), `comunicacao_supressao` (append; motivo), `notificacao`. Payload **sem CPF nem e-mail**
(o RD resolve por `cf_apm_contactid`). Webhook do RD = rota pública nova → só na F2 e com ADR (DEC-18).
**IDs:** TI-18, TI-19, TI-53, TI-55, TI-42, TI-11, TI-13 · EXT-08, EXT-33, EXT-35, EXT-24, EXT-25 · DEC-18,
DEC-19, DEC-20 · DIV-12, DIV-30, DIV-33.

---

## 8. Integrações (§13)

### 8.1 Mapa

| Integração | Spec | Existe hoje | Falta | Dono externo | Estado | Enquanto espera |
|---|---|---|---|---|---|---|
| Cadastro (CRM Dataverse via hub) · INT-01 | dados, categoria, filiação, regional, especialidade, situação, **avisos automáticos**; contrato F0-02 | IdP: claims `carteirinha`; hub: `perfil_consultar` (14 campos, por `contact_id`), escrita implementada e **desligada**; `associado.situacao`/`historico_associacao` existem mas não concedidas (histórico só por CPF); hub é **pull**, sem webhook | nome social, nascimento (faixa), especialidades, regional, histórico por `contact_id`, situação normalizada, isenção/remição, avisos | CRM admin; "novo cadastro" (DEC-17) | 🟡 | ampliar `perfil_consultar` (TI-48), jobs de diferença (TI-55), `hub_stub` com os campos |
| Cobrança (F&O via hub) · INT-02 | situação, mensalidades, **segunda via (PDF, linha digitável, Pix)**, pagamentos, aviso | `financeiro.faturas_associado` por CPF (fatura, vencimento, valor, liquidado, saldo, forma); **sem boleto/Pix/PDF**; ADR-0010 | `contact_id` (P-04), parecer (P-08), regra de situação, 2.ª via (fonte inexistente), aviso de pagamento, renovação | Financeiro, admin F&O; "novo sistema de cobrança" (EXT-24) | ⛔ | contrato `financeiro.situacao_consultar`/`faturas_listar` + stub (TI-49), rota 404 `recurso_desligado`, tela "cobrança indisponível → Central" (TI-57) |
| Login atual (IdP) | contas reaproveitadas (F0-03) | ✅ RP OIDC completo; IdP sem nascimento/celular/continuar conectado | backlog do IdP (TI-83) | TI | ✅ | — |
| API de consulta de associação | "já existe e está em uso" | **não há API JSON**: portal `apm-parceiros` (sessão), `access:validate` do IdP sem consumidor, `/verificar` HTML | nomear a API (DEC-10) | TI | ⚠️ DIV-06 | nada na área (regra 17) |
| RD Station | campos e eventos da régua (69 peças, 8 fluxos), leads, retorno por UTM | integrado no formulário de filiação (api_key, ligado) e no totalpass (OAuth2, outbox, desligado); campos `cf_apm_*` existem; **nada na área** | `app/integracoes/rdstation.py`, outbox, catálogo de gatilhos, consentimento, UTM | Marketing (app OAuth2, régua, campos) + Jurídico (base legal) | ⬜ | `RD_MODE=stub`, outbox grava e marca `suprimido: sem_credencial`, `scripts/check_rd.py` |
| Parceiros com API (tipo 2) | envio da solicitação e retorno por API | nada; ADR-0009 fecha HTTP a parceiro sem ADR própria; espelho CRM (`solicitacao.*` no hub) inexistente | lista de parceiros e contratos técnicos; ADR por parceiro | Benefícios + parceiro | 🔒 | tipo 2 sem API = solicitação local + espelho + canal `relatorio`/`email` (DEC-04) |
| Parceiros sem API (CSV §13.3) | CSV mensal por canal autenticado | nada; backoffice fora de escopo; CPF proibido na área | canal (DEC-05), parser/validador, `importacao*`, resolução CPF→`contact_id` **no hub**, lead (DEC-19) | Benefícios + parceiros | ⬜ · ⚠️ DIV-04 | parser puro com fixtures; `importar_csv` por arquivo em volume dos jobs (operador copia) |
| Qualicorp | F2: consulta de CPF, oportunidade, fechamento | só campo no RD e categoria em `apm-parceiros` | custo da API; ADR | Qualicorp + Benefícios | 🔒 F2 | tipo 2 sem API |
| Clube (Clube Certo) | F1 link; F2 SSO, ofertas, resgates | allowlist de link, flag `clube_economia`, ADR-0009 seed prevista | F2: SSO (IdP como provedor), API de resgates, contrato | fornecedor do clube | 🟡 F1 · 🔒 F2 | seed + clique rastreado |
| Eventos e IESAPM | inscrições, presença, certificados; CPF preenchido no site | nada; eventos pelo WordPress | mapa F0-01; contratos; **CPF no deep link: não** (DIV-28) | IESAPM / fornecedores | ⬜ | tipo 5 = interesse local + link em allowlist |
| WordPress, Portal MBE, biblioteca | notícias via "API do WordPress", acesso único | ADR-0006 (MySQL direto RO, só no job, cache); nada implementado; P-07, P-21; MBE/biblioteca sem fonte | `portal_wp.py`, `WP_*`, `sql/012`, serviço de jobs; MBE/biblioteca: fornecedor e SSO | Planeta W / Locaweb; fornecedores | ⬜ · DIV-29 | `WP_MODE=stub` com fixtures (P10/P11 inteiras sem a Locaweb) |
| WhatsApp (API oficial) e SMS | envios da régua "pelo RD ou direto"; OTP por celular | área só `wa.me`; IdP com Fortics desligado; **SMS não existe** | contrato (RD WhatsApp ou Fortics) | Marketing / Fortics | 🔒 na área (régua sai pelo RD) | `canal_preferido` no perfil |
| Analytics e painéis | eventos com propriedades comuns; ferramenta a definir (F0-06); "Clarity no portal" | `evento_uso` (36 ações, 8 emitidas); **nenhum script de terceiro cabe na CSP** | propriedades derivadas, UTM/gatilho, destino dos painéis | Marketing/Encantada (F0-06) | 🟡 · DIV-32 | `evento_uso` + views RO (DEC-16) |
| `mcp_hub` (plataforma) | — | ✅ transporte, escopos, grants exatos, cota/taxa por conta, auditoria por titular, escrita cercada; cliente da área com token em memória, erros tipados | ferramentas novas (TI-47..52), paginação `@odata.nextLink`, **conta própria de jobs** (120/min e 5.000 PII/dia são incompatíveis com varreduras) | mcp_hub (TI) + usuário (P-41) | ✅ base · ⛔ cota | — |
| SMTP transacional | A04/A06/códigos "saem do próprio sistema" | `email.py` STARTTLS, 2 textos, síncrono; stub em produção proibido; P-27 | credencial (SPF/DKIM), templates HTML (padrão do IdP), fila com recuo | TI/infra | 🟡 | stub |

### 8.2 Contrato de dados §13.2, campo a campo

| Campo | Fonte hoje | Falta | Dono |
|---|---|---|---|
| identificador estável | `contact_id` (IdP e hub) | — | — |
| CPF | só `cpf_mask` na sessão | **nunca entra** (ADR-0014); hub resolve | — |
| nome, e-mail, celular | IdP + hub | escrita existe, desligada (P-29) | CRM admin |
| nome social, nascimento | nada (hub `associado.consultar` lê nascimento, não concedida) | expor `faixa_carreira` derivada e `nome_social` em `perfil_consultar` (TI-48) | CRM admin / hub (EXT-19) |
| categoria atual, data de filiação | IdP + hub (rótulo) | código junto do rótulo (`associado.situacao` já tem) | hub |
| histórico de categorias | hub `historico_associacao` **só por CPF**, não concedida | versão por `contact_id` (TI-47); confirmar se `sol_associacao` registra categoria | hub + CRM admin |
| situação (ativo/suspenso/cancelado) | rótulo `alf_status_associativo` | enum fechado no hub; separar de `pendencia_financeira` (DEC-14) | hub + negócio |
| isenção/remição, especialidades, regional/distrital | nada (RD tem `cf_crm_contato_*` "Não Funcionando") | atributos do `contact` → `perfil_consultar` | CRM admin (EXT-19) |
| CRM e UF | IdP + hub ✓ | — | — |
| financeiro: situação, valor/forma, mensalidades, pagamentos | hub `faturas_associado` por CPF, não concedida | `contact_id` + regra de situação (TI-49) | P-04, P-08, Financeiro |
| segunda via (PDF, linha digitável, Pix) | **nada** (F&O via OData não expõe boleto) | fonte inexistente: só com o "novo sistema de cobrança" ou gateway | Financeiro (EXT-24) |
| avisos automáticos (6) | **nenhum** (hub pull; CRM→RD "Não Funcionando") | eventos do cadastro/cobrança ou webhook Dataverse → hub; substituto: jobs de diferença ≤ 24 h (TI-55) | CRM admin / F&O / novo sistema |
| escrita: contato pelo associado · pedido ao cadastro | `contato_atualizar` (desligada) · `task` (P-06) | ligar após P-29/M-3; `solicitacao.espelhar` (TI-50) | CRM admin |
| requisitos: homolog anonimizada, OpenAPI, < 1 s, aviso de manutenção | hub só produção; OpenAPI do hub existe | sandbox (EXT-22) | TI |

**"Novo sistema de cadastro e cobrança"** não aparece em nenhum dos sete repositórios (DEC-17). Em
qualquer hipótese (D365 + eventos; terceiro; reescrita do formulário de filiação) a área não muda: só o
conector do hub; o contrato `associado.*`/`financeiro.*` por `contact_id` é o ponto de estabilidade.

### 8.3 CSV do plano B (§13.3)

Layout e validação são TI (parser puro: UTF-8, `;`, 11 colunas, tipos, datas, valores, `id_externo`
único por parceiro, `observacao` ≤ 200 sem CPF). O que não é TI: chegada do arquivo até o dia 10 por
canal autenticado (EXT-15) e o canal em si (DEC-05: upload no backoffice na F1 → S3 presigned ou módulo
no `apm-parceiros` depois; nunca SFTP novo nem e-mail). **CPF só em memória no job**, resolvido no hub
(`importacao.resolver_lote`, TI-51) e descartado; `importacao_linha` persiste só `contact_id`/`sem_associado`;
lead de não associado vai ao RD/CRM, nunca à área (DEC-19). Confirmação = INSERT em `uso_valor` (nível 3;
nível 4 após validação do Financeiro) e fechamento de solicitações por `id_externo`. **IDs:** TI-54,
TI-51, TI-81 · EXT-15, EXT-10 · DEC-05, DEC-19 · DIV-04.

---

## 9. Requisitos não funcionais (§14)

| RNF | Spec | Hoje | Falta | Estado · IDs |
|---|---|---|---|---|
| Celular 360 px, alvos 44 px, Safari iOS e Chrome 2 últimas | — | e2e só Chromium 1440/390; `.botao` 42 px; `busca__limpar` 32 px; `100vh` | 360 px + WebKit no Playwright, alvos 44, `scroll-padding-bottom`, `100dvh` | 🟡 TI-62, TI-63 · DIV-38 |
| LCP < 2,5 s e INP < 200 ms (p75 celular) | — | nenhuma medição; animação de entrada com `opacity: 0` (risco de LCP), `backdrop-filter` (INP), 2 round-trips antes do dado, bundle único | Lighthouse no e2e com orçamento, `React.lazy` por rota, RUM próprio (`web-vitals` + `onerror` → `evento_uso`; indicador 14) | ⬜ TI-67 · DIV-38 |
| PWA instalável | manifest + ícone | nada; CSP tem `manifest-src 'self'`; `/area` é `no-store` com sessão e nonce por requisição | manifest + ícones 192/512 maskable servidos pelo FastAPI (sem SW); SW restrito (assets + offline, nunca `/area`/`/api`/foto/QR) só com push; `worker-src 'self'`; unregister no logout; lint contra `caches`/`indexedDB` | ⬜ TI-66 · DEC-07 · DIV-39 |
| Segurança (HTTPS, hash de senha, 2FA backoffice, limites, OWASP, segredos) | — | ✅ CSP sem inline, CSRF triplo, cookie cifrado, TLS no RDS, `limit_req`, container endurecido, segredos no `Settings`; **cert de origem vencido (P-01)**; `npm audit` com 2 avisos (P-40); sem CI | P-01; `navegarSeguro`/React Router 7; `pip-audit`/`npm audit` em CI; 2FA do backoffice (DEC-03) | 🟡 TI-70, TI-10, TI-77 · EXT-26 |
| LGPD (consentimento versionado, registro de acesso) | — | minimização ✓ | §6.4 | ⬜ TI-25, TI-26, TI-90 |
| Auditoria (log imutável) | solicitações e backoffice | ✅ por privilégio (`evento_log`/`evento_uso` só INSERT, CHECK); prova em PROVISIONAMENTO | `solicitacao_evento`, `backoffice_auditoria`; retenção com prazo | ✅/⬜ TI-14, TI-28 · EXT-16 |
| Acessibilidade WCAG **2.2** AA, texto ampliável, testes com associados | — | axe `wcag21aa` em 4 rotas; foco visível, skip link, foco preso, `aria-live`, reduced-motion, contraste `-texto` (P-22); tokens em **px**, base 14 px | axe `wcag22aa` em toda rota; 2.4.11 foco não obscurecido (barra inferior/FAB/toast), 2.5.8 alvos, 3.3.8 OTP colável (IdP); tokens em `rem` + `ControleFonte`; testes com associados (EXT-07) | 🟡 TI-63, TI-64 · EXT-06, EXT-07 · DIV-38 |
| Disponibilidade e monitoramento, backup diário com teste de restauração | — | 1 EC2, 1 RDS Single-AZ, cert vencido; healthcheck + `restart: always`; logs `json-file` 10m×3 (somem na recriação); **nenhum monitor externo desde 14/09**; RDS: retenção 7 d, PITR, snapshots diários, **zero teste de restauração**; `.env` no cofre desatualizado (P-36) | uptime externo, alertas (5xx, Traceback, `uso_falhas`, job com erro, cert < 30 d), runbook de restore ensaiado, snapshot manual antes de migração/cutover, SLO declarado, página de manutenção | 🟡 TI-75, TI-76, TI-73, TI-84 · EXT-27, EXT-28, EXT-29 · DEC-33 · DIV-21, DIV-40 |
| Ambientes dev / homolog anonimizada / prod; publicação automatizada | — | dev = container local stub; **homolog não existe** ("staging" é a produção pública no mesmo RDS/IdP/CRM); deploy manual por SSH sem CI/tag/rollback | homolog com RDS separado por snapshot quando a escrita no CRM chegar (DEC-30), hub stub/sandbox (EXT-22); CI (GitHub Actions) + `scripts/deploy.sh` pull-based com tag e rollback (DEC-31) | ⬜ TI-74, TI-77, TI-79 · EXT-30, EXT-22 · DIV-40 |
| Conteúdo editável sem publicação | — | nada (seed/migração) | backoffice (§4) | ⬜ DEC-03 |
| Chaves de funcionalidade | patrocínio, cartão, comunidade, tipos de ativação novos nascem desligados | ✅ ADR-0007 (8 flags) | flags novas: `notificacoes`, `encaminhamento_parceiro`, `reservas`, `inscricoes`, `comunicacao_outbox`, `cancelamento_online`, `lgpd_consentimentos` (adenda ADR-0007) | 🟡 TI-13 |
| OpenAPI | API documentada | só `APP_ENV=development`, 403 no edge | `openapi.json` gerado no build e versionado em `docs/api/`, modelos de resposta, `/docs` só na rede interna por flag; **nunca** em produção | 🟡 TI-07 · DEC-32 · DIV-09 |
| Identidade visual (Verdana, paleta #004165/#009581/#00675A/#616365) | — | Sora + paleta do mockup (ADR-0017, decisão do usuário); `#616365` não existe nos tokens; botão principal em gradiente navy (branco sobre `#009581` = 3,74) | divergência formal a levar ao Marketing/agência | ⚠️ DIV-34, DIV-37 · EXT-03 · DEC-25 |
| Fila 8h / horário 8h–20h locais | — | containers sem `TZ` (UTC) | `TZ=America/Sao_Paulo` nos serviços | ⬜ TI-78 · DIV-41 |

---

## 10. Divergências DIV-nn (spec v2 × decisões do usuário, ADRs e realidade)

Nenhuma reabre decisão: cada linha diz quem decide, o impacto e a recomendação. "🔒" = decisão do usuário
mantida; a divergência vai à agência/Marketing como registro.

| ID | Divergência | Quem decide | Impacto | Recomendação |
|---|---|---|---|---|
| DIV-01 | P01 descreve login (CPF+senha) "na Minha APM" × sem login próprio (`/` → Login APM, OIDC) 🔒 | usuário (decidido) | P01 inteiro vive no `login_associado`; `login` fica no IdP | manter; responder à agência que P01 = Login APM e listar o backlog do IdP (TI-83) |
| DIV-02 | Spec: "não confirma CPF antes de o nascimento conferir" × triagem do IdP distingue "fora do CRM → filiação" só pelo CPF (enumeração) | Sentinela + usuário | confirma vínculo associativo a quem tem o CPF | adotar a spec (mais estrita): nascimento antes de qualquer distinção de resposta (TI-83, EXT-19) |
| DIV-03 | Nascimento no 1.º acesso, OTP por celular/SMS, "continuar conectado", "meus dados mudaram", página de retorno do ex-associado × nada disso existe no IdP | TI (IdP) | expectativa da agência | backlog do IdP (TI-83); DEC-11, DEC-12; canal celular é contrato (EXT-35) |
| DIV-04 | CSV §13.3 com `cpf` obrigatório e lead com CPF × ADR-0014 (CPF nunca na área) 🔒 | usuário (decidido) + Benefícios | importação não pode ser rota da área | resolver no hub (TI-51, TI-54); layout mantém `cpf` para o parceiro; lead vai ao RD/CRM (DEC-19) |
| DIV-05 | P13 "pedir exclusão" × ADR-0004 (DELETE nunca) 🔒 | usuário + encarregado | exclusão ≠ apagamento | anonimização por coluna de estado + purga por retenção pelo operador (DEC-06, ADR candidata) |
| DIV-06 | §13.1 "API de consulta de associação já existe" × não há API JSON (portal `apm-parceiros`; `access:validate` sem consumidor) | TI | agência espera integração pronta | corrigir a spec; nomear a API (DEC-10); fora da área (regra 17) |
| DIV-07 | P07 validação pública mostra "categoria" × `/verificar` mostra só nome e situação | usuário + Sentinela | categoria numa página pública por token é dado a mais | manter sem categoria (DEC-36) |
| DIV-08 | Tipo 2 "envia os dados ao parceiro", tipos 1/6 "acesso único" × ADR-0009 (nenhuma chamada a parceiro, sem SSO) 🔒 | usuário (decidido) | tipo 2 = solicitação interna encaminhada pela APM; 1/6 = link rastreado | manter; SSO só com ADR por parceiro, com o `login_associado` como provedor (DEC-04, DEC-10) |
| DIV-09 | §14 "API documentada (OpenAPI)" × OpenAPI só em development e 403 no edge | Sentinela | documentação sem superfície | artefato versionado + `/docs` só na rede interna (TI-07, DEC-32) |
| DIV-10 | P15/§3.1 sino de notificações × ADR-0017 "sem sino até existir fonte" 🔒 | Vitrine + agência | só visual | API/tabela atrás de flag; sino só com fonte e aceite visual (DEC-08, EXT-02) |
| DIV-11 | B02 "busca por CPF" × ADR-0014 🔒 | usuário (decidido) | backoffice não busca por CPF na área | busca por nome/número/`contact_id`; CPF só no hub com grant (DEC-03) |
| DIV-12 | §12.1 "transacional sai do próprio sistema", inclusive cobrança × área só envia código de e-mail; ERP só leitura (ADR-0010) 🔒 | usuário | A04/A05/A06 exigem SMTP transacional da área; cobrança não é da área | reabrir escopo só para transacional por e-mail (mesmo `email.py`); cobrança pelo RD ou pelo sistema de cobrança |
| DIV-13 | P07 "consulta a situação no momento da leitura; cancelamento revoga" × cache de 24 h renovado só pelo associado | Sentinela + Integrador | cancelado "Ativo" por até 24 h; depois "não confirmada" para sempre | hub a cada leitura com cache curto + limite global + job noturno + `revogada_em` (TI-45, DEC-09) |
| DIV-14 | §11.2 propriedades pessoais em todo evento e termo de busca × RNF-16/ADR-0012 (minimização) 🔒 | usuário (decidido) + Atlas | | dimensões por junção; termo só em `busca_sem_resultado` sem identidade; valores só em `uso_valor` (DEC-34) |
| DIV-15 | 8 status + marcador × 6 estados (ADR-0003); `enviada` visível × "sync invisível" (RF-SO-06); atores | Maestro/Atlas + usuário | máquina de estados da Fase 3 | adotar os nomes da spec já na `sql/008`, `sem_retorno` como coluna, falha de espelho continua invisível (DEC-01; adenda à ADR-0003) |
| DIV-16 | "Conteúdo enviado" no log imutável × minimização | Atlas + Sentinela | PII replicada em trilha de guarda longa | campos + sha256 + destino (DEC-02) |
| DIV-17 | Backoffice B01–B13 na F1 × "fora de escopo" (REQUISITOS L112) | usuário (29/10: escopo novo) | maior lacuna do projeto | §4; DEC-03 antes de qualquer tela |
| DIV-18 | Catálogo editável sem desenvolvedor (B03/B13) × `beneficio` como seed só SELECT (REQ §6) | usuário + Atlas | REQ §6 desatualizado | catálogo como dado com `beneficio_versao` e UPDATE por `apm_area_bo` (TI-29, DEC-03); até lá, operador por SQL |
| DIV-19 | ADR-0004 §6 exige `db_check` falhar em tabela da allowlist sem grant; o código só checa o inverso e lista 9 tabelas inexistentes | Atlas | guarda frouxa | TI-03 |
| DIV-20 | Numeração: `job_execucao` em `sql/012` mas Fase 3; PENDENCIAS cita "sql/007 seed" | Atlas | confusão operacional | `job_execucao` = `sql/009`; corrigir PENDENCIAS (feito nesta rodada) e REQ (TI-06) |
| DIV-21 | "Backup diário com teste de restauração" × RDS automático 7 d sem teste; `.env` no cofre desatualizado (P-36) e 3 `.env.bak` no disco | operador | recuperação não comprovada | TI-76, TI-73; EXT-27, EXT-28 |
| DIV-22 | P12 trilha para toda categoria, por evento real, bloco da home × onboarding só Acadêmico, por clique, rota própria | Maestro/Vitrine | RF-ON-01/05 mudam | TI-43; DEC-21 |
| DIV-23 | P06 Meu valor é F1 × roteiro fase 8 atrás de `fatura_valor` forçada desligada (P-12) | usuário | a spec dá a fonte (solicitações concluídas + importações + proteção) | antecipar estrutura para a Fase 4; tirar da lista forçada quando `valor.py` existir; só "N vezes" fica sem fonte (TI-35, TI-36, DEC-23) |
| DIV-24 | Cancelamento pelo associado: REQ permite em `aberta`/`aguardando`; spec "enquanto o parceiro não atendeu" | Maestro | | `criada`, `enviada`, `pendente_associado`; nunca `em_atendimento` (DEC-01) |
| DIV-25 | Busca global no servidor com 5 fontes e sugestões × RF-SH-04 (cliente, sem gravar termo) | Maestro/Vitrine | | `GET /busca` (TI-37); termo só sem resultado (DEC-34) |
| DIV-26 | Tipos fechados de solicitação sem benefício × solicitação por benefício/tipo de ativação; ativação toggle × tipos 1–6 | Maestro | REQ §7.4 e RF-BE-07/08 mudam | `beneficio_id` + `tipo_servico`; toggle só tipo 1 (TI-14, TI-31) |
| DIV-27 | P14 FAQ/cancelamento sem fase no roteiro | Maestro | | Fase 3 (dois tipos de solicitação + FAQ) |
| DIV-28 | P10 inscrição "com CPF já preenchido" no site do congresso × ADR-0014 e vazamento por querystring 🔒 | usuário | | não fazer; site do congresso como RP do IdP ou o associado digita lá (EXT-13) |
| DIV-29 | §13.1 notícias via "API do WordPress" (e o hub sugere REST) × ADR-0006 MySQL direto no job 🔒 | usuário (decidido) | | manter ADR-0006; fechamento da 3306 da Locaweb depende de P-07/P-16 |
| DIV-30 | Avisos automáticos do cadastro/cobrança em tempo real × hub é pull sem webhook | CRM admin / hub | A01/A09/A13 com atraso | jobs de diferença ≤ 24 h (TI-55); evento do cadastro quando existir (EXT-24) |
| DIV-31 | "Suspenso" por atraso financeiro × "suspenso" cadastral do CRM | Maestro/Integrador | dois conceitos com um nome | `situacao_cadastral` × `pendencia_financeira` na API (DEC-14) |
| DIV-32 | Analytics "ferramenta a definir", "Clarity no portal", indicador 14 (LCP/JS) × CSP `script-src 'self'` (ADR-0013) 🔒 | usuário (decidido) | | nenhum script de terceiro; RUM próprio em `evento_uso` (TI-67); painéis internos (DEC-16) |
| DIV-33 | WhatsApp "pelo RD ou direto" × nada direto; Fortics no IdP | Marketing | | régua pelo RD; OTP é do IdP; a área não integra WhatsApp |
| DIV-34 | §14 Verdana + `#616365` × Sora + paleta do mockup (ADR-0017) 🔒 | usuário (decidido) | identidade | manter; levar ao Marketing como divergência formal (EXT-03) |
| DIV-35 | Navegação §3.1 (barra Início/Benefícios/Carteirinha/Meu valor/Mais; itens Financeiro, Ajuda; nomes "Meu valor", "Perfil e privacidade", "Eventos") × rotas atuais ("Fatura de valor", "Meu perfil", Clube/Notícias na barra, sem Financeiro/Ajuda) | Vitrine + usuário | shell | TI-60 após DEC-24 |
| DIV-36 | "Nada de em breve" × `EmConstrucao`/"a caminho" | Vitrine | | aceito na construção (ADR-0017 §3); some no cutover (DEC-24) |
| DIV-37 | Botão principal verde `#009581` × gradiente navy do mockup; branco sobre `#009581` = 3,74 (P-22) | Vitrine + agência | | manter mockup (DEC-25); registrar |
| DIV-38 | WCAG 2.2 × RNF-10 2.1; 360 px/Safari × e2e 390 Chromium; alvos 44 × 42 px; fonte ajustável × px | Vitrine | | TI-62, TI-63, TI-64; REQ v0.2 |
| DIV-39 | PWA × `/area` `no-store` com sessão e nonce; RNF-21 | Sentinela/Vitrine | SW não pode cachear HTML nem `/api` | manifest-only; SW restrito só com push (DEC-07) |
| DIV-40 | Ambientes dev/homolog/prod, publicação automatizada, alertas × um host, "staging" = produção pública, deploy manual, só healthcheck | Estivador + operador | | DEC-30, DEC-31; TI-74, TI-75, TI-77, TI-79 |
| DIV-41 | Fila 8h e horário 8h–20h locais × containers sem `TZ` | Estivador | | TI-78 |
| DIV-42 | CLAUDE.md/REQUISITOS citam jobs, `WP_MODE`, `docs/JOBS.md` × nada existe no código | docs | leitor pensa que existe | marcadores [alvo] já corrigidos no CLAUDE.md; `docs/JOBS.md` nasce com TI-01 |
| DIV-43 | Marca no topo fixo × marca só no trilho/drawer; cabeçalho não fixo (mockup) | Vitrine | | manter mockup; registrar |
| DIV-44 | Comunidade (F3) e Onboarding visíveis no menu antes da fase | Vitrine | | DEC-24 |
| DIV-45 | Carteirinha sem número de associado × spec pede | Vitrine | | TI-46 |
| DIV-46 | P-41 estimou consumo do hub só pelo web × jobs (perfis diários, CSV em lote) mudam a cota | Integrador/Estivador | | conta própria de jobs (TI-51); resposta à P-41 refeita |
| DIV-47 | Rótulos de status da spec §8.5 (7 rótulos) × rótulos do App APM em tudo que está no CRM ("Aberta", "A Central aguarda seu retorno", "Aguardando a APM"…) | Vitrine/Maestro | o associado vê dois vocabulários: o da spec enquanto o pedido não chegou ao CRM e o do App depois | decisão do William em 13/11 (ADR-0024): mesmo texto nos dois canais; P-80 para os três rótulos ainda provisórios |
| DIV-48 | Spec/ADR-0018: "responder" em `pendente_associado` e cancelar pela área × com o pedido no CRM a resposta é a **conversa** (Timeline, comum ao App) e o cancelamento segue com a Central | Maestro/Integrador | `POST …/responder` só vale antes do espelho; não há cancelamento pelo associado depois do envio (P-74) | ADR-0024; cancelamento depende de ferramenta de status no hub |
| DIV-49 | App: um registro aberto por slug × área traduz declaração, cancelamento da associação e o formulário da Ajuda para `outros` (e o formulário da Ajuda não tem unicidade, só teto de 5/24 h) | Maestro | enquanto houver um desses aberto na Minha APM, o App recusa "Outros assuntos"; o inverso não bloqueia nada na área | aceito pelo William em 13/11 (adenda da ADR-0024); rever se a Central reclamar |

## 11. Decisões pendentes DEC-nn

| ID | Decisão | Opções (resumo) | Recomendação | Quem decide | Bloqueia |
|---|---|---|---|---|---|
| DEC-01 | Máquina de estados: 8 status da spec já na `sql/008`; `enviada` promovida por confirmação do canal; `sem_retorno` como coluna | (a) 6 + tradução na API · (b) 8 no banco + marcador · (c) 8 + status `sem_retorno` | **(b)**; adenda à ADR-0003 (mantém outbox, otimista, 409) | usuário + Maestro/Atlas | Fase 3 — **decidida em 2026-10-30 (ADR-0018)** |
| DEC-02 | "Conteúdo enviado" no log | (a) JSON completo · (b) campos + sha256 + destino/canal · (c) cifrado | **(b)** | Atlas/Sentinela | Fase 3 — **decidida em 2026-10-30 (ADR-0018)** |
| DEC-03 | Onde vive o backoffice e como autentica; quem tem UPDATE no catálogo | (a) app separado com Entra ID · (b) dentro da área com `login_associado` · (c) portal do `mcp_hub` · hospedagem: mesmo container `/admin` / container próprio + host próprio / + Cloudflare Access | **container próprio na mesma imagem, host próprio, Cloudflare Access + Entra ID (OIDC), usuário de banco `apm_area_bo`, trilhas só INSERT; visão 360/importação de leitura no portal do hub; nunca (b)** | usuário + diretoria (IdP corporativo) | §4 inteiro, B06, catálogo editável — **parte de banco decidida em 2026-10-30 (ADR-0022: `apm_area_bo` + `apm_area_painel`); hospedagem e identidade na Onda 6** |
| DEC-04 | Tipo 2 na F1 sem integração; enviar dados ao parceiro por e-mail? | (a) solicitação com canal `relatorio`/`email` operada pela APM (sim) · e-mail ao parceiro × parceiro consulta no `apm-parceiros` | **solicitação local sim; dados ao parceiro só com allowlist por benefício e aprovação do DPO; alvo = consulta no `apm-parceiros`** | usuário + DPO + Benefícios | tipo 2 na Fase 4 — **decidida em 2026-10-30 (ADR-0018)** |
| DEC-05 | Canal do CSV plano B | (a) upload no backoffice (parceiro entrega por canal corporativo) · (b) S3 presigned · (c) SFTP · (d) módulo no `apm-parceiros` | **(a) na F1 (até lá, operador copia para o volume dos jobs); (b) ou (d) depois; nunca (c) nem e-mail; CPF resolvido no hub** | usuário + Benefícios | B06 |
| DEC-06 | Exclusão de dados | anonimização por coluna × apagamento físico | **anonimização + purga por retenção pelo operador; `evento_log` fica (HMAC)**; ADR candidata | usuário + encarregado | P13 LGPD |
| DEC-07 | PWA | manifest-only · + SW restrito · + offline | **manifest-only no cutover; SW só com push; nunca cache de `/area`, `/api`, foto, QR** | Sentinela/Vitrine/Estivador | RNF |
| DEC-08 | Notificações | in-app · e-mail transacional · Web Push · sino | **in-app + e-mail; push só com consentimento, SW restrito e ADR; sino só com aceite visual** | usuário + agência | P15 (F2) |
| DEC-09 | Revogação da carteirinha | hub a cada leitura com cache curto · job noturno · ambos | **ambos: cache 5–15 min + limite global + job + `revogada_em`** | Sentinela/Maestro | P07 |
| DEC-10 | "API de consulta de associação" | `access:validate` do IdP · hub `associado.situacao` com grupo `parceiros` (`ativo: bool`) · só o portal | **hub com resposta mínima; `access:validate` para RPs internos; ADR por parceiro** | usuário | DIV-06 |
| DEC-11 | Página de retorno do ex-associado | estática no IdP após triagem `INACTIVE` · sessão restrita na área | **estática no IdP** | usuário | P01 |
| DEC-12 | "Continuar conectado" | cookie persistente no IdP (30/90 d, `auth_time` original) · não oferecer | **cookie persistente no IdP; área inalterada (step-up por `idp_at`)** | usuário | P01 |
| DEC-13 | Limites por associado entre workers | contagem no banco para tetos diários + memória por minuto · Redis · tabela para tudo | **contagem no banco; operações sensíveis por unicidade + step-up; sem Redis** | Maestro/Sentinela | Fase 3 — **decidida em 2026-10-30 (ADR-0020)** |
| DEC-14 | Situação financeira sem ERP | `financeiro=None` ⇒ permite · bloquear | **permite, documentado em "como calculamos"; "Suspenso" só com fonte; separar cadastral × financeira** | usuário | Fase 4 |
| DEC-15 | Base da carência | `data_filiacao` · início da categoria atual | **`data_filiacao` + `parametro.carencia_reinicia_por_categoria=false`** | Benefícios (EXT-11) | Fase 4 |
| DEC-16 | Destino dos eventos e painéis (F0-06) | views + página do backoffice · views + ferramenta interna (Metabase/portal do hub) com `apm_area_painel` · analytics externo (Clarity/GA) | **views + ferramenta interna; nunca `contact_id` a terceiro; export agregado k ≥ 20** | usuário + Marketing | B12 |
| DEC-17 | "Novo sistema de cadastro e cobrança" | D365 + eventos no hub · terceiro · reescrita do formulário | **premissa D365 + hub; contrato por `contact_id` atrás do hub; 2.ª via só quando a fonte existir** | diretoria/Financeiro/TI (EXT-24) | P08, A09, A10 |
| DEC-18 | Divisão com o RD | área emite, RD orquestra · área mantém janela | **área emite campos/eventos + supressão por campos; limite e régua no RD; webhooks de retorno só F2 por export** | Marketing + TI | §7 |
| DEC-19 | Lead de não associado | RD (sem CPF) · CRM via hub · formulário de filiação | **F1: RD sem CPF; alvo: CRM via hub** | Benefícios/Sentinela | B05, A17 |
| DEC-20 | Fonte de A01/A02 | evento do IdP · `diff_cadastro` · formulário | **`diff_cadastro` (A01) + `primeiro_acesso_em` (A02)** | Integrador | §7 |
| DEC-21 | Trilha: início dos 90 dias e público | `data_filiacao` · `primeiro_acesso_em`; todas as categorias | **`data_filiacao`, todas as categorias, bloco da home** | usuário | P12 |
| DEC-22 | Avaliação 0–10 | colunas em `solicitacao` + prazo · tabela própria | **colunas, prazo 30 d** | Maestro | Fase 3 — **decidida em 2026-10-30 (ADR-0018)** |
| DEC-23 | Flag `fatura_valor` | manter chave e trocar rótulo · chave nova | **manter chave; rótulo "Meu valor"; sair das forçadas quando `valor.py` existir** | usuário | P06 |
| DEC-24 | Navegação com fontes ausentes | barra com 4 abas até existir Meu valor · rotas sem página somem no cutover · Comunidade/Onboarding fora do menu antes da fase | **sim aos três** | usuário + Vitrine | shell |
| DEC-25 | Cor do botão principal | gradiente navy (mockup) · verde `#009581` ajustado | **mockup (ADR-0017); registrar para a agência** | usuário | — |
| DEC-26 | Tratamento Dr./Dra. | campo "como prefere ser chamado" com padrão neutro · gênero do CRM | **campo no perfil; até lá "Olá, Nome"** | negócio | P02/P13 |
| DEC-27 | Persistência do tamanho de fonte | servidor (perfil declarado) · exceção de `localStorage` · só zoom | **servidor quando P13 existir; até lá `rem` + zoom** | Vitrine/Sentinela | RNF |
| DEC-28 | React Router 7 (P-40) | migrar antes da Fase 3 · bloquear `\` e migrar depois | **migrar antes (custo cresce por tela)** | Vitrine/Sentinela | Fase 3 — **decidida em 2026-10-30 (Onda 2 (tarefa TI-10))** |
| DEC-29 | Agendador dos jobs | loop in-process · `crond` na imagem · crontab do host | **loop in-process + `GET_LOCK` + `job_execucao` + `JOBS_APLICAR` (dry-run)**; ADR | Estivador | TI-01 — **decidida em 2026-10-30 (ADR-0019)** |
| DEC-30 | Homologação | mesmo RDS schema `_hml` · RDS separado por snapshot · não criar | **RDS separado quando a escrita no CRM chegar; até lá "staging" em leitura** | operador | antes de `HUB_ESCRITA_HABILITADA=true` |
| DEC-31 | Deploy | CI valida + deploy pull-based no host · Actions por SSH · runner self-hosted | **pull-based** | operador | CI |
| DEC-32 | OpenAPI | artefato versionado · `/docs` por flag na rede interna · portal | **artefato + flag interna; nunca em produção** | Sentinela/Maestro | RNF |
| DEC-33 | SLO e retenção de backup | SLO 99,5 % Single-AZ · Multi-AZ; 7/14/35 d | **99,5 % declarado; 14 d + snapshot pré-migração/cutover** | operador | RNF |
| DEC-34 | Termo de busca | não gravar · só sem resultado, normalizado, sem identidade, tabela própria | **só sem resultado, sem identidade; purga por retenção** | Sentinela/Atlas | P03 |
| DEC-35 | Vocabulário dos 6 estados e 7 status na UI | textos da spec como proposta · aguardar Marketing | **textos da spec até o aceite (EXT-05)** | Marketing | P03/P05 |
| DEC-36 | Dados da verificação pública | manter nome + situação · + categoria | **manter sem categoria** | Sentinela | P07 |

## 12. LISTA TI — tarefas que a TI executa sem depender de terceiro

Colunas: camada · persona · repo (`area` = este repositório, `hub` = `mcp_hub`, `idp` = `login_associado`,
`infra` = host/porteiro/AWS) · F da spec · fase do roteiro · tamanho (P ≤ 1 d, M 2–5 d, G > 1 sem.) ·
pré-requisito interno · **hoje?** (sim = pode começar sem decisão nem terceiro; "DEC-nn" = espera decisão;
"TI-nn" = espera outra tarefa). Itens que citam EXT no pré-requisito só o fazem para a versão **real**; a
versão com stub/flag começa hoje.

### 12.1 Base transversal (podem começar agora)

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-01 | Serviço `area-associado-jobs` no compose (mesma imagem, `python -m app.jobs`, sem expose, 256M, `read_only`, tmpfs com `size`, `cap_drop`, `pids_limit`, `TZ`, `env_file .env.jobs`, profile `jobs`, heartbeat + healthcheck) + `app/jobs/` (loop in-process, `GET_LOCK` por job, `job_execucao` `sql/009`, `JOBS_APLICAR` dry-run, SIGTERM) + `docs/JOBS.md` | jobs/infra | Estivador + Integrador | area | F1 | 3 | G | DEC-29 (recomendada) | sim (esqueleto com profile desligado) → **✅ 30/10 (serviço em dry-run; profile `jobs`)** |
| TI-02 | Migração `ALTER` em `evento_uso` e `evento_log`: PK `(id, ocorrido_em)` + `PARTITION BY RANGE` mensal (24 partições + MAXVALUE), procedimento para partições futuras; ensaio em MySQL 8.4 | SQL | Atlas | area | F0 | agora | P | — | sim → **✅ 30/10 (migração `sql/008` ensaiada; aplicação pelo operador)** |
| TI-03 | `scripts/db_check.py`: falhar quando tabela da allowlist existe sem grant (ADR-0004 §6); allowlist só com tabelas migradas; suporte a usuários `apm_area_bo` e `apm_area_painel`; conferir partição | scripts | Atlas | area | F0 | agora | P | — | sim → **✅ 30/10** |
| TI-04 | Catálogo de `evento_uso` ampliado (§6.2): ações novas, `detalhes` tipados (`origem`, `estado`, `blocos`, `tema`, `nota`, métricas), retirar `fatura_pdf_baixar`, propriedades derivadas sem PII, teste `AcaoUi` = `ACOES_UI` | dominio/front | Atlas + Maestro + Vitrine | area | F1 | 3+ | M | — | sim (ações da Fase 3; o resto por tela) → **✅ parcial 30/10 (51 ações; o resto por tela)** |
| TI-05 | `acesso_primeiro` emitido em `associado.registrar_acesso` (upsert insere) com `dias_desde_filiacao` | dominio | Sentinela | area | F1 | agora | P | — | sim → **✅ 30/10** |
| TI-06 | REQUISITOS v0.2: §6–§8 com 8 status, catálogo como dado, `uso_valor`, consentimento, comunicação, renumeração `sql/008+`, WCAG 2.2, fases × F; `crm_sync` 3×4 valores | docs | Maestro + Atlas | area | F0 | agora | M | este levantamento | sim → **✅ 30/10 (REQUISITOS v0.2)** |
| TI-07 | OpenAPI como artefato: `scripts/openapi_export.py` → `docs/api/openapi.json` no build, modelos Pydantic de resposta, `operation_id` estável, teste de diff; 403 no edge mantido | API/build | Maestro + Sentinela | area | F1 | agora | P | DEC-32 (recomendada) | sim → **✅ 30/10** |
| TI-08 | Limites de negócio por contagem no banco (tetos diários) + zonas nginx novas por rota (`area_privacidade`, `area_solicitacoes`) + unicidade no banco para pedidos sensíveis | API/infra | Maestro + Sentinela | area | F1 | 3+ | P | DEC-13 (recomendada) | junto de cada rota → **✅ 30/10 (ADR-0020; zonas no vhost de exemplo)** |
| TI-09 | Dependência `exigir_reautenticacao` reutilizável (403 `reautenticacao_necessaria`) aplicada a cancelamento, exclusão, exportação, canais; `PUT /perfil/contato` exige step-up para celular quando o IdP ligar OTP por celular | API | Sentinela | area | F1 | 3 | P | — | sim → **✅ 30/10 (`CELULAR_EXIGE_REAUTH` desligada)** |
| TI-10 | P-40: `lib/navegacao.ts` com `navegarSeguro()` + regra ESLint; migrar para React Router 7 antes das telas da Fase 3 | front | Vitrine + Sentinela | area | F1 | 3 | M | DEC-28 (recomendada) | sim → **✅ 30/10 (react-router 7.18.4; P-40 resolvida)** |
| TI-11 | Catálogo de parâmetros de campanha (`utm_*`, `g=A01..A20`) lido uma vez no boot, validado, removido da URL, anexado a `pagina_ver`/`beneficio_abrir`; validação no servidor; testes de `safe_next` com query | front/uso | Sentinela + Vitrine | area | F1 | 4 | P | catálogo provisório (EXT-08 para o real) | sim → **✅ 30/10 (catálogo provisório)** |
| TI-12 | Runbook de segredos e rotação (`SESSION_ENC_KEYS` MultiFernet, `CARTEIRINHA_HMAC_KEY` → regenerar tokens, chaves novas); `scripts/env_check.sh` (hash do `.env` × cofre) | docs/config | Sentinela + Estivador | area | F1 | agora | P | P-36 antes | sim → **✅ 30/10 (`OPERACAO.md` §8)** |
| TI-13 | Flags novas no enum + seed desligadas + `tipos.ts` + PROVISIONAMENTO: `notificacoes`, `encaminhamento_parceiro`, `reservas`, `inscricoes`, `comunicacao_outbox`, `cancelamento_online`, `lgpd_consentimentos`; adenda à ADR-0007; rótulo de `fatura_valor` | config/SQL | Maestro | area | F1 | 3 | P | — | sim → **✅ 30/10 (`sql/009`; aplicação pelo operador)** |

### 12.2 Fase 3 — solicitações, P05, P14, comunicação produzida

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-14 | `sql/008`: `solicitacao` (8 status, `beneficio_id`, `parceiro_id`, `tipo_ativacao`, `tipo_servico`, `canal_envio`, `prazo_retorno_dias`, `enviada_em`, `sem_retorno_desde`, `responsavel`, `resultado`, `avaliacao_*`, `chave_idempotencia`, `crm_*`) + `solicitacao_evento` (ator, origem, justificativa obrigatória quando backoffice, `conteudo_enviado` = campos + sha256, CHECK anti-CPF) + índices; GRANT UPDATE justificado; allowlist | SQL | Atlas | area | F1 | 3 | M | DEC-01, DEC-02 | após decisão (1 dia) → **✅ 30/10 (`sql/010`)** |
| TI-15 | `app/dominio/solicitacoes/`: `maquina.py` (transições puras + `transitar()` com UPDATE condicional), `schemas/` por tipo com allowlist de campos (`beneficio.sigiloso` ⇒ `dados={}`), `avaliacao.py` | dominio | Maestro + Sentinela | area | F1 | 3 | M | TI-14 | sim (contrato) → **✅ 30/10** |
| TI-16 | API `/api/v1/solicitacoes` (listar com cursor, detalhe + linha do tempo, criar, cancelar, responder, avaliar) + `solicitacoes_aguardando` real em `/sessao` + ações `solicitacao_avaliar`, `cancelamento_pedir` | API | Maestro | area | F1 | 3 | M | TI-15 | sim → **✅ 30/10** |
| TI-17 | Jobs da Fase 3: `espelhar` (outbox CRM; `HUB_MODE=stub` até P-06), `sincronizar` (cursor), `marcar_sem_retorno` (A05; 2.º vencimento → fila), `carencia_vencida` pronta para a Fase 4 | jobs | Integrador | area | F1 | 3 | M | TI-01, TI-14 | sim (stub) → **✅ 30/10 (espelho/sync em dry-run até P-06)** |
| TI-18 | Outbox de comunicação: `sql/014` `comunicacao_evento`/`comunicacao_envio`/`comunicacao_supressao` + `notificacao`, produzidas na transação do negócio (A04, A05, A06, A16; A03 na 4); catálogo fechado de gatilhos; job `enviar_comunicacao` desligado por flag; supressões (pendência financeira, solicitado há 14 d, cancelamento) | SQL/dominio/jobs | Atlas + Maestro + Integrador | area | F1 | 3 | M | TI-14, TI-01 | sim (produção; envio ⛔) → **✅ 30/10 (`sql/012`; envio RD na Onda 3)** |
| TI-19 | Transacionais A04/A05/A06: templates texto + HTML (padrão do IdP), token HMAC de avaliação, fila SMTP com recuo (hoje síncrono), `List-Unsubscribe` não se aplica | integração | Integrador | area | F1 | 3 | P–M | P-27 para produção | sim (stub) → **✅ 30/10 (textos A04/A05/A06/A16; envio real com P-27)** |
| TI-20 | P14: tabela `faq`, `GET /ajuda/faq?q=`, `GET /ajuda/contato` (horário/canais de `parametro`), `POST /ajuda/formulario` (= `outro`), `POST /ajuda/cancelamento` (= `cancelamento_associacao`: motivo ENUM, step-up + confirmação por e-mail + janela de arrependimento, 1 aberto, nunca altera o CRM) + evento + outbox A16 | SQL/API | Maestro + Sentinela | area | F1 | 3 | M | TI-15, TI-09 | sim → **✅ 30/10 (`sql/013`)** |
| TI-21 | Front P05: lista, detalhe (sub-rota), `LinhaDoTempo`, `StatusSolicitacao` (7 rótulos), cancelar, responder, `Avaliacao` 0–10; emissores `solicitacao_*`; testes | front | Vitrine | area | F1 | 3 | G | contrato de `tipos.ts` com TI-16; DEC-35 (textos provisórios) | contrato primeiro → **✅ 30/10** |
| TI-22 | Front P14: rota `ajuda`, `BuscaFaq` + `Accordion`, canais com horário (`tel:` na allowlist de esquemas), pedidos comuns, `FormularioCancelamento` | front | Vitrine | area | F1 | 3 | M | TI-20 | esqueleto sim → **✅ 30/10** |
| TI-23 | Sub-rotas no shell (`/beneficios/{slug}`, `/solicitacoes/{uuid}`, `/eventos/{id}`): `h1` vindo da página, `pagina_ver` com id truncado, `rotaDoCaminho` por prefixo | front | Vitrine | area | F1 | 3 | P | — | sim → **✅ 30/10** |
| TI-24 | Tipo 2 sem API: `canal_envio` `relatorio`/`email`, `enviada` por confirmação, prazo/canal no catálogo; e-mail ao parceiro só com allowlist por benefício e aprovação do DPO | dominio | Integrador + Maestro | area | F1 | 4 | P | DEC-04 | após DEC |

### 12.3 Fase 3b — P13: preferências, consentimentos, direitos do titular

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-25 | `sql/013`: `consentimento_texto` + `consentimento` (append-only, `vw_consentimento_atual`), `preferencia_canal`, `perfil_declarado` (tratamento, atuação, temas, região), `pergunta_perfil`, `titular_pedido`, colunas `anonimizado_em`/`desativado_em` | SQL | Atlas + Sentinela | area | F1 | 3b | M | textos do jurídico só para o conteúdo (EXT-16); estrutura não | sim (atrás de `lgpd_consentimentos`) |
| TI-26 | Domínio + API de P13: preferências (`GET/PUT`), pergunta por visita (`GET /perfil/pergunta`, `POST .../{chave}`), consentimentos (versão obrigatória; `409 versao_desatualizada`), exportação (`POST`, step-up, 1/7 d, JSON síncrono dos dados da área), exclusão (pedido + protocolo + confirmação; anonimização por job após o encarregado concluir; sem DELETE) + eventos `consentimento_alterar`, `perfil_declarado_atualizar` + zona `limit_req` | dominio/API | Maestro + Sentinela | area | F1 | 3b | G | TI-25, TI-09, TI-01 | sim |
| TI-27 | Front P13 extensão: tratamento, atuação, interesses, canais (WhatsApp/SMS só quando existirem: regra 19), consentimentos (switch com versão e histórico), baixar dados, pedir exclusão (`Dialogo` + `reauth`), "complete seu perfil", `PerguntaPerfil` (reusado no bloco 3); título "Perfil e privacidade" | front | Vitrine | area | F1 | 3b | G | TI-26 | após API |
| TI-28 | `docs/RETENCAO.md` (tabela × prazo × mecanismo: partição / anonimização / nunca) + `scripts/retencao.sql` do operador + procedimento de anonimização do titular (script administrativo fora do `apm_area`); fecha P-15 quando os prazos chegarem | docs/SQL | Atlas + Sentinela | area | F0 | 3b | P | prazos (EXT-16) para fechar | rascunho sim |

### 12.4 Fase 4 — catálogo, elegibilidade, home, Meu valor, trilha

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-29 | `sql/010` catálogo como dado: `parceiro`, `beneficio_categoria`, `beneficio` (ficha B03 completa: elegibilidade, tipo, destino, prazo, selos, vigência, status rascunho/aprovado/publicado, `modalidade_mensuracao`, `sigiloso`, `patrocinado`), `beneficio_versao`, `beneficio_faq`, `beneficio_categoria_associado`, `beneficio_afinidade`, `beneficio_ativacao`, `recomendacao_dispensa`, `recomendacao_exposicao`, `parametro`, `associado_categoria_hist`, `ALTER associado_perfil` (faixa, especialidade, regional, nome social, isenção), `perfil_declarado`, `destaque_editorial`, `texto_sistema`; `url_acesso` validada + `parceiro.host`; UPDATE de catálogo só para `apm_area_bo` | SQL | Atlas + Sentinela | area | F1 | 4 | G | DEC-03 (quem faz UPDATE), DEC-15; catálogo validado (EXT-10) só para o seed real | rascunho sim; aplicar com catálogo |
| TI-30 | `app/dominio/elegibilidade.py` puro (6 estados; ordem vigência → categoria → região → financeiro → carência → ativo; `financeiro=None` ⇒ permite) + `parametro` com cache + testes de tabela | dominio | Maestro | area | F1 | 4 | M | DEC-14 (recomendada) | sim |
| TI-31 | `app/dominio/ativacao.py` (estratégia por tipo 1–6) + `GET /beneficios?filtro=&categoria=&q=` (estado, `libera_em`, resumo) + `GET /beneficios/{slug}` (ficha, elegibilidade, `aproveitado_ano`, FAQ, relacionados; `beneficio_abrir` com `origem`) + `POST .../ativar\|desativar` (`409 nao_elegivel`; tipos 1 e 3 na F1; 2 após DEC-04; 4/5/6 atrás de flag) | dominio/API | Maestro | area | F1 | 4 | G | TI-29, TI-30, TI-15 | parcial (tipos 1 e 3) |
| TI-32 | Redirecionador `GET /api/v1/ir/{slug}` (sessão; 302 só do seed; `beneficio_acessar`/`clube_acesso` origem servidor; `no-store`) + validação de `url_acesso`/`parceiro.host` na migração + `links.ts` reduzido (UI sem hosts) | API/SQL/front | Sentinela + Maestro + Vitrine | area | F1 | 4 | M | TI-29; DEC-10 (recomendada) | junto da Fase 4 |
| TI-33 | `app/dominio/recomendacao.py` v1 (pontuação §7.3, exclusões, desempate, diversidade, rotação, `motivos[]`) + `POST /recomendacoes/{slug}/dispensar` + sinais de `evento_uso` | dominio/API | Maestro | area | F1 | 4 | M | TI-29, TI-30 | sim (afinidade por categoria; fase de carreira após TI-48) |
| TI-34 | `app/dominio/inicio.py` + `GET /inicio` por blocos (só com conteúdo; ordem do servidor; `avisos[]` por fonte fora) + `destaque_editorial` (ADM-05; `UNIQUE` segmento × vigência) + `home_vista(blocos)`, `home_bloco_clicar` | dominio/API | Maestro | area | F1 | 4 | M | TI-30, TI-33, TI-43 | sim (blocos disponíveis) |
| TI-35 | `sql/011` valor: `valor_referencia` (append, aprovação), `uso_valor` (append, níveis 1–4, estorno/validação por linha, CHECKs), `vw_meu_valor_ano`; **antecipada da Fase 8** | SQL | Atlas | area | F1 | 4 | M | TI-29 | sim (estrutura) |
| TI-36 | `app/dominio/valor.py` (só nível 4 soma; proteção proporcional; modos relação / valor entregue / o que cobre; "N vezes" só com total pago) + `GET /valor?periodo=` + `GET /valor/pdf` + `meu_valor_visto(periodo)`; retirar `fatura_valor` de `FLAGS_FORCAR_DESLIGADAS` quando houver `valor_referencia` aprovada; rota `/area/meu-valor` | dominio/API/front | Maestro + Vitrine | area | F1 | 4 | M | TI-35, TI-16, TI-31; DEC-23 | sim, atrás da flag |
| TI-37 | Busca global no servidor `GET /busca?q=&limite=` (benefícios, parceiros, eventos, notícias, FAQ; sugestões = `limite=5`; 30/min) + `busca_sem_resultado` (sem identidade, normalizado ≤ 48) + `Combobox` acessível no shell + `busca_global` emitido | API/front | Maestro + Vitrine + Sentinela | area | F1 | 4 | M | TI-20, TI-29; DEC-34 | após TI-20/TI-31 |
| TI-38 | Front P03: `BarraResumo` (some sem fonte), `FiltroChips`, `GradeCategorias` (8 ícones novos), `CardBeneficio` (6 estados, selos com texto), vazio com sugestão de categorias, 503 com "tentar novamente"; emissores `filtro_aplicar`, `categoria_abrir`, `beneficio_abrir` | front | Vitrine | area | F1 | 4 | G | TI-31; DEC-35 | após API |
| TI-39 | Front P04: `/beneficios/{slug}`, `SeloEstado`, `BotaoAtivacao` por tipo (1 via `/ir`, 2/3 `Dialogo` com prazo e próximo passo), `Accordion` (FAQ/regras/como funciona), "aproveitado no ano" só com fonte, relacionados, estados exclusivo/regularize/libera em | front | Vitrine | area | F1 | 4 | G | TI-31, TI-32, TI-23 | após API |
| TI-40 | Front P02 home em blocos: `BlocoHome`, `CardPendencia`, `CardMeuValor` (variantes), `CardProximoPasso`/`PerguntaPerfil`, `Recomendados` (patrocinado com texto, "por que estou vendo", dispensar), atalhos de categorias, `CardDefesa`, `Agenda`, "como funciona" no 1.º acesso; 1 CTA por bloco; skeleton/erro por bloco; emissores | front | Vitrine | area | F1 | 4 | G | TI-34 | por etapas (categorias e próximo passo primeiro) |
| TI-41 | Front P06: `SeletorPeriodo`, `Extrato` (data, benefício, economia, fonte/modalidade), `BlocoProtecao`, `ComoCalculamos` sempre visível, `ValorPotencial` rotulado, `BotaoBaixar` PDF, variantes "o que cobre"/"valor entregue"; renomear rota/título | front | Vitrine | area | F1 | 4 | G | TI-36 | após API |
| TI-42 | Job diário `carencia_vencida` (A03): `data_filiacao` × catálogo → `carencia_vencer` + outbox + `notificacao` + bloco Pendência (≤ 7 d) | jobs | Integrador | area | F1 | 4 | P | TI-17, TI-29 | sim (estrutura) |
| TI-43 | Trilha por evento real: `sql/016` `trilha_passo` (por categoria) + `trilha_progresso` (append) · `trilha.avaliar(contact_id, acao, entidade)` chamado após `uso.registrar` das ações mapeadas · `GET /trilha` (progresso, próximo, `expira_em` = filiação + 90 d) · bloco de 3 passos na home · **sem** `POST .../concluir` · `rota_inicial` fixa `/area` · front `BarraProgresso`/`PassoTrilha`, visibilidade por tempo de casa | SQL/dominio/API/front | Maestro + Vitrine + Atlas | area | F1 bloco / F2 | 4 (bloco) / 6 | M | TI-31; DEC-21 | sim |
| TI-44 | Views de indicadores `sql/021` (`vw_ind_01..14`, `vw_qualidade_parceiro_mes`, k ≥ 20 nos recortes) + `base_ativa_mensal` por job + usuário `apm_area_painel` só `SELECT` nas views + função única `agregar(min_n=20)` | SQL/jobs | Atlas + Sentinela | area | F1 | 4 | M | TI-35, TI-14; DEC-16; base ativa (EXT-25) | definições sim |

### 12.5 Carteirinha, hub, integrações da área

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-45 | Verificação pública em tempo quase real: `associado.situacao(contact_id)` no hub com `VERIFICACAO_CACHE_TTL` (5–15 min), limite global de chamadas a partir de `/verificar` (60/min por processo), fallback "não confirmada", `carteirinha_revogada_em` (+ job noturno de situação em lote, rotação de token na reemissão), `GET /carteirinha` com `revogada`, `compartilhar` 409, resultado em `detalhes` de `carteirinha_verificar`, estado na UI | dominio/jobs/API/front | Sentinela + Integrador + Maestro | area | F1 | 3 | M | TI-47 (hub) + cota (EXT-25); DEC-09 | após TI-47 → **✅ 30/10 (`sql/014`; consulta real após M-7)** |
| TI-46 | Carteirinha: `GET /carteirinha/imagem.png` e `/pdf` gerados no servidor (Pillow/segno, ETag, `no-store`) + `num_contato` no cartão + "Membro" → "Associado" | API/front | Maestro + Vitrine | area | F1 | 3 | P | — | sim → **✅ 30/10 (PNG/PDF, `carteirinha_baixar`)** |
| TI-47 | Hub: `associado.situacao` e `associado.historico_associacao` por `contact_id` **sem CPF na saída**, concedidas à conta da área (grant exato) | hub | Integrador | hub | F1 | 3 | P | — | sim → **✅ 30/10 (código; grant M-7 pelo operador)** |
| TI-48 | Hub: `associado.perfil_consultar` ampliada (ou `cadastro_consultar`): `faixa_carreira` derivada (nunca a data), `nome_social`, especialidades, regional/distrital, `isento_remido`, código da situação normalizada (`ativo\|suspenso\|cancelado\|outro`); `hub_stub` + `CONTRATO-HUB.md` | hub + area | Integrador | hub, area | F1 | 4 | M | atributos no CRM (EXT-19); DEC-14 | parcial (nascimento já é lido em `associado.consultar`) |
| TI-49 | Hub: `financeiro.situacao_consultar` + `financeiro.faturas_listar` por `contact_id` com regra de situação e cache 15 min (ADR-0010) + stub | hub | Integrador | hub | F1 cond. | 7 | M | P-04 (A-5), P-08 para produção | código sim; produção não |
| TI-50 | Hub: `solicitacao.espelhar` / `status_atualizar` / `alteracoes_consultar` (credencial só Create/Write em `task`, idempotência por `uuid`, `@odata.nextLink`) + contrato + stub | hub | Integrador | hub | F1 | 3 | G | P-06 (EXT-20) para o real | contrato e stub sim |
| TI-51 | Hub: `importacao.resolver_lote` (CPF → `contact_id`/`nao_encontrado`, sem CPF na saída, titular auditado; lead → RD/CRM), `associado.alterados_desde(cursor)`, `financeiro.vencidas_desde(cursor)`; conta **`area-associado-jobs`** com cota própria; resposta à P-41 incluindo os jobs | hub | Integrador + Estivador | hub | F1 | 3–4 | M | estimativa da base (EXT-25) | sim → **✅ parcial 30/10 (conta documentada; P-41 respondida)** |
| TI-52 | Hub: grupo `parceiros` com `associado.situacao` em `modo_pii=minimo` (resposta `ativo: bool`), cota e allowlist por parceiro — só se DEC-10 nomear o hub | hub | Sentinela + Integrador | hub | F1 | — | M | DEC-10 | após DEC |
| TI-53 | `app/integracoes/rdstation.py` (OAuth2 refresh → access em memória, `POST /platform/events` conversão, `PATCH contacts/email:{email}` descadastro síncrono com fallback, `GET account_info` + `contacts/fields`, classificação de resposta, `RD_MODE=stub` proibido em produção, `scripts/check_rd.py`) + job `outbox_rd` (revalida o fato, recuo, `GET_LOCK`) + campos `cf_apm_*` conferidos no boot; `cf_apm_contactid` sempre, nunca CPF nem `available_for_mailing` | integração/jobs | Integrador + Sentinela | area | F1 | 3b | M | TI-18; app OAuth2 (EXT-08) para produção | sim (stub) |
| TI-54 | Importação CSV plano B: parser/validador puro (§13.3) com fixtures, `importacao`/`importacao_linha` (sem CPF; único `(parceiro_id, id_externo)`; CHECK anti-CPF em `observacao`), job `importar_csv` (CPF só em memória → hub → descarte), prévia/confirmação → `uso_valor` nível 3, devolução de erros por SMTP sem dado pessoal | jobs/SQL/dominio | Integrador + Atlas + Sentinela | area | F1 | 4 | M | TI-51; canal (DEC-05) | parser sim |
| TI-55 | Jobs de diferença e prazo: `diff_cadastro` (A01/A13; fundido com `atualizar_perfis`, só quem acessou em 90 d), `sem_primeiro_acesso` (A02), `sem_uso_90` (A11) | jobs | Integrador | area | F1/F2 | 4 | M | TI-01, TI-47, TI-51 (cursor/cota) | após TI-47 |
| TI-56 | WordPress: `WP_*` em `Settings` (+ validador stub/prod, fechando DIV-42), `portal_wp.py` + `portal_wp_stub.py` + fixtures, `sql/012` (caches, temas, salvos, inscrições), `scripts/check_portal_wp.py`, job `sincronizar_portal` (15 min, `max_execution_time` 5 s, upsert por hash, nunca DELETE) | integração/jobs/SQL | Integrador + Atlas | area | F2 | 5 | M | P-07, P-21 (EXT-34) para o real | sim (stub) |
| TI-57 | Financeiro na área atrás de `erp_financeiro`: `app/api/v1/financeiro.py` (`GET /financeiro`, 404 `recurso_desligado`), stub do hub, tela "cobrança indisponível → Central"; declarações como solicitação tipo 3 `declaracao_associado` com carência AMB (viável já) | API/front | Maestro + Vitrine | area | F1 cond. | 3 (declarações) / 7 | P | TI-49 para o real | sim → **✅ parcial 30/10 (declarações; financeiro na Onda 5)** |
| TI-58 | API interna do backoffice `/api/interno/v1` (B05 status com justificativa, B06 importação, B13 parâmetros, B01 painel): contrato + autenticação por token de serviço separado (nunca a sessão do associado); UI fora | API | Maestro + Sentinela | area | F1 | — | G | DEC-03 | após DEC |
| TI-59 | Fila de ligações sem backoffice (§10.5): tabela `fila_ligacao` + job 08h + entrega diária à Central (CSV por SMTP interno ou view RO no portal do hub) | jobs | Integrador | area | F1 | 3b | P | TI-01; DEC-03 (provisório) | após DEC |

### 12.6 Front transversal e RNF

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-60 | Navegação §3.1: reordenar/renomear `ROTAS` (Início, Benefícios, Carteirinha, Meu valor, Financeiro, Minhas solicitações, Clube, Eventos, Notícias e ciência, Perfil e privacidade, Ajuda, Sair), bottom-nav Início/Benefícios/Carteirinha/Meu valor/**Mais** (abre o `Drawer`), drawer só com o restante, rotas `financeiro`/`ajuda`, `rotaVisivel` por implementação (rotas sem página somem no cutover), Comunidade/Onboarding fora do menu antes da fase | shell | Vitrine | area | F1 | 3 | M | DEC-24 | após DEC (plano de shell) |
| TI-61 | Voz §3.3: tirar exclamação (`links.ts`), verbo nos botões, "Membro" → "Associado", chamada do Clube sem "cashback", 1 CTA primário no hero | texto | Vitrine | area | F1 | agora | P | — | sim (fast-path) → **✅ 30/10** |
| TI-62 | Alvos 44 px (`.botao`, `.busca__limpar`), `scroll-padding-bottom` no mobile (2.4.11), `100dvh` | CSS | Vitrine | area | F1 | agora | P | — | sim (fast-path) → **✅ 30/10** |
| TI-63 | axe com `wcag22aa` em todas as rotas; projetos Playwright `webkit-iphone` e `mobile-360`; teste de Tab até o rodapé; reflow 320 px | testes | Vitrine | area | F1 | agora | P | WebKit no host de e2e (Estivador) | sim (Chromium já) → **✅ 30/10 (WebKit exige libs no host)** |
| TI-64 | Tokens tipográficos em `rem` + `ControleFonte` (3 passos, `data-fonte` no `html`, sem inline) + base ≥ 15 px avaliada | CSS/shell | Vitrine | area | F1 | 3 | M | DEC-27 (persistência) | parcial (`rem` sim) |
| TI-65 | Primitivos puros com Vitest: `SeloEstado`, `Dialogo`, `Accordion`, `Combobox`, `Tabs`, `BarraProgresso` (CSSOM), `Skeleton`, `EstadoErro` (`request_id` + tentar novamente), `RadioGroup`/`CheckboxGroup`, `ImagemSegura` (host ∈ `CSP_IMG_HOSTS` via `/sessao`, lazy, proporção fixa) | componentes | Vitrine | area | F1 | agora | M | DEC-35 só para rótulos | sim (fast-path) → **✅ 30/10 (10 primitivos)** |
| TI-66 | PWA: `manifest.webmanifest` + ícones 192/512 maskable servidos pelo FastAPI (`start_url=/area`, `scope=/area/`, `display=standalone`), `<link rel=manifest>`, `Cache-Control` próprio, `location` no vhost, e2e com `securitypolicyviolation`; **sem SW**. SW restrito (`/area/sw.js`, `worker-src 'self'`, network-only em navegação e `/api`, cache-first só assets imutáveis, unregister no logout, lint contra `caches`/`indexedDB`) só com DEC-07/push | front/infra | Vitrine + Sentinela + Estivador | area | F1 | cutover | P (manifest) / M (SW) | DEC-07; ícones oficiais (EXT-04) | manifest após ADR curta |
| TI-67 | Medição de desempenho: Lighthouse no e2e com orçamento (`budget.json`: LCP, INP/TBT, CLS, JS ≤ 250 kB; Moto G equivalente, 360 px), `React.lazy` por rota, limitar a animação de entrada ao 1.º filho se medir mal, variante opaca para listas longas; RUM próprio (`web-vitals` self-hosted + `window.onerror`/`unhandledrejection` → `POST /uso` ações `vitais_web`/`erro_js`, sem stack com PII) + leitura em `/db-health`/views (indicador 14) | testes/front/API | Vitrine + Maestro + Estivador | area | F1 | 4 | M | TI-04 (ações) | laboratório sim |
| TI-68 | Higiene de docs/templates: `LICENSES.md` (Figtree → Sora), `frontend/dist` obsoleto, ADR-0017 "12 × 13 mockups", P-24 (`stub_login`/`erro` em Sora), comentário desatualizado no vhost ("DEV_STUB_TOKEN"), `CUTOVER.md` (snapshot manual, `.env` replicado, monitor ligado, pós-reboot, aviso de manutenção, critério de "go" por indicador 14, "expira 10/10" no passado), caminho do certificado em `PENDENCIAS_AWS.md` | docs/templates | Vitrine + Estivador | area, infra | F1 | agora | P | — | sim → **✅ 30/10** |
| TI-69 | Padrão de teste por tela nova: `*.test.tsx` (vazio/erro/carregando/sucesso, eventos emitidos) + bloco e2e (CSP, axe 2.2, 360/390/1440) + skill `nova-fase-minha-apm` | testes | Vitrine | area | F1 | agora | P | — | sim → **✅ 30/10** |

### 12.7 Infra, operação e IdP

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-70 | P-01: instalar Cloudflare Origin CA em `sites-enabled/certs/`, `nginx -t && reload`, remover `temp.pem`, zona Full (strict); validade no pós-reboot | TLS | Estivador | infra | F0 | agora | P | certificado (EXT-26) | mesmo dia da emissão → **arquivos prontos 30/10; execução do operador (P-01)** |
| TI-71 | Catch-all `_00_padrao.conf` (`listen 443 ssl default_server; server_name _; return 444;`, mantendo o default da 80) — P-34; pré-requisito de qualquer DNS `hml`/`admin` | vhost | Estivador | infra | F0 | agora | P | aprovação do operador (mexe em todos) | sim → **arquivo pronto 30/10; execução do operador (P-34)** |
| TI-72 | `verificar-pos-reboot.sh`: + `area_associado`, `mcp_hub`, `appapm-cron`, `area_associado_jobs`; hosts `minha`, `mcp`; validade do `origin.pem`; `docker compose ps` healthy — P-19 | host | Estivador | infra | F0 | agora | P | — | sim → **patch pronto 30/10; execução do operador (P-19)** |
| TI-73 | P-36: replicar `.env` de 21/10 no Secrets Manager; apagar os 3 `.env.bak-*`; `scripts/env_check.sh` | segredos | Estivador | infra | F0 | agora | P | operador (ou `GetSecretValue`, EXT-27) | operador hoje → **runbook pronto 30/10; execução do operador (P-36)** |
| TI-74 | `scripts/deploy.sh`: `git pull --ff-only` + build `DOCKER_BUILDKIT=0` com tag `area:<sha>` + `up -d` + esperar healthy + `db_check`/`check_oidc`/`csp_check` + `curl /health` + rollback para a tag anterior | deploy | Estivador | area | F1 | agora | P–M | DEC-31 (recomendada) | sim → **✅ 30/10** |
| TI-75 | Monitoramento: uptime externo nos 7 hosts (`/health`) + alerta diário/horário no padrão `login_associado/deploy/alertas.sh` (5xx do porteiro, Tracebacks, `uso_falhas`, `job_execucao` com erro, 429 anormais, cert < 30 d, `.env` ≠ cofre) | monitoramento | Estivador | area, infra | F1 | agora | M | conta de monitor (EXT-29); SMTP (P-27) ou webhook | script sim; envio após EXT → **`alertas.sh` pronto 30/10; monitor externo pelo operador (P-61)** |
| TI-76 | Runbook de backup/restore: política (7 d, 06:11 UTC, PITR), snapshot manual antes de cada `sql/NNN` e do cutover, restauração trimestral em instância temporária (`db_check`, contagens, `schema_migrations`), descarte; evidência em CONCLUIDO; opcional export de `evento_log` para S3 Object Lock | docs/infra | Estivador + Atlas | area, infra | F0 | agora | M | IAM (EXT-27) para executar | doc sim; ensaio após EXT → **✅ 30/10 (runbook; ensaio após P-59)** |
| TI-77 | GitHub Actions: `check` (npm check, pytest, build com buildx), e2e Playwright com container stub + MySQL service, Lighthouse CI com orçamento, `pip-audit` + `npm audit --audit-level=high`, `csp_check`/`db_check`; sem deploy automático (DEC-31) — P-25 | CI | Estivador + Sentinela | area | F1 | antes da Fase 3 no ar | M | Actions na org (EXT-30) | arquivo sim; roda após EXT |
| TI-78 | Hardening do compose: `pids_limit`, `tmpfs /tmp:size=64m`, `TZ=America/Sao_Paulo` (web e jobs); pool pequeno nos jobs (2+2) | container | Estivador | area | F1 | agora | P | — | sim → **✅ 30/10** |
| TI-79 | Homologação: `docker-compose.hml.yml` (`-p area_hml`), `.env.hml`, schema `area_associado_hml` + usuário próprio (mesmas migrações), vhost `hml-minha.apm.org.br` restrito (allowlist IP / Cloudflare Access), `noindex`, hub stub ou sandbox, IdP stub ou contatos de teste; RDS separado por snapshot (DEC-30) | ambientes | Estivador | area, infra | F1 | antes de `HUB_ESCRITA_HABILITADA=true` | G | TI-71; DEC-30; EXT-22, EXT-31 | após DEC |
| TI-80 | Backoffice (infra + dados): container `area-associado-admin` (mesma imagem, 256M) ou rotas `/admin` conforme DEC-03; host próprio (`minha-admin.apm.org.br`: o wildcard não cobre `*.minha.`); vhost com allowlist IP + Cloudflare Access; usuário de banco `apm_area_bo`; `sql/017` `usuario_interno`/`backoffice_auditoria`/`acesso_dado_pessoal` | container/vhost/SQL | Estivador + Atlas + Sentinela | area, infra | F1 | — | G | DEC-03; EXT-36, EXT-31 | após DEC |
| TI-81 | Canal do CSV: tmpfs de quarentena com `size=`, `location` de upload com `client_max_body_size` e zona própria; (se S3) bucket privado SSE + lifecycle + role com `PutObject` no prefixo | infra | Estivador | area, infra | F1 | — | M | DEC-05; EXT-32 | após DEC |
| TI-82 | Vhost: `location`s para `/manifest.webmanifest` e `/sw.js` (zona static, `no-cache`), página de manutenção (`maintenance.html` + `return 503` chaveado por arquivo), zona do upload de CSV, `server` do backoffice; regra de rate limit da Cloudflare para `minha.` (`/auth/*`, `/verificar/*`) | vhost | Estivador | infra | F1 | conforme rota | P–M | rotas existirem; EXT-31 | parcial |
| TI-83 | IdP (`login_associado`): (a) 1.º acesso com CPF + nascimento antes de revelar canais, resposta única (anti-enumeração), lockout por CPF e IP; (b) "continuar conectado" (cookie persistente opt-in 30/90 d, `auth_time` original, revogação na troca de senha); (c) "meus dados mudaram" (formulário público → pedido à Central via hub/task, limite 3/h, Turnstile); (d) página de retorno do ex-associado após triagem `INACTIVE`; (e) ACE-05 por rede (/24 ou ASN na Cloudflare); (f) evento/claim `conta_criada` para a área | IdP | Sentinela | idp | F1 | paralela | M | (a) EXT-19; (b) DEC-12; (c) P-06; (d) DEC-11 | (e) sim; resto após EXT/DEC |
| TI-84 | Logs: `awslogs` (CloudWatch, 90 d) ou `journald` para não perder `docker logs` na recriação (mantendo `json-file` como padrão) | logs | Estivador | infra | F1 | — | P | IAM (EXT-27) | após EXT |

### 12.8 F2/F3 (estrutura pode nascer, ligação só na fase)

| ID | Tarefa | Camada | Persona | Repo | F | Fase | Tam. | Pré-req. | Hoje? |
|---|---|---|---|---|---|---|---|---|---|
| TI-85 | Notificações in-app: `GET /notificacoes?cursor=`, `POST .../ler`, `ler-todas`, `notificacoes_nao_lidas` em `/sessao`, flag `notificacoes`; sino só com aceite visual (EXT-02) | API/front | Maestro + Vitrine | area | F2 | — | M | TI-18; DEC-08 | 🔒 F2 (tabela já na Fase 3) |
| TI-86 | Score de engajamento: `sql/019` `score_engajamento` (particionada) + `score_pesos` + job diário; componente "comunicação" por export do RD | SQL/jobs | Atlas + Integrador | area | F2 | — | M | TI-44; DEC-18 | 🔒 F2 |
| TI-87 | Eventos e notícias (P10/P11): `GET /eventos` (filtros), `/eventos/{id}`, `/inscrever` (interesse; carência 3 m pelo motor), `/inscricoes`, `GET /noticias`, `/temas`, salvar/seguir, `conteudo_lido(tema, tempo)`; front com `ImagemSegura`, `ChipTema`, sub-rotas | API/front | Maestro + Vitrine | area | F2 | 5 | G | TI-56 (stub serve) | após TI-56 |
| TI-88 | Clube P09: seed `oferta_clube` + `PARCEIROS_HOSTS` (ADR-0009), `GET /clube` (oferta da semana, grupos, `economia_ano` só com flag), `POST /clube/ofertas/{id}/abrir` via redirecionador, front | SQL/API/front | Maestro + Vitrine | area | F1 link | 6 | M | TI-32; curadoria (P-11) | sim (seed de teste) |
| TI-89 | Comunidade P16 (F3) e trilha completa TRI-01 (F2): conforme REQUISITOS §3.7/§3.10, `sql/016`; fora do menu até a fase | — | Maestro + Vitrine | area | F3 | 6 | G | parecer (EXT-18) para ENC-01 | 🔒 |
| TI-90 | Padrão "registro de acesso a dado pessoal" (`acesso_dado_pessoal` em `evento_log`: `alvo_contact_hash`, `campos`) + função única `agregar(min_n=20)` para qualquer painel/exportação a terceiro | audit/dominio | Sentinela | area | F1 | — | P | DEC-03 para uso | padrão sim |
| TI-91 | Web Push (só se DEC-08 aprovar): SW restrito, VAPID em `.env`, `push_assinatura` cifrada, envio pelo serviço de jobs com egress declarado (regra 16), payload sem conteúdo sensível, consentimento por canal antes de `requestPermission` | front/jobs/SQL | Sentinela + Integrador | area | F2 | — | G | TI-66 (SW), TI-85, TI-25 | 🔒 |
| TI-92 | Vocabulário de categoria do associado: tabela de-para rótulo → código (provisório até EXT-11) usada por elegibilidade, matriz, indicadores e `associado_categoria_hist` | SQL/dominio | Atlas | area | F1 | 4 | P | EXT-11 para o definitivo | sim (provisório) |

**Resumo da lista TI:** 92 tarefas; **podem começar hoje sem decisão nem terceiro: 43** (TI-02, 03, 04, 05, 06,
07, 09, 11, 12, 13, 15*, 16*, 17*, 18*, 19*, 20*, 23, 25, 26, 28, 30, 33*, 34*, 35, 36*, 42*, 43*, 46, 47, 49*,
50*, 51, 53*, 54*, 56*, 57, 61, 62, 63, 65, 68, 69, 71, 72, 74, 78, 92 — * = com stub/flag ou depois da tarefa
anterior da mesma fase); **esperam só decisão do usuário (DEC): 17**; **esperam terceiro para a versão real:
32** (todas têm versão com stub/flag).

## 13. LISTA EXTERNA — dependências de terceiros (EXT-nn)

Colunas: o que precisamos (artefato concreto) · de quem · quais TI destrava · o que a TI faz enquanto espera ·
P-xx (existente, ou **novo** criado em `PENDENCIAS.md` nesta rodada).

### 13.1 Agência (Comunicação Encantada) e Marketing APM

| ID | O que precisamos exatamente | De quem | Destrava | Enquanto espera | P-xx |
|---|---|---|---|---|---|
| EXT-01 | Pacote completo dos 13 mockups (`*.dc.html`, `assets/`, `support.js`) para versionar em `docs/mockups/`; confirmar que `relacionamento` = P16 | agência | fidelidade visual das fases 3–8 (TI-21, TI-38, TI-39, TI-40, TI-88) | tradução por `tokens.css` do que foi colado em 20/10 | P-39 |
| EXT-02 | Mockups que **não existem**: P04 (ficha e 6 estados), P05 (lista, linha do tempo, avaliação), P06 v2 ("como calculamos", potencial, período), P08 (situação, 2.ª via, Pix, declarações), P13 (consentimentos, baixar dados), P14 (FAQ, canais, cancelamento), P12 por categoria, P15 (sino), aba "Mais", selos textuais; aceite visual do sino | agência | TI-21, 22, 27, 38, 39, 41, 85 com visual aprovado | construir com os componentes e a linguagem do ADR-0017; aceite depois | **P-42** |
| EXT-03 | Decisão formal sobre identidade: Sora + paleta do mockup (ADR-0017) × Verdana + `#616365` do brandbook (spec §14); botão verde × gradiente | Marketing APM + agência | fecha DIV-34, DIV-37; TI-64 (base tipográfica), TI-68 (aditivo à ADR-0017 se mudar) | ADR-0017 vale (🔒) | **P-43** |
| EXT-04 | Imagens com direito de uso (hero, selos, capas) e ícones oficiais (logo SVG, 192/512 maskable para o PWA) | Comunicação APM | TI-66, cards com foto | gradientes CSS | P-38 (ampliada) |
| EXT-05 | Textos finais na voz §3.3: títulos/chamadas de rota, estados vazios e de erro (editáveis em `texto_sistema`), rótulos dos 6 estados e 7 status, "como calculamos", FAQ inicial (≥ 20 perguntas), motivos de cancelamento, pedidos comuns | Encantada executa / Marketing APM responde (RACI §10.6) | TI-20, 21, 22, 38, 41 | textos provisórios da spec marcados como proposta (LA-25) | **P-44** |
| EXT-06 | Validação das variantes de contraste `-texto` e dos pares das tags de status | agência | P-22; TI-63 (axe) | variantes atuais | P-22 |
| EXT-07 | Testes de usabilidade com associadas e associados de faixas etárias diferentes (§14) + iPhone real para e2e manual | Marketing/Encantada | aceite de P02/P03 (TI-38, TI-40) e do tamanho de fonte (TI-64) | axe + Playwright | **P-45** |
| EXT-08 | Contrato de comunicação com o RD: app OAuth2 privado (client_id/secret/refresh) para a área ou reuso do app do totalpass; campos `cf_apm_*` novos (score, valor_ano, suprimir_ofertas, canal_preferido…); tabela gatilho → `conversion_identifier` → fluxo; quem aplica o limite 2/semana; nomes de UTM/código do gatilho; dono único dos campos (sincronia CRM→RD `cf_crm_contato_*` "Não Funcionando" e `birthdate` padrão) | Marketing (dono da conta RD) + CRM admin | TI-53 em produção, TI-11 real, A18, indicador 10 | `RD_MODE=stub`, outbox acumula, catálogo provisório | **P-46** |
| EXT-09 | Destino dos dados analíticos e ferramenta de painéis (F0-06); quem acessa cada painel (§11.5) | Marketing/Encantada + usuário | TI-44 (ferramenta), B12 | views + `apm_area_painel` | **P-47** |

### 13.2 Benefícios e parcerias, Financeiro, Jurídico/DPO

| ID | O que precisamos exatamente | De quem | Destrava | Enquanto espera | P-xx |
|---|---|---|---|---|---|
| EXT-10 | Catálogo inicial validado (30–40 benefícios): categoria, tipo de ativação, carência, categorias permitidas, região, vigência, parceiro, canal e prazo de retorno, modalidade de mensuração, **valor de referência aprovado pelo Financeiro** (fonte, data), selos, FAQ por benefício | Benefícios e parcerias + Financeiro (+ Jurídico para a carência do Clube) | seed de TI-29/TI-35; P03/P04/P06 reais; A03/A05 | tabelas vazias; fixture de catálogo de teste; telas em construção | **P-48** (amplia P-10) |
| EXT-11 | Parâmetros e definições de negócio (§15.5): dias de atraso que suspendem, prazo de retorno padrão, prazo de avaliação, "mudança de categoria reinicia carência?" (recomendação: não), carência do Clube, motivos de cancelamento, vocabulário/códigos de categoria e contagem da base conciliada | Presidência / Financeiro / Benefícios / Jurídico | TI-30, TI-92, DEC-15 | `parametro` com padrões documentados; de-para provisório | **P-49** |
| EXT-12 | Lista de parceiros com API e contratos técnicos (B04 "requisito técnico"): autenticação, payload mínimo (LGPD), status de volta, prazo, host de destino por benefício, exigência de "código pessoal"/SSO — cada um vira ADR própria | Benefícios + cada parceiro | tipo 2 por API; TI-32 (hosts) | tipo 2 por canal manual + CSV; allowlist estática | **P-50** |
| EXT-13 | Fornecedores de MBE, biblioteca, Clube Certo e plataformas de eventos/IESAPM (F0-01): mecanismo de acesso único (o `login_associado` como provedor), API de retorno de resgate/inscrição/presença/certificado | Benefícios / fornecedores | tipos 1 e 6 F2, tipo 5 real, CLU-01..03, EVE/CON (TI-87, TI-88, TI-32) | link rastreado; interesse local | **P-51** |
| EXT-14 | Qualicorp: custo e forma (API ou relatório) | Benefícios + Qualicorp | F2 (TI-24 por canal manual; API por ADR própria) | tipo 2 sem API | **P-52** |
| EXT-15 | Arquivos CSV do plano B no layout §13.3, entregues até o dia 10 pelo canal definido em DEC-05 | Benefícios + parceiros | TI-54 em produção; Meu valor v1 | parser com fixtures | **P-53** |
| EXT-16 | Jurídico/encarregado: textos e finalidades dos consentimentos com versão; base legal por finalidade; **prazo de guarda por tabela** (solicitação, auditoria, consentimento, uso/valor, `evento_uso`, comunicação, `job_execucao`); procedimento do pedido de exclusão (anonimizar × apagar, prazo de resposta); quem opera a fila | Jurídico + encarregado de dados | TI-25..28, TI-02 (partições), P-15 | consentimentos atrás de flag com texto v0; retenção segue propostas das migrações | **P-54** (amplia P-15) |
| EXT-17 | Parecer de licença/multiplexação do F&O | TI / Jurídico | TI-49, TI-57, P08, A09, "N vezes" | flag `erp_financeiro` desligada; `financeiro=None` | P-08 |
| EXT-18 | Parecer jurídico sobre dados de saúde para a rede de encaminhamento (ENC-01) | Jurídico | TI-89 (ENC-01) | DIR-01/COM-01 primeiro | **P-55** |

### 13.3 CRM (Dataverse), cadastro e cobrança

| ID | O que precisamos exatamente | De quem | Destrava | Enquanto espera | P-xx |
|---|---|---|---|---|---|
| EXT-19 | Atributos do `contact`: data de nascimento (completude por categoria; exposta só como faixa ou `confere: bool`), nome social, especialidades (1.ª/2.ª/3.ª), regional/distrital, isenção/remição, documentação pendente (acadêmico); se `sol_associacao` registra **categoria** ou só status | CRM admin | TI-48, TI-83(a), fase de carreira, elegibilidade por região, A13/A14/A19 | campos `null`; afinidade só por categoria; `hub_stub` com valores | **P-56** |
| EXT-20 | Entidade do espelho das solicitações no CRM e mapeamento de status, inclusive como distinguir "não seguiu" de "cancelada pela APM", campo de mensagem pública e quem trata a fila | CRM admin / atendimento | TI-50, TI-17 real | fila local + stub | P-06 |
| EXT-21 | Flows em update de `contact` (P-29), homologação da foto (P-30), campos do endereço (P-31), contatos de teste (P-37) | CRM admin | escrita real no CRM (`HUB_ESCRITA_HABILITADA`, código pronto); edição de endereço; contatos de teste para TI-79 | leitura real, escrita desligada | P-29, P-30, P-31, P-37 |
| EXT-22 | Sandbox do Dataverse (ou contatos de teste marcados) acessível por uma conta do hub para homologação | CRM admin | TI-79 com dados anonimizados | `HUB_MODE=stub` | **P-57** |
| EXT-23 | Volume: base ativa por categoria e regional e estimativa de acessos (P-41); cota e `client_id` próprios para os jobs | negócio + usuário (operador do hub) | TI-51, TI-44 (`base_ativa_mensal`), TI-55, partições | hipótese de trabalho explicitada (10 mil) | P-41 (refeita com jobs) |
| EXT-24 | Definir o "novo sistema de cadastro e cobrança" (§13.1/13.2): quem desenvolve, API, **avisos automáticos** (webhooks), situação financeira, segunda via (PDF/linha digitável/Pix), renovação; contrato de dados F0-02 | Diretoria / Financeiro / TI | P08 (TI-49, TI-57), A09/A10 (TI-55), indicadores 4/11 (TI-44), DIV-30 | ERP via hub só leitura, sem 2.ª via ("fale com a Central"); jobs de diferença | **P-58** |
| EXT-25 | (= EXT-23) cota do hub para `/verificar` + job noturno de situação | usuário (hub) | TI-45 | cache 24 h e "não confirmada" | P-41 |

### 13.4 Infra: AWS, Cloudflare, GitHub, Locaweb, fornecedores de canal

| ID | O que precisamos exatamente | De quem | Destrava | Enquanto espera | P-xx |
|---|---|---|---|---|---|
| EXT-26 | Emitir Cloudflare Origin CA `*.apm.org.br` (15 anos), entregar `.pem/.key` ao operador, zona Full (strict) depois de instalar | operador / Cloudflare admin | TI-70; cutover; segurança dos 7 sites | risco aceito desde 10/10 (Cloudflare↔origem sem validação) | P-01 |
| EXT-27 | IAM: ampliar a role `EC2-ReadOnly-Billing` (ou perfil humano) com `rds:CreateDBSnapshot`, `rds:RestoreDBInstanceFromDBSnapshot`, `secretsmanager:GetSecretValue` em `prod/area-associado/env`, `cloudwatch:DescribeAlarms`, opcional `logs:*` | AWS admin | TI-73, TI-76, TI-84 | operador pelo console | **P-59** |
| EXT-28 | Teste de restauração do RDS executado e datado (snapshot → instância temporária → validação → descarte); retenção 7 → 14 d; export de logs `error`/`slowquery` e Performance Insights | operador / AWS admin | §14 "teste de restauração"; DEC-33 | runbook (TI-76) | **P-60** |
| EXT-29 | Conta em monitor externo (UptimeRobot/Better Stack) com contatos de alerta; decisão sobre o Datadog pago (usar ou cancelar) | operador | TI-75 | pós-reboot manual | **P-61** |
| EXT-30 | GitHub Actions habilitado na org `SistemasTiAPM` e branch protection em `main` | GitHub admin | TI-77 | checks no build local | P-25 |
| EXT-31 | Cloudflare Access (Zero Trust) com IdP corporativo e MFA para `admin`/`hml`; lista de IPs/VPN da APM para allowlist; regras de rate limit/WAF para `minha.apm.org.br` | Cloudflare admin / operador | TI-79, TI-80, TI-82 | allowlist IP no porteiro | **P-62** |
| EXT-32 | Egress do SG da EC2 para Locaweb 3306 e API do RD (443) a partir do container de jobs; bucket S3 privado + role `PutObject` (só se DEC-05 escolher S3) | AWS admin | TI-56, TI-53, TI-81 | — | **P-63** |
| EXT-33 | Credencial SMTP própria com SPF/DKIM (`SMTP_HOST/USER/PASSWORD/FROM`) | TI / infra | TI-19, TI-20, TI-26, TI-75 (alertas), troca de e-mail em produção | `SMTP_MODE=stub` (faixa de demonstração) | P-27 |
| EXT-34 | Usuário RO na Locaweb + TLS + restrição de IP (P-07); mapa do post type/taxonomia de notícias (P-21); migrar o appapm (P-16) | infra / Planeta W | TI-56 real | `WP_MODE=stub` | P-07, P-21, P-16 |
| EXT-35 | Canal celular para OTP e régua: WhatsApp API oficial (Fortics, já previsto no IdP) **ou** provedor SMS, com contrato, remetente e limites | TI / contratos / Marketing | OTP por celular no IdP (TI-83), A02 (TI-55), canais em P13 (TI-27) | só e-mail; P13 oculta WhatsApp/SMS (regra 19) | **P-64** |
| EXT-36 | Entra ID da APM: tenant, app registration, grupos → 8 perfis, política de MFA para o backoffice | TI / diretoria | DEC-03, TI-80 | padrões nascem na área/hub | **P-65** |
| EXT-37 | Contratos de patrocínio/cartão (P-12) e contas Apple/Google Wallet (P-13) — F2/F3 | negócio / TI | P17, WAL-01: ligar as flags `mensalidade_zero`/`patrocinio`/`wallet` com dado real (TI-13; UI já existe sob flag) | flags desligadas | P-12, P-13 |
| EXT-38 | Decisões do operador já abertas: buildx (P-26), replicar `.env` (P-36), catch-all (P-34), volume ao hub (P-41) | operador | TI-70..73, TI-77 | — | P-26, P-34, P-36, P-41 |

## 14. Síntese por persona

| Persona | Os 3 pontos que mais pesam | ADRs candidatas (título; gatilho) | Ordem sugerida |
|---|---|---|---|
| 🛡️ **Sentinela** | (1) A validação pública da carteirinha não consulta a situação: cancelado fica "Ativo" por até 24 h e depois "não confirmada" para sempre (DIV-13) → TI-45/47 com cota (P-41). (2) LGPD (consentimento versionado, exportar, excluir) está por construir e a exclusão colide com "DELETE nunca" → anonimização (DEC-06), atrás de flag, dependendo do jurídico (P-54). (3) P01 vive no IdP: a triagem confirma existência de CPF (DIV-02); faltam nascimento, "continuar conectado", "meus dados mudaram", retorno do ex-associado, canal celular; o backoffice **nunca** dentro da área com o `login_associado` (DEC-03). Também: P-40 vira risco real na Fase 3 (TI-10); SW mal delimitado cachearia HTML com nonce e `/api` (DEC-07); CSV com CPF só no hub (DIV-04); dado de saúde em texto livre → allowlist por tipo e `sigiloso` (TI-15). | Direitos do titular (anonimização, sem DELETE; DEC-06) · Consentimento versionado · Backoffice: identidade, 2FA, autorização (DEC-03) · Verificação pública em tempo quase real e revogação (DEC-09) · PWA sem SW / SW restrito (DEC-07) · Encaminhamento rastreado por redirecionador (estende 0009) · Parâmetros de campanha (catálogo fechado) · Importação do plano B no hub (estende 0014) · Notificações (DEC-08) · Step-up generalizado | agora: TI-05, 09, 10, 11, 12, 07, 66 (manifest), 83(e) · decidir: DEC-03, 06, 07, 08, 09, 10, 11 · Fase 3: TI-15, 08, 20, 90, 45 · Fase 3b: TI-25, 26, 28 · Fase 4: TI-32 · IdP em paralelo: TI-83 |
| 🗄️ **Atlas** | (1) A importação CSV é chaveada por CPF e colide com a ADR-0014: resolução e lead no hub (TI-51); a área recebe `importacao_linha` sem CPF, idempotente por `(parceiro_id, id_externo)`. (2) Antes da Fase 3: 8 status com `sem_retorno_desde` como marcador (DEC-01) e "conteúdo enviado" = campos + sha256 (DEC-02); aproveitar as tabelas pequenas para particionar `evento_uso`/`evento_log` (TI-02), o que resolve a purga sem DELETE (P-15). (3) REQ §6 está desatualizado: `beneficio` vira catálogo com elegibilidade/carência/matriz/valor versionado editável; entram `uso_valor`, consentimento, comunicação, usuário interno; exige segundo usuário de banco `apm_area_bo` e `db_check` com allowlist por usuário (TI-03 — hoje nem cumpre a ADR-0004 §6). | Ciclo da solicitação com 8 status (revisa 0003 §1–3) · Catálogo como dado com elegibilidade configurável (substitui seed; `apm_area_bo`) · `uso_valor` e níveis de evidência como fonte do Meu valor · Consentimento append-only · Importação do plano B no hub · Outbox de comunicação · Dimensões por junção, pseudonimização e k-anonimato · Retenção por partição mensal (fecha P-15) · Usuário de banco do backoffice | agora: TI-06, 03, 02, 28 (rascunho), 76 · decidir: DEC-01, 02, 15, 34 · Fase 3: TI-14, 04, 01 · Fase 3b: TI-25 · antes da 4: DEC-03, 16 → TI-29, 30, 35, 44, 92 · com o hub: TI-47, 48, 51 · com o RD: TI-53 |
| ⚙️ **Maestro** | (1) Máquina de estados: adotar os 8 nomes da spec já na `sql/008` (sem legado), `enviada` promovida por confirmação do canal, `sem_retorno` como coluna, atores parceiro/apm/importação com justificativa, avaliação em colunas; cancelamento pelo associado nunca a partir de `em_atendimento` — tudo pode começar hoje; P-06 só para o espelho real. (2) Elegibilidade, recomendação, blocos da home e Meu valor nascem como serviços de domínio **puros** com os insumos já em `associado_perfil`; o que falta é externo (situação financeira, nascimento/especialidade/regional, catálogo curado). P06 é F1 na spec mas está na fase 8 atrás de flag forçada (DIV-23): a spec dá a fonte; só "N vezes" depende do ERP. (3) A Fase 3 deve absorver P14 (dois tipos de solicitação), a produção da outbox e da `notificacao` na mesma transação (consumo atrás de flag), limites diários por contagem no banco, `solicitacoes_aguardando` real, trilha como bloco por evento real (sem `POST concluir`), OpenAPI exportado no build (nunca servido em produção). | Solicitações v2 (8 status, atores, canal, marcador, avaliação) · Motor de elegibilidade e carências por configuração · Recomendação v1 por regras · Meu valor (`uso_valor`, níveis, `fatura_valor` sem forçar desligada) · Outbox e notificações in-app · Tipos de ativação como estratégia + flags por tipo · Trilha por evento real (substitui RF-ON-05) · API interna do backoffice · Limites por contagem no banco · adenda ADR-0007 (flags novas) | Fase 3: TI-14 → 15 → 16 → 08 → 20 → 18 → 17 → 13 → 07 (decidir antes: DEC-01, 02, 04, 13, 22) · Fase 4: TI-30 (puro, testes de tabela) → 31 → 33 → 34 → 43 → 36 (sem ERP) → 37 (EXT-10 para o seed; DEC-14, 21, 23) · Fase 5: TI-87 · transversal: TI-58, 50, 51 quando houver decisão · P13 (TI-26) entre a 3 e a 4 |
| 🔌 **Integrador** | (1) Nada assíncrono existe (`app/jobs/`, serviço, outbox, RD): sem isso não há gatilho A01–A20 nem espelho CRM; e a cota do hub (120/min, 5.000 PII/dia) inviabiliza jobs em lote → conta própria de jobs e ferramentas por cursor (TI-51, P-41 refeita). (2) RD Station é o maior reaproveitamento: OAuth2, outbox com revalidação e campos `cf_apm_*` (inclusive `cf_apm_contactid`) já existem no totalpass/formulário de filiação; a área só emite campos/eventos; régua e limite ficam no RD; descadastro síncrono com fallback (DEC-18). (3) Cadastro/cobrança: avisos automáticos, nascimento, especialidades, regional, histórico de categorias, situação normalizada e segunda via **não têm fonte**; "novo sistema de cadastro e cobrança" não aparece em nenhum repositório → DEC-17/P-58 com a premissa de que a área só muda o contrato por `contact_id` atrás do hub; avisos substituídos por jobs de diferença. Riscos: e-mail como chave do RD (enviar sempre `cf_apm_contactid`), sobrescrita de contato no RD, duas fontes populando o RD, superfície pública nova (webhook/CSV) exige `limit_req` + 403. | Comunicação e RD Station (consolida DEC-18/19) · Serviço de jobs (agendador, `job_execucao`, `GET_LOCK`, disjuntores, conta própria, cursores) · Importação do plano B (canal, CPF efêmero, nível 4, devolução) · Elegibilidade: situação cadastral × pendência financeira · Tipo 2 sem API (e-mail × consulta no `apm-parceiros`) · Painéis sobre `evento_uso` via views RO | TI-01 + TI-18 (jobs + outbox, com stubs) → TI-47 + TI-51 no hub + P-41 (conta de jobs) → TI-50 + P-06 com TI-19/24 → TI-53 + P-46 (primeiro gatilho real: A04/A16; A03 quando o catálogo chegar) → TI-54 + DEC-05 (CSV) → TI-48 + P-56 (contrato ampliado) → TI-56 + P-07/P-21 (WP) → TI-49/57 só com P-04/P-08 · F2: score, webhooks do RD, SSO com fornecedores |
| 🎨 **Vitrine** | (1) Das 17 telas só P07 e metade de P13 existem; P04, P05, P08, P14, P15, P17 e os 6 estados de elegibilidade não têm mockup (P-42); P04/P05 exigem sub-rotas que o shell hoje transforma em "Página não encontrada" (TI-23). (2) Navegação §3.1 diverge item a item (barra Início/Benefícios/Carteirinha/Meu valor/Mais × home/ben/clube/news/card; faltam Financeiro e Ajuda; "Meu valor" com flag forçada → DEC-24) e a busca não tem sugestões nem evento. (3) RNF: PWA inexistente (exige ADR por CSP e `no-store`), nenhuma medição de LCP/INP (animação de entrada com opacidade 0 é risco), axe ainda em WCAG 2.1 e só Chromium 390 px (spec: 2.2, Safari iOS, 360 px, alvos 44 px — `.botao` tem 42), fonte em px sem controle para um público 58 % acima de 51 anos; Verdana × Sora registrada (DIV-34). | PWA (manifest, SW, cache × `no-store`) · Medição de desempenho (laboratório no CI + RUM por `evento_uso`) · Preferências de acessibilidade do associado (fonte, movimento) e onde vivem · Aditivo à ADR-0017 se o Marketing exigir Verdana/paleta/botão verde · Vocabulário de estados na UI · Sub-rotas na SPA | hoje (fast-path): TI-61, 62, 63, 68, 65, 69 · decidir: DEC-24, 25, 28, 35, 27 → TI-60, 10 · Fase 3: contrato de `tipos.ts` → TI-21, 04, 22, 46 · Fase 3b: TI-27 · Fase 4: TI-38, 39, 40, 37, 41 (P-48 e P-42 antes do aceite) · transversal: TI-66, 67, 64 · Fases 5–6: P10/P11 (TI-87), trilha, clube; 7–8: P08, wallet |
| 📦 **Estivador** | (1) P-01 é P0 real: `origin.pem` venceu em 10/10 (autoassinado "TEMPORARIO-NAO-USAR-EM-PRODUCAO"), Cloudflare↔origem sem validação; com P-36 (`.env` sem cópia atual, 3 `.env.bak` no disco) e zero monitor externo desde 14/09 são os três itens sem código mais urgentes. (2) Serviço de jobs não existe em nada: proposta loop Python in-process + `GET_LOCK` + `job_execucao` + `JOBS_APLICAR` dry-run (padrão `CRON_APLICAR` do totalpass), profile desligado, `TZ`, segredos em `.env.jobs`, conta própria no hub; 12 jobs mapeados por fase. (3) Backup confirmado via `aws`: RDS `mysql-producao` db.t4g.micro Single-AZ, retenção 7 d, PITR, snapshots diários, zero manuais, nenhum teste de restauração; homologação não existe ("staging" é a produção pública no mesmo RDS/IdP/CRM) → RDS separado por snapshot só quando a escrita no CRM chegar (DEC-30); backoffice/CSV/PWA/OpenAPI dependem de DEC-03/05/07/32 (recomendações: container separado + Cloudflare Access; upload no B06 em F1 e S3 presigned em F2; manifest + SW sem dado pessoal; `openapi.json` versionado). Recursos: 7,8 GiB com 4,9 GiB de limites somados — jobs (256M), homolog e backoffice cabem; `max_connections` do RDS compartilhado a confirmar. | Serviço de jobs · Backoffice: container separado, host próprio, Cloudflare Access, OIDC corporativo, usuário de banco próprio · Ambientes e promoção (dev → homolog → prod; CI valida, deploy pull-based) · Canal do CSV · Observabilidade (uptime externo, alerta próprio, RUM; sem terceiros por CSP) · PWA · Backup e restauração · OpenAPI versionado | hoje, sem código: EXT-26/TI-70 (cert), TI-73 (`.env`), TI-71 (catch-all), TI-72 (pós-reboot), EXT-29/TI-75 (uptime) · antes da Fase 3 no ar: DEC-29 → TI-01, 78, 74, 76 + P-59/P-60, TI-07, TI-68 · com a Fase 3/4: TI-75, 67, 77 + P-25; DEC-30 e TI-79 antes de `HUB_ESCRITA_HABILITADA=true` · backoffice: DEC-03/05 → P-65/P-62 → TI-80/81 · F2: DEC-07 → TI-66/82, jobs WP/score/resumo, S3, Multi-AZ/retenção |

## 15. Rastreabilidade (item da spec → IDs deste levantamento → nosso)

| Item da spec | TI | EXT | DIV / DEC | REQUISITOS / ADR / código |
|---|---|---|---|---|
| F0 gate (§15.1) | TI-02, 03, 06, 28, 76, 92 | EXT-10, 11, 16, 24, 25 | DEC-16, 17 | Fase 0; `evento_uso`; IdP + hub |
| F1 escopo protegido (§15.2) | §12.1–12.5 | §13 | DIV-17, 23, 27 | fases 1–4 do roteiro |
| P01 Acesso · ACE-01..05 | TI-05, 83 | EXT-19, 35 | DIV-01..03 · DEC-11, 12 | RF-AU-*; `login_associado` |
| P02 Início · HOM-01 · blocos 1–9 · ADM-05 | TI-29, 30, 33, 34, 40, 43, 04 | EXT-10, 11, 19, 05 | DIV-36 · DEC-21, 26 | RF-HO-*; `Inicio.tsx` |
| P03 Benefícios · CAT-02/03 | TI-29, 30, 31, 37, 38 | EXT-10, 05 | DIV-14, 18 · DEC-34, 35 | RF-BE-01..06; `sql/009` previsto |
| P04 Página do benefício · CAT-05 · SOL-01 · tipos 1–6 | TI-23, 24, 29, 31, 32, 39, 13 | EXT-02, 10, 12, 13 | DIV-08, 26 · DEC-04, 10 | RF-BE-07..10; ADR-0008/0009 |
| P05 Minhas solicitações · SOL-04 · §8.5 (criada…sem_retorno) | TI-14, 15, 16, 17, 21, 23, 50 | EXT-20, 02, 05 | DIV-15, 16, 24 · DEC-01, 02, 22 | RF-SO-*; ADR-0003; REQ §7 |
| P06 Meu valor · VAL-01/03 · §8.6 | TI-35, 36, 41, 54 | EXT-10, 17, 24 | DIV-23 · DEC-23 | RF-FA-*; flag `fatura_valor`; ADR-0007 |
| P07 Carteirinha · CAR-01..03 · WAL-01 | TI-45, 46, 47 | EXT-25, 37 | DIV-07, 13, 45 · DEC-09, 36 | RF-CA-*; `carteirinha.py`, `publico.py` |
| P08 Financeiro · INT-02 · FIN-01/03/04 | TI-49, 57, 20 | EXT-17, 24 | DIV-31 · DEC-14, 17 | RF-FA-05; ADR-0010; P-08 |
| P09 Clube · CLU-01..03 | TI-88, 32, 61 | EXT-13, P-11 | DIV-08 · DEC-10 | RF-CL-*; ADR-0009 |
| P10 Eventos · EVE-01/02 · CON-01 | TI-56, 87 | EXT-13, 34 | DIV-28 | RF-EV-*; ADR-0006 |
| P11 Notícias · NEWS-01 | TI-56, 87 | EXT-34, 13 | DIV-29 | RF-NE-*; ADR-0006; P-07, P-21 |
| P12 Trilha · TRI-01 | TI-43, 40 | EXT-10 | DIV-22 · DEC-21 | RF-ON-*; LA-21 |
| P13 Perfil · PER-02/03 · §11.6 | TI-25, 26, 27, 28, 09, 48, 90 | EXT-16, 19, 35 | DIV-05 · DEC-06, 26, 27 | RF-PE-*; ADR-0015; LA-15 |
| P14 Ajuda · AJU-01/02 | TI-20, 22, 09 | EXT-05, 08, 33 | DIV-27 | RF-SH-08 |
| P15 Notificações · NOT-02 | TI-18, 85, 91 | EXT-02 | DIV-10 · DEC-08 | ADR-0017 "sem sino" |
| P16 Comunidade · DIR-01, COM-01, MEN-01, ENC-01 | TI-89, 60 | EXT-18, P-11 | DIV-44 · DEC-24 | RF-CO-*; flag `comunidade_posts` |
| P17 Patrocínio · MZ-01 · CARD-01 | — | EXT-37 | — | flags `mensalidade_zero`/`patrocinio`; P-12 |
| B01–B13, perfis, 2FA, PAR-01 | TI-58, 59, 80, 81, 90, 03 | EXT-36, 31, 22, 15 | DIV-11, 17, 18 · DEC-03, 05, 16 | REQ L112 (fora de escopo) |
| §7.3 recomendação · REC-01 | TI-33 | EXT-10, 19 | — | RF-HO-05; LA-26 |
| §8.1–8.4 elegibilidade, carências, matriz, parâmetros | TI-29, 30, 42, 92 | EXT-10, 11, 19 | DIV-31 · DEC-14, 15 | — (ausente) |
| §11.1 modelo de dados | TI-02, 14, 25, 29, 35, 44, 56, 80, 86 | — | DIV-18, 19, 20 | REQ §6 |
| §11.2 eventos (28) · §11.2.1 níveis | TI-04, 05, 11, 67 | — | DIV-14 · DEC-34 | `app/uso.py`; ADR-0012 |
| §11.3 indicadores 1–14 · §11.5 painéis · §11.4 score | TI-44, 86, 75 | EXT-09, 25, 24 | DIV-32 · DEC-16 | — |
| §12 gatilhos A01–A20 · §12.3 | TI-18, 19, 53, 55, 42, 11, 13 | EXT-08, 33, 35, 24 | DIV-12, 30, 33 · DEC-18, 19, 20 | — (ausente) |
| §13.1 integrações (13) · INT-01 · F0-01/02/03/06 | TI-47..57 | EXT-13, 14, 19, 24, 32, 34, 35 | DIV-06, 29, 30, 33 · DEC-10, 17 | CONTRATO-HUB; ADR-0002/0006/0008/0009/0010 |
| §13.2 contrato de dados | TI-48, 49 | EXT-19, 24 | DIV-30, 31 | CONTRATO-HUB |
| §13.3 CSV plano B | TI-51, 54, 81 | EXT-15, 10 | DIV-04 · DEC-05, 19 | ADR-0014 |
| §14 RNF | TI-07, 10, 62..67, 70, 73..79, 84 | EXT-03, 04, 06, 07, 26..31 | DIV-09, 21, 34, 37..41 · DEC-07, 25, 27, 30..33 | RNF-01..22 |
| §15.3–15.5 governança, aceite, decisões pendentes | TI-06, 69 | EXT-11 | DEC-* | CLAUDE.md §4 |

## 16. Verificação desta rodada

Script de cobertura (scratchpad `verificar_cobertura.py`, executado em 2026-10-29) sobre este documento,
`spec-v2/INDICE-IDS.md` e `spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md`:

```
IDs da spec: 94 · eventos: 28 · TI: 92 · EXT: 38 · DIV: 46 · DEC: 36
OK: cobertura completa
```

Conferido: todo identificador da spec (P01–P17, B01–B13, A01–A20, códigos ACE/HOM/CAT/SOL/VAL/CAR/INT/FIN/
CLU/EVE/NEWS/TRI/PER/AJU/NOT/REC/WAL/PAR/ADM/DIR/COM/MEN/ENC/MZ/CARD/CON e F0-0n) e todo evento de §11.2
aparece no índice e aqui; os 8 status, os 6 tipos de ativação e os temas de integração/RNF aparecem aqui;
sem IDs duplicados; toda `TI-nn` tem camada, persona, repo, fase e tamanho; toda `EXT-nn` cita a `TI-nn` que
destrava e um `P-xx` existente em `PENDENCIAS.md`/`CONCLUIDO.md`; links relativos resolvem. Não foi feito
commit: `git status` mostra só documentação e skills (`CLAUDE.md`, `docs/`, `.claude/skills/`); nenhum arquivo
de código, migração, `.env` ou compose foi alterado.
