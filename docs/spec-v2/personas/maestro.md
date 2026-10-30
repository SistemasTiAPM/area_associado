# ⚙️ Maestro (Backend) — prontidão da API e do domínio para a spec v2 (30/09/2026)

Levantado em 2026-10-29 sobre `HEAD a2af85e`. Fontes: `docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md`
(citada como `spec:L`), `docs/spec-v2/INDICE-IDS.md`, os três inventários de 29/10 (`inventario-codigo.md`,
`inventario-requisitos.md`, `inventario-vizinhos.md`, citados como `inv-codigo`, `inv-req`, `inv-viz`), código e docs
do repositório. Só leitura; nada foi alterado.

Legenda de estado: ✅ atende · 🟡 parcial · ⬜ não existe, pode nascer aqui · ⛔ bloqueado por terceiro/decisão
externa · ⚠️ diverge do que já decidimos (REQUISITOS/ADR) · 🔒 decisão do usuário que não se reabre.
"Fase spec" = F0–F3 da spec (§5.2, §15); "fase roteiro" = fases 1–8 de `docs/PENDENCIAS.md:106-117`.

**Base comum a todos os itens (o que a API já tem e os novos recursos herdam):** sessão cifrada + `require_associado`
(`app/spa.py:67`, `app/api/v1/deps.py:22`); CSRF por header `X-CSRF-Token` + `Sec-Fetch-Site`/`Origin` + tipo de
conteúdo (`app/csrf.py:58`); contrato único de erro `{erro, mensagem, request_id, detalhes?}` (`app/api/erros.py:3-4`,
`61-81`); códigos já fechados em `docs/REQUISITOS-minha-apm.md:166-168`; escrita desligada → 404 `recurso_desligado`
(`app/api/v1/deps.py:35-39`); mapa `HubError` → HTTP (`deps.py:46-51`; `docs/CONTRATO-HUB.md:108-119`); flags por
enum fechado com cache 60 s entregues em `GET /sessao` (`app/flags.py:27-36,54-63`); limite por associado em memória
por processo (`app/limites.py:1-6`); `evento_uso` com catálogo fechado e transação própria (`app/uso.py:83-120`,
`224-239`); chamadas bloqueantes por `run_in_threadpool` em toda rota (`app/api/v1/perfil.py:200-363`). OpenAPI só com
`APP_ENV=development` (`app/config.py:157-158`, `app/main.py:140-142`) e 403 na borda
(`deploy/nginx_porteiro/area_associado.conf.example:61-63`).

---

## Itens

### P02 · Início (blocos 1–9, §7.2; ADM-05)
- **Spec pede:** saudação com tratamento e categoria, atalho da carteirinha, busca e os 9 blocos com regra de
  exibição e ordem (`spec:313-327`, tabela `spec:621-631`); bloco vazio não aparece (`spec:159`); no máximo 1
  patrocinado entre os 4 primeiros recomendados (`spec:321-322`); destaque editorial por segmento com vigência,
  um por vez (`spec:633-634`); eventos `home_vista`, `home_bloco_clicado`, `recomendacao_dispensada` (`spec:323`).
- **Existe hoje:** `Inicio.tsx` com saudação, selo tipo·situação e 2 atalhos, tudo fixo (`inv-codigo:34`); nenhum
  endpoint de home; `GET /sessao` entrega só identidade, flags e config (`app/api/v1/sessao.py:55-77`);
  REQUISITOS RF-HO-01..11 descrevem blocos fixos da spec antiga (`docs/REQUISITOS-minha-apm.md:256-320`);
  eventos `pagina_ver`/`categoria_abrir` existem, `home_bloco_clicado`/`recomendacao_dispensada` não
  (`app/uso.py:84-87`; `INDICE-IDS.md:89-93`).
- **Falta:** SQL `destaque_editorial(segmento, inicio, fim, titulo, texto, link)` (ADM-05) e
  `recomendacao_dispensa(contact_id, beneficio_id, ate)` · domínio `app/dominio/inicio.py` (montagem dos blocos,
  cada bloco com fonte própria e "sem conteúdo = omitido"), `recomendacao.py`, `elegibilidade.py`, `valor.py` ·
  API `GET /api/v1/inicio`, `POST /api/v1/recomendacoes/{slug}/dispensar` · ações `home_bloco_clicado(ui)`,
  `recomendacao_dispensar(servidor)`, `home_vista` com `blocos` em `detalhes` · integrações: pendência financeira
  (ERP, ⛔ P-08), documentação pendente (CRM, campo não contratado), renovação em 30 d (cobrança, ⛔) · frontend:
  página por blocos.
- **Estado:** 🟡 (saudação) / ⬜ (blocos 1, 3, 4, 6) / ⛔ (pendência financeira e renovação, bloco 2 com "total pago").
- **Fase:** spec F1 (HOM-01 regras), F2 (REC-01, CLU-03, NEWS-01) · roteiro: fase 4 (home), hoje sem motor.

### P03 · Benefícios (CAT-02/03)
- **Spec pede:** resumo (ativos, disponíveis, valor no ano), filtros Todos/Disponíveis para mim/Ativos/Novos, 8
  categorias, busca, card com condição em uma linha + selo + botão; ordem padrão disponíveis-não-usados por
  afinidade → ativos → "libera em"; fora da categoria = "exclusivo para associado efetivo" (`spec:334-351`);
  busca sem resultado sugere categorias e **registra o termo** (`spec:353-354`); eventos `busca`, `beneficio_visto`.
- **Existe hoje:** rota `beneficios` em construção (`inv-codigo:34`); REQUISITOS RF-BE-01..10 com `GET /beneficios`,
  `POST /beneficios/{slug}/ativar|desativar [C]`, seed de 19 itens em `sql/009` + `catalogo.py`
  (`docs/REQUISITOS-minha-apm.md:362-386`, `inv-req:84-86`); ações `filtro_aplicar`, `categoria_abrir`,
  `beneficio_abrir` (`app/uso.py:86-91`); allowlist de UPDATE já prevê `beneficio_ativacao`
  (`scripts/db_check.py:22-35`).
- **Falta:** SQL `beneficio` com colunas de elegibilidade (`categorias_permitidas JSON`, `carencia_meses`,
  `regional`, `vigencia_inicio/fim`, `tipo_ativacao`, `parceiro_id`, `prazo_retorno_dias`, `valor_referencia`,
  `valor_referencia_fonte/aprovado_em`, `modalidade_mensuracao`, `patrocinado`, `publicado_em`) e
  `beneficio_afinidade(beneficio_id, segmento, pontos)` · domínio: elegibilidade (abaixo) aplicada item a item ·
  API `GET /beneficios?filtro=&categoria=&q=` devolvendo `estado` (6 valores) + `libera_em` + `motivo`, e
  resumo `{ativos, disponiveis, valor_ano}` · evento `beneficio_visto` = renomear/estender `beneficio_abrir`
  com `origem` e `estado` · termo de busca sem resultado: ver DIV-M04.
- **Estado:** ⬜ (catálogo) / ⚠️ (registro do termo × RNF-16).
- **Fase:** spec F1 · roteiro fase 4 (bloqueada por P-04 só para TotalPass, P-10, P-22).

### P04 · Página do benefício e ativação (CAT-05, SOL-01)
- **Spec pede:** ficha (nome, parceiro, frase, condição × preço de referência, "como funciona" em ≤ 4 passos,
  elegibilidade com data, botão por tipo, FAQ, contato, regras, "quanto já aproveitou no ano", relacionados)
  (`spec:362-371`); nos tipos 1–5 o associado só confirma (dados do cadastro), sem cupom manual; confirmação
  mostra prazo e próximo passo (`spec:374-377`); eventos `beneficio_visto`, `solicitacao_criada`.
- **Existe hoje:** sem rota de detalhe (`INDICE-IDS.md:24`); REQUISITOS trata ativação como toggle de
  `beneficio_ativacao` (RF-BE-07/08, `docs/REQUISITOS-minha-apm.md:362-372`).
- **Falta:** SQL `beneficio_faq`, `beneficio_passo` (ou JSON na ficha) · domínio `app/dominio/ativacao.py` com
  **estratégia por tipo** (abaixo) · API `GET /beneficios/{slug}` (ficha + `estado` + `aproveitado_ano` +
  `relacionados`), `POST /beneficios/{slug}/ativar [C]` cujo corpo e resposta dependem do tipo · frontend: página.
- **Estado:** ⬜.
- **Fase:** spec F1 (tipos 1–3), F2 (4–6) · roteiro fase 4.

### Tipos de ativação 1–6 (§6 P04, `spec:387-394`) — estratégia por tipo
| Tipo | O que o botão faz (proposta) | O que grava | O que responde | Hoje | Estado |
|---|---|---|---|---|---|
| 1 Acesso direto | `POST /beneficios/{slug}/ativar` → valida elegibilidade → upsert `beneficio_ativacao(ativo)` → devolve `url_acesso` (allowlist de hosts) | `beneficio_ativacao`, `evento_uso beneficio_ativar(servidor)`; nível de evidência 2 (acesso), 3 só se o parceiro devolver uso | `200 {estado:"ativo", url_acesso, proximo_passo}` | RF-BE-07/09 planejados; TotalPass por ADR-0008 (hub `totalpass.adesao_consultar`, cache 10 min, flag `totalpass`, 404 desligada — `docs/adr/0008:27-38`) | ⬜ (P-04 só para TotalPass) |
| 2 Encaminhamento ao parceiro | cria `solicitacao` com `beneficio_id`, `parceiro_id`, `tipo_ativacao=2`, `canal_envio` do parceiro; **nenhuma chamada HTTP a parceiro** (ADR-0009 item 1, `docs/adr/0009:24-25`); em F1 o canal é `relatorio`/`email` operado pela APM (encaminhamento rastreado, `spec:110-113`) | `solicitacao` + `solicitacao_evento` + outbox CRM + outbox comunicação A04 | `201 {id, status:"criada", prazo, proximo_passo}` | fora de escopo (`INDICE-IDS.md:63`) | 🔒 ADR-0009 → ⛔ até ADR por parceiro; a solicitação local é viável sem a integração (DEC-M03) |
| 3 Serviço da APM | cria `solicitacao` de um `tipo_servico` fechado (hoje 7 tipos, `docs/adr/0003:29-30`) com `responsavel` (área) e `prazo` da ficha | idem tipo 2, `canal_envio=crm` | `201` idem | ADR-0003 e REQUISITOS §7.4 (`docs/REQUISITOS-minha-apm.md:1071-1082`); nenhuma linha de código | ⬜ (fase 3) |
| 4 Reserva | `GET /beneficios/{slug}/disponibilidade?de=&ate=` + `POST .../reservar` → `solicitacao(tipo_ativacao=4)` com `campos{periodo}`; "mostra disponibilidade" exige fonte do parceiro (Hotel Fazenda/Residencial) | `solicitacao` + `reserva` (datas) | `201` ou `409 indisponivel` | nada | ⛔ (fonte de disponibilidade inexistente) · flag nova `reservas` |
| 5 Inscrição | `POST /eventos/{id}/inscrever` com `perfil_preco` derivado da categoria; F2 com plataforma; F1 = interesse local (RF-EV-05, `docs/REQUISITOS-minha-apm.md:572`) | `evento_inscricao` (allowlist já prevê, `scripts/db_check.py:22-35`) + `evento_uso evento_inscrever` | `201 {status:"interesse"\|"inscrito", preco}` | só ação de uso catalogada (`app/uso.py:100-101`) | 🟡 (interesse) / ⛔ (inscrição real, IESAPM a mapear F0-01) · flag nova `inscricoes` |
| 6 Resgate no clube | `POST /clube/ofertas/{id}/abrir` registra o resgate iniciado e devolve `url_externa` (ADR-0009 item 2–3, seed `oferta_clube`, `docs/adr/0009:26-33`); retorno de economia só F2 | `evento_uso clube_oferta_usar` (`app/uso.py:94`) → em F2 `uso_valor(fonte=clube)` | `200 {url_externa}` | só clique (`INDICE-IDS.md:67`) | 🟡 · flag `clube_economia` já existe (`app/flags.py:31`) |

