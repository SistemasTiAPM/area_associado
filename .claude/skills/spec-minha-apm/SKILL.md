---
name: spec-minha-apm
description: Mapa de conhecimento da Minha APM (área do associado da APM) — onde está cada regra, página, status, evento, gatilho e integração na especificação funcional v2 da agência (docs/spec-v2/), no REQUISITOS, nas ADRs, no levantamento técnico (TI-nn/EXT-nn/DIV-nn/DEC-nn) e no código; regra de precedência entre documentos e lista das decisões do usuário que não se reabrem. Use SEMPRE que um pedido citar uma página (P01–P17), módulo de backoffice (B01–B13), gatilho (A01–A20), tipo de ativação, status de solicitação, carência, elegibilidade, "meu valor", RD Station, CSV do parceiro, backoffice, ou perguntar "o que a spec diz", "o que já existe", "o que falta", "isso depende de terceiro?" — mesmo que a pessoa não diga "spec".
---

# Spec da Minha APM: onde cada coisa está

Este projeto tem **quatro camadas de documento** e cada uma responde a uma pergunta diferente. Ler
a camada errada custa retrabalho (a `SPEC-minha-apm.md` antiga descreve um protótipo com valores
ilustrativos; o `REQUISITOS` v0.2 já reflete a spec v2, mas o levantamento é quem diz o estado). Comece sempre pela tabela abaixo.

| Pergunta | Documento | Observação |
|---|---|---|
| O que o produto deve fazer (funcional, fases, regras de negócio, backoffice, eventos, gatilhos, integrações, RNF)? | `docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md` | Transcrição fiel do PDF da agência (30/09/2026). Âncoras: `#p04`, `#tipos-de-ativacao`, `#status-solicitacao`, `#elegibilidade`, `#carencias`, `#calculo-valor`, `#blocos-home`, `#recomendacao-v1`, `#modulos-backoffice`, `#perfis-backoffice`, `#eventos-de-uso`, `#indicadores`, `#gatilhos`, `#integracoes`, `#contrato-de-dados`, `#csv-plano-b`, `#rnf`, `#governanca`, `#raci`, `#lgpd`. |
| O que esse identificador significa e onde ele cai no nosso código? | `docs/spec-v2/INDICE-IDS.md` | P/B/A/tipos/status/blocos/eventos/códigos ACE/HOM/CAT/… → seção da spec → RF/ADR/arquivo. |
| Já existe? É só TI ou depende de terceiro? Qual persona? Que fase? | `docs/LEVANTAMENTO-TECNICO-spec-v2.md` | Listas **TI-nn** (sem dependência externa), **EXT-nn** (terceiro + o que fazer enquanto espera), **DIV-nn** (spec × decisão nossa), **DEC-nn** (decisão pendente). Seção 15 é a rastreabilidade. |
| Como a tela se comporta em detalhe (textos, estados, componentes) onde a spec v2 só resume? | `docs/SPEC-minha-apm.md` | Protótipo de 01/10. A seção "Fundação visual" é histórica (ADR-0017). Números em R$ e contagens são placeholders: **nunca** chegam ao associado (regra 19). |
| Requisito formal RF/RNF, modelo de dados, catálogo de eventos, lacunas LA-xx? | `docs/REQUISITOS-minha-apm.md` | **v0.2 (30/10)**, alinhado à spec v2: 177 RFs, 8 status, `sql/008..022`, allowlist por usuário, catálogo unificado de eventos. |
| Em que ordem fazer? O que já foi feito? | `docs/PLANO-EXECUCAO.md` | 7 ondas; Onda 1 feita em 30/10; Onda 2 = Fase 3 ampliada (ADR-0018..0021 já decidem a máquina de estados, jobs, limites e flags). |
| Por que decidimos assim? | `docs/adr/` (0001–0024) | Mudar decisão = ADR nova; nunca editar ADR aceita. 0018 solicitações v2 (8 status), 0019 jobs, 0020 limites, 0021 flags v2, 0022 usuário de banco do backoffice, 0023 espelho no CRM por incident/opportunity, 0024 paridade com o App APM (catálogo comum, lista dos dois canais, conversa). |
| O que está travado e com quem? O que já foi entregue? | `docs/PENDENCIAS.md` (P-xx) e `docs/CONCLUIDO.md` | Toda entrega atualiza os dois. |
| Como o hub entrega o cadastro? | `docs/CONTRATO-HUB.md` | Ferramentas `associado.*` por `contact_id`; nunca CPF. |
| Solicitações no CRM, catálogo de tipos, conversa com a Central? | `docs/CONTRATO-HUB.md` "Solicitações" + ADR-0023/0024 | Catálogo comum com o App APM (`catalogo_crm.py`; mudar só junto com o App, pelo William). Web só LÊ (`listar`, `interacoes_listar`, `produtos`); job escreve (`criar`, `interagir`). Rótulos do App em tudo que está no CRM (`situacao_crm.py`). Flag `solicitacoes_crm`. |

## Precedência quando dois documentos discordam

