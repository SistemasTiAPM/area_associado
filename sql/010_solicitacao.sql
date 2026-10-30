-- =====================================================================
-- area_associado — solicitações v2: oito status da spec, marcador
-- `sem_retorno_desde`, vínculo com o catálogo, avaliação 0–10, outbox do CRM
-- e log imutável de status (TI-14; ADR-0018, adenda à ADR-0003; ADR-0004;
-- REQUISITOS §3.12 e §7; spec v2 §6 P05 e §8.5).
--
-- O QUÊ
--   `solicitacao`        fonte da verdade do pedido do associado (o CRM recebe
--                        um espelho pelo job; o associado nunca espera o CRM).
--   `solicitacao_evento` log de status APPEND-ONLY: criação, transições,
--                        marcador sem retorno, avaliação — com ator, origem,
--                        justificativa (obrigatória na origem `backoffice`),
--                        mensagem pública e "conteúdo enviado" (= nomes dos
--                        campos + sha256 + destino + canal; NUNCA o payload).
--
-- POR QUÊ
--   Nomes de status = nomes da spec já na criação (não há dado legado; a v0.1
--   da ADR-0003 nunca chegou ao banco). `enviada` é status de negócio;
--   `sem_retorno` é marcador (coluna), não status. A falha técnica do espelho
--   (`crm_*`) nunca chega à API do associado (RF-SO-06).
--
-- PRIVILÉGIOS (ADR-0004, CLAUDE.md regra 14)
--   `solicitacao`: GRANT UPDATE **por coluna** (abaixo), só nas colunas que a
--   aplicação e o serviço de jobs mudam. Identidade, tipo, vínculo, dados
--   preenchidos, chave de idempotência e data de criação ficam imutáveis
--   para `apm_area` — nem um bug nem uma injeção conseguem trocar o dono ou o
--   conteúdo de um pedido. DELETE nunca (cancelar = status).
--   `solicitacao_evento`: nenhuma concessão — só o SELECT, INSERT do schema
--   (sql/000). Guarda longa: nunca se purga por partição (REQUISITOS §6.4).
--
-- COMO APLICAR (usuário ADMIN do RDS; a aplicação não tem DDL)
--   1. snapshot manual do RDS (docs/OPERACAO.md §6);
--   2. mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--        area_associado < sql/010_solicitacao.sql
--   3. registrar o sha256 em schema_migrations (docs/PROVISIONAMENTO.md §2.5);
--   4. docker compose exec area-associado python -m scripts.db_check
--      → `solicitacao` com GRANT UPDATE (colunas), sem FALHA.
--   Enquanto não aplicada, a área segue no ar: `app/prontidao.py` informa
--   `recursos.solicitacoes=false` e as rotas respondem 503 `recurso_indisponivel`.
--
-- REAPLICÁVEL: sim — `CREATE TABLE IF NOT EXISTS` e GRANT idempotente. Mas
--   uma tabela já existente NÃO é alterada por reaplicação: mudança de
--   estrutura = migração nova.
--
-- Ensaiada em MySQL 8.4 descartável (`mysql-ensaio-a`) em 2026-10-30:
--   000→013 em ordem; INSERT/UPDATE de colunas concedidas como apm_area ok;
--   UPDATE de coluna não concedida, UPDATE em solicitacao_evento e DELETE
--   recusados; CHECKs de CPF, marcador, justificativa e avaliação recusando.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `solicitacao` (
    `id`                   CHAR(36)          NOT NULL COMMENT 'UUID v4 gerado pela aplicação; correlação com o CRM',
    `contact_id`           CHAR(36)          NOT NULL COMMENT 'GUID do contact no CRM (ADR-0014); CPF nunca',
    `sub_hash`             CHAR(64)          NOT NULL COMMENT 'HMAC do sub (LOG_HASH_KEY), correlação com evento_log',
    -- Serviço da APM sem benefício (REQUISITOS §7.4). NULL quando há beneficio_id.
    `tipo_servico`         ENUM('alteracao_cadastro','diagnostico_marketing','submeter_trabalho',
                                'mentoria_pedir','mentoria_oferecer','cartao_apm','outro',
                                'declaracao_associado','cancelamento_associacao','exclusao_dados') NULL,
    -- Vínculo com o catálogo (sql/015, Fase 4), desnormalizado: a ficha pode
    -- mudar, a solicitação guarda o que valia na criação. Sem FOREIGN KEY: o
    -- catálogo ainda não existe e o pedido sobrevive à ficha.
    `beneficio_id`         VARCHAR(36)       NULL,
    `parceiro_id`          VARCHAR(36)       NULL,
    `tipo_ativacao`        TINYINT UNSIGNED  NULL COMMENT '2 encaminhamento, 3 serviço APM, 4 reserva, 5 inscrição',
    `canal_envio`          ENUM('crm','relatorio','email','api','portal') NOT NULL DEFAULT 'crm',
    `prazo_retorno_dias`   SMALLINT UNSIGNED NOT NULL COMMENT 'copiado na criação (parceiro/benefício/parametro)',
    `status`               ENUM('criada','enviada','em_atendimento','pendente_associado',
                                'concluida_positiva','concluida_negativa','cancelada') NOT NULL DEFAULT 'criada',
    `enviada_em`           DATETIME(6)       NULL COMMENT 'UTC; o prazo de retorno conta daqui',
    `sem_retorno_desde`    DATETIME(6)       NULL COMMENT 'UTC; marcador A05 posto pelo job; limpo em qualquer transição',
    `responsavel`          VARCHAR(80)       NULL COMMENT 'quem atende (backoffice/CRM); nunca exibido ao associado',
    `resultado`            JSON              NULL COMMENT 'valor e evidência na conclusão (alimenta uso_valor)',
    `dados`                JSON              NOT NULL COMMENT 'campos do formulário, allowlist por tipo; sem CPF',
    `avaliacao_nota`       TINYINT UNSIGNED  NULL,
    `avaliacao_comentario` VARCHAR(500)      NULL,
    `avaliada_em`          DATETIME(6)       NULL COMMENT 'UTC',
    `cancel_motivo`        VARCHAR(200)      NULL,
    `chave_idempotencia`   CHAR(36)          NULL COMMENT 'UUID gerado no cliente; único por associado',
    `crm_id`               CHAR(36)          NULL COMMENT 'activityid da task no CRM (P-06)',
    `crm_sync`             ENUM('pendente','ok','erro','falhou') NOT NULL DEFAULT 'pendente',
    `crm_tentativas`       TINYINT UNSIGNED  NOT NULL DEFAULT 0,
    `crm_proxima_em`       DATETIME(6)       NOT NULL COMMENT 'UTC; cancelamento da associação: + janela de arrependimento',
    `criada_em`            DATETIME(6)       NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `atualizada_em`        DATETIME(6)       NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `concluida_em`         DATETIME(6)       NULL COMMENT 'UTC; só concluida_*; base do prazo de avaliação',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_solicitacao_idempotencia` (`contact_id`, `chave_idempotencia`),
    KEY `ix_solicitacao_contato_status` (`contact_id`, `status`),
    KEY `ix_solicitacao_contato_atualizada` (`contact_id`, `atualizada_em`, `id`),
    KEY `ix_solicitacao_contato_tipo_criada` (`contact_id`, `tipo_servico`, `criada_em`),
    KEY `ix_solicitacao_crm` (`crm_sync`, `crm_proxima_em`),
    KEY `ix_solicitacao_status_enviada` (`status`, `enviada_em`),
    KEY `ix_solicitacao_parceiro_criada` (`parceiro_id`, `criada_em`),
    CONSTRAINT `ck_solicitacao_id` CHECK (
        REGEXP_LIKE(`id`, '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_solicitacao_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_solicitacao_sub_hash` CHECK (REGEXP_LIKE(`sub_hash`, '^[0-9a-f]{64}$', 'c')),
    CONSTRAINT `ck_solicitacao_chave` CHECK (
        `chave_idempotencia` IS NULL OR
        REGEXP_LIKE(`chave_idempotencia`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_solicitacao_crm_id` CHECK (
        `crm_id` IS NULL OR
        REGEXP_LIKE(`crm_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    -- Todo pedido é de um serviço ou de um benefício (RF-SO-11).
    CONSTRAINT `ck_solicitacao_origem` CHECK (`beneficio_id` IS NOT NULL OR `tipo_servico` IS NOT NULL),
    CONSTRAINT `ck_solicitacao_catalogo_ids` CHECK (
        (`beneficio_id` IS NULL OR REGEXP_LIKE(`beneficio_id`, '^[A-Za-z0-9_-]{1,36}$', 'c')) AND
        (`parceiro_id` IS NULL OR REGEXP_LIKE(`parceiro_id`, '^[A-Za-z0-9_-]{1,36}$', 'c'))
    ),
    CONSTRAINT `ck_solicitacao_tipo_ativacao` CHECK (`tipo_ativacao` IS NULL OR `tipo_ativacao` IN (2, 3, 4, 5)),
    CONSTRAINT `ck_solicitacao_prazo` CHECK (`prazo_retorno_dias` BETWEEN 1 AND 365),
    CONSTRAINT `ck_solicitacao_crm_tentativas` CHECK (`crm_tentativas` <= 20),
    -- `enviada` só com data de envio; o prazo nunca conta de `criada` (RF-SO-09).
    CONSTRAINT `ck_solicitacao_enviada_em` CHECK (`status` <> 'enviada' OR `enviada_em` IS NOT NULL),
    -- Marcador só enquanto a APM/parceiro deve o retorno (ADR-0018 item 3).
    CONSTRAINT `ck_solicitacao_sem_retorno` CHECK (
        `sem_retorno_desde` IS NULL OR `status` IN ('enviada', 'em_atendimento')
    ),
    CONSTRAINT `ck_solicitacao_concluida_em` CHECK (
        `concluida_em` IS NULL OR `status` IN ('concluida_positiva', 'concluida_negativa')
    ),
    CONSTRAINT `ck_solicitacao_cancel_motivo` CHECK (`cancel_motivo` IS NULL OR `status` = 'cancelada'),
    -- Avaliação: uma vez, 0–10, só em concluída (RF-SO-10).
    CONSTRAINT `ck_solicitacao_avaliacao` CHECK (
        (`avaliada_em` IS NULL AND `avaliacao_nota` IS NULL AND `avaliacao_comentario` IS NULL) OR
        (`avaliada_em` IS NOT NULL AND `avaliacao_nota` BETWEEN 0 AND 10
         AND `status` IN ('concluida_positiva', 'concluida_negativa'))
    ),
    -- `dados`: objeto JSON ≤ 16 kB, sem chave proibida nem CPF (molde sql/004).
    CONSTRAINT `ck_solicitacao_dados` CHECK (
        JSON_TYPE(`dados`) = 'OBJECT'
        AND LENGTH(CAST(`dados` AS CHAR)) <= 16384
        AND NOT JSON_CONTAINS_PATH(
            `dados`, 'one',
            '$.token', '$.id_token', '$.access_token', '$.refresh_token',
            '$.client_secret', '$.cpf', '$.senha', '$.password', '$.authorization'
        )
        AND NOT REGEXP_LIKE(CAST(`dados` AS CHAR),
            '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
    ),
    CONSTRAINT `ck_solicitacao_resultado` CHECK (
        `resultado` IS NULL OR (
            JSON_TYPE(`resultado`) = 'OBJECT'
            AND LENGTH(CAST(`resultado` AS CHAR)) <= 4096
            AND NOT JSON_CONTAINS_PATH(
                `resultado`, 'one',
                '$.token', '$.id_token', '$.access_token', '$.refresh_token',
                '$.client_secret', '$.cpf', '$.senha', '$.password', '$.authorization'
            )
            AND NOT REGEXP_LIKE(CAST(`resultado` AS CHAR),
                '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
        )
    ),
    -- Texto livre: sem CPF (a aplicação recusa antes com 400; o CHECK é a rede).
    CONSTRAINT `ck_solicitacao_textos_sem_cpf` CHECK (
        NOT REGEXP_LIKE(CONCAT_WS(' ', `avaliacao_comentario`, `cancel_motivo`, `responsavel`),
            '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `solicitacao_evento` (
    `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `solicitacao_id`   CHAR(36)        NOT NULL,
    `ocorrido_em`      DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC',
    -- criacao: —→criada · transicao: de→para · sem_retorno/sem_retorno_2: marcador
    -- (para = status no momento) · avaliacao: nota registrada (para = status).
    `evento`           ENUM('criacao','transicao','sem_retorno','sem_retorno_2','avaliacao') NOT NULL,
    `de_status`        ENUM('criada','enviada','em_atendimento','pendente_associado',
                            'concluida_positiva','concluida_negativa','cancelada') NULL,
    `para_status`      ENUM('criada','enviada','em_atendimento','pendente_associado',
                            'concluida_positiva','concluida_negativa','cancelada') NOT NULL,
    `ator`             ENUM('associado','sistema','parceiro','apm','importacao') NOT NULL,
    `origem`           ENUM('ui','job','crm','backoffice','importacao','api_parceiro','portal_parceiro') NOT NULL,
    `usuario_interno`  VARCHAR(120)    NULL COMMENT 'identidade externa do atendente (backoffice/CRM)',
    `justificativa`    VARCHAR(500)    NULL COMMENT 'interna; nunca exibida ao associado',
    `mensagem_publica` VARCHAR(2000)   NULL COMMENT 'visível ao associado (pedido do parceiro, resposta dele)',
    `conteudo_enviado` JSON            NULL COMMENT '{campos, sha256, destino, canal} — nunca o payload',
    `request_id`       CHAR(16)        NULL,
    PRIMARY KEY (`id`),
    KEY `ix_sol_evento_solicitacao` (`solicitacao_id`, `ocorrido_em`, `id`),
    KEY `ix_sol_evento_ocorrido` (`ocorrido_em`),
    CONSTRAINT `fk_sol_evento_solicitacao` FOREIGN KEY (`solicitacao_id`) REFERENCES `solicitacao` (`id`),
    CONSTRAINT `ck_sol_evento_forma` CHECK (
        (`evento` = 'criacao' AND `de_status` IS NULL AND `para_status` = 'criada') OR
        (`evento` = 'transicao' AND `de_status` IS NOT NULL AND `de_status` <> `para_status`) OR
        (`evento` IN ('sem_retorno', 'sem_retorno_2', 'avaliacao') AND `de_status` IS NULL)
    ),
    -- Mudança manual sempre com justificativa (spec §8.5; ADR-0018 item 4).
    CONSTRAINT `ck_sol_evento_justificativa` CHECK (
        `origem` <> 'backoffice' OR (`justificativa` IS NOT NULL AND CHAR_LENGTH(TRIM(`justificativa`)) > 0)
    ),
    -- Pedido ao associado sempre com mensagem pública (REQUISITOS §7.3).
    CONSTRAINT `ck_sol_evento_pendente_mensagem` CHECK (
        `evento` <> 'transicao' OR `para_status` <> 'pendente_associado' OR
        (`mensagem_publica` IS NOT NULL AND CHAR_LENGTH(TRIM(`mensagem_publica`)) > 0)
    ),
    CONSTRAINT `ck_sol_evento_conteudo` CHECK (
        `conteudo_enviado` IS NULL OR (
            JSON_TYPE(`conteudo_enviado`) = 'OBJECT'
            AND JSON_LENGTH(`conteudo_enviado`) = 4
            AND JSON_CONTAINS_PATH(`conteudo_enviado`, 'all', '$.campos', '$.sha256', '$.destino', '$.canal')
            AND JSON_TYPE(JSON_EXTRACT(`conteudo_enviado`, '$.campos')) = 'ARRAY'
            AND REGEXP_LIKE(JSON_UNQUOTE(JSON_EXTRACT(`conteudo_enviado`, '$.sha256')), '^[0-9a-f]{64}$', 'c')
            AND LENGTH(CAST(`conteudo_enviado` AS CHAR)) <= 2048
        )
    ),
    CONSTRAINT `ck_sol_evento_request_id` CHECK (
        `request_id` IS NULL OR REGEXP_LIKE(`request_id`, '^[0-9a-f]{16}$', 'c')
    ),
    CONSTRAINT `ck_sol_evento_textos_sem_cpf` CHECK (
        NOT REGEXP_LIKE(CONCAT_WS(' ', `usuario_interno`, `justificativa`, `mensagem_publica`),
            '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE só em `solicitacao`, e só nestas colunas (ADR-0004, ADR-0018).
-- Justificativa, coluna a coluna:
--   status, atualizada_em, concluida_em, cancel_motivo — transição
--     condicional (`UPDATE ... WHERE status = :de`) feita pela máquina de
--     estados (app/dominio/solicitacoes/maquina.py), pelo associado
--     (cancelar, responder) e pelo sync do CRM (jobs);
--   enviada_em, sem_retorno_desde — promoção a `enviada` e marcador A05
--     (jobs, ADR-0018 itens 2–3);
--   avaliacao_nota, avaliacao_comentario, avaliada_em — avaliação única
--     (`WHERE avaliada_em IS NULL`, RF-SO-10);
--   responsavel, resultado — conclusão registrada pelo atendimento (CRM/
--     importação), base de uso_valor;
--   crm_id, crm_sync, crm_tentativas, crm_proxima_em — outbox do espelho no
--     CRM com backoff (ADR-0003 item 5).
-- Fora da lista (imutáveis para a aplicação): id, contact_id, sub_hash,
-- tipo_servico, beneficio_id, parceiro_id, tipo_ativacao, canal_envio,
-- prazo_retorno_dias, dados, chave_idempotencia, criada_em.
-- `solicitacao_evento` não recebe UPDATE em hipótese alguma (trilha).
-- Sem DELETE em nenhuma das duas.
-- ---------------------------------------------------------------------
GRANT UPDATE (`status`, `atualizada_em`, `concluida_em`, `cancel_motivo`,
              `enviada_em`, `sem_retorno_desde`,
              `avaliacao_nota`, `avaliacao_comentario`, `avaliada_em`,
              `responsavel`, `resultado`,
              `crm_id`, `crm_sync`, `crm_tentativas`, `crm_proxima_em`)
    ON `area_associado`.`solicitacao` TO 'apm_area'@'%';
FLUSH PRIVILEGES;

-- Conferência:
--   SHOW GRANTS FOR 'apm_area'@'%';
--   docker compose exec area-associado python -m scripts.db_check
