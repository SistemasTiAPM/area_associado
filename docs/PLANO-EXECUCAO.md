# Plano de execução da Minha APM — do mais fácil ao mais problemático

| Item | Valor |
|---|---|
| Data | 2026-10-30 |
| Base | [`LEVANTAMENTO-TECNICO-spec-v2.md`](LEVANTAMENTO-TECNICO-spec-v2.md) (92 TI, 38 EXT, 46 DIV, 36 DEC) e a [spec v2](spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md) |
| Critério de ordem | (1) sem decisão nem terceiro → (2) só decisão do usuário com recomendação pronta → (3) terceiro com versão stub/flag → (4) decisão arquitetural grande ou fonte inexistente |
| Como usar | Cada onda tem plano próprio e aprovação antes de código (`CLAUDE.md` §4; skill `nova-fase-minha-apm`). Ao fechar uma tarefa, marcar ✅ no levantamento §12 e registrar em `CONCLUIDO.md`. Externos (EXT/P-xx) **nunca** bloqueiam a onda: a versão com stub/flag entra e a real liga quando o terceiro responder. |

HEAD## Onda 0 — operador, sem código (agora)

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

## Onda 2 — Fase 3 ampliada: solicitações, P05, P14, jobs, comunicação produzida, carteirinha (executada em 30/10)

Aprovada pelo usuário em 30/10 ("pode seguir com a onda 2"). Decisões já tomadas: DEC-01, 02, 04, 13, 22,
28, 29 (ADR-0018..0021). Externos que **não** bloqueiam (versão stub/flag/dry-run): P-06 (espelho no CRM),
P-27 (SMTP), P-42/P-44 (mockups e textos: textos da spec como proposta), P-41/M-7 (cota e grant do hub).

### Frentes e posse de arquivos

| Frente | Persona | Tarefas | Arquivos que só ela edita |
|---|---|---|---|
| **A — núcleo de solicitações e ajuda** | Atlas + Maestro + Sentinela | TI-14, TI-15, TI-16, TI-08, TI-18 (produção da outbox), TI-20, TI-57 (declaração), contador real e prontidão em `/sessao` | `sql/010`, `sql/012`, `sql/013`; `app/dominio/solicitacoes/`, `app/dominio/comunicacao.py`, `app/dominio/ajuda.py`, `app/dominio/limites_negocio.py`, `app/prontidao.py`; `app/api/v1/solicitacoes.py`, `ajuda.py`, `modelos_solicitacoes.py`, `sessao.py`, `__init__.py`; `app/uso.py` (só `detalhes`); `scripts/db_check.py` (allowlist); `tests/test_solicitacoes*.py`, `tests/test_ajuda*.py` |
| **B — carteirinha** | Sentinela + Maestro | TI-45 (verificação em tempo quase real e revogação), TI-46 (imagem/PDF, número) | `sql/014`; `app/dominio/carteirinha.py`, `app/publico.py`, `app/api/v1/carteirinha.py`, classe `CarteirinhaResposta` em `modelos.py`; `app/config.py` (só chaves `VERIFICACAO_*`/`CARTEIRINHA_*` novas); `Dockerfile` (só fonte TTF, se precisar); `tests/test_carteirinha*.py` |
| **D — front** | Vitrine | TI-10 (React Router 7 + `navegarSeguro`), TI-21 (P05), TI-22 (P14), TI-46 (front), rota `ajuda` no menu, prontidão | `frontend/**` (inclui `package.json` só para o Router 7) |
| **C — jobs** (depois de A e B) | Integrador + Estivador | TI-01 (serviço, `sql/011`, `docs/JOBS.md`), TI-17 (espelho em dry-run, sync, `sem_retorno`), TI-19 (transacionais A04/A05/A06/A16), job noturno de situação (TI-45), zonas `limit_req` (TI-08, vhost de exemplo) | `sql/011`; `app/jobs/**`; `app/integracoes/hub.py`/`hub_stub.py` (métodos `solicitacao.*`); `app/integracoes/email.py` (textos); `app/config.py` (só `JOBS_*`); `docker-compose.yml`; `deploy/**`; `docs/JOBS.md`; `docs/CONTRATO-HUB.md`; `tests/test_jobs*.py` |
| Integração, deploy e docs | eu | `docs/api/openapi.json` final, REQUISITOS, PENDENCIAS, CONCLUIDO, levantamento, e2e completo, deploy, commit | — |

### Migrações (aplicação pelo operador, em ordem; snapshot antes)

