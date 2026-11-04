# Pendências — Minha APM

Backlog vivo do projeto. Cada item tem dono e diz qual fase ele bloqueia. Quando um item é
resolvido, ele **sai daqui e entra em [CONCLUIDO.md](CONCLUIDO.md)** com data e evidência.

- **Prioridade:** P0 bloqueia uma fase · P1 necessário antes da fase indicada · P2 melhoria ou fase futura.
- **Estado:** aberta · em andamento · aguardando terceiro · bloqueada.
- **Referências:** decisões em [docs/adr/](adr/), requisitos em [REQUISITOS-minha-apm.md](REQUISITOS-minha-apm.md),
  plano por fases em [REQUISITOS-minha-apm.md §12](REQUISITOS-minha-apm.md) e no roteiro abaixo.

## 📍 Onde paramos — 2026-10-30 (Onda 2 fechada)

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
| 2a — Perfil, e-mail por código, foto, carteirinha | **no ar** (hub e SMTP simulados) | CRM real em leitura desde 21/10; e-mail: P-27 |
| 2b — mcp_hub com perfil, contato e foto no CRM | **no ar** com `HUB_MODE=real`, só leitura (21/10) | P-41; escrita real só depois de P-29; P-30, P-31 |
| 3 — Solicitações | **não iniciada**, pode começar já (fila local não depende do hub) | P-06 só para o espelho no CRM |
| 4 a 8 | não iniciadas | ver roteiro no fim deste arquivo |

**O que está nas mãos de quem**
- **Operador (você):** P-01, certificado de origem; P-77, painel do hub para o espelho; deploy e
  ensaio do espelho (ação 7 abaixo; `sql/015` aplicada em 04/11). P-36 (cofre) adiada por decisão sua.
- **TI / infra:** P-27, credencial SMTP.
- **CRM admin:** P-37, contatos de teste no CRM para a agência entrar pelo Login APM; P-29, flows em
  update de `contact`; P-30, homologar a foto (`CanStoreFullImage=False` hoje); P-76, códigos de status
  do tenant e assunto por tipo.
- **mcp_hub:** P-74 (ferramenta de status), P-75 (consulta por cursor), P-76 (`detalhes` no 404).
- **Negócio:** P-31 (confirmar os campos do endereço), P-32 (formato de telefone), P-10 e P-22.

**2026-10-21:** P-02 e P-05 concluídas. A área roda com `HUB_MODE=real` e
`HUB_ESCRITA_HABILITADA=false`: o perfil mostra os dados do CRM só para leitura. A faixa de
demonstração continua por causa do SMTP simulado (P-27). Próximos: P-41 (volume ao hub), P-36
(`.env` no Secrets Manager), P-29 para ligar a edição.

**2026-10-29:** chegou a **especificação funcional v2 da agência** (30/09/2026). Está transcrita em
`docs/spec-v2/` e lida em `docs/LEVANTAMENTO-TECNICO-spec-v2.md` (listas **TI-nn** = só TI,
**EXT-nn** = depende de terceiro, DIV-nn, DEC-nn). As dependências externas novas viraram **P-42 a
P-65** abaixo; as decisões pendentes do usuário estão no §11 do levantamento. O roteiro ganhou a
coluna "F da spec" e quatro blocos que a spec coloca na F1 e o roteiro não tinha: backoffice,
P06 Meu valor v1, P14 Ajuda/cancelamento e o motor de elegibilidade/carências.

**2026-10-30 — Onda 1 executada** (`docs/PLANO-EXECUCAO.md`): base transversal no ar — catálogo de
`evento_uso` com 51 ações e `acesso_primeiro`, `exigir_reautenticacao`, flags v2 (`sql/009`), OpenAPI
versionado em `docs/api/openapi.json` com verificação no build, campanha `utm_*`/`g=`, `db_check` por
usuário, migração `sql/008` (partições; **aplicação pelo operador**), compose com `TZ`/tmpfs/pids,
`scripts/deploy.sh`, `scripts/alertas.sh`, `docs/OPERACAO.md`, front com voz §3.3, alvos 44 px, axe
WCAG 2.2 em todas as rotas, 10 primitivos puros, sub-rotas no shell; hub com `associado.situacao`/
`historico_associacao` por `contact_id` sem CPF (grant M-7 pelo operador); REQUISITOS v0.2; ADR-0018..0022.
Decisões DEC-01/02/04/13/22/28/29 aceitas e DEC-03 (parte de banco) decidida.

**2026-10-30 — Onda 2 executada** (`docs/PLANO-EXECUCAO.md`): solicitações com os 8 status da spec
(`sql/010`, máquina de estados, API `/solicitacoes`, contador real), P14 Ajuda (FAQ, contato da Central,
formulário, declaração, pedido de cancelamento atrás de `cancelamento_online` com step-up), outbox de
comunicação e `notificacao` gravadas na mesma transação (`sql/012`), `faq`/`texto_sistema`/`parametro`
(`sql/013`), carteirinha em tempo quase real com revogação e download em PNG/PDF (`sql/014`), serviço de
jobs em dry-run (`sql/011`, `app/jobs`, profile `jobs`), React Router 7 (P-40 resolvida), telas P05/P14. No
ar desde 30/10; `sql/008`–`014` aplicadas em 2026-11-03, P05 e P14 disponíveis (`/sessao.recursos`).

