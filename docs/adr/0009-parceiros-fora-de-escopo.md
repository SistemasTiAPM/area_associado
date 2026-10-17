# ADR-0009: Integrações com parceiros fora de escopo nesta versão

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0007

## Contexto

A spec "Minha APM" exibe um Clube de Benefícios com ofertas de parceiros (descontos, cupons,
resgates). O usuário indicou que integrações com parceiros serão tratadas **sob demanda**, caso a
caso, e não como requisito desta versão. O levantamento não identificou se os parceiros possuem
APIs, quais autenticações usariam, nem contratos que definam responsabilidade por resgate.

Hoje as ofertas do Clube são publicadas em `clubapm.com.br` (plataforma Clube Certo), um sistema
de terceiro com login próprio. O projeto `apm-parceiros` administra o cadastro de parceiros, mas
não expõe mecanismo de resgate.

Construir um conector genérico de parceiros sem nenhum parceiro concreto criaria abstração sem
requisito e sem forma de testar.

## Decisão

1. **Nenhuma integração com parceiro** é construída nesta versão. Não há chamada HTTP de
   saída para domínios de parceiros a partir da área nem do serviço de jobs.
2. O componente `OfertaClube` é alimentado por **seed estático** em
   `area_associado.oferta_clube` (`id`, `parceiro`, `titulo`, `descricao`, `url_externa`,
   `categoria`, `ativa`, `valida_ate`), mantido pelo operador por migração `sql/`; cada
   oferta tem apenas um **link externo** (`clubapm.com.br` ou página do parceiro), aberto em
   nova aba com `rel="noopener noreferrer"`.
3. O clique registra `clube.oferta_usar` em `evento_uso` (ADR-0012) com `entidade='oferta'`,
   `entidade_id=<id>`. Esse registro é o dado de "resgate" disponível para a futura "economia do
   Clube" (flag `clube_economia`, ADR-0007) e para negociar com parceiros.
4. Cada parceiro futuro entra por **ADR própria**, que define um novo valor de
   `beneficio.tipo_ativacao` (ex.: `parceiro_x_api`, `cupom_estatico`), a autenticação, a trilha
   e os limites de chamada. Nenhuma integração nasce "por configuração" sem ADR.
5. URLs externas das ofertas são validadas na migração e no boot: esquema `https`, host em
   allowlist `PARCEIROS_HOSTS` (`Settings`); URL fora da lista → oferta ignorada e evento
   `clube.oferta_url_invalida` em `evento_log`.

## Consequências

### Positivas
- Escopo fechado e entregável; nenhum acordo com terceiro bloqueia a versão.
- O dado de uso (`clube.oferta_usar`) começa a ser coletado desde o primeiro dia.
- Nenhuma credencial de parceiro no container.

### Negativas / riscos
- O Clube na área é uma vitrine com links; a experiência de resgate acontece fora
  (`clubapm.com.br`), com login separado.
- Seed estático exige migração para cada oferta nova ou expirada; aceito pelo volume baixo.
  Se virar operação frequente, uma ADR futura decide um cadastro via `apm-parceiros`.
- "Economia do Clube" fica desligada até existir definição de valor por oferta (P-10).

### Obrigações decorrentes
- Migração `sql/00N_oferta_clube.sql` (sem `GRANT UPDATE`: cadastro só por migração).
- `PARCEIROS_HOSTS` em `Settings`, validado contra URLs da seed no boot.
- Testes: oferta expirada não aparece; URL fora da allowlist ignorada; evento gravado no clique;
  `rel` no e2e.
- Modelo de ADR para "novo parceiro" referenciado no `docs/adr/README.md`.

## Alternativas descartadas

- **Conector genérico de parceiros (adapter + configuração).** Não existe requisito, parceiro
  concreto, contrato nem API conhecida para validar a abstração; seria código especulativo com
  superfície de rede nova.
