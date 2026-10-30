# Análises por persona (anexos do levantamento da spec v2)

Relatórios brutos produzidos em 2026-10-29 por seis análises paralelas (uma por persona do
`CLAUDE.md`), consolidados em [`../../LEVANTAMENTO-TECNICO-spec-v2.md`](../../LEVANTAMENTO-TECNICO-spec-v2.md).
Os identificadores aqui são **provisórios por persona** (`TI-S01`, `EXT-A02`, `DIV-V03`, `DEC-M05`…); os
definitivos (`TI-nn`, `EXT-nn`, `DIV-nn`, `DEC-nn`) estão no levantamento. Use estes arquivos para o
detalhe que o levantamento resume: modelo de dados coluna a coluna (Atlas), contratos de API e máquina de
transições (Maestro), gatilhos e jobs (Integrador), componentes e RNF de front (Vitrine), requisitos de
segurança por opção (Sentinela), infra e ambientes (Estivador). Fatos citados por `arquivo:linha` valem
para `HEAD a2af85e`.

| Arquivo | Persona | Recorte |
|---|---|---|
| `sentinela.md` | 🛡️ Sentinela | P01 × IdP, LGPD, backoffice (segurança), validação pública, CSV × CPF, PWA/SW × CSP, notificações, limites, step-up, campanha, links a parceiros |
| `atlas.md` | 🗄️ Atlas | modelo de dados, migrações `sql/008+`, grants, trilhas, catálogo de eventos unificado, indicadores, importação, outbox, consentimento, retenção, volume |
| `maestro.md` | ⚙️ Maestro | contratos de API por página, máquina de 8 status, tipos de ativação, elegibilidade, recomendação, blocos da home, valor, flags, backoffice como API interna |
| `integrador.md` | 🔌 Integrador | 13 integrações + hub + SMTP, contrato de dados §13.2 campo a campo, gatilhos A01–A20, jobs, RD Station reaproveitável |
| `vitrine.md` | 🎨 Vitrine | 17 telas × mockups, navegação, componentes, PWA, desempenho, WCAG 2.2, fonte ajustável, compatibilidade, voz |
| `estivador.md` | 📦 Estivador | ambientes, CI/CD, backup/restore (confirmado via `aws`), monitoramento, serviço de jobs, canal do CSV, backoffice (infra), OpenAPI, vhost, P-01/P-19/P-26/P-34/P-36/P-41, recursos do host |
