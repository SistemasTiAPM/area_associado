-- =====================================================================
-- area_associado — identidade do associado na área (ADR-0014).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/005_associado.sql
-- Registrar o hash no schema_migrations após aplicar.
--
-- Guarda só o que é DA ÁREA: primeiro/último acesso e (Fase 2) o token
-- público da carteirinha. Dado cadastral é do CRM; o cache dele nasce em
-- `associado_perfil` na Fase 2, junto com o contrato do mcp_hub.
--
-- Chave: `contact_id` (GUID do contact no Dataverse, claim do IdP). CPF nunca.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `associado` (
    `contact_id`         CHAR(36)    NOT NULL COMMENT 'GUID do contact no CRM (minúsculas)',
    `sub_hash`           CHAR(64)    NOT NULL COMMENT 'HMAC do sub (LOG_HASH_KEY)',
    `primeiro_acesso_em` DATETIME(6) NOT NULL COMMENT 'UTC',
    `ultimo_acesso_em`   DATETIME(6) NOT NULL COMMENT 'UTC',
    -- Fase 2 (ADR-0014): base32 de HMAC-SHA256(CARTEIRINHA_HMAC_KEY, contact_id), 20 chars.
    `carteirinha_token`  CHAR(20)    NULL,
    PRIMARY KEY (`contact_id`),
    UNIQUE KEY `uq_associado_carteirinha_token` (`carteirinha_token`),
    KEY `ix_associado_sub` (`sub_hash`),
    CONSTRAINT `ck_associado_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_associado_token` CHECK (
        `carteirinha_token` IS NULL OR REGEXP_LIKE(`carteirinha_token`, '^[A-Z2-7]{20}$', 'c')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE só nesta tabela (ADR-0004, CLAUDE.md regra 14). Justificativa:
-- o login faz upsert (INSERT ... ON DUPLICATE KEY UPDATE exige UPDATE)
-- de `ultimo_acesso_em`/`sub_hash`; a Fase 2 grava `carteirinha_token`.
-- Sem DELETE: associado não se apaga, para a trilha continuar explicável.
-- ---------------------------------------------------------------------
GRANT UPDATE ON `area_associado`.`associado` TO 'apm_area'@'%';
FLUSH PRIVILEGES;

-- Conferência:
--   SHOW GRANTS FOR 'apm_area'@'%';
--   docker compose exec area-associado python -m scripts.db_check