Regra comum: nos tipos 1–5 o servidor **não aceita dados pessoais no corpo** (vêm do cache do perfil, `spec:374-375`);
a resposta sempre traz `prazo` e `proximo_passo` (`spec:376-377`). Elegibilidade negada → `409 nao_elegivel` com
`estado` e `libera_em` (`spec:858`: "o sistema não deixa solicitar e mostra quando libera").

### P05 · Minhas solicitações (SOL-04, §8.5) — ver "Máquina de estados proposta"
- **Spec pede:** lista com benefício, data, status, prazo e contato; linha do tempo; cancelar enquanto o
  parceiro não atendeu; avaliar 0–10 depois de concluída; 7 rótulos visíveis (8 status internos, `spec:401-412`,
  `754-768`); log imutável com conteúdo enviado; mudança manual com justificativa.
- **Existe hoje:** só documentação (ADR-0003 `docs/adr/0003:27-60`; REQUISITOS §7 `:1024-1099`; RF-SO-01..07
  `:753-793`), 4 ações catalogadas (`app/uso.py:107-110`), allowlist de UPDATE em `solicitacao`
  (`scripts/db_check.py:22-35`), contador fixo `0` em `GET /sessao` (`app/api/v1/sessao.py:75`). Nenhuma tabela,
  rota ou job (`inv-codigo:15,46`).
- **Falta:** SQL `sql/008_solicitacao.sql` com o modelo estendido (abaixo) · domínio `app/dominio/solicitacoes/`
  (`maquina.py`, `schemas/` por tipo, `avaliacao.py`) · API 6 rotas (contratos abaixo) · jobs `espelhar`,
  `sincronizar`, `marcar_sem_retorno`, `enviar_canal` (serviço `area-associado-jobs`, não existe:
  `inv-codigo:15,40`) · frontend: lista, detalhe, formulário, avaliação.
- **Estado:** ⬜ (pode começar hoje; o espelho depende de P-06, `docs/PENDENCIAS.md:56`).
- **Fase:** spec F1 · roteiro fase 3 (próxima, `docs/PENDENCIAS.md:112`).

### P06 · Meu valor (VAL-01/03, §8.6)
- **Spec pede:** período; total pago (cobrança); economia comprovada item a item com fonte; proteção incluída
  separada; total e relação; por categoria; "como calculamos"; potencial rotulado; PDF (`spec:424-433`); regras do
  "N vezes" (`spec:436-441`); modalidades e fórmula (`spec:773-783`); eventos `meu_valor_visto`, `uso_registrado`.
- **Existe hoje:** flag `fatura_valor` **forçada desligada** por padrão (`app/config.py:99`, `app/flags.py:29`) por
  falta de fonte (P-12, `docs/PENDENCIAS.md:75`); RF-FA-01..05 preveem `GET /fatura`, `GET /fatura/pdf`
  (`docs/REQUISITOS-minha-apm.md:468-492`) na **fase 8**; ação `fatura_pdf_baixar` (`app/uso.py:117`); valor pago
  via ERP atrás de `erp_financeiro` + P-08 (ADR-0010 `docs/adr/0010:28-36`).
- **Falta:** SQL `uso_valor(contact_id, beneficio_id, solicitacao_id?, importacao_id?, data, modalidade
  ENUM(economia_uso, desconto_parceiro, servico_apm, protecao_incluida, estimado), valor_referencia, valor_pago,
  economia, fonte, nivel_evidencia 1–4, comprovado, aprovado_em)` append-only + `valor_referencia(beneficio_id,
  valor, fonte, data, aprovado_por, vigencia)` · domínio `app/dominio/valor.py` (soma só nível 4; proteção
  proporcional aos meses; relação só com total pago > 0; "< 3 meses de casa" = "o que cobre") · API
  `GET /valor?periodo=AAAA` e `GET /valor/pdf` · integrações: total pago = hub `financeiro.faturas_associado`
  (`inv-viz:140`, exige P-04 e P-08) · evento `uso_registrado(servidor|job)` novo.
- **Estado:** ⬜ (comprovado via solicitações concluídas e proteção incluída: viável sem ERP) / ⛔ ("N vezes" e
  total pago) / ⚠️ (spec F1 × roteiro fase 8 e flag forçada: DIV-M01).
- **Fase:** spec F1 v1 · roteiro fase 8.

### P07 · Carteirinha (CAR-01..03, WAL-01)
- **Spec pede:** nome, categoria, número, "desde", situação, QR; baixar imagem/PDF; wallet F2; validação pública
  sem dados pessoais; situação consultada na leitura; filiação cancelada revoga (`spec:449-458`).
- **Existe hoje:** `GET /carteirinha`, `GET /carteirinha/qr.svg`, `POST /carteirinha/compartilhar`
  (`app/api/v1/carteirinha.py:23-53`); `GET /verificar/{token}` público (`app/publico.py`), token HMAC base32,
  "situação não confirmada" quando o cache está velho (`inv-codigo:11`); wallet atrás de flag (`app/flags.py:33`).
- **Falta:** API: `GET /carteirinha/imagem.png|pdf` (baixar); `carteirinha_aberta` = `pagina_ver(rota=carteirinha)`
  já cobre (`INDICE-IDS.md:98`); "revoga ao cancelar" depende de `/verificar` consultar o hub na leitura (hoje lê
  o cache local) → DEC-M06.
- **Estado:** ✅ (núcleo) / 🟡 (download, situação ao vivo).
- **Fase:** spec F1 condicional · roteiro fase 2a (feita).

### P08 · Financeiro (INT-02, FIN-01/03/04)
- **Spec pede:** situação, valor/forma, mensalidades do ano, segunda via (PDF, linha digitável, Pix), histórico,
  declarações (inclusive AMB, carência 1 mês), recorrente em cartão F2 (`spec:466-479`).
- **Existe hoje:** só RF-FA-05 (valor pago agregado) atrás de `erp_financeiro`; ADR-0010 fixa leitura, via hub,
  `contact_id`, após P-08 (`docs/adr/0010:28-47`); hub `financeiro.faturas_associado` por **CPF** e **sem
  boleto/linha digitável/Pix** (`inv-viz:140,142`).
- **Falta:** API `GET /financeiro` (situação + mensalidades), `GET /financeiro/mensalidades/{competencia}/segunda-via`
  (⛔ fonte), `POST /financeiro/declaracoes` (= solicitação tipo 3 `declaracao_associado`, com carência 1 mês para
  AMB — viável já) · eventos `financeiro_segunda_via`, `pagamento_confirmado(job)`.
- **Estado:** ⛔ (P-04, P-08, fonte sem segunda via) / ⬜ (declarações como solicitação) / 🔒 ERP só leitura.
- **Fase:** spec F1 condicional · roteiro fase 7.

### P09 · Clube de vantagens (CLU-01..03)
- **Spec pede:** 30–40 ofertas curadas, oferta da semana, categorias, economia no ano quando houver resgate,
  "ver todas"; F1 encaminhamento rastreado sem promessa de SSO (`spec:486-497`).
- **Existe hoje:** allowlist de link `clubapm.com.br` (`inv-codigo:34`), ação `clube_oferta_usar(ui)`
  (`app/uso.py:94`), ADR-0009 com seed `oferta_clube` e flag `clube_economia` (`docs/adr/0009:26-36`).
- **Falta:** SQL `oferta_clube` (ADR-0009 item 2) + `curadoria` (B10 F2) · API `GET /clube` (`oferta_semana`,
  `grupos`, `economia_ano` só com flag) e `POST /clube/ofertas/{id}/abrir [C]` (encaminhamento rastreado: grava no
  servidor em vez de só `ui`) · evento `clube_acesso` ≈ `clube_oferta_usar`.
- **Estado:** ⬜ (F1 é trivial com seed) · 🔒 sem integração até ADR própria.
- **Fase:** spec F1 link / F2 integrado · roteiro fase 6.

### P10 · Eventos e congresso (EVE-01/02, CON-01)
- **Spec pede:** agenda filtrável (especialidade, região, formato), página do evento, inscrição com preço por perfil,
  minhas inscrições, certificados, aulas gravadas, congresso em destaque; carência 3 meses em congressos e cursos
  longos; inscrição parte da área com CPF preenchido (`spec:502-507`).
- **Existe hoje:** RF-EV-01..05 (`docs/REQUISITOS-minha-apm.md:548-576`) sobre `evento_cache` do WordPress
  (ADR-0006, P-07, P-21), interesse local; ações `evento_inscrever`, `congresso_garantir_vaga` (`app/uso.py:100-101`).
- **Falta:** SQL `evento_cache` + `evento_inscricao` (fase 5) · API `GET /eventos?especialidade=&regiao=&formato=`,
  `GET /eventos/{id}`, `POST /eventos/{id}/inscrever [C]` (tipo 5), `GET /eventos/inscricoes` · carência de 3 meses
  entra pelo motor de elegibilidade com `evento.categoria_carencia` · "CPF já preenchido" é ⚠️ com ADR-0014 (a área
  não tem CPF) → o deep link só pode levar `contact_id`/token e o site do congresso resolver via hub (EXT-M05).
- **Estado:** ⬜ / ⛔ (plataformas de eventos e IESAPM a mapear, F0-01) / ⚠️ (CPF no deep link).
- **Fase:** spec F2, F3 · roteiro fase 5.

### P11 · Notícias e ciência (NEWS-01)
- **Spec pede:** conteúdo por temas seguidos e especialidade, filtros, seguir, salvar, submeter trabalho; fontes WP,
  Portal MBE e biblioteca (`spec:512-516`).
- **Existe hoje:** RF-NE-01..07 (`docs/REQUISITOS-minha-apm.md:424-462`), ações `noticia_*`, `tema_*`
  (`app/uso.py:95-99`), allowlist `noticia_cache`, `associado_tema`, `noticia_salva` (`scripts/db_check.py:22-35`);
  nenhum job nem `portal_wp.py` (`inv-codigo:15`).
