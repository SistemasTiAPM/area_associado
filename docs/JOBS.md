# Serviço de jobs — `area-associado-jobs` (runbook)

ADR-0019 (agendador in-process, trava `GET_LOCK`, `job_execucao`, dry-run), ADR-0018 (máquina de
estados), ADR-0003 §5 (outbox e recuo), REQUISITOS §7.3/§7.5, RNF-17/RNF-19. Código em `app/jobs/`;
contrato com o hub em `docs/CONTRATO-HUB.md` → "Solicitações". O job do WordPress (ADR-0006) ainda não
existe. Criado em 2026-10-30 (Onda 2, frente C).

**Regra de ouro:** o serviço nasce em **dry-run** (`JOBS_APLICAR=0`). Jobs com efeito **externo**
(escrita no CRM, e-mail) só registram o que fariam; jobs de efeito **local** (marcador sem retorno,
situação da carteirinha) rodam sempre. Mesma imagem do web, outro processo, sem porta.

## 1. Ligar e desligar

Pré-requisitos, em ordem:

1. Migrações `010` a `014` aplicadas e `db_check` conforme (`docs/PROVISIONAMENTO.md` §2.5). Sem a `011`
   o serviço sobe e **não executa nada** (log `sql/011 (job_execucao) ausente`); sem `010/012/013`, os
   jobs de solicitação/comunicação são pulados; sem a `014`, o de situação.
2. Imagem atual construída (`scripts/deploy.sh` ou `DOCKER_BUILDKIT=0 docker compose build area-associado`).
   O serviço usa a MESMA tag `area_associado-area-associado:latest` (`pull_policy: never`: nunca vai ao
   Docker Hub atrás de uma imagem com esse nome).
3. `.env.jobs` criado (§3). Opcional para o dry-run; obrigatório antes de qualquer job que fale com o hub
   em volume (conta própria, M-8).

```bash
cd /home/ubuntu/area_associado
docker compose --profile jobs up -d area-associado-jobs      # liga (profile "jobs")
docker compose --profile jobs ps area-associado-jobs         # (healthy) em até ~2 min
docker logs --tail 30 area_associado_jobs                    # "modo=SIMULAR (dry-run)", tabela de jobs e próximas execuções
docker compose exec area-associado python -m app.jobs --estado   # última ok por job, erros em 24 h

docker compose --profile jobs stop area-associado-jobs       # desliga (SIGTERM: para entre um item e outro)
docker compose --profile jobs rm -f area-associado-jobs      # remove o container
```

`docker compose up -d` **sem** `--profile jobs` não toca no serviço de jobs (nem sobe, nem para).
Depois de um deploy do web (`scripts/deploy.sh`, que só recria `area-associado`), recriar os jobs na
imagem nova: `docker compose --profile jobs up -d --no-build --force-recreate area-associado-jobs`. O
rollback do `deploy.sh` também não mexe nos jobs: repetir o mesmo comando depois dele.

Endurecimento (igual ao web): `read_only`, `tmpfs /tmp` 64 MB `noexec`, `cap_drop ALL`,
`no-new-privileges`, 256 MB, 64 PIDs, `TZ=America/Sao_Paulo`, logs `json-file` 10 MB × 3,
`stop_grace_period` 40 s. Saúde = idade do heartbeat `/tmp/jobs.heartbeat` (< 180 s); o laço o grava a
cada volta (≤ 15 s) e a cada item processado.

## 2. Jobs

