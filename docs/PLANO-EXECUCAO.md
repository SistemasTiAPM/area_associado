# Plano de execução da Minha APM — do mais fácil ao mais problemático

| Item | Valor |
|---|---|
| Data | 2026-10-30 |
| Base | [`LEVANTAMENTO-TECNICO-spec-v2.md`](LEVANTAMENTO-TECNICO-spec-v2.md) (92 TI, 38 EXT, 46 DIV, 36 DEC) e a [spec v2](spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md) |
| Critério de ordem | (1) sem decisão nem terceiro → (2) só decisão do usuário com recomendação pronta → (3) terceiro com versão stub/flag → (4) decisão arquitetural grande ou fonte inexistente |
| Como usar | Cada onda tem plano próprio e aprovação antes de código (`CLAUDE.md` §4; skill `nova-fase-minha-apm`). Ao fechar uma tarefa, marcar ✅ no levantamento §12 e registrar em `CONCLUIDO.md`. Externos (EXT/P-xx) **nunca** bloqueiam a onda: a versão com stub/flag entra e a real liga quando o terceiro responder. |

Numeração de migrações a partir desta data (o levantamento §6.1 reservava a partir de `sql/008`; deslocou
em +2 porque a partição e as flags v2 entram antes): `008` partição de `evento_uso`/`evento_log` · `009`
flags v2 · `010` solicitação · `011` `job_execucao` · `012` catálogo · `013` valor · `014` conteúdo do portal ·
`015` consentimento/preferências/titular · `016` comunicação/notificação · `017` trilha/comunidade/clube ·
`018` backoffice · `019` financeiro (cache) · `020` score · `021` base ativa · `022` views.

## Onda 0 — operador, sem código (agora)

| Tarefa | O que | Quem executa | Entregue pela TI |
|---|---|---|---|
| P-01 / TI-70 | Emitir Cloudflare Origin CA, instalar em `sites-enabled/certs/`, `nginx -t && reload`, zona Full (strict), remover `temp.pem` | operador + Cloudflare admin | runbook em `OPERACAO.md` |
| P-36 / TI-73 | Replicar `.env` de 21/10 no Secrets Manager; apagar os 3 `.env.bak-*`; conferência por hash | operador | runbook + `scripts/alertas.sh` (conferência) |
| P-34 / TI-71 | Catch-all 443 `_00_padrao.conf` (`return 444`) | operador | `deploy/nginx_porteiro/_00_padrao.conf.example` |
| P-19 / TI-72 | `verificar-pos-reboot.sh` com `area_associado`, `mcp_hub`, `appapm-cron`, hosts `minha`/`mcp`, validade do cert | operador | `deploy/verificar-pos-reboot.patch.md` |
| P-61 / TI-75 | Conta em monitor externo + rodar `scripts/alertas.sh` por cron | operador | `scripts/alertas.sh` |
| P-59, P-60 | IAM para snapshot/restore e `GetSecretValue`; teste de restauração do RDS | AWS admin / operador | runbook de backup em `OPERACAO.md` |

Critério de pronto: `curl -vI https://minha.apm.org.br` com cadeia válida e zona em Full (strict); hash do
`.env` igual ao do cofre; `_00_padrao.conf` ativo; pós-reboot verde; monitor avisando.

## Onda 1 — base transversal e fast-path (executada em 30/10)

Sem decisão nova, sem terceiro. Aprovada e executada em 30/10 (ver `CONCLUIDO.md`).

