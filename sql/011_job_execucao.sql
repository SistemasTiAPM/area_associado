-- =====================================================================
-- area_associado — rastro das execuções do serviço de jobs
-- `area-associado-jobs` (TI-01; ADR-0019 item 3; REQUISITOS RNF-17, RNF-19,
-- §6.2 linha 011).
--
-- O QUÊ
--   `job_execucao`  uma linha por execução de job: aberta (`executando`) logo
--                   depois de o job obter a trava `GET_LOCK('area_job_<nome>')`
--                   e fechada no fim com o resultado (`ok`, `erro`,
--                   `abortado`), as contagens de itens e, se houver, um
--                   resumo curto do erro. O job de sincronização com o CRM
--                   guarda aqui o cursor (`posicao`) — a próxima execução
--                   continua da posição da última execução `ok` em modo
--                   `aplicar` (sem tabela de estado nova).
--
-- POR QUÊ
--   `docker logs` some a cada deploy; o rastro no banco responde "o job rodou?
--   quando foi o último ok? quantos itens? por que falhou?" para o
--   `/db-health`, o `scripts/alertas.sh` e o operador (docs/JOBS.md).
--   `abortado` = o processo parou no meio (SIGTERM, queda): a linha que ficou
--   `executando` é fechada pela execução seguinte do mesmo job, que só chega
--   lá segurando a trava (não há outra execução viva daquele job).
--
-- PRIVILÉGIOS (ADR-0004, CLAUDE.md regra 14)
--   `GRANT UPDATE` **por coluna** (abaixo), só no que FECHA a linha. A
--   identidade da execução (`id`, `job`, `iniciado_em`, `modo`, `host`,
--   `versao_app`) é imutável para `apm_area`. DELETE nunca: retenção é ato do
--   operador (P-15) ou partição futura (molde sql/008) — ver docs/JOBS.md §7.
--
-- PII E SEGREDO: nenhuma coluna guarda identificador de associado.
--   `erro_resumo` (≤ 500) é montado pela aplicação com o tipo da exceção e um
--   código nosso — nunca corpo de resposta de terceiro (CLAUDE.md regra 16);
--   o CHECK recusa CPF e padrões de credencial como rede de proteção.
--   `posicao` é opaca (devolvido pelo mcp_hub), só caracteres de base64/ISO.
--
-- COMO APLICAR (usuário ADMIN do RDS; a aplicação não tem DDL)
--   1. snapshot manual do RDS (docs/OPERACAO.md §6);
--   2. mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--        area_associado < sql/011_job_execucao.sql
--   3. registrar o sha256 em schema_migrations (docs/PROVISIONAMENTO.md §2.5);
--   4. docker compose exec area-associado python -m scripts.db_check
--      → `job_execucao` com GRANT UPDATE (colunas), "resultado : conforme".
--   Enquanto não aplicada, o serviço de jobs sobe e NÃO executa job nenhum
--   (sem rastro não há execução — fail-closed; log `sql/011 ausente`), e o
--   `/db-health` informa `jobs: "n/a"`.
--
-- REAPLICÁVEL: sim — `CREATE TABLE IF NOT EXISTS` e GRANT idempotente. Uma
--   tabela já existente NÃO é alterada por reaplicação.
--
-- Ensaiada em MySQL 8.4 descartável (`mysql-ensaio-c`) em 2026-10-30:
--   000→014 em ordem; reaplicação sem erro; como apm_area: INSERT e UPDATE das
--   colunas concedidas ok; UPDATE de `job`/`iniciado_em`/`host`, DELETE e
--   ALTER recusados; CHECKs de nome, forma, CPF e credencial recusando.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `job_execucao` (
    `id`             BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `job`            VARCHAR(48)      NOT NULL COMMENT 'nome do job no registro (app/jobs/registro.py)',
    `iniciado_em`    DATETIME(6)      NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC',
    `terminado_em`   DATETIME(6)      NULL     COMMENT 'UTC; NULL só enquanto executando',
    `status`         ENUM('executando','ok','erro','abortado') NOT NULL DEFAULT 'executando',
    -- `simular` = JOBS_APLICAR=0: o job registrou o que faria, sem efeito externo.
    `modo`           ENUM('aplicar','simular') NOT NULL,
    `itens_lidos`    INT UNSIGNED     NOT NULL DEFAULT 0,
    `itens_gravados` INT UNSIGNED     NOT NULL DEFAULT 0,
    `itens_erro`     INT UNSIGNED     NOT NULL DEFAULT 0,
    `erro_resumo`    VARCHAR(500)     NULL     COMMENT 'tipo da exceção + código nosso; nunca corpo de terceiro',
    `posicao`        VARCHAR(200)     NULL     COMMENT 'posição opaca para a próxima execução (sync do CRM)',
    `host`           VARCHAR(64)      NOT NULL COMMENT 'hostname do container (id curto do Docker)',
    `versao_app`     VARCHAR(40)      NOT NULL COMMENT 'versão/sha da imagem',
    PRIMARY KEY (`id`),
    KEY `ix_job_execucao_job` (`job`, `iniciado_em`),
    -- Última execução ok por job (/db-health, alertas, posição do sync): varredura solta no índice.
    KEY `ix_job_execucao_status` (`status`, `job`, `iniciado_em`),
    CONSTRAINT `ck_job_execucao_job` CHECK (REGEXP_LIKE(`job`, '^[a-z][a-z0-9_]{2,47}$', 'c')),
    CONSTRAINT `ck_job_execucao_forma` CHECK (
        (`status` = 'executando') = (`terminado_em` IS NULL)
        AND (`terminado_em` IS NULL OR `terminado_em` >= `iniciado_em`)
        AND (`erro_resumo` IS NULL OR `status` IN ('erro', 'abortado', 'ok'))
    ),
    CONSTRAINT `ck_job_execucao_host` CHECK (REGEXP_LIKE(`host`, '^[A-Za-z0-9._-]{1,64}$', 'c')),
    CONSTRAINT `ck_job_execucao_versao` CHECK (REGEXP_LIKE(`versao_app`, '^[A-Za-z0-9._+-]{1,40}$', 'c')),
    CONSTRAINT `ck_job_execucao_posicao` CHECK (
        `posicao` IS NULL OR REGEXP_LIKE(`posicao`, '^[A-Za-z0-9_.:+=/-]{1,200}$', 'c')
    ),
    -- Rede de proteção (a aplicação já monta o resumo só com tipo + código):
    -- sem CPF e sem nada com cara de credencial.
    CONSTRAINT `ck_job_execucao_erro_resumo` CHECK (
        `erro_resumo` IS NULL OR (
            NOT REGEXP_LIKE(`erro_resumo`,
                '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
            AND NOT REGEXP_LIKE(`erro_resumo`,
                '(bearer|basic)[[:space:]]+[A-Za-z0-9._~+/=-]{8,}', 'i')
            AND NOT REGEXP_LIKE(`erro_resumo`,
                '(senha|password|passwd|secret|segredo|token|authorization|api[_-]?key)[[:space:]]*[:=]', 'i')
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE só nas colunas que FECHAM a execução (ADR-0019 item 3). A linha é
-- aberta por INSERT e fechada uma vez (`UPDATE ... WHERE id = :id AND
-- status = 'executando'`); a execução seguinte fecha como `abortado` a que
-- ficou aberta por queda do processo. Justificativa, coluna a coluna:
--   terminado_em, status            — fim da execução;
--   itens_lidos/gravados/erro       — contagens apuradas no fim;
--   erro_resumo                     — causa curta do erro/aborto;
--   posicao                         — cursor do sync do CRM (só no fim ok).
-- Fora da lista (imutáveis): id, job, iniciado_em, modo, host, versao_app.
-- Sem DELETE.
-- ---------------------------------------------------------------------
GRANT UPDATE (`terminado_em`, `status`, `itens_lidos`, `itens_gravados`, `itens_erro`, `erro_resumo`, `posicao`)
    ON `area_associado`.`job_execucao` TO 'apm_area'@'%';
FLUSH PRIVILEGES;

-- Conferência:
--   SHOW GRANTS FOR 'apm_area'@'%';
--   docker compose exec area-associado python -m scripts.db_check
--   SELECT job, status, modo, iniciado_em, terminado_em, itens_lidos, itens_gravados, itens_erro
--     FROM job_execucao ORDER BY id DESC LIMIT 20;