| Job | Agenda | Efeito | Com `JOBS_APLICAR=0` (dry-run) | Com `JOBS_APLICAR=1` |
|---|---|---|---|---|
| `espelhar_solicitacoes` | 1 min (`JOBS_INTERVALO_ESPELHO`) | **externo** (CRM) | conta e loga `<id>:criar|reter|nada`; nada muda | `crm_sync ∈ {pendente, erro}` com `crm_proxima_em ≤ agora` (respeita a janela de arrependimento do cancelamento). Sem `crm_id` e com destino no catálogo (`catalogo_crm.py`) → `solicitacao.criar` (ocorrência da Central; `registro_id` = id, idempotente); sucesso grava `crm_id = id`, entidade, protocolo e o par `statecode/statuscode` e promove `criada → enviada` (ator `sistema`, origem `job`, `evento_uso solicitacao_status_alterado`). Com `crm_id` (mudança local depois do envio) ou sem destino (`exclusao_dados`, benefício) → `crm_sync=retido` + aviso no `evento_log`, sem chamar o hub (não existe ferramenta de status, ADR-0023). Falha recua 1, 2, 4, 8, 16, 32, 60… min e, na 10ª (ou erro permanente: `conflito`, contato inexistente, texto recusado), `falhou` + `evento_log` erro; 429/catálogo inválido/conta sem canal param a rodada sem gastar tentativa. Cancelada antes de existir no CRM → `crm_sync=ok` sem chamar o hub. Exige `HUB_ESCRITA_HABILITADA=true` (senão: espera, execução `erro` "escrita no hub desligada") e a `sql/015` (senão: pulado) |
| `sincronizar_solicitacoes` | 15 min (`JOBS_INTERVALO_SYNC`) | leitura do hub → local | só conta os contatos que consultaria | Contatos com pedido no CRM, não terminal, consultados há mais de `JOBS_SYNC_CADENCIA_H` (6 h): `solicitacao.listar` com `JOBS_SYNC_LIMITE` (10) linhas, 50 se o pedido não estiver na página; casa por `registro_id`; transita **só quando o par `statecode/statuscode` muda** (0/1 de criação não move nada; 0/3 → `pendente_associado` com mensagem padrão + protocolo; resolvida/cancelada → concluída, inclusive de `pendente_associado`). Código desconhecido, registro sumido e terminal local → divergência no `evento_log`. Para no teto diário `JOBS_SYNC_LINHAS_DIA` (5.000 linhas lidas, dia de São Paulo; a cota PII do hub conta linhas) com execução `erro` "teto diário" |
| `marcar_sem_retorno` | 15 min (`JOBS_INTERVALO_SEM_RETORNO`) | local | **roda** | igual: 1º vencimento do prazo → marcador `sem_retorno_desde`, evento, notificação, outbox A05 (associado, equipe, RD); 2º (prazo × 2) → `fila_ligacao` |
| `enviar_comunicacao` | 1 min (`JOBS_INTERVALO_COMUNICACAO`) | **externo** (e-mail) | supressões locais (RD `sem_credencial`; interno sem `CENTRAL_EMAIL` `sem_credencial`; fato mudou `fato_mudou`) acontecem; e-mails só são logados | A04/A05/A06/A16 ao associado (endereço lido do cache `associado_perfil` na hora, nunca gravado na outbox); A05 equipe / A16 Central para `CENTRAL_EMAIL`; `app` → `enviado`; recuo e 10 tentativas como o espelho; `comunicacao_envio` a cada envio/falha. Com `SMTP_MODE=stub` em **staging** nada é marcado (o e-mail espera o SMTP real, P-27); em development/test o stub marca `enviado` com `externo_id=smtp_stub` |
| `situacao_carteirinhas` | diário 03h local (`JOBS_SITUACAO_HORA`) | leitura do hub → local | **roda** | igual: quem tem carteirinha e acessou em 90 dias, leitura com mais de 20 h; lotes ≤ 200 (`JOBS_SITUACAO_LOTE`) × `JOBS_SITUACAO_RODADAS`, pausa `JOBS_SITUACAO_PAUSA` entre chamadas; `cancelado` revoga a carteirinha, `ativo` reativa; 5 leituras seguidas sem resposta → execução `erro` |

Todos: um por vez, trava `GET_LOCK('area_job_<nome>', 0)` (dois containers por engano nunca rodam o
mesmo job), uma linha em `job_execucao` por execução, falha de um job não derruba o laço, 3 falhas
seguidas → `evento_log` `job_falhas_seguidas` severidade `erro` (repetido a cada 20).