`010_solicitacao` (ADR-0018: 8 status, `sem_retorno_desde`, vínculos, canal, prazo, avaliação, idempotência,
`crm_*` com 4 valores; `solicitacao_evento` só INSERT com ator/origem/justificativa/`conteudo_enviado`) ·
`011_job_execucao` (ADR-0019) · `012_comunicacao_notificacao` (`comunicacao_evento` outbox com dedupe,
`comunicacao_envio` e `comunicacao_supressao` append-only, `notificacao` com UPDATE só de `lida_em`,
`fila_ligacao`) · `013_ajuda_parametro` (`faq`, `texto_sistema`, `parametro` com seed `avaliacao_prazo_dias`=30,
`prazo_retorno_padrao_dias`, `cancelamento_janela_horas`=24, `central_horario`/`central_telefone` vazios até
P-44; só leitura para `apm_area`) · `014_carteirinha_revogacao` (`ALTER associado`: `carteirinha_revogada_em`,
`situacao_consultada_em`, `situacao_normalizada`). **Enquanto o operador não aplicar**, o web segue no ar:
`app/prontidao.py` verifica a existência das tabelas (cache 60 s; falha = indisponível) e `GET /sessao` informa
`recursos {solicitacoes, ajuda}`; a SPA mostra "em construção" nessas rotas e o contador fica 0.

### Contrato de API (fixo para as frentes; tudo sob `/api/v1`, sessão obrigatória, `[C]` = CSRF)

Nunca `contact_id`, `sub`, CPF, `crm_*` ou e-mail em resposta. Erros no contrato único.

| Rota | Entrada | Saída | Erros específicos |
|---|---|---|---|
| `GET /sessao` | — | + `recursos: {solicitacoes: bool, ajuda: bool}`; `solicitacoes_aguardando` = contagem real de `pendente_associado` (0 se indisponível) | — |
| `GET /solicitacoes?situacao=andamento\|encerradas&cursor=&limite=` (≤ 20) | — | `{itens: [Resumo], proximo_cursor: str\|null}` | `503 recurso_indisponivel` sem tabelas |
| `GET /solicitacoes/{id}` | — | `Solicitacao` | `404 nao_encontrado` (de outro associado também) |
| `POST /solicitacoes` [C] | `{tipo_servico: outro\|declaracao_associado\|alteracao_cadastro, campos: {...}, chave_idempotencia: uuid}` | `201 Solicitacao` (`200` na repetição da chave) | `400 entrada_invalida` (schema por tipo; tipo fora da lista), `409 estado_invalido` (unicidade por tipo), `409 nao_elegivel {libera_em}` (declaração AMB < 1 mês de filiação), `429 limite_negocio` (`outro` 5/dia) |
| `POST /solicitacoes/{id}/cancelar` [C] | `{motivo?: str ≤ 200}` | `Solicitacao` | `409 estado_invalido` (inclui `em_atendimento`) |
| `POST /solicitacoes/{id}/responder` [C] | `{texto: 1–2000}` | `Solicitacao` | `409 estado_invalido` |
| `POST /solicitacoes/{id}/avaliar` [C] | `{nota: 0–10, comentario?: ≤ 500}` | `Solicitacao` | `409 ja_avaliada`, `409 estado_invalido`, `409 prazo_expirado` |
| `GET /ajuda/faq?q=&categoria=` | `q` ≤ 80 | `{categorias: [{codigo, rotulo}], itens: [{id, pergunta, resposta, categoria}], sugestoes: [codigo]}` | `503 recurso_indisponivel` |
| `GET /ajuda/contato` | — | `{whatsapp: {exibicao, url}\|null, telefone: {exibicao, uri}\|null, horario: str\|null}` (vazios = bloco some) | — |
| `POST /ajuda/formulario` [C] | `{assunto: beneficio\|cadastro\|financeiro\|eventos\|outro, mensagem: 1–2000, chave_idempotencia}` | `201 Solicitacao` (tipo `outro`) | como `POST /solicitacoes` |
| `POST /ajuda/cancelamento` [C] [F:`cancelamento_online`] step-up | `{motivo: nao_uso\|preco\|mudanca\|insatisfacao_servico\|outro, quer_conversa: bool, comentario?: ≤ 500, chave_idempotencia}` | `201 Solicitacao` (`cancelamento_associacao`; espelho só após `cancelamento_janela_horas`; nunca escreve no CRM) | `403 reautenticacao_necessaria`, `404 recurso_desligado`, `409 estado_invalido` (já há pedido aberto) |
| `GET /carteirinha` | — | + `revogada: bool`, `num_contato`; `qr`/`url_verificacao` nulos quando revogada | — |
| `GET /carteirinha/imagem.png`, `GET /carteirinha/documento.pdf` | — | binário, `no-store`, `Content-Disposition: attachment` | `409 carteirinha_revogada`, `503` |
| `POST /carteirinha/compartilhar` [C] | — | como hoje | `409 carteirinha_revogada` |

