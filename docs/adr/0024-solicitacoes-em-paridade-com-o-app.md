# ADR-0024: Solicitações em paridade com o App APM — web lê o CRM, job escreve, conversa pela Timeline

- **Status:** Aceita
- **Data:** 2026-11-13
- **Decisores:** Sistemas TI (William) · Claude Code (Integrador/Maestro/Atlas/Vitrine/Sentinela)
- **Relacionadas:** ADR-0003 e ADR-0018 (solicitações), ADR-0019 (jobs), ADR-0023 (espelho; esta ADR muda os
  itens 1 e 4 dela), ADR-0002 (hub), ADR-0004 (UPDATE por tabela), ADR-0007 (flags), ADR-0014 (sem CPF)

## Contexto

O App APM está em produção com abertura de ocorrências/oportunidades, listagem, mensagens associado ↔ Central
na Timeline do CRM e produto na oportunidade. Em 13/11 o `mcp_hub` publicou o contrato para a Minha APM
oferecer o **mesmo serviço, pelas mesmas ferramentas e com o mesmo catálogo de tipos**
(`docs/CONTRATO-HUB.md` "Solicitações"): `solicitacao.criar` com `produto_id`, `solicitacao.produtos`,
`solicitacao.listar` devolvendo só autoatendimento dos dois canais (regra D-14 do William: o associado vê, nos
dois canais, tudo o que abriu por qualquer um deles), `solicitacao.interacoes_listar` e `solicitacao.interagir`.

A área, até aqui (ADR-0023): só o serviço de jobs falava com o hub sobre solicitações; o slug gravado no CRM
era o `tipo_servico` local (`outro`, diferente do `outros` do App → registro sem conversa); nenhum tipo virava
oportunidade; depois do envio o associado não respondia nem via nada do CRM além do protocolo.

## Decisão

Decisões do William em 13/11 (não reabrir sem ADR nova):

1. **Web lê, job escreve.** A conta web `area-associado` continua só com `ferramentas:ler` (P-29 intacta) e
   ganha três leituras síncronas: `solicitacao.listar`, `solicitacao.interacoes_listar` e
   `solicitacao.produtos`. Toda escrita (`criar`, `interagir`) sai pelo serviço de jobs, conta
   `area-associado-jobs`, por outbox.
2. **Slugs do App.** O que vai ao CRM usa o catálogo comum (`catalogo_crm.TIPOS_CRM`, §2 do contrato). Os
   15 tipos novos entram no ENUM `tipo_servico` com o próprio slug. Os tipos antigos da área são traduzidos
   no envio: `outro → outros`, `alteracao_cadastro → alteracao_cadastral`; `declaracao_associado`,
   `cancelamento_associacao` e os demais → `outros`, com o rótulo real no título (`Minha APM: <rótulo>`).
   `exclusao_dados` e pedido de benefício seguem sem destino. `seguros` (legado) só é reconhecido.
3. **Paridade completa atrás da flag `solicitacoes_crm`** (desligada; `sql/016`): tela "Nova solicitação" com o
   catálogo inteiro, lista dos dois canais e conversa. Desligada = comportamento da Onda 2, e as rotas novas
   respondem 404 `recurso_desligado`.
4. **Rótulos do App em tudo que está no CRM.** A situação é a do BFF do App
   (`situacao_crm.py`: aberta, em andamento, aguardando associado, concluída, cancelada) e o texto depende de
   quem responde (Central × Equipe APM) e de quem falou por último. Os 7 rótulos da spec v2 valem só para o
   que ainda não chegou ao CRM e para os tipos que não vão para lá.

Desenho:

5. **Fonte da verdade da ABERTURA continua local** (ADR-0003): `POST /solicitacoes` grava e responde 201 sem
   esperar o CRM; o espelho cria o registro com `registro_id = id`.
6. **Leitura = fusão por `id == registro_id`** (`leitura_crm.py`): linhas do CRM ∪ linhas da área. Com linha
   do CRM, o par `statecode/statuscode` ao vivo decide situação e rótulo; sem ela vale o último par gravado
   pelo job. Registro aberto pelo App **não ganha linha na área**; a descrição dele fica em trânsito e o
   título do CRM é descartado. Cache por contato em memória (60 s). Sem paginação: até 200 da área + 50 do CRM.