`python -m app.jobs --listar` mostra a tabela e a próxima execução; `--uma-vez NOME` roda um job agora
(com trava e rastro) e sai — útil para conferir um dry-run sem esperar a agenda:

```bash
docker compose --profile jobs exec area-associado-jobs python -m app.jobs --uma-vez espelhar_solicitacoes
docker compose --profile jobs run --rm -e JOBS_APLICAR=0 area-associado-jobs python -m app.jobs --uma-vez enviar_comunicacao
```

## 3. `.env.jobs` (segredos só de job)

Arquivo `0600` ao lado do `.env`, fora do git (`.gitignore` cobre `.env.*`), carregado **por cima** do
`.env` só no serviço de jobs. Replicar no cofre junto com o `.env` (P-36).

```bash
install -m 600 /dev/null .env.jobs
cat >> .env.jobs <<'EOF'
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=2
HUB_CLIENT_ID=area-associado-jobs
HUB_CLIENT_SECRET=<segredo da conta de jobs no hub — M-8>
# A conta de jobs nasce só com `ferramentas:ler`: pedir `escrever` faria o hub responder
# invalid_scope e derrubaria até as leituras. true só quando a conta ganhar `escrever` (ADR-0023, §4b).
HUB_ESCRITA_HABILITADA=false
JOBS_APLICAR=0
# CENTRAL_EMAIL=central@apm.org.br     # avisos internos A05/A16 (vazio = suprimidos)
EOF
```

- **Conta do hub:** `area-associado-jobs` (TI-51, M-8; `docs/OPERACAO.md` §10), cota própria (P-41). Sem
  o `.env.jobs`, o serviço usa a conta do web (`area-associado`) e divide a cota de 120/min com as telas —
  aceitável no dry-run, não para o job noturno em volume.
- **Pool:** o processo é de uma linha só e usa no máximo 3 conexões (trava + transação + auditoria); o
  2 + 2 só reduz o teto no RDS compartilhado.
- **Quando ligar `JOBS_APLICAR=1`:** espelho/sync só depois do ensaio da §4b (conta de jobs com
  `ferramentas:escrever`, grants exatos em `solicitacao.criar` e `solicitacao.listar`, cota 25.000/dia,
  `sql/015` aplicada, `HUB_ESCRITA_HABILITADA=true` no `.env.jobs`);
  e-mails só depois da P-27 (`SMTP_MODE=real` com credencial própria). Antes disso o resultado é inócuo
  (espelho em espera; e-mails pendentes em staging), mas a execução registra erro e alerta.
  `JOBS_APLICAR=1` com `HUB_MODE=stub` só sobe em development/test (validador do `Settings`).

## 4. Dry-run: como conferir o que seria feito

```bash
docker logs --since 1h area_associado_jobs | grep -E "simulação|pulado|falhou|disjuntor"
# espelho (simulação): 3 solicitação(ões) na fila do CRM: <id>:criar, <id>:reter, ...
# sync (simulação): consultaria 12 contato(s) no CRM (cadência 6 h)
# comunicação (simulação): 2 envio(s) seriam feitos: 41:A04/email/associado, ...
```

As linhas de `job_execucao` do dry-run têm `modo = 'simular'`; o cursor do sync nunca é gravado nelas.

## 4b. Ensaio do espelho em produção (ADR-0023) — só o contato sintético

Pré-requisitos: `sql/015` aplicada; no painel do hub, a conta `area-associado-jobs` com `ferramentas:escrever`
e grants exatos em `solicitacao.criar` e `solicitacao.listar` (o mapa `CRM_SOLICITACAO_CONTAS` do hub já tem
`area-associado-jobs` → canal Minha APM, origem Web); janela combinada com a Central. O laço do serviço
continua em simulação: o ensaio roda **avulso**, com `JOBS_ENSAIO_CONTATOS` restringindo espelho e
sincronização ao contato sintético. Nenhuma alteração no `.env.jobs`.