- **Falta:** SQL `sql/010` · job de sincronização (único lugar que fala com a Locaweb) · API `GET /noticias?filtro=&tema=`,
  `POST /noticias/{id}/salvar|dessalvar [C]`, `GET /temas`, `POST /temas/{slug}/seguir|deixar [C]` · `conteudo_lido`
  com tempo de leitura (ui, em `detalhes`).
- **Estado:** ⬜ / ⛔ (P-07, P-21; MBE e biblioteca sem fonte).
- **Fase:** spec F2 · roteiro fase 5.

### P12 · Trilha de ativação (HOM-01, TRI-01)
- **Spec pede:** todo novo associado e todo acadêmico; progresso começa no passo "perfil"; 5–6 passos por categoria;
  o que libera e data de carência; **passo concluído por evento real, não por clique**; some ao terminar ou no dia 90
  (`spec:521-534`); F1 = bloco de 3 passos na home.
- **Existe hoje:** RF-ON-01..11 só para Acadêmico, 6 passos fixos, `POST /onboarding/passos/{slug}/concluir [C]`
  por clique (`docs/REQUISITOS-minha-apm.md:622-656`); ação `onboarding_passo_concluir(servidor)` (`app/uso.py:111`);
  rota `onb` só Acadêmico (`inv-codigo:34`).
- **Falta:** SQL `trilha_passo(categoria, slug, ordem, titulo, libera, carencia_meses, evento_conclusao,
  valor_referencia)` seed + `trilha_progresso` append-only (allowlist já cita `onboarding_progresso` como
  append-only, `inv-req:89`) · domínio `app/dominio/trilha.py` com `avaliar(contact_id, acao, entidade_id)`
  chamado **depois** de `uso.registrar` das ações mapeadas (`perfil_contato_atualizar`, `beneficio_ativar`,
  `totalpass_abrir`, `carteirinha_compartilhar`/`pagina_ver(carteirinha)`, `evento_inscrever`, `solicitacao_criar`) ·
  API `GET /trilha` (progresso, próximo passo, `expira_em` = filiação + 90 d) · **remover** o `POST .../concluir`
  por clique (DIV-M05).
- **Estado:** ⬜ / ⚠️ (clique × evento real; só Acadêmico × todas as categorias).
- **Fase:** spec F1 bloco / F2 completa · roteiro fase 6.

### P13 · Perfil, preferências e privacidade (PER-02/03)
- **Spec pede:** cadastro (contato vai ao cadastro), tratamento, especialidades e área de atuação, região e temas,
  canais preferidos e frequência, consentimentos por finalidade com histórico, baixar dados e pedir exclusão;
  **perfil progressivo: uma pergunta por visita no bloco 3 da home** (`spec:539-553`).
- **Existe hoje:** `GET /perfil`, `PUT /perfil/contato` (10/h), `POST /perfil/email` (+ step-up e código),
  `POST|DELETE|GET /perfil/foto` (`app/api/v1/perfil.py:197-363`); cache `associado_perfil` (`sql/006`, com
  `tipo_associado`, `status_associativo`, `data_filiacao`, `crm_uf` em `sql/006:27-30`); alteração com aprovação
  vira `solicitacao alteracao_cadastro` (RF-PE-03, `docs/REQUISITOS-minha-apm.md:707-712`).
- **Falta:** SQL `associado_preferencia(contact_id PK, tratamento, especialidades JSON, area_atuacao JSON,
  regiao, temas JSON, canais JSON, frequencia, atualizado_em)` GRANT UPDATE; `consentimento(contact_id,
  finalidade, canal, valor, versao_texto, origem, ocorrido_em)` append-only; `pergunta_perfil` (catálogo,
  ordem, condição por categoria); `pedido_titular(contact_id, tipo ENUM(exportar, excluir), status)` ·
  domínio `app/dominio/preferencias.py` (próxima pergunta não respondida; respostas validadas por enum fechado) ·
  API `GET /perfil/preferencias`, `PUT /perfil/preferencias [C]`, `GET /perfil/pergunta`,
  `POST /perfil/pergunta/{chave} [C]`, `GET /perfil/consentimentos`, `POST /perfil/consentimentos [C]`
  (append; versão do texto obrigatória), `POST /perfil/dados/exportar [C]` (job gera arquivo, entrega por link
  assinado e e-mail), `POST /perfil/exclusao [C]` (= solicitação tipo `exclusao_dados`, fila B13) · eventos
  `perfil_atualizado(campo)` (hoje só contato/foto), `consentimento(servidor)` novo · especialidade e regional
  **não vêm do hub** hoje (`docs/CONTRATO-HUB.md:48-65`) → EXT-M02.
- **Estado:** ✅ (cadastro/contato/foto) / ⬜ (preferências, pergunta, consentimentos, LGPD) / ⛔ (especialidade e
  regional do CRM).
- **Fase:** spec F1 · roteiro fase 2 (feito) + sem fase para o resto (absorver na fase 3/4).

### P14 · Ajuda e atendimento (AJU-01/02)
- **Spec pede:** FAQ editável com busca; Central por WhatsApp, telefone ou formulário com horário; pedidos comuns;
  **cancelamento** acessível, motivo obrigatório em lista curta, conversa opcional, vai à Central e dispara fluxo 6
  (`spec:558-564`); evento `cancelamento_pedido` (`spec:983`).
- **Existe hoje:** só FAB WhatsApp (`wa.me`, `inv-codigo:34`) e ação `central_whatsapp_abrir(ui)` (`app/uso.py:118`).
- **Falta:** SQL `faq(id, pergunta, resposta, categoria, ordem, publicada, atualizada_em)` (B07) · domínio
  `ajuda.py` (busca normalizada sem acento; FULLTEXT opcional) · API `GET /ajuda/faq?q=`, `GET /ajuda/contato`
  (horário, canais, do `Settings`/`parametro`), `POST /ajuda/formulario [C]` (= solicitação tipo `outro`),
  `POST /ajuda/cancelamento [C]` (= **solicitação tipo novo `cancelamento_associacao`**, `campos{motivo ENUM(nao_uso,
  preco, mudanca, insatisfacao_servico, outro), quer_conversa bool, comentario ≤500}`, 1 não terminal por
  associado, nunca altera o status no CRM — quem cancela é a APM) · eventos `cancelamento_pedido(servidor)`,
  `ajuda_contato(ui, assunto, canal)` · outbox A16.
- **Estado:** ⬜ (tudo viável localmente; o fluxo 6 no RD é EXT-M03).
- **Fase:** spec F1 · roteiro sem fase → propor na fase 3 (DEC-M08).

### P15 · Notificações (NOT-02)
- **Spec pede:** ícone com contagem, tipos (solicitação atualizada, benefício liberado, evento, pagamento, novidade),
  lida/não lida, atalho para preferências (`spec:569-571`); eventos `notificacao` (`spec:981`).
- **Existe hoje:** nada; cabeçalho sem sino por decisão visual (ADR-0017, `INDICE-IDS.md:35`).
- **Falta:** SQL `notificacao(id, contact_id, tipo ENUM, titulo, corpo, link, criada_em, lida_em)` GRANT UPDATE
  (`lida_em`), índice `(contact_id, lida_em)` · domínio: produzida pelos **mesmos eventos de domínio** que alimentam a
  outbox de comunicação (A03, A04, A05, A06, A15, pagamento) · API `GET /notificacoes?cursor=`,
  `POST /notificacoes/{id}/ler [C]`, `POST /notificacoes/ler-todas [C]`; `GET /sessao` ganha
  `notificacoes_nao_lidas` · flag nova `notificacoes` · frontend: sino (precisa de aceite visual da agência).
- **Estado:** ⬜ · ⚠️ (ADR-0017 "sem sino" × spec §3.1 "notificações (F2)").
- **Fase:** spec F2 · roteiro sem fase.

### Busca global (§3.1 `spec:135-136`; §3.1 ≠ RF-SH-04)
- **Spec pede:** benefícios, parceiros, eventos, notícias e FAQ, com sugestões enquanto digita; termo sem resultado
  registrado (`spec:353-354`, `spec:960`).
- **Existe hoje:** campo que redireciona para `/beneficios?q=` e **não filtra** (`inv-codigo:34`); RF-SH-04 define
  filtragem **no cliente** sobre dados já carregados e proíbe gravar o termo (`docs/REQUISITOS-minha-apm.md:192-196`;
  RNF-16); ação `busca_global(ui, resultados, tamanho)` (`app/uso.py:85`).
- **Falta:** API `GET /busca?q=&limite=` → `{beneficios[], parceiros[], eventos[], noticias[], faq[]}` (servidor,
  consulta por tabela com LIKE normalizado/FULLTEXT, `q` 2–80 chars, limite por associado 30/min) · sugestões =
  mesma rota com `limite=5` · `busca_sem_resultado(termo_normalizado ≤ 80, quando, contact_id NULL)` só quando
  `total=0` (DIV-M04).
- **Estado:** ⬜ / ⚠️ (servidor × cliente; termo × RNF-16).
- **Fase:** spec F1 (implícita em P03) · roteiro fase 4/5.

### `rota_inicial` e `solicitacoes_aguardando` (`GET /sessao`)
- **Spec pede:** não existe rota de onboarding separada: a trilha é bloco da home (`spec:325-326`, `534`); pendência
  de solicitação aparece no bloco 1 (`spec:623`) e no contador de notificações (P15).
- **Existe hoje:** ambos fixos: `"/area"` e `0` (`app/api/v1/sessao.py:65,75`); REQUISITOS manda `/area/onboarding`
  para Acadêmico sem passo `finalizar` (`docs/REQUISITOS-minha-apm.md:96-97`, RF-ON-01 `:622-626`).
- **Falta:** `solicitacoes_aguardando` = `COUNT(*) WHERE contact_id=? AND status='pendente_associado'` (índice
  `(contact_id, status)`, ADR-0003 `docs/adr/0003:79-80`) via `run_in_threadpool` em `obter_sessao`
  (`app/api/v1/sessao.py:80-84`); `rota_inicial` fica `"/area"` sempre (a trilha é bloco, DIV-M05) — manter o
  campo no contrato para não quebrar o front.
- **Estado:** 🟡 → trivial na fase 3.

### Máquina de estados (§8.5) — ver seção própria. Estado: ⬜ / ⚠️ (6 × 8 status, `enviada`, `sem_retorno`, atores).

### Motor de elegibilidade (§8.1–8.4)
- **Spec pede:** disponível = categoria permitida ∧ filiação ≥ carência ∧ situação financeira permite ∧ região
  atendida ∧ vigente; 6 estados (`spec:704-717`); carências configuráveis no backoffice (`spec:722-733`); matriz
  benefício × categoria por configuração; mudança de categoria **não** reinicia a carência (recomendação,
  `spec:737-741`); parâmetro "dias de atraso que suspendem" (`spec:745-749`).