**Ações do operador pendentes, em ordem:**
1. ~~Migrações `sql/008`→`014`~~ aplicadas em 2026-11-03, com telefone e horário da central (ver CONCLUIDO).
2. ~~**M-7**~~ feito em 2026-10-30 (ver CONCLUIDO).
3. ~~Jobs~~: `.env.jobs`, conta M-8 e serviço no ar desde 2026-11-03, em simulação (ver CONCLUIDO).
4. ~~Porteiro~~: zonas da TI-08 e catch-all da 443 (P-34) aplicados em 2026-11-03 (ver CONCLUIDO).
5. Onda 0: P-01 certificado de origem (`docs/OPERACAO.md` §2); P-61 monitor no Grafana (handoff em
   `docs/handoff/MONITOR-EXTERNO-GRAFANA.md`); P-36 adiada pelo usuário; P-19 feita em 03/11; P-71..P-73
   novas; P-59/P-60; WebKit no host de e2e (root).
6. Ligar `cancelamento_online` é decisão de negócio (ADR-0021).
7. **Espelho no CRM (ADR-0023, 2026-11-04), em ordem:** ~~snapshot e `sql/015`~~ (aplicada em 04/11) →
   commit → deploy da área (`scripts/deploy.sh`) e recriar o serviço de jobs → painel do hub (P-77) → ensaio com o
   contato sintético em janela combinada (`docs/JOBS.md` §4b) → decidir `JOBS_APLICAR=1`.

**Para retomar:** **Onda 3** = Fase 3b (P13: preferências, consentimentos versionados, exportação e
exclusão por anonimização; RD Station em stub). Decidir antes DEC-06, DEC-26, DEC-27 (levantamento §11).
Cada onda começa com plano (`docs/PLANO-EXECUCAO.md`) e aprovação (CLAUDE.md §4). Deploy:
`scripts/deploy.sh` (tag, smoke, rollback); o serviço de jobs é recriado à parte (`docs/JOBS.md`).

---

## Bloqueadores externos e de infraestrutura

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-01 | P0 | Certificado de origem do `nginx_porteiro` (`origin.pem`, autoassinado) venceu em 10/10/2026. Os sites só seguem no ar porque a zona Cloudflare não está em Full (strict). Emitir Cloudflare Origin CA e passar a zona para Full (strict). **2026-10-30:** runbook pronto em `docs/OPERACAO.md` §2 (TI-70); `scripts/alertas.sh` acusa o vencimento. | Estivador / infra | Cutover (`docs/CUTOVER.md`) e qualquer acesso externo | aberta | 2026-10-10 |
| P-04 | P0 | `mcp_hub`: aceitar `contact_id` como chave em `associado.consultar`, `totalpass.adesao_consultar` e `financeiro.*`, resolvendo o CPF dentro do hub. **Parcial (2026-10-19):** `dataverse.contato_por_id` existe e as 4 ferramentas da Minha APM já são por `contact_id`, com titular auditado por contato; faltam as ferramentas que hoje exigem CPF. A área não tem CPF por regra (ADR-0014). | mcp_hub | Fases 4 e 7 | em andamento | 2026-10-16 |
| P-07 | P0 | Locaweb `portal_apm`: criar usuário **novo somente leitura** com SELECT só em `pw_portal_{posts,postmeta,terms,term_taxonomy,term_relationships,yoast_indexable}`, verificar suporte a TLS (`have_ssl`), restringir origem ao IP da EC2. Depois de migrar o appapm (P-16), revogar `portal_apm@%`, marcado como vazado em `PENDENCIAS_AWS.md`. | infra / Planeta W | Fase 5 (até lá `WP_MODE=stub`) | aberta | 2026-10-16 |
| P-36 | P1 | Replicar o `.env` da área (alterado em 19/10 e 20/10: `PUBLIC_BASE_URL`, `SESSION_ENC_KEYS`, `CARTEIRINHA_HMAC_KEY`, `HUB_MODE`, `SMTP_MODE`, `AUTH_MODE=oidc`, `OIDC_SCOPES`, sem `DEV_STUB_TOKEN`) no Secrets Manager `prod/area-associado/env`; depois apagar `.env.bak-20261019-dominio` e `.env.bak-20261020-oidc`. Trocar `SESSION_ENC_KEYS` derruba todas as sessões; trocar `CARTEIRINHA_HMAC_KEY` invalida os QRs. **2026-10-30:** runbook em `OPERACAO.md` §3 (TI-73); hoje há 3 `.env.bak-*` no disco; `alertas.sh` acusa. **2026-11-03: decisão do usuário — não replicar no cofre por ora; os `.env.bak-*` ficam no disco.** Risco aceito: sem cópia fora da EC2, perder o disco perde `SESSION_ENC_KEYS`, `CARTEIRINHA_HMAC_KEY` e `LOG_HASH_KEY` (irreversível). `scripts/alertas.sh` segue avisando dos `.bak`. | operador | recuperação do servidor | adiada por decisão do usuário | 2026-10-19 |
| P-08 | P1 | Parecer sobre licença e multiplexação do F&O antes de exibir dados do ERP a associados (`totalpass/docs/RUNBOOK_ERP_FO.md:205-211`). | TI / jurídico | Fase 7 | aberta | 2026-10-16 |