```bash
cd /home/ubuntu/area_associado
J="docker compose --profile jobs exec area-associado-jobs"
E="-e JOBS_APLICAR=1 -e HUB_ESCRITA_HABILITADA=true -e JOBS_ENSAIO_CONTATOS=8eb5da36-3847-ee11-be6f-00224837e097"
$J python -m scripts.ensaio_espelho criar                        # pedido local de ensaio, sem e-mail
docker compose --profile jobs exec $E area-associado-jobs python -m app.jobs --uma-vez espelhar_solicitacoes
$J python -m scripts.ensaio_espelho estado                       # enviada, sync ok, protocolo CAS-…, crm 0/1
docker compose --profile jobs exec $E area-associado-jobs python -m scripts.ensaio_espelho repetir <id>
                                                                 # criada=False e o mesmo protocolo
```

Depois, a Central muda o status da ocorrência no CRM (ex.: "Aguardando detalhes"). A cadência de 6 h
vale também aqui; para não esperar, rodar a sincronização com `JOBS_SYNC_CADENCIA_H=1` uma hora depois
do envio (ou mais):

```bash
docker compose --profile jobs exec $E -e JOBS_SYNC_CADENCIA_H=1 area-associado-jobs \
  python -m app.jobs --uma-vez sincronizar_solicitacoes
$J python -m scripts.ensaio_espelho estado                       # pendente_associado, crm 0/3
```

Por fim a Central **cancela** a ocorrência (nunca apaga); a próxima sincronização leva o pedido a
`concluida_negativa`. Registrar protocolo, horários e saídas em `docs/CONCLUIDO.md`.

## 5. Reprocessar (SQL administrativo)

Com a credencial administrativa (`~/.rds-admin.cnf`), depois de corrigida a causa (P-06, grant, SMTP…).
Registrar em `docs/CONCLUIDO.md` (data, quem, quantos, por quê).

```bash
MYSQL="mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado"
```

Espelho no CRM (`falhou` → fila de novo; o job tenta no próximo minuto):

```sql
SELECT id, tipo_servico, status, crm_tentativas, crm_proxima_em FROM solicitacao
 WHERE crm_sync = 'falhou' ORDER BY crm_proxima_em;
-- e o motivo:
SELECT ocorrido_em, JSON_UNQUOTE(JSON_EXTRACT(detalhes, '$.solicitacao_id')) AS id,
       JSON_UNQUOTE(JSON_EXTRACT(detalhes, '$.codigo')) AS codigo
  FROM evento_log WHERE tipo = 'solicitacao_espelho_falhou' ORDER BY id DESC LIMIT 50;

UPDATE solicitacao SET crm_sync = 'pendente', crm_tentativas = 0, crm_proxima_em = UTC_TIMESTAMP(6)
 WHERE crm_sync = 'falhou' AND id IN ('<uuid>', '<uuid>');
```

Retidos (`crm_sync = 'retido'`, ADR-0023): mudanças locais que o CRM não recebe e tipos sem destino. Não
reprocessar enquanto o hub não tiver a ferramenta de status (P-74); a lista serve para avisar a Central:

```sql
SELECT s.id, s.tipo_servico, s.status, s.crm_protocolo, s.atualizada_em FROM solicitacao s
 WHERE s.crm_sync = 'retido' ORDER BY s.atualizada_em DESC LIMIT 50;
```

Outbox de comunicação (`falhou` → pendente):

```sql
SELECT e.id, e.gatilho, e.canal, e.destinatario, e.tentativas, v.erro_codigo
  FROM comunicacao_evento e
  JOIN comunicacao_envio v ON v.comunicacao_evento_id = e.id AND v.situacao = 'falha'
 WHERE e.status = 'falhou' ORDER BY e.id DESC LIMIT 50;

UPDATE comunicacao_evento SET status = 'pendente', tentativas = 0, proxima_tentativa_em = NULL,
       atualizado_em = UTC_TIMESTAMP(6)
 WHERE status = 'falhou' AND id IN (<id>, <id>);
```

