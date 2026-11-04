# Requisitos — Minha APM (área do associado)

## 0. Controle do documento

| Item | Valor |
|---|---|
| Versão | **0.2** (revisão para a especificação funcional v2 da agência; tarefa TI-06 do levantamento) |
| Data | 2026-10-30 (v0.1: 2026-10-17) |
| Autores | Sistemas TI (William) · Claude Code (Sentinela, Atlas, Maestro, Vitrine, Estivador, Integrador) |
| Fontes | **`docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md`** (especificação funcional v2 da agência, 30/09/2026 — transcrição fiel do PDF; identificadores em `docs/spec-v2/INDICE-IDS.md`) · **`docs/LEVANTAMENTO-TECNICO-spec-v2.md`** (leitura técnica de 29/10/2026: TI-nn, EXT-nn, DIV-nn, DEC-nn; análises por persona em `docs/spec-v2/personas/`) · plano de execução aprovado em 30/10/2026 (ondas 0–7; decisões DEC-01, 02, 04, 13, 22, 28, 29 e DEC-03 parcial) · `docs/SPEC-minha-apm.md` (protótipo navegável, 01/10/2026) · plano da Fase 0 (D-01..D-14) · código em `app/`, `frontend/`, `sql/000–007` (HEAD `6a20cbf`) |
| Documentos irmãos | `docs/PENDENCIAS.md` (P-01..P-65), `docs/CONCLUIDO.md`, `docs/adr/` (ADR-0001..0017; **0018..0022 criadas em 30/10/2026**), `docs/CONTRATO-HUB.md`, `docs/CUTOVER.md`, `docs/PROVISIONAMENTO.md`, `docs/ACESSO-CONSTRUCAO.md` |

**O que mudou da v0.1 para a v0.2.** A spec v2 da agência passou a ser a fonte **funcional**
do produto (fases F0–F3, páginas P01–P17, backoffice B01–B13, 6 tipos de ativação, 8 status de
solicitação, elegibilidade e carências, cálculo do valor, 28 eventos de uso, 20 gatilhos,
13 integrações, RNF). Este documento absorve o delta registrado em `LEVANTAMENTO §3–§11`:
§1 reconcilia fases e escopo (backoffice, P14, P06 v1 e notificações entram); §3 ganha os RFs
novos (BE-11.., SO-08.., FA-06.., FI, PE-10.., AJ, NO, CM, BO) e notas **"Revisão v0.2"** nos RFs
que a spec altera; §4 adota WCAG 2.2 AA, LCP/INP, PWA, OpenAPI, ambientes e backup; §5 acrescenta RD
Station, CSV do plano B e as ferramentas novas do hub; §6 reescreve o modelo de dados com a
numeração `sql/008..022`; §7 passa à máquina de **8 status**; §8 unifica o catálogo de eventos
com os nomes da spec; §9–§10 ganham preferências, consentimentos, direitos do titular e as 7 flags
novas; §11 marca as lacunas que a spec respondeu e aponta as DEC/DIV abertas; §12 cobre os RFs
novos. Nada aqui reabre decisão do usuário (lista em `.claude/skills/spec-minha-apm/SKILL.md`).

**Regra de precedência (v0.2).** (1) **Segurança** (Sentinela, `CLAUDE.md` Sessão 2) vence tudo.
(2) **ADRs e decisões do usuário** vencem a spec quando a alteram explicitamente (ex.: D-01
substitui `localStorage mapm.page` por URL real; D-14 mantém o CPF fora da área mesmo onde a
spec o cita). (3) A **spec v2** vence no **funcional**: regras, fases, status, eventos, gatilhos,
integrações. (4) Os **mockups da agência** vencem no **visual** (ADR-0017, `tokens.css`). (5) A
**SPEC antiga** (`docs/SPEC-minha-apm.md`) vale só para estrutura, texto e comportamento de UI
onde a v2 não detalha; seus números em R$ e contagens são placeholders e nunca chegam ao
associado (regra 19). Divergência nova entre spec v2 e nós vira `DIV-nn` no levantamento, não
mudança silenciosa. Textos marcados como **(proposta)** não existem em nenhuma das fontes e
dependem de validação (seção 11; textos finais em P-44).

**Decisões**

| # | Tema | Decisão (resumo) | Status | ADR |
|---|---|---|---|---|
| D-01 | Front-end | SPA React + Vite + TS, build em estágio Node, servida como estático pelo FastAPI; URLs reais em `/area/*` | Aceita | [0001](adr/0001-spa-react-vite-servida-pelo-fastapi.md) |
| D-02 | D365 leitura | Via `mcp_hub` (REST `/api/v1/ferramentas/{nome}`, `client_credentials`) | Aceita | [0002](adr/0002-d365-via-mcp-hub-leitura-e-escrita.md) |
| D-03 | D365 escrita | Extensão do `mcp_hub` com ferramentas de escrita tipadas; a área nunca fala com o Dataverse | Aceita (implementada no hub na Fase 2b; escrita desligada até P-29) | [0002](adr/0002-d365-via-mcp-hub-leitura-e-escrita.md) |
| D-04 | Solicitações | MySQL próprio (`solicitacao` + `solicitacao_evento`) + espelho no CRM via hub; status sincronizado por job | Aceita; **status revistos por D-15** | [0003](adr/0003-solicitacoes-mysql-proprio-com-espelho-crm.md) |
| D-05 | Grants | `UPDATE` por tabela de domínio (allowlist); trilhas append-only; `DELETE` nunca | Aceita | [0004](adr/0004-grant-update-por-tabela-sem-delete.md) |
| D-06 | Foto de perfil | `contact.entityimage` no CRM via hub, redimensionada no servidor (Pillow) | Aceita (Fase 2a) | [0005](adr/0005-foto-de-perfil-entityimage-redimensionada.md) |
| D-07 | Site WordPress | Leitura direta do MySQL `portal_apm` só por job, usuário RO novo, TLS se suportado, cache local | Aceita (mantida contra "API do WordPress" da spec, DIV-29) | [0006](adr/0006-site-wordpress-leitura-direta-com-cache-local.md) |
| D-08 | Mensalidade Zero / patrocínio / Meu valor | Feature flags desligadas até definição de negócio; UI existe oculta | Aceita; **flags novas por D-18** | [0007](adr/0007-feature-flags-para-patrocinio-e-fatura.md) |
| D-09 | TotalPass | Adesão lida do CRM via hub (`totalpass.adesao_consultar`) + deep-link `https://totalpass.apm.org.br` | Aceita | [0008](adr/0008-totalpass-leitura-via-hub-e-deep-link.md) |
| D-10 | Parceiros | Sob demanda, fora de escopo; nenhuma chamada HTTP a parceiro sem ADR própria | Aceita (tipo 2 da spec = solicitação local, DEC-04) | [0009](adr/0009-parceiros-fora-de-escopo.md) |
| — | ERP F&O | Somente leitura via hub, após parecer de licença (P-08), atrás de flag | Aceita | [0010](adr/0010-erp-somente-leitura-pos-parecer.md) |
| D-11 | Cookie de sessão | Cifrado e autenticado (Fernet/MultiFernet), nome `__Host-area` fora de `development` | Aceita (Fase 1) | [0011](adr/0011-cookie-de-sessao-cifrado.md) |
| D-12 | Analytics | Tabela própria `evento_uso`, gravada em transação própria, nunca derruba a resposta | Aceita | [0012](adr/0012-analytics-evento-uso-transacao-propria.md) |
| D-13 | CSP | Sem `'unsafe-inline'` em `script-src`/`style-src` no SPA; estilos dinâmicos por classe + custom properties via CSSOM | Aceita | [0013](adr/0013-csp-sem-inline-no-spa.md) |
| D-14 | Chave de integração | `contact_id` (GUID do contact) é a chave de integração; CPF nunca | Aceita (vale também para o CSV §13.3 e para o deep link de congresso: DIV-04, DIV-28) | [0014](adr/0014-chave-de-integracao-contact-id-nunca-cpf.md) |
| — | Troca de e-mail | Código no novo endereço + reautenticação recente no IdP (`idp_at`) | Aceita (2026-10-17, LA-05) | [0015](adr/0015-troca-de-email-com-codigo-e-reautenticacao.md) |
| — | Persona incompleta | Userinfo sem tipo ou situação → login recusado | Aceita (2026-10-17, LA-29) | [0016](adr/0016-persona-incompleta-recusa-login.md) |
| — | Visual | Mockups da agência como referência visual (Sora, cards de vidro, trilho); "sem sino até existir fonte" | Aceita (2026-10-20); divergência com §14 da spec registrada (DIV-34, P-43) | [0017](adr/0017-mockup-da-agencia-como-referencia-visual.md) |
| **D-15** | **Solicitações v2** | 8 status da spec já na `sql/010`; `sem_retorno_desde` como coluna-marcador; atores e origens; conteúdo enviado = campos + sha256; avaliação 0–10 em colunas por 30 dias; cancelamento pelo associado só fora de `em_atendimento`; tipo 2 como solicitação local com canal manual (adenda à ADR-0003) | **Aceita (2026-10-30; DEC-01, 02, 04, 22)** | [0018](adr/0018-solicitacoes-v2-oito-status.md) |
| **D-16** | **Serviço de jobs** | `area-associado-jobs` com loop in-process, `GET_LOCK` por job, `job_execucao`, `JOBS_APLICAR` (dry-run), conta própria no hub | **Aceita (2026-10-30; DEC-29)** | [0019](adr/0019-servico-de-jobs-in-process.md) |
| **D-17** | **Limites de negócio** | Tetos diários por contagem no banco na própria transação; por minuto em memória; sem Redis | **Aceita (2026-10-30; DEC-13)** | [0020](adr/0020-limites-de-negocio-por-contagem-no-banco.md) |
| **D-18** | **Flags v2** | 7 chaves novas (`notificacoes`, `encaminhamento_parceiro`, `reservas`, `inscricoes`, `comunicacao_outbox`, `cancelamento_online`, `lgpd_consentimentos`); `fatura_valor` mantém a chave e muda o rótulo para "Meu valor" (adenda à ADR-0007) | **Aceita (2026-10-30; DEC-23)** | [0021](adr/0021-feature-flags-v2.md) |
| **D-19** | **Usuário de banco do backoffice** | `apm_area_bo` com `UPDATE` só em catálogo/configuração; `apm_area` (web) só leitura do catálogo; `db_check` com allowlist por usuário. Hospedagem e identidade do backoffice ficam para a Onda 6 (DEC-03 restante) | **Aceita (2026-10-30; DEC-03 parcial)** | [0022](adr/0022-usuario-de-banco-do-backoffice.md) |

> As ADRs 0018–0022 foram criadas na mesma rodada deste documento (30/10/2026; Onda 1 do
> `docs/PLANO-EXECUCAO.md`), junto com `sql/008_particao_eventos.sql` e `sql/009_flags_v2.sql`.
> D-11..D-14 seguem a numeração do plano da Fase 0; a ADR-0010 e as ADRs 0015–0017 registram
> decisões sem D-xx.

---

## 1. Visão e escopo

### 1.1 Objetivo e tese

Entregar a **Minha APM**: SPA autenticada (fases 1–2b já no ar em `minha.apm.org.br`) em que o
associado descobre, ativa e usa benefícios, acompanha cada solicitação até o resultado, vê o
valor individual que a associação entrega, mantém dados e preferências, porta a carteirinha
digital verificável, acompanha notícias, eventos e comunidades e resolve o financeiro e a ajuda
sem ligar. Para a APM, é a camada que transforma cada interação em dado: interesse, ativação,
uso confirmado, economia comprovada e sinais de permanência (spec:§1, §2).

Tese do produto (spec v2:§2–§3): **tudo começa aqui dentro** — na F1 toda ação começa na Minha
APM e gera um registro, mesmo quando termina em ambiente externo (encaminhamento rastreado); na
F2 o retorno de status e de uso passa a ser integrado. **Valor visível e honesto**: em reais só
o valor individual comprovado e a proteção incluída, separados do potencial e do estimado;
impacto coletivo nunca vira dinheiro somado. **Regra à vista**: o que está bloqueado mostra o
motivo e a data em que libera. **Medido desde o primeiro dia**: nenhuma funcionalidade vai ao ar
sem os eventos de uso instrumentados (`evento_uso`, seção 8). Nenhuma promessa de acesso único,
patrocínio, cashback, cartão ou economia aparece antes de contrato, prova técnica e regra de
negócio aprovados (spec:§2.2; regra 19).

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

**Rota inicial (revisão v0.2).** `GET /api/v1/sessao` continua devolvendo `rota_inicial`, mas o
valor é **sempre `/area`** (`app/api/v1/sessao.py:65`): a trilha de ativação deixa de ser rota de
entrada e vira bloco da home (spec:§7.2 bloco 3, P12; `LEVANTAMENTO` DIV-22, DEC-21). O campo fica
no contrato para não quebrar o front. Deep links (`/area/eventos`, etc.) continuam respeitados.

**Vocabulário de categoria (v0.2).** A spec v2 trabalha com quatro categorias — acadêmico,
aspirante, efetivo, **remido** (spec:§4.1) — e trata "residente" como aspirante (persona "Dra.
Camila"). O CRM entrega o **rótulo** `alf_tipo_associado` (tabela acima; "Correspondente" sem
equivalente na spec). O de-para rótulo → código fechado é dado (`TI-92`), provisório até o
vocabulário validado pelo negócio (EXT-11, P-49); a elegibilidade (§3.3 RF-BE-12), a matriz
benefício × categoria e os indicadores usam o código. Ex-associado e não associado (spec:§4.1)
**não entram** na área: o gate do IdP os barra; a página de retorno do ex-associado é do IdP
(DEC-11) e o lead vai ao RD/CRM sem CPF na área (DEC-19).

### 1.2b Fases da spec v2 × fases do roteiro

A spec organiza a entrega em F0–F3 (spec:§5.2, §15); o roteiro técnico (`docs/PENDENCIAS.md`,
"Roteiro por fase") em fases 1–8, agora distribuídas em sete ondas (`docs/PLANO-EXECUCAO.md`).
Reconciliação (`LEVANTAMENTO §2.1`):

| Spec | O que inclui | Nosso roteiro | Situação (30/10/2026) |
|---|---|---|---|
| **F0** gate de fundação (spec:§15.1) | base conciliada com identificador canônico; fonte de autenticação e situação comprovada; catálogo inicial com regras e carências validadas; contrato de dados e medição por parceiro; destino dos eventos, acessos e critérios de LGPD | Fase 0 (docs) + o que as fases 1–2b provaram | **parcial**: identificador canônico ✅ (`contact_id`, ADR-0014); autenticação e situação ✅ (OIDC + escopo `carteirinha`, ADR-0016); catálogo validado ⛔ (P-48); contrato por parceiro ⛔ (P-50, P-53); destino dos eventos 🟡 (`evento_uso` existe; ferramenta de painel DEC-16/P-47; consentimentos e retenção P-54) |
| **F1** escopo protegido (spec:§15.2) | P01, P02, P03/P04, P05, P06 v1, P09, P13/P14, backoffice B01–B06, B12, B13; P07 e P08 condicionais ao gate técnico | fases 1, 2a, 2b (feitas: shell, sessão, perfil, carteirinha) + **3** (solicitações, P14, outbox produzida) + **3b** (P13) + **4** (catálogo, elegibilidade, home em blocos, Meu valor v1, trilha como bloco) + **backoffice** (sem fase; Onda 6, DEC-03) | em andamento; P07 passou no gate técnico (hub real desde 21/10); P08 segue ⛔ (P-04, P-08, P-58) |
| **F2** comportamento e integrações | tipos 4–6, P10, P11, P12 completa, P15, clube integrado (CLU-01..03), wallet, recomendação v2, A07–A15, A19, A20, Qualicorp, eventos/IESAPM, WordPress/MBE, WhatsApp/SMS | 5 (notícias/eventos), 6 (clube, comunidade, trilha completa), 7 (ERP), 8 (wallet), Onda 7 | não iniciadas; tabela `notificacao` nasce já na Fase 3 (produção), API só na F2 |
| **F3** | P16 comunidade (DIR/COM/MEN/ENC), P17 patrocínio e cartão, CON-01 congresso nativo | 6 (comunidade) e 8 (patrocínio) | não iniciadas; P17 só com contrato (P-12); ENC-01 só com parecer (P-55) |

**Gate F0 na prática.** Item do gate não cumprido ⇒ a funcionalidade entra **apenas como
encaminhamento rastreado**, nunca como integração, uso confirmado ou promessa de economia
(spec:§15.1). Na área isso se traduz em: tabela vazia + tela em construção (catálogo), flag
desligada (valor, financeiro), solicitação local sem canal externo (tipo 2), interesse local
(tipo 5) e link rastreado (tipos 1 e 6) — ver §3.3 RF-BE-13.

### 1.3 Escopo e fora de escopo nesta versão

**Entra no escopo com a v0.2** (não estava na v0.1):

- **Backoffice B01–B13** (spec:§9) deixa de ser "fora de escopo": a área **guarda e expõe** o que
  cada módulo precisa (§3.18, RF-BO-*), com usuário de banco próprio `apm_area_bo` (D-19,
  ADR-0022). Hospedagem, identidade e 2FA ficam para a Onda 6 (DEC-03 restante, P-65, P-62);
  até lá vale o caminho sem backoffice (`LEVANTAMENTO §4.3`): operador por SQL com
  `beneficio_versao`/`backoffice_auditoria` por script administrativo.
- **P14 Ajuda e atendimento** (FAQ, canais, formulário, cancelamento com motivo) — Fase 3
  (§3.15, RF-AJ-*; DIV-27).
- **P06 Meu valor v1** — antecipado da Fase 8 para a **Fase 4** (estrutura `uso_valor` +
  `valor_referencia`; comprovado = solicitações concluídas + importações; proteção incluída);
  só "N vezes o que você pagou" segue sem fonte (DIV-23, DEC-23).
- **P15 Notificações in-app**: tabela e produção na Fase 3, API e sino na F2 atrás de
  `notificacoes` (DEC-08, DIV-10).
- **Motor de elegibilidade e carências** (spec:§8.1–8.4), **recomendação v1** (§7.3), **home em
  blocos** (§7.2), **tipos de ativação 1–6** (P04), **trilha por evento real** (P12) — Fase 4.
- **Preferências, consentimentos versionados e direitos do titular** (P13) — Fase 3b.
- **Comunicação**: outbox produzida na transação de negócio (Fase 3), RD Station como consumidor
  (Fase 3b, `RD_MODE=stub` até P-46), transacionais por SMTP (P-27).
- **Importação do CSV do plano B** (spec:§13.3) com CPF resolvido **no hub** (DIV-04, DEC-05).
- **Serviço de jobs** (D-16, ADR-0019).

**Continua fora de escopo** (ou só como hipótese desligada):

- Regras de negócio do patrocínio, cashback e cartão (P17, F3): flags `mensalidade_zero`,
  `patrocinio` forçadas desligadas até contrato (P-12, EXT-37).
- Wallet Apple/Google (flag `wallet`, F2/Fase 8, P-13).
- Integração HTTP com parceiros, SSO com fornecedores (MBE, biblioteca, Clube Certo, IESAPM) e
  retorno de resgate/inscrição: só por ADR própria por parceiro (D-10; P-50, P-51). Em F1, tipo 1
  e tipo 6 = link rastreado; tipo 2 = solicitação local com canal manual; tipo 5 = interesse.
- Segunda via de boleto, linha digitável e Pix (P08): **fonte inexistente** (o F&O via OData não
  expõe boleto); depende do "novo sistema de cadastro e cobrança" (P-58, DEC-17). Qualquer
  escrita no ERP.
- Comunidade (P16, F3): diretório e grupos moderados primeiro; rede de encaminhamento só com
  parecer jurídico (P-55). Posts ("CONVERSAS EM DESTAQUE") sob `comunidade_posts` desligada. Rota
  fora do menu antes da fase (DEC-24).
- Web Push (só com consentimento, SW restrito e ADR — DEC-08); Service Worker em geral (PWA é
  manifest-only, DEC-07).
- Script de analytics de terceiro na SPA (Clarity/GA): incompatível com a CSP (ADR-0013); RUM
  próprio em `evento_uso` (DIV-32).
- Login próprio, "continuar conectado", nascimento no primeiro acesso, OTP por celular, "meus
  dados mudaram", página de retorno do ex-associado: tudo é **backlog do IdP** `login_associado`
  (TI-83; DIV-01..03), não desta área.
- Busca por CPF no backoffice (DIV-11), CPF no deep link do congresso (DIV-28), lead com CPF na
  área (DEC-19): nunca (ADR-0014).
- App mobile nativo (`appapm`) e site institucional: só fontes ou destinos de link.

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
Endpoints sem prefixo são relativos a `/api/v1`. `[C]` = exige CSRF (RF-AU-05); `[F:x]` = flag;
`[L:n/janela]` = limite por associado. "Fase" é a do roteiro (1–8, 3b, BO = backoffice, F2 =
sem fase ainda); a fase da spec (F0–F3) está na seção 1.2b. Blocos **"Revisão v0.2"** marcam o
que a spec v2 altera em RFs da v0.1; o RF original fica como histórico e descrição do protótipo.
`pagina_ver` é emitido em toda troca de rota (RF-SH-01) e não é repetido em cada RF.

**Mapa de rotas (D-01: URL real substitui `localStorage mapm.page`; revisado para a navegação
§3.1 da spec v2 e DEC-24).**

| Rota | Página da spec v2 | Título (h1 e menu) | Bottom-nav | Fase | Observação v0.2 |
|---|---|---|---|---|---|
| `/area` | P02 | Início | sim ("Início") | 1 (casca) / 4 (blocos) | home em blocos (RF-HO-12) |
| `/area/beneficios` | P03 | Benefícios | sim ("Benefícios") | 4 | filtros Todos / Disponíveis para mim / Ativos / Novos (RF-BE-16) |
| `/area/beneficios/{slug}` | P04 | Página do benefício | — | 4 | sub-rota nova (RF-BE-11; TI-23) |
| `/area/carteirinha` | P07 | Carteirinha digital | sim ("Carteirinha") | 2 ✅ | download e número na Fase 3 (RF-CA-07) |
| `/area/meu-valor` | P06 | Meu valor (título "Extrato de valor") | sim ("Meu valor"), só com `fatura_valor` ligada | 4 (v1) | **renomeada** de `/area/fatura` "Fatura de valor" (DEC-23); chave da flag mantida |
| `/area/financeiro` | P08 | Financeiro | não ("Mais") | 7 (flag `erp_financeiro`) | declarações já na Fase 3 como solicitação (RF-FI-04) |
| `/area/solicitacoes` | P05 | Minhas solicitações | não ("Mais") | 3 | — |
| `/area/solicitacoes/{uuid}` | P05 | Detalhe da solicitação | — | 3 | sub-rota nova (TI-23) |
| `/area/clube` | P09 | Clube de vantagens | não ("Mais") | 6 | encaminhamento rastreado (RF-CL-06) |
| `/area/eventos` (+ `/{id}`) | P10 | Eventos | não ("Mais") | 5 | — |
| `/area/noticias` | P11 | Notícias e ciência | não ("Mais") | 5 | — |
| `/area/perfil` | P13 | Perfil e privacidade | não ("Mais") | 2 ✅ / 3b | título muda de "Meu perfil" |
| `/area/ajuda` | P14 | Ajuda | não ("Mais") | 3 | rota nova (RF-AJ-*) |
| `/area/notificacoes` | P15 | Notificações | não | F2 (flag `notificacoes`) | sino só com aceite visual (DIV-10) |
| `/area/comunidade` | P16 | Comunidade | não | 6 (F3) | fora do menu antes da fase (DEC-24) |
| `/area/onboarding` | P12 | Trilha de ativação | não | 4 (bloco na home) / 6 (completa) | deixa de ser rota inicial; conteúdo vira bloco 3 da home (RF-ON-12); rota fora do menu até a trilha completa |
| — | — | Sair | item do "Mais" / sidebar | 1 ✅ | RF-AU-07 |

Barra inferior (< 900 px): **Início, Benefícios, Carteirinha, Meu valor, Mais** (spec:§3.1);
enquanto `fatura_valor` estiver desligada a barra tem **4 abas** (DEC-24) e "Mais" abre o drawer
com Financeiro, Minhas solicitações, Clube, Eventos, Notícias e ciência, Perfil e privacidade,
Ajuda e Sair. Rota sem página implementada **some do menu** no cutover (DEC-24; a tela
`EmConstrucao` é aceita só durante a construção, ADR-0017 §3). Reordenação do shell = TI-60.

**Contrato de erro da API** (todas as rotas `/api/`): corpo `{"erro", "mensagem", "request_id",
"detalhes"?}`; códigos `400 entrada_invalida`, `401 nao_autenticado`, `403 csrf_invalido |
nao_permitido | reautenticacao_necessaria`, `404 nao_encontrado | recurso_desligado`,
`409 estado_invalido | endereco_indisponivel | nao_elegivel | ja_avaliada | prazo_expirado |
versao_desatualizada`, `413`, `415`, `429 limite_taxa`, `503 fonte_indisponivel`. A SPA exibe
`mensagem` em toast (RF-SH-09). `409 nao_elegivel` traz `detalhes {estado, libera_em}`
(spec:§10.2 "o sistema não deixa solicitar e mostra quando libera"). Toda lista devolve
`itens: []` + `vazio {titulo, texto, acao?}` definido pelo servidor (texto editável em
`texto_sistema`, B07) para a SPA não inventar frase (spec:§15.4).

**Limites por associado (D-17, ADR-0020).** Tetos **diários** de negócio (solicitação `outro`
5/dia, 1 pedido de cancelamento aberto, 1 avaliação por solicitação, dispensa de recomendação
20/dia, exportação LGPD 1/7 d) são contados **no banco, na própria transação**, exatos e
compartilhados entre workers; abuso **por minuto** (uso, busca, pergunta de perfil) segue em
memória por processo (`app/limites.py`). Sem Redis. Notação nos RFs: `[L:n/janela]`.

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
- **UI:** ativo fundo `--green-600` peso 700; item "Onboarding acadêmico" visível só para tipo Acadêmico (LA-21). Item "Minhas solicitações" mostra contador de solicitações em `pendente_associado` (RF-SO-07); o item "Onboarding acadêmico" deixa de existir quando a trilha vira bloco (RF-ON-12, RF-SH-16).
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
- **Revisão v0.2 (spec:§3.1, P03; `LEVANTAMENTO` DIV-25, DEC-34):** a busca passa a ser **no servidor** e cobre cinco fontes — benefícios, parceiros, eventos, notícias e perguntas frequentes — com sugestões enquanto digita. `GET /busca?q=&limite=` `[L:30/min]` devolve `{beneficios[], parceiros[], eventos[], noticias[], faq[], total}`; sugestões = mesma rota com `limite=5`; `q` com 2–80 caracteres, normalizado sem acento e caixa. A filtragem no cliente de `ben`/`news` continua válida como atalho dentro da página. `busca_global` **continua sem o termo**; o termo entra só quando `total = 0`, em `busca_sem_resultado` **sem identidade** (RF-SH-14). Componente `Combobox` acessível no shell (TI-37; Fase 4, depois de TI-20 e TI-31).

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

**RF-SH-14 — Busca sem resultado (ajuste de catálogo)**
- **Descrição:** quando `GET /busca` devolve `total = 0`, o servidor grava o termo normalizado (≤ 48 caracteres, só letras, dígitos e espaço) em `busca_sem_resultado` **sem `contact_id`, sem `request_id` e sem `sub_hash`** — é insumo para "busca sem resultado vira ajuste de catálogo" (spec:§6 P03 "Casos especiais"; §11.2 `busca`), não analytics por pessoa. A resposta sugere categorias.
- **Fonte:** `busca_sem_resultado` (append-only, `sql/016`) · **Endpoint:** `GET /busca` · **Evento:** `busca_global` (ui; `resultados=0`, sem termo) · **Flag:** — · **Fase:** 4
- **UI:** estado vazio com as 8 categorias como atalhos (RF-BE-06).
- **Aceite:** teste de contrato garante que a linha gravada não tem coluna de identidade; termo com CPF ou e-mail é recusado pela allowlist de caracteres antes do INSERT; purga por retenção (P-15/P-54). Divergência com RNF-16 aceita e registrada (DIV-14, DEC-34).

