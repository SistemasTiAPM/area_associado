# Pendências — Minha APM

Backlog vivo do projeto. Cada item tem dono e diz qual fase ele bloqueia. Quando um item é
resolvido, ele **sai daqui e entra em [CONCLUIDO.md](CONCLUIDO.md)** com data e evidência.

- **Prioridade:** P0 bloqueia uma fase · P1 necessário antes da fase indicada · P2 melhoria ou fase futura.
- **Estado:** aberta · em andamento · aguardando terceiro · bloqueada.
- **Referências:** decisões em [docs/adr/](adr/), requisitos em [REQUISITOS-minha-apm.md](REQUISITOS-minha-apm.md),
  plano por fases em [REQUISITOS-minha-apm.md §12](REQUISITOS-minha-apm.md) e no roteiro abaixo.

## 📍 Onde paramos — 2026-10-19 (fim do dia)

**Últimos commits:** área na `main` (`SistemasTiAPM/area_associado`, ver [CONCLUIDO.md](CONCLUIDO.md));
hub `8bb3c43` na `main` de `SistemasTiAPM/mcp_hub`. Ambos no GitHub.

**No ar desde 19/10: `https://minha.apm.org.br`**, público, em modo de construção, para a
agência acompanhar o progresso. **Desde 20/10 a entrada é pelo Login APM** (`AUTH_MODE=oidc`,
login de construção desligado); hub e e-mail seguem simulados com a faixa "dados de
demonstração". Fases 1, 2a e 2b implantadas; RDS com `sql/001`–`007`.

| Fase | Situação | Depende de |
|---|---|---|
| 0 — Documentação | concluída | — |
| 1 — Fundação (SPA, sessão cifrada, API, flags, analytics) | **no ar** em minha.apm.org.br (construção) | — |
| 2a — Perfil, e-mail por código, foto, carteirinha | **no ar** (hub e SMTP simulados) | dados reais: P-02, P-05, P-27 |
| 2b — mcp_hub com perfil, contato e foto no CRM | código concluído nos dois repositórios | provisão P-02, P-05; escrita real só depois de P-29; P-30, P-31 |
| 3 — Solicitações | **não iniciada**, pode começar já (fila local não depende do hub) | P-06 só para o espelho no CRM |
| 4 a 8 | não iniciadas | ver roteiro no fim deste arquivo |

**O que está nas mãos de quem**
- **Operador (você):** replicar o `.env` atualizado no Secrets Manager (P-36); P-02, implantar o hub
  novo (aplicar `sql/004` e `005` do hub no RDS antes do código, credenciais, conta `area-associado`);
  P-01, certificado de origem; decidir o catch-all do porteiro (P-34).
- **TI / infra:** P-27, credencial SMTP.
- **CRM admin:** P-37, contatos de teste no CRM para a agência entrar pelo Login APM; P-05, app
  registration e papel de escrita; P-29, flows em update de `contact`; P-30, homologar a foto;
  P-06, entidade das solicitações.
- **Negócio:** P-31 (confirmar os campos do endereço), P-32 (formato de telefone), P-10 e P-22.

**Para retomar:** Fase 3 (solicitações, plano neste repositório). Cada fase começa com plano e
aprovação (CLAUDE.md, sessão 4). Toda entrega daqui para a frente vai ao ar em minha.apm.org.br
com `DOCKER_BUILDKIT=0 docker compose build && docker compose up -d` (a agência vê na hora).

---