Nunca reprocessar `suprimido`: a supressão é decisão (fato mudou, sem credencial, cancelamento), não
falha. Linha presa em `enviando` volta sozinha a `erro` depois de 15 min (o e-mail pode sair duas vezes,
nunca zero). Sync do CRM antes da cadência (ex.: depois de corrigir um código no mapa): como admin,
`UPDATE solicitacao SET crm_consultado_em = NULL WHERE id IN (...)` — o próximo ciclo consulta esses contatos.

## 6. Ler o rastro

```bash
docker compose exec area-associado python -m app.jobs --estado          # resumo humano
docker compose exec area-associado python -m app.jobs --estado --json   # o que o alertas.sh lê
docker exec area_associado curl -fsS http://localhost:8000/db-health | jq .jobs   # última ok por job (UTC)
```

```sql
SELECT id, job, status, modo, iniciado_em, terminado_em, itens_lidos, itens_gravados, itens_erro, erro_resumo
  FROM job_execucao ORDER BY id DESC LIMIT 30;
SELECT job, status, COUNT(*) FROM job_execucao WHERE iniciado_em >= UTC_TIMESTAMP() - INTERVAL 1 DAY
 GROUP BY job, status;
SELECT ocorrido_em, tipo, rota, JSON_EXTRACT(detalhes, '$.erro') FROM evento_log
 WHERE rota LIKE 'job:%' AND severidade = 'erro' ORDER BY id DESC LIMIT 20;
```

`status`: `executando` (agora, ou o processo caiu — a próxima execução do job a fecha como `abortado`),
`ok`, `erro` (exceção ou disjuntor: `erro_resumo` traz tipo e código, nunca a mensagem do terceiro),
`abortado` (SIGTERM no meio, ou queda). `scripts/alertas.sh` alerta em: execução com erro em 24 h,
`evento_log` de erro gravado por job, job parado além do atraso máximo (3 × intervalo, mínimo 15 min;
diário: 26 h) **se o serviço rodou nas últimas 24 h**, e container `area_associado_jobs` não saudável.

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Log `sql/011 (job_execucao) ausente` | migração não aplicada | §2.5 do PROVISIONAMENTO |
| `job X: pulado — sql/010, 012 ou 013 ausente` / `sql/014 ausente` | idem | idem |
| `em execução em outro processo (trava … ocupada)` | dois containers de jobs (ex.: `run --rm` esquecido) | `docker ps \| grep jobs`; parar o extra |
| execução `erro` "espelho em espera: escrita no hub desligada" | `JOBS_APLICAR=1` sem `HUB_ESCRITA_HABILITADA=true` | voltar a `JOBS_APLICAR=0` ou concluir a P-06 |
| `disjuntor: limite_taxa` | cota do hub | conta própria (M-8), `JOBS_LOTE`/`JOBS_SITUACAO_PAUSA` |
| `disjuntor: smtp_autenticacao` | credencial SMTP | P-27; as linhas voltam sem gastar tentativa |
| container `unhealthy` | laço travado ou `/tmp` cheio | `docker logs`; `docker compose --profile jobs restart area-associado-jobs` |

## 7. Retenção

`job_execucao` cresce ~3.000 linhas/dia (espelho e comunicação a cada minuto). A aplicação não tem
DELETE (regra 14). Expurgo pelo operador, com a credencial administrativa, junto com a política da P-15
(sugestão: 90 dias; manter sempre a última `ok` de cada job, que guarda a posição do sync):

```sql
DELETE FROM job_execucao
 WHERE iniciado_em < UTC_TIMESTAMP() - INTERVAL 90 DAY
   AND id NOT IN (SELECT id FROM (SELECT MAX(id) AS id FROM job_execucao WHERE status = 'ok' GROUP BY job) u);
```

Se o volume incomodar antes disso, a alternativa é particionar por mês (molde `sql/008`) numa migração
nova.