**RF-SH-15 — Parâmetros de campanha (UTM e código do gatilho)**
- **Descrição:** links da régua chegam com `utm_*` e `g=A01..A20` (spec:§12.1, §12.3 "todo link com UTM e código do gatilho"). A SPA lê os parâmetros **uma vez** no boot, valida contra um catálogo fechado (`frontend/src/lib/campanha.ts`), remove-os da URL (`history.replaceState`) e anexa `detalhes.gatilho` (regex `^A(0[1-9]|1[0-9]|20)$`) ao `pagina_ver` de entrada e ao primeiro `beneficio_abrir`; o servidor revalida. Parâmetros fora do catálogo são descartados; nenhum texto livre entra em `evento_uso`.
- **Fonte:** URL de entrada · **Endpoint:** `POST /uso` · **Evento:** `pagina_ver`/`beneficio_abrir` com `detalhes.gatilho` · **Flag:** — · **Fase:** 4 (TI-11; catálogo real com P-46)
- **UI:** invisível ao associado.
- **Aceite:** `safe_next` continua recusando esquema, `//` e `\` mesmo com query; teste cobre `g=` inválido descartado e `utm_*` nunca persistido.

**RF-SH-16 — Navegação v2 e aba "Mais"**
- **Descrição:** sidebar e barra inferior seguem a ordem da spec (§3.1): Início, Benefícios, Carteirinha, Meu valor, **Mais** → Financeiro, Minhas solicitações, Clube de vantagens, Eventos, Notícias e ciência, Perfil e privacidade, Ajuda, Sair. "Mais" abre o drawer existente (RF-SH-05). Rota cuja página não existe some do menu (`rotaVisivel` por implementação); Comunidade e Trilha ficam fora do menu antes da fase. Com `fatura_valor` desligada a barra tem 4 abas (DEC-24).
- **Fonte:** `GET /sessao` (flags) · **Endpoint:** — · **Evento:** `pagina_ver` · **Flag:** item "Meu valor" sob `fatura_valor`; "Financeiro" sob `erp_financeiro`; "Notificações" sob `notificacoes` · **Fase:** 3 (TI-60)
- **UI:** visual do trilho em pílula e do drawer do mockup (ADR-0017) mantidos; marca no topo fixo da spec **não** é adotada (DIV-43).
- **Aceite:** e2e confere a ordem dos itens, a ausência de rota sem página e o comportamento de 4 × 5 abas conforme a flag; axe sem violações no drawer.
---

### 3.2 Início (HO) — `/area` (P02)

> **Revisão v0.2 da home (spec:§7, P02; `LEVANTAMENTO §3.2`, §5.6).** A home deixa de ser a
> sequência fixa de cards do protótipo (RF-HO-02..HO-11) e passa a ser montada **pelo servidor**
> em blocos com regra de exibição (RF-HO-12). Os RFs HO-02..HO-11 continuam válidos como
> descrição dos **conteúdos** que alimentam os blocos: HO-02 (Mensalidade Zero) e HO-03 (Meu
> valor) viram o bloco 2; HO-04 (Congresso) entra no bloco 7 Agenda; HO-05 (Recomendados) vira o
> bloco 4 com a pontuação do §7.3 (RF-BE-17), não mais seleção editorial; HO-06/HO-08 (tiles) viram
> o bloco 5 Categorias com as 8 categorias da spec; HO-07 e HO-11 (diagnóstico, submeter trabalho)
> viram benefícios do catálogo (tipo 2/3) ou chamada do bloco 8; HO-09 ("Como funciona") aparece
> só no primeiro acesso; HO-10 (Notícias) vira o bloco 8 (F2). Textos com patrocínio seguem sob
> `mensalidade_zero`/`patrocinio`.

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

**RF-HO-12 — Home em blocos (`GET /inicio`)**
- **Descrição:** `GET /inicio` devolve `{blocos: [{id, posicao, conteudo}], avisos[]}` com **só os blocos que têm conteúdo**, na ordem fixa do servidor (spec:§7.2): 1 Pendência · 2 Meu valor · 3 Próximo passo · 4 Recomendados · 5 Categorias · 6 Defesa e representação · 7 Agenda · 8 Notícias (F2) · 9 Clube (F2). Fonte indisponível em um bloco ⇒ bloco omitido + item em `avisos[]`; a home nunca cai por causa de um bloco. Um único botão principal por bloco; no máximo uma recomendação patrocinada entre as quatro primeiras; "bloco sem conteúdo não aparece, nada de em breve" (spec:§3.2).
- **Fonte:** `app/dominio/inicio.py` (`montar(perfil)`), que chama `elegibilidade`, `valor`, `trilha`, `preferencias`, `recomendacao`, `destaque_editorial`, `evento_cache` · **Endpoint:** `GET /inicio` · **Evento:** `pagina_ver` (rota `/area`, `detalhes.blocos[]` = ids exibidos, `segmento`), `home_bloco_clicar` (ui: `bloco`, `posicao`, `item`) · **Flag:** bloco 2 sob `fatura_valor`; blocos 8/9 F2 · **Fase:** 4 (TI-34, TI-40)
- **UI:** `BlocoHome` com skeleton e erro por bloco; saudação "Olá, {nome}" com tratamento do perfil (DEC-26: até existir "como prefere ser chamado", sem "Dr./Dra."); atalho da carteirinha e busca no topo.
- **Aceite:** teste de tabela de `inicio.montar` cobre cada regra de exibição; e2e com hub em falha mostra a home sem o bloco dependente e com aviso; `detalhes.blocos` validado por enum no servidor.

**RF-HO-13 — Bloco 1 · Pendência**
- **Descrição:** um card quando há algo que exige ação, na prioridade da spec: pagamento em atraso → documentação pendente → solicitação em `pendente_associado` → benefício liberado pela carência nos últimos 7 dias → renovação em até 30 dias.
- **Fonte:** `solicitacao` (✓ local), `carencia_vencer` (✓ calculado de `data_filiacao` × catálogo), `associado_financeiro` (⛔ P-04/P-08), documentação pendente (⛔ campo do CRM, P-56), renovação (⛔ P-58) · **Endpoint:** `GET /inicio` · **Evento:** `home_bloco_clicar` · **Flag:** — · **Fase:** 4 (fontes locais); 7 (financeiro)
- **UI:** CTA único ("Responder", "Ver benefício", "Segunda via" quando existir).
- **Aceite:** sem fonte financeira o bloco nunca afirma atraso; com duas pendências aparece só a de maior prioridade.

**RF-HO-14 — Bloco 3 · Próximo passo**
- **Descrição:** nos primeiros 90 dias de filiação, o passo da trilha de maior valor ainda não feito (RF-ON-12); depois, **uma pergunta de perfil por visita** (perfil progressivo, RF-PE-11). Some quando não há passo nem pergunta.
- **Fonte:** `trilha_passo` × `trilha_progresso`; `pergunta_perfil` × `perfil_declarado` · **Endpoint:** `GET /inicio` (+ `POST /perfil/pergunta/{chave}`) · **Evento:** `home_bloco_clicar`, `perfil_declarado_atualizar` · **Flag:** — · **Fase:** 4 (trilha) / 3b (pergunta)
- **UI:** `CardProximoPasso` / `PerguntaPerfil` (mesmo componente do perfil).
- **Aceite:** associado com > 90 dias e perfil completo não vê o bloco; responder a pergunta remove-a da próxima visita.

**RF-HO-15 — Bloco 6 · Defesa e representação e destaque editorial (ADM-05)**
- **Descrição:** uma atualização principal (ação, conquista, consulta, conteúdo ou serviço de defesa relevante para a especialidade ou regional) com atalho "acompanhar"/"solicitar apoio"; **nunca converte impacto coletivo em valor financeiro** (spec:§7.2 bloco 6, §2.1). O destaque editorial ADM-05 é um aviso por segmento, com vigência, na posição 2, **um por vez** (`UNIQUE (segmento, vigência)`).
- **Fonte:** `destaque_editorial` (B07, editado pelo backoffice; até lá operador por SQL) · **Endpoint:** `GET /inicio` · **Evento:** `home_bloco_clicar` · **Flag:** — · **Fase:** 4 (estrutura); conteúdo por P-44/EXT-05
- **UI:** texto e link validados (host em allowlist, RF-SH-12).
- **Aceite:** dois destaques vigentes para o mesmo segmento são recusados pela constraint; destaque vencido some sem deploy.

**RF-HO-16 — Bloco 7 · Agenda**
- **Descrição:** até 3 eventos nos próximos 60 dias para a especialidade ou região, data mais próxima primeiro; congresso primeiro quando houver inscrição aberta (substitui o banner fixo de RF-HO-04).
- **Fonte:** `evento_cache` (Fase 5; sem cache o bloco não aparece) + especialidade/regional do perfil (P-56; até lá sem filtro) · **Endpoint:** `GET /inicio` · **Evento:** `home_bloco_clicar` · **Flag:** — · **Fase:** 5
- **UI:** `Agenda` com bloco de data (RNF-14).
- **Aceite:** eventos passados nunca aparecem; sem evento em 60 dias o bloco some.
---

### 3.3 Benefícios (BE) — `/area/beneficios` (P03) e `/area/beneficios/{slug}` (P04)

> **Revisão v0.2 de benefícios (spec:§6 P03/P04, §8.1–8.4; `LEVANTAMENTO §3.3–3.4`, §5.1–5.3).**
> O catálogo deixa de ser seed só `SELECT` e vira **dado** com ficha completa, vigência, carência,
> matriz por categoria, parceiro e valor de referência versionado (DIV-18; §6). "Ativar" deixa de
> ser um toggle genérico: **RF-BE-07/08 passam a valer só para o tipo 1** (acesso direto); os demais
> tipos geram solicitação, inscrição ou resgate rastreado (DIV-26, RF-BE-13). O chip "Patrocinados"
> (RF-BE-02) dá lugar a **"Disponíveis para mim"** (spec:§5.3); os 4 grupos de RF-BE-05 dão lugar às
> **8 categorias** da spec (LA-01 respondida). RF-BE-10 (TotalPass) continua como leitura via hub.

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

**RF-BE-11 — Página do benefício (P04)**
- **Descrição:** sub-rota `/area/beneficios/{slug}` com: nome, parceiro e o que é em uma frase; condição do associado comparada ao preço de referência (a economia); "como funciona" em até 4 passos; **quem tem direito e a situação dele** ("disponível para você desde DD/MM/AAAA" ou "libera em DD/MM/AAAA"); botão de ação conforme o tipo de ativação (RF-BE-13); perguntas frequentes, contato e regras; quanto já aproveitou neste benefício no ano (só com fonte, RF-FA-09); benefícios relacionados. A condição concreta tem destaque, não o logotipo do parceiro.
- **Fonte:** `beneficio` + `beneficio_faq` + `parceiro` + `valor_referencia` vigente + `uso_valor` do associado; `?origem=` validado por enum (home, catalogo, busca, email, trilha) · **Endpoint:** `GET /beneficios/{slug}` → ficha + `elegibilidade {estado, libera_em, motivo, desde}` + `aproveitado_ano` + `faq[]` + `relacionados[]` · **Evento:** `beneficio_abrir` (ui; `detalhes.origem`, `detalhes.estado`) — equivale ao `beneficio_visto` da spec · **Flag:** — · **Fase:** 4 (TI-31, TI-39)
- **UI:** `SeloEstado` com texto (nunca só cor), `BotaoAtivacao` por tipo, `Accordion` para FAQ/regras/como funciona; estados "exclusivo para associado efetivo", "regularize para voltar a usar", "libera em" com o que fazer até lá. Sem mockup (P-42): construído com os componentes do ADR-0017.
- **Aceite:** slug inexistente ou não publicado → `404`; `aproveitado_ano` omitido sem `uso_valor` nível 4; nenhum número de economia sem `valor_referencia` aprovada (regra 19).

**RF-BE-12 — Elegibilidade: seis estados**
- **Descrição:** para cada associado, cada benefício está em um de seis estados (spec:§8.1): **Disponível** (todas as condições), **Ativo** (já ativou ou usa), **Libera em N dias** (só falta a carência), **Não disponível para a categoria** ("exclusivo para associado efetivo" e como mudar), **Suspenso** (atraso passou do limite — "regularize para voltar a usar" e a segunda via), **Indisponível na região** (benefícios equivalentes, se houver). Disponível = categoria permitida ∧ `data_filiacao + carencia_meses ≤ hoje` ∧ situação financeira permite ∧ região atendida (se regional) ∧ vigente. Ordem de avaliação: vigência → categoria → região → financeiro → carência → ativo.
- **Fonte:** `app/dominio/elegibilidade.py` **puro** (`avaliar(perfil, beneficio, ativacoes, financeiro, hoje) → Elegibilidade(estado, libera_em, motivo, acao_sugerida)`); insumos `associado_perfil.tipo_associado` (+ de-para TI-92), `data_filiacao`, `regional_cod` (P-56; até lá região ignorada), `associado_financeiro.situacao` (P-04/P-08; até lá `financeiro=None` ⇒ permite e **"Suspenso" nunca ocorre**, DEC-14, documentado em "como calculamos"), `beneficio.{vigencia_*, carencia_meses, exige_adimplencia, regional}`, `beneficio_categoria_associado`, `beneficio_ativacao` · **Endpoint:** campos `estado` e `libera_em` em `GET /beneficios` e `GET /beneficios/{slug}`; `409 nao_elegivel {estado, libera_em}` na ativação · **Evento:** — · **Flag:** — · **Fase:** 4 (TI-30)
- **UI:** selo e texto por estado (rótulos da spec como proposta até P-44/DEC-35).
- **Aceite:** testes de tabela cobrem as 6 saídas e a ordem de avaliação; carência base = `data_filiacao` (DEC-15) com `parametro.carencia_reinicia_por_categoria=false`; mudança de parâmetro de carência no banco muda a resposta sem deploy.

**RF-BE-13 — Tipos de ativação 1–6 (estratégia por tipo)**
- **Descrição:** cada benefício tem `tipo_ativacao` configurado no catálogo (spec:§6 P04 "Tipos de ativação"); o tipo decide o que o botão faz e o que fica registrado. Regra comum: nos tipos 1–5 os dados do associado vêm do cadastro e ele só confirma — **o corpo da requisição não aceita dado pessoal**; não há cupom manual; a confirmação sempre mostra `prazo` e `proximo_passo`.

  | Tipo | Nome | Fase spec | O botão (F1) | Fica registrado | Flag |
  |---|---|---|---|---|---|
  | 1 | Acesso direto | F1 | `POST /beneficios/{slug}/ativar` → elegibilidade → `beneficio_ativacao` → `url_acesso` via redirecionador (RF-BE-15); "acesso único"/código pessoal só com ADR por parceiro (DIV-08) | ativação (nível 2); uso (nível 3) só se o parceiro devolver | — |
  | 2 | Encaminhamento ao parceiro | F1 | cria `solicitacao` (`beneficio_id`, `parceiro_id`, `tipo_ativacao=2`, `canal_envio` = `relatorio`/`email` na F1; `api`/`portal` F2); **nenhuma chamada HTTP a parceiro** (D-10); dados ao parceiro só com allowlist por benefício e aprovação do DPO (DEC-04) | solicitação com status até o resultado (§7) | `encaminhamento_parceiro` |
  | 3 | Serviço da APM | F1 | cria `solicitacao` de `tipo_servico` com responsável e prazo da ficha, `canal_envio=crm` | solicitação com responsável e prazo | — |
  | 4 | Reserva | F2 | `GET .../disponibilidade?de=&ate=` + `POST .../reservar` → `solicitacao(tipo_ativacao=4)` com período; exige fonte de disponibilidade (Hotel Fazenda, Residencial) | reserva e uso | `reservas` |
  | 5 | Inscrição | F2 | `POST /eventos/{id}/inscrever` com `perfil_preco` pela categoria; F1 = interesse local (RF-EV-05); carência de 3 meses pelo motor (RF-EV-06) | inscrição, presença e certificado (F2) | `inscricoes` (real) |
  | 6 | Resgate no clube | F2 | `POST /clube/ofertas/{id}/abrir` registra e devolve `url_externa` (RF-CL-06); retorno de economia só com integração (P-51) | resgate e economia vindos do clube (F2) | `clube_economia` (retorno) |

- **Fonte:** `app/dominio/ativacao.py` (estratégia por tipo) · **Endpoint:** `POST /beneficios/{slug}/ativar [C] [L:10/h]`: tipo 1 `{}` → `200 {estado, url_acesso, proximo_passo}`; tipos 2/3 `{campos?}` → `201 {solicitacao_id, status, prazo, proximo_passo}` (ou `200` idempotente); tipo 4 `{periodo}`; tipo 5 → redireciona a `/eventos`; tipo 6 → `200 {url_externa}` · **Evento:** `beneficio_ativar` (tipo 1), `solicitacao_criar` (`detalhes.tipo_ativacao`, `beneficio`) (tipos 2–4), `evento_inscrever` (5), `clube_oferta_usar` (6) · **Flag:** por tipo (tabela; D-18) · **Fase:** 4 (tipos 1 e 3; 2 após DEC-04 → aceita); F2 (4–6)
- **UI:** `BotaoAtivacao` com verbo (Ativar, Solicitar, Reservar, Inscrever) e `Dialogo` de confirmação com prazo e próximo passo nos tipos 2–4.
- **Aceite:** não elegível → `409 nao_elegivel` sem gravar nada; corpo com chave de dado pessoal → `400 entrada_invalida`; tipo com flag desligada → `404 recurso_desligado`; teste por tipo da estratégia.

**RF-BE-14 — Resumo, filtros e ordem do catálogo (v2)**
- **Descrição:** resumo no topo (**ativos, disponíveis, valor no ano** — este só com `fatura_valor` e fonte); filtros **Todos / Disponíveis para mim / Ativos / Novos**; ordem padrão: disponíveis e ainda não usados (maior afinidade primeiro, RF-BE-17) → ativos → os que liberam em breve; benefício fora da categoria aparece como "exclusivo para associado efetivo" com o caminho para mudar (spec:§6 P03). Substitui RF-BE-01/02/05 no que conflitar.
- **Fonte:** `beneficio` × elegibilidade × `recomendacao.pontuar` · **Endpoint:** `GET /beneficios?filtro=todos|disponiveis|ativos|novos&categoria=&q=` → `{resumo {ativos, disponiveis, valor_ano?}, categorias[], itens[{slug, titulo, condicao, selo, estado, libera_em, categoria, tipo_ativacao, cta}]}` · **Evento:** `filtro_aplicar` (ui) · **Flag:** `valor_ano` sob `fatura_valor` · **Fase:** 4 (TI-31, TI-38)
- **UI:** `BarraResumo` some sem fonte; `FiltroChips` com `aria-pressed`; `CardBeneficio` com condição em uma linha ("até 30% na mensalidade da escola de idiomas"), selo com texto e botão.
- **Aceite:** "Disponíveis para mim" = só estado Disponível; "Novos" = publicados há < 30 dias; contagens do resumo iguais ao que a lista mostra.

**RF-BE-15 — Redirecionador de acesso (`/api/v1/ir/{slug}`)**
- **Descrição:** todo link externo de benefício ou oferta sai pelo servidor: `GET /api/v1/ir/{slug}` (sessão obrigatória) valida elegibilidade, registra o acesso e responde `302` para a `url_acesso` **do catálogo** (host validado na migração contra `parceiro.host`); a SPA não conhece hosts de parceiro. `Cache-Control: no-store`, `Referrer-Policy: no-referrer`.
- **Fonte:** `beneficio.url_acesso`, `parceiro.host`, `oferta_clube.url` · **Endpoint:** `GET /api/v1/ir/{slug}` · **Evento:** `beneficio_acessar` (servidor, tipo 1) / `clube_oferta_usar` (servidor, tipo 6) com `detalhes.origem` · **Flag:** — · **Fase:** 4 (TI-32)
- **UI:** botão "Acessar" abre em nova aba com `rel="noopener noreferrer"`; `links.ts` reduzido ao mínimo.
- **Aceite:** slug sem URL ou URL fora da allowlist → `404`; nenhum `Location` montado a partir de entrada do cliente; identidade nunca vai na URL de destino (DIV-28).

**RF-BE-16 — Catálogo como dado (ficha B03)**
- **Descrição:** a ficha do benefício é registro em `beneficio` com nome, categoria, parceiro, descrição curta e longa, condição, preço de referência e regra de cálculo (`valor_referencia`), elegibilidade (categorias permitidas via `beneficio_categoria_associado`, `carencia_meses` 0–12, `exige_adimplencia`, `regional`), `tipo_ativacao` e destino, `prazo_retorno_dias`, selos (`novo`, `patrocinado`), imagens, FAQ (`beneficio_faq`), contatos, vigência, ordem, afinidade por segmento (`beneficio_afinidade`), `modalidade_mensuracao` (api_acesso_unico | relatorio_padrao | encaminhamento_sem_retorno), `sigiloso`; ciclo **rascunho → aprovado → publicado → encerrado** com histórico em `beneficio_versao` (spec:§9.2 B03, §10.1). A área (web) **só lê**; escrita pelo backoffice com `apm_area_bo` (D-19) ou, até lá, por script administrativo do operador.
- **Fonte:** `sql/016` · **Endpoint:** `GET /beneficios`, `GET /beneficios/{slug}` (só `publicado` e vigente) · **Evento:** — · **Flag:** — · **Fase:** 4 (TI-29); seed real só com P-48
- **UI:** —
- **Aceite:** `db_check` falha se `apm_area` tiver `UPDATE` em `beneficio`; benefício vencido some do catálogo na data; quem o tinha ativo recebe aviso (A15/outbox, F2); fixture de catálogo de teste para e2e, nunca publicada em produção.

**RF-BE-17 — Recomendação v1 por regras e "dispensar"**
- **Descrição:** pontuação por benefício disponível (spec:§7.3): afinidade com o segmento 0–3 (matriz editável, B08) · liberado pela carência nos últimos 30 dias +2 · página vista nos últimos 30 dias sem ativação +2 · novo no catálogo (< 30 dias) +1 · combina com tema seguido ou área de atuação +1 · patrocinado +1 (no máximo um entre os quatro primeiros, sempre sinalizado; vale 0 enquanto `patrocinio` estiver forçada desligada). Sai da lista: ativo ou usado, dispensado (60 dias), não disponível. Desempate pelo maior valor de referência; no máximo dois da mesma categoria; card exibido por 3 semanas sem interação perde prioridade; cada card traz "por que estou vendo isto" (`motivos[]`).
- **Fonte:** `app/dominio/recomendacao.py` **puro** (`pontuar(candidatos, sinais) → [Recomendacao(beneficio, pontos, motivos[])]`); sinais de `evento_uso` (`beneficio_abrir` 30 d por `entidade_id`), `beneficio_afinidade`, `recomendacao_dispensa` (append), `recomendacao_exposicao` (rotação) · **Endpoint:** embutido em `GET /inicio` (bloco 4, 3–6 cards) e na ordem de `GET /beneficios`; `POST /recomendacoes/{slug}/dispensar [C] [L:20/dia]` `{motivo?}` · **Evento:** `recomendacao_dispensar` (servidor; `detalhes.motivo`) · **Flag:** critério "patrocinado" sob `patrocinio` · **Fase:** 4 (TI-33); fase de carreira só com `faixa_carreira` do hub (P-56)
- **UI:** "Dispensar" como ação secundária em texto; "por que estou vendo isto" sempre disponível.
- **Aceite:** testes de tabela da pontuação; dispensado não volta em 60 dias; sem dado de saúde em nenhum sinal (spec:§7.5).
---

### 3.4 Clube de vantagens (CL) — `/area/clube` (P09)

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

**RF-CL-06 — Encaminhamento rastreado ao clube (tipo 6, F1)**
- **Descrição:** na F1 o acesso ao clube é um **encaminhamento rastreado** que não promete login único nem retorno de economia (spec:§6 P09). "Usar agora"/"Usar"/"Ver todas as ofertas" passam pelo servidor (`POST /clube/ofertas/{id}/abrir [C]` → `{url_externa}` ou redirecionador RF-BE-15), que grava o resgate iniciado. Vitrine com 30–40 ofertas curadas (seed `oferta_clube`, curadoria B10 na F2), oferta da semana e categorias; "economia no clube no ano" só quando houver dado de resgate (`uso_valor fonte=clube`, F2).
- **Fonte:** `oferta_clube` (`sql/020`), allowlist `PARCEIROS_HOSTS` (ADR-0009) · **Endpoint:** `GET /clube`, `POST /clube/ofertas/{id}/abrir [C]` · **Evento:** `clube_oferta_usar` (servidor; `detalhes.origem`) · **Flag:** `clube_economia` (economia e cashback) · **Fase:** 6 (TI-88); F2 para resgate com retorno
- **UI:** chamada do clube sem a palavra "cashback" (P17 só com contrato; TI-61).
- **Aceite:** URL externa só do seed; nenhum valor de economia sem `uso_valor`; evento gravado antes do `302`.
---

### 3.5 Notícias e ciência (NE) — `/area/noticias` (P11)

> **Revisão v0.2 (spec:§6 P11, F2).** Filtros passam a ser **tudo, notícias, ciência, defesa
> profissional, eventos**; conteúdo filtrado pelos temas seguidos **e pela especialidade** (quando
> P-56 entregar); fontes WordPress (ADR-0006 mantida, DIV-29), Portal MBE e biblioteca (sem fonte,
> P-51). Deixar de seguir tema entra na API (`POST /temas/{slug}/seguir|deixar [C]`, evento
> `tema_deixar`; LA-30 respondida). `noticia_abrir` ganha `detalhes.tema`; tempo de leitura opcional
> em `noticia_ler_tempo` (`segundos ≤ 3600`, lote no `pagehide`). RF-NE-01..07 permanecem.

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

### 3.6 Meu valor (FA) — `/area/meu-valor` (P06; flag `fatura_valor`; v0.1 "Fatura de valor", `/area/fatura`)

> **Revisão v0.2 (spec:§6 P06, §8.6, §11.2.1; `LEVANTAMENTO §3.6`, §5.5; DIV-23, DEC-23).** A tela
> passa a chamar-se **"Meu valor"** no menu e **"Extrato de valor"** no título ("Fatura de valor" se
> confunde com a fatura de cobrança do Financeiro); rota `/area/meu-valor`; a **chave da flag
> `fatura_valor` é mantida** (D-18). A spec coloca P06 v1 na **F1** e dá a fonte que faltava: o
> comprovado vem de solicitações concluídas, importações do plano B e proteção incluída — por isso a
> estrutura é **antecipada da Fase 8 para a Fase 4**, e `fatura_valor` sai de `FLAGS_FORCAR_DESLIGADAS`
> quando `valor.py` e uma `valor_referencia` aprovada existirem. Só "N vezes o que você pagou"
> (total pago) continua sem fonte (P-04/P-08/P-58). RF-FA-01..04 permanecem com a nomenclatura
> ajustada (`GET /valor`, `GET /valor/pdf`); RF-FA-05 segue para o total pago.

**RF-FA-01 — Card "Sua fatura de valor"**
- **Descrição:** h3 "Sua fatura de valor", subtítulo "{período} · economia comprovada item a item", total à direita e linhas (ícone, título, descrição, valor) — no protótipo: Coworking médico, Escriba de IA, Terapia subsidiada, Defesa profissional e seguros, Cursos e congresso.
- **Fonte:** cálculo sobre `beneficio_ativacao` × valor de referência do benefício (regra de valor por P-12) · **Endpoint:** `GET /fatura` · **Evento:** — · **Flag:** `fatura_valor` · **Fase:** 8
- **UI:** período × "no ano" em LA-11; moeda sem centavos quando inteiro.
- **Aceite:** soma das linhas = total; flag desligada → `404 recurso_desligado` e rota "não encontrada".

**RF-FA-02 — "Baixar PDF da fatura"**
- **Descrição:** gera PDF no servidor (sem dado do patrocinador; sem CPF) e entrega como download.
- **Fonte:** idem RF-FA-01 · **Endpoint:** `GET /fatura/pdf` (`Content-Disposition: attachment`, `no-store`) · **Evento:** ~~`fatura_pdf_baixar`~~ (retirada do catálogo em 30/10; ver RF-FA-08 `valor_pdf_baixar`) · **Flag:** `fatura_valor` · **Fase:** 8 → 4 (RF-FA-08)
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

**RF-FA-06 — Extrato de valor v1 (comprovado, proteção incluída, modos)**
- **Descrição:** `GET /valor?periodo=AAAA` devolve período (ano corrente e anteriores), **economia comprovada item a item** (data, benefício, economia, fonte, modalidade), **proteção incluída** em bloco separado (coberturas por ser associado, valor de referência anual proporcional aos meses de filiação ativa), total comprovado, valor por categoria (8 da spec), potencial rotulado como potencial (RF-FA-07) e `modo`: `relacao` (só quando total pago > 0 **e** comprovado + proteção > pago — exibe "N vezes"), `valor_entregue` (total pago = 0: "valor entregue pela associação" + composição do patrocínio, sem multiplicador) ou `o_que_cobre` (< 3 meses de casa). Estimado, potencial e impacto coletivo **nunca somam** ao comprovado.
- **Fonte:** `vw_meu_valor_ano` sobre `uso_valor` (**só `nivel_evidencia = 4`** soma ao comprovado) + `valor_referencia` vigente + `associado_perfil.data_filiacao`/`associado_categoria_hist`; total pago via hub `financeiro.*` (RF-FA-05, ⛔) · **Endpoint:** `GET /valor?periodo=` `[F:fatura_valor]` → `{periodo, total_pago?, comprovado {total, itens[]}, protecao {total, itens[]}, relacao?, por_categoria[], potencial[], metodologia, modo}` · **Evento:** `pagina_ver` (rota `/area/meu-valor`, `detalhes.periodo`) — equivale a `meu_valor_visto` · **Flag:** `fatura_valor`; `total_pago` também `erp_financeiro` · **Fase:** 4 (TI-35, TI-36, TI-41)
- **UI:** `SeletorPeriodo`, `Extrato`, `BlocoProtecao`, `ComoCalculamos` **sempre visível**, variantes por `modo`; número sempre com contexto (spec:§3.3).
- **Aceite:** testes de tabela de `valor.py` cobrem os três modos e a exclusão de níveis 1–3 e de `estimado`; soma dos itens = total; flag desligada → `404 recurso_desligado` e rota "não encontrada".

**RF-FA-07 — "Como calculamos" e valor potencial**
- **Descrição:** bloco permanente com a metodologia (spec:§8.6: economia por uso = referência − pago, por uso registrado; desconto informado pelo parceiro; serviço prestado pela APM = valor de referência do serviço; proteção incluída = referência anual proporcional; estimado nunca somado), a frase sobre situação financeira enquanto não houver fonte (DEC-14) e a lista de benefícios disponíveis que o associado ainda não usou com valor **rotulado como potencial**.
- **Fonte:** texto em `texto_sistema` (B07) + `valor_referencia` dos benefícios Disponíveis · **Endpoint:** `GET /valor` (`metodologia`, `potencial[]`) · **Evento:** — · **Flag:** `fatura_valor` · **Fase:** 4
- **UI:** potencial visualmente separado do comprovado; nunca na soma.
- **Aceite:** `potencial[]` vazio quando não há `valor_referencia` aprovada; texto da metodologia editável sem deploy.

**RF-FA-08 — PDF do extrato**
- **Descrição:** substitui RF-FA-02: `GET /valor/pdf?periodo=` `[L:5/h]` gera o extrato do período no servidor (sem CPF, sem dado do patrocinador além do valor coberto), `Content-Disposition: attachment`, `no-store`. PDF anual para a renovação (A10) é F2 (VAL-03).
- **Fonte:** idem RF-FA-06 · **Endpoint:** `GET /valor/pdf` · **Evento:** `valor_pdf_baixar` (servidor; ação nova que substitui `fatura_pdf_baixar`, retirada do catálogo — a segunda via de cobrança é outra ação, `fatura_segunda_via`, RF-FI-03) · **Flag:** `fatura_valor` · **Fase:** 4
- **UI:** toast "PDF do extrato gerado".
- **Aceite:** `run_in_threadpool`, ≤ 2 s p95; nome do arquivo sem dado pessoal.

**RF-FA-09 — Registro de uso e valor (`uso_valor`)**
- **Descrição:** toda evidência de uso com valor entra como linha **append-only** em `uso_valor` (`contact_id`, `beneficio_id`, `parceiro_id?`, `solicitacao_id?`, `importacao_linha_id?`, `data_evento`, `modalidade` ∈ {economia_uso, desconto_parceiro, servico_apm, protecao_incluida, estimado}, `nivel_evidencia` 1–4, `valor_referencia`, `valor_pago`, `economia`, `fonte` ∈ {apm, parceiro_api, importacao, clube, solicitacao}, `validado_em`); estorno é linha nova com `estorna_id`; validação do Financeiro é linha nova de nível 4 apontando a de nível 3 (`valida_id`). Níveis por origem (spec:§11.2.1): 1 visibilidade (`evento_uso`), 2 interesse/solicitação, 3 uso confirmado (solicitação `concluida_positiva`, importação sem validação), 4 valor comprovado (validado pelo Financeiro) — **só o 4 compõe a economia comprovada**.
- **Fonte:** `uso_valor`, `valor_referencia` (`sql/017`) · **Endpoint:** — (gravado por transição de solicitação, confirmação de importação, retorno do clube F2) · **Evento:** `uso_registrar` (servidor/job; `entidade_id` = `uso_valor.id`; `detalhes.fonte`, `nivel`; **sem valores** — dinheiro vive em `uso_valor`) · **Flag:** — · **Fase:** 4 (TI-35)
- **UI:** —
- **Aceite:** CHECK `economia = valor_referencia − valor_pago` quando os três existem; CHECK `nivel_evidencia = 4 ⇒ validado_em NOT NULL`; `db_check` confirma ausência de `UPDATE`/`DELETE` na tabela.
---

### 3.7 Comunidade (CO) — `/area/comunidade` (P16, F3)

> **Revisão v0.2 (spec:§6 P16, F3; `LEVANTAMENTO §3.16`; DIV-44, DEC-24).** A spec coloca a
> comunidade na **F3** com ordem própria: diretório de especialistas (DIR-01) e grupos moderados
> (COM-01) primeiro; mentoria (MEN-01) depois; rede de encaminhamento (ENC-01) só com parecer
> jurídico sobre dados de saúde (P-55). RF-CO-01..07 permanecem como descrição do protótipo para a
> Fase 6, mas a rota **sai do menu** antes da fase; RF-CO-05 (rede) e RF-CO-04 (posts) ficam
> condicionados a ENC-01 e `comunidade_posts`. Mentoria (RF-CO-06) continua como solicitação.

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

### 3.8 Eventos e congresso (EV) — `/area/eventos` (P10)

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

**RF-EV-06 — Inscrição como tipo 5, carência e deep link sem CPF**
- **Descrição:** "Inscrever" é o **tipo de ativação 5** (RF-BE-13): na F1 registra interesse local (RF-EV-05) e responde `{status: "interesse"|"inscrito", preco_perfil}` com o preço por perfil derivado da categoria (associado, acadêmico; não associado nunca entra na área); inscrição real só com a plataforma de eventos/IESAPM mapeada (P-51) atrás de `inscricoes`. Congressos e cursos de longa duração têm **carência de 3 meses**, avaliada pelo motor (RF-BE-12) com `evento.categoria_carencia` → `409 nao_elegivel {libera_em}`. Congressos grandes mantêm seus sites: a inscrição parte da área pelo redirecionador (RF-BE-15), **sem CPF nem identidade na URL** (DIV-28; o site do congresso vira RP do IdP ou o associado digita lá). Agenda filtrável por especialidade, região e formato; `GET /eventos/inscricoes` lista as do associado; certificados e aulas gravadas F2.
- **Fonte:** `evento_cache`, `evento_inscricao`, elegibilidade · **Endpoint:** `GET /eventos?especialidade=&regiao=&formato=`, `GET /eventos/{id}`, `POST /eventos/{id}/inscrever [C]`, `GET /eventos/inscricoes` · **Evento:** `evento_inscrever` / `congresso_garantir_vaga` (`detalhes.perfil_preco`) · **Flag:** `inscricoes` (inscrição real) · **Fase:** 5 (TI-87)
- **UI:** `CardEvento`, página do evento em sub-rota, "Inscrever" com verbo; sem evento → `vazio` do servidor.
- **Aceite:** associado com < 3 meses não consegue inscrever-se em evento com carência e vê a data; nenhum parâmetro de identidade no link externo (teste de allowlist).
---

### 3.9 Carteirinha digital (CA) — `/area/carteirinha` (P07)

**RF-CA-01 — Cartão**
- **Descrição:** card navy com logotipo, selo "MEMBRO", nome completo, "CRM-{UF} {número} · associad{a|o} desde {ano}", "válida até {MM/AAAA}" e QR (RF-CA-02).
- **Fonte:** claims `carteirinha` (P-09) e cache `associado_perfil` (`sol_st_numerocrm`, `alf_uf_crm`, `alf_data_filiacao`, `alf_sexo`) · **Endpoint:** `GET /carteirinha` · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** gênero de "associada/associado" por `alf_sexo` (LA-19; desconhecido → "associado(a)" proibido, usar "na APM desde {ano}" — proposta); sem CRM (acadêmico) a linha mostra só "na APM desde {ano}" (LA-20); "válida até" **omitido** até LA-04.
- **Aceite:** nenhum CPF no payload; hub indisponível sem cache → `503 fonte_indisponivel` com toast; com cache ≤ 24 h, exibe o cache.

**RF-CA-02 — QR de verificação**
- **Descrição:** QR (SVG gerado no cliente, sem biblioteca externa em CDN) com `https://minha.apm.org.br/verificar/{token}`; `token` = base32 de HMAC-SHA256(`CARTEIRINHA_HMAC_KEY`, `contact_id`) truncado a 20 caracteres, chave própria em `Settings` distinta de `SECRET_KEY` (ADR-0014), persistido em `associado.carteirinha_token` com índice único para busca.
- **Fonte:** `associado` · **Endpoint:** `GET /carteirinha` (campo `url_verificacao`) · **Evento:** — · **Flag:** — · **Fase:** 2
- **UI:** 64×64 branco, com texto alternativo "QR code de verificação da carteirinha" (proposta).
- **Aceite:** token não revela `contact_id`; rotação da chave invalida todos os QRs (documentado em `docs/CUTOVER.md`/runbook).