## Segurança e identidade

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-37 | P0 | **Contatos de teste no CRM para a agência.** A área entra só pelo Login APM; quem não é associado precisa de um contato no Dataverse com tipo e situação associativa válidos (o escopo `carteirinha` recusa sem eles, ADR-0016) para fazer o cadastro normal no Login APM. Criar um contato por pessoa da agência (ou um compartilhado), marcado como teste, e remover na virada. Hoje existe um usuário de teste do IdP, usado na validação de 20/10. | CRM admin | acompanhamento pela agência | aberta | 2026-10-20 |
| P-22 | P1 | Contraste AA: a paleta dos mockups (ADR-0017) tem pares que falham em WCAG AA: branco sobre `#009581` = 3,74, `#8A979D` sobre branco = 3,00 e o azul das tags `#007EA3` sobre `#E8F2F6` = 4,09. Em 2026-10-20 ganharam variantes `-texto` (`#00675A` 6,80; `#5E6E75` 5,30; `#006B8C` 5,30) em `frontend/src/styles/tokens.css`, e o axe passa nas 4 telas existentes. Falta: validação visual da agência para as variantes e os pares das tags de status nas telas da Fase 4. | Vitrine / agência | Fase 4 (tags) | aberta | 2026-10-17 |

## Definições de negócio e conteúdo

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-10 | P1 | Decidir as lacunas restantes da spec em [REQUISITOS §11](REQUISITOS-minha-apm.md): regra de validade da carteirinha (hoje omitida), o que é "Inscrever" e "Garantir minha vaga", destino de "Gerenciar", vocabulário único de categorias, textos dos toasts não definidos. E-mail e remoção de foto foram decididos em 2026-10-17. **2026-10-29:** a spec v2 responde boa parte (tipos de ativação 1–6, estados de elegibilidade, categorias); o que resta de catálogo está em P-48 e os textos em P-44. | negócio | Fases 4 e 5 | aberta | 2026-10-16 |
| P-11 | P1 | Conteúdo: número da Central APM no WhatsApp e mensagem pré-preenchida, link de cada comunidade (convite de grupo, não `wa.me` 1:1), oferta da semana e catálogo do Clube. | comunicação | Fase 6 | aberta | 2026-10-16 |
| P-12 | P2 | Fonte de dados para Mensalidade Zero, patrocínio, cashback e Fatura de valor. Até existir, as flags ficam forçadas desligadas (ADR-0007). | negócio | Fase 8 | aberta | 2026-10-16 |
| P-13 | P2 | Wallet Apple/Google: conta developer, certificado de assinatura `.pkpass`, service account do Google Wallet. | TI | Fase 8 | aberta | 2026-10-16 |
| P-38 | P2 | **Imagens e números dos mockups.** A área (e a página de entrada, hoje guardada sem rota) usam gradientes e formas em CSS no lugar das fotos, e só o número "95 anos". Falta a Comunicação/agência enviar, com direito de uso e em resolução de produção, a foto do hero da entrada (`0ebf4ef7.png`), o selo "95 anos" (`c2cd4d74.png`) e as fotos dos cards (Painel `0ebf4ef7.png`, avatares e capas do banco de imagens). Também falta aprovar com fonte, ou retirar, "+40 benefícios" e "60 regionais" (REQUISITOS LA-14). As imagens entram em `app/static/` (CSP `img-src 'self'`). Os arquivos já existem no pacote dos mockups (artifact `KvCeCEoD531nxQ1GyaVjMo`: logos oficiais, foto do hero aparentemente gerada por IA e fotos de banco); em 2026-10-20 o usuário optou por publicar sem eles até a confirmação do direito de uso. | Comunicação / agência | cutover | aberta | 2026-10-20 |
| P-39 | P2 | **Mockups da agência no repositório.** Os 12 `*.dc.html` que definem o visual (ADR-0017) só existem colados na conversa de 2026-10-20, sem `support.js` e sem `assets/`. Pedir à agência o pacote completo e versionar em `docs/mockups/` (sem executar o `support.js`; só referência), para que as fases 3 a 8 sigam a mesma fonte. | Agência / Vitrine | Fase 3 (telas novas) | aberta | 2026-10-20 |

