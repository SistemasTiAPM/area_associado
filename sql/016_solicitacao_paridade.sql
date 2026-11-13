-- =====================================================================
-- area_associado — solicitações em paridade com o App APM
-- (contrato do mcp_hub de 2026-11-13; ADR-0024; adenda às ADR-0018 e 0023).
--
-- O QUÊ
--   1. `solicitacao.tipo_servico` ganha os 15 tipos do catálogo comum com o App
--      que a área ainda não tinha (o slug é o MESMO gravado no CRM). Os tipos
--      antigos continuam: `outro` e `alteracao_cadastro` são traduzidos no
--      envio (`outros`, `alteracao_cadastral`) por `catalogo_crm.py`.
--   2. `solicitacao_mensagem`: outbox das mensagens do associado para a
--      Timeline do CRM (`solicitacao.interagir`). O `id` é o `interacao_id` do
--      hub (idempotência). SEM chave estrangeira para `solicitacao`: o pai pode
--      ter sido aberto pelo App APM e não existir na área. O texto fica só até
--      o hub confirmar (ou até a purga do que falhou): depois é NULL — a
--      conversa é lida do CRM, não daqui.
--   3. `solicitacao_leitura`: quando o associado abriu a conversa de cada
--      registro pela última vez (base do selo "Nova resposta"). No servidor
--      porque a regra 13 proíbe dado em `localStorage`.
--   4. Flag `solicitacoes_crm` (desligada): catálogo novo, lista dos dois canais
--      e conversa só aparecem com ela ligada.
--
-- PRIVILÉGIO (ADR-0004, CLAUDE.md regra 14)
--   `solicitacao_mensagem`: GRANT UPDATE só em
--     status, tentativas, proxima_em, erro_codigo, enviada_em — estado da
--       outbox com recuo, escrito pelo serviço de jobs (`enviar_mensagens`);
--     texto — purga (NULL) depois da confirmação do hub e do que falhou há
--       mais de 7 dias: o texto do associado não fica guardado na área.
--     Imutáveis para a aplicação: id, contact_id, registro_id, entidade,
--     criada_em, request_id.
--   `solicitacao_leitura`: GRANT UPDATE só em `visto_em` (INSERT ... ON
--     DUPLICATE KEY UPDATE ao abrir a conversa).
--   Sem DELETE em nenhuma. Allowlist em scripts/db_check.py.
--
-- OPERAÇÃO
--   Acrescentar valores ao FIM de um ENUM é mudança só de metadados
--   (ALGORITHM=INSTANT no MySQL 8.4): sem cópia da tabela, sem janela.
--   Enquanto não for aplicada, a flag não existe (= desligada) e a área segue
--   como na Onda 2; o job `enviar_mensagens` não roda (confere as tabelas).
--
-- REAPLICÁVEL: o MODIFY repete a mesma definição, as tabelas usam IF NOT
-- EXISTS e o INSERT da flag só atualiza a descrição (`ligada` nunca é tocada).
-- Registrar em `schema_migrations` (versao '016') como as demais.
-- =====================================================================

USE `area_associado`;

ALTER TABLE `solicitacao`
    MODIFY COLUMN `tipo_servico` ENUM(
        'alteracao_cadastro','diagnostico_marketing','submeter_trabalho',
        'mentoria_pedir','mentoria_oferecer','cartao_apm','outro',
        'declaracao_associado','cancelamento_associacao','exclusao_dados',
        -- catálogo comum com o App APM (ADR-0024)
        'duvida','segunda_via_boleto','defesa_profissional','planos_de_saude',
        'seguro_vida','seguro_vida_dit','seguro_carro','seguro_residencial',
        'seguro_viagem','seguro_pet','seguro_responsabilidade_civil',
        'assessoria_aposentadoria','contabilidade','despachante','apm_facilities'
    ) NULL;