**RF-CA-03 — Verificação pública `/verificar/{token}`**
- **Descrição:** página HTML pública (Jinja2 `verificar.html`, sem SPA) que mostra **apenas** nome, status e validade (enquanto LA-04 aberta: status + "verificado em DD/MM/AAAA HH:MM"). Token desconhecido → página "Carteirinha não encontrada" (proposta) com 404.
- **Fonte:** `associado` (revogação e situação consultada) + `associado_perfil` (status); situação mais velha que `VERIFICACAO_CACHE_TTL` (600 s) → `associado.situacao` no hub com limite global de `VERIFICACAO_HUB_POR_MINUTO` (60) por processo; hub fora, sem grant ou limite → **fallback para o cache** e, passadas 24 h, página com "situação não confirmada no momento" (fail-closed no conteúdo: nunca "Ativo" a partir de cache vencido; **sem 503**, decisão da Onda 2 de 30/10); revogada → "carteirinha sem validade", sem motivo · **Endpoint:** `GET /verificar/{token}` · **Evento:** `carteirinha_verificar` (publico, `contact_id` do titular; sem dado do visitante) · **Flag:** — · **Fase:** 2
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

**RF-CA-07 — Baixar carteirinha e número de associado**
- **Descrição:** o cartão passa a exibir o **número de associado** (`num_contato`, já entregue pela API e não renderizado — DIV-45) e a palavra "Associado" no lugar do selo "Membro" (spec:§6 P07, §3.3). Botões "Baixar imagem" (`GET /carteirinha/imagem.png`, 1012×638, 300 dpi) e "Baixar PDF" (`GET /carteirinha/documento.pdf`, 85,6 × 54 mm), gerados no servidor (Pillow/segno, fonte Sora), `no-store` e `Content-Disposition: attachment`, `[L:10/h]` somando os dois formatos, `409 carteirinha_revogada` quando revogada; a imagem salva continua honesta porque o QR consulta a situação na leitura (RF-CA-08).
- **Fonte:** `associado_perfil`, `associado.carteirinha_token` · **Endpoint:** `GET /carteirinha/imagem.png`, `GET /carteirinha/documento.pdf` · **Evento:** `carteirinha_baixar` (servidor; `detalhes.formato` ∈ {png, pdf}) · **Flag:** — · **Fase:** 3 (TI-46)
- **UI:** botões com verbo; carteirinha "a um toque de qualquer tela" (atalho no topo da home).
- **Aceite:** arquivo sem CPF, e-mail ou telefone (PNG sem chunks de texto/EXIF/ICC; PDF com `/Info` genérico); só o dono baixa; sem `ETag`/`304` — cada download é gerado de novo e o QR consulta a situação na leitura (decisão da Onda 2).

**RF-CA-08 — Situação em tempo quase real e revogação**
- **Descrição:** a validação pública consulta a **situação no momento da leitura** e a filiação cancelada **revoga** a carteirinha (spec:§6 P07). `GET /verificar/{token}` passa a chamar `associado.situacao(contact_id)` no hub com cache curto (`VERIFICACAO_CACHE_TTL`, 5–15 min), limite global de chamadas a partir da rota pública (60/min por processo) e fallback "situação não confirmada" quando o hub não responde (fail-closed: nunca "Ativo" a partir de cache vencido). Job noturno de situação em lote preenche `associado.carteirinha_revogada_em` e rotaciona o token na reemissão; `GET /carteirinha` devolve `revogada` e `POST /carteirinha/compartilhar` responde `409` quando revogada. A página pública continua mostrando **só nome e situação** — sem categoria (DEC-36, DIV-07).
- **Fonte:** hub `associado.situacao` por `contact_id` sem CPF (TI-47, concedida à conta da área; cota em P-41) · **Endpoint:** `GET /verificar/{token}`, `GET /carteirinha` · **Evento:** `carteirinha_verificar` (publico; `detalhes.resultado` ∈ {ativo, inativo, nao_confirmado}) · **Flag:** — · **Fase:** 3 (TI-45, após TI-47; DEC-09)
- **UI:** estado "revogada" no cartão com orientação para a Central.
- **Aceite:** cancelado no CRM aparece "não confirmada"/"inativo" em ≤ TTL; hub fora → página 503 "verificação indisponível"; limite global impede que a rota pública esgote a cota do hub.
---

### 3.10 Trilha de ativação (ON) — bloco da home e `/area/onboarding` (P12; v0.1 "Onboarding acadêmico")

> **Revisão v0.2 (spec:§6 P12, §7.2 bloco 3; `LEVANTAMENTO §3.12`; DIV-22, DEC-21).** A trilha de
> ativação é para **todo novo associado e todo acadêmico**, com 5–6 passos **por categoria**;
> o passo é concluído **por evento real** (uso registrado, acesso feito), nunca por clique; a trilha
> some ao terminar ou no dia 90 contado de `data_filiacao`. Na F1 ela é um **bloco de 3 passos na
> home** (HOM-01); a rota própria e a trilha completa (TRI-01) são F2. Consequências: RF-ON-01
> deixa de definir rota inicial (`rota_inicial` é sempre `/area`); **RF-ON-05 e RF-ON-11
> (`POST .../concluir`) são substituídos por RF-ON-12** — não existe endpoint de concluir; RF-ON-04
> passa a ler `trilha_passo` por categoria; RF-ON-02/07 só exibem "mensalidade R$ 0 patrocinada" com
> `mensalidade_zero`; valores por passo viram `valor_referencia` aprovada (LA-12 respondida).
> RF-ON-08/09/10 continuam como conteúdo editorial da trilha completa (Fase 6).

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

**RF-ON-12 — Trilha por evento real (`GET /trilha`)**
- **Descrição:** `GET /trilha` devolve `{ativa, expira_em, passos[{slug, titulo, libera, libera_em, concluido_em, valor_referencia}], proximo}`; `ativa` = `data_filiacao + 90 d > hoje` e há passo pendente (ou categoria Acadêmico); `expira_em` = filiação + 90 dias (DEC-21). Passos vêm de `trilha_passo` (seed por categoria, com `evento_conclusao` e `carencia_meses` para "libera em"); a conclusão é gravada em `trilha_progresso` (append-only) por `trilha.avaliar(contact_id, acao, entidade_id)`, chamado **depois** de `uso.registrar` das ações mapeadas (`perfil_contato_atualizar`, `beneficio_ativar`/`beneficio_acessar`, `totalpass_abrir`, `pagina_ver(carteirinha)`/`carteirinha_baixar`, `evento_inscrever`, `solicitacao_criar`). O passo "perfil" vem concluído quando o cadastro está completo.
- **Fonte:** `trilha_passo`, `trilha_progresso` (`sql/020`) · **Endpoint:** `GET /trilha` (sem `POST concluir`) · **Evento:** `onboarding_passo_concluir` (servidor; `detalhes.dia_jornada`) — equivale a `trilha_passo` da spec · **Flag:** — · **Fase:** 4 (bloco) / 6 (completa) (TI-43)
- **UI:** `BarraProgresso` (`role="progressbar"`), `PassoTrilha` com "o que libera" e data de carência; bloco 3 da home mostra o passo de maior valor pendente (RF-HO-14).
- **Aceite:** ativar um benefício mapeado marca o passo sem ação da UI; trilha some no dia 90 ou ao concluir; teste garante ausência de rota `POST /onboarding/passos/*/concluir`.

**RF-ON-13 — Trilha parada e carência vencida (gatilhos A20, A03)**
- **Descrição:** 7 dias sem novo passo nos primeiros 90 dias ⇒ outbox A20 (F2); benefício liberado pela carência ⇒ `carencia_vencer` + notificação + bloco Pendência por 7 dias + outbox A03 (F1).
- **Fonte:** job diário `carencia_vencida` (`data_filiacao` × catálogo) e leitura de `trilha_progresso` · **Endpoint:** — · **Evento:** `carencia_vencer` (job; `detalhes.liberado_em`) · **Flag:** `comunicacao_outbox` (envio) · **Fase:** 4 (TI-42); A20 F2
- **UI:** card de pendência "a partir de hoje você tem…".
- **Aceite:** o job é idempotente (`UNIQUE (gatilho, contact_id, referencia_id)` na outbox); só associados com perfil em cache recebem.
---

### 3.11 Perfil e privacidade (PE) — `/area/perfil` (P13)

> **Revisão v0.2 (spec:§6 P13, §11.6; `LEVANTAMENTO §3.13`, §6.4).** A tela passa a chamar-se
> **"Perfil e privacidade"** e ganha: como prefere ser chamado, especialidades e área de atuação,
> região e temas de interesse, canais preferidos e frequência, consentimentos por finalidade com
> histórico, "baixar meus dados" e "pedir exclusão". RF-PE-01..09 permanecem (cadastro, contato,
> foto). **RF-PE-07 está superado:** a remoção da foto foi implementada na Fase 2a
> (`DELETE /api/v1/perfil/foto`, `app/api/v1/perfil.py:347`; LA-15 fechada). Tudo o que é novo nasce
> atrás de `lgpd_consentimentos` até os textos do jurídico (P-54) — Fase 3b.

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
- **Descrição:** **implementado na Fase 2a** (revisão v0.2; LA-15 fechada): `DELETE /perfil/foto [C]` limpa `entityimage` no CRM via hub `associado.foto_atualizar` (vazio) e a miniatura local; escrita desligada → `404 recurso_desligado`.
- **Fonte:** CRM via hub + `associado_perfil` · **Endpoint:** `DELETE /perfil/foto [C]` (`app/api/v1/perfil.py:347`) · **Evento:** `perfil_foto_atualizar` (`detalhes.removida=true`) · **Flag:** — · **Fase:** 2a ✅
- **UI:** botão "Remover foto" com confirmação.
- **Aceite:** após remover, o header volta às iniciais; hub fora → `503`, nada muda localmente.

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

**RF-PE-10 — Perfil declarado (preferências)**
- **Descrição:** campos que **não** vêm do CRM e vivem na área: tratamento ("como prefere ser chamado": padrão neutro; opções Dra./Dr./só o nome — DEC-26), área de atuação (consultório próprio, hospital, plantão, pesquisa, gestão, docência), região de interesse, temas (reusa `associado_tema`), canais preferidos (e-mail; WhatsApp e SMS **só quando existirem**, P-64 — regra 19) e frequência. Enums fechados; nenhum texto livre além do tratamento (≤ 40 caracteres, sem HTML).
- **Fonte:** `perfil_declarado`, `preferencia_canal` (`sql/019`) · **Endpoint:** `GET /perfil/preferencias`, `PUT /perfil/preferencias [C]` · **Evento:** `perfil_declarado_atualizar` (servidor; `detalhes.campos[]` = nomes, nunca valores) · **Flag:** `lgpd_consentimentos` (seção inteira) · **Fase:** 3b (TI-25, TI-26, TI-27)
- **UI:** "Complete seu perfil" dizendo o que melhora ("recomendações para a sua especialidade"); especialidade do CRM, quando o hub entregar (P-56), aparece como somente leitura ao lado da declarada.
- **Aceite:** valor fora do enum → `400 entrada_invalida`; `GET /sessao` passa a devolver `tratamento` para a saudação.

**RF-PE-11 — Perfil progressivo (uma pergunta por visita)**
- **Descrição:** em vez de formulário longo, o bloco 3 da home faz **uma pergunta por visita** (spec:§6 P13 "Regras"): `GET /perfil/pergunta` devolve a próxima pergunta não respondida do catálogo `pergunta_perfil` (ordem e condição por categoria) ou `null`; `POST /perfil/pergunta/{chave} [C] [L:10/dia]` grava a resposta em `perfil_declarado`.
- **Fonte:** `pergunta_perfil` (seed), `perfil_declarado` · **Endpoint:** `GET /perfil/pergunta`, `POST /perfil/pergunta/{chave}` · **Evento:** `perfil_declarado_atualizar` · **Flag:** `lgpd_consentimentos` · **Fase:** 3b
- **UI:** `PerguntaPerfil` (mesmo componente na home e no perfil); "pular" conta como visita.
- **Aceite:** pergunta respondida não volta; chave inexistente → `404`.

**RF-PE-12 — Consentimentos por finalidade, versionados**
- **Descrição:** consentimento por **finalidade e canal** (ofertas de parceiros; WhatsApp de relacionamento; demais finalidades por P-54), com **versão do texto obrigatória** e histórico completo (spec:§11.6 "consentimento versionado"). Mensagens transacionais seguem a execução do contrato de associação e não dependem de consentimento. Descadastro em um toque, refletido no RD na hora (RF-CM-03).
- **Fonte:** `consentimento_texto` (texto novo = linha nova, nunca editar) e `consentimento` (**append-only**; estado atual = última linha por finalidade × canal, `vw_consentimento_atual`) (`sql/019`) · **Endpoint:** `GET /perfil/consentimentos` (histórico + vigentes), `POST /perfil/consentimentos [C]` `{finalidade, canal, valor, versao_texto}` · **Evento:** `consentimento_alterar` (servidor; `detalhes.finalidade`, `canal`, `valor`, `versao`) · **Flag:** `lgpd_consentimentos` · **Fase:** 3b
- **UI:** switch com a versão do texto e link "ver histórico"; texto v0 provisório até P-54.
- **Aceite:** `versao_texto` ausente ou diferente da vigente → `409 versao_desatualizada`; nenhum `UPDATE`/`DELETE` em `consentimento` (`db_check`); retirar o consentimento suprime a outbox daquele canal na mesma transação.

**RF-PE-13 — Baixar meus dados**
- **Descrição:** `POST /perfil/dados/exportar [C] [L:1/7 d]` exige **step-up** (`idp_at` ≤ `REAUTH_MAX_IDADE`, regra 22; RF-AU-11) e devolve, de forma síncrona, um JSON com os dados que a **área** guarda do `contact_id` (`associado_perfil`, `perfil_declarado`, `solicitacao` + eventos, `uso_valor`, `consentimento`, `evento_uso`); dados do CRM são os já exibidos no perfil. Nunca por anexo de e-mail; download direto com `no-store`.
- **Fonte:** tabelas acima · **Endpoint:** `POST /perfil/dados/exportar` · **Evento:** registro em `evento_log` (`titular_exportacao`) e `titular_pedido` (tipo `exportacao`, fechado na hora) · **Flag:** `lgpd_consentimentos` · **Fase:** 3b (TI-26)
- **UI:** botão "Baixar meus dados" com `Dialogo` de confirmação e reautenticação quando necessário.
- **Aceite:** arquivo sem CPF, sem `sub` e sem `crm_*`; 2.º pedido em 7 dias → `429 limite_taxa`.

**RF-PE-14 — Pedir exclusão (anonimização, sem DELETE)**
- **Descrição:** `POST /perfil/exclusao [C]` (step-up) cria a solicitação `exclusao_dados` (tipo de serviço, §7.4) e o `titular_pedido` com protocolo; confirmação por e-mail; a fila é do encarregado de dados (B13). "Exclusão" na área = **anonimização administrativa** (DIV-05, DEC-06; ADR-0004 mantida): `associado_perfil` e `perfil_declarado` zerados, `anonimizado_em` preenchido, `contact_id` mantido nas trilhas como pseudônimo, `evento_log` preservado por obrigação legal; expurgo físico só por retenção pelo operador (P-15/P-54). A filiação em si é cancelada pela APM (RF-AJ-04), não por esta rota.
- **Fonte:** `titular_pedido`, `solicitacao` · **Endpoint:** `POST /perfil/exclusao` · **Evento:** `solicitacao_criar` (`tipo_servico=exclusao_dados`) · **Flag:** `lgpd_consentimentos` · **Fase:** 3b (TI-26; procedimento em `docs/RETENCAO.md`, TI-28)
- **UI:** texto explica prazo e o que acontece; 1 pedido aberto por associado.
- **Aceite:** script de anonimização roda fora do usuário `apm_area` (privilégio); após anonimizar, `GET /verificar/{token}` responde "não encontrada"; segundo pedido com um aberto → `409 estado_invalido`.
---

### 3.12 Minhas solicitações (SO) — `/area/solicitacoes` (P05)

> **Revisão v0.2 (spec:§6 P05, §8.5, §10.2; `LEVANTAMENTO §3.5`, §5.4; D-15/ADR-0018).** A máquina
> de estados passa a ter os **8 status da spec** (§7), com `sem_retorno` como coluna-marcador; a
> solicitação ganha vínculo com benefício, parceiro e tipo de ativação, prazo de retorno, contato,
> avaliação 0–10 e log imutável com "conteúdo enviado" (campos + sha256). RF-SO-01..07 permanecem
> com os ajustes abaixo: SO-01 lista os 7 rótulos (RF-SO-08) e mostra prazo e contato (RF-SO-15);
> SO-04 cancela em `criada`, `enviada` e `pendente_associado`, **nunca em `em_atendimento`**
> (RF-SO-12); SO-05 responde em `pendente_associado`; SO-06 continua válida — a **falha** do espelho
> é invisível, mas `enviada` vira status de negócio visível; SO-07 conta `pendente_associado`.

> **Contrato efetivo da Onda 2 (30/10):** `situacao` é opcional (ausente = todas); chave de idempotência
> reusada em outro tipo → `409 estado_invalido`; `409 nao_elegivel` traz a data em
> `detalhes[{campo: "libera_em", mensagem: "AAAA-MM-DD"}]` (o schema de erro é fechado); o `UPDATE` em
> `solicitacao` e `comunicacao_evento` é concedido **por coluna** (`sql/010`, `sql/012`).

**RF-SO-01 — Lista**
- **Descrição:** lista das solicitações do associado, ordenadas por última atualização (desc), com tipo (rótulo pt-BR), status pt-BR (seção 7), data de abertura e última atualização; abas "Em andamento" (não terminais) e "Encerradas" (proposta). Paginação por cursor (20).
- **Fonte:** `solicitacao` · **Endpoint:** `GET /solicitacoes?situacao=&cursor=` · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** vazio "Você ainda não fez nenhuma solicitação." (proposta); status com `Tag` (v0.2, 7 rótulos — RF-SO-08): Recebida pela APM (cinza), Enviada ao parceiro (azul), Em atendimento (azul), O parceiro precisa de algo seu (âmbar), Concluída (mint), Não seguiu (rose), Cancelada (cinza); faixa "Aguardando o parceiro" quando `aguardando_parceiro`.
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
- **Descrição:** disponível em `criada`, `enviada` e `pendente_associado` (v0.2; nunca em `em_atendimento`, RF-SO-12); confirmação em diálogo ("Cancelar esta solicitação?" — proposta).
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `POST /solicitacoes/{uuid}/cancelar [C]` · **Evento:** `solicitacao_cancelar` · **Flag:** — · **Fase:** 3
- **UI:** toast "Solicitação cancelada." (proposta); `409` → toast "Esta solicitação mudou de situação. Atualizamos a página." (proposta) e recarrega o detalhe.
- **Aceite:** transição condicional (`UPDATE … WHERE status IN (…)`); concorrência com o job resulta em exatamente um vencedor.

**RF-SO-05 — Responder**
- **Descrição:** em `pendente_associado`, campo de resposta (texto 1–2000 caracteres) devolve para `em_atendimento`.
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `POST /solicitacoes/{uuid}/responder [C]` · **Evento:** `solicitacao_responder` · **Flag:** — · **Fase:** 3
- **UI:** toast "Resposta enviada." (proposta).
- **Aceite:** resposta fora de `pendente_associado` → `409 estado_invalido`; texto entra em `solicitacao_evento` e é espelhado no CRM.

**RF-SO-06 — Sincronização com o CRM invisível ao associado**
- **Descrição:** `crm_id`, `crm_sync`, tentativas e erros de espelho nunca aparecem na UI nem na API; o associado vê só o status de negócio. Falha definitiva de espelho gera alerta operacional (seção 7), não mensagem ao associado.
- **Fonte:** `solicitacao` · **Endpoint:** — · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** —
- **Aceite:** teste de contrato garante ausência de chaves `crm_*` em todas as respostas.

**RF-SO-07 — Destaque de pendência**
- **Descrição:** contador de solicitações em `pendente_associado` no item "Minhas solicitações" da sidebar/drawer.
- **Fonte:** `solicitacao` · **Endpoint:** `GET /sessao` (campo `solicitacoes_aguardando`) · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** badge com `aria-label` "{n} solicitações aguardando você" (proposta).
- **Aceite:** contador zera após responder ou cancelar.

**RF-SO-08 — Oito status internos e sete rótulos**
- **Descrição:** `status` ∈ {`criada`, `enviada`, `em_atendimento`, `pendente_associado`, `concluida_positiva`, `concluida_negativa`, `cancelada`} + marcador `sem_retorno_desde` (RF-SO-09). Rótulos ao associado: Recebida pela APM · Enviada ao parceiro (tipo 3: "Encaminhada à equipe") · Em atendimento · O parceiro precisa de algo seu · Concluída · Não seguiu · Cancelada · Aguardando o parceiro, a APM já está cobrando (marcador). Rótulos da spec como proposta até P-44 (DEC-35).
- **Fonte:** `solicitacao.status`, `tipo_ativacao` (`sql/010`) · **Endpoint:** `GET /solicitacoes` (`status`, `rotulo`, `aguardando_parceiro`, `pode_cancelar`, `pode_avaliar`) · **Evento:** `solicitacao_status_alterado` (servidor/job; `detalhes.de`, `para`, `origem`) · **Flag:** — · **Fase:** 3 (TI-14..16, TI-21)
- **UI:** `StatusSolicitacao` com `Tag` por status (texto sempre, nunca só cor); destaque para o que depende do associado.
- **Aceite:** nenhum nome da v0.1 (`aberta`, `em_analise`, …) existe no banco ou na API (não há dado legado); teste de contrato dos 7 rótulos.

**RF-SO-09 — Marcador "sem retorno" (A05)**
- **Descrição:** job `marcar_sem_retorno` põe `sem_retorno_desde` quando `enviada_em + prazo_retorno_dias < agora` e `status ∈ {enviada, em_atendimento}`; qualquer transição limpa o marcador. Efeitos: alerta interno ao responsável (B01, SMTP interno), aviso ao associado ("a APM já está cobrando"), notificação in-app, outbox A05. Segundo vencimento (`prazo × 2`) ⇒ evento `sem_retorno_2` → fila de ligações da Central (spec:§10.2 passo 5).
- **Fonte:** `solicitacao.sem_retorno_desde`, `prazo_retorno_dias` (copiado do parceiro/benefício/`parametro.prazo_retorno_padrao_dias` na criação) · **Endpoint:** campo `aguardando_parceiro` em `GET /solicitacoes` · **Evento:** `solicitacao_evento` tipo `sem_retorno` (sem troca de status) · **Flag:** `comunicacao_outbox` (envio) · **Fase:** 3 (TI-17)
- **UI:** faixa "Aguardando o parceiro…" no item.
- **Aceite:** CHECK `sem_retorno_desde IS NULL OR status IN ('enviada','em_atendimento')`; job idempotente; prazo só conta a partir de `enviada_em` (nunca de `criada`).

**RF-SO-10 — Avaliar de 0 a 10 (A06)**
- **Descrição:** depois de `concluida_positiva`/`concluida_negativa`, o associado avalia uma vez: `POST /solicitacoes/{id}/avaliar [C]` `{nota 0–10, comentario ≤ 500}` dentro de `parametro.avaliacao_prazo_dias` (padrão 30; DEC-22). Chega por e-mail transacional com link HMAC (RF-CM-02) e pela própria tela.
- **Fonte:** colunas `avaliacao_nota`, `avaliacao_comentario`, `avaliada_em` em `solicitacao` (D-15) · **Endpoint:** `POST /solicitacoes/{id}/avaliar` · **Evento:** `solicitacao_avaliar` (servidor; `detalhes.nota`) · **Flag:** — · **Fase:** 3
- **UI:** `Avaliacao` com 11 botões rotulados; comentário sem HTML.
- **Aceite:** `UPDATE … WHERE avaliada_em IS NULL` — 2.ª tentativa → `409 ja_avaliada`; fora do prazo → `409 prazo_expirado`; não terminal → `409 estado_invalido`; CHECK `nota BETWEEN 0 AND 10`; comentário passa pelo filtro anti-CPF.

**RF-SO-11 — Vínculo com benefício, parceiro e tipo de ativação**
- **Descrição:** solicitações nascidas do catálogo (tipos 2–4) guardam `beneficio_id`, `parceiro_id`, `tipo_ativacao` e `canal_envio` (`crm` | `relatorio` | `email` | `api` | `portal`) **desnormalizados** (a ficha pode mudar; a solicitação guarda o `conteudo_enviado` da época). Pedidos sem benefício usam `tipo_servico` (RF-SO-14) com `beneficio_id` nulo. Lista e detalhe mostram `beneficio {slug, titulo}` e `parceiro` quando houver.
- **Fonte:** `solicitacao` · **Endpoint:** `GET /solicitacoes`, `GET /solicitacoes/{id}` · **Evento:** `solicitacao_criar` (`detalhes.tipo_ativacao`, `beneficio`) · **Flag:** — · **Fase:** 3 (estrutura) / 4 (criação pelo catálogo)
- **UI:** card com nome do benefício e parceiro.
- **Aceite:** CHECK `beneficio_id IS NOT NULL OR tipo_servico IS NOT NULL`; índice `(parceiro_id, criada_em)` para os indicadores 6–7.

**RF-SO-12 — Cancelamento: pelo associado só antes do atendimento; pela APM com justificativa**
- **Descrição:** o associado cancela em `criada`, `enviada` e `pendente_associado` ("enquanto o parceiro ainda não atendeu", spec:§6 P05) — **nunca** em `em_atendimento` (DIV-24). A APM (backoffice, RF-BO-02) cancela qualquer não terminal **com justificativa obrigatória**. Cancelar limpa outbox/fila pendentes da solicitação (suprime A05) e propaga ao CRM.
- **Fonte:** `solicitacao`, `solicitacao_evento` · **Endpoint:** `POST /solicitacoes/{id}/cancelar [C]` `{motivo?}` · **Evento:** `solicitacao_cancelar` · **Flag:** — · **Fase:** 3
- **UI:** botão só quando `pode_cancelar`; diálogo de confirmação.
- **Aceite:** cancelar em `em_atendimento` → `409 estado_invalido`; evento de origem `backoffice` sem `justificativa` é recusado por CHECK.

