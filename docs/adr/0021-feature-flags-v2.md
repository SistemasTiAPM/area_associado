# ADR-0021: Feature flags v2 — chaves novas da spec v2 (adenda à ADR-0007)

- **Status:** Aceita
- **Data:** 2026-10-30
- **Decisores:** Sistemas TI (William) · Claude Code (Maestro)
- **Relacionadas:** ADR-0007 (mantida integralmente), ADR-0009, ADR-0012

## Contexto

A ADR-0007 fixou oito chaves fechadas (`mensalidade_zero`, `fatura_valor`, `patrocinio`, `clube_economia`,
`comunidade_posts`, `wallet`, `erp_financeiro`, `totalpass`), todas nascendo desligadas, desligada = 404
`recurso_desligado` + UI oculta. A spec v2 §14 pede chave para "mensalidade patrocinada, cartão, comunidade
e **novos tipos de ativação**", e o levantamento identificou funcionalidades com dependência externa ou
decisão pendente que precisam nascer desligadas (`docs/LEVANTAMENTO-TECNICO-spec-v2.md` §9, TI-13).

## Decisão

1. **Chaves novas** no enum de `app/flags.py` e no seed `sql/009_flags_v2.sql` (todas `ligada=0`):
   - `notificacoes` — P15 (rotas `/notificacoes`, contador em `/sessao`, sino); pré-requisito: fonte e
     aceite visual (DEC-08).
   - `encaminhamento_parceiro` — ativação tipo 2 (`POST /beneficios/{slug}/ativar` em benefício com
     `tipo_ativacao=2`); pré-requisito: ADR-0018 item 8 e, para API, ADR por parceiro (ADR-0009).
   - `reservas` — tipo 4; pré-requisito: fonte de disponibilidade.
   - `inscricoes` — tipo 5 real (sem a flag, inscrição = interesse local); pré-requisito: F0-01.
   - `comunicacao_outbox` — job que **envia** a outbox ao RD Station; a outbox é produzida sempre.
   - `cancelamento_online` — `POST /ajuda/cancelamento` (P14); decisão de negócio para ligar.
   - `lgpd_consentimentos` — consentimentos, exportação e exclusão (P13); pré-requisito: textos do
     jurídico (P-54).
2. **`fatura_valor` mantém a chave**; o rótulo na UI passa a "Meu valor" (título "Extrato de valor"). Sai de
   `FLAGS_FORCAR_DESLIGADAS` quando `app/dominio/valor.py` e `valor_referencia` aprovada existirem (DEC-23).
3. **Não se cria flag** para núcleo da F1 (catálogo, solicitações, trilha, FAQ, preferências): entram por
   fase, não por chave.
4. Tudo o mais da ADR-0007 vale: leitura com cache de 60 s, entrega em `GET /sessao`, override só para
   desligar, dados ilustrativos nunca em produção, `docs/PROVISIONAMENTO.md` com o SQL de ligar.

## Consequências

### Positivas
- Cada dependência externa isolada atrás de uma chave; o produto sobe inteiro e liga por partes.

### Negativas / riscos
- Mais componentes "mortos" até ligar; exigem testes com a flag ligada e fixtures (já é obrigação da 0007).

### Obrigações decorrentes
- `sql/009_flags_v2.sql` (INSERT idempotente, só `descricao` atualizável, sem GRANT), espelho em
  `frontend/src/api/tipos.ts`, `docs/PROVISIONAMENTO.md` com a ADR exigida por chave.
- Testes: chave desconhecida falha no boot; cada rota nova sob flag → 404 quando desligada.

## Alternativas descartadas
- **Chave nova `meu_valor`** no lugar de `fatura_valor`: migração e renomeação sem ganho funcional.
- **Flag para solicitações/catálogo**: são o produto; ligar "por partes" aí vira meia-entrega.
