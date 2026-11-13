# Minha APM → Hub: resposta ao contrato de solicitações, mensagens e produto

> **Nota de 2026-11-13 (depois do envio):** o hub trocou o contato sintético. Onde este texto cita
> `8eb5da36-3847-ee11-be6f-00224837e097`, leia `1538029d-dbde-f111-84e8-7ced8db12239`. A `CAS-285559-X6N4J7`
> foi excluída junto com o contato antigo: o pedido de cancelamento manual do item 3 está encerrado.

(da sessão da área do associado, 2026-11-13. Responde ao §8 de "Hub → Minha APM: solicitações, mensagens e
produto (paridade com o App APM)". Decisões do William no mesmo dia; registro na área: ADR-0024.)

## 1. Qual conta chama cada ferramenta

A área separa leitura de escrita: **o processo web só lê; quem escreve é o serviço de jobs.**

| Conta | Escopos | Grants exatos pedidos | Para quê |
|---|---|---|---|
| `area-associado` (web) | `ferramentas:ler` (continua sem `escrever`) | `solicitacao.listar`, `solicitacao.interacoes_listar`, `solicitacao.produtos` | lista e detalhe na tela (os dois canais), conversa, catálogo |
| `area-associado-jobs` | `ferramentas:ler` + `ferramentas:escrever` | `solicitacao.criar` e `solicitacao.listar` (já tem), **`solicitacao.interagir`** (novo) | abertura, sincronização de status e envio das mensagens |

Pedidos junto com os grants:
- **Canal:** confirmar que as duas contas estão no mapa de canal (Minha APM / Web). A conta web só lê, mas se a
  leitura depender do mapa, ela precisa estar lá.
- **Escopo de escrita da conta de jobs:** na área ele foi provado em 04/11; o `PENDENCIAS.md` do hub ainda a
  descreve como só leitura — alinhar o texto.
- **Cota de dado pessoal da conta web:** hoje 5.000 linhas/dia. A lista do associado lê até 50 linhas por
  abertura (com cache de 60 s por associado) e a conversa 1 por mensagem. Pedimos **30.000/dia**, como a conta
  do App, para rever com o uso real. A conta de jobs fica como está (pedido anterior: 25.000/dia).
- **Produto:** confirmar que `produto_id` em `solicitacao.criar` e `solicitacao.produtos` já estão no ar (a
  pendência do hub citava a branch ainda sem merge).

Consequência para o associado: a mensagem escrita na Minha APM chega ao CRM em até ~20 segundos (fila da área),
não na hora. A tela mostra "Enviando…" até lá.

## 2. Slugs

Adotamos exatamente os do §2, inclusive `outros`.
- Os 15 tipos que a área não tinha passam a existir com o mesmo slug: `duvida`, `segunda_via_boleto`,
  `defesa_profissional`, `planos_de_saude`, os sete `seguro_*`, `assessoria_aposentadoria`, `contabilidade`,
  `despachante`, `apm_facilities` — com os assuntos, times e produtos da tabela.
- Tipos que só a área tem são traduzidos no envio: `outro` → `outros`; alteração de cadastro →
  `alteracao_cadastral`; declaração de associado, pedido de cancelamento da associação e os demais → `outros`
  (assunto "Atendimento APM"), com o nome real no título ("Minha APM: Declaração de associado").
- `seguros` (legado): não ofertamos; reconhecemos na lista e mantemos a conversa.
- Título e descrição nos tipos comuns: como o App (título = nome do tipo, descrição = o texto do associado).
- Rótulos de tela, agrupamento "Seguros", ordem e carência: os do App.

## 3. Como a área usa `solicitacao.criar` hoje

- Os jobs estavam no contrato de 04/11 (slug local, sem produto, só ocorrência). **A adaptação ao contrato novo
  está pronta no código** (slug do catálogo, `produto_id` em oportunidade, reenvio sem produto no 503
  `produto_indisponivel`, cancelamento do pedido no 422 `produto_inativo`, mensagens por `solicitacao.interagir`),
  ainda não implantada.
- O espelho está em simulação em produção desde 04/11: **nenhum pedido de associado foi ao CRM**.
- **Nada a migrar.** O único registro com o slug `outro` é o do ensaio de 04/11, ocorrência
  **`CAS-285559-X6N4J7`** (contato sintético; a segunda chamada foi a repetição do mesmo `registro_id`).
  Pedimos que a Central o **cancele à mão**.

## 4. Janela de teste

Do nosso lado, nesta ordem: migração `sql/016` → deploy com a paridade desligada → grants do item 1 → conferência
dos grants de leitura nas duas contas (só contagens) → ensaio com o contato sintético
`8eb5da36-3847-ee11-be6f-00224837e097`:
1. abrir "Seguro Auto" (oportunidade com produto) e "Dúvida" (ocorrência) pela Minha APM;
2. conferir os dois e os registros do App na lista;
3. trocar uma mensagem em cada;
4. William confere no CRM (tipo, Canal "Minha APM", Origem Web, produto na oportunidade, mensagens na Timeline),
   responde a uma delas e cancela os registros ao final.

Nunca usaremos CPF nem contato real em teste. Avisamos quando os três primeiros passos estiverem feitos para
combinar a janela.

## 5. Perguntas de volta

1. **Rótulos do App** para os estados "aberta", "concluída" e "cancelada": no servidor do App só encontramos os
   de "aguarda seu retorno" e "em andamento". Estamos com "Aberta", "Concluída" e "Cancelada" até recebermos os
   textos exatos.
2. **Carências e unicidade:** copiamos do App Defesa Profissional 3 meses, Assessoria para Aposentadoria 3,
   Contabilidade 2, Despachante 2 (demais sem carência) e "um pedido aberto por tipo". Confirmar que são os
   valores em produção.
3. **429 por cota esgotada** (`cota_pii_esgotada`) vem sem `Retry-After`: tratamos como 60 segundos. Se houver
   um valor melhor (ex.: até a virada do dia), avisem.
4. **Cancelamento pelo associado:** continua sem ferramenta? Hoje, depois que o pedido chega ao CRM, a tela
   manda o associado falar com a Central.
5. **Bloqueio de mensagens pela Central** só chega no envio (403). Como a área envia pela fila, o associado vê
   "Não enviada" depois. Se a lista puder trazer o bloqueio, escondemos a caixa de envio antes.
