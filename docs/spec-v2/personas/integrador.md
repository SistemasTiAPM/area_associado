# 🔌 Integrador — prontidão das integrações para a spec v2 (30/09/2026)

Levantado em 2026-10-29, só leitura. Fatos citados por `arquivo:linha`. Spec = `docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md` (abreviado `SPEC`). Inventários de 29/10 (`inventario-codigo.md`, `inventario-requisitos.md`, `inventario-vizinhos.md`) tomados como fatos.

Legenda de estado: ✅ pronto · 🟡 parcial · ⬜ não existe, dá para começar · ⛔ bloqueado por terceiro · ⚠️ divergência com a spec · 🔒 fechado por decisão (ADR) até nova ADR.

Decisões que **não se reabrem** e balizam tudo abaixo: CRM/ERP só via `mcp_hub`, escrita por ferramenta tipada (ADR-0002); WordPress por MySQL direto, usuário RO, só no job, com cache (ADR-0006); TotalPass leitura via hub + deep link (ADR-0008); parceiros fora de escopo até ADR própria por parceiro (ADR-0009); ERP só leitura após parecer (ADR-0010); `contact_id` nunca CPF (ADR-0014); token do hub só em memória (`app/integracoes/hub.py:170-194`).

Ponto de partida factual: **`app/jobs/`, `portal_wp.py`, serviço de jobs no compose e `WP_MODE` não existem** (`inventario-codigo.md:15`). As únicas integrações vivas são o IdP (OIDC), o hub (4 ferramentas, só leitura em produção) e o SMTP (simulado, P-27).

---

## Integrações

### Cadastro de associados (CRM Dataverse, via `mcp_hub`) — INT-01

- **Spec pede** (`SPEC:1125`, `SPEC:1145-1154`): dados cadastrais, categoria, filiação, regional, especialidade, situação **e avisos automáticos de mudança**, "atrás da camada INT-01"; contrato de dados F0-02; menciona "novo [cadastro] em desenvolvimento".
- **Existe hoje**:
  - Claims do IdP no login: `sub`, `contact_id`, `name`, `email`, `num_contato`, `crm`, `crm_uf`, `tipo_associado`, `associado` (rótulo da situação), `data_filiacao` (`inventario-vizinhos.md:20`; `docs/REQUISITOS-minha-apm.md:896-902`). Sem tipo ou situação o login é recusado (ADR-0016).
  - Hub, conta `area-associado`, grants **exatos** em 4 ferramentas, `modo_pii=completo` (`docs/CONTRATO-HUB.md:26-32`): `associado.perfil_consultar` devolve 14 campos — nome, e-mail, 3 telefones, endereço (7 atributos, só com `endereco_disponivel`), `num_contato`, `crm`, `crm_uf`, `tipo_associado`, `status_associativo`, `data_filiacao`, `tem_foto` (`docs/CONTRATO-HUB.md:52-65`; cliente em `app/integracoes/hub.py:254-256`, mapeamento `hub.py:126-148`). Cache 24 h em `associado_perfil` (`PERFIL_CACHE_TTL`).
  - Escrita `associado.contato_atualizar` / `foto_atualizar` implementada nos dois lados (`hub.py:258-275`; `CONTRATO-HUB.md:81-106`) mas **desligada** (`HUB_ESCRITA_HABILITADA=false`; P-29 fechada no hub em 21/10 — `mcp_hub/docs/PENDENCIAS.md:32` — falta o piloto M-3, `mcp_hub/docs/PENDENCIAS.md:25`).
  - No hub, **não concedidas à área**: `associado.situacao` já aceita `cpf|contact_id` e devolve status associativo (rótulo + código), tipo, filiação, `statecode`, associação mais recente (`mcp_hub/app/tools/associado.py:215-272`); `associado.historico_associacao` (registros `sol_associacao` com status e datas) **só por CPF**, `campo_titular="cpf"` (`associado.py:154-208`).
  - O hub é **pull**: não há webhook, assinatura de mudança nem fila de eventos do Dataverse (`mcp_hub/docs/ARQUITETURA.md:12-29`). Limite da conta: 120/min e 5.000 registros PII/dia, provisório (P-41, `docs/PENDENCIAS.md:99`; `mcp_hub/docs/PENDENCIAS.md:24`).
