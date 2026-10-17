# ADR-0007: Feature flags para funcionalidades sem fonte de dados

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0010

## Contexto

A spec "Minha APM" apresenta funcionalidades cujos dados **não existem em nenhum sistema da
APM** hoje: "Mensalidade Zero", patrocínio por empresas, "fatura de valor" (quanto o associado
recebeu em benefícios), cashback, "economia do Clube" e posts de comunidade. O levantamento
cobriu CRM, ERP, TotalPass e site e não encontrou fonte para nenhum deles. A spec usa valores
ilustrativos (R$ 2.480 de valor recebido, R$ 70 de cashback, 60% de economia) que não podem ir ao
ar como se fossem reais.

Ao mesmo tempo, o usuário quer a interface implementada com fidelidade, para que essas áreas
sejam ligadas quando as fontes existirem (pendências P-10 definições de negócio, P-12 fonte de
patrocínio, P-13 wallet, P-08 parecer do ERP). Omitir os componentes agora e reconstruí-los depois
gera retrabalho; exibi-los com dados falsos engana o associado.

O ERP financeiro (ADR-0010) e o TotalPass (ADR-0008) também precisam poder ser desligados sem
deploy, por dependerem de pendências externas (parecer de licença, provisionamento do hub).

## Decisão

1. Tabela `area_associado.feature_flag` (`chave VARCHAR(64) PK`, `ligada TINYINT NOT NULL
   DEFAULT 0`, `descricao VARCHAR(255)`, `atualizada_em`). A **aplicação só lê**; quem liga ou
   desliga é o operador por SQL (`UPDATE` administrativo, fora de `apm_area` — ADR-0004).
2. Override de emergência em `Settings`: `FLAGS_FORCAR_DESLIGADAS` (lista separada por
   vírgula). Uma chave listada ali é tratada como desligada **independentemente** do banco; não
   existe override para ligar.
3. Chaves fechadas (enum no código, `app/flags.py`): `mensalidade_zero`, `fatura_valor`,
   `patrocinio`, `clube_economia`, `comunidade_posts`, `wallet`, `erp_financeiro`, `totalpass`.
   Chave fora da lista → erro de configuração no boot. **Todas nascem desligadas** na migração.
4. **Flag desligada** significa:
   - API: rotas sob a funcionalidade respondem **404 `recurso_desligado`** (não 403, para não
     revelar existência);
   - UI: o componente **não é renderizado** — card, *pill*, rodapé da sidebar, item de menu,
     *asides* e atalhos no onboarding; nada de "em breve" nem valores de exemplo.
5. As flags são lidas do banco com **cache em memória de 60 s** por worker e entregues ao
   front em `GET /api/v1/sessao` (campo `flags: {chave: bool}`), junto com a identidade. O
   front nunca consulta flag separadamente.
6. Flag ligada **não** dispensa a fonte real: ligar `fatura_valor` exige a implementação que a
   calcula a partir de `evento_uso` (ADR-0012) e das definições de P-10; a migração que a
   habilita referencia a ADR correspondente.
7. Dados de exemplo da spec vivem **só** em `frontend/src/mocks/` e nos fixtures de
   `HUB_MODE=stub`; nunca em código de produção nem em seed do banco.

## Consequências

### Positivas
- A UI completa é construída uma vez e ligada por partes, sem deploy.
- Nenhum valor ilustrativo chega ao associado.
- Kill switch imediato (`FLAGS_FORCAR_DESLIGADAS` + restart) para qualquer funcionalidade com
  dependência externa instável (ERP, hub, TotalPass).

### Negativas / riscos
- Componentes atrás de flag desligada são código "morto" até a fonte existir; precisam de
  testes com a flag ligada e fixtures para não apodrecer.
- Cache de 60 s significa que ligar/desligar leva até 1 min para refletir em todos os workers
  (aceito).
- Risco de alguém ligar uma flag sem a fonte pronta: mitigado pelo item 6 e por o `UPDATE` ser
  ato administrativo documentado no `docs/PROVISIONAMENTO.md`.

### Obrigações decorrentes
- Migração `sql/00N_feature_flag.sql` (sem `GRANT UPDATE` para `apm_area`: só leitura).
- `docs/PROVISIONAMENTO.md`: seção "Ligar uma funcionalidade" com o SQL e a ADR exigida por
  chave.
- Testes: rota com flag desligada → 404; `FLAGS_FORCAR_DESLIGADAS` vence o banco; `/api/v1/sessao`
  reflete o estado; chave desconhecida falha no boot; e2e com cada flag ligada renderizando o
  componente.
- P-08, P-10, P-12, P-13 como pré-requisito de cada chave correspondente.

## Alternativas descartadas

- **Mock com selo "em breve".** Mesmo com selo, valores como "R$ 2.480 recebidos" seriam lidos
  como reais pelo associado e gerariam contato com o atendimento.
- **Omitir a UI até existir fonte.** Perde a fidelidade à spec e obriga a reconstruir
  componentes e layout quando a fonte chegar.
