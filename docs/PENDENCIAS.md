# Pendências — Minha APM

Backlog vivo do projeto. Cada item tem dono e diz qual fase ele bloqueia. Quando um item é
resolvido, ele **sai daqui e entra em [CONCLUIDO.md](CONCLUIDO.md)** com data e evidência.

- **Prioridade:** P0 bloqueia uma fase · P1 necessário antes da fase indicada · P2 melhoria ou fase futura.
- **Estado:** aberta · em andamento · aguardando terceiro · bloqueada.
- **Referências:** decisões em [docs/adr/](adr/), requisitos em [REQUISITOS-minha-apm.md](REQUISITOS-minha-apm.md),
  plano por fases em [REQUISITOS-minha-apm.md §12](REQUISITOS-minha-apm.md) e no roteiro abaixo.

---

## Bloqueadores externos e de infraestrutura

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-01 | P0 | Certificado de origem do `nginx_porteiro` (`origin.pem`, autoassinado) venceu em 10/10/2026. Os sites só seguem no ar porque a zona Cloudflare não está em Full (strict). Emitir Cloudflare Origin CA e passar a zona para Full (strict). | Estivador / infra | Cutover (`docs/CUTOVER.md`) e qualquer acesso externo | aberta | 2026-10-10 |
| P-02 | P0 | Provisionar o `mcp_hub` em produção: schemas `mcp_hub`/`mcp_hub_dados`, credenciais próprias de leitura (CRM e F&O), conta de serviço `area-associado` com `ips_permitidos` da `rede_publica`, grupo `app-area-associado` e grants `modo_pii=completo` para `associado.*`, `totalpass.adesao_consultar` e `solicitacao.*`. | mcp_hub / infra | Fase 2 em diante com dados reais (até lá `HUB_MODE=stub`) | aberta | 2026-10-16 |
| P-03 | P0 | `mcp_hub`: override **por conta de serviço** de `cota_pii_diaria` (hoje 500/dia) e `chamadas_por_minuto` (hoje 60). Valores por principal são inviáveis para um app com milhares de associados. | mcp_hub | Fase 2 | aberta | 2026-10-16 |
| P-04 | P0 | `mcp_hub`: aceitar `contact_id` como chave em `associado.consultar`, `totalpass.adesao_consultar` e `financeiro.*`, resolvendo o CPF dentro do hub (nova função `dataverse.contato_por_id`). A área não tem CPF por regra (ADR-0014). | mcp_hub | Fases 2, 4 e 7 | aberta | 2026-10-16 |
| P-05 | P0 | Entra ID: app registration **de escrita** "APM MCP Hub CRM escrita", application user no Dataverse e security role mínima (write em `contact` só nos campos da allowlist, create/write em `task`). Confirmar nomes lógicos de endereço (`address1_*`) na Metadata API. Avaliar field security. | CRM admin | Fase 2 (edição de perfil e foto) | aberta | 2026-10-16 |
| P-06 | P0 | Definir a entidade do CRM que espelha as solicitações. Proposta: `task` *regarding* contact, `subject` `[Minha APM] <tipo> <uuid>`. Alternativa: entidade custom. Verificar flows que disparam em create e quem do atendimento trata a fila. | CRM / negócio | Fase 3 (o espelho; a fila local funciona sem ele) | aberta | 2026-10-16 |
| P-07 | P0 | Locaweb `portal_apm`: criar usuário **novo somente leitura** com SELECT só em `pw_portal_{posts,postmeta,terms,term_taxonomy,term_relationships,yoast_indexable}`, verificar suporte a TLS (`have_ssl`), restringir origem ao IP da EC2. Depois de migrar o appapm (P-16), revogar `portal_apm@%`, marcado como vazado em `PENDENCIAS_AWS.md`. | infra / Planeta W | Fase 5 (até lá `WP_MODE=stub`) | aberta | 2026-10-16 |
| P-08 | P1 | Parecer sobre licença e multiplexação do F&O antes de exibir dados do ERP a associados (`totalpass/docs/RUNBOOK_ERP_FO.md:205-211`). | TI / jurídico | Fase 7 | aberta | 2026-10-16 |