`Resumo` = `{id, tipo: {codigo, rotulo}, beneficio: {slug, titulo}\|null, status, rotulo_status,
aguardando_parceiro: bool, prazo_em: AAAA-MM-DD\|null, contato: {canal, texto}\|null, criada_em,
atualizada_em, pode_cancelar, pode_responder, pode_avaliar}`. `Solicitacao` = `Resumo` + `{campos:
{nome: valor} (só campos permitidos do tipo), linha_do_tempo: [{quando, status, rotulo, ator:
voce\|equipe_apm\|parceiro\|sistema, mensagem\|null}], avaliacao: {nota, comentario, avaliada_em}\|null}`.
Rótulos de status: os 7 da spec (tipo 3: "Encaminhada à equipe" para `enviada`).

**Verificação pública (`/verificar/{token}`):** revogada ⇒ "carteirinha sem validade" (sem motivo); cache de
situação > `VERIFICACAO_CACHE_TTL` (10 min) ⇒ `associado.situacao` no hub com limite global de 60/min por
processo; hub fora/sem grant/limite ⇒ comportamento atual ("não confirmada no momento" quando o cache passa de
24 h); `detalhes.resultado` ∈ `ativo\|inativo\|nao_confirmado`; nunca CPF, e-mail ou telefone.

**Jobs (frente C):** dry-run por padrão (`JOBS_APLICAR=0`); serviço no compose com `profiles: ["jobs"]` (o
operador liga depois das migrações); espelho e sincronização chamam `solicitacao.*` no hub só com
`JOBS_APLICAR=1` (ferramentas chegam na Onda 5 com a P-06); `marcar_sem_retorno` e situação noturna rodam
sempre; e-mails transacionais pelo SMTP da área (stub fora de produção).

### Pronto quando
Associado cria (formulário/declaração), acompanha, responde, cancela e avalia uma solicitação com os 8 status
e a linha do tempo; FAQ e contato da Central na Ajuda; pedido de cancelamento com step-up atrás da flag;
carteirinha baixável e revogável, verificação pública consultando a situação; outbox e notificação gravadas
na mesma transação; jobs com rastro em `job_execucao`; pytest, Vitest e e2e (axe 2.2, CSP) verdes; no ar com
as rotas novas em "em construção" até as migrações.

## Onda 3 — Fase 3b: P13 preferências, consentimentos e direitos do titular

Decisões antes: DEC-06 (anonimização), DEC-26 (tratamento), DEC-27 (fonte). Ordem: TI-25 `sql/019` → TI-26
domínio/API → TI-27 front → TI-28 retenção (`RETENCAO.md`, scripts do operador) → TI-90 padrão de acesso a
dado pessoal → TI-64 tokens em `rem` + controle de fonte → TI-53 cliente RD em stub + `outbox_rd` → TI-59 fila
de ligações provisória. Externos: P-54 (textos/prazos: flag `lgpd_consentimentos` com texto v0), P-46 (RD:
outbox acumula). Pronto quando: consentimento versionado gravado e exibido com histórico; exportação e
pedido de exclusão com step-up; retenção documentada.

## Onda 4 — Fase 4: catálogo como dado, elegibilidade, home em blocos, Meu valor v1

Decisões antes: DEC-14, DEC-15, DEC-16, DEC-23, DEC-24, DEC-25, DEC-34, DEC-35 (DEC-03 parte de banco já
decidida: `apm_area_bo`). Ordem: TI-29 `sql/016` + TI-35 `sql/017` + TI-92 → TI-30 elegibilidade (pura, testes
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
Access/IPs, P-53 arquivos. Entrega: ADR própria, TI-80 (infra + `sql/021`), TI-81 canal do CSV, TI-58 API
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
| 2 | **feita** (ver `CONCLUIDO.md`); restam ações do operador: `sql/008`–`014`, M-7, `.env.jobs` + profile `jobs`, zonas do porteiro | 2026-10-30 |
| 3–7 | planejadas | 2026-10-30 |
