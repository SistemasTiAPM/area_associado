-- =====================================================================
-- area_associado — P13 Perfil, preferências e privacidade (Onda 3, rodada 1;
-- spec v2 §6 P13 e §11.6; levantamento TI-25; ADR-0025 e ADR-0026).
--
-- O QUÊ
--   1. `consentimento_texto`: texto de cada finalidade, POR VERSÃO. Uma versão
--      nunca muda de texto: texto novo = versão nova (linha nova). A vigente é
--      a de maior `vigente_desde` já alcançado. Semente `v0` PROVISÓRIA: os
--      textos definitivos são do jurídico (P-54); até lá a flag
--      `lgpd_consentimentos` fica desligada.
--   2. `consentimento`: trilha append-only por (associado, finalidade, canal).
--      Conceder e retirar são linhas novas; o estado atual é a última linha
--      (`vw_consentimento_atual`). Cada linha aponta a versão do texto que a
--      pessoa viu (chave estrangeira).
--   3. `perfil_declarado`: o que o associado DIZ de si (como prefere ser
--      chamado, área de atuação, temas, canal preferido e frequência, tamanho
--      de fonte) — REQUISITOS §9.1.
--      Não é cadastro: o cadastro é do CRM (`associado_perfil` é cache dele).
--      O tamanho de fonte vive aqui porque a regra 13 proíbe `localStorage`
--      para estado (DEC-27).
--   4. `pergunta_perfil`: perguntas do perfil progressivo que o associado
--      PULOU ("uma pergunta por visita", P13). Respondida não precisa de linha:
--      a resposta está em `perfil_declarado`.
--   5. `titular_pedido`: pedidos do titular (LGPD) — exportação e exclusão —
--      com protocolo. A exportação nasce concluída (é síncrona) e serve de
--      contagem para o limite de 1 a cada 7 dias. A exclusão nasce registrada,
--      ligada à solicitação `exclusao_dados` que o associado acompanha; quem a
--      conclui é o operador, por `scripts/anonimizar_titular.sql` (ADR-0025).
--   6. `associado.anonimizado_em`: marca a linha que o operador anonimizou.
--   7. Flag `perfil_preferencias` (desligada): preferências, perfil
--      progressivo e tamanho de fonte.
--
-- PRIVILÉGIO (ADR-0004, CLAUDE.md regra 14)
--   `consentimento_texto`, `consentimento`, `titular_pedido`: SEM UPDATE para a
--     aplicação. Consentimento é prova; pedido do titular só muda de estado
--     pelo operador (hoje) ou pelo backoffice (`apm_area_bo`, Onda 6).
--   `perfil_declarado`: GRANT UPDATE só em
--     tratamento, atuacao, temas, canal_preferido, frequencia, fonte,
--     atualizado_em —
--     é preferência editável pelo próprio associado. Imutáveis: contact_id,
--     criado_em.
--   `pergunta_perfil`: GRANT UPDATE só em `pulada_em` e `vezes` (INSERT ... ON
--     DUPLICATE KEY UPDATE ao pular de novo).
--   Sem DELETE em nenhuma. Allowlist em scripts/db_check.py.
--
-- COMO APLICAR (usuário ADMIN do RDS; a aplicação não tem DDL)
--   1. mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--        area_associado < sql/017_perfil_privacidade.sql
--   2. registrar o sha256 em schema_migrations (docs/PROVISIONAMENTO.md §2.6);
--   3. docker compose exec area-associado python -m scripts.db_check
--   Enquanto não for aplicada, as rotas de P13 respondem 503
--   `recurso_indisponivel` (`app/prontidao.py`, recurso `privacidade`) e as
--   flags não existem (= desligadas).
--   O ALTER de `associado` é ALGORITHM=INSTANT (só metadados, sem janela).
--
-- REAPLICÁVEL ATÉ O ÚLTIMO COMANDO: tabelas com IF NOT EXISTS, view com OR
-- REPLACE, sementes que não alteram linha existente, GRANT idempotente. O
-- ALTER final falha na segunda execução (coluna duplicada), sem efeito — por
-- isso ele é o último comando. Registrar em `schema_migrations` (versao '017').
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `consentimento_texto` (
    `finalidade`    VARCHAR(32)   NOT NULL COMMENT 'slug da finalidade (catálogo em app/dominio/consentimento.py)',
    `versao`        VARCHAR(16)   NOT NULL COMMENT 'identificador da versão do texto (v0, v1, 2027-01...)',
    `titulo`        VARCHAR(120)  NOT NULL,
    `texto`         VARCHAR(2000) NOT NULL COMMENT 'texto exibido ao associado; imutável por versão',
    `vigente_desde` DATETIME(6)   NOT NULL COMMENT 'UTC — a versão vigente é a de maior data já alcançada',
    `criado_em`     DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`finalidade`, `versao`),
    KEY `ix_consent_texto_vigencia` (`finalidade`, `vigente_desde`),
    CONSTRAINT `ck_consent_texto_finalidade` CHECK (REGEXP_LIKE(`finalidade`, '^[a-z][a-z0-9_]{1,31}$', 'c')),
    CONSTRAINT `ck_consent_texto_versao` CHECK (REGEXP_LIKE(`versao`, '^[a-z0-9][a-z0-9._-]{0,15}$', 'c')),
    CONSTRAINT `ck_consent_texto_conteudo` CHECK (
        CHAR_LENGTH(TRIM(`titulo`)) >= 3 AND CHAR_LENGTH(TRIM(`texto`)) >= 20
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `consentimento` (
    `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `contact_id`    CHAR(36)        NOT NULL COMMENT 'GUID do contact no CRM (ADR-0014); CPF nunca',
    `sub_hash`      CHAR(64)        NULL     COMMENT 'HMAC do sub (LOG_HASH_KEY), correlação com evento_log',
    `finalidade`    VARCHAR(32)     NOT NULL,
    `canal`         ENUM('email','whatsapp','sms','push','telefone') NOT NULL,
    `valor`         ENUM('concedido','retirado') NOT NULL,
    `versao`        VARCHAR(16)     NOT NULL COMMENT 'versão do texto que a pessoa viu ao decidir',
    `origem`        ENUM('perfil','onboarding','backoffice','importacao') NOT NULL DEFAULT 'perfil',
    `request_id`    CHAR(16)        NULL,
    `registrado_em` DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC',
    PRIMARY KEY (`id`),
    KEY `ix_consentimento_atual` (`contact_id`, `finalidade`, `canal`, `id`),
    KEY `ix_consentimento_registrado` (`registrado_em`),
    CONSTRAINT `fk_consentimento_texto` FOREIGN KEY (`finalidade`, `versao`)
        REFERENCES `consentimento_texto` (`finalidade`, `versao`),
    CONSTRAINT `ck_consentimento_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_consentimento_sub_hash` CHECK (`sub_hash` IS NULL OR REGEXP_LIKE(`sub_hash`, '^[0-9a-f]{64}$', 'c')),
    CONSTRAINT `ck_consentimento_request_id` CHECK (
        `request_id` IS NULL OR REGEXP_LIKE(`request_id`, '^[0-9a-f]{16}$', 'c')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Estado atual = última linha de cada (associado, finalidade, canal).
-- SQL SECURITY INVOKER: a view não empresta o privilégio de quem a criou.
CREATE OR REPLACE SQL SECURITY INVOKER VIEW `vw_consentimento_atual` AS
    SELECT c.`contact_id`, c.`finalidade`, c.`canal`, c.`valor`, c.`versao`, c.`origem`, c.`registrado_em`
      FROM `consentimento` c
      JOIN (SELECT MAX(`id`) AS `id` FROM `consentimento` GROUP BY `contact_id`, `finalidade`, `canal`) u
        ON u.`id` = c.`id`;

CREATE TABLE IF NOT EXISTS `perfil_declarado` (
    `contact_id`    CHAR(36)    NOT NULL,
    `tratamento`    VARCHAR(40) NULL COMMENT 'como prefere ser chamado (DEC-26); NULL = saudação neutra',
    `atuacao`       JSON        NULL COMMENT 'lista de slugs (catálogo em app/dominio/preferencias.py)',
    `temas`         JSON        NULL COMMENT 'lista de slugs de temas de interesse',
    `canal_preferido` ENUM('email','whatsapp','sms') NULL COMMENT 'a aplicação só oferece os canais que existem (regra 19)',
    `frequencia`    ENUM('normal','minima') NULL COMMENT 'normal = todas as novidades; minima = só o essencial',
    `fonte`         ENUM('padrao','grande','maior') NOT NULL DEFAULT 'padrao' COMMENT 'tamanho de fonte (DEC-27)',
    `criado_em`     DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `atualizado_em` DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`contact_id`),
    CONSTRAINT `ck_perfil_decl_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    -- Nome de tratamento: sem dígito (barra CPF e telefone), sem marcação, sem controle.
    CONSTRAINT `ck_perfil_decl_tratamento` CHECK (
        `tratamento` IS NULL OR (
            CHAR_LENGTH(TRIM(`tratamento`)) >= 2
            AND NOT REGEXP_LIKE(`tratamento`, '[0-9<>&"[:cntrl:]]')
        )
    ),
    CONSTRAINT `ck_perfil_decl_listas` CHECK (
        (`atuacao` IS NULL OR (JSON_TYPE(`atuacao`) = 'ARRAY' AND JSON_LENGTH(`atuacao`) <= 8
                               AND LENGTH(CAST(`atuacao` AS CHAR)) <= 400))
        AND (`temas` IS NULL OR (JSON_TYPE(`temas`) = 'ARRAY' AND JSON_LENGTH(`temas`) <= 12
                                 AND LENGTH(CAST(`temas` AS CHAR)) <= 600))
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `pergunta_perfil` (
    `contact_id` CHAR(36)         NOT NULL,
    `chave`      VARCHAR(32)      NOT NULL COMMENT 'pergunta do perfil progressivo (catálogo no código)',
    `pulada_em`  DATETIME(6)      NOT NULL COMMENT 'UTC — última vez que o associado pulou',
    `vezes`      TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT 'quantas vezes pulou; no teto a pergunta para de aparecer',
    PRIMARY KEY (`contact_id`, `chave`),
    CONSTRAINT `ck_pergunta_perfil_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_pergunta_perfil_chave` CHECK (REGEXP_LIKE(`chave`, '^[a-z][a-z0-9_]{1,31}$', 'c')),
    CONSTRAINT `ck_pergunta_perfil_vezes` CHECK (`vezes` BETWEEN 1 AND 50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `titular_pedido` (
    `id`                 CHAR(36)     NOT NULL COMMENT 'UUID v4 gerado pela aplicação',
    `protocolo`          CHAR(20)     NOT NULL COMMENT 'LGPD-AAAAMMDD-XXXXXX, informado ao associado',
    `contact_id`         CHAR(36)     NOT NULL COMMENT 'GUID do contact no CRM (ADR-0014); CPF nunca',
    `sub_hash`           CHAR(64)     NOT NULL COMMENT 'HMAC do sub (LOG_HASH_KEY), correlação com evento_log',
    `tipo`               ENUM('exportacao','exclusao') NOT NULL,
    `status`             ENUM('registrado','em_analise','concluido','recusado','cancelado') NOT NULL DEFAULT 'registrado',
    `solicitacao_id`     CHAR(36)     NULL COMMENT 'solicitação exclusao_dados que o associado acompanha',
    `chave_idempotencia` CHAR(36)     NULL COMMENT 'UUID gerado no cliente; único por associado',
    `criado_em`          DATETIME(6)  NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC',
    `concluido_em`       DATETIME(6)  NULL COMMENT 'UTC — fechamento (concluído, recusado ou cancelado)',
    `observacao`         VARCHAR(500) NULL COMMENT 'interna (operador/backoffice); nunca exibida ao associado',
    `request_id`         CHAR(16)     NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_titular_pedido_protocolo` (`protocolo`),
    UNIQUE KEY `uq_titular_pedido_solicitacao` (`solicitacao_id`),
    UNIQUE KEY `uq_titular_pedido_idempotencia` (`contact_id`, `chave_idempotencia`),
    KEY `ix_titular_pedido_contato` (`contact_id`, `tipo`, `criado_em`),
    KEY `ix_titular_pedido_fila` (`tipo`, `status`, `criado_em`),
    CONSTRAINT `ck_titular_pedido_id` CHECK (
        REGEXP_LIKE(`id`, '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_titular_pedido_protocolo` CHECK (
        REGEXP_LIKE(`protocolo`, '^LGPD-20[0-9]{6}-[A-Z2-7]{6}$', 'c')
    ),
    CONSTRAINT `ck_titular_pedido_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_titular_pedido_sub_hash` CHECK (REGEXP_LIKE(`sub_hash`, '^[0-9a-f]{64}$', 'c')),
    CONSTRAINT `ck_titular_pedido_chave` CHECK (
        `chave_idempotencia` IS NULL OR
        REGEXP_LIKE(`chave_idempotencia`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    -- Exclusão sempre ligada à solicitação que o associado acompanha; exportação nunca.
    CONSTRAINT `ck_titular_pedido_solicitacao` CHECK (
        (`tipo` = 'exclusao') = (`solicitacao_id` IS NOT NULL)
        AND (`solicitacao_id` IS NULL OR
             REGEXP_LIKE(`solicitacao_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c'))
    ),
    CONSTRAINT `ck_titular_pedido_fechamento` CHECK (
        (`concluido_em` IS NOT NULL) = (`status` IN ('concluido', 'recusado', 'cancelado'))
    ),
    CONSTRAINT `ck_titular_pedido_request_id` CHECK (
        `request_id` IS NULL OR REGEXP_LIKE(`request_id`, '^[0-9a-f]{16}$', 'c')
    ),
    CONSTRAINT `ck_titular_pedido_observacao_sem_cpf` CHECK (
        `observacao` IS NULL OR NOT REGEXP_LIKE(`observacao`,
            '(^|[^0-9a-fA-F])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-fA-F]|$)')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE por coluna (ADR-0004). `perfil_declarado`: preferência editável
-- pelo próprio associado. `pergunta_perfil`: contar a pergunta pulada.
-- `consentimento*` e `titular_pedido` ficam SEM UPDATE (ver cabeçalho).
-- ---------------------------------------------------------------------
GRANT UPDATE (`tratamento`, `atuacao`, `temas`, `canal_preferido`, `frequencia`, `fonte`, `atualizado_em`)
    ON `area_associado`.`perfil_declarado` TO 'apm_area'@'%';
GRANT UPDATE (`pulada_em`, `vezes`)
    ON `area_associado`.`pergunta_perfil` TO 'apm_area'@'%';
FLUSH PRIVILEGES;

-- Textos PROVISÓRIOS (v0). Finalidades da spec v2 §11.6: ofertas de parceiros
-- e WhatsApp de relacionamento. Mensagem transacional não pede consentimento
-- (execução do contrato de associação). Linha existente nunca é alterada.
INSERT INTO `consentimento_texto` (`finalidade`, `versao`, `titulo`, `texto`, `vigente_desde`) VALUES
    ('ofertas_parceiros', 'v0', 'Ofertas de parceiros por e-mail',
     'Autorizo a APM a me enviar, por e-mail, ofertas e condições especiais de empresas parceiras do Clube de benefícios. A APM não entrega meus dados de contato aos parceiros: a mensagem sai da própria APM. Posso retirar esta autorização a qualquer momento, aqui no perfil, sem afetar minha associação nem os avisos sobre meus pedidos e pagamentos.',
     '2026-11-19 00:00:00.000000'),
    ('whatsapp_relacionamento', 'v0', 'Mensagens de relacionamento por WhatsApp',
     'Autorizo a APM a me enviar, por WhatsApp, mensagens de relacionamento: novidades, lembretes de benefícios e convites para eventos. Posso retirar esta autorização a qualquer momento, aqui no perfil, sem afetar minha associação nem os avisos sobre meus pedidos e pagamentos.',
     '2026-11-19 00:00:00.000000')
AS novo
ON DUPLICATE KEY UPDATE `titulo` = `consentimento_texto`.`titulo`;

INSERT INTO `feature_flag` (`chave`, `ligada`, `descricao`) VALUES
    ('perfil_preferencias', 0, 'P13 preferências, perfil progressivo e tamanho de fonte (ADR-0026) — ligar depois de conferir pela tela')
AS novo
ON DUPLICATE KEY UPDATE `descricao` = novo.`descricao`;

-- ÚLTIMO COMANDO (não reaplicável): marca da anonimização do titular (ADR-0025).
ALTER TABLE `associado`
    ADD COLUMN `anonimizado_em` DATETIME(6) NULL
        COMMENT 'UTC — linha anonimizada pelo operador a pedido do titular (scripts/anonimizar_titular.sql)',
    ALGORITHM=INSTANT;

-- Conferência:
--   SHOW GRANTS FOR 'apm_area'@'%';      -- UPDATE por coluna em perfil_declarado e pergunta_perfil
--   SELECT finalidade, versao, vigente_desde FROM consentimento_texto;
--   SELECT chave, ligada FROM feature_flag WHERE chave IN ('perfil_preferencias', 'lgpd_consentimentos');
--   docker compose exec area-associado python -m scripts.db_check