**RF-SO-13 — Log imutável com conteúdo enviado**
- **Descrição:** toda mudança entra em `solicitacao_evento` (append-only) com data, status anterior, novo status, **ator** (`associado` | `sistema` | `parceiro` | `apm` | `importacao`), **origem** (`ui` | `job` | `crm` | `backoffice` | `importacao` | `api_parceiro` | `portal_parceiro`), usuário interno quando houver, justificativa (obrigatória quando `origem='backoffice'`), mensagem pública e **conteúdo enviado** = lista de campos + `sha256` do payload + destino/canal — **nunca o payload** (DEC-02; minimização). Mudança manual exige justificativa (spec:§8.5).
- **Fonte:** `solicitacao_evento` (`sql/010`) · **Endpoint:** `GET /solicitacoes/{id}` (`linha_do_tempo[{quando, de, para, ator: "Você"|"Equipe APM"|"Parceiro", mensagem}]` — sem campos internos) · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** `LinhaDoTempo`.
- **Aceite:** CHECK anti-CPF em JSON e texto; `db_check` confirma só `INSERT`; teste de contrato garante ausência de `conteudo_enviado`, `justificativa` e `crm_*` na API do associado.

**RF-SO-14 — Tipos de serviço ampliados (tipo 3)**
- **Descrição:** além dos 7 tipos da v0.1 (§7.4), entram `declaracao_associado` (RF-FI-04; inclui "AMB para prova de título" com carência de 1 mês), `cancelamento_associacao` (RF-AJ-04) e `exclusao_dados` (RF-PE-14). Com o catálogo como dado (Fase 4), serviços da APM viram entradas do catálogo com `tipo_ativacao=3`; até lá continuam como `tipo_servico`.
- **Fonte:** `solicitacao.tipo_servico` ENUM; schemas por tipo com allowlist de campos (`beneficio.sigiloso` ⇒ `dados={}`; nunca dado de saúde) · **Endpoint:** `POST /solicitacoes [C]` `{tipo_servico, campos, chave_idempotencia}` · **Evento:** `solicitacao_criar` · **Flag:** `cancelamento_online` só para `cancelamento_associacao` · **Fase:** 3 (TI-15)
- **UI:** formulários por tipo.
- **Aceite:** campo fora da allowlist do tipo → `400 entrada_invalida`; `outro` limitado a 5 em 24 h móveis por contagem no banco (D-17).

**RF-SO-15 — Prazo e contato na lista**
- **Descrição:** cada item mostra data, status, **prazo** (`prazo_em = enviada_em + prazo_retorno_dias`, ou "prazo informado após o envio") e **contato** (canal da Central ou do parceiro, do catálogo), conforme spec:§6 P05 "lista com benefício, data, status, prazo e contato".
- **Fonte:** `solicitacao`, `parceiro.contato`, `parametro` · **Endpoint:** `GET /solicitacoes?situacao=andamento|encerradas&cursor=&limite≤20` · **Evento:** — · **Flag:** — · **Fase:** 3
- **UI:** contato como link `tel:`/`wa.me` em allowlist.
- **Aceite:** contato do parceiro nunca inclui dado de pessoa física; sem `enviada_em` o prazo não é exibido.
---

### 3.13 Autenticação e sessão (AU) — P01 vive no IdP

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
- **Descrição:** devolve: nome de exibição, iniciais, `tipo`, `status`, `tem_foto`, `csrf`, `rota_inicial`, `flags`, `config` (`whatsapp`, `show_whatsapp`, `animations`), `stub` (bool), `solicitacoes_aguardando` (contagem real de `pendente_associado`; 0 se a tabela não existe), `recursos` (`{solicitacoes, ajuda}`: tabelas presentes, `app/prontidao.py`, cache 60 s; a SPA mostra "em construção" quando falso — Onda 2). Nunca CPF, `cpf_mask`, e-mail completo, `sub` ou `contact_id`.
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

**RF-AU-11 — Reautenticação (step-up) reutilizável**
- **Descrição:** dependência `exigir_reautenticacao` (403 `reautenticacao_necessaria`) generaliza a regra 22 (hoje só na troca de e-mail, ADR-0015): `idp_at` do IdP a no máximo `REAUTH_MAX_IDADE`; nunca `auth_at`. Aplicada a cancelamento da associação (RF-AJ-04), exclusão (RF-PE-14), exportação (RF-PE-13), troca de canal preferido quando existir OTP por celular. A SPA, ao receber 403, navega para `/auth/login?reauth=1&next=<rota>` e volta.
- **Fonte:** sessão (`idp_at`) · **Endpoint:** todos os marcados "step-up" · **Evento:** `evento_log` `reauth_exigida` · **Flag:** — · **Fase:** 3 (TI-09)
- **UI:** `Dialogo` "Para continuar, confirme sua identidade" antes de redirecionar, para não perder o que foi digitado.
- **Aceite:** teste com `idp_at` velho recebe 403; com `prompt=login` recente passa; SSO silencioso não renova `idp_at`.

**RF-AU-12 — Evento `acesso_primeiro`**
- **Descrição:** quando `associado.registrar_acesso` **insere** a linha (primeiro login na área), emite `acesso_primeiro` com `dias_desde_filiacao` (spec:§11.2; alimenta ativação em 30 dias e o gatilho A02 por ausência). O método (e-mail/celular) é do IdP (`amr`), não da área (DEC-12).
- **Fonte:** `associado.primeiro_acesso_em` (`sql/005`) · **Endpoint:** `GET /auth/callback` · **Evento:** `acesso_primeiro` (servidor; `detalhes.dias_desde_filiacao`) · **Flag:** — · **Fase:** Onda 1 (TI-05)
- **UI:** "Como funciona" em quatro passos na primeira home (RF-HO-09).
- **Aceite:** segundo login não emite; upsert com `ROW_COUNT()=1` é o critério.

---

### 3.14 Financeiro (FI) — `/area/financeiro` (P08, flag `erp_financeiro`)

Condicional na F1 ao gate técnico da cobrança (spec:§5.2); hoje ⛔ por P-04 (ferramentas por `contact_id`), P-08 (parecer de licença do F&O) e P-58 (segunda via sem fonte). ERP **somente leitura**, via hub, após parecer (ADR-0010). Dois conceitos com um nome: **situação cadastral** (CRM, `alf_status_associativo`) × **pendência financeira** (cobrança) ficam separados na API (DIV-31, DEC-14).

**RF-FI-01 — Situação financeira no topo**
- **Descrição:** "em dia" ou "em atraso (N dias)" a partir do hub; sem fonte, a tela avisa "não foi possível consultar a cobrança agora" e oferece a Central (spec:§6 P08 "Regras").
- **Fonte:** hub `financeiro.situacao_consultar(contact_id)` (TI-49; cache mínimo `associado_financeiro`: situação e dias, **sem valores**) · **Endpoint:** `GET /financeiro` → `{situacao, dias_atraso?, mensalidades[], historico[]}` · **Evento:** — · **Flag:** `erp_financeiro` · **Fase:** 7
- **UI:** situação e botão de segunda via (quando houver) em destaque.
- **Aceite:** flag desligada → `404 recurso_desligado`; hub fora → `503` só neste bloco; nenhuma chamada da área ao ERP com CPF.

**RF-FI-02 — Mensalidades do ano e histórico de pagamentos**
- **Descrição:** mensalidades (competência, vencimento, valor, status) e pagamentos do ano, lidos do hub sob demanda com cache curto; valor e forma de pagamento.
- **Fonte:** hub `financeiro.faturas_listar(contact_id)` (`CustTransactions`) · **Endpoint:** `GET /financeiro` · **Evento:** `pagina_ver` · **Flag:** `erp_financeiro` · **Fase:** 7
- **UI:** tabela acessível; moeda RNF-14.
- **Aceite:** valores nunca persistidos na área além do cache de situação (§6).

**RF-FI-03 — Segunda via (PDF, linha digitável, Pix)**
- **Descrição:** **fonte inexistente**: o F&O via OData não expõe boleto, linha digitável nem Pix (`LEVANTAMENTO §8.2`). O botão não aparece até existir fonte (P-58). Quando existir: `GET /financeiro/mensalidades/{competencia}/segunda-via`, `no-store`, evento `fatura_segunda_via` (`detalhes.competencia`, `forma` ∈ {pdf, linha_digitavel, pix}).
- **Fonte:** — (⛔) · **Endpoint:** reservado · **Evento:** `fatura_segunda_via` (substitui `fatura_pdf_baixar`, retirada) · **Flag:** `erp_financeiro` · **Fase:** 7 (⛔ P-58)
- **UI:** texto "Para a segunda via, fale com a Central" enquanto não houver fonte.
- **Aceite:** nenhuma promessa de segunda via sem fonte (regra 19).

**RF-FI-04 — Declarações de associado (tipo 3)**
- **Descrição:** declarações, inclusive a da **AMB para prova de título** (carência de 1 mês), são solicitação `declaracao_associado` (RF-SO-14) com `campos {finalidade ENUM}`; elegibilidade pelo motor (RF-BE-12) → `409 nao_elegivel {libera_em}`. Viável já, sem ERP.
- **Fonte:** `solicitacao` · **Endpoint:** `POST /solicitacoes [C]` (`tipo_servico=declaracao_associado`) ou `POST /financeiro/declaracoes [C]` (atalho) · **Evento:** `solicitacao_criar` · **Flag:** — (independe de `erp_financeiro`) · **Fase:** 3 (TI-57)
- **UI:** entra também em "pedidos comuns" da Ajuda (RF-AJ-05).
- **Aceite:** associado com < 1 mês não consegue pedir a AMB e vê a data; uma não terminal por finalidade.

**RF-FI-05 — Pagamento confirmado e mensalidade vencida (A09)**
- **Descrição:** a área **consome** a cobrança: job `sincronizar_financeiro` (diário; `financeiro.vencidas_desde(cursor)`) atualiza `associado_financeiro`, emite `pagamento_confirmar` (sem valor) e alimenta supressão de ofertas comerciais (bloco Pendência, elegibilidade "Suspenso" após `parametro.dias_atraso_suspensao`) e o campo `cf_apm_data_inadimplencia` no RD (A09). Recorrente em cartão (FIN-04) é F2 e depende da cobrança.
- **Fonte:** hub (TI-49, TI-51) · **Endpoint:** — · **Evento:** `pagamento_confirmar` (job; `detalhes.competencia`, `forma`) · **Flag:** `erp_financeiro`, `comunicacao_outbox` · **Fase:** 7 (⛔ P-04, P-08, P-58)
- **UI:** —
- **Aceite:** "Suspenso" só nasce com esta fonte; até lá `financeiro=None ⇒ permite` (DEC-14).

---

### 3.15 Ajuda e atendimento (AJ) — `/area/ajuda` (P14)

F1 na spec (AJU-01/02); sem fase na v0.1 → **Fase 3** (DIV-27): são uma tabela de FAQ e dois tipos de solicitação.

**RF-AJ-01 — Perguntas frequentes com busca**
- **Descrição:** FAQ editável (B07) com busca normalizada sem acento, agrupada por categoria; sugere categorias quando não encontra.
- **Fonte:** `faq` (`sql/013`; só publicadas) · **Endpoint:** `GET /ajuda/faq?q=&categoria=` · **Evento:** `pagina_ver`; `busca_global` quando via busca do shell (a FAQ é uma das 5 fontes, RF-SH-04) · **Flag:** — · **Fase:** 3 (TI-20, TI-22)
- **UI:** `BuscaFaq` + `Accordion`; conteúdo inicial (≥ 20 perguntas) por P-44.
- **Aceite:** FAQ despublicada some sem deploy; `q` ≤ 80.

**RF-AJ-02 — Falar com a Central (canais e horário)**
- **Descrição:** WhatsApp (`wa.me`, mensagem na voz §3.3 — sem exclamação), telefone (`tel:` entra na allowlist de esquemas) e formulário, com **horário de atendimento** de `parametro`.
- **Fonte:** `Settings` (`WHATSAPP_CENTRAL`) + `parametro` (horário, telefone) · **Endpoint:** `GET /ajuda/contato` · **Evento:** `ajuda_contatar` (ui; `detalhes.canal` ∈ {whatsapp, telefone, formulario}, `assunto` ENUM) — `central_whatsapp_abrir` migra para este emissor · **Flag:** — · **Fase:** 3
- **UI:** cards por canal; FAB continua (RF-SH-08).
- **Aceite:** horário vem do banco; nenhum dado pessoal na URL do `wa.me` (LA-18).

**RF-AJ-03 — Formulário para a Central**
- **Descrição:** `POST /ajuda/formulario [C]` cria solicitação `outro` (assunto + mensagem) — mesmo caminho de RF-SO-03; e-mail transacional de confirmação (A04).
- **Fonte:** `solicitacao` · **Endpoint:** `POST /ajuda/formulario` (atalho para `POST /solicitacoes`) · **Evento:** `solicitacao_criar` · **Flag:** — · **Fase:** 3
- **UI:** `assunto` em lista curta (pedidos comuns) + "outro".
- **Aceite:** 5 em 24 h móveis por contagem no banco (D-17); texto sem HTML, filtro anti-CPF.

**RF-AJ-04 — Pedido de cancelamento da associação (A16)**
- **Descrição:** acessível sem labirinto; **motivo obrigatório** em lista curta (`nao_uso`, `preco`, `mudanca` — cidade ou fase —, `insatisfacao_servico`, `outro`), oferta de conversa opcional, comentário ≤ 500. Cria solicitação `cancelamento_associacao` (RF-SO-14) com **step-up** (RF-AU-11), confirmação por e-mail e janela de arrependimento; **nunca altera a situação no CRM** — quem cancela é a APM (DEC-08 do Maestro; spec:§6 P14 "o pedido vai para a Central"). Dispara outbox A16 (fluxo 6 da régua), espelho no CRM e SMTP à Central; suprime fluxos de efetivo.
- **Fonte:** `solicitacao`, `comunicacao_evento` · **Endpoint:** `POST /ajuda/cancelamento [C]` `{motivo, quer_conversa, comentario?}` → `201 {solicitacao_id, prazo}` · **Evento:** `cancelamento_pedir` (servidor; `detalhes.motivo`) — equivale a `cancelamento_pedido` da spec · **Flag:** `cancelamento_online` (pode nascer ligada por decisão de negócio) · **Fase:** 3 (TI-20)
- **UI:** `FormularioCancelamento` com `RadioGroup`; texto diz o prazo e o próximo passo.
- **Aceite:** 1 pedido aberto por associado (`409 estado_invalido`); sem `motivo` → `400`; teste garante que nenhuma ferramenta de escrita do hub é chamada; indicadores 12 e 13 leem daqui.

**RF-AJ-05 — Pedidos comuns**
- **Descrição:** atalhos para atualização cadastral (→ `/area/perfil`), declaração (RF-FI-04), dúvida sobre benefício (→ formulário com `assunto=beneficio`).
- **Fonte:** estático + `faq` · **Endpoint:** — · **Evento:** `pagina_ver` · **Flag:** — · **Fase:** 3
- **UI:** 3 cards.
- **Aceite:** navegação correta; nenhum atalho para fluxo inexistente.

---

### 3.16 Notificações (NO) — `/area/notificacoes` (P15, F2, flag `notificacoes`)

Decisão: in-app + e-mail transacional; **sino só com aceite visual** da agência (ADR-0017 "sem sino até existir fonte"; DIV-10, DEC-08, P-42); Web Push só com consentimento, SW restrito e ADR (RF-NO-05). A **tabela nasce na Fase 3** (produzida pelos mesmos eventos da outbox); a API e a tela são F2.

**RF-NO-01 — Lista de notificações**
- **Descrição:** tipos: solicitação atualizada, benefício liberado, evento, pagamento, novidade para o perfil; lida/não lida; atalho para preferências de canal (RF-PE-10).
- **Fonte:** `notificacao` (`sql/012`; `UPDATE` só em `lida_em`) · **Endpoint:** `GET /notificacoes?cursor=` `[F:notificacoes]` → `{itens[{id, tipo, titulo, corpo, link, criada_em, lida}]}` · **Evento:** `notificacao_abrir` (ui; `detalhes.tipo`) · **Flag:** `notificacoes` · **Fase:** F2 (TI-85)
- **UI:** lista com `aria-live` discreto; link interno validado.
- **Aceite:** flag desligada → `404 recurso_desligado`; só as do próprio `contact_id`.

**RF-NO-02 — Marcar como lida**
- **Descrição:** `POST /notificacoes/{id}/ler [C]` e `POST /notificacoes/ler-todas [C]`.
- **Fonte:** `notificacao.lida_em` · **Endpoint:** acima · **Evento:** — · **Flag:** `notificacoes` · **Fase:** F2
- **UI:** —
- **Aceite:** `UPDATE … WHERE lida_em IS NULL AND contact_id = :c`; idempotente.

**RF-NO-03 — Contador no topo**
- **Descrição:** `GET /sessao` devolve `notificacoes_nao_lidas` (só com a flag); ícone com contagem **depois** do aceite visual.
- **Fonte:** índice `(contact_id, lida_em, criada_em)` · **Endpoint:** `GET /sessao` · **Evento:** — · **Flag:** `notificacoes` · **Fase:** F2
- **UI:** sino (pendente de aceite, P-42).
- **Aceite:** contador zera ao ler; ausente sem a flag.

**RF-NO-04 — Produção pelos eventos de domínio**
- **Descrição:** a notificação é criada **na mesma transação** da transição de negócio que alimenta a outbox (A03 carência, A04 solicitação criada, A05 sem retorno, A06 concluída, A15 novo benefício, pagamento) — nunca pela UI.
- **Fonte:** `app/dominio/comunicacao.py` · **Endpoint:** — · **Evento:** `notificacao_criar` (job/servidor; `detalhes.tipo`) · **Flag:** — (produção sempre; exibição sob `notificacoes`) · **Fase:** 3 (TI-18)
- **UI:** —
- **Aceite:** índice único por (tipo, contact_id, referência) impede duplicata; corpo sem dado pessoal além do já visível na área.

**RF-NO-05 — Web Push (hipótese desligada)**
- **Descrição:** só se DEC-08 aprovar: Service Worker restrito (`/area/sw.js`, `worker-src 'self'`, network-only em navegação e `/api`), chaves VAPID em `.env`, `push_assinatura` cifrada, envio pelo serviço de jobs com egress declarado, payload sem conteúdo sensível, consentimento por canal **antes** de `requestPermission`.
- **Fonte / Endpoint / Evento:** a definir em ADR própria · **Flag:** `notificacoes` + consentimento · **Fase:** F2 (TI-91)
- **UI:** —
- **Aceite:** nenhum SW no bundle enquanto a decisão não existir (lint contra `serviceWorker`, `caches`, `indexedDB`).

---

### 3.17 Comunicação e gatilhos (CM) — sem tela (spec:§12)

Arquitetura (DEC-18): a área **emite** campos e eventos (outbox produzida na transação do negócio, consumida por job); a régua de 29/09 (69 peças, 8 fluxos), o limite de 2 mensagens/semana e o horário 8h–20h vivem no **RD Station**; a área aplica só **supressão** por campos e grava consentimento. **Transacionais saem do próprio sistema** (SMTP da área, P-27); mensagens de marketing nunca. Chave no RD = `cf_apm_contactid` (nunca CPF; e-mail muda). Detalhe das integrações em §5.9.

**RF-CM-01 — Outbox de comunicação**
- **Descrição:** `comunicacao_evento` (gatilho ∈ A01..A20, `contact_id`, referência tipo/id, canal sugerido, `enviar_apos`, status `pendente|enviado|suprimido|erro|falhou`, tentativas, `rd_evento_id`; **único `(gatilho, contact_id, referencia_id)`**) produzida **na mesma transação** da transição de negócio; `comunicacao_envio` (append; entregue/aberto/clicado por retorno do RD ou UTM) e `comunicacao_supressao` (append; motivo ∈ {limite_semana, financeiro, cancelamento, sem_consentimento, recomendado_recente}). Payload **sem CPF nem e-mail**. Gatilhos que a área emite na F1: **A03, A04, A05, A06, A16** (`LEVANTAMENTO §7`); A01/A02/A13 por jobs de diferença (TI-55); A09 só com cobrança; A17/A18 fora da área.
- **Fonte:** `sql/012` · **Endpoint:** — · **Evento:** — (a outbox não é `evento_uso`) · **Flag:** `comunicacao_outbox` governa o **envio** (job `outbox_rd`); a produção é sempre ligada · **Fase:** 3 (TI-18); envio 3b (TI-53) com P-46
- **UI:** log visível no backoffice (B09, RF-BO-11).
- **Aceite:** sem credencial do RD o job marca `suprimido: sem_credencial` e nada sai; índice único impede disparo duplo pela mesma causa; `GET_LOCK` no job.

**RF-CM-02 — Transacionais por e-mail (A04, A05, A06, códigos)**
- **Descrição:** confirmação de solicitação criada com prazo e próximo passo (A04), aviso "a APM está cobrando o parceiro" (A05), "como foi?" com link HMAC para avaliar (A06), código de troca de e-mail (ADR-0015), confirmação de cancelamento e de exclusão. Templates texto + HTML no padrão do IdP, fila com recuo (hoje síncrono), nunca marketing.
- **Fonte:** `app/integracoes/email.py` (SMTP STARTTLS; `SMTP_MODE=stub` proibido em produção) · **Endpoint:** — · **Evento:** `evento_log` por envio (sem conteúdo) · **Flag:** — (transacional sempre sai, spec:§12.3) · **Fase:** 3 (TI-19); produção com P-27
- **UI:** —
- **Aceite:** link de avaliação expira em `avaliacao_prazo_dias` e é de uso único; nenhum CPF ou dado de saúde no corpo.

**RF-CM-03 — Supressão e consentimento por canal**
- **Descrição:** supressão local antes de enfileirar: pendência financeira suspende ofertas comerciais (`cf_apm_suprimir_ofertas`); benefício solicitado há < 14 dias sai da recomendação e da comunicação; quem pediu cancelamento sai dos fluxos de efetivo (`cf_apm_cancelamento_pedido`); consentimento retirado = **nunca mais enfileira** para o canal e descadastro síncrono no RD com fallback na outbox (spec:§12.3).
- **Fonte:** `vw_consentimento_atual`, `associado_financeiro`, `solicitacao` · **Endpoint:** — · **Evento:** `consentimento_alterar` · **Flag:** `comunicacao_outbox` · **Fase:** 3b
- **UI:** descadastro em um toque no perfil (RF-PE-12).
- **Aceite:** teste: consentimento negado ⇒ linha em `comunicacao_supressao`, nunca em `enviado`.

**RF-CM-04 — Envio ao RD Station (job `outbox_rd`)**
- **Descrição:** job no serviço de jobs lê `pendente` com `enviar_apos ≤ agora`, **revalida o fato** (a solicitação ainda está no status que originou o gatilho?), envia `POST /platform/events` (conversão com `conversion_identifier` por gatilho) e atualiza campos `cf_apm_*`; recuo exponencial; `falhou` após N tentativas vai ao B01. OAuth2 refresh → access em memória de processo.
- **Fonte:** `app/integracoes/rdstation.py` (`RD_MODE=real|stub`, stub proibido em produção; `scripts/check_rd.py`) · **Endpoint:** — · **Evento:** `comunicacao_envio` · **Flag:** `comunicacao_outbox` · **Fase:** 3b (TI-53); real com P-46
- **UI:** —
- **Aceite:** `cf_apm_contactid` sempre presente; `available_for_mailing` nunca enviado; webhook de retorno do RD só na F2 por ADR (rota pública nova).

**RF-CM-05 — Retorno por UTM e código do gatilho**
- **Descrição:** o clique volta com UTM e `g=A0n` (RF-SH-15) e vira `comunicacao_envio.clicado_em` + `detalhes.gatilho` no `pagina_ver` de entrada; indicador 10 lê daqui.
- **Fonte:** `comunicacao_envio` · **Endpoint:** `POST /uso` · **Evento:** `pagina_ver` · **Flag:** — · **Fase:** 4 (TI-11)
- **UI:** —
- **Aceite:** código fora do catálogo descartado; nenhum `utm_*` persistido como texto.

---

### 3.18 Backoffice como API interna (BO) — sem tela nesta área (spec:§9)

Escopo novo (decisão do usuário, 29/10). Onde o backoffice vive, como autentica e o 2FA ficam
para a Onda 6 (DEC-03 restante: recomendação = container próprio na mesma imagem, host próprio,
Cloudflare Access + Entra ID, P-65/P-62). O que **já está decidido**: usuário de banco próprio
`apm_area_bo` com `UPDATE` só em catálogo/configuração (D-19, ADR-0022); identidade do staff
**nunca** é o `login_associado`; **nunca** dentro da área com a sessão do associado (superfície
`minha.apm.org.br` e cookie `__Host-` não se misturam); trilhas append-only. Até a decisão vale o
caminho sem backoffice (`LEVANTAMENTO §4.3`). Os RFs abaixo descrevem o que a área **guarda e
expõe** por módulo, no namespace `/api/interno/v1`, autenticado por **token de serviço separado**
(como o hub), com `limit_req` próprio e `403` no edge até existir o consumidor.

**RF-BO-01 — Namespace, autenticação e auditoria da API interna**
- **Descrição:** `/api/interno/v1/*` fora do `require_associado`; autenticação por token de serviço (segredo em `Settings`, comparação em tempo constante, rotação documentada) ou, na Onda 6, OIDC corporativo; toda escrita grava `backoffice_auditoria` (`usuario_id`, ação, tabela, registro, valor anterior/novo em JSON com CHECK anti-segredo/CPF, justificativa, `request_id`) — **append-only**; toda leitura de dado pessoal individual grava `acesso_dado_pessoal` (quem, qual `contact_id`, quais campos). Perfis Diretoria e Regional só veem agregados (k ≥ 20); Parceiro (PAR-01, F2) só as próprias solicitações, nunca CPF.
- **Fonte:** `usuario_interno` (sem senha; identidade externa), `backoffice_auditoria`, `acesso_dado_pessoal` (`sql/021`) · **Endpoint:** `/api/interno/v1/*` · **Evento:** — (trilhas próprias) · **Flag:** — · **Fase:** BO (TI-58; após DEC-03)
- **UI:** fora desta área.
- **Aceite:** vhost devolve `403` para `/api/interno/` até o consumidor existir; `db_check` valida `apm_area_bo` com allowlist própria e `apm_area` sem `UPDATE` em catálogo.

**RF-BO-02 — B05 Solicitações e leads**
- **Descrição:** fila com filtros (`status`, `parceiro`, `sem_retorno`), prazo e responsável; `POST /solicitacoes/{id}/status` com **justificativa obrigatória** (`ator=apm`, `origem=backoffice`, usuário no evento), reenvio ao canal, exportação CSV agregada. Leads de não associados **não vivem na área** (RD/CRM, DEC-19).
- **Fonte:** `solicitacao*` · **Endpoint:** `GET /solicitacoes?status=&parceiro=&sem_retorno=`, `POST /solicitacoes/{id}/status`, `POST .../reenviar`, `GET .../exportar.csv` · **Evento:** `solicitacao_status_alterado` (servidor; `origem=usuario`) · **Flag:** — · **Fase:** BO (dados prontos na Fase 3)
- **UI:** —
- **Aceite:** transição inválida → `409`; sem justificativa → `400`; exportação sem CPF.

**RF-BO-03 — B06 Importações (CSV do plano B)**
- **Descrição:** upload (canal DEC-05: upload no backoffice na F1; S3 presigned ou módulo no `apm-parceiros` depois; nunca SFTP novo nem e-mail) → o CSV vai **ao hub** (`importacao.resolver_lote`), que resolve CPF → `contact_id`/`nao_encontrado` e cria o lead no RD/CRM; a área recebe e guarda `importacao` (cabeçalho, sha256, contagens, status `recebida|validada|confirmada|devolvida`) e `importacao_linha` **sem CPF** (único `(parceiro_id, id_externo)`; `erro_codigo` por linha; CHECK anti-CPF em `observacao`). Prévia com erros por linha → confirmar (INSERT em `uso_valor` nível 3; nível 4 após validação do Financeiro; fecha solicitações por `id_externo`) → devolução de erros ao parceiro por SMTP sem dado pessoal. Processamento no **serviço de jobs**, nunca no processo web; CPF só em memória, descartado.
- **Fonte:** `importacao`, `importacao_linha` (`sql/017`); hub TI-51 · **Endpoint:** `POST /importacoes`, `GET /importacoes/{id}/previa`, `POST /importacoes/{id}/confirmar`, `GET /importacoes/{id}/devolucao.csv` · **Evento:** `uso_registrar` (job) · **Flag:** — · **Fase:** BO/4 (TI-54, TI-81; DEC-05 aceita só quanto ao hub)
- **UI:** —
- **Aceite:** teste de contrato recusa coluna `cpf` em qualquer corpo da **área**; reenvio do mesmo arquivo não duplica (`id_externo`); linha com CPF em `observacao` é rejeitada.

**RF-BO-04 — B13 Configurações e LGPD**
- **Descrição:** CRUD com justificativa de `parametro` (dias de atraso que suspendem, prazo de retorno padrão, prazo de avaliação, dias de dispensa, horário da Central), carências (`beneficio.carencia_meses`), `valor_referencia` (aprovação do Financeiro = INSERT da linha aprovada), `consentimento_texto` (versão nova = linha nova), `feature_flag`, usuários e perfis; fila de pedidos do titular (`titular_pedido`).
- **Fonte:** tabelas citadas; `UPDATE` só por `apm_area_bo` · **Endpoint:** `GET|PUT /parametros/{chave}`, `POST /valores-referencia`, `POST /consentimentos/textos`, `GET|POST /titular/pedidos` · **Evento:** `backoffice_auditoria` · **Flag:** — · **Fase:** BO (hoje: operador por SQL, como `feature_flag`)
- **UI:** —
- **Aceite:** leitura pela área com cache 60 s (como `app/flags.py`); mudança de parâmetro reflete sem deploy.

**RF-BO-05 — B01 Painel do dia**
- **Descrição:** agregados: solicitações com `sem_retorno_desde`, importações pendentes, pedidos do titular abertos, outbox em erro, jobs com erro, fila de ligações.
- **Fonte:** `solicitacao`, `importacao`, `titular_pedido`, `comunicacao_evento`, `job_execucao`, `fila_ligacao` · **Endpoint:** `GET /painel/dia` · **Evento:** — · **Flag:** — · **Fase:** BO (dados na Fase 3)
- **UI:** —
- **Aceite:** nenhum dado individual além do necessário à fila.

**RF-BO-06 — B02 Visão 360**
- **Descrição:** busca por **nome, número de associado ou `contact_id`** (nunca CPF na área — DIV-11; busca por CPF só no hub com grant); junta dados locais (ativações, solicitações, `uso_valor`, consentimentos, comunicações, contatos da Central) ao cadastro via hub `associado.visao_360` (sensível); cada visualização registra `acesso_dado_pessoal`. Somente leitura do cadastro.
- **Fonte:** tabelas locais + hub · **Endpoint:** `GET /associados/{contact_id}` · **Evento:** `acesso_dado_pessoal` · **Flag:** — · **Fase:** BO (⛔ grant do hub, DEC-03)
- **UI:** —
- **Aceite:** sem registro de acesso a resposta não é devolvida (registro antes do envio).

