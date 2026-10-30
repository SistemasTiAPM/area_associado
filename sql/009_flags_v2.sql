-- =====================================================================
-- area_associado — feature flags v2 (ADR-0021, adenda à ADR-0007; spec v2 §14).
--
-- Rodar com o usuário ADMIN do RDS:
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED \
--         area_associado < sql/009_flags_v2.sql
-- Registrar o hash no schema_migrations após aplicar (docs/PROVISIONAMENTO.md §2.4).
--
-- Só INSERT na tabela existente `feature_flag` (sql/003): nenhuma estrutura
-- nova, NENHUM GRANT (a aplicação continua só lendo; ligar/desligar é ato do
-- operador por SQL). Reexecução segura: só a `descricao` é atualizada —
-- `ligada` NUNCA é tocada por esta migração, para não religar nem desligar
-- o que o operador já decidiu.
--
-- Todas nascem desligadas (CLAUDE.md, regra 19): cada uma depende de fonte,
-- terceiro ou parecer. Chave nova exige entrada em app/flags.py:FLAGS_CONHECIDAS
-- e em frontend/src/api/tipos.ts:ChaveFlag — o teste tests/test_espelho_front.py
-- confere os três.
-- =====================================================================

USE `area_associado`;

INSERT INTO `feature_flag` (`chave`, `ligada`, `descricao`) VALUES
    ('notificacoes',            0, 'P15 sino e central de notificações — aguarda modelo de notificação (DEC-08)'),
    ('encaminhamento_parceiro', 0, 'Tipo 2: solicitação encaminhada ao parceiro — canal por parceiro (DEC-04, EXT-12)'),
    ('reservas',                0, 'Tipo 4: reserva com disponibilidade do parceiro — sem fonte (F2)'),
    ('inscricoes',              0, 'Tipo 5: inscrição real em evento — aguarda plataforma de eventos (EXT-13)'),
    ('comunicacao_outbox',      0, 'Outbox de comunicação para o RD Station — aguarda contrato (DEC-18, P-46)'),
    ('cancelamento_online',     0, 'P14 pedido de cancelamento pela área — gatilho A16; aguarda espelho no CRM (P-06)'),
    ('lgpd_consentimentos',     0, 'P13 consentimentos, exportação e exclusão — aguarda textos do jurídico (P-54)')
AS novo
ON DUPLICATE KEY UPDATE `descricao` = novo.`descricao`;
