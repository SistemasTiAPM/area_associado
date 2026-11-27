-- =====================================================================
-- area_associado — anonimização a pedido do titular (LGPD; ADR-0025, DEC-06).
--
-- QUEM RODA: o operador, com a credencial ADMINISTRATIVA do RDS, depois que o
-- encarregado de dados concluir a análise do pedido. A aplicação (`apm_area`)
-- não tem privilégio para isto e não deve ganhar: é o menor privilégio que
-- impede uma falha da aplicação de apagar o dado de muita gente.
--
-- COMO RODAR (um pedido por vez, pelo protocolo que o associado recebeu):
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED area_associado \
--     -e "SET @protocolo='LGPD-20261119-ABC234'; SET @operador='nome.sobrenome'; SOURCE scripts/anonimizar_titular.sql;"
--   Antes: snapshot manual do RDS (docs/OPERACAO.md §6). A operação não tem volta.
--
-- O QUE FAZ (numa transação; sem DELETE — ADR-0004)
--   Troca o `contact_id` do titular por um identificador novo, sem relação com
--   o CRM, em TODAS as tabelas da área, e apaga (NULL ou texto fixo) o conteúdo
--   pessoal: cache do cadastro, foto, tratamento, textos de solicitações,
--   mensagens, notificações, anotações. O que sobra são linhas sem dono, que
--   continuam contando em totais (uso, solicitações por tipo) e saem pela
--   retenção normal (docs/RETENCAO.md).
--   `evento_log` FICA (trilha de segurança): só o `contact_id` em claro é
--   trocado; a identidade continua apenas como HMAC (`sub_hash`), como decidido.
--   A solicitação `exclusao_dados` é concluída e o pedido do titular é fechado.
--
-- O QUE NÃO FAZ
--   Não toca o CRM nem o Login APM: o cadastro oficial e a conta de acesso são
--   tratados pelo encarregado nos sistemas de origem. Se a pessoa continuar
--   associada e entrar de novo, a área recria só o cadastro mínimo.
--
-- TRAVAS
--   Só age se o protocolo for de um pedido de EXCLUSÃO ainda aberto
--   (`registrado` ou `em_analise`) cuja solicitação não foi cancelada pelo
--   associado. Fora disso `@cid` fica NULL e nenhum comando altera linha
--   (comparação com NULL nunca casa). A primeira e a última consulta dizem o
--   que aconteceu. Rodar duas vezes o mesmo protocolo: a segunda não faz nada.
--
-- Ensaiado em MySQL 8.4 descartável (tests/test_privacidade_integracao.py).
-- =====================================================================

SET @protocolo := TRIM(COALESCE(@protocolo, ''));
SET @operador := LEFT(TRIM(COALESCE(@operador, 'operador')), 80);
SET @agora := UTC_TIMESTAMP(6);
SET @zeros := REPEAT('0', 64);

SET @cid := (
    SELECT p.`contact_id`
      FROM `titular_pedido` p
      JOIN `solicitacao` s ON s.`id` = p.`solicitacao_id`
     WHERE p.`protocolo` = CONVERT(@protocolo USING utf8mb4) COLLATE utf8mb4_unicode_ci
       AND p.`tipo` = 'exclusao'
       AND p.`status` IN ('registrado', 'em_analise')
       AND s.`tipo_servico` = 'exclusao_dados'
       AND s.`status` <> 'cancelada'
);
SET @sid := (
    SELECT p.`solicitacao_id` FROM `titular_pedido` p
     WHERE p.`protocolo` = CONVERT(@protocolo USING utf8mb4) COLLATE utf8mb4_unicode_ci
       AND p.`contact_id` = @cid
);
SET @anon := IF(@cid IS NULL, NULL, CONVERT(UUID() USING utf8mb4) COLLATE utf8mb4_unicode_ci);

SELECT IF(@cid IS NULL,
          'NADA A FAZER: protocolo inexistente, pedido já fechado ou solicitação cancelada pelo associado',
          CONCAT('anonimizando o titular do pedido ', @protocolo)) AS situacao;

START TRANSACTION;

-- 1. Cadastro em cache e identidade na área.
UPDATE `associado_perfil`
   SET `contact_id` = @anon, `nome` = NULL, `email` = NULL, `celular` = NULL, `telefone` = NULL,
       `telefone2` = NULL, `endereco` = NULL, `num_contato` = NULL, `crm` = NULL, `crm_uf` = NULL,
       `data_filiacao` = NULL, `foto_miniatura` = NULL, `foto_etag` = NULL, `foto_atualizada_em` = NULL
 WHERE `contact_id` = @cid;

UPDATE `associado`
   SET `contact_id` = @anon, `sub_hash` = @zeros, `carteirinha_token` = NULL, `anonimizado_em` = @agora
 WHERE `contact_id` = @cid;

UPDATE `perfil_declarado` SET `contact_id` = @anon, `tratamento` = NULL, `atualizado_em` = @agora
 WHERE `contact_id` = @cid;

UPDATE `pergunta_perfil` SET `contact_id` = @anon WHERE `contact_id` = @cid;

UPDATE `consentimento` SET `contact_id` = @anon, `sub_hash` = NULL WHERE `contact_id` = @cid;

UPDATE `email_verificacao`
   SET `contact_id` = @anon, `email_hash` = @zeros, `codigo_hash` = @zeros,
       `invalidado_em` = COALESCE(`invalidado_em`, @agora)
 WHERE `contact_id` = @cid;