**RF-BO-07 — B03/B04 Catálogo e parceiros**
- **Descrição:** CRUD da ficha do benefício (RF-BE-16) com rascunho → aprovação → publicação agendada, histórico em `beneficio_versao`, prévia "ver como associado" (chama `inicio.montar`/elegibilidade com o perfil alvo); cadastro mínimo de `parceiro` (código APM `PAR017` como chave de conciliação com o CSV, requisito técnico `api|relatorio|portal|email`, prazo de retorno, vigência, contatos sem CPF). `apm-parceiros` continua outro sistema (DEC-10 do Maestro).
- **Fonte:** `beneficio`, `beneficio_versao`, `beneficio_faq`, `beneficio_afinidade`, `parceiro` (`sql/016`) · **Endpoint:** CRUD em `/beneficios`, `/parceiros`; `GET /previa?contact_id=` · **Evento:** `backoffice_auditoria` · **Flag:** — · **Fase:** BO (Fase 4 para os dados)
- **UI:** —
- **Aceite:** publicar sem `valor_referencia` aprovada é recusado quando a ficha tem valor; vigência vencida encerra sem ação manual.

**RF-BO-08 — B12 Painéis e relatórios**
- **Descrição:** views `vw_ind_01..14` (indicadores spec:§11.3), `vw_qualidade_parceiro_mes` e `base_ativa_mensal` (denominadores por categoria/regional gravados por job); **k-anonimato ≥ 20** embutido em qualquer recorte que saia para parceiro, patrocinador ou regional (função única `agregar(min_n=20)`); usuário `apm_area_painel` só `SELECT` nas views; exportação só agregada; ferramenta por DEC-16 (nunca script de terceiro na SPA).
- **Fonte:** `sql/025` (views), `sql/024` (`base_ativa_mensal`) · **Endpoint:** consultas agregadas via ferramenta/`/api/interno/v1/paineis/*` · **Evento:** — · **Flag:** — · **Fase:** BO/4 (TI-44; definições das views já)
- **UI:** —
- **Aceite:** recorte com < 20 pessoas devolve vazio; indicadores com denominador externo (1, 2, 4, 9, 11) rotulados "só numerador" até a fonte.

**RF-BO-09 — B07/B08 Conteúdo e segmentos**
- **Descrição:** `destaque_editorial` (ADM-05), `faq`, `trilha_passo`, `texto_sistema` (estados vazios e de erro editáveis), `segmento` (regras) e `beneficio_afinidade` (matriz), com prévia por perfil.
- **Fonte:** `sql/013` (`faq`, `texto_sistema`, `parametro`), `sql/016`, `sql/020` · **Endpoint:** CRUD · **Evento:** `backoffice_auditoria` · **Flag:** — · **Fase:** BO (Onda 2 para `faq`/`texto_sistema`/`parametro` por SQL do operador)
- **UI:** —
- **Aceite:** texto publicado aparece na API da área em ≤ 60 s (cache).

**RF-BO-10 — B09 Comunicação (log)**
- **Descrição:** `GET /comunicacao?gatilho=&status=` sobre outbox, envios, supressões e notificações; descadastros aparecem como consentimento retirado.
- **Fonte:** `comunicacao_*`, `notificacao`, `vw_consentimento_atual` · **Endpoint:** acima · **Evento:** — · **Flag:** — · **Fase:** BO (dados na Fase 3)
- **UI:** —
- **Aceite:** sem payload de mensagem (vive no RD).

**RF-BO-11 — Fila de ligações da Central (§10.5)**
- **Descrição:** job diário às 8h (`TZ=America/Sao_Paulo`) gera `fila_ligacao` na ordem da régua: renovação (⛔ fonte), passagem para efetivo, novo associado no 3.º mês, interesse, ex-associado (fora da área), `sem_retorno_2`; F2 acrescenta score < 30 (A12). Resultado da ligação registrado pelo atendente; 3 tentativas sem resposta ⇒ sai por 30 dias. Sem backoffice: entrega à Central por CSV interno via SMTP ou view RO no portal do hub (TI-59, provisório).
- **Fonte:** `fila_ligacao` (`sql/012`) · **Endpoint:** `GET /fila-ligacoes`, `POST /fila-ligacoes/{id}/resultado` · **Evento:** — · **Flag:** — · **Fase:** 3b (provisório) / BO
- **UI:** —
- **Aceite:** fila sem CPF (nome, número, canal preferido); itens só com consentimento/transacional conforme finalidade.

---

## 4. Requisitos não funcionais

| ID | Área | Requisito | Verificação |
|---|---|---|---|
| RNF-01 | Segurança · CSP | `default-src 'self'; script-src 'self' 'nonce-…'; style-src 'self'; img-src 'self' data: <CSP_IMG_HOSTS>; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://login.apm.org.br; object-src 'none'`. Sem `'unsafe-inline'`/`'unsafe-eval'`; estilos dinâmicos por classes e custom properties via CSSOM (D-13). Demais cabeçalhos de `app/main.py:167-181` mantidos. | `scripts/csp_check.py`; E2E falha em `securitypolicyviolation` |
| RNF-02 | Segurança · CSRF | RF-AU-05 em toda escrita `/api/`; formulários HTML (`/auth/*`) mantêm token de form. | testes de API |
| RNF-03 | Segurança · cookie | RF-AU-06; nada de token de acesso/refresh, CPF completo ou dado de perfil além do listado. | teste de tamanho e de conteúdo |
| RNF-04 | Segurança · fail-closed | Identidade parcial nunca abre sessão; escrita no CRM nunca é "otimista" (só confirma após 200 do hub); verificação pública nunca afirma status a partir de cache > 24 h; flag desconhecida = desligada. | testes de falha com stubs |
| RNF-05 | Segurança · limites | Vhost: `/api/` 20 r/s burst 40; `/verificar/` 2 r/s; `client_max_body_size 6m` só no location da foto (demais `/api/` 64k); zonas novas por rota (`area_privacidade`, `area_solicitacoes`, upload de CSV do backoffice). App: janelas por minuto/hora em memória por processo (edição de contato 10/h, foto 5/h, renovação de perfil 1/5 min, busca 30/min, `/uso` 60/min) → `429 limite_taxa`; **tetos diários de negócio por contagem no banco, na própria transação** (solicitação `outro` 5/dia, 1 cancelamento aberto, 1 avaliação por solicitação, dispensa 20/dia, exportação LGPD 1/7 d) — D-17/ADR-0020; sem Redis. Limite global de chamadas ao hub a partir de `/verificar/` (RF-CA-08). | `nginx -t`; testes de limite com 2 workers |
| RNF-06 | Segurança · entrada | Pydantic com `extra="forbid"` em todos os corpos; tamanhos máximos explícitos; erro único (3.0); SQL parametrizado (regra 2). | testes de contrato |
| RNF-07 | Segurança · segredos e modos | Segredos (`HUB_CLIENT_SECRET`, `CARTEIRINHA_HMAC_KEY`, `SESSION_ENC_KEYS`, credencial RO do WordPress, credencial SMTP, OAuth2 do RD Station, token de serviço da API interna, VAPID se houver push) só em `Settings`/`.env`/Secrets Manager, com runbook de rotação (TI-12; `SESSION_ENC_KEYS` MultiFernet; rotação de `CARTEIRINHA_HMAC_KEY` regenera tokens); modos `AUTH_MODE`, `HUB_MODE`, `SMTP_MODE`, `WP_MODE`, `RD_MODE` = `stub` proibidos com `APP_ENV=production` (validador derruba o boot); `JOBS_APLICAR` em dry-run por padrão fora de produção. | testes de `config` |
| RNF-08 | Banco | TLS verificado (regra 9); grants da seção 6 **por usuário** (`apm_area`, `apm_area_bo`, `apm_area_painel`); `scripts/db_check.py` falha com `UPDATE` fora da allowlist do usuário, tabela da allowlist sem o grant, qualquer `DELETE`/DDL ou partição ausente em `evento_uso`/`evento_log`; migrações `sql/008..022` com sha256 em `schema_migrations`, aplicadas pelo operador com snapshot manual antes (RNF-26). | `db_check.py` |
| RNF-09 | Upload | RF-PE-05: magic bytes, 25 MP, EXIF transpose, sem metadados, processamento em memória e em threadpool, nada em disco além de `/tmp` tmpfs. | testes com arquivos maliciosos |
| RNF-10 | Acessibilidade | **WCAG 2.2 AA** (spec:§14; v0.1: 2.1): contraste em todos os pares de cor (variantes `-texto`, P-22); foco visível e **não obscurecido** pela barra inferior, FAB ou toast (2.4.11; `scroll-padding-bottom`); alvos de toque ≥ 44 px (2.5.8; `.botao`, `.busca__limpar`); autenticação acessível (3.3.8: OTP colável — IdP); texto ampliável sem quebrar a tela (tokens tipográficos em `rem`, `ControleFonte` em 3 passos, persistência no perfil declarado — DEC-27); nenhum estado comunicado só por cor (selos sempre com texto); `aria-pressed` em chips e marcadores, `aria-live="polite"` no toast, `role="dialog"` com foco preso e Esc, navegação completa por teclado, leitor de tela; testes com associadas e associados de faixas etárias diferentes (P-45). Público: 58% dos efetivos têm 51 anos ou mais (spec:§3 item 10). | axe-core `wcag22aa` em **todas** as rotas no e2e (TI-63); teste de Tab até o rodapé; reflow 320 px |
| RNF-11 | Acessibilidade · métrica | Lighthouse acessibilidade ≥ 90 em `/area`, `/area/beneficios`, `/area/carteirinha` (e meta não bloqueante nas demais). | Lighthouse CI |
| RNF-12 | Desempenho | **LCP < 2,5 s e INP < 200 ms no p75 do celular** (spec:§14; CLS < 0,1): orçamento no Lighthouse do e2e (`budget.json`, Moto G equivalente, 360 px), `React.lazy` por rota, bundle JS inicial ≤ 250 kB gzip, animação de entrada sem `opacity: 0` no elemento do LCP, `backdrop-filter` avaliado para INP; fontes Sora/JetBrains Mono self-hosted woff2 subset `font-display: swap`; ícones SVG inline; imagens `loading="lazy"` com proporção fixa; assets com hash `immutable`; API local p95 ≤ 300 ms, dependente de hub p95 ≤ 1,5 s (timeout 10 s). **RUM próprio** (`web-vitals` self-hosted → ações `vitais_web` e `erro_js` em `evento_uso`; indicador 14 da spec) — nenhum script de terceiro (ADR-0013, DIV-32). | `vite build --report`; Lighthouse CI com orçamento; views de `vitais_web` |
| RNF-13 | Movimento | Tempos e easing da spec (RF-SH-10); desligados com `prefers-reduced-motion: reduce` e com `animations=false`. | E2E |
| RNF-14 | pt-BR · formatos | Moeda `Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'})` sem centavos quando inteiro (`R$ 1.240`); meses de 3 letras em caixa alta nos blocos de data (SET, OUT, JUL); datas `DD/MM/AAAA`; textos em pt-BR, tom da spec. | testes unitários de formatadores |
| RNF-15 | Fuso | Banco e API em UTC (ISO 8601 com `Z`); exibição e cálculos de "dias para", "hoje", "libera em", janela 8h–20h da comunicação e fila das 8h em America/Sao_Paulo; containers web e jobs com `TZ=America/Sao_Paulo` (TI-78; DIV-41); tzdata na imagem. | testes com relógio fixo |
| RNF-16 | Privacidade / LGPD | CPF nunca na área (sessão só `cpf_mask`; API, banco, logs, `evento_uso`, importação do plano B e deep links sem CPF — D-14); QR público só nome e situação (sem categoria, DEC-36); o associado nunca vê dado do patrocinador além do valor coberto; patrocinadores, parceiros e regionais recebem só agregados com k ≥ 20 por recorte; **dado de saúde fora do sistema** (`beneficio.sigiloso ⇒ dados={}`; nada de saúde na personalização — spec:§7.1, §11.6); minimização: perfil em cache só com campos exibidos, nascimento só como faixa derivada no hub, UA só como hash/classe; `evento_uso` sem texto livre e sem valor monetário (termo de busca só sem resultado e sem identidade, RF-SH-14); consentimento versionado por finalidade e canal (§9.2); direitos do titular pelo perfil com anonimização, sem `DELETE` (§9.3); registro de acesso a dado pessoal pelo staff (RF-BO-01); base legal por finalidade e retenção por tabela definidas pelo jurídico (P-54; `docs/RETENCAO.md`). | teste de varredura de CPF em respostas, logs e CSV; `db_check`; revisão do encarregado |
| RNF-17 | Observabilidade | `request_id` em toda resposta (`X-Request-Id`) e no corpo de erro; `evento_log` para segurança/erros; `evento_uso` para analytics (seção 8) em transação própria (D-12; `audit.registrar` comita a sessão recebida, `app/audit.py:125`); `job_execucao` por execução de job (início, fim, itens, erro); contador de falhas de `evento_uso` em `/db-health`; erros ao usuário sempre como toast amigável. | testes + inspeção de `/db-health` |
| RNF-18 | Resiliência | Conteúdo do site servido só do cache local (Locaweb fora não afeta o web); perfil em cache 24 h; TotalPass em cache 10 min; hub fora → `503 fonte_indisponivel` apenas nos endpoints que dependem dele (perfil, carteirinha sem cache, foto, escrita); solicitações aceitas com hub fora (outbox). | testes com stubs em falha |
| RNF-19 | Capacidade | Web: 512M (host t4g.large), 2 workers Gunicorn/Uvicorn, `--timeout 60`; **jobs em serviço separado `area-associado-jobs`** (mesma imagem, `python -m app.jobs`, 256M, `read_only`, tmpfs com `size`, `cap_drop`, `pids_limit`, profile `jobs`, `env_file .env.jobs`, pool 2+2, heartbeat/healthcheck; loop in-process + `GET_LOCK` por job + `job_execucao` + `JOBS_APLICAR` dry-run — D-16/ADR-0019); Pillow limitado a 1 processamento por worker (semáforo); conta própria no hub para os jobs (P-41). | teste de carga leve + `docker stats`; `job_execucao` |
| RNF-20 | Compatibilidade | Navegadores evergreen (duas últimas versões de Chrome, Edge, Firefox, Safari/iOS Safari); 390 a 1440 px sem rolagem horizontal. | Playwright 390/1440 |
| RNF-21 | Persistência local | Nenhum dado do associado em `localStorage`/`sessionStorage`/IndexedDB; estado de domínio só no backend (spec, "Persistência local", com D-01). | lint + revisão |
| RNF-22 | Cache HTTP | `index.html` e `/api/*` com `no-store`; `/verificar/*` `no-store` + `noindex`; foto, imagem/PDF da carteirinha e PDF do extrato `private, no-cache`/`no-store` + ETag quando cabível; `manifest.webmanifest` com `Cache-Control` próprio; assets da SPA `immutable`. | testes de cabeçalho |
| RNF-23 | PWA (instalável) | **Manifest-only** (DEC-07, DIV-39; spec:§14 "Instalável"): `manifest.webmanifest` (`start_url=/area`, `scope=/area/`, `display=standalone`) e ícones 192/512 maskable servidos pelo FastAPI, `<link rel=manifest>`, `location` no vhost; **sem Service Worker** (`/area` é `no-store` com sessão e nonce; `/api` nunca cacheável). SW restrito (`worker-src 'self'`, network-only em navegação e `/api`, cache-first só em assets imutáveis, unregister no logout) só com Web Push aprovado (DEC-08) e ADR própria; lint contra `caches`/`indexedDB`/`serviceWorker`. Ícones oficiais por P-38. App nativo só se os dados de uso justificarem. | e2e sem `securitypolicyviolation` com o manifest; Lighthouse "installable" |
| RNF-24 | Documentação · OpenAPI | API documentada como **artefato versionado** (spec:§14): `scripts/openapi_export.py` roda no build (`APP_ENV=test`) e grava `docs/api/openapi.json`; `operation_id` estável por rota; modelos Pydantic de resposta (incl. `ApiError`); teste que falha se o arquivo divergir do código. `/openapi.json` e `/docs` **nunca em produção** (403 no edge mantido; só `APP_ENV=development` ou flag na rede interna) — DEC-32, DIV-09. Manual de operação do backoffice quando ele existir. | TI-07; teste de diff no CI |
| RNF-25 | Ambientes e publicação | Três ambientes (spec:§14): **dev** (container local, modos stub), **homologação** com dados anonimizados (`docker-compose.hml.yml`, schema e usuário próprios com as mesmas migrações, vhost `hml-minha.apm.org.br` restrito por allowlist IP/Cloudflare Access, `noindex`, hub stub ou sandbox do Dataverse — P-57; RDS separado por snapshot **antes** de `HUB_ESCRITA_HABILITADA=true`, DEC-30) e **produção**. Publicação: CI valida (`npm run check`, pytest, e2e com stub + MySQL, Lighthouse com orçamento, `pip-audit`/`npm audit`, `csp_check`/`db_check`) e deploy **pull-based** no host (`scripts/deploy.sh`: `git pull --ff-only`, build `DOCKER_BUILDKIT=0` com tag `area:<sha>`, `up -d`, espera healthy, smoke, rollback para a tag anterior) — DEC-31, DIV-40; sem deploy automático. | `deploy.sh` ensaiado; CI verde (P-25) |
| RNF-26 | Backup e restauração | RDS `mysql-producao`: snapshots diários + PITR, retenção 7 → **14 dias** (DEC-33); **snapshot manual antes de cada `sql/NNN` e do cutover**; **teste de restauração** trimestral em instância temporária (`db_check`, contagens, `schema_migrations`) com evidência datada em `docs/CONCLUIDO.md` (spec:§14 "cópia de segurança diária com teste de restauração"; DIV-21); `.env` replicado no Secrets Manager e conferido por `scripts/env_check.sh` (P-36); opcional export de `evento_log` para S3 Object Lock. SLO declarado 99,5 % (Single-AZ). | runbook (TI-76); P-59, P-60 |
| RNF-27 | Disponibilidade e monitoramento | Monitor externo de `/health` nos hosts (P-61); alerta diário/horário (5xx do porteiro, Tracebacks, `uso_falhas`, `job_execucao` com erro, 429 anormais, certificado < 30 dias, `.env` ≠ cofre) no padrão `login_associado/deploy/alertas.sh`; logs persistentes (`awslogs`/`journald`) para não perder `docker logs` na recriação; página de manutenção no vhost; critério de "go" do cutover pelo indicador 14 (spec:§11.3). | TI-75, TI-84; `verificar-pos-reboot.sh` |
| RNF-28 | Auditoria · log imutável | Solicitações (`solicitacao_evento`), consentimentos, uso/valor, ações do backoffice (`backoffice_auditoria` com valor anterior/novo e justificativa) e leituras de dado pessoal pelo staff (`acesso_dado_pessoal`) são tabelas **só `INSERT`** por privilégio, com CHECK anti-segredo/CPF (spec:§14 "Auditoria", "LGPD"); retenção por tabela em `docs/RETENCAO.md` com prazos do jurídico (P-54) e expurgo só por partição mensal (`evento_uso`, `evento_log`, `comunicacao_envio`, `score_engajamento`) ou procedimento do operador. | `db_check` (grants); `docs/PROVISIONAMENTO.md` |
| RNF-29 | Conteúdo editável sem publicação | Tudo o que muda com frequência é **dado**, não código (spec:§3 item 8, §14): ficha de benefício, carências, parâmetros, valores de referência, FAQ, destaques, textos de sistema (estados vazios/erro), passos da trilha, matriz de afinidade, textos de consentimento — editados pelo backoffice com `apm_area_bo` (D-19) ou, até ele existir, por script administrativo do operador com histórico (`beneficio_versao`, `backoffice_auditoria`); leitura pela área com cache ≤ 60 s. `app/dominio/catalogo.py` (conteúdo editorial em código) é transitório e migra para `sql/016`/`sql/020`. | teste: alteração no banco reflete sem deploy |
| RNF-30 | Identidade visual | Paleta e tipografia seguem os **mockups da agência** (ADR-0017: Sora, cards de vidro, trilho em pílula) — decisão do usuário mantida frente ao §14 da spec (Verdana; `#004165`, `#009581`, `#00675A`, `#616365`; botão principal verde): divergência formal registrada para Marketing/agência (DIV-34, DIV-37, DIV-43; P-43). Um botão principal por bloco; selos sempre com texto; conteúdo patrocinado sempre sinalizado (spec:§3.2). | revisão visual da agência (P-39, P-42) |

---

## 5. Integrações por fonte

> **Revisão v0.2 (spec:§13; `LEVANTAMENTO §8`).** As seções 5.1–5.8 descrevem o que existe ou já
> estava decidido (5.3 foi implementada no hub na Fase 2b: `associado.perfil_consultar`,
> `contato_atualizar`, `foto_obter`, `foto_atualizar` por `contact_id`, escrita atrás de
> `HUB_ESCRITA_HABILITADA`; `docs/CONTRATO-HUB.md`). As seções **5.9–5.13** são novas: RD Station,
> CSV do plano B, ferramentas novas do hub e conta de jobs, contrato de dados campo a campo e a
> confirmação de que o WordPress segue a ADR-0006. Toda integração nova segue a skill
> `integracao-terceiro-minha-apm`: ADR própria, cliente em `app/integracoes/` com timeout e erro
> tipado, modo stub proibido em produção, allowlist de hosts, `scripts/check_<fonte>.py`.

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
- **Paginação:** `dataverse.py` do hub só faz GET e não segue `odata.nextLink` — corrigir na extensão para `solicitacao.alteracoes_consultar`.

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
- **Segurança:** usuário novo somente leitura (SELECT nas 6 tabelas), rotação e revogação de `portal_apm%` (credencial vazada, grant aberto), TLS se a Locaweb suportar (senão: ADR-0006 registra o risco aceito), host de imagens validado contra `CSP_IMG_HOSTS` (fora → placeholder), HTML do conteúdo **não** é renderizado na SPA (só título, resumo em texto puro e link).
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

### 5.9 RD Station (régua de comunicação) — novo na v0.2

- **Papel (DEC-18):** a área **emite** campos e eventos; a régua de 29/09 (69 peças, 8 fluxos),
  o limite de 2 mensagens/semana por pessoa (WhatsApp no máximo 1), a prioridade entre fluxos
  (3, 5, 4, 6, 1, 2) e o horário 8h–20h vivem no RD (spec:§12.1, §12.3). A área aplica **supressão**
  por campos e grava consentimento (RF-CM-03). Transacionais **nunca** saem pelo RD (RF-CM-02).
- **Escrevemos:** `POST /platform/events` (conversão com `conversion_identifier` por gatilho) e
  `PATCH contacts/email:{email}` para campos `cf_apm_*` e descadastro síncrono (fallback na outbox).
  Campos: `cf_apm_contactid` (**chave; sempre**), `cf_apm_categoria`, `cf_apm_score` (F2),
  `cf_apm_valor_ano`, `cf_apm_suprimir_ofertas`, `cf_apm_cancelamento_pedido`,
  `cf_apm_data_inadimplencia` (só com cobrança), `cf_apm_canal_preferido`. **Nunca** CPF, nunca
  `available_for_mailing`; e-mail só como endereço do registro (muda; a chave é o `contact_id`).
  Campos `cf_apm_*` já existem no RD (planilha de 29/10); os novos são P-46.
- **Lemos:** `GET account_info` e `contacts/fields` no boot (conferência dos campos). Retorno
  (entregue/aberto/clicado) por **UTM + código do gatilho** no clique (RF-CM-05); webhook do RD é
  rota pública nova → só na F2, com ADR, `limit_req` e assinatura.
- **Transporte:** `app/integracoes/rdstation.py` **só no serviço de jobs** (job `outbox_rd`;
  `GET_LOCK`; revalida o fato antes de enviar; recuo exponencial); OAuth2 refresh → access em
  memória de processo (molde do `totalpass`); `RD_MODE=real|stub` (stub proibido em produção);
  `scripts/check_rd.py`; egress 443 do container de jobs (P-63). Settings: `RD_CLIENT_ID`,
  `RD_CLIENT_SECRET`, `RD_REFRESH_TOKEN`, `RD_MODE`.
- **Gatilhos que a área emite (F1):** A03 carência vencida (job), A04 solicitação criada, A05 sem
  retorno, A06 concluída, A16 cancelamento; A01/A02/A13 por jobs de diferença no cache de perfil
  (TI-55); A09 só quando houver cobrança; A17 (lead) e A18 (aniversário) fora da área
  (`LEVANTAMENTO §7`). F2: A07, A08, A10–A15, A19, A20.
- **Falha e degradação:** sem credencial ou RD fora, a outbox acumula (`pendente`/`erro`) e, após
  N tentativas, `falhou` → B01; nada é perdido; nenhum e-mail de marketing sai pela área.
- **Pendências:** P-46 (app OAuth2, campos novos, tabela gatilho → `conversion_identifier`, dono
  único dos campos), P-54 (base legal por finalidade), P-63 (egress). ADR candidata "Outbox de
  comunicação e RD Station" (Onda 3).

### 5.10 Parceiros sem API — CSV do plano B (spec:§13.3) — novo na v0.2

- **O que chega:** um CSV por parceiro por mês, até o dia 10, UTF-8, `;`, 11 colunas:
  `cpf;parceiro_id;beneficio_id;tipo;data_evento;status;valor_referencia;valor_pago;economia;id_externo;observacao`
  (`tipo` ∈ lead|contratacao|uso|cancelamento; `status` ∈ em_andamento|ganho|perdido|usado;
  `id_externo` obrigatório e único por parceiro; `observacao` ≤ 200).
- **Conflito e solução (DIV-04, DEC-05):** o arquivo é chaveado por **CPF** e a área não aceita
  CPF (D-14). O arquivo vai ao `mcp_hub` (`importacao.resolver_lote`, TI-51), que devolve cada
  linha com `contact_id` ou `nao_encontrado` e cria o **lead** no RD/CRM para o CPF que não é
  associado (spec:§10.4; DEC-19). A área persiste só `importacao` e `importacao_linha` **sem CPF**;
  no job, o CPF existe só em memória e é descartado. A coluna `cpf` do layout continua existindo
  para o parceiro — quem a lê é o hub. Canal: upload no backoffice na F1 (até lá, operador copia
  para o volume dos jobs); S3 presigned ou módulo no `apm-parceiros` depois; **nunca** SFTP novo
  nem e-mail comum (P-53, P-63, TI-81).
- **Validação (TI, parser puro com fixtures):** encoding, separador, 11 colunas, tipos, datas
  `AAAA-MM-DD`, valores com ponto decimal, duplicidade por `(parceiro_id, id_externo)`, associado
  existente, CPF em `observacao` (recusa a linha). Prévia com erro por linha → confirmar →
  `uso_valor` nível 3 (nível 4 após validação do Financeiro) e fechamento de solicitações por
  `id_externo` → devolução de erros por SMTP sem dado pessoal (RF-BO-03).
- **Frequência:** mensal; cobrança no dia 11 e registro no contrato após dois atrasos são
  processo de Benefícios (spec:§10.3), não da área.
- **Falha:** layout fora do padrão → `devolvida` com o modelo; nada entra no Meu valor sem
  confirmação. Pendências: P-53 (arquivos), P-48 (códigos `PAR`/`BEN` do catálogo), P-04 ampliada
  (ferramenta do hub).

### 5.11 `mcp_hub` — ferramentas novas e conta de jobs (v0.2)

Estado em 30/10: a área usa `associado.perfil_consultar`, `associado.contato_atualizar`,
`associado.foto_obter`, `associado.foto_atualizar` por `contact_id` (`docs/CONTRATO-HUB.md`;
hub real só leitura desde 21/10, escrita atrás de `HUB_ESCRITA_HABILITADA`). O hub é **pull**
(sem webhook): avisos automáticos do cadastro/cobrança (spec:§13.2) são substituídos por **jobs de
diferença** ≤ 24 h (DIV-30, TI-55). Ferramentas a criar/conceder (repositório `mcp_hub`), todas por
`contact_id` e **sem CPF na saída**:

| Ferramenta | Serve a | Onda/Fase | Pendência |
|---|---|---|---|
| `associado.situacao(contact_id)` → `{ativo: bool, situacao_cod, situacao_rotulo, categoria_cod, verificado_em}` | RF-CA-08 (verificação em tempo quase real), jobs de diferença A01/A13 | Onda 1 (TI-47) | cota P-41 |
| `associado.historico_associacao(contact_id)` | `associado_categoria_hist` (carência se reiniciar, indicador 9, A13) | Onda 1 (TI-47) | confirmar se `sol_associacao` registra categoria (P-56) |
| `associado.perfil_consultar` ampliada: `faixa_carreira` (derivada da data de nascimento **no hub**; a data nunca sai), `nome_social`, `especialidades`, `regional_cod`, `isento_remido`, situação normalizada (`ativo\|suspenso\|cancelado\|outro`) | personalização §7.1, elegibilidade por região, tratamento | Fase 4 (TI-48) | atributos no CRM (P-56) |
| `associado.alterados_desde(cursor)` | jobs de diferença (A01, A13, `atualizar_perfis` só de quem acessou em 90 d) | Fase 4 (TI-51, TI-55) | cota P-41 |
| `financeiro.situacao_consultar(contact_id)` → `{situacao, dias_atraso}` · `financeiro.faturas_listar(contact_id)` · `financeiro.vencidas_desde(cursor)` | RF-FI-01/02/05, estado "Suspenso", A09 | Fase 7 (TI-49) | P-04, P-08, P-58 |
| `solicitacao.espelhar` / `solicitacao.status_atualizar` / `solicitacao.alteracoes_consultar(cursor)` (credencial só Create/Write em `task`; idempotência por `uuid`; `odata.nextLink` tratado no hub) | §7.5 | Fase 3 (TI-50; contrato + stub); real com P-06 | P-06 |
| `importacao.resolver_lote(csv)` → linhas com `contact_id` ou `nao_encontrado`; lead → RD/CRM | §5.10, RF-BO-03 | Fase 4 (TI-51) | P-04 ampliada |
| `associado.visao_360(contact_id)` (sensível; grant só ao backoffice) | RF-BO-06 | BO | DEC-03 |
| `totalpass.adesao_consultar(contact_id)` | RF-BE-10 | Fase 4 | P-04 |

**Conta `area-associado-jobs`** (TI-51, D-16): conta de serviço própria no hub para o serviço de
jobs, com cota separada da conta `area-associado` (web) — os limites provisórios da P-41
(120 chamadas/min, 5.000 PII/dia) são incompatíveis com varreduras em lote; a resposta à P-41 é
refeita com a estimativa da base ativa (EXT-23/P-41). Token em memória de processo, como hoje.

### 5.12 Contrato de dados com cadastro e cobrança (spec:§13.2), campo a campo

