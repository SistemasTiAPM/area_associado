-- =====================================================================
-- area_associado — comunicação produzida pela área: outbox de gatilhos,
-- log de envios, supressões, notificações no app e fila de ligações da
-- Central (TI-18 produção; REQUISITOS §3.16 RF-NO-04, §3.17 RF-CM-01..03,
-- §6.2 linha 012; spec v2 §12; ADR-0004, ADR-0014, ADR-0021).
--
-- O QUÊ
--   `comunicacao_evento`    OUTBOX: um gatilho A01..A20 por (associado,
--                           referência, canal, destinatário), gravado NA MESMA
--                           TRANSAÇÃO da transição de negócio que o causou;
--                           consumido pelo serviço de jobs (envio ao SMTP da
--                           área e, com a flag `comunicacao_outbox`, ao RD).
--                           Sem texto de mensagem e sem e-mail: o job monta o
--                           texto do template e o RD resolve o destinatário
--                           por `cf_apm_contactid`.
--   `comunicacao_envio`     log append-only do que saiu e do retorno
--                           (enviado, entregue, aberto, clicado, falha).
--   `comunicacao_supressao` log append-only de por que algo NÃO saiu.
--   `notificacao`           P15 no app (tabela nasce na Fase 3; API e tela
--                           com a flag `notificacoes`, F2).
--   `fila_ligacao`          pedidos de ligação da Central: segundo vencimento
--                           do prazo (sem_retorno_2) e "quero conversar" do
--                           pedido de cancelamento.
--
-- DECISÃO SOBRE `fila_ligacao` (pedida pelo plano da Onda 2): a aplicação
--   (`apm_area`) só INSERE — o pedido de ligação nasce do job ou do pedido
--   de cancelamento e nunca é mudado pela área do associado. O resultado da
--   ligação (status, quem atendeu, quando) é ato do atendimento: UPDATE
--   concedido ao `apm_area_bo` na migração do backoffice (ADR-0022, sql/020)
--   e, até lá, ato do operador por SQL. Por isso NENHUM grant aqui para ela.
--
-- PRIVILÉGIOS (ADR-0004; UPDATE por coluna, DELETE nunca)
--   `comunicacao_evento`: UPDATE só nas colunas de estado da entrega (job).
--   `notificacao`:        UPDATE só em `lida_em` (RF-NO-02).
--   `comunicacao_envio`, `comunicacao_supressao`, `fila_ligacao`: só INSERT
--   (SELECT, INSERT do schema, sql/000).
--
-- PII: nenhuma coluna guarda e-mail, telefone, CPF ou texto de marketing.
--   Título e corpo da notificação são curtos, escritos pela aplicação a
--   partir de rótulos fixos, sem dado de terceiro; CHECK anti-CPF em todo
--   texto. `link` só caminho relativo da própria área.
--
-- COMO APLICAR (usuário ADMIN do RDS)
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--     area_associado < sql/012_comunicacao_notificacao.sql
--   registrar o sha256 (docs/PROVISIONAMENTO.md §2.5) e rodar o db_check.
--   Ordem: depois da 010 (não há FOREIGN KEY entre elas, mas a criação de
--   solicitação só fica pronta com as duas — app/prontidao.py).
--
-- REAPLICÁVEL: sim (`CREATE TABLE IF NOT EXISTS`, GRANT idempotente); não
--   altera tabela existente.
--
-- PARTIÇÃO: `comunicacao_envio` nasce com PK `(id, ocorrido_em)` e sem
--   FOREIGN KEY, para poder ser particionada por mês (molde sql/008) quando
--   o envio ao RD existir (3b, TI-53). Até lá o volume é o dos transacionais.
--
-- Ensaiada em MySQL 8.4 descartável (`mysql-ensaio-a`) em 2026-10-30.
-- =====================================================================

USE `area_associado`;