## Bloqueadores externos e de infraestrutura

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-01 | P0 | Certificado de origem do `nginx_porteiro` (`origin.pem`, autoassinado) venceu em 10/10/2026. Os sites só seguem no ar porque a zona Cloudflare não está em Full (strict). Emitir Cloudflare Origin CA e passar a zona para Full (strict). | Estivador / infra | Cutover (`docs/CUTOVER.md`) e qualquer acesso externo | aberta | 2026-10-10 |
| P-02 | P0 | Provisionar o `mcp_hub` em produção, na ordem do RUNBOOK do hub (§2 e §3.1): schemas `mcp_hub`/`mcp_hub_dados` com `sql/000`–`005` (004 e 005 **antes** do código novo; conferência do cabeçalho do 005 = 0) e `db_check` OK; credenciais próprias de leitura (CRM e F&O); conta `area-associado` com `ips_permitidos` da `rede_publica`, escopos ler (+ escrever só depois de P-29), `chamadas_por_minuto` e cota PII próprias, grants **exatos** `modo_pii=completo` em `associado.perfil_consultar`, `contato_atualizar`, `foto_obter`, `foto_atualizar` (depois `totalpass.adesao_consultar`, `solicitacao.*`); segredo em `HUB_CLIENT_SECRET` da área, `HUB_MODE=real` e `scripts/check_hub.py` OK. | mcp_hub / operador | dados reais na área (até lá `HUB_MODE=stub`) | aberta | 2026-10-16 |
| P-04 | P0 | `mcp_hub`: aceitar `contact_id` como chave em `associado.consultar`, `totalpass.adesao_consultar` e `financeiro.*`, resolvendo o CPF dentro do hub. **Parcial (2026-10-19):** `dataverse.contato_por_id` existe e as 4 ferramentas da Minha APM já são por `contact_id`, com titular auditado por contato; faltam as ferramentas que hoje exigem CPF. A área não tem CPF por regra (ADR-0014). | mcp_hub | Fases 4 e 7 | em andamento | 2026-10-16 |
| P-05 | P0 | Entra ID: app registration **de escrita** "APM MCP Hub CRM escrita" (outra, nunca a de leitura), application user no Dataverse e security role **só Read + Write em `contact`** (na Fase 3, create/write em `task`, P-06). Gravar no painel do hub como "Dataverse — escrita" e rodar `scripts/check_conectores` do hub: tem que dar OK no papel (sem Create/Delete/Assign/Share/Append) e imprime a Metadata do endereço e da `entityimage`. Avaliar field security. | CRM admin | escrita real de contato e foto | aberta | 2026-10-16 |
| P-06 | P0 | Definir a entidade do CRM que espelha as solicitações. Proposta: `task` *regarding* contact, `subject` `[Minha APM] <tipo> <uuid>`. Alternativa: entidade custom. Verificar flows que disparam em create e quem do atendimento trata a fila. | CRM / negócio | Fase 3 (o espelho; a fila local funciona sem ele) | aberta | 2026-10-16 |
| P-07 | P0 | Locaweb `portal_apm`: criar usuário **novo somente leitura** com SELECT só em `pw_portal_{posts,postmeta,terms,term_taxonomy,term_relationships,yoast_indexable}`, verificar suporte a TLS (`have_ssl`), restringir origem ao IP da EC2. Depois de migrar o appapm (P-16), revogar `portal_apm@%`, marcado como vazado em `PENDENCIAS_AWS.md`. | infra / Planeta W | Fase 5 (até lá `WP_MODE=stub`) | aberta | 2026-10-16 |
| P-34 | P1 | **Catch-all na 443 do porteiro.** Host proxied sem vhost cai no primeiro `server` em ordem alfabética, hoje `apm_parceiros.conf`: em 19/10 `minha.apm.org.br` abriu o Sistema de Parceiros até o vhost da área entrar. Proposta: `server { listen 443 ssl default_server; server_name _; return 444; }` num arquivo `_00_padrao.conf`, mantendo o default da porta 80 (health check do ALB, ver `totalpass.conf`). Mexe no porteiro de todos os projetos. | Estivador / operador | — (risco para qualquer DNS novo) | aberta | 2026-10-19 |
| P-36 | P1 | Replicar o `.env` da área (alterado em 19/10 e 20/10: `PUBLIC_BASE_URL`, `SESSION_ENC_KEYS`, `CARTEIRINHA_HMAC_KEY`, `HUB_MODE`, `SMTP_MODE`, `AUTH_MODE=oidc`, `OIDC_SCOPES`, sem `DEV_STUB_TOKEN`) no Secrets Manager `prod/area-associado/env`; depois apagar `.env.bak-20261019-dominio` e `.env.bak-20261020-oidc`. Trocar `SESSION_ENC_KEYS` derruba todas as sessões; trocar `CARTEIRINHA_HMAC_KEY` invalida os QRs. | operador | recuperação do servidor | aberta | 2026-10-19 |
| P-08 | P1 | Parecer sobre licença e multiplexação do F&O antes de exibir dados do ERP a associados (`totalpass/docs/RUNBOOK_ERP_FO.md:205-211`). | TI / jurídico | Fase 7 | aberta | 2026-10-16 |

