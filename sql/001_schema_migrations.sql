-- =====================================================================
-- area_associado — controle de migrações.
--
-- Rodar com o usuário ADMIN do RDS (o usuário da aplicação não tem DDL):
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/001_schema_migrations.sql
--
-- Convenção: todo arquivo sql/NNN_*.sql aplicado registra uma linha aqui,
-- com o sha256 do arquivo — detecta migração editada depois de aplicada.
--   sha256sum sql/001_schema_migrations.sql
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `schema_migrations` (
    `versao`       VARCHAR(64)  NOT NULL COMMENT 'prefixo numérico do arquivo, ex.: 001',
    `arquivo`      VARCHAR(255) NOT NULL,
    `sha256`       CHAR(64)     NOT NULL COMMENT 'hash do arquivo no momento da aplicação',
    `aplicado_em`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `aplicado_por` VARCHAR(96)  NOT NULL DEFAULT (CURRENT_USER()),
    PRIMARY KEY (`versao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `schema_migrations` (`versao`, `arquivo`, `sha256`)
VALUES ('001', '001_schema_migrations.sql', REPEAT('0', 64))
ON DUPLICATE KEY UPDATE `versao` = `versao`;