## Segurança e identidade

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-09 | P0 | Escopo `carteirinha` **permitido no client `area-associado` do IdP**. O código já o pede desde a Fase 2a (`OIDC_SCOPES`, `docs/CUTOVER.md` atualizado); se o client não o permitir, o login OIDC falha com `invalid_scope`. Conferir com `scripts/check_oidc.py` antes de qualquer uso com `AUTH_MODE=oidc`. | Sentinela / IdP | cutover e qualquer uso com `AUTH_MODE=oidc` | aberta | 2026-10-16 |
| P-22 | P1 | Contraste AA: 7 pares de cor da spec falham em WCAG AA (ex.: branco sobre `#0e8f78` = 4,02; branco sobre `#1faa59` = 3,02). Na Fase 1 foram criadas variantes `-texto` com o menor escurecimento que passa (`frontend/src/styles/tokens.css`). Falta: validação visual com a agência/negócio e os pares das tags `novo` (3,33) e `ativo` (4,41), usados a partir da Fase 4. | Vitrine / negócio | Fase 4 (tags) | aberta | 2026-10-17 |

## Definições de negócio e conteúdo

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-10 | P1 | Decidir as lacunas restantes da spec em [REQUISITOS §11](REQUISITOS-minha-apm.md): regra de validade da carteirinha (hoje omitida), o que é "Inscrever" e "Garantir minha vaga", destino de "Gerenciar", vocabulário único de categorias, textos dos toasts não definidos. E-mail e remoção de foto foram decididos em 2026-10-17. | negócio | Fases 4 e 5 | aberta | 2026-10-16 |
| P-11 | P1 | Conteúdo: número da Central APM no WhatsApp e mensagem pré-preenchida, link de cada comunidade (convite de grupo, não `wa.me` 1:1), oferta da semana e catálogo do Clube. | comunicação | Fase 6 | aberta | 2026-10-16 |
| P-12 | P2 | Fonte de dados para Mensalidade Zero, patrocínio, cashback e Fatura de valor. Até existir, as flags ficam forçadas desligadas (ADR-0007). | negócio | Fase 8 | aberta | 2026-10-16 |
| P-13 | P2 | Wallet Apple/Google: conta developer, certificado de assinatura `.pkpass`, service account do Google Wallet. | TI | Fase 8 | aberta | 2026-10-16 |