- **Existe hoje:** nada (`INDICE-IDS.md:80-81`). Insumos locais: `tipo_associado`, `status_associativo`,
  `data_filiacao`, `crm_uf` em `associado_perfil` (`sql/006:27-30`); `tipo`/`status` na sessão
  (`app/api/v1/sessao.py:59-60`). Sem: histórico de categorias, regional/distrital, situação financeira, data de
  nascimento (fase de carreira).
- **Falta:** SQL `parametro(chave PK, valor, atualizado_em, por)` (carência por benefício fica em `beneficio.
  carencia_meses`; `dias_atraso_suspende`, `prazo_retorno_padrao_dias`, `recomendacao_dispensa_dias` em
  `parametro`) · domínio `app/dominio/elegibilidade.py`: `avaliar(perfil, beneficio, ativacoes, financeiro) ->
  Elegibilidade(estado, libera_em, motivo, acao_sugerida)` puro (sem I/O; testável por tabela); ordem de
  avaliação: vigência → categoria → região → financeiro → carência → ativo · fonte financeira: ⛔ até P-08; até lá
  `financeiro=None` ⇒ "permite" e o estado `Suspenso` nunca ocorre (documentar) · região: `crm_uf` é UF do CRM, não
  regional/distrital (EXT-M02).
- **Estado:** ⬜ (4 de 5 condições viáveis hoje) / ⛔ (financeiro, regional).
- **Fase:** spec F0/F1 · roteiro fase 4.

### Recomendação v1 (§7.3)
- **Spec pede:** pontuação (afinidade 0–3, carência vencida 30 d +2, visto 30 d sem ativar +2, novo +1, tema/área +1,
  patrocinado +1 com ≤ 1 nos 4 primeiros), exclusões (ativo, dispensado 60 d, não disponível), desempate por valor de
  referência, ≤ 2 por categoria, rotação (3 semanas sem interação perde prioridade), "por que estou vendo"
  (`spec:639-658`); matriz editável (B08).
- **Existe hoje:** nada; RF-HO-05 é "seleção editorial por tipo" (`docs/REQUISITOS-minha-apm.md:280-283`).
  Insumos: `evento_uso` (ADR-0012) para "visto", `beneficio_ativacao` para "ativo".
- **Falta:** SQL `beneficio_afinidade(beneficio_id, segmento ENUM(ate_40, 40_55, 55_mais, acadêmico, aspirante,
  efetivo, remido, consultorio, hospital, …), pontos TINYINT)`, `recomendacao_dispensa`, `recomendacao_exposicao
  (contact_id, beneficio_id, primeira_em, ultima_em, interacoes)` GRANT UPDATE (rotação) · domínio
  `app/dominio/recomendacao.py`: `pontuar(candidatos, sinais) -> [Recomendacao(beneficio, pontos, motivos[])]`
  puro; `sinais` lidos por uma consulta agregada em `evento_uso` (`beneficio_abrir` 30 d por `entidade_id`) ·
  API: embutida em `GET /inicio` (bloco 4, 3–6 cards) e `GET /beneficios` (ordem padrão); `POST
  /recomendacoes/{slug}/dispensar [C]` · "fase de carreira" exige data de nascimento (não vem do hub; EXT-M02) ·
  patrocinado: flag `patrocinio` forçada desligada ⇒ critério vale 0 até P-12.
- **Estado:** ⬜ (viável com a matriz por categoria; fase de carreira ⛔).
- **Fase:** spec F1 · roteiro fase 4.

### Blocos da home (§7.2) e ADM-05
- Coberto em P02; acrescento as **fontes por bloco**: 1 Pendência — pagamento (⛔ ERP), documentação pendente (⛔ CRM:
  não há campo no contrato do hub), `solicitacao.status=pendente_associado` (✓ local), carência liberada ≤ 7 d
  (✓ calculado), renovação ≤ 30 d (⛔ cobrança) · 2 Meu valor — `valor.py` (🟡) · 3 Próximo passo — `trilha.py`
  nos 90 d, senão `preferencias.proxima_pergunta` (✓ local) · 4 Recomendados — `recomendacao.py` · 5 Categorias —
  `beneficio_categoria` seed · 6 Defesa — `destaque_editorial(tipo=defesa)` (B07, editorial) · 7 Agenda —
  `evento_cache` 60 d (fase 5) · 8 Notícias — F2 · 9 Clube — F2 · ADM-05 — `destaque_editorial` posição 2,
  `UNIQUE` por (segmento, vigência) garante "um por vez".
- **Estado:** ⬜ · a API devolve só blocos com conteúdo (`spec:159`), ordem fixa pelo servidor.

### §8.6 cálculo do valor e "N vezes"
- Coberto em P06. Regras que viram testes de tabela em `valor.py`: só `nivel_evidencia=4` soma ao comprovado;
  proteção = `valor_referencia_anual × meses_ativos/12`, bloco separado; estimado nunca soma; relação =
  `(comprovado + protecao) ÷ total_pago` só se `total_pago > 0` e numerador > `total_pago`; `total_pago = 0` ⇒
  "valor entregue" + composição do patrocínio; `< 3 meses` ⇒ "o que cobre". Valor de referência precisa de
  `fonte`, `data`, `aprovado_por` (Financeiro) e revisão anual (`spec:781-783`) — coluna `revisar_em`.
- **Estado:** ⬜ / ⛔ (`total_pago`).

### OpenAPI (§14 `spec:1209-1210`)
- **Spec pede:** API documentada (OpenAPI).
- **Existe hoje:** `docs_url`/`openapi_url` só com `APP_ENV=development` (`app/config.py:157-158`,
  `app/main.py:140-142`); 403 na borda (`area_associado.conf.example:61-63`); rotas de saúde fora do schema
  (`app/main.py:369-391`).
- **Falta:** exportação em **tempo de build** (`scripts/openapi_export.py` rodando `app.openapi()` com `APP_ENV=test`
  no estágio Python do Dockerfile) para `docs/api/openapi.json` versionado; `operation_id` estável por rota;
  schemas de erro (`ApiError`) e de cada recurso como modelos Pydantic de resposta (hoje `dict[str, Any]`,
  `app/api/v1/sessao.py:81`); teste que falha se o arquivo divergir do código. **Nunca servir `/openapi.json` em
  produção** (superfície de enumeração; mantém o 403).
- **Estado:** 🟡.

### Flags novas (ADR-0007: enum fechado `app/flags.py:27-36`, nascem desligadas, 404 `recurso_desligado`)
| Chave nova | Governa | Pré-requisito | ADR |
|---|---|---|---|
| `notificacoes` | P15 (rotas `/notificacoes`, contador em `/sessao`, sino) | aceite visual (ADR-0017) | adenda à 0007 |
| `encaminhamento_parceiro` | tipo 2 (`POST .../ativar` em benefício `tipo_ativacao=2`) | ADR por parceiro (0009) | nova por parceiro |
| `reservas` | tipo 4 | fonte de disponibilidade | nova |
| `inscricoes` | tipo 5 real (F1 segue "interesse") | F0-01 | nova |
| `comunicacao_outbox` | job que envia a outbox ao RD (A01–A20) | credencial RD, consentimento | nova (RD Station) |
| `cancelamento_online` | `POST /ajuda/cancelamento` | processo da Central | — (pode nascer ligada por decisão de negócio; DEC) |
| `recomendacao_v2` | REC-01 A/B | 6 meses de dados | F2 |
Mantidas: `fatura_valor` (renomear rótulo para "Meu valor", chave fica — DIV-M01), `erp_financeiro`, `totalpass`,
`clube_economia`, `patrocinio`, `mensalidade_zero`, `wallet`, `comunidade_posts`. **Não** criar flag para
catálogo, solicitações, trilha, FAQ, preferências: são núcleo F1 (spec §14 só exige flag para patrocínio, cartão,
comunidade e novos tipos de ativação, `spec:1207-1208`).
- **Estado:** ⬜ · 🔒 (modelo de flags).

### §12 · o que a área emite para a outbox de comunicação (gatilhos F1: A01–A06, A09, A16, A17, A18)
| Gatilho | A área emite? | Evento de domínio / fonte | Observação |
|---|---|---|---|
| A01 filiação confirmada | não | cadastro (CRM) | a área só conhece quem já logou (`associado.primeiro_acesso_em`, `sql/005`) |
| A02 1º acesso não feito | não (hoje) | exige lista de filiações recentes do hub (`filiacao.propostas`, `inv-viz:140`) | EXT-M04 |
| A03 carência vencida | **sim** | job diário `carencias_vencidas`: para cada associado com perfil em cache, benefícios cujo `data_filiacao + carencia` caiu em D-1 → `evento_uso carencia_vencida(job)` + outbox + notificação | só para quem tem `associado_perfil` (quem já entrou) |
| A04 solicitação criada | **sim** | transição `—→criada` | transacional: e-mail pelo SMTP próprio (P-27) + notificação; também vai ao RD como evento |
| A05 sem retorno | **sim** | job `marcar_sem_retorno` | alerta interno (B01) + aviso ao associado |
| A06 concluída | **sim** | transição `→concluida_*` | pergunta 0–10 (link para `POST /solicitacoes/{id}/avaliar`) |
| A09 mensalidade vencida | não | cobrança | ⛔ P-08; quando existir, a área só **consome** (`pagamento_confirmado`, suspensão de ofertas) |
| A16 cancelamento | **sim** | `cancelamento_associacao` criada | fluxo 6 |
| A17 lead não associado | não | parceiros/formulário | fora da área |
| A18 aniversário | não | já no RD | — |
- **Modelo:** `comunicacao_outbox(id, gatilho ENUM('A01'..'A20'), contact_id, canal_sugerido, payload JSON (sem CPF,
  sem e-mail: o RD resolve pelo identificador), criada_em, status ENUM(pendente, enviada, suprimida, erro),
  tentativas, enviada_em, erro)` GRANT UPDATE; produzida **na mesma transação** da transição de negócio; consumida
  por job (`enviar_comunicacao`) atrás de `comunicacao_outbox`; supressão (§12.3: 2/semana, pendência financeira,
  14 d após solicitar, cancelamento) aplicada no job; log visível em B09.
- **Estado:** ⬜ (produção local viável já na fase 3) / ⛔ (envio: credencial RD, EXT-M03).

### Limites por associado (hoje em memória por processo)
- **Spec pede:** limite de tentativas (`spec:1194-1195`, ACE-05 é do IdP).
- **Existe hoje:** `LimiteJanela` em memória, por processo, 2 workers ⇒ teto efetivo 2× (`app/limites.py:1-6`);
  usados em `/uso` 60/min (`app/api/v1/uso.py:25,50`), contato 10/h e foto 5/h (`perfil.py:44-45`); nginx por IP
  (`area_associado.conf.example:14-22,85-101`).
