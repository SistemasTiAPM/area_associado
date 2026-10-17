-- =====================================================================
-- area_associado — feature flags (ADR-0007, REQUISITOS §10).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/003_feature_flag.sql
-- Registrar o hash no schema_migrations após aplicar (docs/PROVISIONAMENTO.md).
--
-- A aplicação só LÊ esta tabela (SELECT do schema, sql/000). Ligar/desligar
-- é ato do operador, por SQL, e vale em até FLAGS_CACHE_TTL segundos:
--   UPDATE feature_flag SET ligada = 1 WHERE chave = 'totalpass';
-- `FLAGS_FORCAR_DESLIGADAS` (Settings) vence a tabela — em produção
-- mantém mensalidade_zero, fatura_valor e patrocinio desligadas até existir
-- fonte de dados (P-12).
--
-- Flag ausente da tabela = desligada. Chave nova exige também entrada em
-- app/flags.py:FLAGS_CONHECIDAS — senão a aplicação a ignora.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `feature_flag` (
    `chave`         VARCHAR(48)  NOT NULL,
    `ligada`        TINYINT(1)   NOT NULL DEFAULT 0,
    `descricao`     VARCHAR(255) NOT NULL,
    `atualizado_em` DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`chave`),
    CONSTRAINT `ck_feature_flag_chave` CHECK (REGEXP_LIKE(`chave`, '^[a-z][a-z0-9_]{1,47}$', 'c')),
    CONSTRAINT `ck_feature_flag_ligada` CHECK (`ligada` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Todas nascem desligadas (CLAUDE.md, regra 19).
INSERT INTO `feature_flag` (`chave`, `ligada`, `descricao`) VALUES
    ('mensalidade_zero', 0, 'Card Mensalidade Zero, pill do header e rodapé da sidebar — sem fonte (P-12)'),
    ('fatura_valor',     0, 'Rota e card da Fatura de valor — sem fonte (P-12)'),
    ('patrocinio',       0, 'Tag patrocinado, borda âmbar e filtro Patrocinados — sem fonte (P-12)'),
    ('clube_economia',   0, 'Economia e cashback do Clube — sem fonte do Clube Certo'),
    ('comunidade_posts', 0, 'Conversas em destaque — sem fonte'),
    ('wallet',           0, 'Adicionar à Wallet — P-13'),
    ('erp_financeiro',   0, 'Dados financeiros do ERP — aguarda parecer de licença (P-08)'),
    ('totalpass',        0, 'Card TotalPass e passo do onboarding — aguarda mcp_hub (P-02, P-04)')
ON DUPLICATE KEY UPDATE `chave` = `chave`;