## Segurança e identidade

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-37 | P0 | **Contatos de teste no CRM para a agência.** A área entra só pelo Login APM; quem não é associado precisa de um contato no Dataverse com tipo e situação associativa válidos (o escopo `carteirinha` recusa sem eles, ADR-0016) para fazer o cadastro normal no Login APM. Criar um contato por pessoa da agência (ou um compartilhado), marcado como teste, e remover na virada. Hoje existe um usuário de teste do IdP, usado na validação de 20/10. | CRM admin | acompanhamento pela agência | aberta | 2026-10-20 |
| P-22 | P1 | Contraste AA: a paleta dos mockups (ADR-0017) tem pares que falham em WCAG AA: branco sobre `#009581` = 3,74, `#8A979D` sobre branco = 3,00 e o azul das tags `#007EA3` sobre `#E8F2F6` = 4,09. Em 2026-10-20 ganharam variantes `-texto` (`#00675A` 6,80; `#5E6E75` 5,30; `#006B8C` 5,30) em `frontend/src/styles/tokens.css`, e o axe passa nas 4 telas existentes. Falta: validação visual da agência para as variantes e os pares das tags de status nas telas da Fase 4. | Vitrine / agência | Fase 4 (tags) | aberta | 2026-10-17 |

## Definições de negócio e conteúdo

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-10 | P1 | Decidir as lacunas restantes da spec em [REQUISITOS §11](REQUISITOS-minha-apm.md): regra de validade da carteirinha (hoje omitida), o que é "Inscrever" e "Garantir minha vaga", destino de "Gerenciar", vocabulário único de categorias, textos dos toasts não definidos. E-mail e remoção de foto foram decididos em 2026-10-17. | negócio | Fases 4 e 5 | aberta | 2026-10-16 |
| P-11 | P1 | Conteúdo: número da Central APM no WhatsApp e mensagem pré-preenchida, link de cada comunidade (convite de grupo, não `wa.me` 1:1), oferta da semana e catálogo do Clube. | comunicação | Fase 6 | aberta | 2026-10-16 |
| P-12 | P2 | Fonte de dados para Mensalidade Zero, patrocínio, cashback e Fatura de valor. Até existir, as flags ficam forçadas desligadas (ADR-0007). | negócio | Fase 8 | aberta | 2026-10-16 |
| P-13 | P2 | Wallet Apple/Google: conta developer, certificado de assinatura `.pkpass`, service account do Google Wallet. | TI | Fase 8 | aberta | 2026-10-16 |
| P-38 | P2 | **Imagens e números dos mockups.** Landing e área usam gradientes e formas em CSS no lugar das fotos, e só o número "95 anos". Falta a Comunicação/agência enviar, com direito de uso e em resolução de produção, a foto do hero da entrada (`0ebf4ef7.png`), o selo "95 anos" (`c2cd4d74.png`) e as fotos dos cards (Painel `0ebf4ef7.png`, avatares e capas do banco de imagens). Também falta aprovar com fonte, ou retirar, "+40 benefícios" e "60 regionais" (REQUISITOS LA-14). As imagens entram em `app/static/` (CSP `img-src 'self'`). Os arquivos já existem no pacote dos mockups (artifact `KvCeCEoD531nxQ1GyaVjMo`: logos oficiais, foto do hero aparentemente gerada por IA e fotos de banco); em 2026-10-20 o usuário optou por publicar sem eles até a confirmação do direito de uso. | Comunicação / agência | cutover | aberta | 2026-10-20 |
| P-39 | P2 | **Mockups da agência no repositório.** Os 12 `*.dc.html` que definem o visual (ADR-0017) só existem colados na conversa de 2026-10-20, sem `support.js` e sem `assets/`. Pedir à agência o pacote completo e versionar em `docs/mockups/` (sem executar o `support.js`; só referência), para que as fases 3 a 8 sigam a mesma fonte. | Agência / Vitrine | Fase 3 (telas novas) | aberta | 2026-10-20 |
| P-40 | P2 | **`react-router-dom` 6.30 com 2 avisos moderados** (`npm audit`: open redirect por barra invertida em `<Link>`/`useNavigate`, GHSA-wrjc-x8rr-h8h6; injeção em hidratação SSR, GHSA-337j-9hxr-rhxg). Anteriores a 2026-10-20. Hoje a área não monta destino de navegação com dado do usuário e não usa SSR, mas a correção só existe no 7.18+ (troca de major). Avaliar a migração ou um bloqueio de `\` nos destinos. | Sentinela / Vitrine | antes do cutover | aberta | 2026-10-20 |

## Técnicas e operação

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-15 | P2 | Política de retenção e purga de `evento_uso`, `noticia_cache`, `evento_cache` e `job_execucao`, executada pelo operador (sem DELETE pela aplicação). | Atlas | após Fase 5 | aberta | 2026-10-16 |
| P-16 | P2 | Migrar o appapm para o usuário somente leitura novo da Locaweb (P-07) e aposentar `portal_apm@%`. | appapm | — | aberta | 2026-10-16 |
| P-21 | P1 | Mapear no WordPress `portal_apm` como as **notícias** são publicadas (post type, taxonomia de tema, campos de imagem e fonte). As queries do appapm só cobrem `evento`, `banner-header` e `regional`. Exige o usuário RO de P-07. | Integrador / Planeta W | Fase 5 | aberta | 2026-10-17 |
| P-19 | P2 | Incluir `area_associado` e `area-associado-jobs` em `/home/ubuntu/verificar-pos-reboot.sh` (hoje fora da lista de 12 containers). | Estivador | após Fase 1 | aberta | 2026-10-16 |
| P-27 | P0 | Credencial SMTP própria da área (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) com remetente autorizado (SPF/DKIM). Sem ela a troca de e-mail fica indisponível em produção (`SMTP_MODE=stub` é proibido lá). | TI / infra | produção da troca de e-mail (ADR-0015) | aberta | 2026-10-17 |
| P-29 | P0 | **Flows, plugins e workflows que disparam em update de `contact`** no Dataverse: mapear quais existem, o que fazem quando a área muda celular, telefone, e-mail, endereço ou foto, e se algum notifica o associado, sincroniza com outro sistema ou sobrescreve campo. **O escopo `ferramentas:escrever` não é marcado na conta `area-associado` em produção antes disso.** | CRM admin | escrita real no CRM | aberta | 2026-10-19 |
| P-30 | P1 | Homologar a foto no CRM: `entityimage` com `CanStoreFullImage` (senão o CRM guarda só 144×144) e `MaxSizeInKB` (o `check_conectores` do hub imprime os dois); confirmar que o PATCH com base64 é aceito e que `foto_obter` devolve a imagem gravada. Plano B no hub se o PATCH falhar: `PUT .../entityimage` com `application/octet-stream`. | CRM admin / Integrador | foto real no CRM | aberta | 2026-10-19 |
| P-31 | P1 | Confirmar com o negócio que os 7 atributos do endereço no `contact` têm o mesmo significado do lead (`address1_line1` logradouro, `alf_numero_endereco` número, `address1_line2` complemento, `alf_bairro` bairro, `address1_city`, `address1_stateorprovince`, `address1_postalcode`) e então ligar `CRM_ENDERECO_HABILITADO=true` no hub. Até lá a área mostra "o endereço ainda não pode ser alterado por aqui" e o hub responde 409. A Metadata prova só que os campos existem. | negócio / CRM admin | edição de endereço | aberta | 2026-10-19 |
| P-32 | P2 | Convenção de formato de telefone no CRM. A área e o hub gravam `(11) 91234-5678` / `(11) 3188-6200`; confirmar se flows, discador ou integrações esperam outro formato (E.164, só dígitos) antes de virar padrão. | CRM admin / negócio | — | aberta | 2026-10-19 |
| P-33 | P2 | No ensaio ponta a ponta de 19/10, 1 de 9 emissões de token do hub para a área voltou 503 `temporarily_unavailable`; não se repetiu em 8 tentativas e o log daquela rodada se perdeu com o container. Após implantar o hub, vigiar `oauth/token indisponível` e `nenhuma chave de assinatura ativa` no log; se aparecer, investigar o cache do chaveiro e o pool do RDS. | Integrador | — | aberta | 2026-10-19 |
| P-24 | P2 | Páginas Jinja fora da SPA (login stub, erro, `/verificar`) ainda usam o visual antigo (Neo Sans, paleta azul/dourado). Unificar com a linguagem de `entrada.css` (Figtree + tokens da spec). A landing `/` já foi feita em 2026-10-20. | Vitrine | cutover | aberta | 2026-10-17 |
| P-25 | P2 | Sem CI: pytest, Vitest, lint e typecheck rodam no build da imagem, mas o e2e (Playwright) e o Lighthouse são manuais. Avaliar GitHub Actions com a deploy key do repositório. | Estivador | — | aberta | 2026-10-17 |
| P-26 | P2 | O host não tem o plugin `docker-buildx`: build com BuildKit falha; hoje se usa `DOCKER_BUILDKIT=0`. Instalar o plugin (`apt install docker-buildx`) é mudança de sistema, decisão do operador. | infra | — | aberta | 2026-10-17 |

---

## Roteiro por fase

Cada fase tem plano próprio e aprovação antes de codar (CLAUDE.md, sessão 4).

| Fase | Entrega | Pendências que bloqueiam | Estado |
|---|---|---|---|
| 0 | Requisitos, ADRs, pendências, concluídos, CLAUDE.md | — | concluída em 2026-10-17 |
| 1 | Fundação: Vite + shell + tokens + fontes, `spa.py`, sessão cifrada, CSRF por header, `uso.py`, `flags.py`, `sql/003-005`, Dockerfile multi-stage, vhost, testes de rotas | — | código concluído em 2026-10-17; no ar em minha.apm.org.br desde 2026-10-19 |
| 2a | Perfil e carteirinha na área: cache do perfil, contato, e-mail com código, foto, carteirinha com QR, verificação pública, escopo `carteirinha` | — | código concluído em 2026-10-17; no ar em minha.apm.org.br desde 2026-10-19 |
| 2b | mcp_hub com perfil, contato e foto no CRM (contrato em `docs/CONTRATO-HUB.md`) e troca de `HUB_MODE` para `real` | P-02, P-05, P-29, P-30, P-31 | código concluído em 2026-10-19; provisão pendente |
| 3 | Solicitações: `sql/008`, máquina de estados, API, jobs de outbox e sincronização, tela | P-06 | próxima |
| 4 | Benefícios: `sql/007` seed, ativações, TotalPass via hub + deep-link, home | P-04, P-10, P-22 | — |
| 5 | Notícias e eventos: `portal_wp.py` só no job, caches, temas, salvos, inscrições, banner do Congresso | P-07, P-10, P-21 | — |
| 6 | Comunidade, onboarding acadêmico e clube | P-11 | — |
| 7 | ERP via hub `financeiro.*` atrás da flag `erp_financeiro` | P-04, P-08 | — |
| 8 | Patrocínio, fatura de valor e wallet atrás de flags | P-12, P-13 | — |