- **Falta:** para escritas de negócio com teto **diário** (solicitação `outro` 5/dia, `cancelamento` 1 aberta,
  avaliação 1 por solicitação, dispensa 20/dia, exportação LGPD 1/7 d) usar **contagem no banco** na própria
  transação (índice `(contact_id, criada_em)`), exata e compartilhada entre workers; manter `LimiteJanela` para
  abuso por minuto (uso, busca, pergunta de perfil). Sem Redis na stack: não introduzir (DEC-M07).
- **Estado:** 🟡.

### Backoffice B01–B13 como API interna (sem decidir onde vive)
O que **a área precisa expor ou guardar** para cada módulo, independentemente do processo que o sirva:
| Módulo | Dados na área | API interna necessária (namespace `/api/interno/v1`, autenticação própria, nunca a sessão do associado) | Estado |
|---|---|---|---|
| B01 painel do dia | `solicitacao` (sem_retorno), `importacao`, `pedido_titular`, `comunicacao_outbox(erro)`, `job_execucao` | `GET /painel/dia` (agregados) | ⬜ |
| B02 visão 360 | `associado*`, `solicitacao`, `beneficio_ativacao`, `uso_valor`, `consentimento`, `comunicacao_outbox`; cadastro via hub `associado.visao_360` (CPF, sensível, `inv-viz:140`) | `GET /associados/{contact_id}` (junta local + hub) · busca por CPF só no hub | ⬜ / ⛔ (grant do hub) |
| B03 benefícios | `beneficio`, `beneficio_faq`, `beneficio_afinidade`, `valor_referencia`, histórico (`beneficio_versao` append) | CRUD com rascunho/aprovação/publicação agendada | ⬜ · exige UPDATE em tabelas de catálogo (DEC-M09) |
| B04 parceiros e contratos | `parceiro(id, nome, canal ENUM(api, portal, relatorio, email), prazo_retorno_dias, vigencia, contatos)` — cadastro mínimo; `apm-parceiros` é outro sistema (`inv-viz:125`) | CRUD | ⬜ (DEC-M10) |
| B05 solicitações e leads | `solicitacao*` | `GET /solicitacoes?status=&parceiro=&sem_retorno=`, `POST /solicitacoes/{id}/status` (**justificativa obrigatória**, `ator=apm`, `origem=backoffice`, usuário no evento), `POST .../reenviar`, `GET .../exportar.csv`; leads: fora (B05 "tela de leads" vem de parceiros/formulário) | ⬜ |
| B06 importações | `importacao(id, parceiro_id, periodo, arquivo_hash, linhas_total/validas/erro, status, usuario)` + `importacao_linha` (append) → gera `uso_valor` e fecha solicitações (`id_externo`) | `POST /importacoes` (CSV §13.3; **CPF na linha → resolvido para `contact_id` pelo hub**, ADR-0014), `GET .../previa`, `POST .../confirmar`, `GET .../devolucao.csv` | ⬜ / ⛔ (hub: lote CPF→contact_id, EXT-M06) |
| B07 home e conteúdo | `destaque_editorial`, `faq`, `trilha_passo`, `texto_sistema` | CRUD | ⬜ |
| B08 segmentos | `segmento(regras JSON)`, `beneficio_afinidade` | CRUD + `GET /previa?contact_id=` ("ver como associado" = chamar `inicio.montar` com o perfil alvo) | ⬜ |
| B09 comunicação | `comunicacao_outbox`, `notificacao`, supressões | `GET /comunicacao?gatilho=&status=` | ⬜ |
| B10 clube, B11 eventos | F2 | — | ⬜ |
| B12 painéis | `evento_uso`, `uso_valor`, `solicitacao` (indicadores 1–7, 12–14 de `spec:1009-1024`) | consultas agregadas; exportação | ⬜ (fonte já existe) |
| B13 configurações e LGPD | `parametro`, `carência` (em `beneficio`), `valor_referencia`, `consentimento_versao`, `pedido_titular`, `feature_flag`, `auditoria_backoffice` (append) | CRUD de parâmetros com justificativa; fila LGPD | ⬜ · `feature_flag` só muda por operador hoje (`docs/adr/0007:27-29`) |
| Perfis + 2FA (§9.1) | `usuario_interno`? | identidade **não** pode ser o IdP de associados (CPF) — DEC-M11 | ⛔ decisão |
- 🔒 "Backoffice próprio" está fora de escopo (`docs/REQUISITOS-minha-apm.md:112`); aqui só o que a área **tem
  de oferecer** para que algum backoffice exista.

---

## Máquina de estados proposta

### Estados
| Spec (`spec:756-765`) | Rótulo ao associado | Atual (ADR-0003 `docs/adr/0003:31-32`; REQ §7.1) | Proposta | Terminal |
|---|---|---|---|---|
| `criada` | Recebida pela APM | `aberta` | `criada` | não |
| `enviada` | Enviada ao parceiro | — (`crm_sync=ok`, técnico e invisível, RF-SO-06) | `enviada` (**status de negócio**, promovido pelo job quando o canal confirma: `canal=crm` ⇒ espelho ok; `relatorio`/`email` ⇒ operador marca no B05; `api`/`portal` F2 ⇒ ack do parceiro). A **falha** continua invisível (RF-SO-06 preservada) | não |
| `em_atendimento` | Em atendimento | `em_analise` | `em_atendimento` | não |
| `pendente_associado` | O parceiro precisa de algo seu | `aguardando_associado` | `pendente_associado` | não |
| `concluida_positiva` | Concluída | `concluida` | `concluida_positiva` | sim |
| `concluida_negativa` | Não seguiu | `recusada` | `concluida_negativa` | sim |
| `cancelada` | Cancelada | `cancelada` (só associado) | `cancelada` (associado **ou APM com justificativa**) | sim |
| `sem_retorno` (marcador) | Aguardando o parceiro (a APM já está cobrando) | — | **não é status**: coluna `sem_retorno_desde DATETIME NULL` + flag `aguardando_parceiro` na API; posta pelo job, limpa em qualquer transição. Evita o estado "de ida e volta" que a spec chama de marcador | — |

Nomes internos passam a ser os da spec (não há dado legado: a tabela ainda não existe). `crm_sync` continua
camada técnica (`pendente, ok, erro, falhou`).

### Colunas novas em `solicitacao` (além de ADR-0003 item 1)
`beneficio_id CHAR(36) NULL`, `parceiro_id NULL`, `tipo_ativacao TINYINT NULL (2|3|4|5)`, `tipo_servico ENUM`
(os 7 de ADR-0003 + `declaracao_associado`, `cancelamento_associacao`, `exclusao_dados`) NULL quando há
`beneficio_id`, `canal_envio ENUM('crm','relatorio','email','api','portal')`, `prazo_retorno_dias`,
`enviada_em`, `sem_retorno_desde`, `responsavel VARCHAR(80)`, `resultado JSON` (valor, para `uso_valor`),
`avaliacao_nota TINYINT NULL CHECK 0..10`, `avaliacao_comentario VARCHAR(500)`, `avaliada_em`, `cancel_motivo`,
`chave_idempotencia`. `solicitacao_evento` ganha `ator ENUM('associado','sistema','parceiro','apm','importacao')`,
`origem ENUM('ui','job','crm','backoffice','importacao','api_parceiro','portal_parceiro')`, `justificativa`
(obrigatória quando `origem='backoffice'`), `usuario_interno`, `conteudo_enviado JSON` (`spec:767-768`), `request_id`.

### Transições
| De | Para | Ator | Origem | Gatilho | Efeitos (mesma transação: UPDATE condicional + INSERT evento) · depois: evento_uso · outbox · espelho CRM |
|---|---|---|---|---|---|
| — | `criada` | associado | ui | `POST /solicitacoes` ou `POST /beneficios/{slug}/ativar` (tipos 2–4) | INSERT + evento `criada`; `uso solicitacao_criar(tipo_ativacao, beneficio)`; outbox **A04** + `notificacao`; `crm_sync=pendente`; se `canal=relatorio|email`, item na fila B05 |
| `criada` | `enviada` | sistema | job | canal confirmou (crm ok / ack API) | evento; `enviada_em=NOW()`; `uso solicitacao_status_alterado(job)`; espelho já feito |
| `criada` | `enviada` | apm | backoffice | operador marcou "enviado ao parceiro" (canal manual) | evento com usuário + justificativa opcional; `enviada_em` |
| `criada` \| `enviada` | `em_atendimento` | parceiro / apm | crm / backoffice / api_parceiro / portal_parceiro | CRM "Em andamento"; parceiro confirmou | evento; limpa `sem_retorno_desde`; uso; espelho se origem ≠ crm |
| `em_atendimento` | `pendente_associado` | parceiro / apm | crm / backoffice / api / portal | pedido ao associado (mensagem pública obrigatória) | evento com mensagem; contador em `/sessao`; outbox + `notificacao` (tipo solicitação) |
| `pendente_associado` | `em_atendimento` | associado | ui | `POST .../responder` | evento com texto; `crm_sync=pendente`; uso `solicitacao_responder` |
| `enviada` \| `em_atendimento` | `concluida_positiva` \| `concluida_negativa` | parceiro / importacao / apm | crm / importacao / backoffice / api | resultado registrado | evento; `concluida_em`; se `resultado` tem valor e evidência ⇒ INSERT `uso_valor` (nível 3; nível 4 só com aprovação); `alteracao_cadastro` ⇒ invalida `associado_perfil`; uso; outbox **A06**; `notificacao` |
| `criada` \| `enviada` \| `pendente_associado` | `cancelada` | associado | ui | `POST .../cancelar` ("enquanto o parceiro não atendeu" = nunca a partir de `em_atendimento`, `spec:404`) | evento; `crm_sync=pendente` (status_atualizar); uso `solicitacao_cancelar`; limpa fila/outbox pendente da solicitação (suprime A05) |
| qualquer não terminal | `cancelada` | apm | backoffice | operador, justificativa obrigatória | evento com usuário; espelho |
| terminal | — | — | — | — | `409 estado_invalido` (ADR-0003 item 3). CRM concluindo algo cancelado localmente: terminal local prevalece, divergência em `evento_log` (REQ §7.5) |
| (marcador) | `sem_retorno_desde` | sistema | job | `enviada_em + prazo_retorno_dias < NOW()` e status ∈ {enviada, em_atendimento} e marcador vazio | evento `sem_retorno` (sem troca de status); outbox **A05** (interno + associado); `notificacao`; B01. Segundo vencimento (`prazo × 2`): evento `sem_retorno_2` → fila de ligações (`spec:855`) |
| terminal `concluida_*` | (avaliação) | associado | ui | `POST .../avaliar` 1× até N dias (`parametro avaliacao_prazo_dias`, padrão 30) | UPDATE `avaliacao_*` com `WHERE avaliada_em IS NULL`; evento `avaliada`; uso `solicitacao_avaliar` (ação nova); espelho opcional |

