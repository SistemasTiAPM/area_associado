-- =====================================================================
-- area_associado — revogação da carteirinha e situação em tempo quase real
-- (TI-45, DEC-09, RF-CA-08; ADR-0014).
--
-- O QUÊ
--   Três colunas em `associado` (sql/005):
--   - `situacao_normalizada`  : último `situacao_normalizada` EFETIVO lido do
--     hub (`associado.situacao`, docs/CONTRATO-HUB.md). "Efetivo" = o enum do
--     hub, exceto `ativo` com registro desativado no CRM (`statecode` <> 0),
--     que é gravado como `outro` — nesta coluna `ativo` só existe quando o
--     CRM confirma associado ativo E registro ativo (`SituacaoCrm.ativa`).
--   - `situacao_consultada_em`: quando essa leitura aconteceu (UTC). É o
--     cache curto da verificação pública (`VERIFICACAO_CACHE_TTL`) e a fila
--     do job noturno de situação (índice `ix_associado_situacao_consultada`).
--   - `carteirinha_revogada_em`: preenchida quando o hub responde `cancelado`
--     (a filiação cancelada revoga a carteirinha, spec P07); volta a NULL
--     só quando o hub confirma associado ativo de novo (reativação).
--
-- POR QUÊ
--   Antes, `/verificar/{token}` só lia o cache de perfil renovado pelo
--   próprio associado: um cancelado aparecia "Ativo" por até 24 h e depois
--   "não confirmada" para sempre (DIV-13). Com estas colunas a rota pública
--   consulta o hub com cache curto e limite global por processo, e o job
--   noturno (frente C) mantém a revogação mesmo sem leitura pública.
--
-- PRIVILÉGIO
--   NENHUM GRANT novo: `apm_area` já tem UPDATE em `associado` (sql/005,
--   upsert do login e `carteirinha_token`); as colunas novas são do mesmo
--   registro e da mesma natureza (estado da área sobre o associado).
--   DELETE continua inexistente. `scripts/db_check.py` não muda.
--
-- COMO APLICAR (usuário ADMIN do RDS; a aplicação não tem DDL)
--   1. snapshot manual do RDS (docs/OPERACAO.md §6);
--   2. mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--        area_associado < sql/014_carteirinha_revogacao.sql
--   3. registrar o sha256 em schema_migrations (docs/PROVISIONAMENTO.md §2.5b);
--   4. docker compose exec area-associado python -m scripts.db_check
--   O CHECK novo obriga ALGORITHM=COPY (MySQL 8.4 recusa INPLACE para
--   ADD CHECK — conferido no ensaio): a tabela é reconstruída e o upsert do
--   login espera o lock durante a cópia (segundos: uma linha por associado
--   que já entrou). Janela de pouco tráfego; nada da área cai por isso.
--   Enquanto não for aplicada, a aplicação segue no comportamento anterior
--   (`app/dominio/carteirinha.py` confere as colunas no information_schema).
--
-- NÃO REAPLICÁVEL: a segunda execução falha inteira, sem alterar nada
-- (ERROR 3822, CHECK duplicado — conferido no ensaio). A proteção é o
-- registro em `schema_migrations` (versao '014'), que o operador confere
-- antes (`SELECT versao FROM schema_migrations`).
--
-- Ensaiado em MySQL 8.4 descartável em 2026-10-30 (sql/000..009 e 014 em
-- ordem; SHOW CREATE TABLE; UPDATE das colunas novas como apm_area ok;
-- DELETE e ALTER recusados; db_check sem FALHA).
-- =====================================================================

USE `area_associado`;

ALTER TABLE `associado`
    ADD COLUMN `carteirinha_revogada_em` DATETIME(6) NULL
        COMMENT 'UTC — filiação cancelada no CRM (hub); NULL = carteirinha válida'
        AFTER `carteirinha_token`,
    ADD COLUMN `situacao_consultada_em` DATETIME(6) NULL
        COMMENT 'UTC — última leitura de associado.situacao no hub'
        AFTER `carteirinha_revogada_em`,
    ADD COLUMN `situacao_normalizada` ENUM('ativo','suspenso','cancelado','outro') NULL
        COMMENT 'situação efetiva do hub; ativo só com registro ativo no CRM'
        AFTER `situacao_consultada_em`,
    ADD KEY `ix_associado_situacao_consultada` (`situacao_consultada_em`),
    -- Par consistente: leitura do hub grava as duas colunas juntas.
    ADD CONSTRAINT `ck_associado_situacao_par` CHECK (
        (`situacao_normalizada` IS NULL) = (`situacao_consultada_em` IS NULL)
    );

-- Conferência:
--   SHOW CREATE TABLE associado\G
--   SHOW GRANTS FOR 'apm_area'@'%';      -- UPDATE em `associado` (sql/005), nada novo
--   docker compose exec area-associado python -m scripts.db_check
