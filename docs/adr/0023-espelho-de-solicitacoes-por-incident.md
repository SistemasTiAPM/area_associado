# ADR-0023: Espelho das solicitações no CRM por `incident`/`opportunity`, sincronização por mudança

- **Status:** Aceita
- **Data:** 2026-11-04
- **Decisores:** Sistemas TI (William) · Claude Code (Integrador/Maestro/Atlas/Vitrine)
- **Relacionadas:** ADR-0002 (hub), ADR-0003 e ADR-0018 (solicitações; esta ADR muda o espelho e o item 6
  da 0018), ADR-0019 (jobs), ADR-0014 (sem CPF)

## Contexto

A área propôs em 30/10 (`docs/CONTRATO-HUB.md`, frente C da Onda 2) três ferramentas no `mcp_hub` sobre a
entidade `task`: `solicitacao.espelhar`, `solicitacao.status_atualizar` e
`solicitacao.alteracoes_consultar(cursor)`. O hub implantou e ensaiou em 04/11 **outro contrato**, comum ao
App APM (`mcp_hub/docs/PLANO-SOLICITACOES.md`): `solicitacao.criar` (cria `incident` ou `opportunity` com o
`registro_id` do chamador como chave primária, canal e origem pela conta) e `solicitacao.listar` (por
contato, até 50 linhas, `statecode/statuscode` crus). Não há escrita de status (o app user do hub não tem
Write nessas entidades), nem consulta por cursor, nem campo de mensagem pública. A cota PII do hub conta
LINHAS devolvidas, inclusive as de registros abertos pela Central.

## Decisão

1. **Entidade:** toda solicitação de serviço vira **ocorrência** (`incident`) do time **Central de
   Relacionamento**; assunto por tipo numa tabela fixa (`app/dominio/solicitacoes/catalogo_crm.py`):
   `alteracao_cadastro` → "Atualização Cadastral - Pessoa Física"; os demais → "Atendimento APM" até a
   Central escolher. `exclusao_dados` (LGPD, DEC-06) e pedido de benefício (Fase 4) ficam sem destino.
2. **Identidade:** `crm_id` = o próprio `solicitacao.id` (o `registro_id` do hub). Guardamos `crm_entidade`,
   `crm_protocolo` (ticketnumber, mostrado ao associado) e o último par `statecode/statuscode` visto
   (`sql/015`).
3. **Texto:** a área formata o formulário em texto puro (`crm.py`), medido em unidades UTF-16; o limite é
   garantido na origem (mensagem livre ≤ 1700, assunto ≤ 120); corte só como defesa, marcado.
4. **Sem escrita de status:** com o pedido no CRM, o associado **não cancela nem responde pela área** (409
   `na_central`; a tela mostra o protocolo e orienta a falar com a Central). Mudança local depois do envio
   (backoffice) fica `crm_sync='retido'` com aviso no `evento_log`, reprocessável quando houver ferramenta.
5. **Sincronização por mudança:** por contato, cadência `JOBS_SYNC_CADENCIA_H` (6 h), até
   `JOBS_SYNC_LIMITE` linhas (10; 50 se o pedido não aparecer), teto diário `JOBS_SYNC_LINHAS_DIA` (5.000).
   Transita **só quando o par muda**; 0/1 na criação não move nada, mas 0/1 vindo de outro estado é
   `em_atendimento`; 0/3 → `pendente_associado` com mensagem padrão + protocolo.
6. **Máquina (adenda ao item 6 da ADR-0018):** `(apm, crm)` pode levar `pendente_associado → em_atendimento`
   sem mensagem; com o caminho intermediário, o CRM conclui a partir de `pendente_associado` (P-66).
7. **Erros do hub:** 429 com `Retry-After` pausa o processo; `escrita_indeterminada` repete com o mesmo id;
   `conflito` e contato inexistente são permanentes; assunto/time inexistente e conta sem canal são
   sistêmicos (param a rodada sem gastar tentativa).

## Consequências

### Positivas
- Um contrato só para App APM e Minha APM no hub; o CRM tem protocolo, assunto e dono desde a criação.
- Idempotência pela chave primária: repetir um envio nunca duplica.
- A área não promete ao associado o que não chega ao CRM.

### Negativas / riscos
- O associado perde o cancelamento em autoatendimento depois do envio (a spec permite até o atendimento
  começar — divergência registrada; volta com a ferramenta de status, P-74).
- A sincronização custa cota proporcional ao histórico do contato no CRM, não às mudanças; mitigado por
  cadência, página curta e teto diário; resolvido com consulta por cursor (P-75).
- Os códigos de status são os padrão do Dataverse; customização do tenant precisa ser confirmada (P-76).

### Obrigações decorrentes
- `sql/015_solicitacao_crm.sql` (colunas, CHECKs, `GRANT UPDATE` nas 5 colunas), aplicada antes do deploy.
- Conta `area-associado-jobs` com `ferramentas:escrever` e grants exatos em `solicitacao.criar` e
  `solicitacao.listar`; cota PII 25.000/dia (varredura noturna da carteirinha + sincronização + margem).
- `docs/CONTRATO-HUB.md` §Solicitações, `docs/JOBS.md`, testes em `tests/test_solicitacoes_crm.py` e
  `tests/test_jobs_integracao.py`.

## Alternativas descartadas
- **Mapear 0/1 "Em andamento" para `em_atendimento`.** É o status de criação: todo pedido apareceria "em
  atendimento" minutos depois do envio.
- **Sincronizar pelo estado a cada 5 minutos.** Oscilaria depois de o associado agir e gastaria a cota em
  mais de 40 vezes o teto.
- **Manter cancelamento e resposta só na área.** O associado acharia que cancelou enquanto a Central seguia
  atendendo, e o CRM depois "concluiria" um pedido cancelado.