Mapeamento `task` do CRM (REQ §7.5 `:1091`) continua válido com os nomes novos: Não iniciado → `criada`/`enviada`
(a área não regride: se já está `enviada`, ignora); Em andamento → `em_atendimento`; Aguardando outra pessoa →
`pendente_associado`; `statecode=1` → `concluida_positiva`; `statecode=2` pelo atendente → `concluida_negativa`.
**`concluida_negativa` por `statecode=2` precisa de confirmação em P-06** (a spec distingue "não seguiu" de
"cancelada pela APM"; a `task` não distingue).

Vínculo com benefício/parceiro: `beneficio_id` + `parceiro_id` + `tipo_ativacao` desnormalizados na solicitação
(a ficha pode mudar; a solicitação guarda `conteudo_enviado` da época). `prazo_retorno_dias` copiado do parceiro
(ou do benefício, ou `parametro.prazo_retorno_padrao_dias`) na criação, para o job não depender de ficha viva.

---

## Contratos de API (esboço)

Convenções: tudo sob `/api/v1`, sessão obrigatória (`require_associado`), `[C]` = `exigir_csrf`, `[F:x]` = flag,
`[L:n/janela]` = limite por associado, nunca `contact_id`/`sub`/CPF/`crm_*` no payload (RF-SO-06, ADR-0014);
erros do contrato de `docs/REQUISITOS-minha-apm.md:166-168` + novos `409 nao_elegivel`, `409 ja_avaliada`,
`409 periodo_indisponivel`. Respostas tipadas (Pydantic) para alimentar o OpenAPI.

| Recurso | Método · caminho | Dependências | Payload (resumo) | Erros específicos |
|---|---|---|---|---|
| Sessão | `GET /sessao` | sessão | + `solicitacoes_aguardando` (real), `notificacoes_nao_lidas` [F:notificacoes], `trilha_ativa bool` | — |
| Início | `GET /inicio` | sessão | `{blocos: [{id, posicao, conteudo}]}` só os com conteúdo; bloco 4 cards com `motivos[]` e `patrocinado` | `503 fonte_indisponivel` por bloco ⇒ bloco omitido + `avisos[]` (nunca derruba a home) |
| Recomendações | `POST /recomendacoes/{slug}/dispensar` | [C] [L:20/dia] | `{motivo?}` | `404` slug |
| Benefícios | `GET /beneficios?filtro=todos\|disponiveis\|ativos\|novos&categoria=&q=` | sessão | `{resumo{ativos, disponiveis, valor_ano}, categorias[], itens[{slug, titulo, condicao, selo, estado, libera_em, categoria, tipo_ativacao, cta}]}` | — |
| Ficha | `GET /beneficios/{slug}` | sessão | ficha + `elegibilidade{estado, libera_em, motivo, desde}` + `aproveitado_ano` + `faq[]` + `relacionados[]`; emite `beneficio_visto(origem)` via `?origem=` validado por enum | `404` |
| Ativar | `POST /beneficios/{slug}/ativar` | [C] [L:10/h] [F por tipo 2/4/5/6] | tipo 1 `{}` → `200 {estado, url_acesso, proximo_passo}`; tipo 2/3 `{campos?}` → `201 {solicitacao_id, status, prazo, proximo_passo}` (ou `200` idempotente); tipo 4 `{periodo}`; tipo 5 → redireciona a `/eventos`; tipo 6 → `200 {url_externa}` | `409 nao_elegivel {estado, libera_em}`, `409 estado_invalido` (já ativa) |
| Desativar | `POST /beneficios/{slug}/desativar` | [C] | só tipo 1 | `409` |
| Solicitações | `GET /solicitacoes?situacao=andamento\|encerradas&cursor=&limite≤20` | sessão | `itens[{id, tipo, beneficio{slug,titulo}?, parceiro?, status, rotulo, aguardando_parceiro, prazo_em, contato, criada_em, atualizada_em, pode_cancelar, pode_avaliar}]`, `proximo_cursor` | — |
| Detalhe | `GET /solicitacoes/{id}` | sessão | + `campos` (sem internos), `linha_do_tempo[{quando, de, para, ator: "Você"\|"Equipe APM"\|"Parceiro", mensagem}]`, `avaliacao?` | `404` (outro dono) |
| Criar | `POST /solicitacoes` | [C] [L:5/dia para `outro` por contagem no banco] | `{tipo_servico, campos, chave_idempotencia}` (só tipos sem benefício: `alteracao_cadastro`, `outro`, `declaracao_associado`, `cancelamento_associacao`, `exclusao_dados`) → `201`/`200` | `400 entrada_invalida` (schema por tipo), `409 estado_invalido` (unicidade) |
| Cancelar | `POST /solicitacoes/{id}/cancelar` | [C] | `{motivo?}` | `409 estado_invalido` |
| Responder | `POST /solicitacoes/{id}/responder` | [C] | `{texto 1–2000}` | `409` |
| Avaliar | `POST /solicitacoes/{id}/avaliar` | [C] | `{nota 0–10, comentario ≤500}` | `409 ja_avaliada`, `409 estado_invalido`, `409 prazo_expirado` |
| Meu valor | `GET /valor?periodo=AAAA` | [F:fatura_valor] | `{periodo, total_pago?, comprovado{total, itens[{data, beneficio, economia, fonte, modalidade}]}, protecao{total, itens[]}, relacao?, por_categoria[], potencial[], metodologia, modo: "relacao"\|"valor_entregue"\|"o_que_cobre"}` | `404 recurso_desligado` |
| PDF | `GET /valor/pdf?periodo=` | [F] [L:5/h] | `application/pdf`, `no-store` | — |
| Carteirinha | `GET /carteirinha/imagem.png`, `GET /carteirinha/pdf` | sessão [L:10/h] | binário `no-store` | — |
| Financeiro | `GET /financeiro`, `GET /financeiro/mensalidades/{competencia}/segunda-via` | [F:erp_financeiro] | ADR-0010 | `404 recurso_desligado`, `503` |
| Clube | `GET /clube`, `POST /clube/ofertas/{id}/abrir` | sessão; [C] | `{url_externa}` (host na allowlist) | `404` |
| Eventos | `GET /eventos?…`, `GET /eventos/{id}`, `POST /eventos/{id}/inscrever` [C] [F:inscricoes para real], `GET /eventos/inscricoes` | | `{status: interesse\|inscrito, preco_perfil}` | `409 nao_elegivel` (carência 3 m) |
| Notícias | `GET /noticias`, `POST /noticias/{id}/salvar\|dessalvar` [C], `GET /temas`, `POST /temas/{slug}/seguir\|deixar` [C] | | | `400` tema inexistente; limite 20 temas |
| Trilha | `GET /trilha` | sessão | `{ativa, expira_em, passos[{slug, titulo, libera, libera_em, concluido_em, valor_referencia}], proximo}` | — (sem `concluir`) |
| Preferências | `GET\|PUT /perfil/preferencias` [C] · `GET /perfil/pergunta` · `POST /perfil/pergunta/{chave}` [C] [L:10/dia] | | enums fechados; `pergunta: null` quando não há | `400`, `404` chave |
| Consentimentos | `GET /perfil/consentimentos` · `POST /perfil/consentimentos` [C] | | `{finalidade, canal, valor, versao_texto}` append; resposta = histórico | `409 versao_desatualizada` |
| LGPD | `POST /perfil/dados/exportar` [C] [L:1/7 d] · `POST /perfil/exclusao` [C] | step-up (`idp_at`, regra 22) nos dois | `202` (job) · `201` solicitação | `403 reauth_necessaria` |
| Ajuda | `GET /ajuda/faq?q=` · `GET /ajuda/contato` · `POST /ajuda/formulario` [C] · `POST /ajuda/cancelamento` [C] [F:cancelamento_online] | | `{motivo ENUM, quer_conversa, comentario}` → `201 {solicitacao_id, prazo}` | `409 estado_invalido` (já há pedido aberto) |
| Notificações | `GET /notificacoes?cursor=` · `POST /notificacoes/{id}/ler` · `POST /notificacoes/ler-todas` [C] | [F:notificacoes] | `{itens[{id, tipo, titulo, corpo, link, criada_em, lida}]}` | `404 recurso_desligado` |
| Busca | `GET /busca?q=&limite=` | sessão [L:30/min] | `{beneficios[], parceiros[], eventos[], noticias[], faq[], total}`; `q` 2–80 | `400` |
| Uso | `POST /uso` | existente | + ações `home_bloco_clicado`, `beneficio_visto(origem, estado)`, `conteudo_lido(tempo)`, `ajuda_contato(assunto, canal)`, `notificacao(tipo, acao)` | — |

Estados vazios (§15.4 `spec:1249-1252`): toda lista devolve `itens: []` + `vazio: {titulo, texto, acao?}` definido
pelo servidor (texto editável, B07), para a SPA não inventar frase; erro de fonte por bloco nunca derruba a página.

---

## Propostas