-- 2. Solicitações: textos saem; tipo, status e datas ficam (totais por tipo).
UPDATE `solicitacao_evento`
   SET `mensagem_publica` = IF(`mensagem_publica` IS NULL, NULL, '[removido a pedido do titular]'),
       `justificativa` = IF(`justificativa` IS NULL, NULL, '[removido a pedido do titular]')
 WHERE `solicitacao_id` IN (SELECT `id` FROM `solicitacao` WHERE `contact_id` = @cid);

INSERT INTO `solicitacao_evento`
       (`solicitacao_id`, `ocorrido_em`, `evento`, `de_status`, `para_status`, `ator`, `origem`,
        `usuario_interno`, `justificativa`, `mensagem_publica`)
SELECT s.`id`, @agora, 'transicao', s.`status`, 'concluida_positiva', 'apm', 'backoffice',
       @operador, CONCAT('Anonimização concluída a pedido do titular (', @protocolo, ')'),
       'Seu pedido de exclusão de dados foi concluído.'
  FROM `solicitacao` s
 WHERE s.`id` = @sid AND s.`contact_id` = @cid
   AND s.`status` NOT IN ('concluida_positiva', 'concluida_negativa', 'cancelada');

UPDATE `solicitacao`
   SET `status` = 'concluida_positiva', `concluida_em` = @agora, `sem_retorno_desde` = NULL,
       `atualizada_em` = @agora
 WHERE `id` = @sid AND `contact_id` = @cid
   AND `status` NOT IN ('concluida_positiva', 'concluida_negativa', 'cancelada');

UPDATE `solicitacao`
   SET `contact_id` = @anon, `sub_hash` = @zeros, `dados` = JSON_OBJECT(), `resultado` = NULL,
       `avaliacao_comentario` = NULL, `cancel_motivo` = NULL,
       -- O que ainda esperava o espelho no CRM não sai mais: o contato deixou de existir para a área.
       `crm_sync` = IF(`crm_sync` IN ('pendente', 'erro'), 'retido', `crm_sync`)
 WHERE `contact_id` = @cid;

UPDATE `solicitacao_mensagem`
   SET `contact_id` = @anon, `texto` = NULL,
       `erro_codigo` = IF(`status` IN ('pendente', 'erro'), 'titular_anonimizado', `erro_codigo`),
       `status` = IF(`status` IN ('pendente', 'erro'), 'falhou', `status`)
 WHERE `contact_id` = @cid;

UPDATE `solicitacao_leitura` SET `contact_id` = @anon WHERE `contact_id` = @cid;

-- 3. Notificações e comunicação: o que estava para sair é suprimido.
UPDATE `notificacao`
   SET `contact_id` = @anon, `titulo` = 'Notificação removida', `corpo` = NULL, `link` = NULL
 WHERE `contact_id` = @cid;

UPDATE `comunicacao_evento`
   SET `contact_id` = @anon, `atualizado_em` = @agora,
       `supressao_motivo` = IF(`status` IN ('pendente', 'enviando', 'erro'), 'fato_mudou', `supressao_motivo`),
       `status` = IF(`status` IN ('pendente', 'enviando', 'erro'), 'suprimido', `status`)
 WHERE `contact_id` = @cid;

UPDATE `comunicacao_envio` SET `contact_id` = @anon WHERE `contact_id` = @cid;
UPDATE `comunicacao_supressao` SET `contact_id` = @anon WHERE `contact_id` = @cid;

UPDATE `fila_ligacao`
   SET `contact_id` = @anon, `resultado` = NULL,
       `status` = IF(`status` IN ('pendente', 'em_contato'), 'cancelada', `status`)
 WHERE `contact_id` = @cid;

-- 4. Trilhas: perdem o vínculo com o CRM. `evento_uso` também perde o HMAC;
--    `evento_log` mantém o HMAC (trilha de segurança). Sem índice por
--    `contact_id` em `evento_log`: a consulta varre as partições (segundos a minutos).
UPDATE `evento_uso` SET `contact_id` = @anon, `sub_hash` = NULL WHERE `contact_id` = @cid;
UPDATE `evento_log` SET `contact_id` = @anon WHERE `contact_id` = @cid;

-- 5. Pedidos do titular: os dele ficam sem dono; o de exclusão é fechado.
UPDATE `titular_pedido`
   SET `status` = 'concluido', `concluido_em` = @agora,
       `observacao` = CONCAT('anonimizado por ', @operador)
 WHERE `protocolo` = CONVERT(@protocolo USING utf8mb4) COLLATE utf8mb4_unicode_ci AND `contact_id` = @cid;

UPDATE `titular_pedido` SET `contact_id` = @anon, `sub_hash` = @zeros WHERE `contact_id` = @cid;

COMMIT;

SELECT IF(@cid IS NULL, 'nada alterado', 'anonimização concluída') AS resultado,
       @protocolo AS protocolo,
       (SELECT `status` FROM `titular_pedido`
         WHERE `protocolo` = CONVERT(@protocolo USING utf8mb4) COLLATE utf8mb4_unicode_ci) AS status_do_pedido,
       (SELECT COUNT(*) FROM `associado` WHERE `contact_id` = @anon AND `anonimizado_em` IS NOT NULL) AS associado_anonimizado;