## Técnicas e operação

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-15 | P1 | Política de retenção e purga de `evento_uso`, `noticia_cache`, `evento_cache` e `job_execucao`, executada pelo operador (sem DELETE pela aplicação). **2026-10-29:** prazos por tabela vêm do jurídico (P-54); mecanismo proposto = partição mensal + `DROP PARTITION` administrativo (levantamento TI-02, TI-28). Antecipar para antes da Fase 4. | Atlas | Fase 4 | aberta | 2026-10-16 |
| P-16 | P2 | Migrar o appapm para o usuário somente leitura novo da Locaweb (P-07) e aposentar `portal_apm@%`. | appapm | — | aberta | 2026-10-16 |
| P-21 | P1 | Mapear no WordPress `portal_apm` como as **notícias** são publicadas (post type, taxonomia de tema, campos de imagem e fonte). As queries do appapm só cobrem `evento`, `banner-header` e `regional`. Exige o usuário RO de P-07. | Integrador / Planeta W | Fase 5 | aberta | 2026-10-17 |
| P-27 | P0 | Credencial SMTP própria da área (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) com remetente autorizado (SPF/DKIM). Sem ela a troca de e-mail fica indisponível em produção (`SMTP_MODE=stub` é proibido lá). | TI / infra | produção da troca de e-mail (ADR-0015) | aberta | 2026-10-17 |
| P-29 | P0 | **Flows, plugins e workflows que disparam em update de `contact`** no Dataverse: mapear quais existem, o que fazem quando a área muda celular, telefone, e-mail, endereço ou foto, e se algum notifica o associado, sincroniza com outro sistema ou sobrescreve campo. **O escopo `ferramentas:escrever` não é marcado na conta `area-associado` em produção antes disso.** | CRM admin | escrita real no CRM | aberta | 2026-10-19 |
| P-30 | P1 | Homologar a foto no CRM: `entityimage` com `CanStoreFullImage` (senão o CRM guarda só 144×144) e `MaxSizeInKB` (o `check_conectores` do hub imprime os dois); confirmar que o PATCH com base64 é aceito e que `foto_obter` devolve a imagem gravada. Plano B no hub se o PATCH falhar: `PUT .../entityimage` com `application/octet-stream`. **2026-10-21 (hub):** o CRM está com `CanStoreFullImage=False` e `MaxSizeInKB=10240`, ou seja, guarda só 144×144. A miniatura local (128×128) não sofre; quem mais lê a foto do CRM recebe 144×144. Decidir com o CRM admin se liga a imagem cheia. | CRM admin / Integrador | foto real no CRM | aberta | 2026-10-19 |
| P-31 | P1 | Confirmar com o negócio que os 7 atributos do endereço no `contact` têm o mesmo significado do lead (`address1_line1` logradouro, `alf_numero_endereco` número, `address1_line2` complemento, `alf_bairro` bairro, `address1_city`, `address1_stateorprovince`, `address1_postalcode`) e então ligar `CRM_ENDERECO_HABILITADO=true` no hub. Até lá a área mostra "o endereço ainda não pode ser alterado por aqui" e o hub responde 409. A Metadata prova só que os campos existem. | negócio / CRM admin | edição de endereço | aberta | 2026-10-19 |
| P-32 | P2 | Convenção de formato de telefone no CRM. A área e o hub gravam `(11) 91234-5678` / `(11) 3188-6200`; confirmar se flows, discador ou integrações esperam outro formato (E.164, só dígitos) antes de virar padrão. | CRM admin / negócio | — | aberta | 2026-10-19 |
| P-33 | P2 | No ensaio ponta a ponta de 19/10, 1 de 9 emissões de token do hub para a área voltou 503 `temporarily_unavailable`; não se repetiu em 8 tentativas e o log daquela rodada se perdeu com o container. Após implantar o hub, vigiar `oauth/token indisponível` e `nenhuma chave de assinatura ativa` no log; se aparecer, investigar o cache do chaveiro e o pool do RDS. | Integrador | — | aberta | 2026-10-19 |
| P-24 | P2 | Páginas Jinja fora da SPA (login stub e erro) ainda usam o visual antigo (Neo Sans, paleta azul/dourado). Unificar com a linguagem de `entrada.css` (Sora + paleta do mockup). Entrada (guardada sem rota) e `/verificar/{token}` já foram feitas em 2026-10-20. | Vitrine | cutover | aberta | 2026-10-17 |
| P-25 | P2 | Sem CI: pytest, Vitest, lint e typecheck rodam no build da imagem, mas o e2e (Playwright) e o Lighthouse são manuais. Avaliar GitHub Actions com a deploy key do repositório. **2026-10-30:** `scripts/deploy.sh` (tag, smoke, rollback) e `docs/api/openapi.json` verificado no build já existem; GitHub Actions é TI-77 (Onda 5, EXT-30). WebKit no e2e configurado (`E2E_WEBKIT=1`) mas o host não tem as libs: `npx playwright install --with-deps webkit` exige root (Estivador). | Estivador | — | aberta | 2026-10-17 |
| P-26 | P2 | O host não tem o plugin `docker-buildx`: build com BuildKit falha; hoje se usa `DOCKER_BUILDKIT=0`. Instalar o plugin (`apt install docker-buildx`) é mudança de sistema, decisão do operador. | infra | — | aberta | 2026-10-17 |

| P-41 | P1 | **Respondida ao mcp_hub em 2026-10-30** (hipótese de **10 mil associados ativos** até o número real, EXT-23/P-49). **Conta web `area-associado`:** `perfil_consultar` 1×/24 h por associado que abre o Perfil (≈ 5 %/dia → ≈ 500/dia) + 1 por worker a cada deploy; `/verificar` em tempo quase real (TI-45, Onda 2) via `associado.situacao` com cache 5–15 min e limite global 60/min por processo (2 workers → teto 120/min; ≈ 100–300/dia); escrita < 50/dia. Total ≈ 1.000 registros PII/dia, pico teórico 150/min → **pedir 200/min e manter 5.000/dia** (hoje 120/min e 5.000/dia; subir só quando TI-45 entrar). **Conta `area-associado-jobs`** (Onda 2; `client_credentials` próprio, só `ler`, grants exatos em `situacao` e `perfil_consultar`, mesma allowlist): situação noturna em lote 10.000/noite (01h–05h, ≤ 5/s) + `diff_cadastro` só para quem acessou em 90 d (≈ 3.000 `perfil_consultar`/noite) → **300/min e 15.000 PII/dia**; cai para ≈ 2.000/dia com `associado.alterados_desde(cursor)` (TI-51). Dataverse: ≈ 26.000 pedidos/noite, abaixo de 6.000/5 min. Rever com `evento_uso` + `auditoria_chamada` 30 dias após a virada. Hub registrou como M-1/M-8. | usuário (painel do hub) | taxa e cota das duas contas | **respondida; aplicação pelo operador** | 2026-10-21 |
---

