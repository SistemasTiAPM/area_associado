# ADR-0018: Solicitações v2 — oito status da spec, marcador `sem_retorno` e atores

- **Status:** Aceita — o espelho no CRM e o item 6 (P-66) foram alterados pela [ADR-0023](0023-espelho-de-solicitacoes-por-incident.md) em 2026-11-04
- **Data:** 2026-10-30
- **Decisores:** Sistemas TI (William) · Claude Code (Maestro/Atlas/Sentinela)
- **Relacionadas:** ADR-0003 (adenda aos itens 1–3; o resto da 0003 continua válido), ADR-0004, ADR-0009, ADR-0014

## Contexto

A especificação funcional v2 da agência (`docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md` §8.5, P05)
define **oito status internos** para a solicitação — `criada`, `enviada`, `em_atendimento`,
`pendente_associado`, `concluida_positiva`, `concluida_negativa`, `cancelada` e o marcador `sem_retorno` —
com rótulos ao associado, quem pode mudar cada um, log imutável "com conteúdo enviado", mudança manual
com justificativa, avaliação de 0 a 10 depois de concluída e cancelamento "enquanto o parceiro ainda não
atendeu". A ADR-0003 (16/10) desenhou seis estados (`aberta`, `em_analise`, `aguardando_associado`,
`concluida`, `recusada`, `cancelada`) e sete tipos fechados sem vínculo com benefício ou parceiro. A tabela
`solicitacao` ainda não existe (`sql/` vai até a 007): não há dado legado. O levantamento registrou a
divergência (`docs/LEVANTAMENTO-TECNICO-spec-v2.md` DIV-15, DIV-16, DIV-24, DIV-26; DEC-01, DEC-02, DEC-04,
DEC-22).

## Decisão

1. **Nomes internos = nomes da spec**, já na migração `sql/010_solicitacao.sql`: `criada`, `enviada`,
   `em_atendimento`, `pendente_associado`, `concluida_positiva`, `concluida_negativa`, `cancelada`.
   Mapeamento da ADR-0003: `aberta→criada`, `em_analise→em_atendimento`, `aguardando_associado→
   pendente_associado`, `concluida→concluida_positiva`, `recusada→concluida_negativa`.
2. **`enviada` é status de negócio**, promovido pelo sistema quando o canal confirma: `canal_envio=crm` ⇒
   espelho ok (`crm_sync=ok`); `relatorio`/`email` ⇒ marcação pelo atendimento (backoffice ou CRM);
   `api`/`portal` (F2) ⇒ confirmação do parceiro. O rótulo ao associado varia por `tipo_ativacao` (tipo 3:
   "Encaminhada à equipe"). A **falha** do espelho continua invisível (RF-SO-06).
3. **`sem_retorno` não é status**: é a coluna `sem_retorno_desde DATETIME NULL`, posta por job quando
   `enviada_em + prazo_retorno_dias < agora` e status ∈ {`enviada`, `em_atendimento`}, limpa em qualquer
   transição; gera evento `sem_retorno` em `solicitacao_evento`, gatilho A05 e item no painel; o segundo
   vencimento gera `sem_retorno_2` (fila de ligações).
4. **Atores e origens** em `solicitacao_evento`: `ator ENUM(associado, sistema, parceiro, apm, importacao)`,
   `origem ENUM(ui, job, crm, backoffice, importacao, api_parceiro, portal_parceiro)`, `justificativa`
   obrigatória (CHECK) quando `origem='backoffice'`, `usuario_interno` quando houver.
5. **"Conteúdo enviado" = `campos_enviados` (lista de nomes) + `sha256` do payload + `destino` + `canal`**,
   nunca o payload (minimização; `solicitacao.dados` continua na tabela principal com CHECK anti-CPF).
6. **Transições** (UPDATE condicional `WHERE status = :de` + INSERT no log, mesma transação; zero linhas ⇒
   409 `estado_invalido`): `—→criada` (associado · ui) · `criada→enviada` (sistema · job | apm · backoffice)
   · `criada|enviada→em_atendimento` (parceiro/apm · crm/backoffice/api/portal) · `em_atendimento→
   pendente_associado` (mensagem pública obrigatória) · `pendente_associado→em_atendimento` (associado
   responde) · `enviada|em_atendimento→concluida_positiva|concluida_negativa` (parceiro/importação/apm) ·
   `criada|enviada|pendente_associado→cancelada` (associado; **nunca** a partir de `em_atendimento`) ·
   qualquer não terminal `→cancelada` (apm com justificativa). Terminais não mudam; CRM concluindo algo
   cancelado localmente: o terminal local prevalece e a divergência vai para `evento_log`.
