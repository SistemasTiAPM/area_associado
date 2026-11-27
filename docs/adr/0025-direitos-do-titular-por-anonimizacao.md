# ADR-0025: Direitos do titular pelo perfil — exportação síncrona e exclusão por anonimização feita pelo operador

- **Status:** Aceita
- **Data:** 2026-11-19
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine)
- **Relacionadas:** ADR-0004 (UPDATE por tabela, DELETE nunca), ADR-0014 (sem CPF), ADR-0015 (step-up),
  ADR-0020 (limites por contagem no banco), ADR-0022 (usuário de banco do backoffice), ADR-0026 (consentimento
  e perfil declarado). Fecha DEC-06 e DIV-05 do levantamento.

## Contexto

A spec v2 (P13 e §11.6) pede "baixar meus dados e pedir exclusão (LGPD)", com fila no backoffice. A área tem
duas regras que colidem com um "excluir" literal: a aplicação nunca tem `DELETE` (ADR-0004) e as trilhas são
append-only. O backoffice (Onda 6) ainda não existe. Os textos e prazos são do jurídico (P-54).

## Decisão

Decisão do William em 19/11 (DEC-06): **exclusão é anonimização**, sem `DELETE`; `evento_log` fica, com a
identidade só como HMAC; purga definitiva pela retenção, pelo operador.

1. **Exportação é síncrona e só do que a área guarda.** `POST /api/v1/perfil/dados/exportar` devolve um JSON
   (`minha-apm-dados/1`) com cadastro em cache, acessos, perfil declarado, consentimentos, solicitações com
   linha do tempo, mensagens ainda não enviadas, notificações, comunicações, pedidos do titular e uso (até
   2.000 eventos). Não entra: CPF (a área não tem), `sub`, `contact_id`, hashes, anotação interna, conversa
   com a Central (vive no CRM) e a trilha de segurança. O arquivo diz isso em `observacoes`. Nada do arquivo é
   guardado: só o fato (`titular_pedido` tipo `exportacao`, já `concluido`).
2. **Uma exportação a cada 7 dias**, contada no banco com a linha do associado travada (ADR-0020). A montagem
   e o registro são uma transação: se a montagem falha, nada conta.
3. **Exportar e pedir exclusão exigem step-up** (`idp_at` ≤ `REAUTH_MAX_IDADE`, regra 22), CSRF e limite de
   taxa. A exportação fica no `evento_log` como `acesso_dado_pessoal` (item 7).
4. **Pedir exclusão é registrar um pedido**, nunca executar. A rota exige a palavra `EXCLUIR` digitada, abre a
   solicitação `exclusao_dados` (que o associado acompanha e pode cancelar em Solicitações) e grava
   `titular_pedido` tipo `exclusao` com protocolo `LGPD-AAAAMMDD-XXXXXX`. Uma aberta por associado.
5. **Quem anonimiza é o operador**, com a credencial administrativa, por `scripts/anonimizar_titular.sql`,
   depois da análise do encarregado. A aplicação (`apm_area`) **não** recebe `UPDATE` em `titular_pedido`,
   nem privilégio novo em coluna pessoal: uma falha da aplicação não consegue anonimizar ninguém. O
   levantamento (TI-26) previa um job; ficou o script, pelo menor privilégio. Quando o backoffice existir, a
   fila e o botão passam para ele (`apm_area_bo`), com ADR própria.
6. **O que a anonimização faz** (uma transação, sem `DELETE`): troca o `contact_id` do titular por um
   identificador novo, sem relação com o CRM, em todas as tabelas; apaga cache do cadastro, foto, tratamento,
   textos de solicitações, mensagens e notificações; suprime comunicação pendente; zera `sub_hash` fora do
   `evento_log`; marca `associado.anonimizado_em`; conclui a solicitação e fecha o pedido. As linhas ficam
   sem dono, contam em totais e saem pela retenção (`docs/RETENCAO.md`). Em `evento_log` só o `contact_id` em
   claro é trocado; o HMAC do `sub` fica (trilha de segurança).
7. **Registro de acesso a dado pessoal (TI-90).** `audit.registrar_acesso_dado_pessoal` é o padrão único:
   `evento_log` `seguranca`/`acesso_dado_pessoal` com HMAC do titular, nomes dos grupos de campos e finalidade
   de um catálogo fechado. Agregado para terceiro só por `dominio.agregacao.agregar(min_n=20)`.
8. **Tudo atrás de `lgpd_consentimentos`** (desligada). Desligada = 404 `recurso_desligado` e seção oculta.

## Consequências

- Exclusão **não é desfiliação nem apaga o CRM ou a conta do Login APM**: o encarregado trata esses sistemas.
  Quem continua associado e entra de novo recebe um cadastro mínimo novo, sem herdar nada (e um novo
  `acesso_primeiro`). A tela diz isso antes da confirmação.
- O pedido cancelado pelo associado não é alterado pela aplicação: o estado efetivo é lido da solicitação, e
  o script recusa pedido cuja solicitação foi cancelada.
- O `contact_id` em claro de `evento_log` é alterado pelo script administrativo. É a única escrita prevista
  nessa trilha e só existe fora da aplicação.
- Enquanto não houver backoffice, o encarregado depende do operador para ver a fila
  (`docs/RETENCAO.md` §4) e para executar.
- Prazo de resposta ao titular, texto da confirmação e destino da prova de consentimento depois da
  anonimização são do jurídico (P-54); a flag só deve ser ligada depois disso.

## Alternativas rejeitadas

- **`DELETE` pela aplicação ou por job:** viola a ADR-0004 e dá à aplicação o poder de apagar em massa.
- **Job de anonimização com `UPDATE` em colunas pessoais:** mesmo problema, com privilégio permanente para um
  ato raro.
- **Exportação assíncrona por e-mail:** mandaria dado pessoal por um canal que hoje é simulado (P-27) e
  guardaria o arquivo em algum lugar.
- **Só marcar `desativado_em`:** o dado continuaria ligado à pessoa; não atende o pedido.