## Técnicas e operação

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-15 | P2 | Política de retenção e purga de `evento_uso`, `noticia_cache`, `evento_cache` e `job_execucao`, executada pelo operador (sem DELETE pela aplicação). | Atlas | após Fase 5 | aberta | 2026-10-16 |
| P-16 | P2 | Migrar o appapm para o usuário somente leitura novo da Locaweb (P-07) e aposentar `portal_apm@%`. | appapm | — | aberta | 2026-10-16 |
| P-21 | P1 | Mapear no WordPress `portal_apm` como as **notícias** são publicadas (post type, taxonomia de tema, campos de imagem e fonte). As queries do appapm só cobrem `evento`, `banner-header` e `regional`. Exige o usuário RO de P-07. | Integrador / Planeta W | Fase 5 | aberta | 2026-10-17 |
| P-19 | P2 | Incluir `area_associado` e `area-associado-jobs` em `/home/ubuntu/verificar-pos-reboot.sh` (hoje fora da lista de 12 containers). | Estivador | após Fase 1 | aberta | 2026-10-16 |
| P-27 | P0 | Credencial SMTP própria da área (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) com remetente autorizado (SPF/DKIM). Sem ela a troca de e-mail fica indisponível em produção (`SMTP_MODE=stub` é proibido lá). | TI / infra | produção da troca de e-mail (ADR-0015) | aberta | 2026-10-17 |
| P-28 | P0 | **Fase 2b — extensão do mcp_hub** conforme [CONTRATO-HUB.md](CONTRATO-HUB.md): `associado.perfil_consultar`, `contato_atualizar`, `foto_obter`, `foto_atualizar` por `contact_id`, sem CPF, com escopo `ferramentas:escrever` e auditoria de escrita. Plano próprio no repositório do hub. Depende de P-02 a P-05. | mcp_hub | dados reais de perfil e foto (a área roda com `HUB_MODE=stub`) | aberta | 2026-10-17 |
| P-23 | P0 | **Implantar as Fases 1 e 2a no ambiente de construção** (ato do operador): aplicar `sql/003` a `sql/007` no RDS e registrar o sha256 (`docs/PROVISIONAMENTO.md` §2.1 e §2.2); gerar `SESSION_ENC_KEYS` no `.env` e no Secrets Manager; manter `HUB_MODE=stub` e `SMTP_MODE=stub` até P-27/P-28; `DOCKER_BUILDKIT=0 docker compose build && docker compose up -d`; copiar o vhost atualizado para o porteiro (`nginx -t` e `reload`); rodar `db_check` e `csp_check`. | operador / Estivador | uso das Fases 1 e 2a pela equipe | aberta | 2026-10-17 |
| P-24 | P2 | Páginas Jinja fora da SPA (`/`, login stub, erro) ainda usam o visual antigo (Neo Sans, paleta azul/dourado). Unificar com os tokens da spec quando a landing pública for desenhada. | Vitrine | cutover | aberta | 2026-10-17 |
| P-25 | P2 | Sem CI: pytest, Vitest, lint e typecheck rodam no build da imagem, mas o e2e (Playwright) e o Lighthouse são manuais. Avaliar GitHub Actions com a deploy key do repositório. | Estivador | — | aberta | 2026-10-17 |
| P-26 | P2 | O host não tem o plugin `docker-buildx`: build com BuildKit falha; hoje se usa `DOCKER_BUILDKIT=0`. Instalar o plugin (`apt install docker-buildx`) é mudança de sistema, decisão do operador. | infra | — | aberta | 2026-10-17 |

---

## Roteiro por fase

Cada fase tem plano próprio e aprovação antes de codar (CLAUDE.md, sessão 4).

| Fase | Entrega | Pendências que bloqueiam | Estado |
|---|---|---|---|
| 0 | Requisitos, ADRs, pendências, concluídos, CLAUDE.md | — | concluída em 2026-10-17 |
| 1 | Fundação: Vite + shell + tokens + fontes, `spa.py`, sessão cifrada, CSRF por header, `uso.py`, `flags.py`, `sql/003-005`, Dockerfile multi-stage, vhost, testes de rotas | — | código concluído em 2026-10-17; implantação pendente (P-23) |
| 2a | Perfil e carteirinha na área: cache do perfil, contato, e-mail com código, foto, carteirinha com QR, verificação pública, escopo `carteirinha` | — | código concluído em 2026-10-17; implantação pendente (P-23) |
| 2b | Extensão do mcp_hub (contrato em `docs/CONTRATO-HUB.md`) e troca de `HUB_MODE` para `real` | P-02, P-03, P-04, P-05, P-09, P-27, P-28 | próxima |
| 3 | Solicitações: `sql/006`, máquina de estados, API, jobs de outbox e sincronização, tela | P-06 | — |
| 4 | Benefícios: `sql/007` seed, ativações, TotalPass via hub + deep-link, home | P-04, P-10, P-22 | — |
| 5 | Notícias e eventos: `portal_wp.py` só no job, caches, temas, salvos, inscrições, banner do Congresso | P-07, P-10, P-21 | — |
| 6 | Comunidade, onboarding acadêmico e clube | P-11 | — |
| 7 | ERP via hub `financeiro.*` atrás da flag `erp_financeiro` | P-04, P-08 | — |
| 8 | Patrocínio, fatura de valor e wallet atrás de flags | P-12, P-13 | — |
