-- =====================================================================
-- area_associado — Ajuda (FAQ), textos do sistema e parâmetros de negócio
-- (TI-20; REQUISITOS §3.15 RF-AJ-01/02, §6.2 linha 013; spec v2 B07/B13;
-- ADR-0022 item 2 e item 6).
--
-- O QUÊ
--   `faq`           perguntas frequentes da P14 (só as `publicada=1` chegam
--                   ao associado; despublicar = UPDATE do operador, sem deploy).
--   `texto_sistema` textos editáveis da interface (estados vazios, avisos)
--                   com vigência — texto novo = linha nova (chave, início).
--   `parametro`     parâmetros de negócio lidos em tempo de execução: prazos
--                   de avaliação, de retorno padrão, janela de arrependimento
--                   do cancelamento, horário e telefone da Central.
--
-- PRIVILÉGIOS
--   SÓ LEITURA para `apm_area` (ADR-0022 item 2): nenhum GRANT aqui. Mudar um
--   valor é ato do operador por SQL (ou do `apm_area_bo`, quando o backoffice
--   existir — sql/020) com registro em `backoffice_auditoria`. Observação: o
--   `INSERT` do schema (sql/000) alcança estas tabelas, mas sem UPDATE a
--   aplicação não consegue alterar linha existente — e toda chave que o código
--   lê nasce semeada aqui, então um INSERT indevido não muda valor em uso.
--   O código não insere nestas tabelas.
--
-- SEED
--   `parametro`: avaliacao_prazo_dias=30 (DEC-22), prazo_retorno_padrao_dias=10,
--   cancelamento_janela_horas=24, central_horario='' e central_telefone=''
--   (vazios até P-44: vazio = o bloco some da tela). Reexecução atualiza só
--   `descricao` e `tipo` — NUNCA `valor`, para não desfazer o que o operador
--   ajustou. FAQ sem seed: o conteúdo é da P-44.
--
-- COMO APLICAR (usuário ADMIN do RDS)
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--     area_associado < sql/013_ajuda_parametro.sql
--   registrar o sha256 (docs/PROVISIONAMENTO.md §2.5) e rodar o db_check.
--   Mudar um parâmetro (vale em até 60 s — cache por processo):
--     UPDATE parametro SET valor = '(11) 3188-6200' WHERE chave = 'central_telefone';
--   Publicar uma pergunta:
--     INSERT INTO faq (categoria, pergunta, resposta, ordem, publicada)
--     VALUES ('carteirinha', '...?', '...', 10, 1);
--
-- REAPLICÁVEL: sim (`CREATE TABLE IF NOT EXISTS`; seed com ON DUPLICATE KEY
--   que não toca `valor`).
--
-- Ensaiada em MySQL 8.4 descartável (`mysql-ensaio-a`) em 2026-10-30.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `faq` (
    `id`            INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    `categoria`     VARCHAR(32)       NOT NULL COMMENT 'código (slug); rótulo em app/dominio/ajuda.py',
    `pergunta`      VARCHAR(255)      NOT NULL,
    `resposta`      TEXT              NOT NULL COMMENT 'texto simples (sem HTML); a SPA não interpreta marcação',
    `ordem`         SMALLINT UNSIGNED NOT NULL DEFAULT 100,
    `publicada`     TINYINT(1)        NOT NULL DEFAULT 0,
    `criada_em`     DATETIME(6)       NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `atualizada_em` DATETIME(6)       NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`id`),
    KEY `ix_faq_publicada` (`publicada`, `categoria`, `ordem`),
    CONSTRAINT `ck_faq_categoria` CHECK (REGEXP_LIKE(`categoria`, '^[a-z][a-z0-9_]{1,31}$', 'c')),
    CONSTRAINT `ck_faq_publicada` CHECK (`publicada` IN (0, 1)),
    CONSTRAINT `ck_faq_tamanhos` CHECK (
        CHAR_LENGTH(TRIM(`pergunta`)) > 0 AND CHAR_LENGTH(TRIM(`resposta`)) > 0 AND CHAR_LENGTH(`resposta`) <= 4000
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `texto_sistema` (
    `chave`           VARCHAR(64)   NOT NULL,
    `vigencia_inicio` DATETIME(6)   NOT NULL COMMENT 'UTC',
    `vigencia_fim`    DATETIME(6)   NULL     COMMENT 'UTC; NULL = sem fim',
    `texto`           VARCHAR(2000) NOT NULL,
    `criado_em`       DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`chave`, `vigencia_inicio`),
    CONSTRAINT `ck_texto_sistema_chave` CHECK (REGEXP_LIKE(`chave`, '^[a-z][a-z0-9_.]{1,63}$', 'c')),
    CONSTRAINT `ck_texto_sistema_vigencia` CHECK (`vigencia_fim` IS NULL OR `vigencia_fim` > `vigencia_inicio`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `parametro` (
    `chave`         VARCHAR(48)  NOT NULL,
    `valor`         VARCHAR(255) NOT NULL DEFAULT '',
    `tipo`          ENUM('int','decimal','bool','texto') NOT NULL,
    `descricao`     VARCHAR(255) NOT NULL,
    `atualizado_em` DATETIME(6)  NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`chave`),
    CONSTRAINT `ck_parametro_chave` CHECK (REGEXP_LIKE(`chave`, '^[a-z][a-z0-9_]{1,47}$', 'c')),
    -- Valor coerente com o tipo: o código confia no formato (e ainda valida).
    CONSTRAINT `ck_parametro_valor` CHECK (
        (`tipo` = 'int'     AND REGEXP_LIKE(`valor`, '^-?[0-9]{1,9}$', 'c')) OR
        (`tipo` = 'decimal' AND REGEXP_LIKE(`valor`, '^-?[0-9]{1,12}([.][0-9]{1,6})?$', 'c')) OR
        (`tipo` = 'bool'    AND `valor` IN ('0', '1')) OR
        (`tipo` = 'texto')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `parametro` (`chave`, `valor`, `tipo`, `descricao`) VALUES
    ('avaliacao_prazo_dias',      '30', 'int',   'Dias após a conclusão em que o associado pode avaliar a solicitação (DEC-22, RF-SO-10)'),
    ('prazo_retorno_padrao_dias', '10', 'int',   'Prazo de retorno copiado na criação quando não há parceiro/benefício (RF-SO-09)'),
    ('cancelamento_janela_horas', '24', 'int',   'Janela de arrependimento do pedido de cancelamento antes do espelho no CRM (RF-AJ-04)'),
    ('central_horario',           '',   'texto', 'Horário de atendimento da Central exibido na Ajuda; vazio = não exibe (P-44)'),
    ('central_telefone',          '',   'texto', 'Telefone da Central (DDD + número); vazio = não exibe (P-44)')
AS novo
ON DUPLICATE KEY UPDATE `descricao` = novo.`descricao`, `tipo` = novo.`tipo`;

-- Conferência:
--   SELECT chave, valor, tipo FROM parametro ORDER BY chave;   -- 5 linhas
--   SHOW GRANTS FOR 'apm_area'@'%';                             -- nada novo
