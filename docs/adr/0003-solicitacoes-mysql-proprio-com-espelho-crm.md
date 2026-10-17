# ADR-0003: Solicitações em MySQL próprio com espelho no CRM

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0002, ADR-0004

## Contexto

Várias ações da spec "Minha APM" (`docs/SPEC-minha-apm.md`) não são comandos imediatos, mas
**pedidos** que alguém da APM precisa atender: diagnóstico de marketing, submissão de trabalho
científico, pedir ou oferecer mentoria, solicitar o cartão APM, alteração cadastral que exige
validação. O usuário pediu que o associado **acompanhe o status** de cada pedido dentro da área.

O levantamento no CRM não encontrou entidade de solicitação ou caso em uso: nenhum projeto
irmão usa `incident`, e não existe entidade customizada equivalente. O Dataverse impõe o limite de
6.000 requisições por 5 minutos por usuário de serviço, e há *flows* do Power Automate que disparam
em `create` de algumas entidades, o que torna gravar diretamente no CRM a cada clique um risco de
cota e de efeitos colaterais.

Pelo ADR-0002, toda escrita no Dynamics passa pelo `mcp_hub`, que ainda não está provisionado.
A área precisa funcionar — inclusive registrar e listar pedidos — mesmo com o hub indisponível, e
o atendimento da APM precisa enxergar os pedidos onde já trabalha (o CRM).

## Decisão

1. **Fonte da verdade** é a tabela `area_associado.solicitacao`:
   - `id CHAR(36)` (UUID v4 gerado pela aplicação), `contact_id CHAR(36)`, `sub_hash CHAR(64)`;
   - `tipo ENUM('alteracao_cadastro','diagnostico_marketing','submeter_trabalho',
     'mentoria_pedir','mentoria_oferecer','cartao_apm','outro')`;
   - `status ENUM('aberta','em_analise','aguardando_associado','concluida','recusada',
     'cancelada')`;
   - `campos JSON` (formulário enviado, validado por schema por tipo), `resposta JSON`
     (mensagens do atendimento), `crm_id CHAR(36) NULL`,
     `crm_sync ENUM('pendente','ok','erro')`, `crm_tentativas TINYINT`, `crm_proxima_em DATETIME`;
   - `criada_em`, `atualizada_em`, `concluida_em` (sem `DELETE`: cancelamento é status).
2. Trilha `solicitacao_evento` **append-only**: `solicitacao_id`, `de_status`, `para_status`,
   `ator ENUM('associado','sistema','atendente')`, `origem ENUM('ui','job','crm')`,
   `mensagem`, `request_id`, `ocorrido_em`.
3. **Tabela de transições** (única fonte, em `app/solicitacoes/maquina.py`):
   - Associado: `aberta → cancelada`; `aguardando_associado → em_analise` (ao responder);
     `aguardando_associado → cancelada`.
   - Sistema/CRM: `aberta → em_analise`; `em_analise → aguardando_associado | concluida |
     recusada`.
   - Qualquer outra transição responde **409 `estado_invalido`** e não grava nada.
4. Toda transição é **um `UPDATE` em `solicitacao` + um `INSERT` em `solicitacao_evento` na
   mesma transação**, com `WHERE status = :de_status` no `UPDATE` (controle otimista); zero linhas
   afetadas → rollback + 409.
5. **Espelho no CRM por outbox**: job a cada 1 min seleciona `crm_sync='pendente'` com
   `crm_proxima_em <= NOW()`, chama `solicitacao.espelhar` (ou `solicitacao.status_atualizar`)
   no hub, *backoff* exponencial (1, 2, 4, ... min, teto 60 min), máximo **10 tentativas**; após
   isso `crm_sync='erro'` e alerta em `evento_log`. Status alterado pelo atendimento volta por job
   a cada 5 min via `solicitacao.alteracoes_consultar(desde=)`, aplicando a mesma máquina de
   estados com `ator='atendente', origem='crm'`.
6. **Entidade no CRM** (proposta, pendência P-06): `task` com `regardingobjectid` apontando para
   o `contact`, `subject = "[Minha APM] <tipo> <uuid>"`, `description` com os campos em texto, e
   `statecode/statuscode` mapeados para os status da área. O `uuid` no `subject` é a chave de
   correlação; o `activityid` retornado vai em `crm_id`.
7. O associado **nunca** espera o CRM: a resposta HTTP da criação é 201 assim que o `INSERT`
   local comita.

## Consequências

### Positivas
- Área funcional e consistente mesmo com hub ou CRM indisponíveis; nenhum pedido se perde.
- Histórico completo e auditável por `solicitacao_evento`; status não pode "pular" etapas.
- O atendimento vê os pedidos no CRM, onde já trabalha, sem nova ferramenta.
- Carga no Dataverse limitada e previsível (jobs em lote, não por clique).

### Negativas / riscos
- Consistência eventual: o CRM pode ficar até alguns minutos atrás da área e vice-versa.
- Exige `GRANT UPDATE` em `solicitacao` (ADR-0004), quebrando o "só INSERT" original.
- Entidade `task` é uma convenção; se a APM escolher outra entidade (P-06), só o conector do
  hub muda, mas o mapeamento de status precisa ser revisto.
- Jobs são um processo novo no compose (serviço `jobs`), com sua própria superfície de falha.

### Obrigações decorrentes
- P-06: confirmar entidade e mapeamento de status com o atendimento antes de `HUB_MODE=real`.
- Migração `sql/00N_solicitacao.sql` com `GRANT UPDATE` justificado (ADR-0004) e índices
  `(contact_id, status)`, `(crm_sync, crm_proxima_em)`.
- JSON Schema por `tipo` em `app/solicitacoes/schemas/`, validado no servidor; tamanho máximo
  de `campos` 16 kB; CHECK na tabela contra chaves proibidas (mesmo filtro de `evento_log`).
- Testes: tabela de transições completa (válidas e inválidas), concorrência (dois UPDATEs
  simultâneos → um 409), outbox com backoff e teto de tentativas, isolamento por `contact_id`.
- P-10: definições de negócio de cada tipo (campos obrigatórios, prazos, quem atende).

## Alternativas descartadas

- **Somente CRM.** Cada clique dependeria da disponibilidade e da cota do Dataverse, a entidade
  de solicitação não existe e *flows* em `create` teriam efeitos colaterais não planejados.
- **Somente MySQL.** O atendimento não enxergaria os pedidos no sistema onde trabalha; criaria
  uma fila paralela sem dono operacional.