| Grupo | Tarefas | Pronto quando |
|---|---|---|
| Docs | TI-06 REQUISITOS v0.2 · TI-68 higiene (LICENSES, ADR-0017 errata, CUTOVER, vhost, PENDENCIAS_AWS) · TI-76 runbook backup/restore · TI-12 runbook de chaves | arquivos revisados; links resolvem |
| Front fast-path | TI-61 voz §3.3 · TI-62 alvos 44 px/`scroll-padding`/`dvh` · TI-63 axe `wcag22aa` + `mobile-360` · TI-65 primitivos puros · TI-69 template de teste · TI-23 sub-rotas no shell | `npm run check` verde; e2e sem violação de CSP; axe 2.2 em todas as rotas |
| Backend pequeno | TI-05 `acesso_primeiro` · TI-09 `exigir_reautenticacao` · TI-13 flags v2 (`sql/009`) · TI-07 OpenAPI artefato (`docs/api/openapi.json`) · TI-11 campanha · TI-04 parcial (catálogo de `uso.py` + teste `AcaoUi` = `ACOES_UI`) | pytest verde; `openapi.json` versionado; flags desligadas no seed |
| Banco/scripts | TI-03 `db_check` honesto (+ usuários `apm_area_bo`/`apm_area_painel`) · TI-02 `sql/008` partição mensal (ensaiada; **aplicação pelo operador**) | ensaio em MySQL 8.4 registrado; `db_check` falha em tabela da allowlist sem grant |
| Infra leve | TI-78 compose (`pids_limit`, tmpfs `size`, `TZ`) · TI-74 `scripts/deploy.sh` | `docker compose config` ok; deploy com smoke e rollback documentado |
| Hub | TI-47 `associado.situacao`/`historico_associacao` por `contact_id` sem CPF, concedidas à área · TI-51 parcial (conta de jobs documentada; resposta à P-41) | `check_hub` imprime `situacao : ok` sem chave `cpf` |

Decisões registradas nesta onda (ADRs): 0018 Solicitações v2 · 0019 Serviço de jobs · 0020 Limites de
negócio · 0021 Flags v2 · 0022 Usuário de banco do backoffice.

## Onda 2 — Fase 3 ampliada: solicitações, P05, P14, jobs, comunicação produzida

Pré-requisitos: Onda 1 no ar; ADR-0018..0021 (feitas). Decisão restante: nenhuma (DEC-01, 02, 04, 13, 22,
28, 29 decididas em 30/10).

Ordem interna: TI-14 `sql/010` solicitação → TI-15 máquina/schemas → TI-16 API `/solicitacoes` + contador
real → TI-08 limites/zonas → TI-10 React Router 7 + `navegarSeguro` → TI-01 serviço de jobs (`sql/011`
`job_execucao`) → TI-17 jobs (espelho em stub, sync, `sem_retorno`) → TI-18 outbox de comunicação +
`notificacao` produzidas (envio desligado por flag) → TI-19 transacionais A04/A05/A06 (stub SMTP) → TI-20 P14
(FAQ, contato, cancelamento como solicitação) → TI-21 front P05 → TI-22 front P14 → TI-46 carteirinha
(download + número) → TI-45 verificação em tempo quase real (usa TI-47) → TI-57 declarações como
solicitação. Tamanho total: G (3 G + 7 M + 5 P).

Externos que não bloqueiam: P-06 (espelho: stub), P-27 (SMTP: stub), P-42/P-44 (mockups/textos: textos da
spec como proposta), P-41 (cota: cache e limite global). Pronto quando: associado cria, acompanha, cancela e
avalia uma solicitação de ponta a ponta com os 8 status; A04/A05/A06 aparecem na outbox; `job_execucao` tem
rastro; e2e da tela P05/P14 com axe 2.2.

## Onda 3 — Fase 3b: P13 preferências, consentimentos e direitos do titular

Decisões antes: DEC-06 (anonimização), DEC-26 (tratamento), DEC-27 (fonte). Ordem: TI-25 `sql/015` → TI-26
domínio/API → TI-27 front → TI-28 retenção (`RETENCAO.md`, scripts do operador) → TI-90 padrão de acesso a
dado pessoal → TI-64 tokens em `rem` + controle de fonte → TI-53 cliente RD em stub + `outbox_rd` → TI-59 fila
de ligações provisória. Externos: P-54 (textos/prazos: flag `lgpd_consentimentos` com texto v0), P-46 (RD:
outbox acumula). Pronto quando: consentimento versionado gravado e exibido com histórico; exportação e
pedido de exclusão com step-up; retenção documentada.

