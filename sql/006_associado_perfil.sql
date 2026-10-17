-- =====================================================================
-- area_associado — cache do perfil do associado (Fase 2, ADR-0002/0005).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/006_associado_perfil.sql
-- Registrar o hash no schema_migrations após aplicar.
--
-- O CRM é a fonte da verdade do cadastro. Esta tabela é CACHE dos campos que
-- a área exibe (minimização, RNF-16): preenchida no login a partir do
-- userinfo (escopo `carteirinha`) e completada pelo mcp_hub. CPF NUNCA
-- (ADR-0014). Foto: só a miniatura 128×128 (a 512×512 vive no CRM).
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `associado_perfil` (
    `contact_id`         CHAR(36)     NOT NULL,
    `nome`               VARCHAR(160) NULL,
    `email`              VARCHAR(254) NULL,
    `celular`            VARCHAR(20)  NULL,
    `telefone`           VARCHAR(20)  NULL,
    `telefone2`          VARCHAR(20)  NULL,
    `endereco`           JSON         NULL COMMENT 'logradouro, numero, complemento, bairro, cidade, uf, cep',
    `num_contato`        VARCHAR(20)  NULL,
    `crm`                VARCHAR(20)  NULL,
    `crm_uf`             CHAR(2)      NULL,
    `tipo_associado`     VARCHAR(40)  NULL,
    `status_associativo` VARCHAR(40)  NULL,
    `data_filiacao`      DATE         NULL,
    `foto_miniatura`     MEDIUMBLOB   NULL COMMENT 'JPEG 128x128, sem metadados',
    `foto_etag`          CHAR(16)     NULL,
    `foto_atualizada_em` DATETIME(6)  NULL COMMENT 'UTC',
    `origem`             ENUM('userinfo','hub','stub') NOT NULL,
    `atualizado_em`      DATETIME(6)  NOT NULL COMMENT 'UTC — última confirmação de nome/situação/carteirinha (login ou hub)',
    `contato_atualizado_em` DATETIME(6) NULL   COMMENT 'UTC — última leitura de contatos/endereço no hub',
    PRIMARY KEY (`contact_id`),
    KEY `ix_perfil_atualizado` (`atualizado_em`),
    CONSTRAINT `ck_perfil_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_perfil_uf` CHECK (`crm_uf` IS NULL OR REGEXP_LIKE(`crm_uf`, '^[A-Z]{2}$', 'c')),
    CONSTRAINT `ck_perfil_foto` CHECK (`foto_miniatura` IS NULL OR LENGTH(`foto_miniatura`) <= 65536),
    CONSTRAINT `ck_perfil_endereco_sem_cpf` CHECK (
        `endereco` IS NULL OR NOT JSON_CONTAINS_PATH(`endereco`, 'one', '$.cpf')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE só nesta tabela (ADR-0004). Justificativa: é cache — cada
-- leitura da fonte (login, hub) e cada edição confirmada pelo CRM
-- sobrescreve a linha. Sem DELETE: dado obsoleto é sobrescrito.
-- ---------------------------------------------------------------------
GRANT UPDATE ON `area_associado`.`associado_perfil` TO 'apm_area'@'%';
FLUSH PRIVILEGES;
