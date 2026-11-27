-- =====================================================================
-- area_associado — purga por retenção, pelo OPERADOR (TI-28; docs/RETENCAO.md).
--
-- A aplicação não tem DELETE (ADR-0004): tudo aqui roda com a credencial
-- ADMINISTRATIVA do RDS, depois de um snapshot manual (docs/OPERACAO.md §6).
--
-- OS PRAZOS SÃO PROPOSTA (P-54: jurídico e encarregado decidem). Ajuste as
-- variáveis abaixo ao que for aprovado ANTES de rodar qualquer DELETE.
--
-- COMO USAR
--   1. Conferência (não altera nada) — rode só o bloco A:
--        mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED area_associado
--        mysql> SOURCE scripts/retencao.sql;      -- com os DELETE ainda comentados
--   2. Decidido o que purgar: snapshot, descomente o bloco aprovado em B e rode
--      de novo. Cada DELETE tem LIMIT: repita até "0 rows affected".
--   3. Registre em docs/CONCLUIDO.md (tabela, critério, linhas, data, quem).
--
-- `evento_uso` e `evento_log` NÃO são purgados aqui: são particionados por mês
-- e saem por DROP/EXCHANGE PARTITION (procedimento no cabeçalho da sql/008).
-- Titular que pediu exclusão: scripts/anonimizar_titular.sql (não é retenção).
-- =====================================================================

SET @agora := UTC_TIMESTAMP(6);
SET @corte_email_verificacao := @agora - INTERVAL 30 DAY;      -- sql/007
SET @corte_job_execucao      := @agora - INTERVAL 90 DAY;      -- docs/JOBS.md §7
SET @corte_notificacao       := @agora - INTERVAL 12 MONTH;
SET @corte_mensagem          := @agora - INTERVAL 12 MONTH;
SET @corte_comunicacao       := @agora - INTERVAL 24 MONTH;
SET @corte_solicitacao       := @agora - INTERVAL 5 YEAR;      -- P-54
SET @corte_consentimento     := @agora - INTERVAL 5 YEAR;      -- P-54
SET @corte_titular           := @agora - INTERVAL 5 YEAR;      -- P-54

-- ---------------------------------------------------------------------
-- A. CONFERÊNCIA — quantas linhas cada critério alcança hoje.
-- ---------------------------------------------------------------------
SELECT 'email_verificacao' AS tabela, COUNT(*) AS purgaveis FROM `email_verificacao`
 WHERE `criado_em` < @corte_email_verificacao
UNION ALL
SELECT 'job_execucao', COUNT(*) FROM `job_execucao`
 WHERE `iniciado_em` < @corte_job_execucao
   AND `id` NOT IN (SELECT `id` FROM (SELECT MAX(`id`) AS `id` FROM `job_execucao` WHERE `status` = 'ok' GROUP BY `job`) u)
UNION ALL
SELECT 'notificacao', COUNT(*) FROM `notificacao` WHERE `criada_em` < @corte_notificacao
UNION ALL
SELECT 'solicitacao_mensagem', COUNT(*) FROM `solicitacao_mensagem`
 WHERE `criada_em` < @corte_mensagem AND `status` IN ('enviada', 'falhou')
UNION ALL
SELECT 'comunicacao_evento', COUNT(*) FROM `comunicacao_evento`
 WHERE `criado_em` < @corte_comunicacao AND `status` IN ('enviado', 'suprimido', 'falhou')
UNION ALL
SELECT 'comunicacao_envio', COUNT(*) FROM `comunicacao_envio` WHERE `ocorrido_em` < @corte_comunicacao
UNION ALL
SELECT 'comunicacao_supressao', COUNT(*) FROM `comunicacao_supressao` WHERE `ocorrido_em` < @corte_comunicacao
UNION ALL
SELECT 'fila_ligacao', COUNT(*) FROM `fila_ligacao`
 WHERE `criada_em` < @corte_comunicacao AND `status` IN ('concluida', 'sem_sucesso', 'cancelada')
UNION ALL
SELECT 'solicitacao (fechadas)', COUNT(*) FROM `solicitacao`
 WHERE `status` IN ('concluida_positiva', 'concluida_negativa', 'cancelada') AND `atualizada_em` < @corte_solicitacao
UNION ALL
SELECT 'consentimento (fora do estado atual)', COUNT(*) FROM `consentimento` c
 WHERE c.`registrado_em` < @corte_consentimento
   AND c.`id` NOT IN (SELECT `id` FROM (SELECT MAX(`id`) AS `id` FROM `consentimento`
                                        GROUP BY `contact_id`, `finalidade`, `canal`) u)