7. **GET não muda a máquina local.** Transições, notificações e o contador do menu continuam com o job de
   sincronização (cadência de 6 h, P-75); a tela mostra o par ao vivo. A única escrita de uma leitura é
   `solicitacao_leitura.visto_em` (selo "Nova resposta").
8. **Degradação.** Hub fora na lista → só o que é da área, com `parcial: true`. Registro que só existe no
   CRM com o hub fora → 503, nunca 404. Conversa com o hub fora → 503.
9. **Conversa.** Leitura síncrona do hub + mensagens ainda na outbox. Envio: `solicitacao_mensagem`
   (`id` = `interacao_id`, idempotente), publicado pelo job `enviar_mensagens` (20 s). **O texto é apagado da
   área quando o hub confirma** e, se falhar em definitivo, 7 dias depois. Limites na área: 1 a cada 30 s,
   10/h e 40/dia contados na outbox; o limite do hub (que soma o App) chega ao job como 429 `limite_titular`
   e adia tudo do contato pelo `Retry-After`, sem gastar tentativa.
10. **Catálogo ligado/desligado pelo CRM.** `solicitacao.produtos` em cache de 12 min; tipo com produto inativo
    some da tela e é recusado na criação (422 `servico_indisponivel`). No envio: 503 `produto_indisponivel` →
    mesmo `registro_id` sem `produto_id`; 422 `produto_inativo` → o pedido é cancelado pelo sistema com a
    mensagem pública (nova regra `criada → cancelada` por `sistema/job`).
11. **Sincronização** passa a conhecer 0/100000001 (respondido pelo associado → `em_atendimento`) e
    0/100000002 (respondido pela Central → `pendente_associado`).
12. **Texto ao CRM** nos tipos novos igual ao App: título = nome do tipo, descrição = texto do associado.
13. **Carência e unicidade** dos tipos novos iguais às do App (meses por tipo; um aberto por tipo, conferido
    também na lista do CRM, melhor esforço).

O que **não** muda: cancelamento pelo associado depois do envio continua 409 `na_central` (o hub não tem
ferramenta de status, P-74); `POST …/responder` vale só para pedido ainda não espelhado.

## Consequências

### Positivas
- Mesmo serviço e mesmo vocabulário nos dois canais; a conversa cruza canais.
- A APM liga e desliga serviço pelo CRM, sem deploy.
- O processo web continua sem credencial de escrita no CRM; nada do contrato de perfil mudou.
- A área não acumula texto de conversa: lê do CRM, guarda só o que ainda não saiu.

### Negativas / riscos
- A mensagem do associado sai em até ~20 s e depende de `JOBS_APLICAR=1`; a recusa do hub aparece depois,
  na conversa ("Não enviada"), não no envio.
- Cada abertura da lista custa até 50 linhas da cota PII do hub (mitigado pelo cache; P-79 pede cota maior).
- Status local e contador do menu seguem a cadência de 6 h; a tela mostra o par ao vivo (duas velocidades).
- Cache por processo (2 workers): catálogo e lista podem divergir por até o TTL.
- O limite por hora da área não enxerga as mensagens mandadas pelo App.
- Divergência com a spec v2 §8.5 (rótulos) e com a ADR-0023 item 4 (resposta pela área): registradas no
  levantamento (DIV-47 e DIV-48).

### Obrigações decorrentes
- `sql/016` (ENUM, `solicitacao_mensagem`, `solicitacao_leitura`, flag) com UPDATE por coluna e allowlist no
  `db_check`; job `enviar_mensagens` na tabela do `docs/JOBS.md`.
- Pendências: P-78 (grants), P-79 (cota PII da conta web), P-80 (rótulos de aberta/concluída/cancelada do
  App), P-81 (carências), P-82 (cancelar o ensaio `outro`), P-83 (merge de `feat/produto-oportunidade` no hub).
- Mudança de catálogo só junto com o App, combinada pelo William.
- Testes: `tests/test_paridade_unidades.py`, `tests/test_paridade_integracao.py`, `frontend/src/pages/Paridade.test.tsx`.

