# ADR-0019: Serviço de jobs `area-associado-jobs` com agendador in-process

- **Status:** Aceita
- **Data:** 2026-10-30
- **Decisores:** Sistemas TI (William) · Claude Code (Estivador/Integrador/Atlas)
- **Relacionadas:** ADR-0003 (outbox), ADR-0004, ADR-0006 (sincronização do portal), ADR-0002

## Contexto

A spec v2 exige rotinas assíncronas desde a F1: espelho e sincronização de solicitações, marcador
`sem_retorno` por prazo do parceiro (A05), carência vencida (A03), importação mensal do CSV, outbox para
o RD Station, fila de ligações às 8h, score diário, resumo mensal, sincronização do WordPress (ADR-0006).
Hoje **nada assíncrono existe**: não há `app/jobs/`, o compose tem um só serviço e `requirements.txt` não
tem agendador (`docs/LEVANTAMENTO-TECNICO-spec-v2.md` §12.1 TI-01; `docs/spec-v2/personas/estivador.md`
"Serviço de jobs"). Os projetos irmãos resolvem de três formas: `crond` na imagem com `flock` e
`CRON_APLICAR` (totalpass), loop `sh` com heartbeat (appapm) e crontab do host com `docker exec`
(login_associado). A cota da conta `area-associado` no hub (120/min, 5.000 PII/dia) foi dimensionada só
para o web (P-41).

## Decisão

1. **Um serviço `area-associado-jobs`** no `docker-compose.yml`: mesma imagem, `command: python -m
   app.jobs`, sem `expose`, 256M, `read_only`, `tmpfs /tmp:size=64m`, `cap_drop ALL`, `no-new-privileges`,
   `pids_limit`, `TZ=America/Sao_Paulo`, `env_file: .env` + `.env.jobs` (`required: false`, segredos só de
   job: Locaweb, RD, credencial de job do hub), `profiles: ["jobs"]` enquanto não houver job com efeito
   externo liberado, `restart: always`, logs `json-file 10m×3`.
2. **Agendador in-process em Python** (`app/jobs/__main__.py`): loop único com "próxima execução" por job,
   intervalo fixo com jitter, tratamento de SIGTERM, falha de um job não derruba o loop, um job por vez na
   primeira versão (2 vCPU compartilhadas). Sem `crond` (evitaria `cap_add SETUID/SETGID` e pacote extra)
   e sem crontab do host (perde reprodutibilidade e `docker logs`).
3. **Trava e rastro**: `SELECT GET_LOCK('area_job_<nome>', 0)` por execução (sobrevive a dois containers
   por engano, libera na queda da conexão) **e** linha em `job_execucao` (`sql/011`: `job` com CHECK de
   regex, `iniciado_em`, `terminado_em`, `status ENUM(executando, ok, erro, abortado)`, contagens,
   `erro_resumo` com CHECK anti-segredo/CPF, `host`, `versao_app`; `GRANT UPDATE` justificado para fechar a
   linha). Outbox usa claim condicional (`UPDATE … WHERE status='pendente' AND proxima_em <= NOW()`).
4. **Dry-run obrigatório para efeito externo**: `JOBS_APLICAR=0|1` no `Settings` (padrão `0`); com `0`, jobs
   que escrevem no CRM, no RD ou enviam e-mail só registram o que fariam. Jobs só de leitura/local
   (WordPress em stub, `sem_retorno`, carência) rodam normalmente.
5. **Observabilidade**: heartbeat em `/tmp/jobs.heartbeat` a cada ciclo + `HEALTHCHECK` por idade do arquivo;
   `/db-health` do web expõe a última execução ok de cada job; 3 falhas seguidas ⇒ `evento_log` severidade
   `erro` ⇒ alerta (`scripts/alertas.sh`); `verificar-pos-reboot.sh` inclui o container.
6. **Conta própria no hub** (`area-associado-jobs`, `client_credentials`, mesma allowlist de rede, grants
   exatos nas ferramentas de leitura em lote/cursor, cota separada) — provisão pelo operador do hub; até lá,
   jobs que falam com o hub rodam com amostra e disjuntor (`max_por_rodada`).
7. **Pool de banco pequeno** nos jobs (`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=2`); jobs de varredura de madrugada.
8. Runbook em `docs/JOBS.md` (ligar/desligar, dry-run, reprocessar outbox, ler `job_execucao`).

## Consequências

### Positivas
- Tudo assíncrono num lugar só, reproduzível em homologação e CI, com `docker logs`, lock e rastro.
- Efeito externo nunca acontece por acidente (dry-run por padrão), lição já paga pelo totalpass.

### Negativas / riscos
- Disciplina de lock e intervalo fica no código (sem crontab legível). Mitigação: tabela de jobs em
  `docs/JOBS.md` e teste do agendador.
- Segundo container consome memória (cabe: 4,9 GiB de limites somados em 7,8 GiB) e conexões no RDS
  compartilhado (`max_connections` a confirmar).

### Obrigações decorrentes
- TI-01 (Onda 2): compose, `app/jobs/`, `sql/011_job_execucao.sql`, `docs/JOBS.md`, `JOBS_APLICAR` em
  `app/config.py`, `.env.example` com as chaves de job.
- `scripts/db_check.py` já aceita `job_execucao` na allowlist quando a migração existir (TI-03).
- P-41 refeita com os jobs; conta `area-associado-jobs` no hub (TI-51).

## Alternativas descartadas
- **`crond` na imagem** (totalpass): crontab legível, mas exige `cap_add` e pacote no slim.
- **Crontab do host com `docker compose exec`** (login_associado): zero código, mas fora do compose, logs
  em arquivo do host, não reproduzível em homologação.
- **Celery/APScheduler**: dependência e superfície novas para meia dúzia de jobs com intervalo fixo.