UNION ALL
SELECT 'titular_pedido (fechados)', COUNT(*) FROM `titular_pedido`
 WHERE `status` IN ('concluido', 'recusado', 'cancelado') AND `criado_em` < @corte_titular;

-- Pedidos de exclusão do titular ainda abertos (não é purga: é a fila — docs/RETENCAO.md §4).
SELECT COUNT(*) AS exclusoes_abertas, MIN(`criado_em`) AS mais_antiga FROM `titular_pedido`
 WHERE `tipo` = 'exclusao' AND `status` IN ('registrado', 'em_analise');

-- ---------------------------------------------------------------------
-- B. PURGA — descomente SÓ o bloco aprovado. Snapshot antes. Repita cada
--    DELETE até 0 linhas (LIMIT evita transação longa e lock prolongado).
-- ---------------------------------------------------------------------

-- B1. Pedidos de troca de e-mail (só HMAC; sem valor depois de 30 dias).
-- DELETE FROM `email_verificacao` WHERE `criado_em` < @corte_email_verificacao LIMIT 5000;

-- B2. Rastro dos jobs, mantendo a última execução `ok` de cada job (posição do sync).
-- DELETE FROM `job_execucao`
--  WHERE `iniciado_em` < @corte_job_execucao
--    AND `id` NOT IN (SELECT `id` FROM (SELECT MAX(`id`) AS `id` FROM `job_execucao` WHERE `status` = 'ok' GROUP BY `job`) u)
--  LIMIT 20000;

-- B3. Notificações antigas.
-- DELETE FROM `notificacao` WHERE `criada_em` < @corte_notificacao LIMIT 5000;

-- B4. Outbox da conversa já resolvida (o texto já é NULL depois do envio).
-- DELETE FROM `solicitacao_mensagem`
--  WHERE `criada_em` < @corte_mensagem AND `status` IN ('enviada', 'falhou') LIMIT 5000;

-- B5. Comunicação: rastro primeiro, evento depois.
-- DELETE FROM `comunicacao_envio` WHERE `ocorrido_em` < @corte_comunicacao LIMIT 5000;
-- DELETE FROM `comunicacao_supressao` WHERE `ocorrido_em` < @corte_comunicacao LIMIT 5000;
-- DELETE FROM `comunicacao_evento`
--  WHERE `criado_em` < @corte_comunicacao AND `status` IN ('enviado', 'suprimido', 'falhou') LIMIT 5000;
-- DELETE FROM `fila_ligacao`
--  WHERE `criada_em` < @corte_comunicacao AND `status` IN ('concluida', 'sem_sucesso', 'cancelada') LIMIT 5000;

-- B6. Solicitações fechadas há mais que o prazo (P-54). Filhos antes do pai:
--     `solicitacao_evento` tem chave estrangeira para `solicitacao`; pedido do
--     titular ligado à solicitação sai junto (senão fica órfão).
-- DELETE e FROM `solicitacao_evento` e JOIN `solicitacao` s ON s.`id` = e.`solicitacao_id`
--  WHERE s.`status` IN ('concluida_positiva', 'concluida_negativa', 'cancelada') AND s.`atualizada_em` < @corte_solicitacao;
-- DELETE l FROM `solicitacao_leitura` l JOIN `solicitacao` s ON s.`id` = l.`registro_id`
--  WHERE s.`status` IN ('concluida_positiva', 'concluida_negativa', 'cancelada') AND s.`atualizada_em` < @corte_solicitacao;
-- DELETE p FROM `titular_pedido` p JOIN `solicitacao` s ON s.`id` = p.`solicitacao_id`
--  WHERE s.`status` IN ('concluida_positiva', 'concluida_negativa', 'cancelada') AND s.`atualizada_em` < @corte_solicitacao;
-- DELETE FROM `solicitacao`
--  WHERE `status` IN ('concluida_positiva', 'concluida_negativa', 'cancelada') AND `atualizada_em` < @corte_solicitacao
--  LIMIT 2000;

-- B7. Trilha de consentimento além do prazo, NUNCA a linha que é o estado atual.
-- DELETE FROM `consentimento`
--  WHERE `registrado_em` < @corte_consentimento
--    AND `id` NOT IN (SELECT `id` FROM (SELECT MAX(`id`) AS `id` FROM `consentimento`
--                                       GROUP BY `contact_id`, `finalidade`, `canal`) u)
--  LIMIT 5000;

-- B8. Pedidos do titular fechados além do prazo (exportações; exclusões sem solicitação viva).
-- DELETE FROM `titular_pedido`
--  WHERE `status` IN ('concluido', 'recusado', 'cancelado') AND `criado_em` < @corte_titular
--    AND (`solicitacao_id` IS NULL OR `solicitacao_id` NOT IN (SELECT `id` FROM `solicitacao`))
--  LIMIT 5000;
