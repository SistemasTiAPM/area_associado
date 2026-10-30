# ADR-0020: Limites de negócio por contagem no banco; janela por minuto em memória; sem Redis

- **Status:** Aceita
- **Data:** 2026-10-30
- **Decisores:** Sistemas TI (William) · Claude Code (Maestro/Sentinela)
- **Relacionadas:** ADR-0004, ADR-0011, ADR-0015

## Contexto

`app/limites.py` implementa janela deslizante **em memória, por processo**; com 2 workers Uvicorn o teto
efetivo dobra (contato 10/h, foto 5/h, `/uso` 60 lotes/min). Era aceitável para abuso por minuto. A Fase 3
traz tetos **de negócio** que precisam ser exatos e compartilhados: solicitação `outro` 5/dia, um pedido de
cancelamento aberto por associado, uma avaliação por solicitação, dispensa de recomendação 20/dia,
exportação de dados 1 a cada 7 dias, consentimentos 20/h (`docs/LEVANTAMENTO-TECNICO-spec-v2.md` §12.1
TI-08; `docs/spec-v2/personas/sentinela.md` "Limites de taxa novos por rota"; DEC-13).

## Decisão

1. **Tetos diários ou por entidade** são verificados por **contagem no banco, na própria transação** do
   negócio (índice `(contact_id, criada_em)` ou único parcial), exatos e compartilhados entre workers;
   helper único em `app/dominio/limites_negocio.py` (`contar_no_periodo`, `exigir_unico_aberto`).
2. **Operações sensíveis não dependem de contador**: unicidade no banco (um pedido de cancelamento
   aberto, uma avaliação por solicitação, um pedido de exclusão aberto) + step-up por `idp_at`
   (`exigir_reautenticacao`, ADR-0015 generalizada).
3. **Abuso por minuto** continua com `LimiteJanela` em memória por processo (documentado "× 2 workers") e
   com `limit_req` do porteiro por IP; zonas novas por grupo de rota (`area_solicitacoes`,
   `area_privacidade`) com 429 e `Retry-After`.
4. **Sem Redis** nem serviço novo: a stack fica em MySQL + memória de processo.

## Consequências

### Positivas
- Exatidão onde importa (dinheiro, LGPD, atendimento) sem componente novo.
- Defesa em profundidade: unicidade + step-up + contador + porteiro.

### Negativas / riscos
- Uma consulta a mais por escrita de negócio (barata com índice).
- Tetos por minuto continuam aproximados (aceito).

### Obrigações decorrentes
- Helper e testes (contagem no limite, concorrência, índice presente) na Fase 3 (TI-08).
- Tabela de limites por rota em `docs/REQUISITOS-minha-apm.md` v0.2 (RNF-05).

## Alternativas descartadas
- **Redis**: serviço novo com porta, memória e segredo, para um problema que o banco resolve.
- **Tabela de janelas no MySQL para tudo**: uma escrita por requisição, inclusive para `/uso`.