1. **Segurança** (Sentinela, `CLAUDE.md` Sessão 2) vence tudo.
2. **ADRs e decisões do usuário** (lista abaixo) vencem a spec quando a alteram explicitamente.
3. **Spec v2** vence no funcional (regras, fases, status, eventos, integrações).
4. **Mockups da agência** vencem no visual (ADR-0017, `frontend/src/styles/tokens.css`).
5. **SPEC antiga** só onde as anteriores não detalham.

Divergência nova entre spec v2 e nós → registra-se como `DIV-nn` no levantamento (§10) com quem
decide, impacto e recomendação. Não se "resolve" em código sem decisão registrada.

## Decisões do usuário que NÃO se reabrem (registre divergência, não proponha mudar)

- Sem login próprio: `/` vai direto ao Login APM (`login_associado`, OIDC + PKCE). A página P01
  da spec é o IdP; o que falta lá (data de nascimento, SMS) é tarefa no repositório do IdP.
- SPA React + Vite servida pelo FastAPI (ADR-0001); URLs reais, sem `localStorage` de rota.
- CRM e ERP **só** via `mcp_hub`; escrita por ferramenta tipada (ADR-0002); chave `contact_id`,
  nunca CPF (ADR-0014); token do hub só em memória.
- Paridade com o App APM (ADR-0024, 13/11): web lê o CRM e job escreve; tipos antigos fora do catálogo do App vão
  como `outros`; rótulos do App em tudo que está no CRM; tudo atrás da flag `solicitacoes_crm`.
- Solicitações em MySQL próprio com espelho no CRM (ADR-0003); UPDATE só por GRANT de tabela,
  DELETE nunca, trilhas append-only (ADR-0004); `evento_uso` catálogo fechado em transação própria
  (ADR-0012).
- WordPress por MySQL direto, usuário RO, **só no job**, com cache (ADR-0006).
- Flags nascem desligadas; desligada = 404 `recurso_desligado` + UI oculta (ADR-0007).
- Parceiros fora de escopo até ADR própria por parceiro (ADR-0009); ERP só leitura após parecer
  (ADR-0010); TotalPass leitura via hub + deep link (ADR-0008).
- CSP sem inline, sem CDN, fontes self-hosted (ADR-0013); mockups como visual (ADR-0017).
- Troca de e-mail com código + reautenticação (ADR-0015); persona incompleta recusa login
  (ADR-0016); validade da carteirinha omitida; sem sino de notificações até existir fonte.

## Rotina para responder "o que falta para X?"

1. `grep -n "<ID ou termo>" docs/spec-v2/INDICE-IDS.md` → seção da spec e item do levantamento.
2. Ler a seção da spec (âncora) e o item do levantamento (estado ✅ 🟡 ⬜ ⛔ ⚠️ 🔒, camadas, TI/EXT).
3. Confirmar no código o "existe hoje" (o levantamento cita `arquivo:linha`; verifique, pode ter
   mudado) — `app/api/v1/`, `app/dominio/`, `app/integracoes/`, `sql/`, `frontend/src/pages/`.
4. Separar na resposta: **TI pode fazer agora** (TI-nn sem pré-requisito aberto) × **espera
   terceiro** (EXT-nn, com dono e P-xx) × **decisão pendente** (DEC/DIV).
5. Se o pedido vira trabalho de fase, siga a skill `nova-fase-minha-apm`; se envolve fonte ou
   parceiro novo, a skill `integracao-terceiro-minha-apm`.

## Vocabulário que muda de nome entre documentos

| Spec v2 | Nosso código/REQUISITOS |
|---|---|
| Meu valor / Extrato de valor | "Fatura de valor", rota `fatura`, flag `fatura_valor` (renomear é TI-nn do levantamento) |
| `criada / enviada / em_atendimento / pendente_associado / concluida_positiva / concluida_negativa / cancelada / sem_retorno` | **adotados como nomes internos** (ADR-0018, 30/10): `sem_retorno` é coluna `sem_retorno_desde`, não status; a ADR-0003 vale para outbox/409 |
| eventos `beneficio_visto`, `solicitacao_criada`, `carteirinha_validada`… | `beneficio_abrir`, `solicitacao_criar`, `carteirinha_verificar`… (tabela completa em `INDICE-IDS.md`) |
| Categoria do associado (acadêmico, aspirante, efetivo, remido) | `tipo_associado` do claim `carteirinha` (rótulo do CRM) |
| Situação (ativo, suspenso, cancelado) | `status_associativo` (rótulo `alf_status_associativo`) |
| Identificador interno estável | `contact_id` (GUID do Dataverse) |
| Backoffice | não existe; decisão DEC no levantamento |

## Quando parar e perguntar

- O pedido contraria uma decisão da lista acima.
- O pedido exige dado que nenhuma fonte entrega (patrocínio, cashback, economia do clube, dados
  de cobrança além do F&O): isso é EXT ou DEC, nunca valor ilustrativo.
- A spec v2 e o mockup pedem coisas diferentes para a mesma tela e nenhuma ADR cobre.
