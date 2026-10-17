# ADR-0010: ERP (F&O) somente leitura, via hub, após parecer de licença

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0002, ADR-0007

## Contexto

O financeiro da APM roda no Dynamics 365 Finance & Operations
(`apm.operations.dynamics.com`, OData com `cross-company=true`, `dataAreaId = 'apm'`). As
entidades relevantes, já usadas pelo projeto `totalpass`, são `CustomersV3` (cliente
identificado por CPF no formato `999999999-99` em `BrazilianCNPJOrCPF`), `CustTransactions`
(lançamentos) e `SalesInvoiceV4Lines` (linhas de fatura). **Não existe vínculo técnico entre o
`contact` do CRM e o cliente do ERP**; a única chave comum é o CPF.

Há uma pendência formal de **parecer sobre licenciamento e multiplexação** antes de exibir dados
do F&O a usuários finais por meio de outra aplicação
(`/home/ubuntu/totalpass/docs/RUNBOOK_ERP_FO.md:205-211`, pendência P-08). Exibir faturas a
milhares de associados sem esse parecer pode caracterizar acesso indireto não licenciado.

Além disso, a semântica contábil não é trivial: uma "fatura aberta" em `CustTransactions` nem
sempre significa "não paga" (compensações, boletos em trânsito, parcelamento). A spec mostra
"fatura" e "mensalidade" de forma simplificada.

## Decisão

1. **ERP é somente leitura. Nunca escrita.** Nenhuma ferramenta `financeiro.*` de escrita será
   criada no hub, e a área não terá rota que altere qualquer dado financeiro.
2. O acesso é **exclusivamente pelo `mcp_hub`** (ADR-0002), por ferramentas `financeiro.*`
   (`financeiro.situacao_consultar`, `financeiro.faturas_listar`) que aceitam **`contact_id`**;
   a resolução `contact_id → CPF → cliente F&O` ocorre **dentro do hub** (P-04). O CPF nunca
   chega à área (ADR-0014).
3. Toda a funcionalidade fica atrás da flag **`erp_financeiro`** (ADR-0007), que nasce
   desligada e **só pode ser ligada após P-08** (parecer favorável registrado no
   `docs/PROVISIONAMENTO.md`, com data e responsável).
4. A implementação na área é alocada à **Fase 7** do plano; até lá só existe o contrato de API
   (`app/api/financeiro.py` com rotas que respondem 404 `recurso_desligado`) e os tipos no
   front.
5. **Isolamento por associado**: o hub só devolve dados do cliente resolvido a partir do
   `contact_id` da sessão; a área nunca aceita CPF, cliente ou `contact_id` como parâmetro da
   requisição. Teste de isolamento obrigatório (associado A não enxerga fatura de B).
6. Semântica apresentada ao associado é a definida em P-10: a área exibe "situação"
   (`em dia`, `pendência em análise`, `consulte o financeiro`) derivada por regra no hub, e
   **não** expõe saldo bruto de `CustTransactions` sem essa regra.
7. Cache de leitura de 15 min por `contact_id` no hub (não na área), para proteger o F&O e
   respeitar cotas (P-03).

## Consequências

### Positivas
- Risco de licenciamento tratado antes de qualquer exposição.
- Nenhum SDK, credencial ou esquema do F&O na área.
- Interpretação contábil concentrada no hub, com regra única para todos os consumidores.

### Negativas / riscos
- A tela financeira da spec fica desligada até P-08 e Fase 7; o associado não verá faturas
  no lançamento.
- Dependência do mapeamento CPF↔cliente no hub; CPF com cadastro duplicado no F&O precisa de
  regra de desempate (definida no hub, não aqui).
- Se o parecer for desfavorável, a funcionalidade será removida e a flag permanece desligada
  definitivamente.

### Obrigações decorrentes
- P-08 registrado antes de `UPDATE feature_flag SET ligada=1 WHERE chave='erp_financeiro'`.
- Hub: ferramentas `financeiro.*` com `efeito=leitura`, `contact_id` como entrada, regra de
  "situação" e cache de 15 min.
- Testes: flag desligada → 404; isolamento por associado; rota rejeita qualquer parâmetro de
  identidade; nenhum valor bruto exibido sem regra.
- P-10: definição de "situação" financeira com o setor responsável.

## Alternativas descartadas

- **Acessar o F&O diretamente da área.** Criaria credencial OData no container, duplicaria o
  cliente do `totalpass` e espalharia a lógica contábil.
- **Exibir antes do parecer, com aviso.** O risco é contratual, não de UX; um aviso não
  resolve exposição indireta não licenciada.