| Grupo / campo | Fonte hoje | Falta | Dono |
|---|---|---|---|
| identificador interno estável | `contact_id` (IdP e hub) | — | — |
| CPF | só `cpf_mask` na sessão | **nunca entra na área** (D-14); o hub resolve quando a fonte exige | — |
| nome, e-mail, celular | IdP (`profile`, `email`) + hub | escrita existe, desligada (P-29) | CRM admin |
| nome social, data de nascimento | nada (hub lê nascimento em `associado.consultar`, não concedida) | `faixa_carreira` derivada + `nome_social` em `perfil_consultar` (TI-48) | CRM admin / hub (P-56) |
| categoria atual, data de filiação | IdP (`carteirinha`) + hub, como **rótulo** | código junto do rótulo (`associado.situacao`); de-para TI-92 | hub / negócio (P-49) |
| histórico de categorias com datas | hub `historico_associacao` só por CPF, não concedida | versão por `contact_id` (TI-47); confirmar se `sol_associacao` registra categoria | hub + CRM admin |
| situação (ativo, suspenso, cancelado) | rótulo `alf_status_associativo` | enum fechado no hub; **separar de pendência financeira** (DEC-14, DIV-31) | hub + negócio |
| isenção/remição, especialidades, regional/distrital | nada | atributos do `contact` → `perfil_consultar` | CRM admin (P-56) |
| CRM e UF | IdP + hub ✓ | — | — |
| financeiro: situação (dias), valor/forma, mensalidades, pagamentos | hub `faturas_associado` por CPF, não concedida | `contact_id` + regra de situação (TI-49) | P-04, P-08, Financeiro |
| segunda via (PDF, linha digitável, Pix) | **nada** (F&O via OData não expõe boleto) | fonte inexistente: só com o "novo sistema de cobrança" ou gateway | Financeiro (P-58) |
| avisos automáticos (filiação criada, categoria alterada, pagamento confirmado, mensalidade vencida, cancelamento, contato alterado) | **nenhum** (hub pull; CRM→RD "Não Funcionando") | eventos do cadastro/cobrança ou webhook Dataverse → hub; substituto: jobs de diferença ≤ 24 h (TI-55) | CRM admin / F&O / P-58 |
| escrita: contato pelo associado · pedido ao cadastro | `contato_atualizar` (desligada) · `task` (P-06) | ligar após P-29; `solicitacao.espelhar` (TI-50) | CRM admin |
| requisitos: homologação anonimizada, OpenAPI, < 1 s, aviso de manutenção | hub só produção; OpenAPI do hub existe | sandbox do Dataverse (P-57); homologação (DEC-30) | TI |

O "novo sistema de cadastro e cobrança" (spec:§13.1) não aparece em nenhum repositório (DEC-17,
P-58). Em qualquer hipótese a área não muda: só o conector do hub; o contrato `associado.*`/
`financeiro.*` por `contact_id` atrás do hub é o ponto de estabilidade.

### 5.13 WordPress — inalterado (ADR-0006, DIV-29)

A spec cita "API do WordPress e acesso único" para notícias, Portal MBE e biblioteca
(spec:§13.1). A decisão de ler o MySQL `portal_apm` diretamente, com usuário RO, **só no serviço
de jobs** e com cache local (§5.6; D-07) é mantida; `WP_MODE=real|stub` com fixtures permite
construir P10/P11 sem a Locaweb (TI-56). MBE e biblioteca não têm fonte (P-51). Fechamento da
porta 3306 da Locaweb depende de P-07/P-16.
---

## 6. Modelo de dados lógico

Convenções (mantidas): chave de associado `contact_id CHAR(36)` com CHECK de GUID (D-14; padrão de
`sql/005`), `sub_hash CHAR(64)` (HMAC com `LOG_HASH_KEY`) em toda tabela de guarda longa, datas
`DATETIME(6)` UTC, JSON e texto livre com `CHECK` que recusa chaves proibidas e CPF (lista de
`app/audit.py` + regex de `sql/004`), remoção lógica por coluna (sem `DELETE`), `GRANT UPDATE` **na
própria migração** com comentário de justificativa (D-05, ADR-0004). Reescrito na v0.2 a partir
do modelo de dados da spec (spec:§11.1, 15 entidades) e do `LEVANTAMENTO §6.1`; detalhe coluna a
coluna em `docs/spec-v2/personas/atlas.md` ("Modelo de dados proposto"). A numeração abaixo é a
**ordem de aplicação acordada em 30/10/2026** (deslocada em relação ao levantamento porque a
partição e as flags entram antes); o número definitivo é o da migração aprovada.

### 6.1 Migrações existentes (`sql/000–007`)

| Migração | Tabela | Conteúdo | Grant de `apm_area` |
|---|---|---|---|
| `000` | — | schema `area_associado`, usuário `apm_area` (`REQUIRE SSL`; `SELECT, INSERT, EXECUTE`) | — |
| `001` | `schema_migrations` | controle com sha256 | SELECT |
| `002` | `evento_log` | trilha de segurança (append-only; CHECK anti-segredo/CPF) | INSERT |
| `003` | `feature_flag` | 8 chaves (seção 10); operador por SQL | SELECT |
| `004` | `evento_uso` | analytics (seção 8; append-only) | INSERT |
| `005` | `associado` | `contact_id`, `sub_hash`, primeiro/último acesso, `carteirinha_token` | SELECT, INSERT, UPDATE |
| `006` | `associado_perfil` | cache do `contact` exibido + `foto_miniatura` + ETag | SELECT, INSERT, UPDATE |
| `007` | `email_verificacao` | troca de e-mail por código (ADR-0015) | SELECT, INSERT, UPDATE |

### 6.2 Migrações planejadas (`sql/008–025`)

> **Renumeração de 2026-10-30 (Onda 2):** a numeração segue a **ordem de criação**, para o operador
> aplicar sempre em ordem crescente. A Onda 2 precisou de comunicação, ajuda/parâmetros e revogação da
> carteirinha antes do catálogo: `012` comunicação (era 016), `013` ajuda e parâmetros (saiu do
> catálogo), `014` revogação da carteirinha (nova); as reservas seguintes deslocaram (catálogo 015,
> valor 016, portal 017, LGPD 018, trilha/clube 019, backoffice 020, financeiro 021, score 022, base
> ativa 023, views 024).
>
> **Renumeração de 2026-11-04 (espelho no CRM, ADR-0023):** `015` = colunas do espelho por
> incident/opportunity; as reservas seguintes andaram uma casa (catálogo 016, valor 017, portal 018,
> LGPD 019, trilha/clube 020, backoffice 021, financeiro 022, score 023, base ativa 024, views 025).
> Comentários dentro de migrações JÁ APLICADAS (`010`, `012`, `013`) mantêm a numeração antiga: arquivo
> aplicado não se edita (o sha256 está em `schema_migrations`).

Coluna "UPDATE" = quem recebe o grant: `web` = `apm_area`; `bo` = `apm_area_bo` (D-19; até o
backoffice existir, operador por SQL); `—` = ninguém (append-only ou só leitura). "Spec" = entidade
de spec:§11.1 que a tabela realiza.

| Migração | Tabelas | Spec §11.1 | UPDATE (justificativa) | Append-only | Fase |
|---|---|---|---|---|---|
| **`008`** | `evento_uso`, `evento_log` → `ALTER`: PK `(id, ocorrido_em)` + `PARTITION BY RANGE (TO_DAYS(ocorrido_em))` mensal (24 partições + `MAXVALUE`); procedimento para partições futuras; expurgo = `DROP PARTITION` administrativo, sem `DELETE` (P-15) | Evento de uso | — | — | **Onda 1** (TI-02; aplicação pelo operador) |
| **`009`** | `feature_flag` → seed das 7 chaves novas desligadas (seção 10; D-18) | — | — | — | Onda 1 (TI-13) |
| **`010`** | `solicitacao` (8 status; `beneficio_id`, `parceiro_id`, `tipo_ativacao`, `tipo_servico`, `canal_envio`, `prazo_retorno_dias`, `enviada_em`, `sem_retorno_desde`, `responsavel`, `resultado JSON`, `avaliacao_nota/comentario`, `avaliada_em`, `cancel_motivo`, `chave_idempotencia`, `crm_id`, `crm_sync`, `crm_tentativas`, `crm_proxima_em`, `dados JSON ≤ 16 kB`) · `solicitacao_evento` (`de_status`, `para_status`, `ator`, `origem`, `usuario_interno`, `justificativa` — CHECK obrigatória quando `origem='backoffice'` —, `mensagem_publica`, `conteudo_enviado` = campos + sha256 + destino, `request_id`) | Solicitação · Log de status | `solicitacao`: web (transição condicional, outbox CRM, marcador, avaliação) e bo (status com justificativa) | `solicitacao_evento` | **3** (TI-14; D-15) |
| **`011`** | `job_execucao` (`job` com CHECK regex, `iniciado_em`, `terminado_em`, `status ∈ executando\|ok\|erro\|abortado`, `itens_lidos/gravados/erro`, `erro_resumo` com CHECK anti-segredo, `host`, `versao_app`) | — (RNF-17) | web/jobs (fechar a linha aberta no início) | — | 3 (TI-01; D-16) |
| **`012`** | **Comunicação:** `comunicacao_evento` (outbox; único `(gatilho, contact_id, referencia_id)`; `(status, enviar_apos)`), `comunicacao_envio` (particionada), `comunicacao_supressao`, `notificacao` (UPDATE só `lida_em`), `fila_ligacao` | Comunicação | `comunicacao_evento`: jobs (status, tentativas); `notificacao`: web (`lida_em`); `fila_ligacao`: bo (resultado) | `comunicacao_envio`, `comunicacao_supressao` | 3 (TI-18; produção) / 3b (envio) |
| **`013`** | **Ajuda e parâmetros:** `faq` (pergunta, resposta, categoria, ordem, `publicada`, `atualizada_em`; FULLTEXT opcional), `texto_sistema` (chave, texto, vigência — estados vazios/erro editáveis), `parametro` (chave PK com CHECK regex como `feature_flag`, valor, tipo `int\|decimal\|bool\|texto`, descrição; seed: `avaliacao_prazo_dias`=30, `prazo_retorno_padrao_dias`, `central_horario`, `central_telefone` vazio até P-44) | Segmento e bloco (conteúdo) · configuração B13 | **bo** (até o backoffice: operador por SQL); web só lê | — | **Onda 2** (TI-20) |
| **`014`** | **Revogação da carteirinha:** `ALTER associado` + `carteirinha_revogada_em DATETIME(6) NULL`, `situacao_consultada_em DATETIME(6) NULL`, `situacao_normalizada` (cache curto da verificação pública; UPDATE já concedido na `005`) | Filiação (situação) | web/jobs (já em `005`) | — | **Onda 2** (TI-45) |
| **`015`** | **Espelho no CRM (ADR-0023):** `ALTER solicitacao` + `crm_entidade ENUM(ocorrencia,oportunidade)`, `crm_protocolo` (ticketnumber, CHECK de formato, só ocorrência), `crm_estado`/`crm_status` (último `statecode`/`statuscode` visto: a sincronização reage à MUDANÇA), `crm_consultado_em` (cadência por contato), `crm_sync` + `retido`; CHECKs `crm_id = id` e coerência do par | — | web (`GRANT UPDATE` só nas 5 colunas novas: o serviço de jobs grava a criação e cada leitura do CRM) | — | Onda 2b (2026-11-04) |
| **`016`** | **Catálogo como dado:** `parceiro` (código APM `PAR017`, `requisito ∈ api\|relatorio\|portal\|email`, `prazo_retorno_dias`, vigência, `contato JSON` sem CPF, `host`), `beneficio_categoria` (8 da spec), `beneficio` (ficha B03: textos, `tipo_ativacao` 1–6, `destino`/`url_acesso`, `carencia_meses` 0–12, `exige_adimplencia`, `regional`, `modalidade_mensuracao`, `prazo_retorno_dias`, vigência, `status ∈ rascunho\|aprovado\|publicado\|encerrado`, `patrocinado`, `sigiloso`, `ordem`), `beneficio_versao` (snapshot JSON), `beneficio_faq`, `beneficio_categoria_associado` (matriz × categoria), `beneficio_afinidade` (segmento, pontos 0–3), `beneficio_ativacao` (tipo 1; `ativo`, `ativado_em`, `desativado_em`), `recomendacao_dispensa`, `recomendacao_exposicao`, `associado_categoria_hist`, `ALTER associado_perfil` (+`faixa_carreira`, `especialidade_cod`, `regional_cod`, `nome_social`, `isento_remido`), `destaque_editorial` (`UNIQUE (segmento, vigência)`), `busca_sem_resultado` (sem identidade), `categoria_associado` (de-para rótulo → código, TI-92) | Benefício · Parceiro e contrato · Segmento e bloco · Filiação (hist.) | catálogo/configuração/editorial: **bo**; `beneficio_ativacao`, `recomendacao_exposicao`: web | `beneficio_versao`, `recomendacao_dispensa`, `associado_categoria_hist`, `busca_sem_resultado` | **4** (TI-29); seed real só com P-48 |
| **`017`** | **Valor e importação:** `valor_referencia` (valor, `base ∈ anual\|por_uso`, fonte, `data_fonte`, `aprovado_por`, `aprovado_em`, vigência, `revisao_prevista_em`; vigente = última aprovada ≤ hoje), `uso_valor` (RF-FA-09; CHECK `economia = referencia − pago`; CHECK nível 4 ⇒ `validado_em`; `estorna_id`, `valida_id`), `importacao` (cabeçalho: parceiro, competência, `arquivo_sha256`, contagens, `status ∈ recebida\|validada\|confirmada\|devolvida`, usuário), `importacao_linha` (**sem CPF**; `contact_id` ou `sem_associado`; único `(parceiro_id, id_externo)`; `erro_codigo`; CHECK anti-CPF em `observacao`), view `vw_meu_valor_ano` | Uso e valor · Importação | `importacao`: bo (status, contagens) | `valor_referencia`, `uso_valor`, `importacao_linha` | 4 (TI-35, TI-54; antecipada da 8) |
| **`018`** | **Conteúdo do portal:** `noticia_cache`, `evento_cache` (+ `categoria_carencia`), `tema`, `associado_tema`, `noticia_salva`, `evento_inscricao` (+ `perfil_preco`, `status ∈ interesse\|inscrito`) | Conteúdo e evento | web (cache por upsert; "desfazer" por coluna) | — | 5 (TI-56; ADR-0006) |
| **`019`** | **LGPD e preferências:** `consentimento_texto` (finalidade, canal, versão, texto; texto novo = linha nova), `consentimento` (append; `vw_consentimento_atual`), `preferencia_canal`, `perfil_declarado` (tratamento, área de atuação, região, temas), `pergunta_perfil` (catálogo), `titular_pedido` (`tipo ∈ exportacao\|exclusao`, status, protocolo), colunas `anonimizado_em` em `associado_perfil`/`perfil_declarado` | Perfil declarado · Consentimento | `preferencia_canal`, `perfil_declarado`: web; `titular_pedido`: web (abrir) e bo (fechar) | `consentimento_texto`, `consentimento` | **3b** (TI-25) |
| **`020`** | **Trilha, comunidade, clube:** `trilha_passo` (por categoria; `evento_conclusao`, `carencia_meses`, `valor_referencia`), `trilha_progresso` (append), `comunidade`, `comunidade_adesao`, `oferta_clube` | Conteúdo e evento | `comunidade_adesao`: web; `oferta_clube`, `trilha_passo`, `comunidade`: bo | `trilha_progresso` | 4 (trilha) / 6 (comunidade, clube) |
| **`021`** | **Backoffice:** `usuario_interno` (e-mail, nome, `perfil ENUM(8)`, ativo; **sem senha** — identidade externa), `backoffice_auditoria` (valor anterior/novo JSON, justificativa; CHECK anti-segredo/CPF), `acesso_dado_pessoal` (quem, `contact_id` alvo, campos); criação do usuário `apm_area_bo` e `GRANT UPDATE` nas tabelas de catálogo/configuração | Usuário interno e auditoria | `usuario_interno`: bo | `backoffice_auditoria`, `acesso_dado_pessoal` | BO (TI-80; D-19) |
| **`022`** | `associado_financeiro` (cache mínimo: `situacao ∈ em_dia\|em_atraso\|desconhecida`, `dias_atraso`, `atualizado_em`, `fonte`; **sem valores nem mensalidades**) | Situação financeira | jobs (cache) | — | 7 (⛔ P-04, P-08) |
| **`023`** | `score_engajamento` (PK `(contact_id, data)`, 5 componentes, `versao_pesos`; particionada por mês), `score_pesos` | — (spec:§11.4) | — | ambas | F2 (TI-86) |
| **`024`** | `base_ativa_mensal` (`mes`, `categoria`, `regional`, `total`, `novos`, `cancelados`; gravada por job a partir do hub) | — (denominadores §11.3) | — | sim | BO/4 (TI-44; EXT-25) |
| **`025`** | views `vw_ind_01..14`, `vw_qualidade_parceiro_mes`, `vw_consentimento_atual`, `vw_meu_valor_ano` (se não criadas antes); usuário `apm_area_painel` só `SELECT` nas views; k ≥ 20 nos recortes a terceiro/regional | Evento de uso (painéis) | — | — | BO/4 (TI-44; DEC-16) |

Entidades da spec **sem tabela própria na área**, por desenho: *Associado* e *Filiação* (fonte
CRM via hub; cache em `associado_perfil` + histórico em `associado_categoria_hist`), *Situação
financeira* (só o cache mínimo de `021`; valores vêm do hub na hora, só na P08), *Conteúdo
editorial* dos protótipos (migra de `app/dominio/catalogo.py` para `texto_sistema`/
`destaque_editorial`/`oferta_clube` em `013`/`015`/`019`), *Adesão TotalPass* (cache em memória 10 min),
*Carteirinha* e *Meu valor* (derivadas), *Lead* (RD/CRM, DEC-19).

### 6.3 Allowlist de `UPDATE` por usuário (`scripts/db_check.py`, TI-03)

| Usuário | Tabelas com `UPDATE` | Nunca |
|---|---|---|
| `apm_area` (web e jobs) | `associado`, `associado_perfil`, `email_verificacao` (existentes) · `solicitacao`, `job_execucao`, `beneficio_ativacao`, `recomendacao_exposicao`, `preferencia_canal`, `perfil_declarado`, `titular_pedido`, `comunicacao_evento`, `notificacao` (`lida_em`), `noticia_cache`, `evento_cache`, `associado_tema`, `noticia_salva`, `evento_inscricao`, `comunidade_adesao`, `associado_financeiro` | `UPDATE` em catálogo/configuração (`beneficio*`, `parceiro`, `parametro`, `valor_referencia`, `faq`, `texto_sistema`, `destaque_editorial`, `oferta_clube`, `trilha_passo`, `comunidade`, `usuario_interno`); `DELETE` em qualquer tabela; DDL |
| `apm_area_bo` (backoffice; D-19) | `beneficio`, `beneficio_categoria`, `beneficio_faq`, `beneficio_categoria_associado`, `beneficio_afinidade`, `parceiro`, `parametro`, `faq`, `texto_sistema`, `destaque_editorial`, `oferta_clube`, `trilha_passo`, `comunidade`, `feature_flag`, `usuario_interno`, `importacao`, `solicitacao` (status com justificativa), `titular_pedido`, `fila_ligacao` | `UPDATE` em tabelas do associado (`associado*`, `beneficio_ativacao`, `perfil_declarado`, `preferencia_canal`, `consentimento`, `uso_valor`); `DELETE`; DDL |
| `apm_area_painel` (ferramenta de painel; DEC-16) | nenhuma — só `SELECT` nas views `vw_*` | qualquer tabela base |

A allowlist do `db_check.py` lista **só tabelas já migradas** (hoje `associado`, `associado_perfil`,
`email_verificacao`); cada migração acrescenta as suas no mesmo commit. `db_check` falha se:
tabela da allowlist existe sem o grant (ADR-0004 §6), `UPDATE` fora da allowlist do usuário,
`DELETE` ou DDL em qualquer tabela, partição ausente em `evento_uso`/`evento_log`.

### 6.4 Append-only (só `INSERT`, por privilégio)

`evento_log`, `evento_uso`, `solicitacao_evento`, `beneficio_versao`, `recomendacao_dispensa`,
`associado_categoria_hist`, `busca_sem_resultado`, `valor_referencia`, `uso_valor`,
`importacao_linha`, `consentimento_texto`, `consentimento`, `comunicacao_envio`,
`comunicacao_supressao`, `trilha_progresso`, `backoffice_auditoria`, `acesso_dado_pessoal`,
`score_engajamento`, `score_pesos`, `base_ativa_mensal`. Correção = linha nova (estorno,
validação, versão); estado atual = última linha (views). Purga só por partição (`evento_uso`,
`evento_log`, `comunicacao_envio`, `score_engajamento`) ou por procedimento do operador conforme
`docs/RETENCAO.md` (TI-28; prazos em P-54). `consentimento` e `solicitacao_evento` são de guarda
longa e nunca se purgam por partição.

### 6.5 O que **nunca** existe na área

CPF em qualquer forma (ADR-0014 — inclusive na importação do plano B e em `lead`); senha de
usuário interno (identidade externa); payload de mensagem de marketing (vive no RD); dado de
saúde (spec:§11.6 — `beneficio.sigiloso ⇒ dados={}`); data de nascimento (só `faixa_carreira`
derivada no hub); valores e mensalidades do associado além do cache de situação; `lead` com dado
pessoal (DEC-19); UA bruto (só `ua_hash` em `evento_log` e classe grossa de dispositivo em
`evento_uso`); termo de busca associado a pessoa (RF-SH-14).

---

## 7. Solicitações — máquina de estados (v2, 8 status)

Revisada na v0.2 para spec:§8.5 e §10.2 (D-15, ADR-0018, adenda à ADR-0003: a ADR-0003 mantém
MySQL próprio, outbox, controle otimista e `409`; mudam os status, os atores e as colunas).
Como a tabela ainda não existe, **os nomes da spec entram já na `sql/010`** — não há dado legado
nem tradução na API (DEC-01).

### 7.1 Estados

| Status interno | Rótulo ao associado (proposta até P-44) | v0.1 (ADR-0003) | Terminal | Quem muda (spec) |
|---|---|---|---|---|
| `criada` | Recebida pela APM | `aberta` | não | o sistema |
| `enviada` | Enviada ao parceiro · tipo 3: "Encaminhada à equipe" | — (`crm_sync=ok`, técnico) | não | o sistema (canal confirmou: `crm` ⇒ espelho ok; `api`/`portal` ⇒ ack) ou a APM (canal `relatorio`/`email`: operador marca no B05) |
| `em_atendimento` | Em atendimento | `em_analise` | não | o parceiro (API, portal ou relatório) ou a APM |
| `pendente_associado` | O parceiro precisa de algo seu | `aguardando_associado` | não | o parceiro ou a APM (mensagem pública obrigatória) |
| `concluida_positiva` | Concluída | `concluida` | sim | o parceiro, a importação ou a APM |
| `concluida_negativa` | Não seguiu | `recusada` | sim | o parceiro, a importação ou a APM |
| `cancelada` | Cancelada | `cancelada` (só associado) | sim | o associado **ou a APM com justificativa** |
| *(marcador)* `sem_retorno_desde` | Aguardando o parceiro, a APM já está cobrando | — | — | o sistema (job), quando `enviada_em + prazo_retorno_dias` vence (A05); **não é status**: coluna `DATETIME NULL`, limpa em qualquer transição |

A falha técnica do espelho (`crm_sync ∈ {pendente, ok, erro, falhou}` — 4 valores, corrigindo a
divergência interna com a ADR-0003) continua **invisível** ao associado (RF-SO-06); `enviada` é
status de **negócio**, promovido só por confirmação do canal.

### 7.2 Diagrama

```
            (associado: POST /solicitacoes | POST /beneficios/{slug}/ativar, tipos 2–4)
                                    │
                                    ▼
   ┌───────────────────────────  criada  ────────────────────────────────┐
   │ cancelar (associado)          │ canal confirmou (job) /              │
   │                               │ operador marcou (backoffice)         │
   │                               ▼                                      │
   │ ┌──────────────────────── enviada ──────────────────────────────┐    │
   │ │ cancelar (associado)        │ parceiro/APM assumiu            │    │
   │ │                             ▼                                 │    │
   │ │                      em_atendimento ──────▶ concluida_positiva│    │
   │ │                        │       ▲   └──────▶ concluida_negativa│    │
   │ │        (pede algo ao   │       │ responder                    │    │
   │ │         associado)     ▼       │ (associado)                  │    │
   │ │               pendente_associado                              │    │
   │ │                        │ cancelar (associado)                 │    │
   │ ▼                        ▼                                      │    │
   └─┴──────────────────▶ cancelada ◀── APM, qualquer não terminal ──┴────┘
                                          (justificativa obrigatória)

   marcador sem_retorno_desde: posto pelo job em enviada/em_atendimento quando o prazo vence;
   limpo em qualquer transição. enviada|em_atendimento → concluida_* também por importação (CSV).
```

### 7.3 Transições

| De | Para | Ator | Origem | Gatilho | Efeitos (mesma transação: `UPDATE` condicional + `INSERT solicitacao_evento`) · depois: `evento_uso`, outbox, espelho |
|---|---|---|---|---|---|
| — | `criada` | associado | `ui` | `POST /solicitacoes` ou ativação de tipo 2–4 | `INSERT solicitacao` (`crm_sync=pendente`, `prazo_retorno_dias` copiado do parceiro/benefício/`parametro`) + evento `criada` com `conteudo_enviado`; `notificacao`; outbox **A04**; `uso solicitacao_criar(tipo_ativacao, beneficio)`; canal `relatorio`/`email` ⇒ item na fila B05 |
| `criada` | `enviada` | sistema | `job` | espelho CRM ok / ack do parceiro (API, F2) | `enviada_em = NOW()`; evento; `uso solicitacao_status_alterado(job)` |
| `criada` | `enviada` | apm | `backoffice` | operador marcou "enviado ao parceiro" (canal manual) | idem, com `usuario_interno` (justificativa opcional) |
| `criada` \| `enviada` | `em_atendimento` | parceiro / apm | `crm` / `backoffice` / `api_parceiro` / `portal_parceiro` | CRM "Em andamento"; parceiro confirmou | evento; limpa `sem_retorno_desde`; uso; espelho se origem ≠ `crm` |
| `em_atendimento` | `pendente_associado` | parceiro / apm | `crm` / `backoffice` / `api` / `portal` | pedido ao associado (mensagem pública **obrigatória**) | evento com mensagem; contador em `GET /sessao`; `notificacao`; outbox |
| `pendente_associado` | `em_atendimento` | associado | `ui` | `POST .../responder` (texto 1–2000) | evento com texto; `crm_sync=pendente`; `uso solicitacao_responder` |
| `enviada` \| `em_atendimento` | `concluida_positiva` \| `concluida_negativa` | parceiro / importacao / apm | `crm` / `importacao` / `backoffice` / `api` | resultado registrado | `concluida_em`; evento; `resultado` com valor e evidência ⇒ `INSERT uso_valor` nível 3 (nível 4 só com validação do Financeiro); `alteracao_cadastro` ⇒ invalida `associado_perfil`; `notificacao`; outbox **A06**; uso |
| `criada` \| `enviada` \| `pendente_associado` | `cancelada` | associado | `ui` | `POST .../cancelar` — **nunca** a partir de `em_atendimento` (spec: "enquanto o parceiro ainda não atendeu"; DIV-24) | evento; `cancel_motivo`; `crm_sync=pendente` (`status_atualizar`); suprime outbox/fila pendentes (A05); `uso solicitacao_cancelar` |
| qualquer não terminal | `cancelada` | apm | `backoffice` | operador, **justificativa obrigatória** (CHECK) | evento com `usuario_interno`; espelho |
| *(marcador)* | `sem_retorno_desde` | sistema | `job` | `enviada_em + prazo_retorno_dias < NOW()` ∧ `status ∈ {enviada, em_atendimento}` ∧ marcador vazio | evento `sem_retorno` (sem troca de status); outbox **A05** (alerta interno B01 + aviso ao associado); `notificacao`. 2.º vencimento (`prazo × 2`): evento `sem_retorno_2` → `fila_ligacao` (spec:§10.2 passo 5) |
| terminal `concluida_*` | *(avaliação)* | associado | `ui` | `POST .../avaliar` `{nota 0–10, comentario}` 1× até `parametro.avaliacao_prazo_dias` (30; DEC-22) | `UPDATE avaliacao_* WHERE avaliada_em IS NULL`; evento `avaliada`; `uso solicitacao_avaliar` |
| terminal | qualquer | — | — | — | `409 estado_invalido`. CRM concluindo algo cancelado localmente: terminal local prevalece, divergência em `evento_log` (aviso), cancelamento reenviado |

**Conteúdo enviado** (`solicitacao_evento.conteudo_enviado`, DEC-02): `{campos: [nomes], sha256,
destino, canal}` — nunca o payload; prova **o que** e **quando** foi enviado sem replicar dado
pessoal em trilha de guarda longa. Os dados que o associado preencheu continuam em
`solicitacao.dados` (CHECK anti-CPF; allowlist por tipo; `beneficio.sigiloso ⇒ {}`).

### 7.4 Tipos

**Solicitações nascidas do catálogo** (RF-BE-13): `beneficio_id` + `parceiro_id` + `tipo_ativacao`
∈ {2, 3, 4} desnormalizados; campos permitidos vêm da ficha do benefício; `canal_envio` do
parceiro (`relatorio`/`email` na F1 — **nenhuma chamada HTTP a parceiro**, D-10/DEC-04; `api`/
`portal` F2) ou `crm` (tipo 3); `prazo_retorno_dias` copiado na criação.

**Serviços da APM sem benefício** (`tipo_servico`, `beneficio_id` nulo; migram para o catálogo
com `tipo_ativacao=3` quando `sql/016` existir, DIV-26):

| `tipo_servico` | Rótulo (proposta) | Origem | Campos obrigatórios | Opcionais | Unicidade / limite |
|---|---|---|---|---|---|
| `alteracao_cadastro` | Alteração de cadastro | RF-PE-03 | `alteracoes` (`{campo: novo_valor}`, campos ∈ regime "com aprovação", ≥ 1) | `justificativa` (≤ 500) | 1 não terminal por campo |
| `diagnostico_marketing` | Diagnóstico de marketing | RF-HO-07 (vira benefício tipo 2 na Fase 4) | — | — | 1 não terminal |
| `submeter_trabalho` | Publicação na revista | RF-HO-11, RF-NE-07 | — | `titulo` (≤ 200) | 1 não terminal |
| `mentoria_pedir` | Quero um mentor | RF-CO-06 (F3) | — | `area_interesse` (≤ 120) | 1 não terminal |
| `mentoria_oferecer` | Quero ser mentor | RF-CO-06 (F3) | — | `area_interesse` (≤ 120) | 1 não terminal |
| `cartao_apm` | Cartão APM | RF-ON-09 (F3, só com contrato) | — | — | 1 não terminal |
| `outro` | Outro assunto | RF-SO-03, RF-AJ-03 | `assunto` (1–120), `mensagem` (1–2000) | — | 5 em 24 h móveis (contagem no banco, D-17) |
| **`declaracao_associado`** | Declaração de associado | RF-FI-04 | `finalidade` ENUM (inclui `amb_prova_titulo`, carência 1 mês) | `observacao` (≤ 200) | 1 não terminal por finalidade |
| **`cancelamento_associacao`** | Cancelamento da associação | RF-AJ-04 | `motivo` ENUM(`nao_uso`, `preco`, `mudanca`, `insatisfacao_servico`, `outro`), `quer_conversa` | `comentario` (≤ 500) | 1 aberto por associado; step-up; flag `cancelamento_online` |
| **`exclusao_dados`** | Exclusão de dados (LGPD) | RF-PE-14 | — | — | 1 aberto; step-up; flag `lgpd_consentimentos` |