- **Falta**: nome social, data de nascimento, especialidades, regional/distrital, histórico de categorias por `contact_id`, situação normalizada (ativo/suspenso/cancelado — hoje só o rótulo `alf_status_associativo`), isenção/remição; **qualquer aviso automático** (filiação criada, categoria alterada, contato alterado). Detalhe campo a campo em [§13.2](#contrato-de-dados-132).
- **Dono externo**: CRM admin (Dataverse); quem desenvolve o "novo sistema de cadastro" (desconhecido — DEC-I01).
- **Estado**: 🟡 leitura real desde 21/10; escrita 🟡; avisos ⬜.
- **Fase spec / roteiro**: F1 (INT-01, F0-02) / Fases 2b (feita), 3, 4.
- **Enquanto espera**: ampliar `perfil_consultar` (ou criar `associado.situacao_ampliada`) por `contact_id` no hub (P–M); `hub_stub.py` já recebe os campos novos para as telas; "avisos" substituídos por **job de diferença** sobre o cache de perfil (TI-I09) até existir evento do cadastro.

### Cobrança (ERP Dynamics 365 F&O, via `mcp_hub`) — INT-02

- **Spec pede** (`SPEC:1126`, `SPEC:1151`, P08 `SPEC:461-479`): situação (em dia/atraso, dias), valor e forma, mensalidades do ano com status, **segunda via (PDF, linha digitável, Pix)**, pagamentos do ano, declarações, **aviso de pagamento**; "depende do novo sistema de cobrança"; P08 condicional na F1 ao gate técnico.
- **Existe hoje**: `financeiro.faturas_associado` no hub, **só por CPF**, `CustomersV3` → `CustTransactions` (`mcp_hub/app/tools/financeiro.py:101-190`): empresa, conta ERP, fatura, emissão, vencimento, valor, liquidado, saldo, liquidada em, forma de pagamento; `somente_abertas`; `timeout_s=40`, 200 linhas, classe sensível. **Sem boleto, linha digitável, Pix ou PDF** (`inventario-vizinhos.md:25`). `financeiro.inadimplencia_totalpass` lê o espelho do totalpass no RDS. ADR-0010 fixa: só leitura, só pelo hub, `contact_id`, flag `erp_financeiro` após P-08, "situação" derivada por regra **no hub** (ADR-0010 `docs/adr/0010:26-47`). O totalpass já mantém o espelho `erp_inadimplencia`/`erp_fo_faturas_item` do F&O para a mensalidade TotalPass (`totalpass/docs/AUTOMACOES_COBRANCA.md:20-26`) — desenho reaproveitável, fonte distinta.
- **Falta**: `contact_id` (P-04, `docs/PENDENCIAS.md:55`); parecer de licença (P-08, `:60`); regra de "situação"; segunda via (não há entidade OData conhecida com boleto/Pix — a cobrança da mensalidade APM não passa pelo Asaas do totalpass); aviso de pagamento (push) — inexistente; renovação anual (A10) — dado sem fonte.
- **Dono externo**: Financeiro + admin F&O; "novo sistema de cobrança" (DEC-I01).
- **Estado**: ⛔ (P-04 + P-08).
- **Fase**: F1 condicional (INT-02, FIN-01/03) / Fase 7.
- **Enquanto espera**: contrato `financeiro.situacao_consultar` + `financeiro.faturas_listar` por `contact_id` (nomes da ADR-0010) com stub; rota `GET /api/v1/financeiro` respondendo 404 `recurso_desligado`; tela com estado "cobrança indisponível → Central" (`SPEC:476-477`).

### Login atual da APM (IdP `login_associado`)

- **Spec pede** (`SPEC:1127`; P01 `SPEC:282-310`): contas reaproveitadas sem recadastro (F0-03); CPF+senha, "continuar conectado", 1º acesso **CPF + data de nascimento**, código por e-mail **ou celular**, "meus dados mudaram", ACE-05; `login`, `acesso_primeiro`.
- **Existe hoje**: RP OIDC completo (`app/oidc.py`, PKCE, RS256, back-channel). IdP: CPF+senha, lockout, triagem, 1º acesso **só por CPF** (sem nascimento), código **só por e-mail** (`login_associado/app/config.py:83-84`: `WHATSAPP_ENABLED=False`, Fortics "Fase 2"; `app/notifications.py:3-5`), **sem SMS**, sem "continuar conectado", sem "meus dados mudaram" (`inventario-vizinhos.md:16-21`). `POST /api/v1/access/validate` server-to-server (`login_associado/app/access.py:63-83`).
- **Falta**: nascimento no 1º acesso (regra `SPEC:300`), WhatsApp OTP (Fortics), evento `acesso_primeiro` (a área só conhece `associado.primeiro_acesso_em`, `inventario-codigo.md:11`; o IdP sabe quando a conta foi criada), lembrete A02.
- **Dono externo**: TI (IdP é nosso) + Fortics (contrato WhatsApp).
- **Estado**: ✅ (F0-03 resolvida: o login é o IdP).
- **Fase**: F1 / Fases 1–2 feitas.
- **Enquanto espera**: nada a esperar para a área; A01/A02 dependem de quem emite "filiação confirmada" e "conta criada" (DEC-I04).

### API de consulta de associação (parceiro confirma CPF)

- **Spec pede** (`SPEC:1128`): "já existe e está em uso".
- **Existe hoje**: **não há API JSON** (`inventario-vizinhos.md:29-30`). O que existe: portal `apm-parceiros` (sessão de parceiro, `POST /consulta/pf`, declaração PDF com QR); `/api/v1/access/validate` do IdP (Bearer `access:validate`, sem consumidor externo); `/verificar/{token}` da área (HTML, só nome/situação/hora, `app/publico.py`); `associado.situacao` no hub.
- **Falta**: definição do que a spec chama de API. Se for o portal, está coberto fora da área.
- **Dono externo**: TI. **Estado**: 🟡 (portal, não API). **Fase**: F1.
- **Enquanto espera**: nada na área. Se a APM quiser API: conta de serviço por parceiro no hub (`associado.situacao`, allowlist de IP, taxa, auditoria de titular já existem — `mcp_hub/docs/ARQUITETURA.md:47-66`) — exige ADR própria (ADR-0009 item 4).

### RD Station Marketing

- **Spec pede** (`SPEC:1065-1071`, `SPEC:1129`, `SPEC:1103-1114`): a área gera o dado e envia **campos e eventos** ao RD (régua de 29/09, 69 peças, 8 fluxos); transacional sai do próprio sistema; clique volta com **UTM + código do gatilho** virando novo evento; limite 2 msg/semana (WhatsApp ≤ 1); supressão; consentimento por canal/finalidade com **descadastro refletido no RD na hora**; horário 8–20h; leads (A17).
- **Existe hoje (reaproveitável)**:
  - `app_facial_recognition`: modo **api_key** `POST /platform/conversions?api_key=` (`api/services/RdStationService.php:14-16,57-63`); fila `rdstation_eventos` + cron a cada 2 min (`bin/apm_rdstation_sync.php:14`); `GET_LOCK` contra sobreposição (`RdStationService.php:130`); classes de resposta 2xx/400-422/401-403/429/5xx com backoff 2 min→24 h e 8 tentativas (`:21-25,35,173-224`); descarte de etapa superada (`:233-255`); dedupe e-mail+etapa+dia; UTMs `traffic_source/medium/campaign/value` só em eventos do navegador (`api/lib/RdStationEventos.php:184-186`); `legal_bases=legitimate_interest`, nunca `available_for_mailing`, nunca CPF/CRM (`CLAUDE.md §3.15`); campos `cf_categoria_apm`, `cf_regional`, `cf_parceiro`, `cf_etapa_filiacao`, `cf_status_filiacao`, `cf_origem_filiacao`.
  - `totalpass`: modo **OAuth2** (`client_id`+`secret`+`refresh_token` → `access_token` 24 h com cache e margem, refresh renovado e regravado — `src/includes/rdstation.php:7-12,127-150`); `POST /platform/events?event_type=conversion` com 1 renovação em 401 (`:224-231`); `GET /marketing/account_info` + `GET /platform/contacts/fields` para testar credencial e conferir `cf_*` (`:235-265`); classificação `ok|transitoria|credencial|configuracao|definitiva` (`:200-211`); payload puro sem CPF (`:160-193`); **outbox único** `associado_eventos` (fato, dedupe) + `associado_eventos_entregas` (uma linha por canal `rdstation|email`, estados `pendente|enviando|enviado|erro|expirado|descartado`, recuo) + `comunicacao_bloqueios` (descadastro/bounce) + matriz evento × canal + revalidação do fato antes de enviar (`docs/AUTOMACOES_COBRANCA.md:11-26`); eventos de estado `inadimplente`/`regularizado` idempotentes (`:29-50`); criação de campos por script (`rdstation_criar_campos.php`, `:66`).
  - Campos **já existentes no RD** (`totalpass/docs/rd_campos_cruzamento_planilha_x_rd_2026-10-29.csv`): `cf_apm_contactid`, `cf_apm_status_associacao`, `cf_apm_status_associativo`, `cf_apm_categoria`, `cf_apm_data_associacao`, `cf_apm_data_status`, `cf_apm_uf_crm`, `cf_apm_data_inadimplencia`, `cf_apm_metodo_pagamento`, `cf_apm_reativacao`, `cf_parceiro`, `cf_etapa_filiacao`, `cf_status_filiacao`, `cf_voce_possui_um_plano_de_saude_qualicorp`, 11 `cf_totalpass_*`. A planilha marca como **"Não Funcionando"** a sincronia CRM→RD de `cf_crm_contato_{status_associativo,data_filiacao,pri/seg/ter_especialidade,regional,tipo_assoc}` e anota que `birthdate` **tem de ser o campo padrão** (segmentação por data só nele).
- **Falta na área**: tudo (`inventario-codigo.md:46`: "RD Station: ausente"). Não há `app/integracoes/rdstation.py`, outbox, catálogo de gatilhos, leitura de `utm_*`/código de gatilho na SPA, preferências de canal, consentimento (P13 `SPEC:545-547`), webhooks de abertura/clique (necessários ao componente "interação com a comunicação" do score, `SPEC:1028-1031`).
- **Dono externo**: Marketing APM (régua, fluxos, campos, **app OAuth2 em `appstore.rdstation.com`** — receita em `totalpass/docs/AUTOMACOES_COBRANCA.md:78-81`); Jurídico (base legal por finalidade, `SPEC:1048-1049`).
- **Estado**: ⬜ na área / ✅ padrão pronto nos repos irmãos.
- **Fase**: F1 (A01–A06, A09, A16, A17, A18) / sem fase no roteiro — propor "Fase 3b comunicação".
- **Enquanto espera**: `RD_MODE=stub` (proibido em produção, mesmo validador de `HUB_MODE`), outbox + catálogo fechado de gatilhos (como `uso.py`), `scripts/check_rd.py` (token + `account_info` + `contacts/fields`), campos `cf_apm_*` conferidos no boot do job.

### Parceiros com API (tipo 2 — encaminhamento)

- **Spec pede** (`SPEC:1130`, tipo 2 `SPEC:390`, §10.2 `SPEC:851-859`): envio da solicitação com os dados do cadastro e retorno de status/uso por API ou aviso automático; "definido por parceiro"; falha no envio → reenvio automático + alerta; status `enviada` (`SPEC:759`).
- **Existe hoje**: nada. ADR-0009 fecha qualquer HTTP de saída para parceiro sem ADR própria (`docs/adr/0009:22-39`). ADR-0003 define o espelho da solicitação no CRM (`task`, P-06, `docs/PENDENCIAS.md:56`), com `solicitacao.espelhar`/`status_atualizar`/`alteracoes_consultar` ainda não existentes no hub (`docs/REQUISITOS-minha-apm.md:920-927`; hub lista como C-1, `mcp_hub/docs/OPORTUNIDADES.md:144`). Tipos de solicitação fechados sem vínculo com benefício/parceiro (`inventario-requisitos.md:49`).
- **Falta**: lista de parceiros com API e seus contratos (B04 "requisito técnico"); por parceiro: autenticação, payload mínimo (LGPD `SPEC:1050`), status de volta, prazo.
- **Dono externo**: Benefícios e parcerias + cada parceiro. **Estado**: 🔒 (ADR-0009). **Fase**: F1 → F2.
- **Enquanto espera**: tipo 2 sem API = solicitação local + espelho no CRM + **e-mail ao parceiro pelo SMTP da área** com dados mínimos (é o "aviso automático" da spec); `enviada` = e-mail aceito pelo SMTP; retorno por CSV plano B. Cada parceiro com API nasce por ADR com `beneficio.tipo_ativacao` próprio (ADR-0009 item 4).

### Parceiros sem API — CSV plano B (§13.3)

- **Spec pede** (`SPEC:1159-1180`, §10.3 `SPEC:864-875`, B06 `SPEC:816`): CSV UTF-8 `;`, um por parceiro/mês até o dia 10, **por canal autenticado e protegido, nunca e-mail comum**; colunas `cpf;parceiro_id;beneficio_id;tipo;data_evento;status;valor_referencia;valor_pago;economia;id_externo;observacao`; validação automática (CPF, associado, duplicidade, datas, valores); linhas com erro devolvidas; confirmação alimenta Meu valor e painéis; CPF não associado vira lead (§10.4).
- **Existe hoje**: nada (`inventario-requisitos.md:64`). Backoffice "fora de escopo" (`docs/REQUISITOS-minha-apm.md:112`). A área **não pode guardar CPF** (ADR-0014); o hub resolve CPF→`contact_id` e audita titular (`associado.situacao` aceita `cpf`, `mcp_hub/app/tools/associado.py:215-240`). Parceiros já se autenticam no `apm-parceiros` (`inventario-vizinhos.md:10`).
- **Falta**: canal de recepção; parser/validador; modelo `importacao` + `importacao_linha` + `uso_registrado` (nível 4 de evidência, `SPEC:991-996`); ferramenta do hub para resolver CPF em lote **devolvendo só `contact_id`**; tratamento do lead (CPF fora da área → DEC-I05).
- **Dono externo**: Benefícios (dono do processo) + cada parceiro (layout). **Estado**: ⬜. **Fase**: F1.
- **Enquanto espera**: parser + validador puros (sem I/O) com fixtures; `importar_csv` como job acionado por arquivo em volume do serviço de jobs (operador copia; fase 1) — canal autenticado definitivo em DEC-I03.

### Qualicorp (plano de saúde)

- **Spec pede** (`SPEC:1132`): F2 — consulta de CPF, oportunidade e fechamento por API ou relatório; custo da API em levantamento.
- **Existe hoje**: só dado/doc: categoria em `apm-parceiros/sql/006`, campo RD `cf_voce_possui_um_plano_de_saude_qualicorp` e novos `cf_crm_possui_plano_de_saude`/`cf_crm_operadora` (`rd_campos_...csv`). Nenhuma integração (`inventario-vizinhos.md:37`).
- **Dono externo**: Qualicorp + Benefícios. **Estado**: 🔒 (ADR-0009) / ⬜. **Fase**: F2.
- **Enquanto espera**: tipo 2 sem API (e-mail + CSV plano B). Qualquer API = ADR por parceiro.

### Clube de vantagens (Clube Certo, `clubapm.com.br`)

- **Spec pede** (`SPEC:1133`, P09 `SPEC:493-497`, tipo 6 `SPEC:394`): F1 encaminhamento rastreado; F2 acesso único, ofertas, resgates que **nascem no Minha APM** e devolvem economia.
- **Existe hoje**: allowlist `clubapm.com.br` (`frontend/src/lib/links.ts`), ação `clube_oferta_usar`, flag `clube_economia` (`inventario-codigo.md:22,25`); ADR-0009 prevê seed `oferta_clube` com `PARCEIROS_HOSTS` (`docs/adr/0009:24-39`) — ainda não implementado.
- **Falta**: tudo da F2 (SSO do fornecedor, API de ofertas/resgates, retorno de economia); contrato (P-11 catálogo/oferta da semana, `docs/PENDENCIAS.md:74`).
- **Dono externo**: fornecedor do clube. **Estado**: 🟡 F1 / 🔒 F2. **Fase**: F1 link, F2 CLU-01..03.
- **Enquanto espera**: F1 completo com seed + clique rastreado. F2 exige ADR própria; se o fornecedor suportar SSO, o provedor deve ser o **IdP `login_associado`** (o clube vira RP), nunca a área passando identidade na URL (mesmo princípio da ADR-0008 item 4).

### Plataformas de eventos e IESAPM

- **Spec pede** (`SPEC:1134`, P10 `SPEC:502-507`, tipo 5 `SPEC:393`): inscrições, presença, certificados; link/incorporação → API (F3); congressos mantêm sites próprios **com CPF já preenchido** pela área (`SPEC:506`); F0-01 mapear.
- **Existe hoje**: nada; eventos vêm do WordPress (`post type evento`, ADR-0006); IESAPM só doc (`inventario-codigo.md:46`).
- **Falta**: mapa das plataformas (F0-01); contratos. **CPF preenchido na URL contraria ADR-0014 e vaza CPF por querystring** → DIV-I04.
- **Dono externo**: IESAPM / fornecedores das plataformas. **Estado**: ⬜. **Fase**: F2 → F3.
- **Enquanto espera**: tipo 5 = interesse local (`RF-EV-02`) + link externo em allowlist; inscrição efetiva fora de escopo (`docs/REQUISITOS-minha-apm.md:100-114`).

### Portal WordPress, Portal MBE e biblioteca

- **Spec pede** (`SPEC:1135`, P11 `SPEC:512-516`, tipo 1 `SPEC:389`): notícias/conteúdo via **"API do WordPress"** e acesso único ao MBE/biblioteca.
- **Existe hoje**: decisão fechada ADR-0006 — MySQL `portal_apm` (Locaweb) direto, usuário RO novo, **só no serviço de jobs**, cache `noticia_cache`/`evento_cache` a cada 15 min, `WP_MODE=real|stub` (`docs/adr/0006:28-58`). Código: nada (`inventario-codigo.md:15`). Pendências P-07 (usuário RO, TLS, IP), P-21 (mapear post type/taxonomia de notícias), P-16 (`docs/PENDENCIAS.md:57,86-87`). O hub sugere o contrário (REST do WP via conector `http_api` F3 para fechar a 3306 da Locaweb — `mcp_hub/docs/OPORTUNIDADES.md:90-93,156`) → DIV-I02, registrada, **não reabre** a ADR-0006.
- **Falta**: `portal_wp.py`, fixtures, `WP_*` em `Settings`, `sql/010`, serviço `area-associado-jobs`; MBE/biblioteca: fornecedor e mecanismo de acesso único (desconhecidos).
- **Dono externo**: Planeta W / Locaweb (P-07, P-21); MBE/biblioteca (fornecedor a mapear). **Estado**: ⬜ (Fase 5). **Fase**: F2.
- **Enquanto espera**: `WP_MODE=stub` com `app/integracoes/fixtures/portal_*.json` (ADR-0006 item 7) — dá para construir P10/P11 inteiras sem a Locaweb.

### WhatsApp (API oficial) e SMS

- **Spec pede** (`SPEC:1136`, `SPEC:1104`, P13 `SPEC:545`): envios da régua "pelo RD ou direto"; WhatsApp ≤ 1/semana; canal preferido no perfil; contrato pendente.
- **Existe hoje**: área só `wa.me` (FAB, 1:1, `docs/REQUISITOS-minha-apm.md §5.8`); IdP com Fortics previsto e desligado (`login_associado/app/config.py:83-84`); **SMS não existe em nenhum sistema** (`inventario-vizinhos.md:17`). O RD já oferece WhatsApp/SMS como canal da régua (`SPEC:1070`).
- **Falta**: contrato (RD WhatsApp ou Fortics).
- **Dono externo**: Marketing (canal no RD) / Fortics. **Estado**: 🔒 na área (a régua sai pelo RD; a área só emite campos/eventos). **Fase**: F2.
- **Enquanto espera**: nada na área além de `canal_preferido` no perfil (campo RD). Transacional por WhatsApp (códigos) é assunto do IdP, não da área.

### Analytics e painéis

- **Spec pede** (`SPEC:1137`, §11.2–11.5): eventos de uso com propriedades comuns (categoria, fase de carreira, especialidade, regional, tempo de casa, dispositivo, UTM — `SPEC:950-952`), ferramenta a definir (F0-06); "Clarity já está no portal"; painéis por público.
- **Existe hoje**: `evento_uso` append-only, catálogo fechado de 36 ações, 16 emitidas pela UI (`inventario-codigo.md:24-25`); 16 eventos da spec sem equivalente (`inventario-requisitos.md:65`). **Clarity/GA: nenhuma ocorrência** e a CSP `script-src 'self'` sem CDN (regra 15, ADR-0013) os impede na SPA.
- **Falta**: propriedades comuns (fase de carreira exige nascimento — não vem; especialidade/regional — não vêm); origem UTM/gatilho; destino dos painéis.
- **Dono externo**: Marketing/Encantada (F0-06). **Estado**: 🟡. **Fase**: F1.
- **Enquanto espera**: manter `evento_uso` como fonte única; painéis via **views RO em `mcp_hub_dados`** lidas pelo portal do hub (mesmo padrão de `vw_totalpass_adesao`, `mcp_hub/docs/ARQUITETURA.md:70-78`) — zero script de terceiro na SPA (DEC-I07).

### `mcp_hub` (plataforma de integração)

- **Existe hoje**: transporte REST, `client_credentials`, escopos `ferramentas:ler|escrever` por conta, grants exatos, taxa/min e cota PII por conta, auditoria de titular por `contact_id`, escrita com intenção/resultado e `If-Match: *` (`docs/CONTRATO-HUB.md:10-44`; `mcp_hub/docs/ARQUITETURA.md:31-45`). Cliente da área: token só em memória com lock, 1 renovação em 401, sem redirect, corpo ≤ 2 MiB, chave `cpf` descartada e logada, `HubError` tipado com mapa 400/404/409/429/504 (`app/integracoes/hub.py:43,170-251`). Timeouts 10 s leitura / 30 s escrita (`hub.py:160-161`). Smoke `scripts/check_hub.py`.
- **Falta**: ferramentas novas (lista em TI-I02..I06); paginação `@odata.nextLink` para cursor de alterações (`docs/REQUISITOS-minha-apm.md §5.4`); limites definitivos (P-41/M-1); conector `http_api` (F3 do hub) se algum parceiro entrar por API — mantendo a área sem HTTP direto a terceiros (ADR-0002 + ADR-0009).
- **Estado**: ✅ base. **Capacidade**: 120/min e 5.000 PII/dia são incompatíveis com jobs em lote (A03/A08/A09/A13 varrem a base) → EXT-I03.

### SMTP transacional da área

- **Existe hoje**: `smtplib` STARTTLS/465, destinatário validado, corpo nunca logado, `EmailError`, stub proibido em produção (`app/integracoes/email.py:49-80`); só 2 textos (código e aviso de troca, `:83-102`), texto puro. P-27 (credencial própria, SPF/DKIM) aberta (`docs/PENDENCIAS.md:89`). O IdP tem templates HTML multipart com logo CID e Jinja autoescape (`login_associado/app/notifications.py:7-15`) — padrão a copiar. SMTP corporativo ~30/min (`totalpass/docs/AUTOMACOES_COBRANCA.md:85`).
- **Falta**: templates A04/A06/códigos de avaliação; `List-Unsubscribe` não se aplica (transacional); fila com recuo (hoje síncrono na rota).
- **Estado**: 🟡 (P-27). **Uso previsto**: só transacional (A04, A05 aviso ao associado, A06, códigos, e-mail ao parceiro tipo 2). Volume (A08 resumo mensal, A03 em massa) vai pelo RD.

---

## Contrato de dados §13.2

Fonte hoje = claim do IdP (`userinfo`, escopo `carteirinha`) ou campo de `associado.perfil_consultar` (hub). "hub (não concedida)" = existe em ferramenta que a conta `area-associado` não tem.

| Grupo | Campo (SPEC:1147-1153) | Fonte hoje | Falta | Dono |
|---|---|---|---|---|
| Identificação | identificador interno estável | IdP `contact_id`; hub `contact_id` | — | — |
| | CPF | IdP escopo `cpf` (só `cpf_mask` na sessão) | **nunca entra** (ADR-0014); hub resolve | — |
| | nome | IdP `name`; hub `nome` (`fullname`) | — | — |
| | nome social | nada | atributo do `contact` a identificar; expor em `perfil_consultar` | CRM admin |
| | data de nascimento | nada (hub `associado.consultar` tem "nascimento", `REQUISITOS §5.2`, não concedida) | expor em `perfil_consultar` ou `associado.situacao_ampliada`; necessário à fase de carreira (`SPEC:602`) e ao `birthdate` padrão do RD | CRM admin / hub |
| Contato | e-mail, celular | IdP `email`; hub `email`, `celular` | — (escrita existe, desligada) | P-29 piloto M-3 |
| Filiação | categoria atual | IdP `tipo_associado`; hub `tipo_associado` (rótulo) | código numérico junto do rótulo (o hub já o tem em `associado.situacao`: `status_associativo_codigo`) | hub (P) |
| | data de filiação | IdP `data_filiacao`; hub `data_filiacao` | — | — |
| | histórico de categorias com datas | hub `associado.historico_associacao` (`sol_associacao`: status, data, criada/modificada) **só por CPF**, não concedida | versão por `contact_id`, sem CPF na saída; confirmar se `sol_associacao` registra **categoria** ou só status | hub (P–M) + CRM admin |
| | situação (ativo, suspenso, cancelado) | IdP `associado` (rótulo `alf_status_associativo`); hub `status_associativo` | normalização fechada `ativo|suspenso|cancelado|outro` com código (`SPEC:716` "Suspenso" é financeiro, não cadastral — ver DEC-I06) | hub + negócio |
| | isenção ou remição | nada | atributo do CRM a identificar | CRM admin |
| Profissional | CRM e UF | IdP `crm`, `crm_uf`; hub `crm`, `crm_uf` (sigla) | — | — |
| | especialidades | nada (RD tem `cf_crm_contato_pri/seg/ter_especialidade` "Não Funcionando") | atributos do `contact` (option set? lookup?) → `perfil_consultar` | CRM admin / hub |
| | regional ou distrital | nada (RD `cf_crm_contato_regional/distrital` "Não Funcionando"; hub sugere `institucional.regionais`, `OPORTUNIDADES.md:86`) | lookup do contato → nome da regional em `perfil_consultar` | CRM admin / hub |
| Financeiro | situação (em dia/atraso, dias) | nada (hub `faturas_associado` por CPF, não concedida; regra de situação inexistente) | `financeiro.situacao_consultar(contact_id)` com regra no hub (ADR-0010 item 6) | P-04, P-08, Financeiro |
| | valor e forma de pagamento | hub `faturas_associado.forma_pagamento`, `valor` (não concedida) | `contact_id` | P-04, P-08 |
| | mensalidades (competência, vencimento, valor, status) | hub `faturas_associado` (fatura, emissão, vencimento, valor, liquidado, saldo, liquidada_em) | competência não existe como campo; derivar de `TransDate`; `contact_id` | P-04, P-08 |
| | segunda via (PDF, linha digitável, Pix) | **nada** — o F&O via OData não expõe boleto (`inventario-vizinhos.md:25`) | fonte inexistente; só com o "novo sistema de cobrança" ou gateway | Financeiro (DEC-I01) |
| | pagamentos do ano | hub `faturas_associado` liquidadas (não concedida); hub sugere `financeiro.valor_pago_ano` (`OPORTUNIDADES.md:117`) | agregado por `contact_id` | P-04, P-08 |
| Avisos automáticos | filiação criada, categoria alterada, pagamento confirmado, mensalidade vencida, cancelamento, contato alterado | **nenhum** — hub é pull; CRM→RD "Não Funcionando" para status/filiação | eventos do cadastro/cobrança (ou webhook do Dataverse para o hub); substituto: jobs de diferença (TI-I09) | CRM admin / F&O / novo sistema |
| Escrita | contato pelo associado | hub `associado.contato_atualizar` (implementada, desligada) | ligar após M-3; endereço após P-31 | CRM admin |
| | pedido registrado para o cadastro | ADR-0003 `task` regarding contact (P-06) | `solicitacao.espelhar` no hub (C-1) | CRM / hub |
| Requisitos | homologação anonimizada, OpenAPI, < 1 s, aviso de manutenção | hub: `APP_ENV` só produção; OpenAPI do hub existe; `TIMEOUT_CURTO_S` no login | ambiente de homologação do CRM existe no form_filiacao (`app_facial_recognition/CLAUDE.md:45`), não no hub | TI |

**O que "novo sistema de cadastro e cobrança" pode significar (DEC-I01).** Hoje cadastro = Dataverse (`contact`, `sol_associacao`) e cobrança = F&O (`CustomersV3`/`CustTransactions`), ambos só via hub. A spec trata os dois como um sistema novo com API, avisos e segunda via. Não há evidência nos sete repositórios de outro sistema. Hipóteses: (a) é o próprio D365 com Power Automate/webhooks ainda não configurados; (b) é um sistema terceiro a contratar; (c) é a reescrita do `form_filiacao` (EOL PHP 8.2 em 31/12/2026, `mcp_hub/docs/OPORTUNIDADES.md:41`). Em qualquer hipótese a área **não muda**: só o hub troca de conector; o contrato `financeiro.*`/`associado.*` por `contact_id` é o ponto de estabilidade.

---

## Gatilhos A01–A20

Canal: **RD-campo** = atualiza `cf_apm_*` do contato (segmentação); **RD-evento** = conversão com `conversion_identifier` fixo (dispara fluxo); **SMTP** = e-mail transacional da área; **app** = aviso em P15 (F2) ou bloco Pendência da home (F1). Reaproveitável: **AFR** = `app_facial_recognition`, **TP** = `totalpass`.

| ID | Gatilho | Fase | Fonte do evento | Canal | Pré-requisito externo | Reaproveitável |
|---|---|---|---|---|---|---|
| A01 | Filiação confirmada | F1 | **cadastro** (CRM: lead → contato ativo). Hoje o AFR já envia `filiacao-concluida` quando o lead é criado, não quando vira associado | RD-evento `apm_filiacao_confirmada` + RD-campo | aviso do cadastro **ou** ferramenta `associado.novos_desde(cursor)` no hub (varredura diária) | AFR `RdStationEventos::ETAPAS` (fluxo 3 já recebe `filiacao-concluida`) |
| A02 | 1º acesso não feito (3 d após A01) | F1 | derivado: A01 sem `associado.primeiro_acesso_em` | RD-evento (WhatsApp/SMS pelo RD) | A01; WhatsApp no RD | — |
| A03 | Carência vencida | F1 | **área**: job diário `data_filiacao` × catálogo de carências (`SPEC:725-730`) por benefício relevante ao segmento | app (bloco Pendência) + RD-evento `apm_carencia_vencida` com `cf_apm_beneficio_liberado` | catálogo com carências aprovado (B13/seed, `SPEC:1256`); regra de mudança de categoria (`SPEC:741`) | TP: eventos de estado idempotentes (`AUTOMACOES_COBRANCA.md:29-50`) |
| A04 | Solicitação criada | F1 | área (`solicitacao_criar`) | **SMTP** (transacional) + app | P-27 | `email.py`; templates HTML do IdP |
| A05 | Sem retorno no prazo | F1 | área: job `sem_retorno` (prazo por parceiro/benefício) | SMTP interno à equipe + SMTP/app ao associado; marcador `sem_retorno` | prazo por parceiro (B04 inexistente → coluna no seed do catálogo) | — |
| A06 | Solicitação concluída → "como foi?" 0–10 | F1 | área (`solicitacao_status_alterado` → concluída) | SMTP com link assinado (HMAC, como a carteirinha) → `POST /api/v1/solicitacoes/{uuid}/avaliar` | — | `app/dominio/carteirinha.py` token HMAC |
| A07 | Visto 2× sem ativar em 14 d | F2 | área (`evento_uso` `beneficio_abrir` × 2 sem `beneficio_ativar`) | RD-evento | — | — |
| A08 | Resumo mensal "o que é seu em {mês}" | F2 (F1 com proteção) | área: job dia 1 (Meu valor agregado) | **RD-campo** (`cf_apm_valor_ano`, `cf_apm_protecao_incluida`, `cf_apm_beneficios_usados`) + RD-evento `apm_resumo_mensal` — e-mail sai do RD (volume > SMTP 30/min) | fórmula do Meu valor aprovada (Financeiro) | TP `rdstationMontarPayload` |
| A09 | Mensalidade vencida sem pagamento (3 d) | F1 | **cobrança**: job diário `financeiro.faturas_listar(contact_id, somente_abertas)` por associado ativo → vencida > 3 d; supressão local `pendencia_financeira` | RD-evento `apm_mensalidade_vencida` + RD-campo `cf_apm_data_inadimplencia` (já existe) ; encerra com `apm_pagamento_confirmado` (sem aviso → próxima varredura) | **P-04, P-08**; segunda via inexistente (a mensagem só pode apontar a Central/portal) ; cota do hub para varrer a base (EXT-I03) | TP `inadimplente`/`regularizado` (sql/026) é o mesmo desenho, fonte diferente (mensalidade TotalPass) |
| A10 | Renovação 60/30/7 d + ligação | F2 | cobrança: data de renovação **sem fonte** no contrato do hub | RD-evento + fila de ligações | definir "renovação" (anuidade? data de filiação + 12 m?) — DEC-I01 | — |
| A11 | Sem acesso e sem uso 90 d | F2 | área: `associado.ultimo_acesso_em` + `evento_uso` | RD-evento com 1 benefício recomendado (`cf_apm_recomendado`) | — | — |
| A12 | Score < 30 | F2 | área: job diário score (`SPEC:1028-1033`); componente "interação com comunicação" exige dados do RD (webhooks ou export) | fila de ligações (B01, inexistente) + RD-campo `cf_apm_score` | webhooks do RD (OAuth2) ou leitura de abertura/clique | — |
| A13 | Mudança de categoria | F2 | **cadastro** (sem aviso) → job de diferença no cache de perfil (`tipo_associado` anterior × atual) | RD-evento `apm_categoria_alterada` + RD-campo `cf_apm_categoria` (existe) | ferramenta de histórico por `contact_id` (TI-I04) ou varredura | — |
| A14 | Evento da especialidade/região publicado | F2 | job WP (`evento_cache` novo) × temas seguidos × regional | RD-evento com link de inscrição | especialidade/regional no contrato (§13.2); P-07/P-21 | — |
| A15 | Novo benefício com afinidade alta | F2 | catálogo (publicação) × matriz de afinidade | app + entra no resumo (A08); sem e-mail isolado | matriz de afinidade (B08 inexistente → seed) | — |
| A16 | Pedido de cancelamento | F1 | área (P14, motivo obrigatório) | RD-evento `apm_cancelamento_pedido` (fluxo 6) + espelho CRM (`task`) + SMTP à Central | P-06 | — |
| A17 | Interesse de não associado | F1 | parceiro (CSV com CPF não associado) / formulário / evento | RD-evento (fluxo 1) — **o AFR já cobre o formulário** (`filiacao-inicio`…) | onde o lead vive: a área não pode guardar CPF (DEC-I05) | AFR inteiro |
| A18 | Aniversário e Dia do Médico | F1 | **RD** (campo padrão `birthdate`, "já no RD") | RD | sincronia CRM→RD do `birthdate` (planilha: tem de ser o campo padrão) | — (fora da área) |
| A19 | Documentação pendente (acadêmico, 7 d) | F2 | cadastro/AFR (`aguardando_biometria` já é conversão) | RD-evento | status de documentação no `contact` | AFR etapa `aguardando_biometria` |
| A20 | Trilha parada 7 d | F2 | área: `onboarding_progresso` | RD-evento + app | — | — |

**Regras de orquestração (`SPEC:1103-1114`) — onde vivem.** Limite 2/semana somando canais e WhatsApp ≤ 1: o RD não impõe limite entre fluxos; ou vive na régua (Marketing configura) ou a área só emite eventos e deixa o RD decidir — recomendação: **a área não aplica limite de relacionamento** (não conhece envios de outros sistemas: AFR, TP, CRM→RD); aplica só supressão (`pendencia_financeira`, benefício solicitado 14 d, cancelamento pedido) via **campos** `cf_apm_suprimir_ofertas`/`cf_apm_cancelamento_pedido` que os fluxos do RD leem (DEC-I02). Horário 8–20h: do RD. Descadastro "na hora": `PATCH /platform/contacts/email:{email}` com `legal_bases` `status=declined` por OAuth2 — chamada **síncrona com fallback para o outbox** (se o RD falhar, o descadastro fica `pendente` prioritário e o perfil já mostra "descadastrado"); além disso a área grava o consentimento localmente e **nunca mais enfileira** para aquele canal. UTM + código do gatilho de volta: links do RD levam `utm_source=rd&utm_medium=<canal>&utm_campaign=<fluxo>&apm_gatilho=A04`; `App.tsx` lê e envia `pagina_ver` com `origem` (catálogo fechado de `apm_gatilho`), sem persistir em `localStorage`.

---

## Jobs

Serviço `area-associado-jobs` (mesma imagem, `python -m app.jobs`, 256M, sem porta — CLAUDE.md "Jobs [alvo Fase 3]"), tabela `job_execucao` (`sql/012`, allowlist de UPDATE já prevê, `scripts/db_check.py:22-35`), `GET_LOCK` por job (padrão AFR `RdStationService.php:130`), registro em `evento_uso` com `origem=job` quando muda estado visível ao associado.

| Job | Periodicidade | Lê / escreve | Integração | Fase spec / roteiro |
|---|---|---|---|---|
| `outbox_crm` (espelho de solicitações) | 1 min | `solicitacao` (crm_sync pendente/erro) → hub `solicitacao.espelhar`/`status_atualizar`; escreve `crm_id`, `crm_sync` | hub escrita (C-1, P-06) | F1 / Fase 3 |
| `sync_status_crm` | 5 min | hub `solicitacao.alteracoes_consultar(cursor)` → `solicitacao`, `solicitacao_evento`; `evento_uso solicitacao_status_alterado` | hub leitura | F1 / Fase 3 |
| `sem_retorno` (A05) | diário 07h | `solicitacao` × prazo do benefício → marcador `sem_retorno`, `solicitacao_evento`; outbox SMTP interno | SMTP | F1 / Fase 3 |
| `importar_csv` (§13.3) | sob demanda (arquivo em volume) e dia 11 (cobrança de atraso) | arquivo → `importacao`, `importacao_linha`, `uso_registrado`; CPF→`contact_id` via hub em lote, CPF descartado | hub (`associado.resolver_cpf_lote`), SMTP devolução | F1 / Fase 4 |
| `sincronizar_portal` | 15 min | Locaweb (RO) → `noticia_cache`, `evento_cache` (upsert por hash, `ativo=0`, nunca DELETE) | WordPress (ADR-0006) | F2 / Fase 5 |
| `outbox_rd` | 2 min | `comunicacao_evento` + `comunicacao_entrega` (pendente, `proxima_tentativa <= now`) → RD; revalida o fato antes de enviar | RD Station | F1 / Fase 3b |
| `carencia_vencida` (A03) | diário 06h | `associado_perfil.data_filiacao` × catálogo → `comunicacao_evento`, `evento_uso carencia_vencida`, `beneficio_liberacao` | — (RD via outbox) | F1 / Fase 4 |
| `faturas_vencidas` (A09) | diário 06h30 | hub `financeiro.faturas_listar` por associado ativo → `associado.pendencia_financeira`, `comunicacao_evento` | hub (ERP) — cota | F1 condicional / Fase 7 |
| `diff_cadastro` (A13, A01 substituto) | diário 05h | hub `associado.situacao_ampliada` (ou `perfil_consultar`) → compara com `associado_perfil` → `comunicacao_evento` (`categoria_alterada`, `filiacao_confirmada`) | hub — cota | F2 / Fase 4 |
| `atualizar_perfis` | diário | renova cache de perfil vencido (REQUISITOS §5.2) — fundir com `diff_cadastro` | hub | Fase 2b (previsto) |
| `sem_primeiro_acesso` (A02) / `sem_uso_90` (A11) | diário | `associado` + `evento_uso` → `comunicacao_evento` | — | F1 / F2 |
| `resumo_mensal` (A08) | dia 1, 03h | `uso_registrado`, `beneficio_ativacao`, proteção incluída → RD-campo + evento | RD | F2 (F1 reduzido) |
| `score_engajamento` (A12) | diário 03h30 | `evento_uso`, `uso_registrado`, `pendencia_financeira`, interação RD → `associado.score` + RD-campo | RD (webhooks/export) | F2 |
| `fila_ligacoes` | diário 08h | ordem da régua (`SPEC:893-895`) → tabela `fila_ligacao` (sem backoffice: CSV para a Central por e-mail interno ou view RO para o portal do hub) | SMTP / hub views | F1 (A10/A12 F2) |
| `trilha_parada` (A20) | diário | `onboarding_progresso` → `comunicacao_evento` | — | F2 / Fase 6 |
| retenção/purga | operador | `evento_uso`, caches, `job_execucao`, `comunicacao_*` (payload apagado após envio, como AFR) | — | P-15 |

Observação de capacidade: `faturas_vencidas` + `diff_cadastro` em base de dezenas de milhares de associados **não cabem** em 120/min e 5.000 PII/dia (`docs/PENDENCIAS.md:99`). Ou o hub ganha ferramentas **agregadas por cursor** (`associado.alterados_desde`, `financeiro.vencidas_desde`) com classe própria, ou a conta de jobs recebe cota separada (EXT-I03).

---

## Propostas

### TI

| ID | Tarefa | Camada | Repo | Tam. | Pré-requisito | Começa hoje? |
|---|---|---|---|---|---|---|
| TI-I01 | Serviço `area-associado-jobs` no compose + `app/jobs/` (agendador, `job_execucao`, `GET_LOCK`, `sql/012`) | jobs/infra | area_associado | M | plano aprovado (Fase 3) | sim |
| TI-I02 | Hub: `associado.situacao` e `historico_associacao` por `contact_id` **sem CPF na saída** concedidas à área (variante `_area` ou `campo_titular=contact_id`) | hub tools | mcp_hub | P | — | sim |
| TI-I03 | Hub: ampliar `associado.perfil_consultar` (ou nova `associado.cadastro_consultar`) com nascimento, nome social, especialidades, regional/distrital, isenção/remição, código da situação | hub tools | mcp_hub | M | EXT-I01 (atributos no CRM) | parcial (nascimento já é lido em `associado.consultar`) |
| TI-I04 | Hub: `financeiro.situacao_consultar` + `financeiro.faturas_listar` por `contact_id` com regra de situação e cache 15 min (ADR-0010) | hub tools | mcp_hub | M | P-04 (A-5), P-08 | código sim; produção não |
| TI-I05 | Hub: `solicitacao.espelhar` / `status_atualizar` / `alteracoes_consultar` (C-1: credencial só Create/Write em `task`, idempotência por `uuid`, `@odata.nextLink`) | hub escrita | mcp_hub | G | P-06 | contrato e stub sim |
| TI-I06 | Hub: `associado.resolver_cpf_lote` (CSV plano B: lista de CPFs → `contact_id`/`nao_encontrado`, titular auditado, sem CPF na saída) + `associado.alterados_desde(cursor)` e `financeiro.vencidas_desde` para jobs | hub tools | mcp_hub | M | EXT-I03 cota | sim |
| TI-I07 | `app/integracoes/rdstation.py`: OAuth2 refresh→access em memória, `POST /platform/events?event_type=conversion`, `PATCH contacts/email:{email}` (descadastro), `GET account_info` + `contacts/fields`, classificação de resposta, `RD_MODE=stub`, `scripts/check_rd.py` | integração | area_associado | M | EXT-I04 (app OAuth2) | sim (stub) |
| TI-I08 | Outbox de comunicação: `sql/0xx comunicacao_evento` (fato, dedupe) + `comunicacao_entrega` (canal, estado, recuo; GRANT UPDATE) + `consentimento` (append-only) + catálogo fechado de gatilhos/`conversion_identifier` + job `outbox_rd` | banco/jobs | area_associado | M | TI-I01 | sim |
| TI-I09 | Jobs de diferença e de prazo: `diff_cadastro` (A01/A13), `carencia_vencida` (A03), `sem_retorno` (A05), `sem_primeiro_acesso` (A02), `sem_uso_90` (A11) | jobs | area_associado | M | TI-I01, TI-I02 | sim |
| TI-I10 | `importar_csv`: parser/validador §13.3 (UTF-8, `;`, 11 colunas, tipos, dedupe `parceiro_id+id_externo`), `sql/0xx importacao/importacao_linha/uso_registrado`, devolução de erros por SMTP, lead sem CPF local | jobs/domínio | area_associado | M | TI-I06; DEC-I03/I05 | parser sim |
| TI-I11 | Transacional A04/A05/A06: templates (texto + HTML no padrão do IdP), token HMAC de avaliação, `POST /api/v1/solicitacoes/{uuid}/avaliar`, fila SMTP com recuo (hoje síncrono) | API/integração | area_associado | P–M | P-27 | sim (stub SMTP) |
| TI-I12 | Tipo 2 sem API: e-mail ao parceiro com dados mínimos (allowlist por benefício), status `enviada`, `prazo_dias` e `canal` no seed do catálogo | domínio | area_associado | P | DEC-I08 | sim |
| TI-I13 | UTM + `apm_gatilho` de volta: leitura na SPA, catálogo fechado, `origem` em `evento_uso` (sem `localStorage`) | front/analytics | area_associado | P | — | sim |
| TI-I14 | Perfil: `canal_preferido`, consentimentos por finalidade/canal com versão do texto, "baixar meus dados" (JSON do que a área tem) e "pedir exclusão" (vira solicitação) — espelhados no RD por campo | API/domínio | area_associado | M | Jurídico (textos) | sim |
| TI-I15 | WordPress: `WP_*` em `Settings` (+ validador stub/prod), `portal_wp.py` + `portal_wp_stub.py` + fixtures, `sql/010`, `scripts/check_portal_wp.py` | integração/jobs | area_associado | M | P-07, P-21 para o real | sim (stub) |
| TI-I16 | Financeiro na área atrás de `erp_financeiro`: `app/api/v1/financeiro.py` (404 `recurso_desligado`), stub do hub, tela com "cobrança fora → Central" | API | area_associado | P | TI-I04 | sim |
| TI-I17 | Painéis: views RO `vw_area_*` em `mcp_hub_dados` sobre `evento_uso`/`uso_registrado`/`solicitacao` (agregados, ≥ 20 pessoas por recorte, `SPEC:1053`) | banco/hub | mcp_hub + area_associado (sql) | M | DEC-I07 | sim |
| TI-I18 | `supressao`: `associado.pendencia_financeira`, `beneficio_solicitado_em` 14 d, `cancelamento_pedido_em` → campos RD + regra local de recomendação | domínio | area_associado | P | TI-I08 | sim |
| TI-I19 | `fila_ligacoes` sem backoffice: tabela + entrega diária à Central (CSV por SMTP interno ou view no hub) | jobs | area_associado | P | DEC-I09 | sim |
| TI-I20 | IdP: data de nascimento no 1º acesso (regra P01) e evento `conta_criada` para a área (ou claim `created_at`) | IdP | login_associado | P–M | decisão do usuário (fora do recorte da área) | sim |

### EXT

| ID | O que exatamente | De quem | Destrava | Enquanto isso | Ref. |
|---|---|---|---|---|---|
| EXT-I01 | Nomes dos atributos do `contact` para nome social, nascimento, especialidades (1ª/2ª/3ª), regional/distrital, isenção/remição; se `sol_associacao` guarda **categoria** ou só status | CRM admin | TI-I03, §13.2, A03/A13/A14, fase de carreira | telas com campos opcionais `null`; stub com valores | novo |
| EXT-I02 | Definir o que é o "novo sistema de cadastro e cobrança", quem desenvolve, API, avisos, segunda via (PDF/linha digitável/Pix) | Diretoria / Financeiro / TI | P08, A09, A10, segunda via | ERP via hub só leitura, sem segunda via (texto "fale com a Central") | novo (DEC-I01) |
| EXT-I03 | Cota e taxa da conta de jobs no hub (varreduras diárias de dezenas de milhares de `contact_id`) ou aprovação de ferramentas por cursor | mcp_hub + usuário | A03/A09/A13, `importar_csv` | jobs com amostra e disjuntor (`max_por_rodada`, padrão TP) | P-41 / M-1 |
| EXT-I04 | App OAuth2 privado no `appstore.rdstation.com` para a área (callback `https://minha.apm.org.br/`), `client_id/secret`, autorização única → `refresh_token`; criação dos campos `cf_apm_*` novos (`cf_apm_score`, `cf_apm_valor_ano`, `cf_apm_suprimir_ofertas`, `cf_apm_canal_preferido`, …) | Marketing (dono da conta RD) | TI-I07 em produção | `RD_MODE=stub`; receita pronta em `totalpass/docs/AUTOMACOES_COBRANCA.md:78-81` | novo |
| EXT-I05 | Régua: tabela gatilho → `conversion_identifier` → fluxo; quem aplica o limite 2/semana; base legal por finalidade; texto de consentimento versionado | Marketing + Jurídico | TI-I08, TI-I14, DEC-I02 | catálogo provisório com os IDs A01–A20 | novo |
| EXT-I06 | Catálogo inicial com carências, categorias permitidas, **prazo de retorno e canal por parceiro**, valores de referência aprovados | Benefícios + Financeiro | A03, A05, tipo 2, Meu valor | seed vazio; nada exibido sem fonte (regra 19) | `SPEC:1256`; P-10 |
| EXT-I07 | Lista de parceiros "com API" e seus contratos técnicos; para cada um: ADR própria | Benefícios + parceiro | tipo 2 por API | tipo 2 por e-mail + CSV | ADR-0009 |
| EXT-I08 | Canal autenticado de recepção do CSV (decisão + provisão: pasta em volume, SFTP, bucket, ou módulo no `apm-parceiros`) | TI / infra + Benefícios | `importar_csv` em produção | operador copia o arquivo | novo (DEC-I03) |
| EXT-I09 | Usuário RO na Locaweb, TLS, IP; mapa do post type de notícias | Planeta W / infra | TI-I15 real | `WP_MODE=stub` | P-07, P-21 |
| EXT-I10 | Credencial SMTP própria com SPF/DKIM | TI / infra | A04/A06, troca de e-mail | `SMTP_MODE=stub` (faixa de demonstração) | P-27 |
| EXT-I11 | Parecer de licença/multiplexação do F&O; P-04 no hub | Jurídico / TI; mcp_hub | TI-I04/I16, A09 | flag `erp_financeiro` desligada | P-08, P-04 |
| EXT-I12 | Entidade/credencial do espelho de solicitações no CRM e quem trata a fila | CRM admin / negócio | TI-I05 | fila local funciona sem espelho | P-06 |
| EXT-I13 | Fornecedores de MBE, biblioteca, clube e plataformas de eventos: mecanismo de acesso único (OIDC/SAML? o IdP seria o provedor) e API de retorno | Benefícios / fornecedores | tipos 1 e 6 F2, F0-01 | link rastreado | novo; ADR-0008 item 4 |
| EXT-I14 | Sincronia CRM→RD dos campos `cf_crm_contato_*` marcados "Não Funcionando" (status, filiação, especialidade, regional) e `birthdate` padrão | Marketing + CRM admin | A18, segmentação base | a área pode popular `cf_apm_*` equivalentes (duplicidade de fonte — DEC-I02) | planilha 29/10 |

### DIV (spec × decisões/realidade)

| ID | Divergência | Onde | Tratamento |
|---|---|---|---|
| DIV-I01 | Spec: "API de consulta de associação já existe e está em uso" — não existe API JSON; existe portal `apm-parceiros` e `access:validate` sem consumidor | `SPEC:1128` × `inventario-vizinhos.md:29-30` | Registrar; se precisar de API → ADR por parceiro no hub |
| DIV-I02 | Spec: notícias via "API do WordPress" (e o hub sugere REST via `http_api`) × ADR-0006 MySQL direto no job | `SPEC:1135`; `OPORTUNIDADES.md:90-93` × `docs/adr/0006` | Decisão do usuário prevalece; registrar que o fechamento da 3306 da Locaweb (achado do hub) depende de P-07/P-16, não da área |
| DIV-I03 | Spec: cadastro/cobrança com **avisos automáticos** em tempo real × hub pull sem webhook | `SPEC:1152` × `ARQUITETURA.md:12-29` | Jobs de diferença (TI-I09) com atraso de até 24 h; registrar SLA |
| DIV-I04 | Spec: congresso "com o CPF já preenchido" na URL do site externo × ADR-0014 (área sem CPF) e vazamento por querystring | `SPEC:506` × `docs/adr/0014` | Não fazer; alternativa: o site do congresso autentica no IdP (RP) ou o associado digita o CPF lá |
| DIV-I05 | Spec: CSV plano B chega **com CPF** e lead de não associado com CPF/telefone/e-mail na "tela de leads" × ADR-0014 | `SPEC:1165,881` × ADR-0014 | CPF só em memória no job; `contact_id` persiste; lead vai ao CRM (via hub, `filiacao.lead_criar` C-3 futura) ou ao RD, nunca à área (DEC-I05) |
| DIV-I06 | Spec: estado "Suspenso" por atraso financeiro (dias configuráveis) × hoje "suspenso" é rótulo cadastral do CRM e a situação financeira não existe para a área | `SPEC:716,745` × §13.2 | Dois conceitos: `situacao_cadastral` (CRM) e `pendencia_financeira` (ERP, P-08); nomear diferente na API |
| DIV-I07 | Spec: analytics "ferramenta a definir", Clarity no portal × CSP `script-src 'self'` (regra 15, ADR-0013) | `SPEC:1137` × `docs/adr/0013` | Nenhum script de terceiro na SPA; `evento_uso` + painéis internos (DEC-I07) |
| DIV-I08 | Spec: transacional "sai do próprio sistema" inclusive **cobrança** × a área não emite cobrança (ERP só leitura, ADR-0010) | `SPEC:1067` × ADR-0010 | Mensagens de cobrança (A09) saem pelo RD como relacionamento ou pelo sistema de cobrança; a área só sinaliza |
| DIV-I09 | Spec: WhatsApp "pelo RD ou direto" × nada direto existe; IdP tem Fortics planejado | `SPEC:1136` | Régua pelo RD; transacional WhatsApp é do IdP; a área não integra WhatsApp |
| DIV-I10 | Spec: 8 status com `enviada` e `sem_retorno` × ADR-0003 com 6 estados | `SPEC:756-765` × `inventario-requisitos.md:50` | `enviada` só faz sentido no tipo 2 (e-mail/API aceito); `sem_retorno` é marcador booleano + data, não estado |
| DIV-I11 | Spec: "contas migradas", "continuar conectado", 1º acesso com nascimento, OTP por celular × IdP atual | `SPEC:288-290` × `inventario-vizinhos.md:16-21` | Backlog do IdP (TI-I20), fora do recorte da área |

### DEC (decisões a tomar)

| ID | Decisão | Opções | Prós / contras | Recomendação |
|---|---|---|---|---|
| DEC-I01 | O que é o "novo sistema de cadastro e cobrança" | (a) D365 atual + Power Automate/webhooks → hub; (b) sistema terceiro; (c) reescrita do form_filiacao com cobrança própria | (a) nada muda na área, só conector/eventos no hub; (b)/(c) contrato novo, mas **sempre atrás do hub** | Registrar (a) como premissa; contrato da área = `associado.*`/`financeiro.*` por `contact_id`; segunda via só quando a fonte existir |
| DEC-I02 | Divisão de responsabilidade com o RD: quem decide envio, limite 2/semana e supressão | (a) área só emite campos/eventos, RD orquestra; (b) área mantém janela e bloqueia envios | (a) simples, mas o RD não conhece limites entre fluxos; (b) a área não vê envios do AFR/TP/CRM→RD | (a) + campos de supressão (`cf_apm_suprimir_ofertas`, `cf_apm_cancelamento_pedido`) lidos pelos fluxos; limite configurado na régua |
| DEC-I03 | Canal autenticado do CSV plano B | (a) volume do serviço de jobs, operador copia (F1 imediato); (b) SFTP com chave por parceiro (infra nova no porteiro/EC2); (c) bucket S3 presigned (role da EC2 é read-only, `mcp_hub/docs/PENDENCIAS.md:17`); (d) upload no `apm-parceiros` (já autentica parceiros) + view RO lida pelo hub/área | (a) zero infra, manual; (b) seguro, operação de chaves; (c) exige mudar IAM; (d) reaproveita login de parceiro, mas acopla dois sistemas | F1: (a); alvo: (d) com upload no `apm-parceiros` gravando no schema `apm_parceiros` e ferramenta `parceiros.importacoes_pendentes` no hub; nunca e-mail |
| DEC-I04 | Fonte de A01/A02 ("filiação confirmada", "conta criada") | (a) IdP emite evento/claim de conta criada; (b) job de diferença no cache (`diff_cadastro`); (c) AFR reaproveitado (`filiacao-concluida` já vai ao RD) | (a) exato, mas conta criada ≠ filiação; (b) atraso ≤ 24 h; (c) marca o lead, não o associado ativo | (b) para A01 (`status_associativo` passa a Ativo) + (a) para A02 (`primeiro_acesso_em` da área já basta: A02 = A01 sem acesso em 3 d) |
| DEC-I05 | Onde vive o lead de não associado (CSV, evento) sem a área guardar CPF | (a) RD (conversão com e-mail/nome/telefone, `cf_cpf` existe no RD mas o AFR nunca o envia); (b) CRM `lead` via hub (C-3 futura); (c) AFR (já cria lead no CRM) | (a) rápido, dado de marketing; (b) oficial, exige escrita nova; (c) acopla ao form | F1: (a) sem CPF (AFR invariante); alvo: (b) quando C-3 existir |
| DEC-I06 | Normalização de "situação" para elegibilidade | (a) rótulos do CRM como estão; (b) enum fechado no hub (`ativo|suspenso|cancelado|outro` + código) | (a) frágil (texto muda); (b) regra em um lugar, auditável | (b) no hub, com tabela de mapeamento versionada; separar de `pendencia_financeira` |
| DEC-I07 | Destino dos eventos/painéis (F0-06) | (a) `evento_uso` + views RO no hub + portal do hub; (b) ferramenta externa (Clarity/GA/Metabase) | (a) zero terceiro, CSP intacta, LGPD pseudonimizada já; (b) CSP e dados fora | (a); se o Marketing exigir ferramenta, export agregado (≥ 20 pessoas) por job, nunca script na SPA |
| DEC-I08 | Tipo 2 sem API: enviar dados do associado ao parceiro por e-mail? | (a) sim, mínimo por benefício, SMTP com TLS, log sem corpo; (b) não: parceiro consulta no `apm-parceiros` com o número da solicitação | (a) é o "aviso automático" da spec, mas e-mail não é canal protegido; (b) mais seguro, exige módulo no parceiros | (b) como alvo; (a) só com allowlist de campos e aprovação do DPO (minimização `SPEC:1050`) |
| DEC-I09 | Backoffice B01–B13 inexistente: onde vivem fila de ligações, importação, leads, log de comunicação | (a) portal do `mcp_hub` com views/ferramentas (já tem TOTP, perfis, auditoria — `ARQUITETURA.md:47-57`); (b) backoffice novo na área; (c) planilhas/e-mail interno | (a) reaproveita identidade e trilha; (b) escopo grande; (c) F1 rápido | F1: (c) + (a) para leitura; escrita (status com justificativa) exige decisão própria |
| DEC-I10 | Webhooks do RD (abertura/clique) para o score | (a) rota pública na área (`POST /api/v1/rd/webhook`, assinatura, `limit_req`); (b) export diário por API; (c) sem componente de comunicação no score | (a) tempo real, superfície pública nova; (b) simples, atraso; (c) perde 15 pontos do score | (b) na F2; (a) só com ADR da Sentinela |

---

## Riscos e ADRs candidatas

**Riscos**
1. **Cota do hub × jobs em lote.** 120/min e 5.000 PII/dia inviabilizam A03/A09/A13 sobre a base inteira; sem ferramentas por cursor o job vira varredura diária que estoura a cota e derruba o Perfil (que compartilha a conta) — separar conta `area-associado-jobs` (EXT-I03).
2. **E-mail como chave do RD.** O RD identifica o contato por e-mail; troca de e-mail na área (ADR-0015) cria contato novo no RD a menos que a área envie `cf_apm_contactid` sempre e o Marketing use esse campo para deduplicar. Enviar sempre `cf_apm_contactid`; nunca `cf_cpf`.
3. **Sobrescrita de contato no RD.** O AFR já queimou isso (`name` em evento de teste renomeou contato real). A área deve enviar `name` só em eventos de servidor com dado do CRM e nunca `available_for_mailing`.
4. **Duas fontes populando o RD** (CRM→RD nativo "Não Funcionando" + área `cf_apm_*` + AFR + TP). Sem dono único dos campos, segmentações divergem. Planilha de campos como contrato (EXT-I14).
5. **Resultado incerto em escrita** vale também para o RD e o espelho CRM: outbox com `enviando` + revalidação (padrão TP), nunca reenvio cego.
6. **CSV com CPF** é o único ponto em que CPF entra no processo da área: só em memória, nunca em log, linha ou `detalhes`; o CHECK de `evento_uso`/`evento_log` já recusa a chave `cpf`.
7. **Superfície pública nova** (webhook do RD, recepção de CSV) exige `limit_req` + 403 no edge por padrão (regra 11).
8. **SMTP corporativo ~30/min**: nada de massa pela área.

**ADRs candidatas**
- ADR-0018 Comunicação e RD Station: a área emite campos/eventos por outbox, transacional por SMTP, régua/limites no RD, consentimento local espelhado, `cf_apm_contactid` como chave, sem CPF (consolida DEC-I02/I05/I10).
- ADR-0019 Serviço de jobs: agendador, `job_execucao`, `GET_LOCK`, disjuntores, conta própria no hub, ferramentas por cursor (consolida TI-I01/I09, EXT-I03).
- ADR-0020 Importação do plano B (§13.3): canal de recepção, CPF efêmero → `contact_id`, nível de evidência 4, devolução de erros (DEC-I03/I05).
- ADR-0021 Elegibilidade: situação cadastral × pendência financeira, carências por catálogo, regra no hub (DEC-I06).
- ADR-0022 Tipo 2 sem API: e-mail ao parceiro × consulta no `apm-parceiros` (DEC-I08). Parceiro com API continua uma ADR por parceiro (ADR-0009).
- ADR-0023 Painéis sobre `evento_uso` via views RO no hub (DEC-I07).

## Ordem sugerida

1. **TI-I01 + TI-I08** (jobs + outbox) — base de tudo que é assíncrono; pode começar hoje com stubs.
2. **TI-I02 + TI-I06** no hub (situação/histórico por `contact_id`, `resolver_cpf_lote`, cursores) + **EXT-I03** (conta de jobs) — pequeno, destrava A01/A03/A13 e o CSV.
3. **TI-I05 + P-06** (espelho de solicitações) com **TI-I11/I12** (A04/A05/A06 transacionais, tipo 2 por e-mail) — fecha P05 e os gatilhos F1 que não dependem de cobrança.
4. **TI-I07 + EXT-I04/I05** (cliente RD + app OAuth2 + régua) — primeiro gatilho real: A04/A16 (transacionais já existem) → A03 quando o catálogo (EXT-I06) chegar.
5. **TI-I10 + DEC-I03** (CSV plano B) — alimenta Meu valor v1.
6. **TI-I03 + EXT-I01** (contrato de dados ampliado) — personalização (fase de carreira, especialidade, regional).
7. **TI-I15 + EXT-I09** (WordPress em stub → real) — P10/P11.
8. **TI-I04/I16 + EXT-I11** (financeiro) — só quando P-04 e P-08 saírem; A09 junto.
9. F2: score, webhooks do RD (DEC-I10), SSO com fornecedores (EXT-I13, ADR por parceiro).
