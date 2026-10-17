-- =====================================================================
-- area_associado — códigos de confirmação de troca de e-mail (Fase 2).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/007_email_verificacao.sql
-- Registrar o hash no schema_migrations após aplicar.
--
-- O e-mail do CRM é o canal de recuperação de senha do Login APM: trocar
-- exige código enviado ao NOVO endereço (decisão de 2026-10-17) e login
-- recente no IdP. Aqui ficam só HMACs (LOG_HASH_KEY): nem o e-mail novo nem
-- o código são recuperáveis a partir da tabela.
--
-- Regras (app/dominio/email_verificacao.py): código de 6 dígitos, validade
-- EMAIL_CODIGO_TTL (padrão 10 min), 5 tentativas, 60 s entre envios, 5 envios
-- por hora por associado. Pedido novo invalida os anteriores.
--
-- Retenção (P-15, só o operador): linhas com mais de 30 dias podem ser
-- purgadas em lotes.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `email_verificacao` (
    `id`            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `contact_id`    CHAR(36)         NOT NULL,
    `email_hash`    CHAR(64)         NOT NULL COMMENT 'HMAC do e-mail novo normalizado',
    `codigo_hash`   CHAR(64)         NOT NULL COMMENT 'HMAC do código (ligado ao id do pedido)',
    `criado_em`     DATETIME(6)      NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `expira_em`     DATETIME(6)      NOT NULL,
    `tentativas`    TINYINT UNSIGNED NOT NULL DEFAULT 0,
    `usado_em`      DATETIME(6)      NULL,
    `invalidado_em` DATETIME(6)      NULL,
    PRIMARY KEY (`id`),
    KEY `ix_email_verif_contato` (`contact_id`, `criado_em`),
    CONSTRAINT `ck_email_verif_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_email_verif_hashes` CHECK (
        REGEXP_LIKE(`email_hash`, '^[0-9a-f]{64}$', 'c') AND REGEXP_LIKE(`codigo_hash`, '^[0-9a-f]{64}$', 'c')
    ),
    CONSTRAINT `ck_email_verif_tentativas` CHECK (`tentativas` <= 10)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE só nesta tabela (ADR-0004). Justificativa: contar tentativa,
-- marcar uso e invalidar pedidos anteriores. Sem DELETE.
-- ---------------------------------------------------------------------
GRANT UPDATE ON `area_associado`.`email_verificacao` TO 'apm_area'@'%';
FLUSH PRIVILEGES;
