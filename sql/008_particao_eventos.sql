-- =====================================================================
-- area_associado — partição mensal das trilhas `evento_log` e `evento_uso`
-- (TI-02; ADR-0004 §3, ADR-0012; fecha o mecanismo da P-15).
--
-- O QUÊ
--   As duas trilhas append-only passam a ter PK composta `(id, ocorrido_em)`
--   e `PARTITION BY RANGE (TO_DAYS(ocorrido_em))`, uma partição por mês,
--   pré-criadas de 2026-10 a 2028-10 (25 meses) + `pMAX` (MAXVALUE), que
--   recebe o que ultrapassar a última partição mensal até o operador criar
--   as próximas (procedimento no fim deste arquivo).
--
-- POR QUÊ
--   O expurgo por retenção vira `ALTER TABLE ... DROP PARTITION` — ato
--   administrativo, instantâneo, sem `DELETE` em lotes e sem fragmentar o
--   InnoDB. A aplicação continua sem UPDATE nem DELETE nessas tabelas
--   (nenhuma concessão aqui; vale o SELECT, INSERT do schema, sql/000).
--   Feito agora, com as tabelas pequenas: o ALTER reconstrói a tabela.
--
-- O QUE NÃO MUDA
--   Colunas, defaults, índices secundários (viram índices locais de cada
--   partição, com o mesmo nome) e as CONSTRAINT CHECK anti-segredo/CPF.
--   Não há UNIQUE além da PK nem FOREIGN KEY nas duas tabelas — ambas
--   exigiriam a coluna de partição ou impediriam o particionamento.
--   `id` continua AUTO_INCREMENT (é a primeira coluna da PK, como o InnoDB
--   exige). `ix_ocorrido`/`ix_uso_ocorrido` ficam: ajudam a poda de
--   partição e o ORDER BY dentro do mês.
--
-- COMO APLICAR (usuário ADMIN do RDS; a aplicação não tem DDL)
--   Janela de pouco tráfego: durante a cópia (segundos nas tabelas de hoje)
--   os INSERTs da aplicação esperam o metadata lock; `audit.registrar` e
--   `uso.registrar` nunca derrubam a resposta ao associado.
--   1. snapshot manual do RDS (docs/OPERACAO.md §6);
--   2. mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--        area_associado < sql/008_particao_eventos.sql
--   3. registrar o sha256 em schema_migrations (docs/PROVISIONAMENTO.md §2.3);
--   4. docker compose exec area-associado python -m scripts.db_check
--      → linha `particoes : evento_log=26 evento_uso=26` sem FALHA.
--
-- NÃO REAPLICÁVEL: rodar de novo reconstrói as tabelas sem necessidade.
-- A proteção é o registro em `schema_migrations` (versao '008'), que o
-- operador confere antes (`SELECT versao FROM schema_migrations`).
--
-- Ensaiado em MySQL 8.4 descartável em 2026-10-30 (sql/000..008 em ordem;
-- SHOW CREATE TABLE; INSERT como apm_area ok; UPDATE/DELETE recusados).
-- =====================================================================

USE `area_associado`;