## Alternativas descartadas
- **Tudo pelo job** (proposta do hub): a tela leria cache local; o que vem do App e as respostas da Central
  apareceriam com o atraso do job e a cota seria gasta mesmo sem o associado abrir a tela.
- **Web escreve síncrono**: melhor experiência no erro, mas exige `ferramentas:escrever` na conta web antes
  da P-29 e um controle à parte para não ligar junto a edição de perfil; contraria ADR-0003/0019.
- **Pedir slugs novos ao hub/App** para declaração e cancelamento: depende de terceiro e de mudança no App.
- **Importar os registros do App para `solicitacao`**: copiaria texto do associado vindo de outro canal e
  criaria uma segunda fonte para o mesmo registro.
- **Guardar "visto em" no navegador** (como o App guarda no aparelho): a regra 13 proíbe dado em `localStorage`.

## Adenda — 2026-11-13, retorno do hub à resposta da área

O hub aceitou contas, grants e cota (30.000/dia na conta web) e confirmou a regra de situação. Ajustes
aprovados pelo William no mesmo dia, sem mudar as decisões acima:

- **Item 4 (rótulos):** o texto segue a **entidade**, não "quem responde": ocorrência → "a Central",
  oportunidade e entidade desconhecida → "a APM" (Defesa Profissional é ocorrência). Quem assina a conversa
  continua por tipo. Situação aberta = `aberta`, `em_andamento`, `aguardando_associado` (unicidade e caixa de envio).
- **Item 9 (conversa):** `interacoes_listar` com limite 20 (`HUB_CONVERSA_LIMITE`) e cache em memória de
  processo (`HUB_CONVERSA_TTL`); relê do hub só quando `ultima_interacao_em` da lista muda, quando o job acabou
  de publicar uma mensagem da área ou no "Atualizar conversa" (que relê a lista antes). O texto continua fora
  de banco e de log.
- **Bloqueio pela Central:** a lista não traz o bloqueio; a área o aprende no 403 `interacao_nao_permitida`
  (mensagem `falhou` na outbox) e esconde a caixa de envio daquele registro dali em diante.
- **Cota esgotada (429 `cota_pii_esgotada`):** só zera às 00:00 de Brasília e cada negação é auditada. As
  leituras pessoais da conta ficam suspensas por 15 min; escritas e `solicitacao.produtos` seguem. Na tela, a
  lista sai `parcial` e a conversa fica indisponível.
- **Cancelamento:** sem ferramenta no hub **por desenho**. Com o registro aberto, o associado pede o
  cancelamento pela conversa; fechado ou sem conversa, fala com a Central.
- **Unicidade em `outros`:** o App permite um registro aberto por slug; declaração, cancelamento da associação
  e o formulário da Ajuda vão como `outros` e, enquanto abertos, impedem "Outros assuntos" no App. Decisão do
  William: **aceitar** — nada muda na área (DIV-49).
- **Mapa de canal:** só `criar` e `interagir` dependem dele; a conta web fica fora (só lê).

## Adenda — 2026-11-13, adendo do hub: `pode_enviar_mensagem` na lista

`solicitacao.listar` passou a devolver `pode_enviar_mensagem` por registro. Substitui o item "Bloqueio pela
Central" da adenda anterior (decisão do William em 13/11):

- A caixa de envio aparece com a regra local **e** a coluna. Registro aberto com `false` mostra o texto do App
  ("Esta conversa foi encerrada pela Central. Para falar conosco, abra uma nova solicitação.").
- **A coluna manda**: o bloqueio deixou de ser definitivo na área, porque a Central pode desbloquear. O 403
  `interacao_nao_permitida` visto na outbox só vale quando a lista não respondeu, não trouxe o registro, não
  trouxe a coluna ou é anterior à falha (cobre o cache da lista).
- Sem migração e sem mudança no contrato da API (`pode_enviar`, `motivo_bloqueio = nao_permitida`).

Contato sintético dos ensaios desde 13/11: `1538029d-dbde-f111-84e8-7ced8db12239` (o anterior foi excluído do
CRM). O job de sincronização trata 404 `nao_encontrado` de `solicitacao.listar` como resposta definitiva sobre o
contato (divergência `nao_encontrada_no_crm`, segue a rodada), não como falha do hub.
