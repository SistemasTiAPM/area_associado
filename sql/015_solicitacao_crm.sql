-- =====================================================================
-- area_associado — espelho das solicitações no CRM por `incident`/`opportunity`
-- (P-06 resolvida pelo mcp_hub em 2026-11-04; ADR-0023; adenda à ADR-0018).
--
-- O QUÊ
--   Em `solicitacao` (sql/010):
--   - `crm_entidade`      : `ocorrencia` (incident) ou `oportunidade` (opportunity),
--                           o que o catálogo da área mandou criar. Gravada junto
--                           com `crm_id` (CHECK `ck_solicitacao_crm_par`).
--   - `crm_protocolo`     : `ticketnumber` da ocorrência (`CAS-######-XXXXXX`),
--                           mostrado ao associado. NULL em oportunidade.
--   - `crm_estado`/`crm_status`: último `statecode`/`statuscode` VISTOS no CRM
--                           (criação ou `solicitacao.listar`). A sincronização só
--                           transita quando o par MUDA: o CRM continua em
--                           "Aguardando detalhes" depois de o associado agir na
--                           área, e reagir ao estado (não à mudança) faria o
--                           pedido oscilar a cada ciclo.
--   - `crm_consultado_em` : última consulta do CRM para este pedido; a fila da
--                           sincronização (cadência por contato, JOBS_SYNC_INTERVALO_H).
--   - `crm_sync` ganha `retido`: transição local que o CRM não pode receber
--                           (o hub não tem ferramenta de status) ou tipo sem
--                           destino no catálogo. Fica parada, sem tentativa, com
--                           aviso no evento_log; reprocessável quando houver
--                           ferramenta (`WHERE crm_sync = 'retido'`).
--   - `crm_id` passa a ser o PRÓPRIO `id` (o hub usa o `registro_id` da área
--     como chave primária no CRM): CHECK `ck_solicitacao_crm_id_igual`.
--
-- PRIVILÉGIO (ADR-0004, CLAUDE.md regra 14)
--   GRANT UPDATE só nas cinco colunas novas, escritas pelo serviço de jobs
--   (espelho grava entidade/protocolo/estado; sincronização grava estado e
--   `crm_consultado_em`). Nada muda no resto da tabela; DELETE continua
--   inexistente. `scripts/db_check.py` conta a tabela (já na allowlist).
--
-- COMO APLICAR (usuário ADMIN do RDS; a aplicação não tem DDL)
--   1. snapshot manual do RDS (docs/OPERACAO.md §6);
--   2. mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--        area_associado < sql/015_solicitacao_crm.sql
--   3. registrar o sha256 em schema_migrations (docs/PROVISIONAMENTO.md §2.6);
--   4. docker compose exec area-associado python -m scripts.db_check
--   Os CHECKs novos obrigam ALGORITHM=COPY: a tabela é reconstruída e as
--   escritas em `solicitacao` esperam o lock durante a cópia (segundos com o
--   volume atual). Janela de pouco tráfego.
--   Enquanto não for aplicada, o espelho fica parado (o job confere as colunas
--   no information_schema) e a API devolve `protocolo: null`.
--
-- NÃO REAPLICÁVEL: a segunda execução falha inteira, sem alterar nada
-- (coluna e CHECK duplicados). A proteção é o registro em `schema_migrations`
-- (versao '015').
--
-- Ensaiada em MySQL 8.4 descartável em 2026-11-04 (000→015 em ordem): ver o
-- registro em docs/CONCLUIDO.md.
-- =====================================================================

USE `area_associado`;

ALTER TABLE `solicitacao`
    MODIFY COLUMN `crm_id` CHAR(36) NULL
        COMMENT 'incidentid/opportunityid no CRM = o próprio id (registro_id do hub)',
    MODIFY COLUMN `crm_sync` ENUM('pendente','ok','erro','falhou','retido') NOT NULL DEFAULT 'pendente',
    ADD COLUMN `crm_entidade` ENUM('ocorrencia','oportunidade') NULL
        COMMENT 'entidade criada no CRM pelo catálogo da área'
        AFTER `crm_id`,
    ADD COLUMN `crm_protocolo` VARCHAR(32) NULL
        COMMENT 'ticketnumber da ocorrência (mostrado ao associado); NULL em oportunidade'
        AFTER `crm_entidade`,
    ADD COLUMN `crm_estado` TINYINT UNSIGNED NULL
        COMMENT 'último statecode visto no CRM'
        AFTER `crm_protocolo`,
    ADD COLUMN `crm_status` INT UNSIGNED NULL
        COMMENT 'último statuscode visto no CRM'
        AFTER `crm_estado`,
    ADD COLUMN `crm_consultado_em` DATETIME(6) NULL
        COMMENT 'UTC — última leitura do CRM (criação ou listar)'
        AFTER `crm_status`,
    ADD KEY `ix_solicitacao_crm_consulta` (`status`, `crm_consultado_em`),
    ADD CONSTRAINT `ck_solicitacao_crm_id_igual` CHECK (`crm_id` IS NULL OR `crm_id` = `id`),
    -- Criação confirmada grava id, entidade e estado juntos.
    ADD CONSTRAINT `ck_solicitacao_crm_par` CHECK (
        (`crm_id` IS NULL) = (`crm_entidade` IS NULL)
        AND (`crm_estado` IS NULL) = (`crm_status` IS NULL)
        AND (`crm_estado` IS NULL OR `crm_id` IS NOT NULL)
    ),
    ADD CONSTRAINT `ck_solicitacao_crm_protocolo` CHECK (
        `crm_protocolo` IS NULL OR (
            `crm_entidade` = 'ocorrencia'
            AND REGEXP_LIKE(`crm_protocolo`, '^[A-Z]{2,5}-[0-9]{3,10}-[A-Z0-9]{3,10}$', 'c')
        )
    );

GRANT UPDATE (`crm_entidade`, `crm_protocolo`, `crm_estado`, `crm_status`, `crm_consultado_em`)
    ON `area_associado`.`solicitacao` TO 'apm_area'@'%';

-- Conferência:
--   SHOW CREATE TABLE solicitacao\G
--   SHOW GRANTS FOR 'apm_area'@'%';   -- UPDATE (…, crm_entidade, crm_protocolo, crm_estado, crm_status, crm_consultado_em)
--   docker compose exec area-associado python -m scripts.db_check
