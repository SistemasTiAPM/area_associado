# ADR-0004: GRANT UPDATE por tabela, nunca DELETE

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0003, ADR-0012

## Contexto

O `CLAUDE.md` (regras 4 e 8) e a migração `sql/000_schema_e_usuario.sql` fixam o usuário
`apm_area` com `SELECT, INSERT, EXECUTE` no schema `area_associado`, **sem UPDATE/DELETE/DDL**.
A premissa era um serviço que só lê e registra trilha (`evento_log`), e a regra 4 previa que
qualquer necessidade de escrita mutável nasceria por decisão explícita.

A spec "Minha APM" introduz estado mutável do associado: **desfazer** ações (dessalvar uma
notícia, desativar um benefício, deixar um tema de interesse), progresso de onboarding e, pelo
ADR-0003, solicitações que mudam de `status` várias vezes. Modelar tudo como "nova linha" tornaria
cada leitura uma consulta de "última linha por chave" e o atendimento ficaria sem visão simples
do estado atual.

Há precedente na própria APM: `apm-parceiros/sql/008_*.sql` faz `REVOKE` no schema e concede
`GRANT UPDATE` **por tabela**, cada um com comentário de justificativa, sem conceder `DELETE`
em nenhuma. O `scripts/db_check.py` da área já verifica os grants do usuário e pode ser estendido
para fiscalizar esse formato.

## Decisão

1. `apm_area` **mantém** `SELECT, INSERT, EXECUTE ON area_associado.*`. Nenhum `UPDATE` nem
   `DELETE` no schema inteiro, em nenhuma hipótese.
2. Cada migração que cria uma tabela mutável concede `GRANT UPDATE ON area_associado.<tabela>
   TO 'apm_area'@'%'` **somente nessa tabela**, precedido de comentário `-- UPDATE: <motivo>`
   e, quando aplicável, lista das colunas que a aplicação de fato altera.
3. **`DELETE` nunca.** Remoção é estado por coluna: `desativado_em DATETIME NULL`,
   `removida_em DATETIME NULL`, `status`. Consultas filtram `IS NULL`. Expurgo físico (retenção,
   pendência P-15) é ato administrativo com usuário distinto, fora da aplicação.
4. Tabelas de **trilha permanecem INSERT-only**: `evento_log`, `evento_uso`,
   `solicitacao_evento`, `onboarding_progresso`. Nenhuma migração pode conceder `UPDATE` a elas.
5. Tabelas com `UPDATE` previstas nesta versão: `solicitacao`, `associado_perfil`,
   `noticia_salva`, `beneficio_ativacao`, `tema_interesse`, `noticia_cache`, `evento_cache`,
   `feature_flag` (esta última só pelo operador; a aplicação não a altera — ver ADR-0007).
6. `scripts/db_check.py` ganha a allowlist `TABELAS_COM_UPDATE` (conjunto fechado no código) e
   **falha com exit 1** se encontrar: `UPDATE` ou `DELETE` no nível do schema; `UPDATE` em
   tabela fora da allowlist; `DELETE` em qualquer tabela; ou tabela da allowlist sem o grant.
   O script roda no `docs/PROVISIONAMENTO.md` após cada migração e no *smoke test* do deploy.
7. Migrações continuam em `sql/NNN_*.sql`, aplicadas pelo operador, com sha256 registrado em
   `schema_migrations`; a aplicação nunca executa DDL nem `GRANT`.

## Consequências

### Positivas
- Mínimo privilégio preservado: cada `UPDATE` tem tabela, motivo e revisão explícitos.
- Separação entre ato da aplicação (nunca apaga) e ato administrativo (expurgo com outro usuário).
- Um erro de código ou injeção não consegue apagar trilha nem dados; o pior caso é um
  `UPDATE` indevido em uma tabela conhecida, com trilha em `solicitacao_evento`/`evento_uso`.
- O `db_check.py` torna a política verificável, não só documentada.

### Negativas / riscos
- Linhas "removidas" acumulam; precisam de política de retenção (P-15) e índices que incluam
  a coluna de estado.
- Uma allowlist no código e grants no banco podem divergir; o `db_check.py` existe para isso,
  mas precisa de fato ser executado.
- Modelo "estado por coluna" exige disciplina nas consultas (`WHERE removida_em IS NULL`);
  esquecer um filtro vaza linha "removida" para a UI.

### Obrigações decorrentes
- Atualizar `CLAUDE.md` (Sessão 1 "Banco" e regra 4/8) para "UPDATE por tabela justificado,
  DELETE nunca".
- Cada migração nova com `GRANT UPDATE` cita este ADR no comentário.
- Teste de `db_check.py` com fixtures de `SHOW GRANTS` (caso válido, schema-level UPDATE,
  tabela fora da lista, DELETE).
- Repositórios SQLAlchemy expõem métodos `desativar()`/`remover()` que setam a coluna de
  estado; nenhum `session.delete()` no código (checado por `grep` em CI).
- P-15: política de retenção e procedimento de expurgo administrativo.

## Alternativas descartadas

- **100% append-only com *event sourcing*.** Preserva o "só INSERT", mas toda consulta vira
  "último evento por chave", o atendimento perde a visão do estado atual e a complexidade não
  se justifica para o volume e a natureza dos dados.
- **`UPDATE`/`DELETE` no schema inteiro.** Simples, mas perde a separação entre aplicação e
  ato administrativo e deixa trilhas (`evento_log`, `solicitacao_evento`) tecnicamente
  alteráveis pelo processo web.