### TI (`TI-M01`…)
| ID | Tarefa | Camada | Repo | Tam. | Pré-requisito | Hoje? |
|---|---|---|---|---|---|---|
| TI-M01 | `sql/008_solicitacao.sql` com os 8 status da spec, colunas de vínculo/canal/prazo/avaliação, `solicitacao_evento` com atores/origens/justificativa, índices `(contact_id,status)`, `(crm_sync,crm_proxima_em)`, `(status, enviada_em)`; GRANT UPDATE justificado | SQL | área | M | ADR-0003 adenda (DEC-M01) | sim |
| TI-M02 | `app/dominio/solicitacoes/maquina.py` (tabela de transições pura + `transitar()` com UPDATE condicional), `schemas/` por tipo (incl. `cancelamento_associacao`, `declaracao_associado`, `exclusao_dados`), `avaliacao.py` | domínio | área | M | TI-M01 | sim |
| TI-M03 | API `/solicitacoes` (6 rotas), `solicitacoes_aguardando` real em `/sessao`, ações de uso `solicitacao_avaliar`, `cancelamento_pedido` | API | área | M | TI-M02 | sim |
| TI-M04 | Serviço `area-associado-jobs` (`python -m app.jobs`, `job_execucao`) com `espelhar`, `sincronizar`, `marcar_sem_retorno`, `carencias_vencidas`, `enviar_comunicacao` (desligado por flag) | jobs+infra | área | G | TI-M01; P-06 só para o espelho real | sim (stub do hub) |
| TI-M05 | `comunicacao_outbox` + `notificacao` (tabelas e produção na transação de negócio); consumo RD atrás de `comunicacao_outbox`; P15 atrás de `notificacoes` | SQL/domínio | área | M | TI-M01 | sim (produção); envio ⛔ |
| TI-M06 | `POST /ajuda/cancelamento`, `GET /ajuda/faq`, `GET /ajuda/contato`, tabela `faq` | SQL/API | área | P | TI-M02 | sim |
| TI-M07 | `app/dominio/elegibilidade.py` puro + `parametro` + colunas de elegibilidade em `beneficio` (`sql/009`) | SQL/domínio | área | M | catálogo curado (EXT-M01) para o seed; o motor não depende | sim (motor) |
| TI-M08 | `app/dominio/ativacao.py` (estratégia por tipo), `GET /beneficios`, `GET /beneficios/{slug}`, `POST .../ativar|desativar` | domínio/API | área | G | TI-M07, sql/009 | parcial (tipos 1 e 3) |
| TI-M09 | `recomendacao.py` + `beneficio_afinidade` + `recomendacao_dispensa/exposicao` + `POST /recomendacoes/{slug}/dispensar` | SQL/domínio/API | área | M | TI-M07 | sim (matriz por categoria; fase de carreira depois) |
| TI-M10 | `inicio.py` + `GET /inicio` por blocos + `destaque_editorial` (ADM-05) + ações `home_vista(blocos)`, `home_bloco_clicado` | domínio/API | área | M | TI-M07..09 | sim (com blocos disponíveis) |
| TI-M11 | `valor.py` + `uso_valor` + `valor_referencia` + `GET /valor` (modo "valor_entregue"/"o_que_cobre" sem ERP) + PDF | SQL/domínio/API | área | M | TI-M08 (ativações), TI-M03 (concluídas) | sim, atrás de `fatura_valor` |
| TI-M12 | `trilha.py` por evento real + `trilha_passo` por categoria + `GET /trilha`; retirar `POST /onboarding/passos/*/concluir` do plano; `rota_inicial` fixa | SQL/domínio/API | área | M | TI-M08 | sim |
| TI-M13 | `associado_preferencia`, `pergunta_perfil`, `consentimento`, `pedido_titular` + rotas de P13 (pergunta por visita, consentimentos, exportar/excluir com step-up) | SQL/domínio/API | área | M | — | sim |
| TI-M14 | `GET /busca` no servidor + `busca_sem_resultado` | API | área | P | tabelas de catálogo/FAQ | após TI-M06/M08 |
| TI-M15 | Limites diários por contagem no banco (helper em `app/dominio/limites_negocio.py`) | domínio | área | P | TI-M01 | sim |
| TI-M16 | OpenAPI exportado no build (`scripts/openapi_export.py`, `docs/api/openapi.json`, teste de diff, `operation_id`, modelos de resposta) | API/infra | área | P | — | sim |
| TI-M17 | Flags novas no enum + migração + `docs/PROVISIONAMENTO.md` | config/SQL | área | P | adenda ADR-0007 | sim |
| TI-M18 | API interna `/api/interno/v1` (B05 status com justificativa, B06 importação CSV, B13 parâmetros) — só o contrato e a autenticação por token de serviço separado; UI fora | API | área (ou repo novo) | G | DEC-M09, DEC-M11 | não (decisão) |
| TI-M19 | Hub: `solicitacao.espelhar`, `solicitacao.status_atualizar`, `solicitacao.alteracoes_consultar` (ADR-0003 item 5) | integração | mcp_hub | M | P-06 | não |
| TI-M20 | Hub: `associado.contatos_por_cpf_lote` (importação B06: CPF → `contact_id`, PII, só conta interna) | integração | mcp_hub | P | grant próprio | não |

### EXT (`EXT-M01`…)
| ID | O que | De quem | Destrava | Enquanto isso | P-xx |
|---|---|---|---|---|---|
| EXT-M01 | Catálogo curado (30–40 benefícios) com categoria, tipo de ativação, carência, categorias permitidas, região, vigência, valor de referência aprovado, parceiro e canal/prazo de retorno (`spec:260`, `spec:1256-1259`) | Benefícios + Financeiro + Jurídico (carência do Clube) | TI-M07/08 seed, P03/P04 reais | motor + seed de teste (`HUB_MODE=stub` não cobre; usar fixture de catálogo) | P-10 (ampliar) |
| EXT-M02 | Campos do cadastro que o hub não entrega: data de nascimento (fase de carreira), especialidades, regional/distrital, histórico de categorias, documentação pendente (acadêmico) (`spec:1147-1150`) | CRM admin + mcp_hub (`associado.perfil_consultar` estendido) | recomendação por fase de carreira, bloco Pendência "documentação", região no motor | especialidade/região **declaradas** em `associado_preferencia`; afinidade só por categoria | novo |
| EXT-M03 | Credencial RD Station (OAuth2 client + refresh, molde do `totalpass`, `inv-viz:151`) e definição dos campos/eventos da régua por gatilho | Marketing + RD | envio da `comunicacao_outbox` | outbox só acumula (log B09); transacionais por SMTP (P-27) | novo (ADR RD Station) |
| EXT-M04 | Fonte para A02 (lista de filiações confirmadas sem primeiro acesso): hub `filiacao.*` por período ou aviso do cadastro | mcp_hub / CRM | A02 | nada (o IdP e o CRM já têm o dado; régua manual) | novo |
| EXT-M05 | Deep link de inscrição em congresso "com CPF preenchido" (`spec:506`) sem a área ter CPF: o site do congresso aceita `contact_id` assinado ou token resolvido no hub | sites de congresso / IESAPM / hub | tipo 5 real | interesse local | F0-01, novo |
| EXT-M06 | Hub: resolução CPF→`contact_id` em lote para a importação (CSV §13.3 traz CPF) | mcp_hub | B06 | importação indisponível | novo |
| EXT-M07 | Entidade e mapeamento no CRM para as solicitações, incluindo como distinguir "não seguiu" de "cancelada pela APM" e campo de mensagem pública | CRM admin / atendimento | espelho real (TI-M04/19) | fila local + `HUB_MODE=stub` | P-06 |
| EXT-M08 | ERP: parecer de licença e `financeiro.*` por `contact_id`, situação (dias de atraso), mensalidades, segunda via | TI/jurídico + mcp_hub | P08, bloco Pendência financeira, "N vezes", estado `Suspenso` | `financeiro=None` ⇒ permite; "valor entregue" sem relação | P-04, P-08 |
| EXT-M09 | Credencial SMTP própria (transacionais A04/A06 e código de e-mail) | TI/infra | e-mails transacionais em produção | `SMTP_MODE=stub` (proibido em produção) | P-27 |
| EXT-M10 | Parâmetros de negócio: dias de atraso que suspendem, prazo de retorno padrão, prazo de avaliação, regra de mudança de categoria (reinicia carência?), lista de motivos de cancelamento | Presidência/Financeiro/Benefícios (`spec:745`, `737-741`, `1256`) | TI-M07 valores reais | `parametro` com padrões documentados (recomendação da spec: não reinicia) | novo |
| EXT-M11 | Aceite visual da agência para sino de notificações, página de benefício, lista de solicitações, Meu valor (mockups P-39) | agência | frontend de P04/P05/P06/P15 | API pode andar antes | P-39 |

### DIV (`DIV-M01`…) — divergências entre a spec e o que já decidimos
| ID | Divergência | Onde | Proposta |
|---|---|---|---|
| DIV-M01 | P06 "Meu valor" é F1 na spec; no roteiro é fase 8 atrás de `fatura_valor` forçada desligada por falta de fonte (P-12) | `spec:443`, `app/config.py:99`, `docs/PENDENCIAS.md:75` | A spec resolve a fonte: comprovado = solicitações concluídas + importações; proteção = valor de referência. Tirar `fatura_valor` de `FLAGS_FORCAR_DESLIGADAS` quando `valor.py` existir; o que fica sem fonte é só `total_pago` ("N vezes"). Rota `/area/fatura` → `/area/meu-valor`, rótulo "Meu valor"/"Extrato de valor" (`spec:421-422`) |
| DIV-M02 | 6 status (ADR-0003/REQ §7) × 8 da spec; `enviada` visível × RF-SO-06 "sync invisível"; atores só associado/sistema/atendente | `docs/adr/0003:31-32,37-39`, `docs/REQUISITOS-minha-apm.md:783-787` | Adotar os nomes da spec; `enviada` como status de negócio promovido por confirmação; falha de espelho continua invisível; `sem_retorno` como marcador (coluna); atores `parceiro`, `apm`, `importacao`. Adenda à ADR-0003 |
| DIV-M03 | Cancelamento pelo associado: REQ permite em `aberta` e `aguardando_associado`; spec "enquanto o parceiro não atendeu" | `docs/REQUISITOS-minha-apm.md:771-775`, `spec:404` | Permitir em `criada`, `enviada`, `pendente_associado`; nunca em `em_atendimento`. APM cancela em qualquer não terminal com justificativa |
| DIV-M04 | Spec registra termo de busca sem resultado; RNF-16/RF-SH-04 proíbem registrar o termo; busca da spec é servidor (5 fontes + sugestões), RF-SH-04 é cliente | `spec:353-354,960`, `docs/REQUISITOS-minha-apm.md:192-196` | Busca no servidor (`GET /busca`); termo gravado **só** com `total=0`, normalizado, ≤ 80, sem `contact_id`, em tabela própria (não em `evento_uso`), purga por P-15; `busca_global` continua sem termo |
| DIV-M05 | Trilha: REQ só Acadêmico, rota própria, `POST .../concluir` por clique, `rota_inicial=/area/onboarding`; spec: todas as categorias, bloco da home, passo por evento real, some no dia 90 | `docs/REQUISITOS-minha-apm.md:96-97,622-651`, `spec:521-534` | Trilha como bloco 3 + `GET /trilha`; conclusão por `trilha.avaliar` após `uso.registrar`; sem endpoint de concluir; `rota_inicial` sempre `/area` |
| DIV-M06 | Tipos de solicitação fechados sem vínculo com benefício (REQ §7.4) × solicitação "associado, benefício, tipo" (`spec:937`) e tipos 2–3 nascendo do catálogo | `docs/REQUISITOS-minha-apm.md:1071-1082`, `spec:390-391` | `beneficio_id` nulo + `tipo_servico` ENUM para pedidos sem benefício; tipos de serviço da APM viram entradas do catálogo (`tipo_ativacao=3`) quando `sql/009` existir; os 7 tipos atuais ficam como `tipo_servico` até lá |
| DIV-M07 | Ativação como toggle `beneficio_ativacao` (RF-BE-07/08 "desativar") × tipos 1–6 com registro por tipo | `docs/REQUISITOS-minha-apm.md:362-372` | `beneficio_ativacao` só para tipo 1 (e TotalPass por leitura); demais tipos geram solicitação/inscrição/resgate. "Desativar" só tipo 1 |
| DIV-M08 | P14 cancelamento com motivo e FAQ não existem no roteiro; "Backoffice próprio" fora de escopo × B01–B13 F1 | `docs/REQUISITOS-minha-apm.md:112`, `spec:558-564,809-823` | P14 entra na fase 3 (é solicitação). Backoffice: a área expõe API interna (TI-M18); UI e identidade por ADR própria (DEC-M11) |
| DIV-M09 | Eventos de uso: 16 da spec sem equivalente (`INDICE-IDS.md:87-114`); spec quer "blocos exibidos", "origem", "estado", "tempo de leitura", "termo" | `app/uso.py:83-120` | Ampliar o catálogo (ação nova = entrada nova, regra 20): `home_bloco_clicado`, `recomendacao_dispensar`, `uso_registrado`, `carencia_vencida`, `consentimento`, `notificacao`, `cancelamento_pedido`, `solicitacao_avaliar`, `financeiro_segunda_via`, `pagamento_confirmado`; estender `detalhes` validados de `pagina_ver`, `beneficio_abrir`, `noticia_abrir`. Propriedades comuns (`spec:950-952`: categoria, fase, especialidade, regional, tempo de casa) **não** vão em cada linha: derivam por junção com `associado_perfil`/`associado_preferencia` no painel |
| DIV-M10 | P15 notificações × "sem sino" (ADR-0017) | `INDICE-IDS.md:35`, `spec:134,569` | API e tabela nascem atrás de `notificacoes`; sino só com aceite visual (EXT-M11) |
| DIV-M11 | "Inscrição com CPF preenchido" (`spec:506`) × ADR-0014 | `docs/adr/0014` | Nunca CPF no deep link; EXT-M05 |
| DIV-M12 | Carteirinha "revoga ao cancelar" e "consulta a situação no momento da leitura" (`spec:453-455`) × `/verificar` lê o cache local e diz "situação não confirmada" se velho | `inv-codigo:11` | DEC-M06 |

