# Registros de Decisão de Arquitetura (ADR) — area_associado

Decisões de arquitetura da Área do Associado da APM (`minha.apm.org.br`), tomadas durante o
planejamento da interface "Minha APM" (`docs/SPEC-minha-apm.md`). Cada ADR é imutável depois de
aceita: mudança de rumo gera uma ADR nova que **substitui** a anterior (status `Substituída por
ADR-xxxx`), nunca edição retroativa.

Pendências referenciadas (P-xx) estão no plano de implementação; as regras citadas são as do
`CLAUDE.md` do projeto.

## Índice

| Nº | Título | Status | Data |
|----|--------|--------|------|
| [ADR-0001](0001-spa-react-vite-servida-pelo-fastapi.md) | SPA React + Vite servida pelo FastAPI | Aceita | 2026-10-16 |
| [ADR-0002](0002-d365-via-mcp-hub-leitura-e-escrita.md) | Dynamics 365 somente via mcp_hub (leitura e escrita) | Aceita | 2026-10-16 |
| [ADR-0003](0003-solicitacoes-mysql-proprio-com-espelho-crm.md) | Solicitações em MySQL próprio com espelho no CRM | Aceita | 2026-10-16 |
| [ADR-0004](0004-grant-update-por-tabela-sem-delete.md) | GRANT UPDATE por tabela, nunca DELETE | Aceita | 2026-10-16 |
| [ADR-0005](0005-foto-de-perfil-entityimage-redimensionada.md) | Foto de perfil em `contact.entityimage`, redimensionada no servidor | Aceita | 2026-10-16 |
| [ADR-0006](0006-site-wordpress-leitura-direta-com-cache-local.md) | Site WordPress por leitura direta do MySQL, com cache local | Aceita | 2026-10-16 |
| [ADR-0007](0007-feature-flags-para-patrocinio-e-fatura.md) | Feature flags para funcionalidades sem fonte de dados | Aceita | 2026-10-16 |
| [ADR-0008](0008-totalpass-leitura-via-hub-e-deep-link.md) | TotalPass por leitura via hub e deep link, sem escrita | Aceita | 2026-10-16 |
| [ADR-0009](0009-parceiros-fora-de-escopo.md) | Integrações com parceiros fora de escopo nesta versão | Aceita | 2026-10-16 |
| [ADR-0010](0010-erp-somente-leitura-pos-parecer.md) | ERP (F&O) somente leitura, via hub, após parecer de licença | Aceita | 2026-10-16 |
| [ADR-0011](0011-cookie-de-sessao-cifrado.md) | Cookie de sessão cifrado | Aceita (2026-10-17) | 2026-10-16 |
| [ADR-0012](0012-analytics-evento-uso-transacao-propria.md) | Analytics em `evento_uso` com transação própria | Aceita | 2026-10-16 |
| [ADR-0013](0013-csp-sem-inline-no-spa.md) | CSP sem inline no SPA | Aceita | 2026-10-16 |
| [ADR-0014](0014-chave-de-integracao-contact-id-nunca-cpf.md) | Chave de integração é `contact_id`, nunca CPF | Aceita | 2026-10-16 |
| [ADR-0015](0015-troca-de-email-com-codigo-e-reautenticacao.md) | Troca de e-mail com código e reautenticação | Aceita | 2026-10-17 |
| [ADR-0016](0016-persona-incompleta-recusa-login.md) | Cadastro sem tipo ou situação recusa o login | Aceita | 2026-10-17 |
| [ADR-0017](0017-mockup-da-agencia-como-referencia-visual.md) | Mockups da agência como referência visual | Aceita | 2026-10-20 |

## Mapa de dependências

```
0001 SPA ──────────────── 0013 CSP ──── 0006 WordPress
0002 Hub ──┬── 0003 Solicitações ── 0004 UPDATE por tabela ── 0012 evento_uso
           ├── 0005 Foto
           ├── 0008 TotalPass
           ├── 0010 ERP ──── 0007 Flags ──── 0009 Parceiros
           └── 0014 contact_id ── 0011 Cookie cifrado
```

## Status possíveis

- **Proposta** — em discussão; não orienta implementação até ser aceita.
- **Aceita** — vigente; o código deve refletir a decisão.
- **Substituída por ADR-xxxx** — mantida por histórico; a nova ADR é a vigente.
- **Rejeitada** — registrada para que a alternativa não seja reavaliada sem fato novo.

## Como criar uma ADR

1. Próximo número sequencial (`NNNN`), nome de arquivo em *kebab-case* sem acentos:
   `NNNN-titulo-curto.md`.
2. Preencher o template abaixo. Contexto cita **arquivos e linhas** do levantamento; Decisão
   usa frases afirmativas; Consequências listam obrigações verificáveis (pendências, regras do
   `CLAUDE.md`, testes).
3. Adicionar a linha no índice acima.
4. Uma ADR que altera regra do `CLAUDE.md` lista essa atualização em "Obrigações decorrentes";
   o `CLAUDE.md` é atualizado no mesmo conjunto de mudanças.
5. Integração com parceiro novo (ADR-0009) usa este mesmo template, definindo o
   `tipo_ativacao`, a autenticação, a trilha e os limites de chamada.

## Template

```markdown
# ADR-NNNN: <título>

- **Status:** Aceita
- **Data:** AAAA-MM-DD
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-xxxx, ...

## Contexto
<2–4 parágrafos: situação, restrições, fatos do levantamento com caminhos de arquivo>

## Decisão
<o que foi decidido, em frases afirmativas; detalhes técnicos concretos>

## Consequências
### Positivas
### Negativas / riscos
### Obrigações decorrentes
<o que precisa existir: pendências P-xx, regras do CLAUDE.md, testes>

## Alternativas descartadas
<cada alternativa com 1–2 frases de por que não>
```
