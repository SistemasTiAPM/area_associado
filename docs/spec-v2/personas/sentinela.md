# 🛡️ Sentinela · Prontidão de segurança, identidade e LGPD × spec v2 (30/09/2026)

Levantado em 2026-10-29 sobre `HEAD a2af85e` (+ compose 512M fora de commit). Fontes: spec v2
(`docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md`, citada como `spec:L<linha>`), índice
`docs/spec-v2/INDICE-IDS.md`, os três inventários de 29/10 (`inventario-codigo.md`,
`inventario-requisitos.md`, `inventario-vizinhos.md`), código da área e do IdP. Só leitura; nada
foi editado no repositório.

Legenda de estado: ✅ pronto · 🟡 parcial · ⬜ a construir · ⛔ bloqueado por terceiro ·
⚠️ divergência · 🔒 fase > F1.

Decisões que não se reabrem e que este recorte respeita: sem login próprio na área (`/` → Login
APM, OIDC); CRM/ERP só via `mcp_hub`; UPDATE por tabela e DELETE nunca (ADR-0004); CSP sem
inline (ADR-0013); `contact_id` nunca CPF (ADR-0014); troca de e-mail com código + reautenticação
(ADR-0015); persona incompleta recusa login (ADR-0016); parceiros fora de escopo até ADR própria
(ADR-0009).

---

## Itens

### P01 · Acesso — o que a spec pede × o que o IdP `login_associado` já faz

**Spec pede** (`spec:L303-333`): CPF com máscara + senha + "continuar conectado"; primeiro acesso
por **CPF + data de nascimento** → código no e-mail **ou celular** já cadastrado (mascarado) →
senha; "esqueci a senha" por código; **"Meus dados mudaram"** (pedido à Central com prazo);
não-associado → filiação; **ex-associado entra e vê a página de retorno**; "a tela não confirma se
um CPF existe antes de a data de nascimento conferir"; limite de tentativas **por CPF e por rede**
(ACE-05); eventos `login` (sucesso/falha + motivo) e `acesso_primeiro` (método, dias desde a
filiação) (`spec:L956-957`); cadastro sem e-mail nem celular → Central; conta bloqueada → tempo de
espera informado.

**Existe hoje**
- Área: RP OIDC Authorization Code + PKCE S256, client confidencial (`app/oidc.py:40`
  claims obrigatórias incluem `auth_time`; `app/oidc.py:117-129` `prompt=login` no `reauth`).
  `GET /` → `/auth/login?next=/area` (`app/main.py:255-268`). Sessão cifrada `__Host-area`
  (`app/config.py:198-201`), 8 h deslizante / 12 h absoluta (`app/config.py:53-54`,
  `app/session_guard.py:111`), **sem refresh token** (regra 4). Logout RP-initiated com
  `id_token_hint` (`app/main.py:360-361`). `evento_log` grava `login_ok`/`login_falha` (motivo) e
  `logout` (inventário-código L28); `associado.primeiro_acesso_em` existe, **sem evento**
  (índice L113). Gate de persona: sem `tipo_associado`/`associado` → `persona_incompleta`
  (ADR-0016).
- IdP (inventário-vizinhos L15-22): CPF + senha, mensagem genérica, lockout 5/900 s por CPF
  (`login_associado/app/config.py:58-59`); primeiro acesso **pede só CPF** (não pede data de
  nascimento), gate CRM → canais mascarados → OTP (6 dígitos, TTL 600 s, 5 tentativas, 60 s entre
  reenvios, 3 reenvios/fluxo, 5 envios/h por CPF, `config.py:73-81`) → senha. **Só e-mail
  funciona**: `WHATSAPP_ENABLED=False` (`config.py:84`, Fortics "Fase 2"); **SMS não existe**.
  Recuperação de senha pelo mesmo OTP, revoga sessões OAuth e avisa por e-mail. Triagem
  (`login_triage.py:8,44`): fora do CRM → filiação; ativo sem conta → primeiro acesso;
  **inativo → `INACTIVE` → Central** (não há "página de retorno"). "Continuar conectado": **não
  existe** (sessão do IdP 3600 s, `config.py:44`; refresh 30/90 d só para clientes que o usam —
  a área não usa). 2FA: sem TOTP; step-up por código após 90 dias (`STEPUP_AFTER_DAYS`,
  `config.py:63`). "Meus dados mudaram": **não existe**. Limites por rede: nginx `login_post_ip`
  1 r/s, `oauth_ip` 3 r/s, Cloudflare `login-abuso` 15 req/10 s por IP (inventário-vizinhos L19).
  O IdP aceita `prompt` e `max_age` (`login_associado/app/oauth_routes.py:221-268`).

**Falta**
- SQL (área): nada para P01 em si. Opcional: nada novo; `associado.primeiro_acesso_em` já basta.
- dominio/uso (área): ação `acesso_primeiro` no catálogo de `app/uso.py` (origem `servidor`),
  emitida em `registrar_acesso` quando `primeiro_acesso_em` nasce, com `dias_desde_filiacao`
  (de `associado_perfil.data_filiacao`) e **sem** método (o IdP não informa por qual canal foi o
  OTP; ver DEC-S12). Evento `login` como taxa de sucesso: a área só vê o callback; a falha de senha
  vive no IdP → fonte do indicador 14 é o IdP (DEC-S12).
- IdP (login_associado): (a) primeiro acesso com **data de nascimento** como segundo fator de
  posse antes de revelar canais mascarados (anti-enumeração; hoje a triagem distingue "fora do
  CRM → filiação" de "no CRM" só pelo CPF, o que **confirma existência de CPF**, contra
  `spec:L320`); (b) "continuar conectado" = cookie persistente do IdP com teto absoluto e
  `amr`/`auth_time` honestos (a área não muda: step-up já usa `idp_at`, ADR-0015); (c) "meus dados
  mudaram" = formulário público → pedido à Central (sem revelar nada do cadastro, com limite e
  trilha); (d) página de retorno para ex-associado (DEC-S05); (e) canal celular (WhatsApp oficial
  ou SMS) é contrato externo (EXT-S02); (f) limite "por rede": existe por IP; falta por /24 ou
  por ASN no Cloudflare se o negócio quiser mais do que IP (TI-S05).
- frontend (área): nada (a tela é do IdP).
- infra: nada novo na área.

**Estado:** 🟡 parcial (autenticação sólida; faltam nascimento, continuar conectado, dados
mudaram, retorno do ex-associado, canal celular, evento `acesso_primeiro`). ⚠️ divergência
DIV-S01 (login na tela da área) e DIV-S02 (enumeração de CPF na triagem).
**Fase spec / roteiro:** F1 · ACE-01..05 / fases 1 (feita) + backlog do IdP (sem fase no roteiro).

---

### P13 · Perfil, preferências e privacidade — LGPD

**Spec pede** (`spec:L542-556`): canais preferidos (e-mail, WhatsApp, SMS) e frequência;
**consentimentos por finalidade, com histórico**; **baixar meus dados e pedir exclusão**; evento
`consentimento` (finalidade, canal, versão do texto, `spec:L980`); consentimento **versionado**
(`spec:L1196`); descadastro em um toque refletido no RD na hora (`spec:L1111`); direitos do titular
pelo perfil **com fila no backoffice** (`spec:L1056`); RACI: pedidos do titular executa TI, responde
o encarregado (`spec:L919`).

**Existe hoje**
- Perfil: `GET /api/v1/perfil`, `PUT /perfil/contato` (10/h), e-mail com código + step-up
  (`app/api/v1/perfil.py:44-45,176-181`), foto. Nada de consentimento, preferências de canal,
  exportação ou exclusão (inventário-requisitos L62, L68: "notificações e-mail/push" fora de
  escopo).
- Minimização já existente: `contact_id` + `sub_hash` como chave (ADR-0014), CHECK em
  `evento_log`/`evento_uso` contra CPF/segredos (sql/002, sql/004), HMAC de `sub`/IP/UA
  (`app/audit.py:44-60`), `/api/v1/sessao` nunca devolve CPF/e-mail/`sub`
  (`app/api/v1/sessao.py:4`). ESLint proíbe `localStorage` (`frontend/eslint.config:38-44`).
- Trilhas append-only sem DELETE (ADR-0004) — relevante para exclusão (ver DIV-S04).

**Falta**
- SQL: `consentimento_texto` (finalidade, canal, versão, texto, vigente_de/ate; só SELECT/INSERT,
  versão nova = linha nova) e `consentimento` **append-only** (contact_id, sub_hash, finalidade,
  canal, valor, versao, origem ENUM ui/backoffice/rd/job, request_id, ocorrido_em; sem UPDATE —
  o estado atual é a última linha). `preferencia_canal` (contact_id, canal, frequencia; UPDATE
  justificado). `titular_pedido` (contact_id, tipo ENUM exportacao/exclusao, status ENUM
  recebido/em_analise/concluido/recusado, protocolo, criado_em, concluido_em, origem; UPDATE só
  em status/concluido_em; **um pedido aberto por titular**, UNIQUE parcial via coluna
  `aberto` gerada). Para exclusão: colunas de estado `anonimizado_em` em `associado_perfil`
  (PII → NULL, foto → NULL) e `associado` (`carteirinha_token` → NULL, `desativado_em`), sem
  DELETE.
- dominio: `consentimento.py` (ler vigente, registrar com versão vigente, histórico),
  `titular.py` (abrir pedido, exportar, anonimizar). Catálogo `uso.py`: `consentimento`
  (finalidade, canal, versao, valor), `titular_pedido` (tipo).