CREATE TABLE IF NOT EXISTS `comunicacao_evento` (
    `id`                   BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `gatilho`              ENUM('A01','A02','A03','A04','A05','A06','A07','A08','A09','A10',
                                'A11','A12','A13','A14','A15','A16','A17','A18','A19','A20') NOT NULL,
    `contact_id`           CHAR(36)         NOT NULL COMMENT 'associado a quem o fato se refere (ADR-0014)',
    `referencia_tipo`      ENUM('solicitacao','beneficio','evento','associado','fatura','trilha') NOT NULL,
    `referencia_id`        VARCHAR(64)      NOT NULL COMMENT 'id da causa; com o gatilho, impede disparo duplo',
    `canal`                ENUM('email','rd','app','interno') NOT NULL,
    `destinatario`         ENUM('associado','central','equipe') NOT NULL,
    `criado_em`            DATETIME(6)      NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `enviar_apos`          DATETIME(6)      NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC; janela/atraso',
    `status`               ENUM('pendente','enviando','enviado','suprimido','erro','falhou') NOT NULL DEFAULT 'pendente',
    `tentativas`           TINYINT UNSIGNED NOT NULL DEFAULT 0,
    `proxima_tentativa_em` DATETIME(6)      NULL,
    `supressao_motivo`     ENUM('limite_semana','financeiro','cancelamento','sem_consentimento',
                                'recomendado_recente','sem_credencial','fato_mudou') NULL,
    `externo_id`           VARCHAR(64)      NULL COMMENT 'id devolvido pelo destino (RD/SMTP), sem PII',
    `atualizado_em`        DATETIME(6)      NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_com_evento_dedupe` (`gatilho`, `contact_id`, `referencia_id`, `canal`, `destinatario`),
    KEY `ix_com_evento_fila` (`status`, `enviar_apos`),
    KEY `ix_com_evento_contato` (`contact_id`, `criado_em`),
    KEY `ix_com_evento_referencia` (`referencia_tipo`, `referencia_id`, `status`),
    CONSTRAINT `ck_com_evento_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_com_evento_referencia_id` CHECK (REGEXP_LIKE(`referencia_id`, '^[A-Za-z0-9_.:-]{1,64}$', 'c')),
    CONSTRAINT `ck_com_evento_externo_id` CHECK (
        `externo_id` IS NULL OR REGEXP_LIKE(`externo_id`, '^[A-Za-z0-9_.:@<>-]{1,64}$', 'c')
    ),
    CONSTRAINT `ck_com_evento_tentativas` CHECK (`tentativas` <= 20),
    CONSTRAINT `ck_com_evento_supressao` CHECK (
        (`status` = 'suprimido') = (`supressao_motivo` IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `comunicacao_envio` (
    `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `ocorrido_em`           DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `comunicacao_evento_id` BIGINT UNSIGNED NOT NULL,
    `contact_id`            CHAR(36)        NOT NULL,
    `gatilho`               ENUM('A01','A02','A03','A04','A05','A06','A07','A08','A09','A10',
                                 'A11','A12','A13','A14','A15','A16','A17','A18','A19','A20') NOT NULL,
    `canal`                 ENUM('email','rd','app','interno') NOT NULL,
    `situacao`              ENUM('enviado','entregue','aberto','clicado','falha') NOT NULL,
    `origem_retorno`        ENUM('smtp','rd_api','rd_webhook','utm','app') NOT NULL,
    `erro_codigo`           VARCHAR(48)     NULL COMMENT 'código curto nosso; nunca corpo de resposta de terceiro',
    PRIMARY KEY (`id`, `ocorrido_em`),
    KEY `ix_com_envio_evento` (`comunicacao_evento_id`),
    KEY `ix_com_envio_contato` (`contact_id`, `ocorrido_em`),
    KEY `ix_com_envio_ocorrido` (`ocorrido_em`),
    CONSTRAINT `ck_com_envio_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_com_envio_erro` CHECK (
        `erro_codigo` IS NULL OR REGEXP_LIKE(`erro_codigo`, '^[a-z][a-z0-9_]{0,47}$', 'c')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `comunicacao_supressao` (
    `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `ocorrido_em`           DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `comunicacao_evento_id` BIGINT UNSIGNED NULL COMMENT 'NULL quando nem chegou a enfileirar',
    `contact_id`            CHAR(36)        NOT NULL,
    `gatilho`               ENUM('A01','A02','A03','A04','A05','A06','A07','A08','A09','A10',
                                 'A11','A12','A13','A14','A15','A16','A17','A18','A19','A20') NOT NULL,
    `canal`                 ENUM('email','rd','app','interno') NOT NULL,
    `motivo`                ENUM('limite_semana','financeiro','cancelamento','sem_consentimento',
                                 'recomendado_recente','sem_credencial','fato_mudou') NOT NULL,
    PRIMARY KEY (`id`),
    KEY `ix_com_supressao_contato` (`contact_id`, `ocorrido_em`),
    KEY `ix_com_supressao_evento` (`comunicacao_evento_id`),
    CONSTRAINT `ck_com_supressao_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `notificacao` (
    `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `contact_id`      CHAR(36)        NOT NULL,
    `tipo`            ENUM('solicitacao_criada','solicitacao_pendente','solicitacao_sem_retorno',
                           'solicitacao_concluida','solicitacao_cancelada','cancelamento_recebido',
                           'beneficio_liberado','evento','pagamento','novidade') NOT NULL,
    -- Dedupe: a mesma causa nunca gera duas notificações (RF-NO-04). A
    -- aplicação compõe a chave (ex.: `A04:<uuid>`, `pendente:<evento_id>`).
    `chave`           VARCHAR(80)     NOT NULL,
    `referencia_tipo` ENUM('solicitacao','beneficio','evento','associado','fatura','trilha') NULL,
    `referencia_id`   VARCHAR(64)     NULL,
    `titulo`          VARCHAR(120)    NOT NULL,
    `corpo`           VARCHAR(300)    NULL,
    `link`            VARCHAR(200)    NULL COMMENT 'caminho relativo da área (/area/...)',
    `criada_em`       DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    `lida_em`         DATETIME(6)     NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_notificacao_chave` (`contact_id`, `chave`),
    KEY `ix_notificacao_contato` (`contact_id`, `lida_em`, `criada_em`),
    CONSTRAINT `ck_notificacao_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_notificacao_chave` CHECK (REGEXP_LIKE(`chave`, '^[A-Za-z0-9_.:-]{1,80}$', 'c')),
    CONSTRAINT `ck_notificacao_referencia_id` CHECK (
        `referencia_id` IS NULL OR REGEXP_LIKE(`referencia_id`, '^[A-Za-z0-9_.:-]{1,64}$', 'c')
    ),
    -- Só caminho da própria área: sem esquema, sem `//`, sem `\`, sem `..`.
    CONSTRAINT `ck_notificacao_link` CHECK (
        `link` IS NULL OR (REGEXP_LIKE(`link`, '^/area(/[A-Za-z0-9_-]+)*/?$', 'c') AND `link` NOT LIKE '%..%')
    ),
    CONSTRAINT `ck_notificacao_textos_sem_cpf` CHECK (
        NOT REGEXP_LIKE(CONCAT_WS(' ', `titulo`, `corpo`),
            '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `fila_ligacao` (
    `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `contact_id`      CHAR(36)        NOT NULL,
    `motivo`          ENUM('sem_retorno_2','cancelamento_conversa') NOT NULL,
    `referencia_tipo` ENUM('solicitacao') NOT NULL DEFAULT 'solicitacao',
    `referencia_id`   VARCHAR(64)     NOT NULL,
    `criada_em`       DATETIME(6)     NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    -- Mutáveis só pelo backoffice (apm_area_bo, sql/020) ou pelo operador.
    `status`          ENUM('pendente','em_contato','concluida','sem_sucesso','cancelada') NOT NULL DEFAULT 'pendente',
    `atendido_por`    VARCHAR(120)    NULL,
    `atendido_em`     DATETIME(6)     NULL,
    `resultado`       VARCHAR(500)    NULL COMMENT 'anotação interna; nunca exibida ao associado',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_fila_ligacao_causa` (`motivo`, `referencia_tipo`, `referencia_id`),
    KEY `ix_fila_ligacao_status` (`status`, `criada_em`),
    KEY `ix_fila_ligacao_contato` (`contact_id`, `criada_em`),
    CONSTRAINT `ck_fila_ligacao_contact_id` CHECK (
        REGEXP_LIKE(`contact_id`, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 'c')
    ),
    CONSTRAINT `ck_fila_ligacao_referencia_id` CHECK (REGEXP_LIKE(`referencia_id`, '^[A-Za-z0-9_.:-]{1,64}$', 'c')),
    CONSTRAINT `ck_fila_ligacao_textos_sem_cpf` CHECK (
        NOT REGEXP_LIKE(CONCAT_WS(' ', `atendido_por`, `resultado`),
            '(^|[^0-9a-f])[0-9]{3}[.]?[0-9]{3}[.]?[0-9]{3}-?[0-9]{2}([^0-9a-f]|$)')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- UPDATE por coluna (ADR-0004). Justificativas:
--   comunicacao_evento — o job da outbox marca a entrega (status,
--     tentativas, próxima tentativa, supressão, id externo) e a área suprime
--     o que ficou pendente quando o fato muda (cancelar a solicitação
--     suprime A04/A05/A06 pendentes, RF-SO-12). `enviar_apos` muda quando o
--     job adia para a janela de horário (8h–20h, spec §12.3). Identidade,
--     gatilho, referência, canal e destinatário são imutáveis.
--   notificacao — marcar como lida (`UPDATE ... WHERE lida_em IS NULL AND
--     contact_id = :c`, RF-NO-02). Nada mais muda.
-- Sem DELETE em nenhuma tabela desta migração.
-- ---------------------------------------------------------------------
GRANT UPDATE (`status`, `tentativas`, `proxima_tentativa_em`, `supressao_motivo`, `externo_id`,
              `enviar_apos`, `atualizado_em`)
    ON `area_associado`.`comunicacao_evento` TO 'apm_area'@'%';
GRANT UPDATE (`lida_em`) ON `area_associado`.`notificacao` TO 'apm_area'@'%';
FLUSH PRIVILEGES;

-- Conferência:
--   SHOW GRANTS FOR 'apm_area'@'%';
--   docker compose exec area-associado python -m scripts.db_check