### DEC (`DEC-M01`…) — decisões a tomar
| ID | Questão | Opções | Prós/contras | Recomendação |
|---|---|---|---|---|
| DEC-M01 | Adotar os 8 status da spec já na `sql/008`? | (a) 6 de ADR-0003 e mapear na API · (b) 8 nomes da spec no banco | (a) mantém ADR, mas a API traduz e `enviada`/`sem_retorno` ficam sem lugar · (b) sem legado ainda, uma fonte só, exige adenda à ADR-0003 | **(b)**, com `sem_retorno` como coluna-marcador |
| DEC-M02 | `enviada` quando o canal é o CRM (tipo 3): promover no `crm_sync=ok`? | (a) sim: espelho ok ⇒ `enviada` · (b) `enviada` só para parceiro externo; tipo 3 vai `criada→em_atendimento` | (a) rótulo "Enviada ao parceiro" soa estranho para serviço da APM, mas o rótulo pode ser por tipo ("Encaminhada à equipe") · (b) deixa o associado sem sinal de que a APM recebeu de fato | **(a)** com rótulo por `tipo_ativacao` |
| DEC-M03 | Tipo 2 na F1 sem integração: criar a solicitação com `canal=relatorio|email` operada pela APM? | (a) sim (encaminhamento rastreado, `spec:110-113`) · (b) esperar ADR por parceiro | (a) não viola ADR-0009 (nenhuma chamada HTTP a parceiro); gera rastro e `sem_retorno` desde já · (b) nenhum benefício tipo 2 no catálogo até lá | **(a)**; a ADR por parceiro só muda o `canal` |
| DEC-M04 | Avaliação 0–10: onde guardar e por quanto tempo aceitar | (a) colunas em `solicitacao` + prazo em `parametro` · (b) tabela `solicitacao_avaliacao` | (a) simples, 1 avaliação por solicitação por `WHERE avaliada_em IS NULL` · (b) permite reavaliar (a spec não pede) | **(a)**, prazo padrão 30 d |
| DEC-M05 | Situação financeira sem ERP (até P-08): como o motor trata? | (a) `financeiro=None` ⇒ permite, estado `Suspenso` inexistente · (b) bloquear tudo que depende de financeiro | (a) honesto se documentado em "como calculamos"; (b) esvazia o catálogo | **(a)**; registrar em PENDENCIAS que "Suspenso" só nasce com EXT-M08 |
| DEC-M06 | `/verificar/{token}` consultar o hub a cada leitura? | (a) sim, com cache curto (5 min) e fallback "não confirmada" · (b) manter cache de 24 h | (a) atende "situação no momento" e "revoga ao cancelar"; custo = chamadas ao hub por leitura pública (limite 2 r/s na borda já existe) · (b) até 24 h de atraso | **(a)** com TTL próprio `VERIFICACAO_CACHE_TTL` e cota no hub (P-41 revisada) |
| DEC-M07 | Limites por associado compartilhados entre workers | (a) contagem no banco para tetos diários; janela por minuto segue em memória · (b) Redis · (c) tabela de janelas no MySQL para tudo | (a) zero infra nova, exato onde importa · (b) componente novo, fora da stack · (c) escrita por requisição | **(a)** |
| DEC-M08 | Cancelamento da associação (P14): solicitação local espelhada no CRM ou pedido direto ao CRM? | (a) solicitação `cancelamento_associacao` + espelho + A16 · (b) ferramenta de escrita no hub que marca o contato | (a) segue ADR-0003, dá rastro, não muda situação sem a Central · (b) escrita nova no CRM, flows desconhecidos (P-29) | **(a)**; só a APM altera a situação |
| DEC-M09 | Backoffice escreve nas tabelas de catálogo/parâmetros: mesmo usuário `apm_area`? | (a) GRANT UPDATE nas tabelas de catálogo para `apm_area` · (b) usuário `apm_area_bo` separado com UPDATE nas tabelas editoriais · (c) catálogo só por migração `sql/` (operador) | (a) amplia privilégio do processo web · (b) segrega; `db_check` ganha segunda allowlist · (c) "editável sem desenvolvedor" (`spec:121-122`) não atendido | **(b)**; o processo web continua só leitura do catálogo |
| DEC-M10 | Cadastro de parceiros (B04): tabela própria ou `apm-parceiros`? | (a) `parceiro` mínimo na área (canal, prazo, vigência) · (b) ler de `apm-parceiros` | (a) autônomo; duplica cadastro · (b) acopla a outro sistema PHP sem API | **(a)**, com `codigo_apm` (PAR017) como chave de conciliação com o CSV |
| DEC-M11 | Identidade e 2FA do backoffice | (a) Entra ID da APM (OIDC, grupos → perfis) · (b) usuários próprios + TOTP · (c) IdP `login_associado` | (a) 2FA e perfis já existem na organização; a área vira RP de 2 IdPs · (b) construir gestão de senha/2FA · (c) IdP é por CPF de associado: inadequado | **(a)**, ADR própria; até lá, API interna por token de serviço (como o hub) |
| DEC-M12 | Trilha para "todo novo associado": início da contagem dos 90 dias | (a) `data_filiacao` (CRM) · (b) `primeiro_acesso_em` (área) | (a) é o que a spec mede ("dia 90", `spec:533`); quem entra no dia 80 vê 10 dias · (b) mais útil, diverge da métrica 2 (`spec:1012`) | **(a)**, com `trilha_expira_em` persistido |
| DEC-M13 | Rótulo e chave da flag `fatura_valor` | (a) manter chave, mudar rótulo · (b) nova chave `meu_valor` | (a) sem migração; (b) limpa, exige adenda | **(a)** |

---

## Riscos e ADRs candidatas

**Riscos**
1. **Estado `enviada` sem canal confirmável** (tipo 2 em F1, canal manual): o status depende de alguém marcar no
   B05; sem backoffice, tudo fica `criada` e `sem_retorno` dispara contra a própria APM. Mitigação: `prazo_retorno`
   só conta a partir de `enviada_em`; e `canal=crm` promove automaticamente.
2. **Dois clientes de escrita no CRM** (área via hub para espelho + flows P-29): ADR-0003 e P-06 continuam
   bloqueando o espelho real; a fila local funciona, mas o atendimento só vê no CRM.
3. **Motor de elegibilidade com entrada incompleta** (sem financeiro, regional, nascimento): risco de prometer
   "disponível" a quem está suspenso. Mitigação: DEC-M05 documentado no "como calculamos" e na ficha.
4. **Crescimento de `evento_uso`** com `home_vista(blocos)` e `beneficio_visto` em cada abertura; P-15 (retenção)
   vira P1 antes da fase 4.
5. **Limites em memória × tetos de negócio**: sem DEC-M07, um associado abre 10 solicitações `outro`/dia com 2
   workers.
6. **OpenAPI exportado** expõe nomes de rotas internas se for publicado fora do repositório: manter em `docs/`.
7. **Consentimento sem versão de texto** (`spec:1196`): se o front mandar sem `versao_texto`, o registro é inválido
   para LGPD; o servidor recusa.

**ADRs candidatas**
- ADR-0018 · Solicitações v2: 8 status, atores, canal de envio, marcador `sem_retorno`, avaliação (adenda/substitui
  ADR-0003 itens 1–3).
- ADR-0019 · Motor de elegibilidade e carências por configuração (`parametro`, colunas em `beneficio`, DEC-M05).
- ADR-0020 · Recomendação v1 por regras (matriz de afinidade, dispensa, exposição/rotação, "por quê").
- ADR-0021 · Meu valor: `uso_valor`, níveis de evidência, valor de referência aprovado, `fatura_valor` sem
  forçar desligada (substitui a parte da ADR-0007 sobre `fatura_valor`).
- ADR-0022 · Outbox de comunicação e notificações no app (RD Station como consumidor; supressões §12.3).
- ADR-0023 · Tipos de ativação como estratégia por tipo e flags por tipo (2, 4, 5, 6).
- ADR-0024 · Trilha de ativação por evento real (substitui RF-ON-05).
- ADR-0025 · API interna do backoffice: namespace, identidade (DEC-M11), usuário de banco segregado (DEC-M09).
- ADR-0026 · Limites de negócio por contagem no banco (DEC-M07).
- Adenda ADR-0007 · chaves novas.

## Ordem sugerida (o que a Fase 3 deve absorver já)

1. **Fase 3 (agora):** TI-M01 → TI-M02 → TI-M03 → TI-M15 → TI-M06 (P14 é só mais dois tipos de solicitação) →
   TI-M05 (outbox + notificação **produzidas**, consumo desligado) → TI-M04 (jobs: espelho em stub, `sem_retorno`,
   `carencias_vencidas` fica pronto para a fase 4) → TI-M17 (flags) → TI-M16 (OpenAPI). Decisões necessárias
   antes do plano: DEC-M01, M02, M03, M04, M07, M08. Pedir já: EXT-M07 (P-06), EXT-M09 (P-27), EXT-M10.
2. **Fase 4:** TI-M07 (motor puro primeiro, com testes de tabela) → TI-M08 → TI-M09 → TI-M10 → TI-M12 → TI-M11
   (modo sem ERP) → TI-M14. Precisa de EXT-M01 para o seed real; DEC-M05, M12, M13.
3. **Fase 5:** eventos e notícias conforme roteiro; tipo 5 "interesse"; carência de congresso pelo motor.
4. **Transversal, quando houver decisão:** TI-M18/M19/M20 (backoffice e hub), EXT-M02/M03/M08.
5. **P13 (preferências, consentimentos, LGPD) — TI-M13:** independente de tudo; cabe entre a fase 3 e a 4 e
   destrava "próximo passo" (bloco 3) e os sinais de recomendação.