-- ---------------------------------------------------------------------
-- evento_log (sql/002): ocorrido_em DATETIME(3) — TO_DAYS ignora a fração.
-- A primeira partição (p202610) recebe também qualquer linha anterior a
-- 2026-10-01 (a tabela nasceu em outubro de 2026).
-- ---------------------------------------------------------------------
ALTER TABLE `evento_log`
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (`id`, `ocorrido_em`)
    PARTITION BY RANGE (TO_DAYS(`ocorrido_em`)) (
        PARTITION p202610 VALUES LESS THAN (TO_DAYS('2026-11-01')),
        PARTITION p202611 VALUES LESS THAN (TO_DAYS('2026-12-01')),
        PARTITION p202612 VALUES LESS THAN (TO_DAYS('2027-01-01')),
        PARTITION p202701 VALUES LESS THAN (TO_DAYS('2027-02-01')),
        PARTITION p202702 VALUES LESS THAN (TO_DAYS('2027-03-01')),
        PARTITION p202703 VALUES LESS THAN (TO_DAYS('2027-04-01')),
        PARTITION p202704 VALUES LESS THAN (TO_DAYS('2027-05-01')),
        PARTITION p202705 VALUES LESS THAN (TO_DAYS('2027-06-01')),
        PARTITION p202706 VALUES LESS THAN (TO_DAYS('2027-07-01')),
        PARTITION p202707 VALUES LESS THAN (TO_DAYS('2027-08-01')),
        PARTITION p202708 VALUES LESS THAN (TO_DAYS('2027-09-01')),
        PARTITION p202709 VALUES LESS THAN (TO_DAYS('2027-10-01')),
        PARTITION p202710 VALUES LESS THAN (TO_DAYS('2027-11-01')),
        PARTITION p202711 VALUES LESS THAN (TO_DAYS('2027-12-01')),
        PARTITION p202712 VALUES LESS THAN (TO_DAYS('2028-01-01')),
        PARTITION p202801 VALUES LESS THAN (TO_DAYS('2028-02-01')),
        PARTITION p202802 VALUES LESS THAN (TO_DAYS('2028-03-01')),
        PARTITION p202803 VALUES LESS THAN (TO_DAYS('2028-04-01')),
        PARTITION p202804 VALUES LESS THAN (TO_DAYS('2028-05-01')),
        PARTITION p202805 VALUES LESS THAN (TO_DAYS('2028-06-01')),
        PARTITION p202806 VALUES LESS THAN (TO_DAYS('2028-07-01')),
        PARTITION p202807 VALUES LESS THAN (TO_DAYS('2028-08-01')),
        PARTITION p202808 VALUES LESS THAN (TO_DAYS('2028-09-01')),
        PARTITION p202809 VALUES LESS THAN (TO_DAYS('2028-10-01')),
        PARTITION p202810 VALUES LESS THAN (TO_DAYS('2028-11-01')),
        PARTITION pMAX    VALUES LESS THAN MAXVALUE
    );

-- ---------------------------------------------------------------------
-- evento_uso (sql/004): ocorrido_em DATETIME(6) UTC, mesma grade mensal.
-- ---------------------------------------------------------------------
ALTER TABLE `evento_uso`
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (`id`, `ocorrido_em`)
    PARTITION BY RANGE (TO_DAYS(`ocorrido_em`)) (
        PARTITION p202610 VALUES LESS THAN (TO_DAYS('2026-11-01')),
        PARTITION p202611 VALUES LESS THAN (TO_DAYS('2026-12-01')),
        PARTITION p202612 VALUES LESS THAN (TO_DAYS('2027-01-01')),
        PARTITION p202701 VALUES LESS THAN (TO_DAYS('2027-02-01')),
        PARTITION p202702 VALUES LESS THAN (TO_DAYS('2027-03-01')),
        PARTITION p202703 VALUES LESS THAN (TO_DAYS('2027-04-01')),
        PARTITION p202704 VALUES LESS THAN (TO_DAYS('2027-05-01')),
        PARTITION p202705 VALUES LESS THAN (TO_DAYS('2027-06-01')),
        PARTITION p202706 VALUES LESS THAN (TO_DAYS('2027-07-01')),
        PARTITION p202707 VALUES LESS THAN (TO_DAYS('2027-08-01')),
        PARTITION p202708 VALUES LESS THAN (TO_DAYS('2027-09-01')),
        PARTITION p202709 VALUES LESS THAN (TO_DAYS('2027-10-01')),
        PARTITION p202710 VALUES LESS THAN (TO_DAYS('2027-11-01')),
        PARTITION p202711 VALUES LESS THAN (TO_DAYS('2027-12-01')),
        PARTITION p202712 VALUES LESS THAN (TO_DAYS('2028-01-01')),
        PARTITION p202801 VALUES LESS THAN (TO_DAYS('2028-02-01')),
        PARTITION p202802 VALUES LESS THAN (TO_DAYS('2028-03-01')),
        PARTITION p202803 VALUES LESS THAN (TO_DAYS('2028-04-01')),
        PARTITION p202804 VALUES LESS THAN (TO_DAYS('2028-05-01')),
        PARTITION p202805 VALUES LESS THAN (TO_DAYS('2028-06-01')),
        PARTITION p202806 VALUES LESS THAN (TO_DAYS('2028-07-01')),
        PARTITION p202807 VALUES LESS THAN (TO_DAYS('2028-08-01')),
        PARTITION p202808 VALUES LESS THAN (TO_DAYS('2028-09-01')),
        PARTITION p202809 VALUES LESS THAN (TO_DAYS('2028-10-01')),
        PARTITION p202810 VALUES LESS THAN (TO_DAYS('2028-11-01')),
        PARTITION pMAX    VALUES LESS THAN MAXVALUE
    );

