-- =====================================================================
-- area_associado — eventos de uso / analytics (ADR-0012, REQUISITOS §8).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/004_evento_uso.sql
-- Registrar o hash no schema_migrations após aplicar.
--
-- Spec: "cada resgate vira dado" — {associadoId, acao, entidade, id, timestamp}.
-- A Fatura de valor e o relatório para patrocinadores dependem disto.
--
-- APPEND-ONLY POR PRIVILÉGIO: nenhuma concessão nesta migração — vale o
-- SELECT, INSERT do schema (sql/000). Sem UPDATE, sem DELETE.
--
-- Identidade: `contact_id` (GUID do CRM, ADR-0014) + `sub_hash` (HMAC com
-- LOG_HASH_KEY, mesmo de evento_log, para correlação). CPF nunca.
-- `acao` é validada contra o catálogo fechado em app/uso.py.
--
-- Retenção (P-15, só o operador): purgar em lotes conforme a política
-- definida, ex.:
--   DELETE FROM evento_uso WHERE ocorrido_em < NOW() - INTERVAL 24 MONTH
--     ORDER BY ocorrido_em LIMIT 5000;
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `evento_uso` (
    `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `ocorrido_em` DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC',
    `contact_id`  CHAR(36)        NULL     COMMENT 'GUID do contact no CRM',
    `sub_hash`    CHAR(64)        NULL     COMMENT 'HMAC do sub (LOG_HASH_KEY)',
    `acao`        VARCHAR(48)     NOT NULL,
    `entidade`    VARCHAR(32)     NOT NULL,
    `entidade_id` VARCHAR(64)     NULL,
    `origem`      ENUM('servidor','ui','job','publico') NOT NULL,
    `request_id`  CHAR(16)        NULL,
    `detalhes`    JSON            NULL,
    PRIMARY KEY (`id`),
    KEY `ix_uso_contato` (`contact_id`, `ocorrido_em`),
    KEY `ix_uso_acao` (`acao`, `ocorrido_em`),
    KEY `ix_uso_entidade` (`entidade`, `entidade_id`),
    KEY `ix_uso_ocorrido` (`ocorrido_em`),
    CONSTRAINT `ck_uso_acao` CHECK (REGEXP_LIKE(`acao`, '^[a-z][a-z0-9_]{1,47}$', 'c')),
    -- Mesma rede de proteção de evento_log (sql/002), mais CPF por padrão de
    -- valor: detalhes nunca carrega segredo nem CPF, com ou sem pontuação.
    CONSTRAINT `ck_uso_detalhes_sem_segredo` CHECK (
        `detalhes` IS NULL OR (
            NOT JSON_CONTAINS_PATH(
                `detalhes`, 'one',
                '$.token', '$.id_token', '$.access_token', '$.refresh_token',
                '$.client_secret', '$.cpf', '$.senha', '$.password', '$.authorization'
            )
            -- Delimitado por não-hex: 11 dígitos dentro de um request_id
            -- hexadecimal não é CPF e não pode recusar a linha.
            AND NOT REGEXP_LIKE(CAST(`detalhes` AS CHAR),
                '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