## Dependências externas da spec v2 (levantamento de 2026-10-29)

Cada item corresponde a um `EXT-nn` de `docs/LEVANTAMENTO-TECNICO-spec-v2.md` §13 (o levantamento diz
o que a TI faz enquanto espera). Estado inicial: aguardando terceiro.

| ID | Pri | Item | Dono | Bloqueia | Estado | Desde |
|---|---|---|---|---|---|---|
| P-42 | P1 | **Mockups que não existem** (EXT-02): P04 ficha e 6 estados, P05 lista/linha do tempo/avaliação, P06 v2, P08, P13 consentimentos/LGPD, P14, P12 por categoria, P15 sino, aba "Mais", selos textuais; aceite visual do sino. Até lá a TI constrói com os componentes e a linguagem do ADR-0017 e pede aceite depois. | agência | aceite visual das fases 3–4 | aguardando terceiro | 2026-10-29 |
| P-43 | P2 | **Identidade visual formal** (EXT-03): a spec §14 pede Verdana e `#616365`; o projeto segue Sora e a paleta do mockup (ADR-0017, decisão do usuário). Botão principal verde `#009581` × gradiente navy (contraste 3,74). Registrar a divergência com Marketing/agência; ADR-0017 vale até resposta. | Marketing APM / agência | — | aguardando terceiro | 2026-10-29 |
| P-44 | P1 | **Textos finais na voz §3.3** (EXT-05): chamadas de rota, estados vazios/erro, rótulos dos 6 estados de elegibilidade e 7 status, "como calculamos", FAQ inicial (≥ 20), motivos de cancelamento, pedidos comuns. Até lá, textos da spec marcados como proposta. | Encantada / Marketing APM | Fases 3–4 (aceite) | aguardando terceiro | 2026-10-29 |
| P-45 | P2 | **Testes de usabilidade** com associados de faixas etárias diferentes (§14) e iPhone real para e2e manual (EXT-07). | Marketing / Encantada | aceite de P02/P03 e tamanho de fonte | aguardando terceiro | 2026-10-29 |
| P-46 | P1 | **Contrato de comunicação com o RD Station** (EXT-08): app OAuth2 privado para a área (ou reuso do app do totalpass), campos `cf_apm_*` novos, tabela gatilho A01–A20 → `conversion_identifier` → fluxo, quem aplica o limite 2/semana, nomes de UTM/código do gatilho, dono único dos campos (sincronia CRM→RD `cf_crm_contato_*` marcada "Não Funcionando", `birthdate` padrão). Até lá `RD_MODE=stub` e outbox acumulando. | Marketing (dono da conta RD) + CRM admin | envio real dos gatilhos; indicador 10; A18 | aguardando terceiro | 2026-10-29 |
| P-47 | P2 | **Destino dos dados analíticos e ferramenta de painéis** (F0-06, EXT-09; DEC-16): views RO + ferramenta interna; nunca script de terceiro na SPA (CSP). Quem acessa cada painel do §11.5. | Marketing / Encantada / usuário | B12 | aguardando terceiro | 2026-10-29 |
| P-48 | P0 | **Catálogo inicial validado** (EXT-10; amplia P-10): 30–40 benefícios com categoria, tipo de ativação, carência (regulamento 01/03/2024), categorias permitidas, região, vigência, parceiro, canal e prazo de retorno, modalidade de mensuração e **valor de referência aprovado pelo Financeiro**. É item do gate F0 (§15.1). Até lá: tabelas vazias e fixture de teste; nenhum card real. | Benefícios e parcerias + Financeiro (+ Jurídico: carência do Clube) | Fase 4 (P03/P04/P06 reais), A03/A05 | aguardando terceiro | 2026-10-29 |
| P-49 | P1 | **Parâmetros e definições de negócio** (EXT-11; §15.5): dias de atraso que suspendem, prazo de retorno padrão, prazo de avaliação, "mudança de categoria reinicia carência?" (recomendação da spec: não), carência do Clube, motivos de cancelamento, vocabulário/códigos de categoria e contagem da base conciliada. Até lá `parametro` com padrões documentados e de-para provisório. | Presidência / Financeiro / Benefícios / Jurídico | Fase 4 (elegibilidade) | aguardando terceiro | 2026-10-29 |
| P-50 | P2 | **Parceiros com API e contratos técnicos** (EXT-12; B04): por parceiro, autenticação, payload mínimo (LGPD), status de volta, prazo, host de destino por benefício, exigência de SSO/código pessoal. Cada um entra por ADR própria (ADR-0009). Até lá tipo 2 por canal manual + CSV. | Benefícios + parceiros | tipo 2 por API (F2) | aguardando terceiro | 2026-10-29 |
| P-51 | P2 | **Fornecedores de MBE, biblioteca, Clube Certo e plataformas de eventos/IESAPM** (F0-01, EXT-13): mecanismo de acesso único (o Login APM como provedor; nunca identidade na URL) e API de retorno (resgate, inscrição, presença, certificado). Até lá link rastreado e inscrição como interesse. | Benefícios / fornecedores | tipos 1/5/6 reais; CLU-01..03; EVE/CON | aguardando terceiro | 2026-10-29 |
| P-52 | P2 | **Qualicorp** (EXT-14): custo e forma da integração (API ou relatório). F2. | Benefícios + Qualicorp | F2 | aguardando terceiro | 2026-10-29 |
| P-53 | P1 | **Arquivos CSV do plano B** (EXT-15; §13.3): parceiros sem API entregam até o dia 10 pelo canal definido em DEC-05 (upload no backoffice na F1; nunca e-mail). Parser e validador são TI. | Benefícios + parceiros | Meu valor v1 com importações; B06 | aguardando terceiro | 2026-10-29 |
| P-54 | P1 | **Jurídico/encarregado de dados** (EXT-16; amplia P-15): textos e finalidades dos consentimentos com versão; base legal por finalidade; prazo de guarda por tabela (solicitação, auditoria, consentimento, uso/valor, `evento_uso`, comunicação, `job_execucao`); procedimento do pedido de exclusão (anonimização, sem DELETE — DEC-06; prazo de resposta); quem opera a fila. Até lá consentimentos atrás de flag com texto v0 e retenção pelas propostas das migrações. | Jurídico + encarregado | Fase 3b (P13 LGPD), retenção | aguardando terceiro | 2026-10-29 |
| P-55 | P2 | **Parecer sobre dados de saúde** para a rede de encaminhamento (ENC-01, EXT-18). F3; antes vêm DIR-01/COM-01. | Jurídico | P16 ENC-01 | aguardando terceiro | 2026-10-29 |
| P-56 | P1 | **Atributos do `contact` no CRM** (EXT-19; §13.2): data de nascimento (completude; exposta só como faixa de carreira ou `confere: bool`), nome social, especialidades, regional/distrital, isenção/remição, documentação pendente; se `sol_associacao` registra categoria ou só status. Destrava personalização (§7.1), elegibilidade por região, nascimento no primeiro acesso do IdP, A13/A14/A19. | CRM admin | Fase 4 (fase de carreira, região), IdP | aguardando terceiro | 2026-10-29 |
| P-57 | P2 | **Sandbox do Dataverse** (ou contatos de teste marcados) acessível por uma conta do hub, para a homologação (EXT-22; DEC-30). | CRM admin | homologação antes da escrita real | aguardando terceiro | 2026-10-29 |
| P-58 | P1 | **"Novo sistema de cadastro e cobrança"** (EXT-24; §13.1/13.2, F0-02): não aparece em nenhum repositório. Definir o que é, quem desenvolve, API, avisos automáticos (webhooks), situação financeira, **segunda via (PDF, linha digitável, Pix)** e renovação. Premissa da TI (DEC-17): D365 + eventos no hub; a área só muda o contrato por `contact_id` atrás do hub. Até lá ERP só leitura, sem 2.ª via ("fale com a Central"); jobs de diferença no lugar de avisos. | Diretoria / Financeiro / TI | P08, A09, A10, indicadores 4 e 11 | aguardando terceiro | 2026-10-29 |
| P-59 | P1 | **IAM da EC2** (EXT-27): ampliar a role `EC2-ReadOnly-Billing` (ou perfil humano) com `rds:CreateDBSnapshot`, `rds:RestoreDBInstanceFromDBSnapshot`, `secretsmanager:GetSecretValue` em `prod/area-associado/env`, `cloudwatch:DescribeAlarms`, opcional `logs:*`. Até lá o operador faz pelo console. | AWS admin | backup/restore ensaiado, `env_check`, logs | aguardando terceiro | 2026-10-29 |
| P-60 | P1 | **Teste de restauração do RDS** executado e datado (snapshot → instância temporária → `db_check` e contagens → descarte); retenção 7 → 14 dias; export de logs `error`/`slowquery` e Performance Insights (EXT-28; §14 "cópia de segurança diária com teste de restauração"; DEC-33). Hoje: snapshots diários, PITR, **zero teste**. | operador / AWS admin | cutover | aguardando terceiro | 2026-10-29 |
| P-61 | P1 | **Monitor externo** (EXT-29). **2026-11-03: será no Grafana**; orientação para a sessão do servidor do Grafana em `docs/handoff/MONITOR-EXTERNO-GRAFANA.md` (9 checagens, 4 regras, bloco de resposta). Antes: conta (UptimeRobot/Better Stack ou similar) com contatos de alerta para os 7 hosts; decidir o destino do Datadog pago. Nenhum monitor externo desde 14/09. | operador | alertas (indicador 14) | aguardando terceiro | 2026-10-29 |
| P-62 | P2 | **Cloudflare Access e regras** (EXT-31): Zero Trust com IdP corporativo e MFA para `admin`/`hml`; lista de IPs/VPN da APM para allowlist; rate limit/WAF para `minha.apm.org.br` (`/auth/*`, `/verificar/*`). | Cloudflare admin / operador | backoffice, homologação | aguardando terceiro | 2026-10-29 |
| P-63 | P2 | **Egress e armazenamento** (EXT-32): confirmar saída do SG da EC2 para Locaweb 3306 e API do RD (443) a partir do container de jobs; bucket S3 privado + role `PutObject` só se DEC-05 escolher S3 para o CSV. | AWS admin | jobs WP/RD; canal do CSV (F2) | aguardando terceiro | 2026-10-29 |
| P-64 | P2 | **Canal celular para OTP e régua** (EXT-35): WhatsApp API oficial (Fortics, já previsto no IdP e desligado) ou provedor SMS, com contrato, remetente e limites. SMS não existe em nenhum sistema. Até lá só e-mail; P13 não mostra WhatsApp/SMS (regra 19). | TI / contratos / Marketing | OTP por celular no IdP, A02, canais em P13 | aguardando terceiro | 2026-10-29 |
| P-65 | P1 | **Entra ID da APM para o backoffice** (EXT-36; DEC-03): tenant, app registration, grupos → 8 perfis (§9.1), política de MFA. O backoffice nunca usa o `login_associado` (IdP de associados). | TI / diretoria | backoffice (B01–B13) | aguardando terceiro | 2026-10-29 |
| P-67 | P2 | **Rotação do token da carteirinha** (DEC-09): o token é HMAC determinístico do `contact_id`; hoje a revogação é desfeita quando o CRM volta a dizer "ativo". Rotacionar exige versionar o token (coluna + chave por versão) — ADR futura. | Sentinela | — | aberta | 2026-10-30 |
| P-68 | P2 | **`CENTRAL_EMAIL`** (endereço da Central para os avisos internos A05/A16 e do formulário): sem ele, o job grava `suprimido: sem_credencial`. Definir o endereço junto com a credencial SMTP (P-27). | Central / TI | avisos internos por e-mail | aguardando terceiro | 2026-10-30 |
| P-69 | P2 | **Conteúdo da Ajuda**: FAQ inicial (≥ 20 perguntas), `central_horario` e `central_telefone` em `parametro` (preenchidos em 2026-11-03; falta validar com a Central). Faz parte de P-44; carga por SQL do operador até existir backoffice. | Marketing APM / Central | P14 completa | aguardando terceiro | 2026-10-30 |
| P-70 | P3 | **Falso alarme de job nunca executado**: `app/jobs/rastro.py` marca `parado` quando não existe execução ok, então um job diário recém-ligado (`situacao_carteirinhas`) aparece `PARADO` em `--estado` e dispara alerta em `scripts/alertas.sh` até a primeira execução às 03:00. Ajuste proposto: sem execução, contar o atraso a partir da subida do serviço. Some sozinho depois da primeira execução. | Integrador (código de jobs, exige plano) | alerta falso só até a primeira execução de cada job novo (o histórico em `job_execucao` sobrevive à recriação do container) | aberta | 2026-11-03 |
| P-71 | P2 | **`docker logs` ilegível no `nginx_porteiro`** (Docker 29.1.3, json-file com rotação 3×50m): `--since` não devolve nada em nenhuma janela e `--tail` acima de ~100 mil linhas devolve um trecho anterior ao restart de 29/10 no lugar das linhas recentes. Contornado em 03/11 em `scripts/alertas.sh` e `~/verificar-pos-reboot.sh` (leitura com conferência da última linha e filtro pelo carimbo). Antes disso as checagens de 5xx/crit/real_ip do porteiro passavam sem ler nada. Causa raiz não investigada (arquivo rotacionado corrompido? bug do Docker 29.1). | Estivador / operador | qualquer leitura de log do porteiro por janela | contornada, causa aberta | 2026-11-03 |
| P-72 | P3 | **Swap com 1 arquivo de 2 GB**; em 02/09 eram 6 GB em dois arquivos (`PENDENCIAS_AWS.md`). O segundo sumiu, provavelmente no upgrade para t4g.large (8 GB de RAM; 0,6 GB de swap em uso em 03/11). Decidir: recriar ou baixar a expectativa do pós-reboot para 1. | operador | `verificar-pos-reboot.sh` acusa `swap: 1 arquivos (esperado 2)` | aberta | 2026-11-03 |
| P-73 | P3 | **Container de teste esquecido `kind_agnesi`**: criado em 30/10 por uma frente da Onda 2 (`pytest` de jobs e `db_check`, repositório montado, `.env` = `/dev/null`, sem porta), travado há 4 dias e `unhealthy`. Remover: `docker rm -f kind_agnesi`. | operador | pós-reboot acusa container fora da lista | aberta | 2026-11-03 |
| P-74 | P1 | **Ferramenta de status no hub** (`solicitacao.status_atualizar` ou equivalente): o app user do hub não tem Write em incident/opportunity, então cancelamento e resposta do associado não chegam ao CRM. Enquanto isso a área recusa cancelar/responder pedido já no CRM (409 `na_central`, tela com protocolo) — **divergência com a spec** (cancelar "enquanto o parceiro não atendeu", DIV-24) — e mudança local depois do envio fica `crm_sync='retido'` (reprocessável). Pedir plano no mcp_hub. | mcp_hub / William | autoatendimento de cancelamento e resposta após o envio | aberta | 2026-11-04 |
| P-75 | P2 | **Consulta por cursor no hub** (`solicitacao.alteracoes_desde(cursor)` filtrada pelo canal Minha APM): hoje a sincronização usa `listar` por contato, que gasta cota pelo histórico do contato (registros da Central também contam). Com cursor, dezenas de linhas/dia; cadência poderia cair de 6 h para minutos. | mcp_hub | custo de cota e atraso de até 6 h no status | aberta | 2026-11-04 |
| P-76 | P2 | **Confirmações do hub/CRM para a sincronização**: (a) option set `statuscode` de `incident` e `opportunity` do tenant (a área usa os códigos padrão do Dataverse: 0/1, 0/2, 0/3, 0/4, 1/5, 1/1000, 2/6, 2/2000; customizado ativo = sem transição + divergência); (b) `detalhes: [{"campo": "contact_id\|assunto_id\|time_id"}]` no 404 `nao_encontrado` do `criar` (hoje a área distingue pela mensagem fixa); (c) escolha final de assunto por tipo pela Central (candidatos: Declarações, Cancelamento associativo). | mcp_hub / Central | precisão do mapeamento | aberta | 2026-11-04 |
| P-77 | P1 | **Painel do hub para o espelho**: conta `area-associado-jobs` com escopo `ferramentas:escrever` e grants exatos `solicitacao.criar` e `solicitacao.listar` (nunca `solicitacao.*`); cota PII de 15.000 → **25.000/dia** (situação noturna até 10.000 + sincronização até 10.000 + margem). O mapa `CRM_SOLICITACAO_CONTAS` já tem `area-associado-jobs` (conferido em 04/11). Corrigir no RUNBOOK do hub o §3.1 passo 4b, que diz que os jobs da área só leem. | William (painel) / sessão do hub | ensaio e ligar o espelho | aberta | 2026-11-04 |