Dados de contato não são copiados para a solicitação: o atendente os vê no contact (regarding) ou
na visão 360.

### 7.5 Espelho no CRM e canais

- **Outbox CRM:** `crm_sync ∈ {pendente, ok, erro, falhou}`, `crm_tentativas`, `crm_proxima_em`.
  Job `espelhar` (1 min; `HUB_MODE=stub` até P-06) processa `pendente`/`erro` vencidos: sem
  `crm_id` → `solicitacao.espelhar`; com `crm_id` → `solicitacao.status_atualizar` (cancelamento,
  resposta, justificativa). Confirmação do espelho promove `criada → enviada` quando
  `canal_envio = crm`.
- **Backoff:** exponencial 1, 2, 4, 8, 16, 32, 60, 60, 60, 60 min; após **10 tentativas** →
  `falhou`, `evento_log` severidade `erro`, B01; reprocessamento pelo operador/backoffice
  (`UPDATE crm_sync='pendente'`, documentado em `docs/JOBS.md`).
- **Idempotência:** `uuid` da área como chave de correlação; `solicitacao.espelhar` devolve o
  registro existente se o `uuid` já existir.
- **Sync de volta:** job `sincronizar` (5 min) chama `solicitacao.alteracoes_consultar` com cursor
  (`modifiedon`, `odata.nextLink` tratado no hub) e aplica só transições válidas da tabela 7.3
  com `origem = crm`.
- **Canais manuais (tipo 2 na F1):** `relatorio`/`email` — a APM encaminha ao parceiro fora do
  sistema; dados ao parceiro só com allowlist por benefício e aprovação do DPO (DEC-04); o retorno
  vem pelo CSV mensal (§5.10) que fecha a solicitação por `id_externo`.
- **Mapeamento `task` do CRM (P-06):** "Não iniciado" → `criada`/`enviada` (a área não regride: se
  já está `enviada`, ignora); "Em andamento" → `em_atendimento`; "Aguardando outra pessoa" →
  `pendente_associado`; `statecode=1` (Concluída) → `concluida_positiva`; `statecode=2` (Cancelada)
  pelo atendente → `concluida_negativa` — **P-06 precisa distinguir "não seguiu" de "cancelada pela
  APM"** (a `task` não distingue) e definir o campo de mensagem pública (nunca a descrição interna).

### 7.6 Regras

- Só o dono vê e age: toda consulta filtra por `contact_id` da sessão; `uuid` de outro → `404`.
- Transição concorrente: `UPDATE … SET status=:novo WHERE id=:u AND contact_id=:c AND status IN
  (:origens)`; 0 linhas → `409 estado_invalido`.
- `UPDATE solicitacao` + `INSERT solicitacao_evento` (+ `notificacao` + `comunicacao_evento`)
  sempre na mesma transação; `evento_uso` depois, em transação própria (D-12).
- Criação idempotente: `chave_idempotencia` única por `contact_id`; tipos de clique único devolvem
  a não terminal existente (200). Tetos diários por contagem no banco (D-17).
- Prazo só conta a partir de `enviada_em`; sem backoffice, canal manual fica `criada` e o
  marcador **não** dispara contra a própria APM.
- Nenhum dado proibido (`app/audit.py`) em `dados`, `mensagem`, `comentario`, `justificativa`;
  texto livre limitado e sem HTML; `sigiloso ⇒ dados = {}`.
- Indicadores derivados (spec:§11.3): 5 rastro = terminal ÷ criadas; 6 prazo do parceiro = mediana
  `enviada_em → 1.º retorno` por `parceiro_id` (view com `ROW_NUMBER`); 7 conversão =
  `concluida_positiva` ÷ solicitações do parceiro.

---

## 8. Catálogo de eventos de uso (analytics)

Registro: `{contact_id, acao, entidade, entidade_id, origem, request_id, criado_em (UTC), detalhes}`
em `evento_uso` (spec:§11.2 `{associadoId, acao, entidade, id, timestamp}` + propriedades). `acao`
validada contra catálogo fechado em `app/uso.py`; ação desconhecida é descartada com log. Eventos
de origem `ui` chegam em lote por `POST /api/v1/uso [C]` (`keepalive`, máx. 20 por lote, 60
lotes/min por sessão); o servidor ignora `contact_id` vindo do cliente e usa o da sessão. Teste
obrigatório: `AcaoUi` (front) = `ACOES_UI` (servidor) (TI-04).

**Unificação com a spec (v0.2; `LEVANTAMENTO §6.2`, DIV-14, DEC-34).** Os nomes já em código são
**mantidos** (renomear quebraria 8 emissores e 47 testes do front por ganho cosmético); o nome da
spec entra como coluna e nas views (`vw_ind_*` traduzem). Acréscimos seguem `substantivo_verbo`.
**Propriedades comuns da spec** (categoria, fase de carreira, especialidade, regional, tempo de
casa) **não vão em cada linha**: são dimensões obtidas por junção com `associado_perfil`/
`associado_categoria_hist` na data do evento (minimização, D-12/ADR-0012). `dispositivo` =
classe grossa (`mobile`/`desktop`/`pwa`) derivada **no servidor** do UA (nunca o UA), só em
`pagina_ver`; UTM/código do gatilho = `detalhes.gatilho` validado por catálogo fechado (RF-SH-15).
Só o que não é derivável entra em `detalhes` (tipado, sem texto livre, **sem valor monetário** —
dinheiro vive em `uso_valor`). O que a spec quer e **não** entra em `evento_uso`: `login` (fica em
`evento_log`, ADR-0012 §4), termo de busca (só `busca_sem_resultado` sem identidade), valor
exibido no Meu valor (derivável), propriedades pessoais por linha.

| # | `acao` | Nome na spec (§11.2) | `entidade` | Quando dispara | `detalhes` tipados | Origem | RF |
|---|---|---|---|---|---|---|---|
| 1 | `pagina_ver` | `home_vista`, `carteirinha_aberta`, `meu_valor_visto` | `rota` | troca de rota na SPA | `blocos[]` (enum; só `/area`), `segmento`, `periodo` (meu valor), `disp`, `gatilho` | ui | SH-01, HO-12, FA-06 |
| 2 | `busca_global` | `busca` | `rota` | busca com ≥ 2 caracteres (**sem o termo**) | `resultados`, `tamanho` | ui | SH-04, SH-14 |
| 3 | `filtro_aplicar` | — | `beneficio`/`noticia` | chip de filtro, tema, categoria ou "Limpar filtros" | `filtro`, `limpar` | ui | BE-02, BE-14, NE-02 |
| 4 | `categoria_abrir` | `home_bloco_clicado` (bloco 5) | `beneficio_categoria` | clique em tile ou "Conhecer" | — | ui | HO-08 |
| 5 | `home_bloco_clicar` | `home_bloco_clicado` | `home_bloco` | clique em bloco da home | `bloco`, `posicao`, `item` | ui | HO-12..16 |
| 6 | `beneficio_abrir` | `beneficio_visto` | `beneficio` | **página do benefício aberta** (muda de semântica: antes era o CTA) | `origem` ∈ {home, catalogo, busca, email, trilha}, `estado` (6) | ui | BE-11 |
| 7 | `beneficio_acessar` | — | `beneficio` | CTA externo via redirecionador (tipo 1) | `origem` | servidor | BE-15 |
| 8 | `beneficio_ativar` | `solicitacao_criada` (tipo 1) | `beneficio` | ativação tipo 1 gravada | — | servidor | BE-07, BE-13 |
| 9 | `beneficio_desativar` | — | `beneficio` | desativação (só tipo 1) | — | servidor | BE-08 |
| 10 | `beneficio_gerenciar` | — | `beneficio` | abertura de "Gerenciar" (agora = ficha) | — | ui | BE-08, BE-11 |
| 11 | `recomendacao_dispensar` | `recomendacao_dispensada` | `beneficio` | dispensa gravada | `motivo` ENUM | servidor | BE-17 |
| 12 | `totalpass_abrir` | — | `beneficio` | deep-link TotalPass | — | ui | BE-10 |
| 13 | `plantoes_abrir` | — | `beneficio` | banco de plantões (vira benefício tipo 1/2) | — | ui | ON-08 |
| 14 | `clube_oferta_usar` | `clube_acesso` | `oferta` | encaminhamento rastreado ao clube | `origem` | servidor (antes ui) | CL-03, CL-04, CL-06 |
| 15 | `clube_resgatar` | `clube_resgate` | `uso_valor` | resgate devolvido pelo clube (F2) | `fonte` | job | CL-06 (F2) |
| 16 | `noticia_abrir` | `conteudo_lido` | `noticia` | abertura de matéria | `tema` | ui | NE-03, NE-06 |
| 17 | `noticia_ler_tempo` | `conteudo_lido` (tempo) | `noticia` | `pagehide` (opcional) | `segundos` ≤ 3600 | ui | NE-03 |
| 18 | `noticia_salvar` / `noticia_dessalvar` | — | `noticia` | salvar/dessalvar gravado | — | servidor | NE-04 |
| 19 | `tema_seguir` / `tema_deixar` | `tema_seguido` | `tema` | tema adicionado/removido | — | servidor | NE-05 |
| 20 | `evento_inscrever` | `evento_inscricao` | `evento` | inscrição/interesse gravado | `perfil_preco`, `status` | servidor | EV-05, EV-06 |
| 21 | `congresso_garantir_vaga` | `evento_inscricao` | `evento` | vaga do Congresso gravada | `perfil_preco` | servidor | HO-04, EV-02 |
| 22 | `congresso_programacao_abrir` | — | `evento` | link de programação | — | ui | EV-01 |
| 23 | `evento_presenca_registrar` | `evento_presenca` | `evento` | presença/certificado (F2, plataforma) | `tipo` ∈ {presenca, certificado} | job | EV (F2) |
| 24 | `comunidade_entrar` / `comunidade_abrir` / `programa_saber_mais` / `rede_entrar` | — | `comunidade` | como na v0.1 (F3) | — | servidor/ui | CO-01..05 |
| 25 | `solicitacao_criar` | `solicitacao_criada` | `solicitacao` | solicitação criada | `tipo_servico` ou `tipo_ativacao` + `beneficio` | servidor | SO-03, BE-13, AJ-03, PE-03, PE-14, FI-04 |
| 26 | `solicitacao_cancelar` | — | `solicitacao` | cancelamento pelo associado | `motivo?` | servidor | SO-04, SO-12 |
| 27 | `solicitacao_responder` | — | `solicitacao` | resposta do associado | — | servidor | SO-05 |
| 28 | `solicitacao_status_alterado` | `solicitacao_status` | `solicitacao` | transição aplicada por job, CRM, importação ou backoffice | `de`, `para`, `origem` ∈ {sistema, parceiro, importacao, usuario} | servidor, job | §7, BO-02 |
| 29 | `solicitacao_avaliar` | — (A06) | `solicitacao` | avaliação 0–10 gravada | `nota` | servidor | SO-10 |
| 30 | `cancelamento_pedir` | `cancelamento_pedido` | `associado` | pedido de cancelamento da associação | `motivo` ENUM | servidor | AJ-04 |
| 31 | `uso_registrar` | `uso_registrado` | `uso_valor` | linha em `uso_valor` (concluída com valor, importação confirmada, clube) | `fonte`, `nivel` (**sem valores**) | servidor, job | FA-09, BO-03 |
| 32 | `carencia_vencer` | `carencia_vencida` | `beneficio` | job diário: benefício liberado pela carência | `liberado_em` | job | ON-13, HO-13 |
| 33 | `onboarding_passo_concluir` | `trilha_passo` | `onboarding_passo` | passo concluído **por evento real** | `dia_jornada` | servidor | ON-12 |
| 34 | `perfil_contato_atualizar` / `perfil_foto_atualizar` | `perfil_atualizado` | `associado_perfil` | edição confirmada pelo hub | `campos[]` (nomes) | servidor | PE-02, PE-05 |
| 35 | `perfil_declarado_atualizar` | `perfil_atualizado` | `perfil_declarado` | preferência/pergunta gravada | `campos[]` (nomes) | servidor | PE-10, PE-11 |
| 36 | `consentimento_alterar` | `consentimento` | `consentimento` | consentimento dado ou retirado | `finalidade`, `canal`, `valor`, `versao` | servidor | PE-12 |
| 37 | `carteirinha_compartilhar` | — | `carteirinha` | link de verificação gerado | — | servidor | CA-04 |
| 38 | `carteirinha_baixar` | — | `carteirinha` | imagem/PDF gerado | `formato` ∈ {png, pdf} | servidor | CA-07 |
| 39 | `carteirinha_verificar` | `carteirinha_validada` | `carteirinha` | página pública aberta com token válido | `resultado` ∈ {ativo, inativo, nao_confirmado} | publico | CA-03, CA-08 |
| 40 | `wallet_adicionar` | — | `carteirinha` | "+ Adicionar à Wallet" (flag) | — | ui | CA-05 |
| 41 | `valor_pdf_baixar` | — | `fatura` | PDF do extrato de valor (substitui `fatura_pdf_baixar`, **retirada**) | `periodo` | servidor | FA-08 |
| 42 | `fatura_segunda_via` | `financeiro_segunda_via` | `fatura` | segunda via gerada (⛔ fonte) | `competencia`, `forma` ∈ {pdf, linha_digitavel, pix} | servidor | FI-03 |
| 43 | `pagamento_confirmar` | `pagamento_confirmado` | `fatura` | job de sync da cobrança (**sem valor**) | `competencia`, `forma` | job | FI-05 |
| 44 | `notificacao_criar` / `notificacao_abrir` | `notificacao` | `notificacao` | criada pelo domínio / aberta na UI (F2) | `tipo` | job / ui | NO-01, NO-04 |
| 45 | `central_whatsapp_abrir` → `ajuda_contatar` | `ajuda_contato` | `central` | contato com a Central (emissor atual migra) | `canal` ∈ {whatsapp, telefone, formulario}, `assunto` ENUM | ui | SH-08, AJ-02 |
| 46 | `acesso_primeiro` | `acesso_primeiro` | `associado` | primeiro login na área (upsert insere) | `dias_desde_filiacao` | servidor | AU-12 |
| 47 | `erro_exibido` | — (indicador 14) | `rota` | toast de erro exibido | `codigo`, `request_id` | ui | SH-09, PE-08 |
| 48 | `vitais_web` | — (indicador 14: LCP) | `rota` | RUM próprio (`web-vitals` self-hosted) | `lcp`, `inp`, `cls` numéricos, `disp` | ui | RNF-12 |
| 49 | `erro_js` | — (indicador 14: erros de JS) | `rota` | `window.onerror`/`unhandledrejection` | `tipo`, `arquivo` (sem stack com PII) | ui | RNF-17 |

Fora de `evento_uso`, por desenho: `login` (`evento_log` `login_ok`/`login_falha`; indicadores 1 e
14 leem de lá), supressões e envios de comunicação (`comunicacao_*`), leituras de dado pessoal
pelo staff (`acesso_dado_pessoal`), ações do backoffice (`backoffice_auditoria`). Mecânica que
**não muda** (D-12): catálogo fechado, identidade da sessão, lote ≤ 20, transação própria, nunca
lança, CHECK anti-CPF. Cada fase acrescenta só as ações das suas telas (regra 20).

---

## 9. Perfil — campos editáveis, preferências e direitos do titular

### 9.0 Campos do cadastro (CRM) — regime de edição

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
5 uploads/h; vhost `client_max_body_size 6m` no location da foto. Remoção implementada
(`DELETE /perfil/foto`, Fase 2a; LA-15 fechada).

### 9.1 Perfil declarado e preferências (v0.2; spec:§6 P13)

Campos que **não** vêm do CRM e vivem só na área (`perfil_declarado`, `preferencia_canal`,
`sql/019`; `UPDATE` pelo web — é perfil editável, não trilha):

| Campo | Rótulo (proposta) | Tipo | Validação | Uso |
|---|---|---|---|---|
| `tratamento` | Como prefere ser chamado | ENUM(`neutro`, `dra`, `dr`, `nome`) + apelido ≤ 40 sem HTML | enum fechado | saudação (RF-HO-01; DEC-26: até existir, "Olá, Nome") |
| `area_atuacao` | Onde você atua | SET(`consultorio_proprio`, `hospital`, `plantao`, `pesquisa`, `gestao`, `docencia`) | enum fechado | afinidade (+1), recomendação |
| `regiao_interesse` | Região | código de regional (lista fechada; CRM quando P-56) | lista | agenda, parceiros regionais |
| temas | Temas de interesse | reusa `associado_tema` (≤ 20) | seed | notícias, agenda, afinidade |
| `canal_preferido` | Canal preferido | ENUM(`email`, `whatsapp`, `sms`) — WhatsApp/SMS **só exibidos quando existirem** (P-64; regra 19) | enum | RD (`cf_apm_canal_preferido`), fila de ligações |
| `frequencia` | Frequência | ENUM(`normal`, `minima`) | enum | supressão local |

Perfil progressivo: uma pergunta por visita (RF-PE-11; catálogo `pergunta_perfil` com ordem e
condição por categoria). Evento `perfil_declarado_atualizar` com nomes de campos, nunca valores.

### 9.2 Consentimentos versionados (spec:§11.6, §14)

- **Base legal por finalidade:** consentimento para ofertas de parceiros e para WhatsApp de
  relacionamento; transacionais seguem a execução do contrato de associação (não dependem de
  consentimento); demais finalidades e textos por P-54.
- **Modelo:** `consentimento_texto` (finalidade, canal, versão, texto, `vigente_desde`; texto novo
  = linha nova) e `consentimento` **append-only** (`contact_id`, `consentimento_texto_id`,
  `valor`, `origem` ∈ {perfil, onboarding, backoffice, importacao}, `request_id`, `ocorrido_em`);
  estado atual = última linha por finalidade × canal (`vw_consentimento_atual`).
- **API:** `GET /perfil/consentimentos` (vigentes + histórico), `POST /perfil/consentimentos [C]`
  com `versao_texto` obrigatória (`409 versao_desatualizada`); descadastro em um toque reflete no RD
  na hora (RF-CM-03) e nunca mais enfileira para o canal.
- **Trilha:** `consentimento_alterar` em `evento_uso`; nenhum `UPDATE`/`DELETE` (ADR-0004 §4,
  mesma classe de `evento_log`).

### 9.3 Direitos do titular (spec:§11.6; DIV-05, DEC-06)

- **Baixar meus dados** (RF-PE-13): síncrono, JSON com o que a área guarda do `contact_id`,
  step-up, 1/7 dias, nunca anexado a e-mail; registro em `titular_pedido` (fechado na hora) e
  `evento_log`.
- **Pedir exclusão** (RF-PE-14): solicitação `exclusao_dados` + `titular_pedido` com protocolo e
  confirmação por e-mail; fila do encarregado (B13). "Exclusão" = **anonimização administrativa**
  (`associado_perfil` e `perfil_declarado` zerados, `anonimizado_em`; `contact_id` mantido nas
  trilhas como pseudônimo; `evento_log` preservado por obrigação legal) por script fora do usuário
  `apm_area`; expurgo físico só por retenção pelo operador (`docs/RETENCAO.md`, TI-28; prazos
  P-54). A filiação é cancelada pela APM (RF-AJ-04), não por esta rota.
- **Registro de acesso a dado pessoal** pelo staff: `acesso_dado_pessoal` (RF-BO-01/06).
- **Agregados a terceiros** (parceiros, patrocinadores, regionais): k ≥ 20 por recorte, função
  única `agregar(min_n=20)` (RF-BO-08).
---

## 10. Feature flags

Fonte: `feature_flag` + `FLAGS_FORCAR_DESLIGADAS` (CSV em `Settings`, vence a tabela); enum fechado
em `app/flags.py` (`FLAGS_CONHECIDAS`); cache 60 s; entregues em `GET /sessao`. Flag ausente ou
desconhecida = desligada; desligada = API `404 recurso_desligado` + UI oculta (D-08, regra 19).
A spec só exige chave para patrocínio, cartão, comunidade e **novos tipos de ativação**
(spec:§14); **não** há flag para catálogo, solicitações, trilha, FAQ ou preferências — são núcleo
da F1. Chaves novas (D-18, ADR-0021; adenda à ADR-0007) nascem desligadas na `sql/009`.

### 10.1 As 8 chaves existentes (`sql/003`)

| Chave | Padrão | O que oculta na UI | Resposta da API | Libera com |
|---|---|---|---|---|
| `mensalidade_zero` | desligada (**forçada**) | card/pill/bloco "Mensalidade Zero", trecho "patrocinada" da trilha, "O QUE A SUA MENSALIDADE COBRE" | bloco `mensalidade` ausente | contrato de patrocínio (P-12; P17 F3) |
| `fatura_valor` | desligada (**forçada até `valor.py` + `valor_referencia` aprovada**) | rota `/area/meu-valor`, item "Meu valor" do menu e da barra (5.ª aba), bloco 2 da home, "valor no ano" do resumo de benefícios | `GET /valor`, `GET /valor/pdf` → `404 recurso_desligado` | TI-36 + P-48 (DEC-23: **chave mantida, rótulo "Meu valor"**) |
| `patrocinio` | desligada (**forçada**) | selo `patrocinado`, critério +1 da recomendação, borda âmbar | campo `patrocinado` omitido | P-12 |
| `clube_economia` | desligada | economia/cashback no clube e no Meu valor (`fonte=clube`) | campos de economia omitidos em `GET /clube` | integração com o fornecedor (P-51; F2) |
| `comunidade_posts` | desligada | "CONVERSAS EM DESTAQUE" | sem endpoint | COM-01 (F3) |
| `wallet` | desligada | "+ Adicionar à Wallet" | endpoint da Fase 8 → `404` | P-13 (F2) |
| `erp_financeiro` | desligada | rota `/area/financeiro`, item "Financeiro", "total pago"/"N vezes" no Meu valor, bloco Pendência financeira | `GET /financeiro*` → `404` | P-04, P-08 (ADR-0010) |
| `totalpass` | desligada | card TotalPass e passo da trilha | campo `totalpass` omitido | P-02 ✅, P-04 |

### 10.2 As 7 chaves novas (`sql/009`; D-18)

| Chave | Governa | O que oculta na UI | Resposta da API | Pré-requisito | Fase |
|---|---|---|---|---|---|
| `notificacoes` | P15 (RF-NO-01..03) | sino, rota `/area/notificacoes`, contador | `GET /notificacoes*` → `404`; `notificacoes_nao_lidas` ausente de `/sessao` | aceite visual do sino (P-42; DEC-08) | F2 |
| `encaminhamento_parceiro` | tipo 2 (RF-BE-13) | botão "Solicitar" em benefício `tipo_ativacao=2` | `POST .../ativar` → `404` | DEC-04 aceita (solicitação local); por parceiro, ADR própria (P-50) | 4 |
| `reservas` | tipo 4 | botão "Reservar" e disponibilidade | `GET .../disponibilidade`, `POST .../reservar` → `404` | fonte de disponibilidade (Hotel Fazenda, Residencial) | F2 |
| `inscricoes` | tipo 5 **real** (F1 segue "interesse" sem flag) | preço por perfil e "Inscrito" | `POST /eventos/{id}/inscrever` continua respondendo `interesse` | plataforma de eventos/IESAPM (P-51) | F2 |
| `comunicacao_outbox` | job `outbox_rd` (RF-CM-04) — a **produção** da outbox é sempre ligada | — | — (job não envia; marca `suprimido: sem_credencial`) | credencial do RD (P-46), consentimento (P-54) | 3b |
| `cancelamento_online` | `POST /ajuda/cancelamento` (RF-AJ-04) | formulário de cancelamento (fica o caminho pela Central) | `404` | processo da Central; pode nascer **ligada** por decisão de negócio | 3 |
| `lgpd_consentimentos` | RF-PE-10..14 (preferências, consentimentos, exportar, excluir) | seções novas do perfil, pergunta por visita, canais | `GET\|POST /perfil/consentimentos`, `/preferencias`, `/pergunta`, `/dados/exportar`, `/exclusao` → `404` | textos do jurídico (P-54) para ligar em produção | 3b |

Configurações (não são flags de produto, ficam em `Settings`): `WHATSAPP_CENTRAL`, `SHOW_WHATSAPP`,
`ANIMATIONS`, `JOBS_APLICAR` (dry-run dos jobs, D-16), `HUB_ESCRITA_HABILITADA`, modos `*_MODE`
(`real|stub`, stub proibido em produção: `AUTH`, `HUB`, `SMTP`, `WP`, `RD`), `VERIFICACAO_CACHE_TTL`,
`REAUTH_MAX_IDADE`.

---

## 11. Lacunas e ambiguidades

Cada lacuna tem uma **proposta padrão** já refletida nos RFs; a implementação segue a proposta até
decisão do dono. Na v0.2 cada linha recebeu um marcador **v0.2** (11.1) e as decisões e
divergências do levantamento entram em 11.2 por ID.