- API: `GET/PUT /api/v1/privacidade/consentimentos` (PUT = INSERT de nova linha, CSRF, limite),
  `GET /privacidade/consentimentos/historico`, `GET/PUT /privacidade/canais`,
  `POST /privacidade/exportacao` (step-up `idp_at` ≤ `REAUTH_MAX_IDADE`; síncrono JSON com os
  dados **da área** — perfil em cache, consentimentos, solicitações, evento_uso do titular — ou
  job com link de uso único; DEC-S11), `POST /privacidade/exclusao` (step-up + confirmação +
  e-mail ao endereço cadastrado; abre `titular_pedido`, **não** anonimiza na hora; 409 se já
  houver pedido aberto). Erros tipados no contrato único.
- integrações+jobs: e-mail de protocolo ao titular (P-27); aviso ao encarregado (e-mail ou
  `task` no CRM via hub quando P-06 existir); espelho do descadastro no RD (fora da área:
  RD só existe no `app_facial_recognition`/`totalpass`; EXT-S08); job que executa a anonimização
  após o encarregado concluir (quando houver backoffice/fila) e que replica retirada de
  consentimento para o RD.
- frontend: seção "Privacidade" no Perfil (consentimentos com texto da versão, histórico,
  canais, baixar dados, pedir exclusão com confirmação e `reauth`).
- infra: `limit_req` específico para `/api/v1/privacidade/` (zona nova, 1 r/s por IP, burst 3).

**Estado:** ⬜ a construir (só a minimização de base existe). ⚠️ DIV-S04 (exclusão × DELETE nunca).
**Fase spec / roteiro:** F1 · PER-02/03 / sem fase no roteiro (proposta: Fase 3b, logo após
solicitações, porque reaproveita jobs e e-mail).

---

### §11.6 · LGPD e governança — agregados ≥ 20, pseudonimização, dado de saúde fora, retenção

**Spec pede** (`spec:L1046-1057`): base legal por finalidade (consentimento para ofertas de
parceiros e WhatsApp de relacionamento; transacional = execução do contrato); minimização ao
parceiro; **dado de saúde fora do sistema** (serviços sigilosos: só o fato do uso, agregado);
parceiros/patrocinadores só agregados **≥ 20 pessoas por recorte**; analytics com identificador
pseudonimizado; prazo de guarda de logs definido pelo jurídico. Propriedades comuns de todo
evento (`spec:L950-952`): id pseudonimizado, categoria, fase de carreira, especialidade, regional,
tempo de casa, dispositivo, origem UTM.

