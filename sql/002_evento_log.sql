-- =====================================================================
-- area_associado — trilha geral de eventos (segurança, negócio, erro).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/002_evento_log.sql
-- Registrar o hash no schema_migrations após aplicar:
--   sha256sum sql/002_evento_log.sql
--
-- APPEND-ONLY POR PRIVILÉGIO: o usuário `apm_area` tem só SELECT/INSERT no
-- schema (sql/000). Não há gatilho — o RDS recusa SIGNAL sem SUPER (erro
-- 1419) e o privilégio é mais forte: recusa antes de chegar ao motor.
--
-- Retenção (só o operador consegue): `categoria='request'` expira em 12
-- meses; `seguranca`, `negocio` e `erro` não expiram. Purgar em lotes:
--   DELETE FROM evento_log WHERE categoria='request'
--     AND ocorrido_em < NOW() - INTERVAL 12 MONTH ORDER BY ocorrido_em LIMIT 1000;
--
-- Tipos previstos (app/main.py): login_ok, login_falha, login_stub,
-- login_stub_falha, logout, sessao_expirada.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `evento_log` (
    `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `ocorrido_em`  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `request_id`   CHAR(16)        NULL     COMMENT 'ecoado no header X-Request-Id',
    `categoria`    ENUM('seguranca','negocio','erro','request') NOT NULL,
    `tipo`         VARCHAR(48)     NOT NULL,
    `severidade`   ENUM('info','aviso','erro') NOT NULL DEFAULT 'info',
    -- Identidade só como HMAC (LOG_HASH_KEY). O `sub` do IdP já é HMAC do CPF;
    -- re-hashear aqui impede correlacionar dumps dos dois schemas.
    `sub_hash`     CHAR(64)        NULL,
    `contact_id`   VARCHAR(64)     NULL     COMMENT 'id do contato no CRM (não é PII direta)',
    `ip_hash`      CHAR(64)        NULL,
    `ua_hash`      CHAR(64)        NULL,
    `metodo`       VARCHAR(8)      NULL,
    `rota`         VARCHAR(160)    NULL,
    `status_http`  SMALLINT UNSIGNED NULL,
    `duracao_ms`   INT UNSIGNED    NULL,
    `detalhes`     JSON            NULL,
    PRIMARY KEY (`id`),
    KEY `ix_ocorrido` (`ocorrido_em`),
    KEY `ix_sub` (`sub_hash`, `ocorrido_em`),
    KEY `ix_cat_tipo` (`categoria`, `tipo`, `ocorrido_em`),
    KEY `ix_request` (`request_id`),
    -- Rede de proteção: segredo e CPF nunca entram em `detalhes` (audit.py
    -- também filtra). JSON_CONTAINS_PATH com 'one' devolve 1 se QUALQUER
    -- chave existir.
    CONSTRAINT `ck_detalhes_sem_segredo` CHECK (
        `detalhes` IS NULL OR NOT JSON_CONTAINS_PATH(
            `detalhes`, 'one',
            '$.token', '$.id_token', '$.access_token', '$.refresh_token',
            '$.client_secret', '$.cpf', '$.senha', '$.password', '$.authorization'
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