| ID | Lacuna | Impacto | Proposta padrão adotada | Dono | Pendência |
|---|---|---|---|---|---|
| LA-01 | Três vocabulários de categoria: grupos de benefícios (4: TECNOLOGIA E IA; CONSULTÓRIO E FINANÇAS; SAÚDE, BEM-ESTAR E PROTEÇÃO; EDUCAÇÃO E CARREIRA), tiles da home (8: Tecnologia e IA, Consultório e prática, Saúde mental e bem-estar, Finanças e proteção, Educação e carreira, Defesa e jurídico, Comunidade, Vida e lazer) e barras da fatura (Consultório, Tecnologia e IA, Saúde e bem-estar) | filtro por tile, contagens e agregação da fatura inconsistentes | categoria (8) é atributo do benefício; grupo (4) é agrupamento de categorias: Tecnologia e IA → TECNOLOGIA E IA; Consultório e prática e Finanças e proteção → CONSULTÓRIO E FINANÇAS; Saúde mental e bem-estar e Defesa e jurídico → SAÚDE, BEM-ESTAR E PROTEÇÃO; Educação e carreira → EDUCAÇÃO E CARREIRA; barras da fatura usam o grupo | negócio | P-10 · **v0.2:** **respondida** — 8 categorias de P03 (spec:§6 P03) e valor por categoria no Meu valor (P06); os 4 grupos deixam de existir (RF-BE-14); nomes finais na lista curada (P-48). |
| LA-02 | Toasts sem texto: submeter trabalho, Wallet, mentoria (pedir e oferecer), embaixadores, rede de encaminhamento, garantir vaga no Congresso, desativar benefício, pedir Cartão APM | feedback inconsistente; risco de prometer o que não acontece | propostas: "Recebemos seu interesse em publicar. A equipe da revista entra em contato." · "Carteirinha adicionada à Wallet." · "Pedido de mentoria recebido. Acompanhe em Minhas solicitações." · "Obrigado! Recebemos seu interesse em ser mentor." · "Abrindo Embaixadores acadêmicos…" · rede: sem toast (rótulo "Você está na rede ✓" basta) · Congresso: sem toast até LA-07 · "{título} desativado" · "Pedido do Cartão APM recebido. Acompanhe em Minhas solicitações." | comunicação | P-10 · **v0.2:** **parcial** — voz §3.3 fixa o tom (verbo no botão, sem exclamação, sem jargão); textos finais em P-44. |
| LA-03 | Destino de "Gerenciar" | sem forma de desativar ou acessar benefício ativo | diálogo com "Acessar" e "Desativar" (RF-BE-08) | negócio | P-10 · **v0.2:** **respondida** — "Gerenciar" abre a página do benefício P04 (spec:§8.1 estado Ativo; RF-BE-11); "Desativar" só tipo 1. |
| LA-04 | Regra de validade da carteirinha ("válida até 12/2026"); não há claim nem campo conhecido | carteirinha e verificação pública podem afirmar validade falsa | omitir "válida até" no cartão; verificação mostra status + "verificado em" | negócio / CRM | P-10, P-09 · **Decidido (2026-10-17): omitir a validade até regra do negócio; mostrar situação e "verificado em".** · **v0.2:** **respondida** — não há "válida até": a validação consulta a situação na leitura e o cancelamento revoga (spec:§6 P07; RF-CA-08). |
| LA-05 | E-mail editável direto × com verificação de posse | e-mail é canal de segurança do IdP; troca sem verificação permite sequestro de notificações | direto (plano), com auditoria e limite; reavaliar verificação por código antes da Fase 2 com Sentinela | negócio / Sentinela | P-10 · **Decidido (2026-10-17): direto com código no novo e-mail + reautenticação recente (ADR-0015).** |
| LA-06 | "Inscrever" em evento: interesse local × inscrição real no site/sistema de eventos | associado pode acreditar estar inscrito sem estar | registra interesse local e abre `link_externo` do evento quando existir; toast da spec mantido | negócio | P-10, P-07 · **v0.2:** **respondida** — tipo 5: interesse local na F1, inscrição real na F2 com a plataforma (spec:§6 P04; RF-EV-06). |
| LA-07 | "Garantir minha vaga" no Congresso: onde a inscrição acontece de fato; Congresso 2026 (26–28/09) já ocorreu | promessa de vaga sem inscrição; banner desatualizado | registra interesse; banner/hero só com Congresso futuro no cache; CTA abre a página de inscrição do site quando houver link | negócio | P-10 · **v0.2:** **respondida** — congresso em destaque só com inscrição aberta; congressos grandes mantêm seus sites, inscrição parte da área **sem CPF no link** (spec:§6 P10; DIV-28). |
| LA-08 | Entidade do CRM para solicitações (`task` × custom), mapeamento de status e campo de mensagem pública; flows em create | bloqueia espelho (Fase 3) | `task` regarding contact, mapeamento da seção 7.5 | CRM / negócio | P-06 · **v0.2:** **mantida e ampliada** — P-06 precisa distinguir "não seguiu" de "cancelada pela APM" e definir a mensagem pública (§7.5; EXT-20). |
| LA-09 | Número da Central e links por comunidade; `wa.me` abre chat 1:1, não grupo | "Entrar" não leva ao grupo; atendimento manual | `wa.me` para número de atendimento por comunidade com a mensagem da spec; se a comunicação fornecer convites de grupo (`chat.whatsapp.com`), trocar o destino no seed | comunicação | P-11 · **v0.2:** **adiada (F3)** — grupos moderados COM-01 (spec:§6 P16); rota fora do menu até lá (DEC-24). |
| LA-10 | Mensalidade Zero inconsistente: "100% coberta" × barra 40%/60% ("R$ 28 você · 40%", "R$ 42 patrocínio · 60%") | dado financeiro contraditório ao associado | flag `mensalidade_zero` desligada; textos que citam patrocínio têm variante sem patrocínio (RF-HO-09, RF-ON-02) | negócio | P-12 · **v0.2:** **respondida** — faixa da Mensalidade Zero só com patrocínio contratado (spec:§5.3, P17); flag forçada até P-12. |
| LA-11 | Período da fatura ("janeiro a junho de 2026") × "você pagou R$ 336 no ano" | múltiplo "7×" compara períodos diferentes | quando ligada, período = ano civil corrente até hoje em ambos | negócio | P-12 · **v0.2:** **respondida** — período = ano corrente e anteriores; relação = (comprovado + proteção) ÷ pago no período; "N vezes" só com pago > 0 (spec:§6 P06, §8.6; RF-FA-06). |
| LA-12 | "R$ 1.500+ em benefícios/ano" × "Valor para você ≈ R$ 2.490/ano" × soma dos passos | números divergentes na mesma tela | valores calculados dos seeds (passos e coberturas) | negócio / comunicação | P-12, P-10 · **v0.2:** **respondida** — valores por benefício viram `valor_referencia` aprovada pelo Financeiro (spec:§5.3, §8.6); nenhum número sem aprovação. |
| LA-13 | Posts de comunidade ("CONVERSAS EM DESTAQUE") sem fonte | seção sem dado real; moderação e LGPD | flag `comunidade_posts` desligada | comunicação | P-11 · **v0.2:** **adiada (F3)** — COM-01 (spec:§6 P16). |
| LA-14 | Contagens apresentadas como reais: "40+ benefícios", "320 médicos", "210 mentores", "1.240/380/920 membros", "64 faculdades", "340 vagas hoje", "30 mil parceiros", "61% dos associados", "● ativa agora", "sua especialidade" | números falsos ao associado | só exibe contagem com fonte (ativações reais, adesões reais) ou texto editorial aprovado no seed; sem fonte → omitir o número | negócio / comunicação | P-10, P-11 · **v0.2:** **confirmada** — "nenhuma promessa … antes de contrato, prova técnica e regra de negócio" (spec:§2.2); "número sempre com contexto" (§3.3). |
| LA-15 | Remover foto de perfil | associado não consegue apagar a foto (LGPD: direito de eliminação via Central) | não implementado; remoção pela Central; avaliar ferramenta `associado.foto_remover` no hub | negócio / Sentinela | P-10 · **v0.2:** **fechada** — `DELETE /perfil/foto` implementado na Fase 2a (RF-PE-07). |
| LA-16 | Personas "residente" (sem tipo no CRM) e "sem patrocínio" (spec só cobre patrocinado) | textos e rota inicial errados para parte da base | persona = tipo do CRM; sem flag de patrocínio, nenhum texto de patrocínio | negócio / CRM | P-10, P-12 · **v0.2:** **respondida** — categorias acadêmico, aspirante, efetivo, remido; residente = aspirante; sem patrocínio é o padrão (spec:§4.1); de-para TI-92. |
| LA-17 | "Todo resgate acontece dentro da Minha APM", mas o resgate do clube ocorre em `clubapm.com.br` sem retorno | fatura de valor e economia do clube sem dado; afirmação falsa | registra só o clique; textos que afirmam o contrário ficam sob `clube_economia` | negócio | P-12 · **v0.2:** **respondida** — F1 encaminhamento rastreado sem promessa de SSO ou economia; retorno só na F2 (spec:§6 P09; RF-CL-06). |
| LA-18 | Mensagem pré-preenchida da Central APM não definida | atendimento sem contexto | "Olá! Sou associado(a) da APM e preciso de ajuda." (proposta) — sem dado pessoal na URL | comunicação | P-11 · **v0.2:** **parcial** — voz §3.3 (sem exclamação; TI-61); texto final P-44. |
| LA-19 | Tratamento "Dr./Dra." e concordância ("associada/associado") | saudação e carteirinha com gênero errado | sem prefixo na saudação; concordância por `alf_sexo`; desconhecido → construções neutras ("na APM desde") | comunicação | P-10 · **Fase 2a: carteirinha usa "na APM desde {ano}"; saudação sem prefixo.** · **v0.2:** **respondida** — "como prefere ser chamado" no perfil (spec:§3.3, §6 P13; RF-PE-10; DEC-26); até existir, "Olá, Nome". |
| LA-20 | Acadêmico sem CRM: linha "CRM-SP 000000" | carteirinha com campo vazio | linha mostra só "na APM desde {ano}" | negócio | P-10 · **v0.2:** **confirmada** — acadêmico não tem CRM (spec:§4.1). |
| LA-21 | Item "Onboarding acadêmico" exibido a todos no protótipo; critério de "onboarding concluído" | não acadêmicos veem trilha que não se aplica; rota inicial indefinida | item visível só a Acadêmico; concluído = passo `finalizar` ("Ir para a Minha APM →") | negócio | P-10 · **v0.2:** **respondida** — trilha para todo novo associado e acadêmico, por evento real, some ao terminar ou no dia 90 (spec:§6 P12; RF-ON-12; DEC-21). |
| LA-22 | Busca "Buscar especialista por área..." da rede de encaminhamento sem fonte | campo que não funciona | campo oculto | negócio | P-10 · **v0.2:** **adiada (F3)** — diretório DIR-01 antes; ENC-01 só com parecer jurídico (P-55). |
| LA-23 | Tipos de notícia (ciência/publicação/notícia/evento/nota), fontes além do site (Portal MBE, revista APM, IESAPM) e "atualizado hoje" | tags e filtros "Notícias/Ciência" sem regra | tipo derivado de categoria do WordPress por tabela de mapeamento no seed; só o site nesta versão; "atualizado em DD/MM" quando não for hoje | comunicação | P-07, P-10, P-21 · **v0.2:** **parcial** — filtros tudo / notícias / ciência / defesa profissional / eventos (spec:§6 P11); mapa do WordPress continua P-21; MBE e biblioteca sem fonte (P-51). |
| LA-24 | Banco de plantões: destino e "340 vagas hoje" | card sem destino | card oculto até URL definida; contagem omitida | negócio | P-10 · **v0.2:** **respondida** — banco de plantões vira página de benefício com parceiro (P04, tipo 1 ou 2), F2, parceiro a contratar (spec:§5.3). |
| LA-25 | Textos das telas novas (Perfil, Minhas solicitações), do botão "Sair", mensagens de erro e estados vazios novos | tom e terminologia fora da spec | propostas marcadas nos RFs | comunicação | P-10 · **v0.2:** **parcial** — voz §3.3; estados vazios e de erro editáveis em `texto_sistema` (B07); textos finais P-44. |
| LA-26 | "RECOMENDADOS PARA A SUA SITUAÇÃO": regra de recomendação | recomendação arbitrária | seleção editorial por tipo de associado no seed | negócio | P-10 · **v0.2:** **respondida** — pontuação por regras do §7.3 (RF-BE-17). |
| LA-27 | Elegibilidade TotalPass "status 2 ou 3" × gate do IdP (só status 2 entra) | regra morta para status 3 | elegível = sessão válida; registrar no ADR-0008 | negócio | P-10 · **v0.2:** **mantida** — regra morta para status 3; nada muda. |
| LA-28 | Tag `patrocinado` em benefícios (patrocínio de parceiro) × flag `patrocinio` | perda de fidelidade visual ou exposição de patrocínio indefinido | tag, borda e chip sob `patrocinio` | negócio | P-12 · **v0.2:** **parcial** — regra de exibição definida (sempre sinalizado; ≤ 1 nos 4 primeiros; spec:§3.2, §7.3); fonte continua P-12. |
| LA-29 | Userinfo sem `tipo_associado`/`associado` (CRM incompleto) | persona indefinida | recusar login (fail-closed) ou sessão sem persona → decisão Sentinela antes da Fase 1 (RF-AU-09) | Sentinela | P-20 · **Decidido (2026-10-17): recusa o login (ADR-0016).** |
| LA-30 | Deixar de seguir tema: spec só adiciona | lista de temas só cresce | API suporta (`PUT /temas`); UI de remoção a definir (ex.: chip com ×) | comunicação | P-10 · **v0.2:** **respondida** — `tema_seguido` com ação seguido/deixado (spec:§11.2); API `seguir\|deixar`. |


### 11.1 Leitura da tabela acima na v0.2

A coluna "Pendência" de cada LA ganhou um marcador **v0.2**: *respondida* (a spec v2 fixa a regra;
a referência está no marcador), *parcial* (a spec fixa a direção, o conteúdo final continua com
terceiro), *adiada* (a spec coloca o item em F2/F3) ou *mantida*. LA-04, LA-05, LA-15 e LA-29
estavam fechadas antes (ADR-0015/0016, Fase 2a). Textos finais de todos os rótulos e estados
continuam em P-44 (EXT-05) e os mockups que não existem em P-42 (EXT-02).

### 11.2 Lacunas novas: decisões (DEC) e divergências (DIV) do levantamento

Só título e ponteiro; o texto completo, opções e recomendação estão em `LEVANTAMENTO §10–§11`.
Decididas em 30/10/2026 viram D-15..D-19 (seção 0).

| ID | Título | Estado (30/10) | Onde |
|---|---|---|---|
| DEC-01 | 8 status da spec já na `sql/010`; `enviada` por confirmação; `sem_retorno` como coluna | **decidida** → D-15 / ADR-0018 | §7 |
| DEC-02 | "Conteúdo enviado" no log = campos + sha256 + destino | **decidida** → D-15 / ADR-0018 | §7.3 |
| DEC-03 | Onde vive o backoffice, identidade, 2FA; quem tem UPDATE no catálogo | **parcial**: banco decidido → D-19 / ADR-0022; hospedagem e identidade na Onda 6 (P-65, P-62) | §3.18, §6.3 |
| DEC-04 | Tipo 2 na F1 sem integração: solicitação local com canal manual; dados ao parceiro só com DPO | **decidida** → D-15 / ADR-0018 | RF-BE-13 |
| DEC-05 | Canal do CSV do plano B (upload no backoffice; nunca SFTP/e-mail; CPF no hub) | recomendação; decide usuário + Benefícios | §5.10 |
| DEC-06 | Exclusão de dados = anonimização + purga por retenção | recomendação; decide usuário + encarregado | RF-PE-14, §9.3 |
| DEC-07 | PWA manifest-only; SW só com push | recomendação; Sentinela/Vitrine/Estivador | RNF-23 |
| DEC-08 | Notificações in-app + e-mail; push só com consentimento/SW/ADR; sino só com aceite visual | recomendação; usuário + agência | §3.16 |
| DEC-09 | Revogação da carteirinha: hub a cada leitura com cache curto + job + `revogada_em` | recomendação; Sentinela/Maestro | RF-CA-08 |
| DEC-10 | "API de consulta de associação": hub com resposta mínima; `access:validate` para RPs internos | recomendação; usuário | §5 (fora da área) |
| DEC-11 / DEC-12 | Página de retorno do ex-associado (estática no IdP) · "continuar conectado" (cookie persistente no IdP) | recomendação; usuário | IdP (TI-83) |
| DEC-13 | Limites por associado: contagem no banco para tetos diários; sem Redis | **decidida** → D-17 / ADR-0020 | §3.0 |
| DEC-14 | Situação financeira sem ERP: `financeiro=None ⇒ permite`; separar cadastral × financeira | recomendação; usuário | RF-BE-12, §3.14 |
| DEC-15 | Base da carência = `data_filiacao` + `parametro.carencia_reinicia_por_categoria=false` | recomendação; Benefícios (P-49) | RF-BE-12 |
| DEC-16 | Destino dos eventos e painéis: views + ferramenta interna; `apm_area_painel`; k ≥ 20 | recomendação; usuário + Marketing (P-47) | RF-BO-08 |
| DEC-17 | "Novo sistema de cadastro e cobrança": premissa D365 + hub | recomendação; diretoria/Financeiro/TI (P-58) | §5.12 |
| DEC-18 / DEC-19 / DEC-20 | Divisão com o RD (área emite, RD orquestra) · lead sem CPF no RD · fonte de A01/A02 por `diff_cadastro` | recomendação; Marketing + TI / Integrador | §5.9, §3.17 |
| DEC-21 | Trilha: 90 dias de `data_filiacao`, todas as categorias, bloco da home | recomendação; usuário | RF-ON-12 |
| DEC-22 | Avaliação 0–10 em colunas, prazo 30 d | **decidida** → D-15 / ADR-0018 | RF-SO-10 |
| DEC-23 | `fatura_valor`: manter chave, rótulo "Meu valor"; sair das forçadas com `valor.py` | recomendação aceita como parte de D-18 / ADR-0021 | §10 |
| DEC-24 / DEC-25 | Navegação com fontes ausentes (4 abas, rotas sem página somem, Comunidade/Trilha fora do menu) · botão principal do mockup | recomendação; usuário + Vitrine | RF-SH-16 |
| DEC-26 / DEC-27 | Tratamento Dr./Dra. por campo no perfil · persistência do tamanho de fonte no servidor | recomendação; negócio / Vitrine | §9.1, RNF-10 |
| DEC-28 | React Router 7 antes das telas da Fase 3 (P-40) | **decidida** (tarefa da Onda 2, sem ADR) | — |
| DEC-29 | Agendador dos jobs: loop in-process + `GET_LOCK` + `job_execucao` + `JOBS_APLICAR` | **decidida** → D-16 / ADR-0019 | RNF-19 |
| DEC-30 / DEC-31 / DEC-33 | Homologação com RDS separado antes da escrita no CRM · deploy pull-based · SLO 99,5 % e retenção 14 d | recomendação; operador | RNF-25, RNF-26 |
| DEC-32 | OpenAPI como artefato versionado; `/docs` só na rede interna; nunca em produção | recomendação; Sentinela/Maestro | RNF-24 |
| DEC-34 | Termo de busca só sem resultado, sem identidade | recomendação; Sentinela/Atlas | RF-SH-14 |
| DEC-35 / DEC-36 | Rótulos dos 6 estados e 7 status como proposta até Marketing · verificação pública sem categoria | recomendação; Marketing / Sentinela | §3.3, RF-CA-08 |
| DIV-01..03 | P01 vive no IdP; anti-enumeração por nascimento; backlog do IdP | registradas; TI-83 | §1.3 |
| DIV-04 | CSV com CPF × ADR-0014 → resolução no hub | registrada | §5.10 |
| DIV-05 | "Pedir exclusão" × DELETE nunca → anonimização | registrada | §9.3 |
| DIV-06 | "API de consulta de associação já existe" — não há API JSON | registrada; corrigir com a agência | — |
| DIV-07 / DIV-13 / DIV-45 | Verificação pública sem categoria · situação ao vivo · número no cartão | registradas | RF-CA-07/08 |
| DIV-08 / DIV-26 / DIV-28 | Tipo 2 "envia dados"/SSO × ADR-0009 · toggle × tipos 1–6 · CPF no deep link × ADR-0014 | registradas | RF-BE-13, RF-EV-06 |
| DIV-09 | OpenAPI só em development | registrada | RNF-24 |
| DIV-10 | Sino × ADR-0017 | registrada | §3.16 |
| DIV-11 / DIV-17 / DIV-18 / DIV-19 / DIV-20 | Busca por CPF no B02 · backoffice fora de escopo · catálogo seed × dado · `db_check` frouxo · numeração das migrações | registradas; resolvidas no texto da v0.2 (§3.18, §6) | §6 |
| DIV-12 / DIV-30 / DIV-33 | Transacional pelo próprio sistema (só e-mail) · avisos em tempo real × hub pull · WhatsApp direto × RD | registradas | §5.9, §5.12 |
| DIV-14 / DIV-25 | Propriedades pessoais por evento e termo × RNF-16 · busca servidor × cliente | registradas | §8, RF-SH-04 |
| DIV-15 / DIV-16 / DIV-24 | 8 × 6 status · conteúdo enviado · cancelamento só antes do atendimento | resolvidas por D-15 | §7 |
| DIV-21 / DIV-40 / DIV-41 | Backup sem teste · ambientes/deploy · `TZ` | registradas; TI-76, TI-74, TI-78 | RNF-25..27 |
| DIV-22 / DIV-27 | Trilha por evento real × onboarding por clique · P14 sem fase | resolvidas no texto (RF-ON-12, §3.15) | — |
| DIV-23 | Meu valor F1 × fase 8 forçada | resolvida: antecipado para a Fase 4 | §3.6 |
| DIV-29 | API do WordPress × ADR-0006 | registrada; ADR mantida | §5.13 |
| DIV-31 | "Suspenso" financeiro × cadastral | registrada | §3.14 |
| DIV-32 | Analytics de terceiro × CSP | registrada; RUM próprio | §8 |
| DIV-34 / DIV-37 / DIV-43 | Verdana e paleta × Sora (ADR-0017) · botão verde × gradiente · marca no topo fixo | registradas; P-43 | RNF-30 |
| DIV-35 / DIV-36 / DIV-44 | Navegação §3.1 × rotas atuais · "nada de em breve" × `EmConstrucao` · Comunidade/Onboarding no menu | resolvidas por DEC-24 (RF-SH-16) | §3.0 |
| DIV-38 / DIV-39 | WCAG 2.2/360 px/44 px/fonte ajustável · PWA × `no-store` | resolvidas no texto (RNF-10, RNF-12, RNF-23) | §4 |
| DIV-42 | Docs citavam jobs/`WP_MODE` inexistentes | resolvida (marcadores [alvo]) | — |
| DIV-46 | Cota do hub sem os jobs | registrada; conta `area-associado-jobs` | §5.11 |
---

## 12. Rastreabilidade

Linhas até RF-AU-10 referem-se às seções da **SPEC antiga** (protótipo); as linhas da v0.2
(RF-SH-14 em diante) referem-se à **spec v2** (P0x, B0x, A0n, §). Fase = roteiro (BO = backoffice,
F2 = sem fase ainda).

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
| RF-SH-14 | P03 (busca sem resultado) · §11.2 `busca` | `GET /busca` | `busca_sem_resultado` | `busca_global` | 4 |
| RF-SH-15 | §12.1, §12.3 (UTM, código do gatilho) | `POST /uso` | — | `pagina_ver`/`beneficio_abrir` (`gatilho`) | 4 |
| RF-SH-16 | §3.1 Navegação | `GET /sessao` | `feature_flag` | `pagina_ver` | 3 |
| RF-HO-12 | P02 · §7.2 blocos 1–9 · HOM-01 | `GET /inicio` | `destaque_editorial`, `recomendacao_*`, `trilha_*`, `pergunta_perfil` | `pagina_ver` (`blocos`), `home_bloco_clicar` | 4 |
| RF-HO-13 | §7.2 bloco 1 Pendência | `GET /inicio` | `solicitacao`, `associado_financeiro` | `home_bloco_clicar` | 4 / 7 |
| RF-HO-14 | §7.2 bloco 3 Próximo passo · P13 perfil progressivo | `GET /inicio`, `POST /perfil/pergunta/{chave}` | `trilha_progresso`, `perfil_declarado` | `home_bloco_clicar`, `perfil_declarado_atualizar` | 4 / 3b |
| RF-HO-15 | §7.2 bloco 6 · ADM-05 | `GET /inicio` | `destaque_editorial` | `home_bloco_clicar` | 4 |
| RF-HO-16 | §7.2 bloco 7 Agenda | `GET /inicio` | `evento_cache` | `home_bloco_clicar` | 5 |
| RF-BE-11 | P04 · CAT-05 | `GET /beneficios/{slug}` | `beneficio`, `beneficio_faq`, `parceiro`, `valor_referencia`, `uso_valor` | `beneficio_abrir` (`origem`, `estado`) | 4 |
| RF-BE-12 | §8.1–8.4 elegibilidade, carências, matriz, parâmetros | `GET /beneficios*` (`estado`, `libera_em`) | `beneficio`, `beneficio_categoria_associado`, `parametro`, `associado_perfil`, `associado_financeiro` | — | 4 |
| RF-BE-13 | P04 tipos de ativação 1–6 · SOL-01 | `POST /beneficios/{slug}/ativar` | `beneficio_ativacao`, `solicitacao`, `evento_inscricao` | `beneficio_ativar`, `solicitacao_criar`, `evento_inscrever`, `clube_oferta_usar` | 4 / F2 |
| RF-BE-14 | P03 · CAT-02/03 | `GET /beneficios?filtro=&categoria=&q=` | `beneficio`, `beneficio_ativacao` | `filtro_aplicar` | 4 |
| RF-BE-15 | §3 item 4 "encaminhamento rastreado" | `GET /api/v1/ir/{slug}` | `beneficio`, `parceiro`, `oferta_clube` | `beneficio_acessar`, `clube_oferta_usar` | 4 |
| RF-BE-16 | B03 ficha · §10.1 | `GET /beneficios*` (leitura) | `beneficio`, `beneficio_versao`, `beneficio_faq`, `beneficio_afinidade`, `parceiro` | — | 4 |
| RF-BE-17 | §7.3 recomendação v1 · REC-01 (F2) | `GET /inicio`, `GET /beneficios`, `POST /recomendacoes/{slug}/dispensar` | `beneficio_afinidade`, `recomendacao_dispensa`, `recomendacao_exposicao`, `evento_uso` | `recomendacao_dispensar` | 4 |
| RF-CL-06 | P09 · CLU-01..03 · tipo 6 | `GET /clube`, `POST /clube/ofertas/{id}/abrir` | `oferta_clube` | `clube_oferta_usar` | 6 |
| RF-FA-06 | P06 · VAL-01 · §8.6 | `GET /valor?periodo=` | `uso_valor`, `valor_referencia`, `vw_meu_valor_ano` | `pagina_ver` (`periodo`) | 4 |
| RF-FA-07 | P06 "como calculamos", potencial | `GET /valor` | `texto_sistema`, `valor_referencia` | — | 4 |
| RF-FA-08 | P06 PDF · VAL-03 (anual, F2) | `GET /valor/pdf` | `uso_valor` | `valor_pdf_baixar` | 4 |
| RF-FA-09 | §8.6 modalidades · §11.2.1 níveis 1–4 · `uso_registrado` | — (transições, importação, clube) | `uso_valor`, `valor_referencia` | `uso_registrar` | 4 |
| RF-EV-06 | P10 · EVE-01/02 · tipo 5 · carência 3 m · CON-01 | `GET /eventos*`, `POST /eventos/{id}/inscrever`, `GET /eventos/inscricoes` | `evento_cache`, `evento_inscricao` | `evento_inscrever` (`perfil_preco`) | 5 |
| RF-CA-07 | P07 · CAR-01 (baixar, número) | `GET /carteirinha/imagem.png`, `GET /carteirinha/pdf` | `associado_perfil`, `associado` | `carteirinha_baixar` | 3 |
| RF-CA-08 | P07 · CAR-03 (situação na leitura, revogação) | `GET /verificar/{token}`, `GET /carteirinha` | `associado` (`carteirinha_revogada_em`); hub `associado.situacao` | `carteirinha_verificar` (`resultado`) | 3 |
| RF-ON-12 | P12 · HOM-01 · TRI-01 · `trilha_passo` | `GET /trilha` | `trilha_passo`, `trilha_progresso` | `onboarding_passo_concluir` (`dia_jornada`) | 4 / 6 |
| RF-ON-13 | A03 · A20 · `carencia_vencida` | — (job) | `comunicacao_evento`, `notificacao` | `carencia_vencer` | 4 / F2 |
| RF-PE-10 | P13 · PER-02 | `GET\|PUT /perfil/preferencias` | `perfil_declarado`, `preferencia_canal` | `perfil_declarado_atualizar` | 3b |
| RF-PE-11 | P13 perfil progressivo · §7.2 bloco 3 | `GET /perfil/pergunta`, `POST /perfil/pergunta/{chave}` | `pergunta_perfil`, `perfil_declarado` | `perfil_declarado_atualizar` | 3b |
| RF-PE-12 | P13 · PER-03 · §11.6 consentimento | `GET\|POST /perfil/consentimentos` | `consentimento_texto`, `consentimento` | `consentimento_alterar` | 3b |
| RF-PE-13 | P13 "baixar meus dados" · §11.6 | `POST /perfil/dados/exportar` | `titular_pedido` (+ leitura das tabelas do titular) | `evento_log` `titular_exportacao` | 3b |
| RF-PE-14 | P13 "pedir exclusão" · §11.6 · B13 | `POST /perfil/exclusao` | `titular_pedido`, `solicitacao` | `solicitacao_criar` | 3b |
| RF-SO-08 | P05 · §8.5 status | `GET /solicitacoes*` | `solicitacao` | `solicitacao_status_alterado` | 3 |
| RF-SO-09 | §8.5 `sem_retorno` · A05 · §10.2 | — (job) | `solicitacao`, `solicitacao_evento`, `comunicacao_evento` | — | 3 |
| RF-SO-10 | P05 avaliar 0–10 · A06 | `POST /solicitacoes/{id}/avaliar` | `solicitacao` | `solicitacao_avaliar` | 3 |
| RF-SO-11 | §11.1 Solicitação (associado, benefício, tipo) | `GET /solicitacoes*` | `solicitacao` | `solicitacao_criar` | 3 / 4 |
| RF-SO-12 | P05 cancelar · §10.2 exceções | `POST /solicitacoes/{id}/cancelar` | `solicitacao`, `solicitacao_evento` | `solicitacao_cancelar` | 3 |
| RF-SO-13 | §8.5 log imutável · §11.1 Log de status | `GET /solicitacoes/{id}` | `solicitacao_evento` | — | 3 |
| RF-SO-14 | P04 tipo 3 · P08 declarações · P14 cancelamento · P13 exclusão | `POST /solicitacoes` | `solicitacao` | `solicitacao_criar` | 3 |
| RF-SO-15 | P05 lista (prazo, contato) | `GET /solicitacoes` | `solicitacao`, `parceiro`, `parametro` | — | 3 |
| RF-AU-11 | §14 segurança (step-up) · regra 22 | todos "step-up" | — | `evento_log` `reauth_exigida` | 3 |
| RF-AU-12 | P01 · §11.2 `acesso_primeiro` · A02 | `GET /auth/callback` | `associado` | `acesso_primeiro` | Onda 1 |
| RF-FI-01 | P08 · INT-02 · FIN-01 | `GET /financeiro` | `associado_financeiro`; hub `financeiro.situacao_consultar` | — | 7 |
| RF-FI-02 | P08 mensalidades e histórico | `GET /financeiro` | — (hub) | `pagina_ver` | 7 |
| RF-FI-03 | P08 segunda via · `financeiro_segunda_via` | reservado | — (⛔ fonte) | `fatura_segunda_via` | 7 ⛔ |
| RF-FI-04 | P08 declarações (AMB, carência 1 m) · tipo 3 | `POST /solicitacoes` (`declaracao_associado`) | `solicitacao` | `solicitacao_criar` | 3 |
| RF-FI-05 | A09 · `pagamento_confirmado` · §8.4 | — (job) | `associado_financeiro`, `comunicacao_evento` | `pagamento_confirmar` | 7 ⛔ |
| RF-AJ-01 | P14 · AJU-01 (FAQ) | `GET /ajuda/faq?q=` | `faq` | `pagina_ver`, `busca_global` | 3 |
| RF-AJ-02 | P14 canais e horário · `ajuda_contato` | `GET /ajuda/contato` | `parametro` | `ajuda_contatar` | 3 |
| RF-AJ-03 | P14 formulário | `POST /ajuda/formulario` | `solicitacao` | `solicitacao_criar` | 3 |
| RF-AJ-04 | P14 · AJU-02 cancelamento · A16 · `cancelamento_pedido` | `POST /ajuda/cancelamento` | `solicitacao`, `comunicacao_evento` | `cancelamento_pedir` | 3 |
| RF-AJ-05 | P14 pedidos comuns | — | `faq` | `pagina_ver` | 3 |
| RF-NO-01 | P15 · NOT-02 | `GET /notificacoes` | `notificacao` | `notificacao_abrir` | F2 |
| RF-NO-02 | P15 lida/não lida | `POST /notificacoes/{id}/ler`, `POST /notificacoes/ler-todas` | `notificacao` | — | F2 |
| RF-NO-03 | §3.1 topo fixo (notificações) | `GET /sessao` | `notificacao` | — | F2 |
| RF-NO-04 | A03/A04/A05/A06/A15 "aviso no app" | — | `notificacao` | `notificacao_criar` | 3 |
| RF-NO-05 | — (hipótese; DEC-08) | — | `push_assinatura` | — | F2 |
| RF-CM-01 | §12.1–12.3 · B09 | — | `comunicacao_evento`, `comunicacao_envio`, `comunicacao_supressao` | — | 3 |
| RF-CM-02 | §12.1 transacionais · A04/A05/A06 | — | — (SMTP) | `evento_log` | 3 |
| RF-CM-03 | §12.3 supressão e consentimento · §11.6 | — | `vw_consentimento_atual`, `comunicacao_supressao` | `consentimento_alterar` | 3b |
| RF-CM-04 | §13.1 RD Station | — (job `outbox_rd`) | `comunicacao_evento`, `comunicacao_envio` | — | 3b |
| RF-CM-05 | §12.3 medição (UTM, código do gatilho) · indicador 10 | `POST /uso` | `comunicacao_envio` | `pagina_ver` (`gatilho`) | 4 |
| RF-BO-01 | §9 (perfis, 2FA, auditoria) · §14 LGPD "registro de acesso" | `/api/interno/v1/*` | `usuario_interno`, `backoffice_auditoria`, `acesso_dado_pessoal` | — | BO |
| RF-BO-02 | B05 | `GET /solicitacoes`, `POST /solicitacoes/{id}/status`, `.../reenviar`, `.../exportar.csv` | `solicitacao*` | `solicitacao_status_alterado` | BO |
| RF-BO-03 | B06 · §10.3 · §13.3 | `POST /importacoes`, `.../previa`, `.../confirmar`, `.../devolucao.csv` | `importacao`, `importacao_linha`, `uso_valor` | `uso_registrar` | BO / 4 |
| RF-BO-04 | B13 · §8.2 carências · §8.4 parâmetros · §8.6 valores | `/parametros`, `/valores-referencia`, `/consentimentos/textos`, `/titular/pedidos` | `parametro`, `valor_referencia`, `consentimento_texto`, `feature_flag`, `titular_pedido` | — | BO |
| RF-BO-05 | B01 | `GET /painel/dia` | `solicitacao`, `importacao`, `titular_pedido`, `comunicacao_evento`, `job_execucao`, `fila_ligacao` | — | BO |
| RF-BO-06 | B02 | `GET /associados/{contact_id}` | tabelas locais; hub `associado.visao_360` | `acesso_dado_pessoal` | BO ⛔ |
| RF-BO-07 | B03 · B04 · §10.1 | CRUD `/beneficios`, `/parceiros`, `GET /previa` | `beneficio*`, `parceiro` | — | BO / 4 |
| RF-BO-08 | B12 · §11.3 indicadores · §11.5 painéis · §11.6 k ≥ 20 | `/paineis/*` (ou ferramenta) | `vw_ind_*`, `vw_qualidade_parceiro_mes`, `base_ativa_mensal` | — | BO / 4 |
| RF-BO-09 | B07 · B08 · ADM-05 | CRUD | `destaque_editorial`, `faq`, `trilha_passo`, `texto_sistema`, `segmento`, `beneficio_afinidade` | — | BO / 3 |
| RF-BO-10 | B09 | `GET /comunicacao` | `comunicacao_*`, `notificacao` | — | BO |
| RF-BO-11 | §10.5 fila de ligações · A12 (F2) | `GET /fila-ligacoes`, `POST /fila-ligacoes/{id}/resultado` | `fila_ligacao` | — | 3b / BO |
