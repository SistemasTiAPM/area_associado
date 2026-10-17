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
| P-09 | P1 | Pedir o escopo `carteirinha` no RP: `OIDC_SCOPES` em `app/config.py` e `.env.example`, conferência em `scripts/check_oidc.py` e comando `generate_client` em `docs/CUTOVER.md`. **Divergência a confirmar no IdP:** o levantamento indica o escopo já permitido ao client `area-associado`, mas `docs/CUTOVER.md:20` registra o client só com `openid profile email cpf`. | Sentinela | Fase 2 | aberta | 2026-10-16 |
| P-20 | P1 | Decidir o comportamento quando o userinfo vier sem `tipo_associado` ou `associado` (CRM incompleto): recusar o login (fail-closed) ou abrir sessão sem persona, com rota inicial padrão. REQUISITOS LA-29 e RF-AU-09. | Sentinela | Fase 1 | aberta | 2026-10-17 |
| P-17 | P1 | Confirmar ADR-0011 (cookie de sessão cifrado com Fernet, nome `__Host-area` fora de development) e definir a origem da chave (`SESSION_ENC_KEY` própria ou HKDF de `SECRET_KEY`). | Sentinela | Fase 1 | aberta | 2026-10-16 |
| P-18 | P1 | Corrigir o defeito `html.js .alert { display:none }` (`app/static/style.css:323` + `boot.js`): a faixa do login stub e as mensagens de erro ficam invisíveis com JS ativo. O SweetAlert2 citado no comentário não existe. | Vitrine | Fase 1 | aberta | 2026-10-16 |

## Definições de negócio e conteúdo

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-10 | P1 | Decidir as lacunas da spec listadas em [REQUISITOS §11](REQUISITOS-minha-apm.md): regra de validade da carteirinha, e-mail editável direto ou com verificação, o que é "Inscrever" e "Garantir minha vaga", destino de "Gerenciar", vocabulário único de categorias, textos dos toasts não definidos, remoção de foto. | negócio | Fases 2, 4 e 5 | aberta | 2026-10-16 |
| P-11 | P1 | Conteúdo: número da Central APM no WhatsApp e mensagem pré-preenchida, link de cada comunidade (convite de grupo, não `wa.me` 1:1), oferta da semana e catálogo do Clube. | comunicação | Fase 6 | aberta | 2026-10-16 |
| P-12 | P2 | Fonte de dados para Mensalidade Zero, patrocínio, cashback e Fatura de valor. Até existir, as flags ficam forçadas desligadas (ADR-0007). | negócio | Fase 8 | aberta | 2026-10-16 |
| P-13 | P2 | Wallet Apple/Google: conta developer, certificado de assinatura `.pkpass`, service account do Google Wallet. | TI | Fase 8 | aberta | 2026-10-16 |

## Técnicas e operação

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-14 | P2 | Fontes Figtree (400–800) e JetBrains Mono em woff2, subset latin e latin-ext, com a licença OFL em `frontend/public/fonts/LICENSE`. A fonte local atual é Neo Sans e sai das telas novas. | Vitrine | Fase 1 | aberta | 2026-10-16 |
| P-15 | P2 | Política de retenção e purga de `evento_uso`, `noticia_cache`, `evento_cache` e `job_execucao`, executada pelo operador (sem DELETE pela aplicação). | Atlas | após Fase 5 | aberta | 2026-10-16 |
| P-16 | P2 | Migrar o appapm para o usuário somente leitura novo da Locaweb (P-07) e aposentar `portal_apm@%`. | appapm | — | aberta | 2026-10-16 |
| P-21 | P1 | Mapear no WordPress `portal_apm` como as **notícias** são publicadas (post type, taxonomia de tema, campos de imagem e fonte). As queries do appapm só cobrem `evento`, `banner-header` e `regional`. Exige o usuário RO de P-07. | Integrador / Planeta W | Fase 5 | aberta | 2026-10-17 |
| P-19 | P2 | Incluir `area_associado` e `area-associado-jobs` em `/home/ubuntu/verificar-pos-reboot.sh` (hoje fora da lista de 12 containers). | Estivador | após Fase 1 | aberta | 2026-10-16 |

---

## Roteiro por fase

Cada fase tem plano próprio e aprovação antes de codar (CLAUDE.md, sessão 4).

| Fase | Entrega | Pendências que bloqueiam | Estado |
|---|---|---|---|
| 0 | Requisitos, ADRs, pendências, concluídos, CLAUDE.md | — | concluída em 2026-10-17 |
| 1 | Fundação: Vite + shell + tokens + fontes, `spa.py`, sessão cifrada, CSRF por header, `uso.py`, `flags.py`, `sql/003-005`, Dockerfile multi-stage, vhost, testes de rotas | P-14, P-17, P-18, P-20 | próxima |
| 2 | Perfil e carteirinha: cliente do hub (stub até P-02), escopo `carteirinha`, edição direta, foto, `/verificar/{token}`; extensão de escrita do hub | P-02, P-03, P-04, P-05, P-09, P-10 | — |
| 3 | Solicitações: `sql/006`, máquina de estados, API, jobs de outbox e sincronização, tela | P-06 | — |
| 4 | Benefícios: `sql/007` seed, ativações, TotalPass via hub + deep-link, home | P-04, P-10 | — |
| 5 | Notícias e eventos: `portal_wp.py` só no job, caches, temas, salvos, inscrições, banner do Congresso | P-07, P-10, P-21 | — |
| 6 | Comunidade, onboarding acadêmico e clube | P-11 | — |
| 7 | ERP via hub `financeiro.*` atrás da flag `erp_financeiro` | P-04, P-08 | — |
| 8 | Patrocínio, fatura de valor e wallet atrás de flags | P-12, P-13 | — |