## Onda 4 — Fase 4: catálogo como dado, elegibilidade, home em blocos, Meu valor v1

Decisões antes: DEC-14, DEC-15, DEC-16, DEC-23, DEC-24, DEC-25, DEC-34, DEC-35 (DEC-03 parte de banco já
decidida: `apm_area_bo`). Ordem: TI-29 `sql/012` + TI-35 `sql/013` + TI-92 → TI-30 elegibilidade (pura, testes
de tabela) → TI-31 ativação por tipo + API de benefícios → TI-32 redirecionador → TI-33 recomendação v1 →
TI-34 `GET /inicio` → TI-43 trilha por evento real (bloco) → TI-36 Meu valor (modo sem ERP) → TI-37 busca
→ TI-38 P03 → TI-39 P04 → TI-40 P02 → TI-41 P06 → TI-42 job carência → TI-44 views/indicadores → TI-60
navegação §3.1 → TI-48 hub perfil ampliado → TI-54 parser CSV + tabelas → TI-55 jobs de diferença.
Externos: P-48 catálogo validado (sem ele: fixture de teste e telas vazias — regra 19), P-49 parâmetros,
P-56 atributos, P-53 CSV, P-42/P-44. Pronto quando: catálogo publicado por dado, 6 estados corretos por
associado, home em blocos sem valor ilustrativo, Meu valor v1 com proteção incluída e solicitações concluídas.

## Onda 5 — integrações reais, na ordem em que os terceiros responderem

| Chegou | Liga | Tarefas |
|---|---|---|
| P-06 entidade no CRM | espelho real das solicitações | TI-50 (hub `solicitacao.*`), TI-17 real |
| P-27 SMTP | e-mails transacionais e alertas | TI-19, TI-20, TI-75 |
| P-46 RD | gatilhos A01–A06, A16 | TI-53 real, TI-11 real |
| P-07/P-21 Locaweb | notícias e eventos | TI-56 real → TI-87 (Fase 5), depois TI-88 clube (Fase 6) |
| P-04/P-08 ERP | financeiro | TI-49, TI-57 (Fase 7) |
| P-50 parceiros | tipo 2 por canal | TI-24 (+ ADR por parceiro com API) |
| P-25 Actions | CI | TI-77 |

## Onda 6 — backoffice (o mais problemático pela decisão institucional)

Decisões: DEC-03 completa (hospedagem e identidade; recomendação: container próprio na mesma imagem,
host próprio, Cloudflare Access + Entra ID) e DEC-05 (canal do CSV). Externos: P-65 Entra ID, P-62 Cloudflare
Access/IPs, P-53 arquivos. Entrega: ADR própria, TI-80 (infra + `sql/018`), TI-81 canal do CSV, TI-58 API
interna, TI-90 em uso; módulos mínimos B01, B05, B06, B13. Até lá: catálogo/parâmetros por SQL do operador
(limitação registrada), fila de ligações por CSV interno (TI-59).

## Onda 7 — F2/F3 e RNF maiores

TI-66 PWA (DEC-07) · TI-67 medição/RUM · TI-79 homologação (DEC-30, P-57) · TI-84 logs · TI-83 IdP
(nascimento, continuar conectado, dados mudaram, retorno; P-56/P-64) · TI-85 notificações in-app (DEC-08) ·
TI-86 score · TI-89 comunidade (F3) · TI-91 push · P08 segunda via e P-58 "novo sistema de cadastro e
cobrança" — **o mais problemático: a fonte não existe**.

## Estado

| Onda | Estado | Última atualização |
|---|---|---|
| 0 | arquivos entregues (`OPERACAO.md`, `_00_padrao.conf.example`, `verificar-pos-reboot.patch.md`, `alertas.sh`); execução pelo operador | 2026-10-30 |
| 1 | **feita** (ver `CONCLUIDO.md` 2026-10-30); restam ações do operador: grant M-7 no hub, `sql/008`, `sql/009`, WebKit no host de e2e | 2026-10-30 |
| 2–7 | planejadas | 2026-10-30 |
