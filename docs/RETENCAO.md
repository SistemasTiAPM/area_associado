# Retenção e direitos do titular — Minha APM

> Estado: **rascunho técnico de 2026-11-19** (TI-28). Os **prazos são proposta** de Sistemas TI; quem decide é
> o jurídico e o encarregado de dados (**P-54**). Nada aqui é executado pela aplicação: ela não tem `DELETE`
> (ADR-0004). Tudo é ato do operador, com a credencial administrativa do RDS, registrado em
> `docs/CONCLUIDO.md` (tabela, critério, data, quem).

## 1. Princípios

1. **A aplicação nunca apaga.** Purga = operador (`scripts/retencao.sql`) ou descarte de partição (`sql/008`).
2. **Exclusão a pedido do titular = anonimização** (ADR-0025): as linhas perdem o vínculo com a pessoa e o
   conteúdo pessoal; o resto sai pela retenção normal.
3. **Trilha de segurança fica** pelo prazo próprio, com identidade só em HMAC.
4. **Snapshot manual do RDS antes de qualquer purga** (`docs/OPERACAO.md` §6). Nunca a partição do mês corrente.

## 2. Tabela × prazo × mecanismo

| Tabela | O que guarda | Prazo proposto | Mecanismo | Na anonimização do titular |
|---|---|---|---|---|
| `associado` | primeiro/último acesso, token da carteirinha | enquanto associado | nunca purgar; anonimizar | id novo, sem token, `anonimizado_em` |
| `associado_perfil` | cache do cadastro do CRM, miniatura da foto | enquanto associado | cache sobrescrito; anonimizar | contatos, endereço, CRM, foto → NULL |
| `perfil_declarado` | tratamento, atuação, temas, frequência, fonte | enquanto associado | anonimizar | tratamento → NULL; listas ficam (agregado) |
| `pergunta_perfil` | perguntas puladas | enquanto associado | anonimizar | id novo |
| `consentimento_texto` | textos por versão | permanente | nunca | — |
| `consentimento` | trilha de decisões | **5 anos** após a última decisão (prova) — P-54 | `scripts/retencao.sql` | id novo, sem `sub_hash` |
| `titular_pedido` | pedidos de exportação e exclusão | **5 anos** (prova do atendimento) — P-54 | `scripts/retencao.sql` | id novo; o pedido fica como registro |
| `solicitacao` + `solicitacao_evento` | pedidos e linha do tempo | **5 anos** após o fechamento — P-54 | `scripts/retencao.sql` (filhos antes do pai) | textos removidos; tipo, status e datas ficam |
| `solicitacao_mensagem` | outbox da conversa (texto só até o envio) | texto: até a confirmação do hub (job); linha: 12 meses | job (texto) + `scripts/retencao.sql` | texto → NULL, pendente vira `falhou` |
| `solicitacao_leitura` | última abertura da conversa | junto com a solicitação | `scripts/retencao.sql` | id novo |
| `notificacao` | avisos no app | **12 meses** | `scripts/retencao.sql` | título fixo, corpo e link → NULL |
| `comunicacao_evento` / `_envio` / `_supressao` | outbox e rastro de comunicação | **24 meses** | `scripts/retencao.sql` | id novo; pendente vira suprimido |
| `fila_ligacao` | pedidos de ligação | **24 meses** | `scripts/retencao.sql` | id novo; anotação → NULL |
| `email_verificacao` | pedidos de troca de e-mail (só HMAC) | **30 dias** (sql/007) | `scripts/retencao.sql` | hashes zerados |
| `evento_uso` | analytics pseudonimizado | **24 meses** | `DROP PARTITION` (sql/008) | id novo, sem `sub_hash` |
| `evento_log` | trilha de segurança e de negócio | `request` **12 meses**; `seguranca`/`negocio`/`erro` **5 anos** — P-54 | `EXCHANGE PARTITION` + arquivo (sql/008) | só o `contact_id` em claro é trocado; HMAC fica |
| `job_execucao` | rastro dos jobs (sem dado pessoal) | **90 dias**, mantendo a última `ok` de cada job | `scripts/retencao.sql` | — |
| `feature_flag`, `parametro`, `faq`, `texto_sistema`, `schema_migrations` | configuração | permanente | nunca | — |

O que **não** está na área e por isso não aparece aqui: CPF (ADR-0014), a conversa com a Central e o cadastro
oficial (CRM), a conta de acesso (Login APM). O encarregado trata esses sistemas à parte.

## 3. Rotina do operador

- **Mensal:** criar partições futuras se o `db_check` avisar (sql/008, item 1).
- **Trimestral:** rodar `scripts/retencao.sql` em modo de conferência (só os `SELECT COUNT`), decidir, snapshot,
  rodar os blocos aprovados, registrar.
- **Quando houver pedido de exclusão:** §4.

## 4. Pedido de exclusão do titular (ADR-0025)

Enquanto não existir backoffice (Onda 6), a fila é esta consulta (credencial administrativa ou de leitura):

```sql
SELECT p.protocolo, p.criado_em, p.status, s.status AS solicitacao, p.contact_id
  FROM titular_pedido p JOIN solicitacao s ON s.id = p.solicitacao_id
 WHERE p.tipo = 'exclusao' AND p.status IN ('registrado', 'em_analise')
 ORDER BY p.criado_em;
```

Linha com `solicitacao = 'cancelada'`: o associado desistiu; nada a fazer (o script também recusa).

1. O encarregado analisa (identidade, obrigação legal de guarda, pendência financeira) e autoriza por escrito.
2. O encarregado trata o CRM e o Login APM, se for o caso (fora desta área).
3. Operador: snapshot manual do RDS.
4. Operador:
   ```bash
   cd /home/ubuntu/area_associado
   mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado \
     -e "SET @protocolo='LGPD-AAAAMMDD-XXXXXX'; SET @operador='nome.sobrenome'; SOURCE scripts/anonimizar_titular.sql;"
   ```
   A primeira linha de saída diz `anonimizando…` ou `NADA A FAZER…`; a última, `anonimização concluída` com
   `status_do_pedido = concluido` e `associado_anonimizado = 1`.
5. Registrar em `docs/CONCLUIDO.md`: protocolo, data, quem autorizou, quem executou. **Sem** nome, CPF ou
   `contact_id`.
6. Responder ao titular pelo canal que o encarregado definir (a área já mostra a solicitação como concluída,
   mas a pessoa pode não entrar mais).

Recusa (obrigação legal de guarda, por exemplo): hoje, por SQL do operador —
`UPDATE titular_pedido SET status='recusado', concluido_em=UTC_TIMESTAMP(6), observacao='…' WHERE protocolo='…'`
e transição da solicitação para `concluida_negativa` com mensagem pública. Vira tela no backoffice.

A operação **não tem volta** depois do `COMMIT`; a única reversão é restaurar o snapshot.

## 5. Pendências que fecham este documento

- **P-54:** prazos da coluna "Prazo proposto", prazo de resposta ao titular, destino da prova de consentimento
  depois da anonimização, quem opera a fila.
- **P-15:** fecha quando a P-54 confirmar os prazos e a primeira purga for executada e registrada.
- **Onda 6:** fila LGPD e botão de anonimização no backoffice (`apm_area_bo`), no lugar do script.