**Existe hoje**
- Pseudonimização: `evento_uso` tem `contact_id` + `sub_hash` (sql/004); `evento_log` só HMAC
  (`app/audit.py:4-5,44-60`); CHECK contra CPF em `detalhes` (sql/002, sql/004). O `contact_id`
  é GUID do CRM — pseudônimo reversível **só** com acesso ao CRM; a spec ("nunca o CPF em
  texto") está atendida.
- Retenção: P-15 aberta (`docs/PENDENCIAS.md:85`), purga pelo operador, sem DELETE pela
  aplicação.
- Dado de saúde: nenhuma tabela recebe; `solicitacao.dados` (ADR-0003) é JSON livre por tipo —
  **sem allowlist de campos por tipo ainda** (tabela não existe).
- Agregados ≥ 20: nada (não há painel nem exportação a parceiro).

**Falta**
- SQL: `solicitacao` (sql/008) com CHECK de tamanho e sem campo de texto livre para benefícios
  marcados `sigiloso` no catálogo (sql/009: coluna `beneficio.sigiloso`); `evento_uso.detalhes`
  nunca recebe termo de busca livre (RNF-16 já evita) nem texto de solicitação. Propriedades
  comuns: gravar **faixa** de carreira (derivada), nunca `data_nascimento` (a área não deve
  sequer cachear nascimento; só a faixa, recalculada pelo hub/perfil).
- dominio: validador por `tipo` de solicitação com allowlist de campos (molde do hub); para
  benefício `sigiloso` o `dados` é `{}` e o evento `uso_registrado` só carrega `beneficio_id`.
- API/painéis: toda consulta agregada exposta a terceiro (patrocinador, parceiro) passa por uma
  função única `agregar(min_n=20)` que suprime recortes < 20 (mora onde os painéis morarem;
  DEC-S01). Na área hoje: nada a expor.
- integrações+jobs: política de retenção executável (`scripts/retencao.sql` para o operador)
  com prazos por tabela definidos pelo jurídico (EXT-S03); `job_execucao` idem.
- frontend: nada.
- infra: nada.

**Estado:** 🟡 parcial (pseudonimização e minimização prontas; saúde/agregados/retenção a
definir). ⛔ prazo de guarda depende do jurídico (EXT-S03).
**Fase spec / roteiro:** F1 (gate F0 "critérios de LGPD", `spec:L1221-1224`) / P-15 após Fase 5.

---

### §9 · Backoffice — modelo de autenticação/autorização interno (requisitos de segurança)

**Spec pede** (`spec:L790-823`, `spec:L1194-1198`): 8 perfis (Administrador TI, Produto e
conteúdo, Benefícios e parcerias, Central, Financeiro, Diretoria, Regional, Parceiro F2);
**verificação em duas etapas em todo acesso**; toda ação registrada; log imutável; B02 "busca por
CPF, nome ou número" com visão 360 (`spec:L812`); B13 usuários/perfis, consentimentos e versões,
pedidos do titular e auditoria; **"registro de acesso a dados pessoais no backoffice"**
(`spec:L1196-1197`); 2FA; PAR-01 portal do parceiro com "dados mínimos".

**Existe hoje**
- Área: nada de backoffice ("fora de escopo", REQUISITOS L112). O IdP `login_associado` autentica
  **associados** (contato no CRM); um funcionário sem contato no CRM é triado para filiação
  (`login_triage.py`), logo **não serve** como IdP de staff sem mudança de modelo.
- Padrões reutilizáveis já existentes: `evento_log` append-only com HMAC e CHECK (sql/002),
  `feature_flag` só SELECT (sql/003), `db_check.py` com allowlist de UPDATE, cookie cifrado
  `__Host-` (ADR-0011), CSRF de API (`app/csrf.py:58-72`), CSP sem inline (`app/main.py:95-106`).
- Vizinhos: `mcp_hub` já tem usuários, grupos, `permissao` nega-por-padrão com `modo_pii`,
  `exportar`, allowlist de IP e taxa, e auditoria por titular (inventário-vizinhos L26);
  `associado.visao_360` por CPF é ferramenta **sensível** do hub. Dataverse/Entra ID já existe
  na APM (conta do hub). `apm-parceiros` é o portal de parceiro com sessão própria.

**Requisitos de segurança de cada opção (não decide onde vive — DEC-S01)**
| Opção | Autenticação / 2FA | Autorização | Auditoria e "registro de acesso a dados pessoais" | Riscos |
|---|---|---|---|---|
| (a) App separado, OIDC com **Entra ID** da APM | MFA do Entra (Conditional Access), contas corporativas, desligamento centralizado | grupos do Entra → 8 perfis (claim `groups`/app roles), RBAC por rota + por campo (PII) | `evento_log` próprio append-only; cada leitura de B02 grava `acesso_dado_pessoal` (quem, qual contact_id, quais campos, justificativa opcional) | tenant/app registration a configurar; sem CPF na tela: busca por nome/número/`contact_id` resolvida no hub (ADR-0014) |
| (b) Dentro da área, sessão de staff pelo `login_associado` | precisaria de "conta de staff" no IdP + TOTP novo | mistura perfil de associado e staff num mesmo cookie/CSRF; eleva superfície de `minha.apm.org.br` | mesma `evento_log` | **não recomendada**: viola separação de módulos e "sem login próprio"; IdP é de associados; um XSS na área expõe o backoffice |
| (c) No **portal do `mcp_hub`** (já tem usuários, grupos, grants, PII mode, cota, auditoria por titular) | hub já tem login próprio; falta 2FA (TOTP ou Entra) | `permissao` por ferramenta/grupo; `modo_pii` e `exportar` já modelam "dados mínimos" e "agregado" | auditoria por titular já existe (registro de acesso a dado pessoal pronto por desenho) | B03/B07/B08 (catálogo, textos, segmentos) são dados **da área**: o hub precisaria de ferramentas de escrita no MySQL da área ou a área expõe API interna com token de serviço (regra 11: 403 no edge) |

Invariantes que valem para qualquer opção: 2FA obrigatório (MFA do IdP corporativo ou TOTP
com segredo cifrado e códigos de recuperação); sessão de staff **curta** (≤ 8 h absoluta,
inatividade 30 min) e cookie `__Host-`; perfil "Diretoria" e "Regional" sem PII individual (só
agregados ≥ 20, §11.6); "Central" vê PII com registro de cada visualização; "Parceiro" (PAR-01)
vê só as próprias solicitações com campos mínimos e **nunca CPF** (o parceiro já recebeu o que
precisa no encaminhamento); exportação (B05 "exportação", B12) marca `exportar` e grava
`evento_log`; mudança manual de status exige justificativa (texto, não PII) e vai para
`solicitacao_evento` (append-only); OpenAPI do backoffice só interna; CSP sem inline igual à da
área; `limit_req` próprio; nenhuma rota pública.

**Falta**: tudo (decisão de lugar, IdP corporativo, 2FA, RBAC, telas). Camadas só após DEC-S01.

**Estado:** ⬜ a construir, ⛔ bloqueado por DEC-S01 e EXT-S04 (Entra ID / tenant).
**Fase spec / roteiro:** F1 (B01–B06, B12, B13) / sem fase no roteiro.

---

### P07 · Carteirinha — validação pública e revogação por cancelamento

**Spec pede** (`spec:L436-444`): validação pública mostra nome, categoria, situação ("associado
ativo") e hora; nunca CPF/e-mail/telefone; QR carrega **identificador assinado**; "a validação
**consulta a situação no momento da leitura**, então uma imagem salva continua honesta";
**filiação cancelada revoga a carteirinha**; eventos `carteirinha_aberta`, `carteirinha_validada`
(resultado ativo ou não).

**Existe hoje**
- Token HMAC base32 de 20 caracteres por `contact_id` (`app/dominio/carteirinha.py:36`,
  `CARTEIRINHA_HMAC_KEY` obrigatória em produção), `carteirinha_token UNIQUE` em `associado`
  (sql/005). `GET /verificar/{token}` público (`app/publico.py:29-48`): 404 igual para inválido e
  inexistente, `noindex`, `no-store`, zona `area_verificar` 2 r/s burst 5
  (`deploy/nginx_porteiro/area_associado.conf.example:22,113-115`), grava
  `carteirinha_verificar` origem `publico`. Mostra só nome e situação.
- **Revogação: não consulta a situação na leitura.** `resolver` lê `associado_perfil.status_associativo`
  e `atualizado_em` do cache local; se o cache tem mais de `PERFIL_CACHE_TTL` (24 h) responde
  "não confirmada no momento" (`app/dominio/carteirinha.py:83-90`). O cache só é renovado quando o
  **próprio associado** abre o Perfil (`perfil.obter`, inventário-código L11). Consequência: após
  um cancelamento no CRM, a página pública pode mostrar "Ativo" por até 24 h; depois degrada
  para "não confirmada" indefinidamente (nem "ativo" nem "cancelado"). O IdP recusa login do
  inativo, mas a verificação pública não depende de login.
- Categoria (tipo) **não** aparece na página pública (spec pede; `publico.py:46` passa só nome,
  situação, quando) — decisão de privacidade atual, registrar (DIV-S06).
- Hub já tem `associado.situacao (cpf|contact_id)` (inventário-vizinhos L25), mas a conta
  `area-associado` só tem 4 ferramentas liberadas (P-41).

**Falta**
- SQL: `associado.carteirinha_revogada_em` (UPDATE já concedido em 005) e, opcionalmente,
  `carteirinha_situacao_cache` (contact_id, situacao, consultado_em) ou reaproveitar
  `associado_perfil.status_associativo` + coluna `situacao_consultada_em` separada do
  `atualizado_em` do perfil.
- dominio: `resolver` passa a (1) checar `revogada_em`; (2) se o cache de situação tem mais de
  N min (ex.: 5–15), consultar `associado.situacao(contact_id)` no hub com **limite global** de
  chamadas vindas de `/verificar` (`LimiteJanela`, ex.: 60/min por processo) e fallback "não
  confirmada no momento" quando o hub falha ou o limite estoura; (3) nunca revelar motivo.
  Resultado da verificação (`ativo`/`nao_ativo`/`nao_confirmada`) vai no `detalhes` de
  `carteirinha_verificar`.
- integrações+jobs: job noturno de sincronização de situação (por `contact_id`, lote, dentro da
  cota P-41) que marca `carteirinha_revogada_em` quando o CRM diz cancelado; `associado.situacao`
  liberada na conta (EXT-S05). Rotação do token na reemissão/retorno do associado.
- API: `GET /carteirinha` devolve `revogada` e esconde o QR; `POST /carteirinha/compartilhar` 409
  quando revogada.
- frontend: estado "carteirinha indisponível" com caminho para a Central.
- infra: manter zona 2 r/s; adicionar `limit_req` por token? (não há como no nginx sem map;
  o limite global de hub no domínio cobre).

**Estado:** 🟡 parcial (QR assinado e privacidade prontos; revogação e consulta em tempo real
não). ⛔ `associado.situacao` na conta do hub (EXT-S05).
**Fase spec / roteiro:** F1 condicionada · CAR-01..03 ("gate técnico de dados e validação",
`spec:L444`) / Fase 2a feita; complemento proposto na Fase 3 (jobs).

---

### §13.1 · "API de consulta de associação" (parceiro confirma CPF)

**Spec pede** (`spec:L1128`): integração F1 "o parceiro confirma se o CPF é associado — já
existe e está em uso".

**Existe hoje** (inventário-vizinhos L29-30): **não há API JSON** para parceiro. `apm-parceiros`
é portal com sessão (`POST /consulta/pf`, declaração PDF com QR, `GET /verificar`); o IdP tem
`POST /api/v1/access/validate` server-to-server com escopo `access:validate`
(`login_associado/app/access.py:63-83`), **sem consumidor externo**; `totalpass/api/validate_cpf.php`
é do fluxo de adesão. A área não aceita CPF em nenhuma rota (ADR-0014) e `/verificar/{token}` é
HTML por token, não por CPF.

**Falta**: nada **na área** (e não deve haver: regra 17). O que existe de fato precisa ser
nomeado como "a API" (DEC-S07): (1) `access:validate` do IdP (contrato pronto, OAuth
client_credentials, sem PII na resposta além de `contact_id`) ou (2) ferramenta do hub
`associado.situacao` com conta por parceiro (grants por grupo, `modo_pii`, cota, allowlist de
IP, auditoria por titular — mais aderente ao §11.6) ou (3) manter só o portal `apm-parceiros`.
Requisitos de segurança de qualquer opção: credencial por parceiro, cota por conta, resposta
sem nome/CRM (só `ativo`/`nao_ativo`), registro de cada consulta por titular (é "acesso a dado
pessoal"), lead de não-associado (§10.4/A17) **não** nasce aí sem base legal explícita.

**Estado:** ⚠️ divergência DIV-S05 (spec afirma existir; não existe como API). ⬜ fora da área.
**Fase spec / roteiro:** F1 / fora do roteiro (ADR-0009 parceiros fora de escopo).

---

### §13.3 · CSV do plano B com `cpf` × ADR-0014

**Spec pede** (`spec:L1157-1180`): CSV mensal por parceiro com coluna `cpf` obrigatória (11
dígitos), `parceiro_id`, `beneficio_id`, `tipo`, `status`, valores, `id_externo`; "sempre que
possível usa o identificador interno em vez de CPF"; "canal autenticado e protegido; nunca por
e-mail comum"; importação no B06 com validação "CPF, associado, duplicidade"; CPF não associado
vira lead (`spec:L873`).

**Existe hoje**: nada. ADR-0014: "a área não aceita CPF em nenhuma rota"; o hub já descarta a
chave `cpf` em respostas (`hub.py`, inventário-código L14) e resolve CPF→`contact_id`
internamente (P-04 parcial).

**Falta**
- integrações (mcp_hub): ferramenta `importacao.plano_b_resolver` (entrada: linhas com CPF;
  saída: linhas com `contact_id` ou `nao_associado` **sem** o CPF), com cota e auditoria por
  titular; ou a própria importação vive no hub/backoffice e a área recebe só `uso_registrado`
  por `contact_id` (EXT-S06).
- SQL (área): `importacao` (arquivo hash sha256, parceiro, período, linhas válidas/erro, usuário
  de staff, `concluida_em`) e `uso_registrado` (contact_id, beneficio_id, data_evento, status,
  valores, `id_externo` UNIQUE por parceiro, fonte ENUM importacao/api/clube, nível de evidência
  1–4) — nunca CPF (CHECK no `detalhes`, molde sql/004).
- infra: canal de upload = backoffice autenticado com 2FA (DEC-S01), **nunca** rota da área
  pública; `client_max_body_size` próprio; arquivo nunca gravado em disco da área (`read_only`,
  tmpfs) — processado em memória pelo hub.
- Leads de não-associado (§10.4): CPF de não-associado é dado pessoal de **não titular da
  relação**; só com base legal e consentimento no formulário de origem; fica fora da área.

**Estado:** ⚠️ divergência DIV-S03 (formato com CPF × ADR-0014; solução: resolver no hub).
⬜ a construir, ⛔ depende de onde vive o backoffice.
**Fase spec / roteiro:** F1 / sem fase.

---

### §14 · PWA / service worker × CSP (ADR-0013) e cache de dados pessoais

**Spec pede** (`spec:L1192-1193`): "aplicativo web instalável (PWA), com ícone na tela inicial".

**Existe hoje**: nada de PWA (sem `manifest`, sem SW, sem `public/`; inventário-código L34).
CSP já tem `manifest-src 'self'` (`app/main.py:103`); sem `worker-src` → cai em `script-src
'self' 'nonce-…'` (SW de `'self'` seria aceito). `Cache-Control: no-store` em tudo que não é
`/static/spa/assets` (`app/main.py:175-185`). `index.html` da SPA recebe o **nonce por
requisição** (`app/spa.py:62`) e exige sessão (`app/spa.py`). ESLint bloqueia `localStorage`
(`frontend/eslint.config:38-44`), não bloqueia `caches`/`indexedDB` (ainda não usados).

**Falta e riscos**
- Manifest (`app/static/manifest.webmanifest`, `start_url=/area`, `scope=/area`, ícones
  próprios, `display=standalone`): seguro, sem SW. Lighthouse "instalável" no Chrome atual não
  exige SW (confirmar no audit, TI-S18).
- Service worker: **o shell HTML não pode ser pré-cacheado** (nonce por requisição e `require_associado`
  — um `index.html` em cache ignoraria o nonce e serviria conteúdo sem sessão); `/api/` nunca
  entra na Cache API (a Cache API ignora `no-store`: a exclusão tem de ser explícita no SW);
  escopo `/area` exige SW servido em `/area/sw.js` ou `Service-Worker-Allowed` — rota nova com
  `script-src 'self'`; `worker-src 'self'` explícito na CSP; SW atualizado a cada deploy (hash);
  no logout, `caches.delete` + `registration.unregister`. Lint: proibir `caches`, `indexedDB`,
  `sessionStorage` (RNF-21) fora do SW.
- Cache de dados pessoais: se houver SW, a política é "network-only para navegação e `/api/`;
  cache-first só para `/static/spa/assets/*` (imutáveis, sem PII)". Foto (`/api/v1/perfil/foto`)
  e QR (`/carteirinha/qr.svg`) **não** entram em cache (contêm dado pessoal; dispositivo
  compartilhado).
- infra: `Permissions-Policy` atual não lista `push`/`notifications` — sem efeito até existir
  push (P15).

**Estado:** ⬜ a construir; manifest = P; SW = DEC-S03. 🔒 "instalável" é RNF sem fase; push é F2.
**Fase spec / roteiro:** §14 (sem fase) / fora do roteiro (proposta: manifest no cutover; SW só
com P15).

---

### P15 · Notificações (push?) × CSP e consentimento

**Spec pede** (`spec:L569-572`, F2 · NOT-02): ícone com contagem no topo; tipos; lida/não lida;
atalho para preferências; `spec:L1066-1068` "notificações no app são do Minha APM"; A03/A04/A15
"aviso no app"; evento `notificacao` (`spec:L981`). Não diz "push" explicitamente; "aviso no app"
pode ser lista in-app.

**Existe hoje**: nada ("sem sino", ADR-0017; `Cabecalho` sem sino; inventário-código L34).
`solicitacoes_aguardando` fixo 0 em `/sessao`. E-mail só para código (ADR-0015; SMTP stub, P-27).

**Falta**
- SQL: `notificacao` (contact_id, tipo ENUM fechado, titulo, corpo curto sem PII de terceiro,
  entidade/entidade_id, criada_em, lida_em; UPDATE só em `lida_em`); se push: `push_assinatura`
  (contact_id, endpoint, chaves p256dh/auth **cifradas** com `SESSION_ENC_KEYS`-like, ua_hash,
  criada_em, revogada_em) — o endpoint identifica o dispositivo: é dado pessoal.
- dominio/API: `GET /api/v1/notificacoes` (paginado), `POST /notificacoes/{id}/lida` (CSRF),
  contagem em `/sessao`; emissão só por servidor/job (nunca pela UI).
- Web Push (se DEC-S04 aprovar): SW obrigatório (ver PWA), VAPID (par de chaves em `.env`, nunca
  no front além da pública), envio pelo serviço de jobs com `httpx` **para o endpoint do
  navegador** (host de terceiro: `fcm.googleapis.com`, `*.push.apple.com`, Mozilla) — exceção à
  regra 16 "sem redirect, timeout, erro tipado" e **egress novo** do container de jobs; payload
  cifrado (RFC 8291) **sem conteúdo sensível** (só "você tem uma atualização"); consentimento por
  canal (P13) antes de pedir permissão do navegador; `Permissions-Policy` sem bloquear
  `notifications`.
- CSP: `connect-src 'self'` continua (a assinatura push é API do navegador, não fetch); nada de
  CDN. Sem SW não há push: a opção de menor risco em F1/F2 é lista in-app + e-mail transacional.
- frontend: sino (diverge de ADR-0017 "sem sino" — Vitrine decide com a agência; registrar).

**Estado:** 🔒 F2, ⬜ a construir. DEC-S04 (push × in-app).
**Fase spec / roteiro:** F2 · NOT-02 / fora do roteiro.

---

### P-40 · `react-router-dom` 6.30 (open redirect por `\` em `<Link>`/`useNavigate`)

**Spec pede**: §14 "proteção contra as falhas mais comuns da lista OWASP" (`spec:L1194-1195`).

**Existe hoje**: P-40 aberta (`docs/PENDENCIAS.md:79`): GHSA-wrjc-x8rr-h8h6 (open redirect com
barra invertida) e GHSA-337j-9hxr-rhxg (SSR, não usado). Hoje a área **não monta destino com dado
do usuário**: `CampoBusca` navega para alvo fixo + `?q=` codificado
(`frontend/src/shell/CampoBusca.tsx:41`); `client.ts` leva `next` = rota atual
(`frontend/src/api/client.ts:50-51`) e o servidor passa por `safe_next`
(`app/session_guard.py:56-67`, que recusa `\`, `//`, esquema, controle, `/auth/`).

**Falta**: as fases 3–6 trarão `navigate(destino)` com dado de API (detalhe de solicitação,
benefício por slug, `?utm`/gatilho — ver §12.3). Ou migrar para 7.x (major; validar com o
Vitrine) ou introduzir `navegarSeguro()` que recusa `\\`, `//`, esquema e qualquer destino fora
de `rotas.ts` **antes** do cutover; regra ESLint proibindo `useNavigate` direto fora de
`lib/navegacao.ts`.

**Estado:** 🟡 parcial (mitigado por ausência de destino dinâmico; vira risco real na Fase 3).
**Fase spec / roteiro:** §14 / "antes do cutover" (P-40).

---

### §14 · OWASP, segredos, OpenAPI, ambientes

**Spec pede** (`spec:L1194-1210`): HTTPS; hash forte de senha (IdP); 2FA no backoffice; limite
de tentativas; OWASP; segredos fora do código; log imutável; cópia de segurança diária com teste
de restauração; ambientes dev/homolog (dados anonimizados)/prod; publicação automatizada;
**API documentada (OpenAPI)**.

**Existe hoje**: segredos só em `Settings` (`app/config.py`), `.env` fora do git, cópia no
Secrets Manager (P-36 pendente de replicar); CSP sem inline, XFO DENY, nosniff, Referrer
no-referrer, COOP, HSTS só prod (`app/main.py:160-187`); CSRF triplo (`app/csrf.py:58-72`);
cookie `__Host-` cifrado (ADR-0011); `limit_req` por zona no vhost; container `read_only`,
`cap_drop ALL`, `no-new-privileges`, uid 10001; TLS verificado no RDS; `/docs`, `/redoc`,
`/openapi.json` só com `APP_ENV=development` e 403 no edge (`area_associado.conf.example:61-63`);
`npm audit` com 2 avisos (P-40); sem CI (P-25); backup: ausente nos documentos (inventário-requisitos
L3, L67); ambientes: só `APP_ENV` (staging hoje) — sem homologação com dados anonimizados.
`check_oidc.py`, `check_hub.py`, `csp_check.py`, `db_check.py` existem.

**Falta**
- OpenAPI: a spec quer documentação; a decisão de segurança é não expor em produção. Gerar
  `openapi.json` no estágio Node/Python do build e versionar em `docs/api/` (artefato, não rota)
  — atende "documentada" sem abrir superfície (DIV-S08).
- OWASP em CI: `pip-audit` + `npm audit --audit-level=high` + `csp_check.py` + `db_check.py` no
  build (P-25); SAST leve (`bandit`, `eslint-plugin-security`) opcional.
- Segredos novos previstos: `VAPID_PRIVATE_KEY` (se push), chave de assinatura de link de
  exportação (`EXPORT_HMAC_KEY`), chaves do backoffice (TOTP), credenciais RD (fora da área);
  rotação de `SESSION_ENC_KEYS` (MultiFernet já suporta) e de `CARTEIRINHA_HMAC_KEY` (invalida
  QRs — requer `garantir_token` regenerar; registrar runbook).
- Ambientes: homologação com dados anonimizados = `HUB_MODE=stub` + `SMTP_MODE=stub` já cobrem
  (CRM nunca real fora de produção); formalizar em `docs/PROVISIONAMENTO.md`.
- Backup/restauração: RDS snapshots (infra, fora do repo) — registrar evidência (Estivador).

**Estado:** 🟡 parcial (controles essenciais prontos; CI, OpenAPI como artefato, runbook de
rotação e evidência de backup faltam).
**Fase spec / roteiro:** §14 / cutover.

---

### Limites de taxa novos por rota (fases 3–6 e LGPD)

**Spec pede**: ACE-05 (IdP); implícito em §14 "limite de tentativas"; P05 cancelar/avaliar; P14
cancelamento da associação; P13 exportar/excluir; P03 busca com termo registrado (`spec:L370-371`).

**Existe hoje**: nginx por IP (`area_auth` 5 r/s, `area_api` 20 r/s burst 40, foto burst 10,
`area_verificar` 2 r/s, `area_static` 30 r/s, `area_publico` 10 r/s;
`area_associado.conf.example:14-22,71-139`); por associado em memória por processo
(`app/limites.py:1-7`: 2 workers → até 2×): contato 10/h, foto 5/h (`perfil.py:44-45`), e-mail
60 s/5 h, confirmar 5 tentativas, `uso` 60 lotes/min (`uso.py:25`).

**Falta** (valores iniciais, a calibrar com `evento_uso`)
| Rota nova | Limite por associado (processo) | Observação |
|---|---|---|
| `POST /api/v1/solicitacoes` | 5/h e 20/dia; 1 aberta por tipo+benefício (UNIQUE no banco, não limite) | idempotência por `chave_idempotencia` (ADR-0003) |
| `POST /solicitacoes/{id}/cancelar`, `/responder`, `/avaliar` | 10/h | avaliar: 1 por solicitação (UNIQUE) |
| `POST /api/v1/ajuda/cancelamento` (P14) | **1 pedido aberto** por associado (UNIQUE parcial) + step-up | nunca "limite de taxa" como única defesa |
| `POST /privacidade/exportacao` | 1/dia | step-up; resultado assinado com validade curta |
| `POST /privacidade/exclusao` | 1 pedido aberto | step-up + confirmação por e-mail |
| `PUT /privacidade/consentimentos` | 20/h | append-only; flood vira custo de disco |
| `GET /beneficios?q=` com termo registrado | 30/min por associado; termo **não** vai para `detalhes` (RNF-16) — só `sem_resultado=true` e hash do termo | evita vazar texto livre na trilha |
| `GET /verificar/{token}` → hub | global 60/min por processo para chamadas ao hub | protege a cota P-41 (120/min) |
| `/api/v1/notificacoes/*` | 60/min | leitura barata |
- infra: zonas novas `area_privacidade` (1 r/s burst 3) e `area_solicitacoes` (5 r/s burst 10);
  manter 429 com `Retry-After`.
- DEC-S09: limite distribuído (hoje por processo) — para operações sensíveis a defesa correta é
  unicidade no banco, não contador.

**Estado:** 🟡 (modelo pronto; valores e zonas a criar junto com cada rota).
**Fase spec / roteiro:** F1 / fases 3–6.

---

### Step-up para operações sensíveis (P14 cancelamento, exclusão, troca de canal)

**Spec pede**: P14 cancelamento "acessível sem labirinto", motivo obrigatório, oferta de
conversa, pedido à Central + fluxo 6 (`spec:L562-566`, A16); P13 exclusão; troca de canais
preferidos (WhatsApp/SMS) e de celular (canal de OTP no IdP quando WhatsApp for ligado).

**Existe hoje**: step-up pronto e correto: `autenticacao_recente` usa `idp_at` (`auth_time` do
IdP), nunca `auth_at` (`app/session_guard.py:129-134`), `REAUTH_MAX_IDADE` 900 s
(`app/config.py:140,338-339`), `/auth/login?reauth=1` → `prompt=login` (`app/main.py:255-268`,
`app/oidc.py:129`; IdP honra `prompt=login`, `oauth_routes.py:262`). Aplicado **só** à troca de
e-mail (`perfil.py:176-181`, ADR-0015). `PUT /perfil/contato` (celular/telefone) **não** exige
step-up — aceitável enquanto o celular não é canal de OTP (IdP: `WHATSAPP_ENABLED=False`).

**Falta**
- API: dependência reutilizável `exigir_reautenticacao` (403 `reautenticacao_necessaria`, mesmo
  contrato de erro) aplicada a: `POST /ajuda/cancelamento`, `POST /privacidade/exclusao`,
  `POST /privacidade/exportacao`, `PUT /privacidade/canais` quando ligar WhatsApp/SMS, e
  **`PUT /perfil/contato` para o campo celular no dia em que o IdP passar a mandar OTP por
  celular** (senão a troca de celular rouba a recuperação de senha, mesmo raciocínio da
  ADR-0015). Cancelamento da associação: step-up **+** confirmação por e-mail (código ou link de
  uso único) **+** janela de arrependimento antes de ir à Central (gravação em `solicitacao`
  tipo `cancelamento` com `motivo` ENUM fechado, sem texto livre obrigatório).
- dominio: `cancelamento` como tipo de solicitação (ADR-0003) ou tabela própria com motivo ENUM
  (não uso, preço, mudança, insatisfação, outro) — nunca sai da área sem passar pelo hub (task no
  CRM, P-06).
- frontend: fluxo `reauth=1` já existe para e-mail; reaproveitar.
- IdP: nada (já honra `prompt=login`/`max_age`).

**Estado:** 🟡 (mecanismo pronto; falta aplicar às novas operações e à troca de celular).
**Fase spec / roteiro:** F1 · AJU-02 / Fase 3 (solicitações) + Fase 3b (LGPD).

---

### §12.3 · UTM e código de gatilho em links × `safe_next` / open redirect

**Spec pede** (`spec:L1070-1071`, `spec:L1114`): "clique volta com UTM e código do gatilho →
novo evento"; "todo link com UTM e código do gatilho"; propriedade comum `origem (UTM)`
(`spec:L952`); `beneficio_visto` com origem "e-mail" (`spec:L961`).

**Existe hoje**: `safe_next` aceita só caminho relativo com `?` (`app/session_guard.py:56-67`:
checa `:` apenas antes do `?`, logo `?next=https://x` dentro da query passa como **texto**, não
como destino — correto); `next` é só do login. A SPA não lê `utm_*` nem gatilho (inventário:
sem ocorrência de `utm` em `frontend/src`). `evento_uso` não tem coluna de origem de campanha
(`origem` ENUM é servidor/ui/job/publico, sql/004). `Referrer-Policy: no-referrer` já impede
vazar a query para terceiros.

**Falta**
- Contrato (EXT-S08 com Marketing/RD): nomes fixos (`utm_source`, `utm_medium`, `utm_campaign`,
  `g=<A01..A20>`), valores **de catálogo fechado** (regex curto), só em links para
  `https://minha.apm.org.br/area/...` (nunca para `/auth/login` direto: o `next` leva a query
  inteira e `safe_next` a preserva).
- frontend: `lib/campanha.ts` lê a query **uma vez** no boot, valida contra o catálogo, descarta o
  resto, limpa a URL (`history.replaceState`) e anexa `campanha{origem,gatilho}` ao próximo
  `pagina_ver`/`beneficio_abrir`; **nunca** usa o valor como destino de navegação (P-40) nem o
  renderiza como HTML.
- uso.py: validar `detalhes.campanha` pelo mesmo catálogo (servidor nunca confia na UI);
  tamanho máximo; sem texto livre.
- Nada muda em `safe_next` (já suficiente); adicionar teste em `tests/test_guard.py` para
  `next=/area/beneficios/x?utm_source=rd&g=A03` (aceito) e `next=/area?next=//evil` (aceito como
  texto, nunca seguido).

**Estado:** ✅ `safe_next` pronto; ⬜ catálogo e captura da origem a construir.
**Fase spec / roteiro:** F1 (A01–A06) / Fase 4 (benefícios) ou junto do RD (fora do roteiro).

---

### Tipos 1/2/6 · links para parceiros × allowlist de hosts

**Spec pede** (`spec:L395-405`): tipo 1 "abre o serviço com acesso único ou código pessoal";
tipo 2 "envia os dados ao parceiro e abre a solicitação"; tipo 6 "abre a oferta no clube com
acesso único"; princípio 4 "encaminhamento rastreado" (`spec:L178-181`); P09 F1 "encaminhamento
rastreado" (`spec:L477-479`).

**Existe hoje**: `LinkExterno` só `https:` e hosts fixos (`frontend/src/lib/links.ts:7-28`:
`wa.me`, `clubapm.com.br`, `apm.org.br`, `totalpass.apm.org.br`, `login.apm.org.br`);
`beneficio.url_acesso` previsto no seed (sql/009, não existe); ADR-0009: nenhuma chamada HTTP a
parceiro; `Referrer-Policy: no-referrer`; `rel=noopener` (COOP same-origin cobre `window.opener`).
"Acesso único" (SSO com parceiro) **não existe** e exigiria ADR (parceiro como RP do Login APM ou
assinatura de token pela área — fora de escopo).

**Falta**
- SQL (sql/009): `beneficio.url_acesso` validada na migração (só `https://` + host em
  `parceiro.host` cadastrado); `parceiro.host` UNIQUE; sem UPDATE em `parceiro` (muda por
  migração).
- API: redirecionador **servidor** `GET /api/v1/ir/{beneficio_slug}` (sessão obrigatória; 302
  `Location` montada **só** a partir do seed, nunca de query; grava `beneficio_abrir`/
  `clube_acesso` origem `servidor` com `request_id` — é o "encaminhamento rastreado" sem
  depender do `sendBeacon` da UI), `Cache-Control: no-store`, `Referrer-Policy: no-referrer`
  já global. Tipo 2 **não** envia dados ao parceiro (ADR-0009): abre `solicitacao` e a APM
  encaminha; se um dia houver API do parceiro, nasce ADR + integração em `integracoes/`.
- frontend: allowlist de `links.ts` vira **derivada do seed via `/api/v1/sessao` ou do próprio
  redirecionador** (a UI não precisa mais conhecer hosts; só chama `/ir/{slug}`); manter
  `urlExternaSegura` como segunda barreira para o que restar (wa.me, clube).
- CSP: nada muda (`form-action` continua `'self'` + issuer; 302 do servidor não é afetado por
  CSP). **Nunca** `<iframe>` de parceiro (`frame-src` não existe → `default-src 'self'`).
- "Código pessoal" (tipo 1): se o parceiro exigir identificação, é dado derivado via hub (nunca
  CPF na URL); `num_contato` na query de terceiro é dado pessoal → só com contrato (ADR própria).

**Estado:** 🟡 (allowlist estática pronta; redirecionador e seed a construir). ⚠️ "acesso único"
e "envia os dados ao parceiro" × ADR-0009 (DIV-S07).
**Fase spec / roteiro:** F1 (tipos 1–3) / Fase 4 (benefícios), Fase 6 (clube).

---

## Propostas

### TI — tarefas internas

| ID | Tarefa | Camada | Repo | Tam. | Pré-requisito interno | Hoje? |
|---|---|---|---|---|---|---|
| TI-S01 | Evento `acesso_primeiro` (origem servidor, `dias_desde_filiacao`) emitido em `associado.registrar_acesso` quando `primeiro_acesso_em` nasce; teste | dominio/uso | area_associado | P | — | sim |
| TI-S02 | Primeiro acesso no IdP com **CPF + data de nascimento** antes de revelar canais; resposta única para "CPF inexistente" e "nascimento não confere"; lockout próprio por CPF e IP; `evento` de auditoria | IdP (triage/cadastro) | login_associado | M | EXT-S01 (nascimento no CRM via hub) | não |
| TI-S03 | "Continuar conectado" no IdP: cookie persistente opt-in (30 d deslizante, 90 d absoluto), `amr` sem `pwd` após o primeiro login, `auth_time` original preservado (a área já faz step-up por `idp_at`); revogação no logout e na troca de senha | IdP sessão | login_associado | M | DEC-S06 | após DEC |
| TI-S04 | "Meus dados mudaram": formulário público no IdP (CPF + o que mudou + contato novo) → abre pedido para a Central (task no CRM via hub) **sem** revelar nada do cadastro; limite 3/h por IP, honeypot/Turnstile; prazo informado | IdP + hub (task) | login_associado, mcp_hub | M | P-06 (entidade de task) | parcial |
| TI-S05 | ACE-05 "por rede": zona nginx por `/24` (map de `$binary_remote_addr`) no vhost do IdP ou regra Cloudflare por ASN; documentar os limites já existentes como ACE-05 | infra | infra (porteiro/Cloudflare) | P | — | sim |
| TI-S06 | Página de retorno do ex-associado conforme DEC-S05 (opção a: estática no IdP a partir da triagem `INACTIVE`, com link para filiação e Central, sem sessão) | IdP | login_associado | P | DEC-S05 | após DEC |
| TI-S07 | Consentimentos versionados: `sql/0xx` `consentimento_texto` + `consentimento` (append-only) + `preferencia_canal`; dominio; `GET/PUT /api/v1/privacidade/consentimentos` + histórico + canais; ação `consentimento` no catálogo; UI no Perfil | SQL/dominio/API/front | area_associado | M | textos e finalidades (EXT-S03) — pode nascer com texto placeholder "v0" **desligado por flag** `lgpd_consentimentos` | sim (atrás de flag) |
| TI-S08 | "Baixar meus dados": `POST /privacidade/exportacao` com step-up, 1/dia, JSON (+PDF opcional) gerado em memória com dados da área (perfil cache, consentimentos, solicitações, notificações, `evento_uso` do titular); `evento_log` `titular_exportacao` | API/dominio | area_associado | M | TI-S07; DEC-S11 | após DEC |
| TI-S09 | "Pedir exclusão": `titular_pedido` + `POST /privacidade/exclusao` (step-up + confirmação por e-mail), protocolo, 1 aberto; anonimização por coluna de estado (`anonimizado_em`, PII → NULL, token → NULL, foto → NULL) executada por job após conclusão do encarregado; **sem DELETE** (ADR nova) | SQL/dominio/API/jobs | area_associado | G | TI-S07, jobs (Fase 3), P-27, DEC-S02 | não |
| TI-S10 | Retenção (P-15) com prazos do jurídico: `scripts/retencao.sql` do operador + `docs/PROVISIONAMENTO.md`; `evento_log` mantém só HMAC (já) | SQL/infra | area_associado | P | EXT-S03 | parcial |
| TI-S11 | Propriedades comuns de `evento_uso` sem PII: `faixa_carreira`, `tipo`, `uf`, `tempo_casa_meses` derivados no servidor (nunca nascimento cru); CHECK em `detalhes` contra `nascimento`/`data_nascimento`/`telefone`/`email` | SQL/uso | area_associado | P | — | sim |
| TI-S12 | Allowlist de campos por `tipo` de solicitação (molde do hub) + `beneficio.sigiloso` → `dados={}`; CHECK de tamanho | SQL/dominio | area_associado | P | sql/008 (Fase 3) | junto da Fase 3 |
| TI-S13 | Padrão "registro de acesso a dado pessoal": tipo `acesso_dado_pessoal` em `evento_log` (categoria `seguranca`, `detalhes{alvo_contact_hash, campos}`) — pronto para o backoffice e já usado pela área quando a Central (futuro) ler perfil | audit | area_associado (padrão), backoffice | P | DEC-S01 | sim (padrão) |
| TI-S14 | Verificação pública consulta situação: `associado.situacao(contact_id)` via hub com cache de N min, limite global de hub a partir de `/verificar`, fallback "não confirmada", `carteirinha_revogada_em`, resultado no `detalhes` de `carteirinha_verificar` | dominio/integrações/SQL | area_associado | M | EXT-S05 | não |
| TI-S15 | Job noturno de situação (lote por `contact_id`, dentro da cota) marcando revogação; `GET /carteirinha` com `revogada`; rotação de token na reemissão | jobs/API | area_associado | M | jobs (Fase 3), EXT-S05 | não |
| TI-S16 | `apm-parceiros`/IdP: nomear a API de consulta de associação (DEC-S07) e, se for o hub, criar grupo `parceiros` com `associado.situacao` em `modo_pii=minimo` (resposta só `ativo` bool) e cota | hub grants | mcp_hub | M | DEC-S07 | após DEC |
| TI-S17 | Importação plano B no hub: ferramenta que recebe CSV com CPF e devolve linhas com `contact_id`/`nao_associado` (sem CPF), auditoria por titular; área só ingere `uso_registrado` por `contact_id` | integrações | mcp_hub + area_associado | M | DEC-S01 (onde fica o upload), EXT-S06 | não |
| TI-S18 | PWA mínima: `manifest.webmanifest` + ícones em `app/static/`, `<link rel=manifest>` no `index.html` do Vite, `theme_color`; **sem SW**; Lighthouse "instalável" conferido; CSP inalterada | front/infra | area_associado | P | — | sim |
| TI-S19 | Service worker restrito (só se DEC-S03 aprovar): `app/static/spa/sw.js` em `/area/sw.js`, `worker-src 'self'`, network-only para navegação e `/api/`, cache-first só `/static/spa/assets/`, unregister no logout; lint proíbe `caches`/`indexedDB` fora do SW; e2e com `securitypolicyviolation` | front/infra | area_associado | M | TI-S18, DEC-S03 | após DEC |
| TI-S20 | P-40: `lib/navegacao.ts` com `navegarSeguro()` (recusa `\\`, `//`, esquema, fora de `rotas.ts`), regra ESLint contra `useNavigate`/`<Link to={dinamico}>` fora dela; avaliar react-router 7.x com o Vitrine | front | area_associado | P | — | sim |
| TI-S21 | Catálogo de parâmetros de campanha (`utm_*`, `g=A01..A20`) lido uma vez no boot, validado, removido da URL, anexado a `pagina_ver`/`beneficio_abrir`; `uso.py` valida no servidor; testes de `safe_next` com query | front/uso | area_associado | P | EXT-S08 (nomes) — pode nascer com catálogo provisório | sim |
| TI-S22 | Redirecionador `GET /api/v1/ir/{slug}` (sessão, 302 só do seed, evento servidor) + validação de `url_acesso`/`parceiro.host` na migração sql/009 + `links.ts` reduzido | API/SQL/front | area_associado | M | sql/009 (Fase 4) | junto da Fase 4 |
| TI-S23 | Limites por rota nova (tabela do item) + zonas `area_privacidade`/`area_solicitacoes` no vhost + unicidade no banco para pedidos sensíveis | API/infra | area_associado | P | cada rota | junto de cada fase |
| TI-S24 | Dependência `exigir_reautenticacao` reutilizável + aplicação a cancelamento, exclusão, exportação, canais; regra: `PUT /perfil/contato` exige step-up para `celular` quando o IdP ligar OTP por celular (`WHATSAPP_ENABLED`) | API | area_associado | P | — | sim |
| TI-S25 | Cancelamento da associação (P14/AJU-02): tipo `cancelamento` em `solicitacao` com `motivo` ENUM, step-up + confirmação por e-mail + janela de arrependimento, 1 aberto; espelho em task no CRM; evento `cancelamento_pedido` | SQL/dominio/API/front | area_associado | M | sql/008 (Fase 3), P-06, P-27 | junto da Fase 3 |
| TI-S26 | Segredos novos e rotação: runbook de rotação de `SESSION_ENC_KEYS` (MultiFernet) e `CARTEIRINHA_HMAC_KEY` (regenerar tokens), `EXPORT_HMAC_KEY`, `VAPID_*` (condicional); replicar no Secrets Manager (P-36) | config/docs | area_associado | P | — | sim |
| TI-S27 | OpenAPI como artefato: gerar `docs/api/openapi.json` no build (script Python) e manter 403 no edge; diff no PR | build/docs | area_associado | P | — | sim |
| TI-S28 | CI de segurança (P-25): `pip-audit`, `npm audit --audit-level=high`, `csp_check.py`, `db_check.py`, e2e com CSP; GitHub Actions com a deploy key | infra | area_associado | M | acesso ao GitHub Actions | sim |
| TI-S29 | Notificações in-app (F2): tabela `notificacao`, `GET /notificacoes`, `POST /{id}/lida`, contagem no `/sessao`, emissão só servidor/job; sem push | SQL/API/front | area_associado | M | jobs; DEC-S04; Vitrine × "sem sino" | 🔒 F2 |
| TI-S30 | Web Push (só se DEC-S04 aprovar): `push_assinatura` cifrada, VAPID, envio pelo serviço de jobs com egress a push services (regra 16: timeout, sem redirect, erro tipado), payload sem conteúdo sensível, consentimento por canal antes do `Notification.requestPermission` | jobs/integrações/front | area_associado | G | TI-S19, TI-S29, TI-S07 | 🔒 F2 |
| TI-S31 | Função única de agregação `k≥20` para qualquer painel/exportação a terceiro (onde os painéis morarem); `evento_uso` nunca exportado cru | dominio/backoffice | backoffice/hub | P | DEC-S01 | após DEC |
| TI-S32 | Homologação com dados anonimizados formalizada: `APP_ENV=staging` + `HUB_MODE=stub` + `SMTP_MODE=stub` como ambiente de homolog; validador já proíbe stub em produção | docs/config | area_associado | P | — | sim |

### EXT — dependências externas

| ID | O que precisamos exatamente | De quem | Destrava | Enquanto espera | P-xx |
|---|---|---|---|---|---|
| EXT-S01 | Campo de **data de nascimento** no `contact` com completude por categoria (≥ 95%?) e exposição ao IdP via hub (`associado.consultar` já devolve? confirmar) só como **comparação** (hub responde `confere: bool`, nunca a data) | CRM admin + mcp_hub | TI-S02; fase de carreira (§7.1) | IdP segue com CPF + canais mascarados; a área deriva faixa só quando o hub expuser `faixa_carreira` | novo |
| EXT-S02 | Canal celular para OTP e avisos: WhatsApp API oficial (Fortics) **ou** provedor SMS, com contrato, remetente aprovado e limites | TI/contratos | OTP por celular no IdP; "método" de `acesso_primeiro`; P13 canais; A02 | só e-mail; P13 mostra WhatsApp/SMS como "em breve"? **Não** (regra 19): oculta até existir | novo (P-11 é conteúdo, não canal) |
| EXT-S03 | Jurídico/encarregado: (1) textos e finalidades dos consentimentos com versão; (2) base legal por finalidade; (3) prazo de guarda por tabela (`evento_log`, `evento_uso`, `solicitacao*`, `job_execucao`); (4) procedimento do pedido de exclusão (anonimizar × apagar; o que fica por obrigação legal; prazo de resposta 15 dias); (5) quem opera a fila | Jurídico + encarregado | TI-S07..S10 | consentimentos atrás de flag com texto v0; retenção segue P-15 | P-15 + novo |
| EXT-S04 | Decisão institucional: IdP corporativo (Entra ID da APM) e tenant/app registration para o backoffice; política de MFA | TI/diretoria | §9 inteiro (DEC-S01) | padrões (TI-S13, TI-S31) nascem na área/hub | novo |
| EXT-S05 | `mcp_hub`: liberar `associado.situacao` por `contact_id` na conta `area-associado` e cota compatível com `/verificar` + job noturno (estimar: base ativa ÷ lote) | mcp_hub | TI-S14, TI-S15 | `/verificar` continua com cache de 24 h e "não confirmada" | P-04/P-41 |
| EXT-S06 | Decidir e implementar no hub a resolução CPF→`contact_id` para importação (ferramenta ou importação inteira no hub) | mcp_hub + Benefícios | TI-S17, §13.3 | nada de CSV entra na área | novo |
| EXT-S07 | Lista de parceiros com contrato e **host de destino** por benefício (para `parceiro.host`), requisito de "código pessoal"/SSO por parceiro | Benefícios | TI-S22, sql/009 | allowlist estática atual | P-10 (parcial) + novo |
| EXT-S08 | Contrato de campanha com Marketing/RD: nomes de parâmetros, catálogo de valores, códigos A01–A20, quem envia o quê ao RD e credencial OAuth do RD (fora da área) | Marketing + Encantada | TI-S21; §12 | catálogo provisório interno | novo |
| EXT-S09 | Credencial SMTP própria (já P-27) — necessária para confirmação de exclusão/cancelamento e protocolo | TI/infra | TI-S09, TI-S25 | stub (fora de produção) | P-27 |
| EXT-S10 | `.env` no Secrets Manager (P-36) antes de qualquer chave nova | operador | TI-S26 | — | P-36 |

### DIV — divergências spec × decisões/ADRs

| ID | Spec × decisão/ADR | Quem decide | Impacto | Recomendação |
|---|---|---|---|---|
| DIV-S01 | P01 descreve tela de CPF+senha "na Minha APM" × **sem login próprio** (OIDC, `/` → Login APM) | usuário (decidido) | P01 inteiro vive no `login_associado`; eventos `login` ficam no IdP e `login_ok/falha` na área; "continuar conectado" e "meus dados mudaram" são tarefas do IdP | manter; registrar na resposta à agência que P01 = Login APM e listar o backlog do IdP (TI-S02..S06) |
| DIV-S02 | P01 "a tela não confirma se um CPF existe antes de a data de nascimento conferir" × triagem atual do IdP revela "fora do CRM → filiação" (`login_triage.py`) | Sentinela + usuário | enumeração de CPF de associados (lista pública de médicos + CPF confirma vínculo) | adotar a spec (mais estrita): TI-S02 com nascimento antes de qualquer distinção de resposta |
| DIV-S03 | §13.3 CSV com `cpf` obrigatório × ADR-0014 (CPF nunca na área) | usuário (decidido) + Benefícios | importação não pode ser rota da área | resolver no hub (TI-S17); o layout pode manter `cpf` para o parceiro, mas o arquivo nunca toca a área |
| DIV-S04 | P13 "pedir exclusão" × ADR-0004 (DELETE nunca; trilhas append-only) | usuário + encarregado | exclusão = anonimização por coluna de estado; `evento_log`/`evento_uso` mantidos com HMAC (base legal: segurança/obrigação) | ADR nova (ADR-0018) formalizando "exclusão = anonimização + purga por retenção pelo operador" |
| DIV-S05 | §13.1 "API de consulta de associação já existe e está em uso" × fato: não há API JSON; portal `apm-parceiros` + `access:validate` sem consumidor | TI | expectativa da agência de integração pronta | corrigir a spec; DEC-S07 nomeia a API; fora da área (ADR-0009) |
| DIV-S06 | P07 validação pública mostra "categoria" × `/verificar` mostra só nome e situação (`publico.py:46`) | usuário + Sentinela | categoria (Acadêmico/Efetivo) é dado a mais numa página pública por token | manter sem categoria (minimização); se o negócio exigir, mostrar só "associado efetivo"/"acadêmico" sem CRM |
| DIV-S07 | Tipo 2 "envia os dados ao parceiro" e tipos 1/6 "acesso único" × ADR-0009 (nenhuma chamada a parceiro, sem SSO) | usuário (decidido) | tipo 2 = solicitação interna encaminhada pela APM; tipo 1/6 = link rastreado sem SSO | manter; "acesso único" só com ADR própria por parceiro (parceiro como RP do Login APM é a via segura) |
| DIV-S08 | §14 "API documentada (OpenAPI)" × OpenAPI só em development e 403 no edge | Sentinela | documentação sem superfície | OpenAPI como artefato versionado (TI-S27) |
| DIV-S09 | P15/§3.1 "notificações no topo" (sino) × ADR-0017 "sem sino" | Vitrine + agência | só visual; segurança indiferente | Vitrine decide; se houver sino, lista in-app (TI-S29), não push por padrão |
| DIV-S10 | §9 B02 "busca por CPF" × ADR-0014 | usuário (decidido) | backoffice não pode buscar por CPF **na área**; no hub pode (grants/PII) | backoffice fora da área (DEC-S01) ou busca por nome/número/`contact_id` |
| DIV-S11 | §12.1 "mensagens transacionais saem do próprio sistema" × área só envia código de e-mail (ADR-0015); e-mail/push de notificação fora de escopo (REQUISITOS L100-114) | usuário | A04/A06 por e-mail exigem o serviço de jobs enviar e-mail transacional | reabrir escopo só para transacional por e-mail (mesmo `email.py`), nunca marketing (fica no RD) |
| DIV-S12 | P07 "a validação consulta a situação no momento da leitura" × cache de 24 h renovado só pelo próprio associado | Sentinela + Integrador | carteirinha de cancelado válida por até 24 h; depois "não confirmada" | TI-S14/S15 (não é conflito de decisão; é lacuna que a spec expõe) |

### DEC — decisões pendentes

| ID | Decisão | Opções (prós / contras) | Recomendação |
|---|---|---|---|
| DEC-S01 | Onde vive o backoffice (B01–B13) e como autentica | (a) app separado com Entra ID: MFA e desligamento centralizados, perfis por grupo; custo de tenant/app novo. (b) dentro da área com o `login_associado`: zero infra nova; mistura staff e associado, IdP é de associados, superfície de `minha.apm.org.br` cresce, XSS vira backoffice. (c) portal do `mcp_hub`: usuários, grupos, grants, PII mode, cota e auditoria por titular já existem; falta 2FA e ele teria de escrever no MySQL da área (catálogo, textos) | **(a) ou (c), nunca (b).** Sugestão: visão 360, importações e consulta de associação em (c); catálogo/textos/segmentos em (a) ou numa área administrativa separada (`admin.minha.apm.org.br`) com Entra ID, lendo/escrevendo no schema da área com usuário MySQL **próprio** (grants separados de `apm_area`) |
| DEC-S02 | Exclusão de dados: anonimização × apagamento | anonimização por coluna (ADR-0004, trilhas íntegras, reversível só por restauração de backup — tratar backup na retenção) / apagamento físico pelo operador (quebra append-only, exige DELETE manual, risco operacional) | anonimização + purga por retenção (TI-S09/S10); no CRM o pedido vai à fila do cadastro via hub; `evento_log` fica (HMAC) |
| DEC-S03 | PWA: manifest só × SW restrito × offline | manifest só: instalável, zero risco de cache de PII. SW restrito: pré-requisito de push, exige disciplina (shell com nonce não cacheável, logout limpa). Offline: incompatível com `no-store` de dados pessoais e sessão | manifest só (TI-S18) no cutover; SW só se push for aprovado (DEC-S04) |
| DEC-S04 | Notificações: in-app × e-mail transacional × Web Push | in-app: só banco e API, sem egress. E-mail: `email.py` já existe, precisa P-27 e jobs. Web Push: SW + VAPID + egress a Google/Apple/Mozilla + assinatura é dado pessoal + consentimento por canal | F1/F2: in-app + e-mail transacional; Web Push só com consentimento, SW restrito e ADR |
| DEC-S05 | Ex-associado "entra e vê a página de retorno" | (a) página estática no IdP após triagem `INACTIVE` (sem sessão, sem dado pessoal, zero mudança na área). (b) sessão restrita na área com status ≠ Ativo e rota única `/retorno` (personalizável "o que perdeu", mas abre sessão para não-ativo: ADR-0016/gate do IdP mudam, hub precisa servir inativo) | (a) na F1; (b) só se o negócio exigir personalização, com ADR e `status` na sessão limitando **todas** as rotas |
| DEC-S06 | "Continuar conectado" | (a) cookie persistente no IdP com teto absoluto, `auth_time` original (área faz step-up por `idp_at`) / (b) não oferecer (sessão IdP 1 h; área 8 h/12 h + SSO silencioso já reduz atrito) | (a) com 30 d/90 d, revogação na troca de senha, `amr` honesto; área inalterada |
| DEC-S07 | API de consulta de associação para parceiros | (1) `access:validate` do IdP (pronto; contrato devolve `contact_id` e rótulos de status — mais do que o parceiro precisa). (2) hub `associado.situacao` com grupo `parceiros` (grants, PII mínimo, cota, auditoria por titular). (3) só portal `apm-parceiros` | (2), com resposta reduzida a `ativo: bool`; (1) continua para RPs internos |
| DEC-S08 | Revogação da carteirinha | (a) hub a cada leitura com cache curto + fallback (fiel à spec; custo na cota). (b) job noturno (barato; janela de até 24 h). (c) a+b | (c): cache 15 min + job noturno + `revogada_em` |
| DEC-S09 | Limite de taxa distribuído | manter por processo (2 workers) / tabela MySQL INSERT-only (consulta a cada chamada) / Redis (componente novo) | manter; operações sensíveis protegidas por unicidade no banco e step-up, não por contador |
| DEC-S10 | Links a parceiros | `<a>` direto com allowlist estática / redirecionador servidor `/ir/{slug}` com allowlist do seed | redirecionador (rastreio servidor-side, allowlist num só lugar, UI sem hosts) |
| DEC-S11 | Exportação "baixar meus dados" | síncrona JSON (simples, só dados da área) / job com link assinado de uso único (inclui PDF, mais custo) / inclui dados do CRM via hub (visão 360 é ferramenta sensível; exige grant) | síncrona com dados da área + texto "os dados do cadastro são fornecidos pela Central"; CRM via pedido formal ao encarregado |
| DEC-S12 | Fonte do indicador "taxa de sucesso de acesso" e do método de `acesso_primeiro` | IdP (tem senha, OTP, canal) / área (só callback) | IdP é a fonte; a área emite `acesso_primeiro` sem método; o painel cruza os dois por `sub_hash` |

---

## Riscos e ADRs candidatas

**Riscos (ordem de severidade)**
1. **Carteirinha de cancelado válida por até 24 h e depois "não confirmada" para sempre**
   (`carteirinha.py:83-90`): a spec expõe que a validação pública não consulta a situação. Risco
   de uso indevido em parceiro/evento. Mitigação: TI-S14/S15 (EXT-S05).
2. **Enumeração de CPF na triagem do IdP** (`login_triage.py`: fora do CRM → filiação): confirma
   vínculo associativo a quem tem o CPF. A spec pede nascimento antes. TI-S02 (EXT-S01).
3. **Exclusão/consentimento sem desenho** enquanto já há dado pessoal em produção (perfil em
   cache, foto, trilhas): a área está no ar sem canal para o titular exercer direitos (só a
   Central). TI-S07/S09 atrás de flag + ADR-0018.
4. **Backoffice em lugar errado** (opção b) seria o maior aumento de superfície do projeto.
   DEC-S01 antes de qualquer tela.
5. **P-40** vira real na Fase 3 (destinos dinâmicos). TI-S20 antes do cutover.
6. **Troca de celular sem step-up** no dia em que o IdP ligar OTP por celular (EXT-S02): mesma
   classe da ADR-0015. TI-S24 condiciona ao `WHATSAPP_ENABLED`.
7. **Service worker mal delimitado** cachearia HTML com nonce e respostas de `/api/` com dado
   pessoal em dispositivo compartilhado. DEC-S03/TI-S19.
8. **CSV com CPF** chegando por rota da área (ou por e-mail comum) quebraria ADR-0014 e §13.3.
   TI-S17 no hub.
9. **Cota do hub (120/min)** estourada por `/verificar` público após TI-S14 sem limite global →
   degrada o Perfil de todos. Limite global + cache no domínio.
10. **Dado de saúde em texto livre** de solicitação (terapia, plano de saúde). TI-S12 allowlist
    por tipo e `sigiloso`.

**ADRs candidatas**
- **ADR-0018 · Direitos do titular**: exclusão = anonimização por coluna de estado + purga por
  retenção pelo operador; pedido com protocolo, step-up e confirmação; sem DELETE (estende 0004).
- **ADR-0019 · Consentimento versionado por finalidade e canal**: tabelas append-only, versão
  do texto, origem; evento `consentimento`; reflexo no RD por job.
- **ADR-0020 · Backoffice — identidade, 2FA e autorização**: Entra ID/hub, perfis, usuário MySQL
  próprio, registro de acesso a dado pessoal, agregados k≥20.
- **ADR-0021 · Verificação pública em tempo quase real e revogação**: hub `associado.situacao`
  com cache curto, limite global, job noturno, `carteirinha_revogada_em`.
- **ADR-0022 · PWA**: manifest sem service worker; SW restrito só com push; política de cache
  (nunca HTML/`/api/`).
- **ADR-0023 · Encaminhamento rastreado a parceiros**: redirecionador servidor, allowlist do
  seed, sem SSO e sem envio de dados (estende 0009).
- **ADR-0024 · Parâmetros de campanha**: catálogo fechado de `utm_*`/gatilho, lido uma vez,
  nunca destino de navegação, registrado como propriedade de `evento_uso`.
- **ADR-0025 · Importação do plano B no hub**: CPF resolvido no hub; a área recebe só
  `contact_id` (estende 0014).
- **ADR-0026 · Notificações**: in-app + e-mail transacional; Web Push condicionado a
  consentimento, SW restrito e egress declarado.
- **ADR-0027 · Step-up generalizado**: dependência única; lista de operações que exigem
  `idp_at` recente (cancelamento, exclusão, exportação, canais, celular quando OTP por celular).

---

## Ordem sugerida

1. **Agora, sem dependência (P, área):** TI-S01 (`acesso_primeiro`), TI-S11 (propriedades sem
   PII), TI-S20 (P-40), TI-S21 (campanha com catálogo provisório), TI-S24 (step-up reutilizável),
   TI-S26 (runbook de chaves; P-36 antes), TI-S27 (OpenAPI artefato), TI-S18 (manifest),
   TI-S32 (homolog formalizada), TI-S05 (ACE-05 documentado).
2. **Decisões a tomar nesta rodada (sem código):** DEC-S01 (backoffice), DEC-S02 (exclusão),
   DEC-S05 (ex-associado), DEC-S07 (API de associação), DEC-S08 (revogação), DEC-S03/S04
   (PWA/push) — e pedir EXT-S01, EXT-S03, EXT-S04, EXT-S05 em paralelo.
3. **Fase 3 (solicitações) leva junto:** TI-S12 (allowlist por tipo), TI-S23 (limites e zonas),
   TI-S25 (cancelamento com step-up), TI-S13 (padrão de acesso a dado pessoal) e, com o serviço
   de jobs nascendo, TI-S15 (job de situação) e TI-S14 (verificação em tempo quase real) assim
   que EXT-S05 liberar `associado.situacao`.
4. **Fase 3b (LGPD, logo após):** TI-S07 (consentimentos atrás de flag `lgpd_consentimentos`),
   TI-S08 (exportação), TI-S09 (exclusão) + ADR-0018/0019 + TI-S10 (retenção com prazos).
5. **Fase 4 (benefícios):** TI-S22 (redirecionador + allowlist do seed, ADR-0023), TI-S21 ligado
   ao contrato real (EXT-S08).
6. **IdP (trilha paralela, Sentinela + login_associado):** TI-S02 (nascimento; EXT-S01) →
   TI-S06 (retorno do ex-associado) → TI-S04 (meus dados mudaram) → TI-S03 (continuar conectado).
7. **Cutover:** TI-S28 (CI de segurança), P-36, P-27, P-01, TI-S20 fechado.
8. **F2 (quando chegar):** TI-S29 (in-app) → TI-S19 (SW restrito) → TI-S30 (push), cada um com a
   ADR correspondente; TI-S16/S17 no hub conforme DEC-S07/EXT-S06; backoffice conforme DEC-S01
   com TI-S31.