7. **Vínculo com o catálogo**: `beneficio_id`, `parceiro_id`, `tipo_ativacao` (2, 3, 4, 5) desnormalizados
   na solicitação; `tipo_servico` ENUM (os sete da ADR-0003 + `declaracao_associado`,
   `cancelamento_associacao`, `exclusao_dados`) para pedidos sem benefício; `canal_envio`,
   `prazo_retorno_dias` (copiado do parceiro/benefício/`parametro` na criação), `enviada_em`,
   `responsavel`, `resultado JSON` (alimenta `uso_valor`), `chave_idempotencia`.
8. **Tipo 2 (encaminhamento ao parceiro) na F1 é solicitação local** com `canal_envio` `relatorio`/`email`
   operado pela APM — nenhuma chamada HTTP a parceiro (ADR-0009 mantida). Dados do associado só vão ao
   parceiro por e-mail com allowlist de campos por benefício e aprovação do encarregado de dados; o alvo é
   o parceiro consultar no `apm-parceiros` pelo número da solicitação.
9. **Avaliação 0–10** em colunas da própria solicitação (`avaliacao_nota`, `avaliacao_comentario` ≤ 500,
   `avaliada_em`), uma vez (`WHERE avaliada_em IS NULL`), aceita até `parametro.avaliacao_prazo_dias`
   (padrão 30) após `concluida_em`; evento `solicitacao_avaliar`.
10. `crm_sync ENUM(pendente, ok, erro, falhou)` (quatro valores; a ADR-0003 dizia três) continua camada
    técnica; mapeamento da `task` do CRM mantido com os nomes novos; **P-06 precisa distinguir "não seguiu"
    de "cancelada pela APM"** (a `task` não distingue).

## Consequências

### Positivas
- Uma única fonte de nomes (banco = spec = backoffice = indicadores 5–7); sem migração de status depois.
- `enviada` e `sem_retorno` dão ao associado o que a spec promete ("Enviada ao parceiro", "a APM já está
  cobrando") sem expor falha técnica.
- Rastro completo com justificativa para mudança manual; conteúdo enviado provado sem replicar PII.

### Negativas / riscos
- Status `enviada` com canal manual depende de alguém marcar (backoffice ou CRM): sem isso, tudo fica
  `criada` e o marcador dispara contra a própria APM. Mitigação: `prazo_retorno` conta a partir de
  `enviada_em`; `canal=crm` promove automaticamente.
- Mais colunas e CHECKs na `solicitacao`; mais transições para testar.

### Obrigações decorrentes
- `sql/010_solicitacao.sql` com `GRANT UPDATE` justificado em `solicitacao`, `solicitacao_evento` só
  INSERT, índices `(contact_id, status)`, `(crm_sync, crm_proxima_em)`, `(status, enviada_em)`,
  `(parceiro_id, criada_em)`, único `(contact_id, chave_idempotencia)`; CHECK do marcador e da justificativa.
- `app/dominio/solicitacoes/maquina.py` com a tabela de transições como única fonte; testes de tabela
  (válidas, inválidas, concorrência, isolamento por `contact_id`, marcador, avaliação).
- Ações no catálogo de `app/uso.py`: `solicitacao_criar(tipo_ativacao, beneficio)`,
  `solicitacao_status_alterado(de, para, origem)`, `solicitacao_avaliar`, `cancelamento_pedir`.
- `docs/REQUISITOS-minha-apm.md` §7 v0.2 e `docs/CONTRATO-HUB.md` (ferramentas `solicitacao.*`, P-06).

## Alternativas descartadas
- **Manter os seis estados e traduzir na API.** Deixaria `enviada` e `sem_retorno` sem lugar e duas
  linguagens (banco × backoffice × spec) para o mesmo fato.
- **`sem_retorno` como status.** Estado de ida e volta que explodiria as transições; a própria spec o chama
  de marcador.
- **Payload completo no log imutável.** Replica dado pessoal em trilha de guarda longa, contra a ADR-0014 e
  a minimização do §11.6 da spec.