-- =====================================================================
-- PROCEDIMENTOS ADMINISTRATIVOS (usuário ADMIN; nunca a aplicação)
--
-- 1) Criar partições futuras — a cada semestre, ou quando o db_check avisar
--    "última partição mensal termina em < 90 dias". Divide pMAX sem mover
--    as linhas dos meses já fechados (só pMAX é reorganizada; se ela já
--    tiver linhas do mês novo, elas vão para a partição certa):
--
--   ALTER TABLE evento_log REORGANIZE PARTITION pMAX INTO (
--       PARTITION p202811 VALUES LESS THAN (TO_DAYS('2028-12-01')),
--       PARTITION p202812 VALUES LESS THAN (TO_DAYS('2029-01-01')),
--       PARTITION pMAX    VALUES LESS THAN MAXVALUE);
--   ALTER TABLE evento_uso REORGANIZE PARTITION pMAX INTO (
--       PARTITION p202811 VALUES LESS THAN (TO_DAYS('2028-12-01')),
--       PARTITION p202812 VALUES LESS THAN (TO_DAYS('2029-01-01')),
--       PARTITION pMAX    VALUES LESS THAN MAXVALUE);
--
--    Conferir: SELECT TABLE_NAME, PARTITION_NAME, PARTITION_DESCRIPTION, TABLE_ROWS
--              FROM information_schema.PARTITIONS
--              WHERE TABLE_SCHEMA='area_associado' AND TABLE_NAME IN ('evento_log','evento_uso')
--              ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION;
--
-- 2) Expurgo por retenção (P-15; prazo por tabela/categoria é do jurídico,
--    P-54). Sempre: snapshot manual antes; nunca a partição do mês corrente;
--    registrar em docs/CONCLUIDO.md (tabela, partição, data, quem).
--
--    a) Mês inteiro descartável (ex.: evento_uso após 24 meses):
--         ALTER TABLE evento_uso DROP PARTITION p202610;
--
--    b) evento_log — `request` expira em 12 meses, mas `seguranca`,
--       `negocio` e `erro` não (sql/002). Antes de descartar o mês, retirar
--       a partição inteira para uma tabela de arquivo (troca de ponteiros,
--       sem copiar linha) e só então apagar, no ARQUIVO, o que expirou:
--         CREATE TABLE evento_log_arq_202610 LIKE evento_log;
--         ALTER TABLE evento_log_arq_202610 REMOVE PARTITIONING;
--         ALTER TABLE evento_log EXCHANGE PARTITION p202610
--               WITH TABLE evento_log_arq_202610;
--         DELETE FROM evento_log_arq_202610 WHERE categoria = 'request';
--         -- opcional: ALTER TABLE evento_log DROP PARTITION p202610; (fica vazia)
--       O arquivo permanece fora da tabela quente, só com as categorias de
--       guarda longa; a aplicação não o lê nem o escreve.
--
-- 3) Relatório de ocupação por mês (para a política de retenção):
--      SELECT TABLE_NAME, PARTITION_NAME, TABLE_ROWS,
--             ROUND((DATA_LENGTH+INDEX_LENGTH)/1024/1024, 1) AS mb
--      FROM information_schema.PARTITIONS
--      WHERE TABLE_SCHEMA='area_associado' AND TABLE_NAME IN ('evento_log','evento_uso')
--      ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION;
-- =====================================================================