### Decisões pendentes da spec v2

As 36 decisões (DEC-01..36: máquina de estados, backoffice, CSV, exclusão, PWA, notificações, revogação
da carteirinha, API de consulta de associação, navegação, jobs, homologação, deploy, OpenAPI…) estão no
§11 de `docs/LEVANTAMENTO-TECNICO-spec-v2.md`, cada uma com opções e recomendação. As 46 divergências
(DIV-01..46) estão no §10. Nenhuma delas reabre decisão já tomada pelo usuário.

## Roteiro por fase

Cada fase tem plano próprio e aprovação antes de codar (CLAUDE.md, sessão 4). A ordem de execução por **ondas** está em [`PLANO-EXECUCAO.md`](PLANO-EXECUCAO.md): Onda 1 (base transversal) feita em 30/10; Onda 2 = Fase 3 ampliada; 3 = 3b; 4 = Fase 4; 5 = integrações reais (Fases 5–7); 6 = backoffice; 7 = F2/F3.

| Fase | Entrega | F da spec | Pendências que bloqueiam | Estado |
|---|---|---|---|---|
| 0 | Requisitos, ADRs, pendências, concluídos, CLAUDE.md; **levantamento da spec v2 (29/10)** | F0 | gate F0 parcial (catálogo e contratos de parceiro são externos: P-48, P-50) | concluída em 2026-10-17; levantamento em 2026-10-29 |
| 1 | Fundação: Vite + shell + tokens + fontes, `spa.py`, sessão cifrada, CSRF por header, `uso.py`, `flags.py`, `sql/003-005`, Dockerfile multi-stage, vhost, testes de rotas | F1 | — | código concluído em 2026-10-17; no ar em minha.apm.org.br desde 2026-10-19 |
| 2a | Perfil e carteirinha na área: cache do perfil, contato, e-mail com código, foto, carteirinha com QR, verificação pública, escopo `carteirinha` | F1 (P07, P13 parcial) | — | código concluído em 2026-10-17; no ar em minha.apm.org.br desde 2026-10-19 |
| 2b | mcp_hub com perfil, contato e foto no CRM (contrato em `docs/CONTRATO-HUB.md`) e troca de `HUB_MODE` para `real` | F1 (INT-01) | P-41, P-29, P-30, P-31 | no ar em leitura desde 2026-10-21; escrita depois da P-29 |
| 3 | Solicitações **ampliada**: `sql/008` com os 8 status da spec, `sql/009` `job_execucao`, serviço de jobs, API, P05, **P14 (FAQ + cancelamento como solicitação)**, outbox de comunicação e `notificacao` produzidas (envio desligado), transacionais A04/A05/A06, carteirinha em tempo quase real | F1 (P05, P14, SOL, A04–A06, A16) | P-06 só para o espelho; P-27 para e-mail real; P-41 para a situação na verificação | próxima |
| 3b | P13 preferências, consentimentos versionados, baixar dados, pedir exclusão (anonimização), retenção; RD Station com stub | F1 (PER-02/03, LGPD) | P-54 (textos e prazos), P-46 (RD) | — |
| 4 | Benefícios: `sql/010` catálogo como dado + `sql/011` valor (antecipado da 8), elegibilidade/carências, ativações por tipo, recomendação v1, home em blocos, TotalPass via hub + deep-link | F1 | P-04, P-48, P-49, P-22; DEC-03/14/15 | — |
| 5 | Notícias e eventos: `portal_wp.py` só no job, caches, temas, salvos, inscrições (interesse), banner do Congresso | F2 (P10, P11) | P-07, P-21, P-51 | — |
| 6 | Clube (link rastreado), trilha completa, comunidade (F3) | F1 link / F2 / F3 | P-11, P-51, P-55 | — |
| 7 | Financeiro P08 via hub `financeiro.*` atrás de `erp_financeiro` (situação, mensalidades; 2.ª via só com fonte) | F1 condicional | P-04, P-08, P-58 | — |
| 8 | Patrocínio (P17), wallet, "N vezes" com total pago — Meu valor v1 foi para a Fase 4 | F2/F3 | P-12, P-13, P-58 | — |
| — | **Backoffice B01–B13** (sem fase; F1 na spec) | F1 | DEC-03, P-65, P-62, P-47 | a decidir |