CREATE TABLE IF NOT EXISTS `solicitacao_mensagem` (
    `id`          CHAR(36)         NOT NULL COMMENT 'UUID v4 da aplicação = interacao_id no hub (idempotência)',
    `contact_id`  CHAR(36)         NOT NULL COMMENT 'GUID do contact no CRM (ADR-0014); CPF nunca',
    `registro_id` CHAR(36)         NOT NULL COMMENT 'incident/opportunity pai no CRM (pode ter nascido no App)',
    `entidade`    ENUM('ocorrencia','oportunidade') NOT NULL,
    `texto`       VARCHAR(2000)    NULL COMMENT 'mensagem do associado; NULL depois de enviada ou purgada',
    `status`      ENUM('pendente','erro','enviada','falhou') NOT NULL DEFAULT 'pendente',
    `tentativas`  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    `proxima_em`  DATETIME(6)      NOT NULL COMMENT 'UTC — não tentar antes (recuo; limite do titular)',
    `erro_codigo` VARCHAR(48)      NULL COMMENT 'código curto do último erro (nunca texto de terceiro)',
    `criada_em`   DATETIME(6)      NOT NULL COMMENT 'UTC',
    `enviada_em`  DATETIME(6)      NULL COMMENT 'UTC — confirmação do hub',
    `request_id`  CHAR(16)         NULL,
    PRIMARY KEY (`id`),
    KEY `ix_sol_mensagem_fila` (`status`, `proxima_em`, `criada_em`),
    KEY `ix_sol_mensagem_conversa` (`contact_id`, `registro_id`, `criada_em`),
    KEY `ix_sol_mensagem_contato` (`contact_id`, `criada_em`),
    CONSTRAINT `ck_sol_mensagem_id` CHECK (
        REGEXP_LIKE(`id`, '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_sol_mensagem_guids` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
        AND REGEXP_LIKE(`registro_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    -- Texto presente enquanto há o que enviar; enviada = sem texto guardado.
    CONSTRAINT `ck_sol_mensagem_texto` CHECK (
        (`status` IN ('pendente', 'erro') AND `texto` IS NOT NULL AND CHAR_LENGTH(TRIM(`texto`)) >= 2)
        OR (`status` = 'enviada' AND `texto` IS NULL AND `enviada_em` IS NOT NULL)
        OR (`status` = 'falhou')
    ),
    CONSTRAINT `ck_sol_mensagem_sem_cpf` CHECK (
        `texto` IS NULL OR NOT REGEXP_LIKE(`texto`,
            '(^|[^0-9a-fA-F])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-fA-F]|$)')
    ),
    CONSTRAINT `ck_sol_mensagem_erro` CHECK (
        `erro_codigo` IS NULL OR REGEXP_LIKE(`erro_codigo`, '^[a-z][a-z0-9_]{0,47}$', 'c')
    ),
    CONSTRAINT `ck_sol_mensagem_request_id` CHECK (
        `request_id` IS NULL OR REGEXP_LIKE(`request_id`, '^[0-9a-f]{16}$', 'c')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `solicitacao_leitura` (
    `contact_id`  CHAR(36)    NOT NULL,
    `registro_id` CHAR(36)    NOT NULL COMMENT 'id da solicitação (área) = registro no CRM',
    `visto_em`    DATETIME(6) NOT NULL COMMENT 'UTC — última abertura da conversa pelo associado',
    PRIMARY KEY (`contact_id`, `registro_id`),
    CONSTRAINT `ck_sol_leitura_guids` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
        AND REGEXP_LIKE(`registro_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

GRANT UPDATE (`status`, `tentativas`, `proxima_em`, `erro_codigo`, `enviada_em`, `texto`)
    ON `area_associado`.`solicitacao_mensagem` TO 'apm_area'@'%';
GRANT UPDATE (`visto_em`)
    ON `area_associado`.`solicitacao_leitura` TO 'apm_area'@'%';
FLUSH PRIVILEGES;

INSERT INTO `feature_flag` (`chave`, `ligada`, `descricao`) VALUES
    ('solicitacoes_crm', 0, 'Paridade com o App APM: catálogo comum, lista dos dois canais e conversa com a Central (ADR-0024) — aguarda grants no hub e ensaio')
AS novo
ON DUPLICATE KEY UPDATE `descricao` = novo.`descricao`;

-- Conferência:
--   SHOW CREATE TABLE solicitacao\G            -- tipo_servico com 25 valores
--   SHOW GRANTS FOR 'apm_area'@'%';            -- UPDATE por coluna nas duas tabelas novas
--   SELECT chave, ligada FROM feature_flag WHERE chave = 'solicitacoes_crm';
--   docker compose exec area-associado python -m scripts.db_check
