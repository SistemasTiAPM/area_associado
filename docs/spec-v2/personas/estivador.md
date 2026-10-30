# 📦 Estivador — prontidão de infra/DevOps para a spec v2 (29/10/2026)

Recorte: §14 RNF (ambientes, publicação, backup, alertas/monitoramento, disponibilidade), serviço de
jobs, canal do CSV plano B, hospedagem do backoffice, OpenAPI, PWA, vhost/WAF, P-01, P-19, P-25,
P-26, P-34, P-36, P-41, recursos do host, cutover × gate F0, dados anonimizados, logs imutáveis.
Só leitura: nada foi alterado em repositório ou host. Linhas citadas conferidas hoje.

Legenda de estado: ✅ pronto · 🟡 parcial · ⬜ não iniciado · ⛔ bloqueado por terceiro · ⚠️ risco ativo · 🔒 decisão fechada (não reabrir).

Decisões fechadas que condicionam tudo abaixo 🔒: Compose com `read_only`, tmpfs, `cap_drop ALL`,
`no-new-privileges`, sem `ports:` (docker-compose.yml:11-20); tudo atrás do `nginx_porteiro`;
host sem buildx (`DOCKER_BUILDKIT=0`); `.env` fora do git com cópia no Secrets Manager;
`APP_ENV=production` recusa stubs (`app/config.py`).

---

## Itens

### Ambientes (desenvolvimento, homologação anonimizada, produção)
- **Spec pede:** §14 "Ambientes. Desenvolvimento, homologação com dados anonimizados e produção" (spec:1204-1205); §13.2 exige do cadastro/cobrança "homologação com dados anonimizados" (spec:1154).
- **Existe hoje:** um único host EC2 `t4g.large` (`aws ec2 describe-instances`: i-02372f3925cf1e984, sa-east-1a) com 15 containers (`docker ps`), um único RDS `mysql-producao` (db.t4g.micro, MySQL 8.4.8, Single-AZ) compartilhado por todos os projetos; a área roda **`APP_ENV=staging`** no container `area_associado` com `HUB_MODE=real`, `SMTP_MODE=stub`, `AUTH_MODE=oidc` (`docker inspect`), público em `https://minha.apm.org.br` com `noindex` (area_associado.conf:55). Ou seja, "staging" **é** a produção em construção: mesmo RDS, mesmo IdP real, mesmo CRM real (leitura). Desenvolvimento = container local com `AUTH_MODE=stub`/`APP_ENV=development` na porta 127.0.0.1:18000 só para e2e (README.md:80-81) e MySQL 8.4 descartável para integração (PROVISIONAMENTO.md:51,70-71). Não há `docker-compose.override.yml`, `.env.hml` nem segundo schema.
- **Falta:** ambiente de homologação separado (compose project, schema, vhost restrito, hub/IdP sem dado real) e definição da origem dos dados anonimizados (ver `## Ambientes`).
- **Estado:** ⬜ (homolog) · 🟡 (dev) · 🟡 (prod: cutover pendente).
- **Fase spec / roteiro:** F0/F1 (gate 15.1 exige "fonte de autenticação comprovada", que já temos) · nosso: antes do backoffice (F1) e da escrita real no CRM (P-29).

### Publicação automatizada (CI/CD)
- **Spec pede:** "publicação automatizada" (spec:1205); "API documentada" e "nada só na cabeça de uma pessoa" (spec:1209-1210).
- **Existe hoje:** sem `.github/` (`ls -la .github` → inexistente); remote `git@github-area-associado:SistemasTiAPM/area_associado.git` com deploy key própria (CONCLUIDO.md:567-571). O portão de qualidade roda **no build da imagem**: `npm run check` (typecheck, ESLint CSP, Vitest) + build (Dockerfile:24); pytest fora da imagem por `docker run` (README.md:57-63); e2e Playwright e Lighthouse manuais (P-25, PENDENCIAS.md:96). Deploy = SSH no host + `DOCKER_BUILDKIT=0 docker compose build && docker compose up -d` (ACESSO-CONSTRUCAO.md:36-43); não há script de deploy, tag de imagem, nem rollback além de "reconstruir".
- **Falta:** CI para checks + e2e + Lighthouse (GitHub Actions), script de deploy idempotente com smoke (`db_check`, `check_oidc`, `csp_check`, `curl /health`) e rollback por tag de imagem; política de branch.
- **Estado:** ⬜ CI · 🟡 deploy (manual, documentado).
- **Fase:** F1 · roteiro: P-25 (P2) — sugiro subir para P1 antes de a Fase 3 entrar no ar.

### Cópia de segurança diária + teste de restauração
- **Spec pede:** "cópia de segurança diária com teste de restauração" (spec:1202-1203).
- **Existe hoje (confirmado com `aws rds describe-db-instances`, role `EC2-ReadOnly-Billing`):** `mysql-producao` com `BackupRetentionPeriod=7`, janela `06:11-06:41 UTC` (03:11 BRT), PITR `LatestRestorableTime=2026-10-29T17:49Z`, `DeletionProtection=true`, 30 GB `StorageEncrypted=true`, Single-AZ, `EnabledCloudwatchLogsExports=None`, `PerformanceInsightsEnabled=false`, `MonitoringInterval=0`. Snapshots automáticos diários presentes (`rds:mysql-producao-2026-10-25-06-16` … `-10-29-06-16`, todos `available`); **zero snapshots manuais**. AWS Backup: `AccessDenied` para a role (não há como confirmar plano). Nenhum runbook de restauração em `docs/` ou `/home/ubuntu/*.md` (grep "restaur|restore" em PENDENCIAS_AWS.md: só menções a AMI/EBS da t2.micro, linhas 242-267). `.env`: cópia manual no Secrets Manager `prod/area-associado/env` (PROVISIONAMENTO.md:125-130), **desatualizada desde 19/10** (P-36) e com 3 `.env.bak-*` no disco (`ls -la .env*`: `-20261019-dominio`, `-20261020-oidc`, `-202610211310`) — P-36 cita só dois. Volumes: a área não tem volume (tudo em RDS), logo backup = RDS + `.env` + git.
- **Falta:** runbook de restauração (snapshot → instância temporária → `db_check`/contagens → descarte) executado e datado; snapshot manual antes de cada `sql/NNN`; decisão de retenção (7 dias cobre só uma semana de erro humano silencioso); P-36.
- **Estado:** 🟡 backup (automático, sem teste) · ⬜ teste de restauração · ⚠️ P-36.
- **Fase:** F0/F1 · roteiro: novo (TI-E12) + P-36.

### Alertas de erro e monitoramento (ind. 14: sucesso de acesso, LCP, erros JS, disponibilidade)
- **Spec pede:** "Alertas de erro (há erros de JavaScript em produção no portal hoje)" (spec:1202); indicador 14 "Saúde técnica — diária — sucesso de acesso, LCP no celular, erros de JavaScript, disponibilidade" (spec:1024); LCP < 2,5 s e INP < 200 ms p75 (spec:1190).
- **Existe hoje:** `HEALTHCHECK` com `curl /health` 30 s (Dockerfile:69-70) + `restart: always` (docker-compose.yml:5); logs `json-file` 10m×3 (docker-compose.yml:27-31) — `docker logs` reinicia a cada recriação (login_associado/deploy/alertas.sh:5-6 registra a limitação); `request_id` em `X-Request-Id`, `evento_log` categoria `erro`, contador `uso_falhas` em `/db-health` (REQUISITOS RNF-17:881). **Nenhum monitor externo** desde a remoção do ALB em 14/09 (PENDENCIAS_AWS.md:93-94: "o health check do ALB é hoje o único monitor externo. Some junto… UptimeRobot ou similar"). Datadog: integração CloudWatch existente (`us5.datadoghq.com`, US$ ~10/mês) com a pergunta aberta "quem consome?" (PENDENCIAS_AWS.md:148-172). CloudWatch alarms/SNS: `AccessDenied` para a role (não confirmável). Resumo diário de segurança do IdP por e-mail existe e está **desativado** (crontab do host, linha comentada `#5 7 * * *`). Métricas de front (LCP/INP/erros JS): nada; `erro_exibido` em `evento_uso` cobre só toasts. Erros da área nas últimas 24 h: 0 (`docker logs --since 24h | grep -c`).
- **Falta:** uptime externo; alerta de 5xx/Traceback/`uso_falhas`/job com erro/certificado a vencer; RUM próprio (web-vitals + `window.onerror`) compatível com CSP `script-src 'self'` (regra 15) — Clarity (spec:1137) e qualquer script de terceiro ficam fora.
- **Estado:** 🟡 (saúde local) · ⬜ (alertas, uptime, RUM).
- **Fase:** F1 (indicador 14 é diário) · roteiro: novo (TI-E06, TI-E07, TI-E08).

### Disponibilidade
- **Spec pede:** "Disponibilidade e monitoramento" (spec:1202); consultas do cadastro < 1 s e "aviso de manutenção" (spec:1154).
- **Existe hoje:** 1 EC2, 1 RDS Single-AZ, 1 `nginx_porteiro` (imagem fixada `nginx:1.31.0`, nginx-proxy/docker-compose.yml:6); sem réplica, sem Multi-AZ; certificado de origem vencido (P-01, abaixo); swap 2 GiB (`free -m`); `verificar-pos-reboot.sh` como único checklist de retorno. Janela de manutenção do RDS `fri:02:27-02:57 UTC` (sexta 23:27 BRT) — sem aviso ao associado.
- **Falta:** SLO declarado (a spec não dá número), página/aviso de manutenção (vhost com `return 503` + página estática é suficiente), Multi-AZ é decisão de custo (RDS P4 em PENDENCIAS_AWS.md:211 trata de RI, não de HA).
- **Estado:** 🟡 · ⚠️ P-01.
- **Fase:** F1 · roteiro: novo (DEC-E09).

### Serviço de jobs `area-associado-jobs`
- **Spec pede (jobs implícitos):** outbox/espelho de solicitações e status (§8.5, spec:752-768); marcador `sem_retorno` quando o prazo do parceiro vence (A05, spec:1083); importação mensal do CSV até o dia 10 (§10.3, spec:862-875); fila de ligações diária às 8h (§10.5, spec:890-902); score diário (§11.4, spec:1026-1032); resumo mensal A08; carência vencida A03; eventos ao RD Station (§12.1-12.2); WordPress (§13.1, F2); A09 mensalidade vencida (depende da cobrança).
- **Existe hoje:** **nada executável.** `app/jobs/` não existe, compose tem um único serviço (docker-compose.yml:1-37), `Settings` não tem `WP_MODE` nem variável de job (`.env.example` sem `JOB|WP_|RD_`), `requirements.txt` sem agendador (14 pacotes, nenhum APScheduler/celery). Só desenho: RNF-19 "jobs em serviço separado `area-associado-jobs` (mesma imagem, 256M)" (REQUISITOS:883), `job_execucao` em `sql/012` (REQUISITOS:1012), outbox 1 min + sync 5 min + backoff 10 tentativas (REQUISITOS:1087-1090), ADR-0003:49-52,75 e ADR-0006:30-31,44,49,55,71-72,84 (WP a cada 15 min, `WP_DB_*` só no serviço jobs, `max_execution_time` 5 s, alerta após 3 falhas). `job_execucao` já está na allowlist de UPDATE do `db_check` (scripts/db_check.py:22-35, inventário) sem migração. Padrões dos irmãos: ver `## Serviço de jobs`.
- **Falta:** tudo (compose, `app/jobs`, locks, `job_execucao`, healthcheck, segregação de segredos, TZ, observabilidade, runbook `docs/JOBS.md` citado em REQUISITOS:1088 e inexistente).
- **Estado:** ⬜.
- **Fase:** F1 (outbox, sem_retorno, CSV, RD, fila 8h, carência) · F2 (WP, score, resumo) · roteiro: Fase 3 (próxima).

### Recepção do CSV plano B por "canal autenticado e protegido"
- **Spec pede:** CSV UTF-8 `;` um por parceiro/mês "enviado até o dia 10 por canal autenticado e protegido; nunca por e-mail comum" (spec:1159-1161); importação no backoffice B06 com validação, prévia por linha, histórico e devolução (spec:822); CPF na 1ª coluna (spec:1165-1167).
- **Existe hoje:** nenhum canal, nenhuma pasta, nenhum bucket. Vhost só aceita corpo grande em `/api/v1/perfil/foto` (6m, area_associado.conf:99-110); `/api/` limita a 64k (:88). Role da EC2 é somente leitura (sem `s3:PutObject` confirmável). `totalpass_uploads` mostra o padrão de volume de upload fora do document root (totalpass/docker-compose.yml). Regra 17/ADR-0014: **CPF não entra na área** — o CSV traz CPF obrigatório: a resolução CPF→`contact_id` tem de acontecer no hub ou numa zona de quarentena fora do schema da área.
- **Falta:** decisão de canal (DEC-E03), `location` com `client_max_body_size` e `limit_req` próprios, tmpfs com `size=` para o arquivo em trânsito, trilha `importacao`/`importacao_linha` (Atlas), ferramenta do hub para resolver CPF em lote (Integrador).
- **Estado:** ⬜ · conflito de regra (CPF) a resolver.
- **Fase:** F1 (B06) · roteiro: novo.

### Backoffice — onde vive, como autentica, 2FA
- **Spec pede:** "Todo acesso tem verificação em duas etapas e toda ação fica registrada" (spec:790); 8 perfis (spec:793-805); 13 módulos (spec:807-825); manual de operação (spec:1209).
- **Existe hoje:** fora de escopo em REQUISITOS (L112); IdP `login_associado` sem TOTP (inventário-vizinhos: "2FA: sem TOTP; step-up por código após 90 dias") e voltado a associados, não a funcionários; padrão de área administrativa restrita por IP no porteiro em `mcp_hub.conf:45-49,87-91` (`allow 186.224.200.94; allow 179.179.67.20; deny all` = rede da APM/VPN, "APM_ALLOWLIST_NAVEGADOR 20/10"); `feature_flag` só por SQL do operador (sql/003). Container atual tem `PidsLimit=<nil>` e tmpfs sem `size=` (docker inspect / docker-compose.yml:12-13) — relevante se o backoffice compartilhar o processo.
- **Falta:** decisão de hospedagem/autenticação (DEC-E02) com requisitos de infra por opção:
  - (a) **mesmo container, rotas `/admin/*`**: zero infra nova; vhost com `location ^~ /admin/` + allowlist IP + zona `limit_req` própria; 2FA tem de ser da aplicação (TOTP próprio) ou do IdP; risco: mesma superfície e mesmo pool de banco que o associado.
  - (b) **container separado, mesma imagem** (`python -m app.backoffice`, `expose 8001`, 256M): isola pool, limites de memória e falhas; vhost `admin.minha.apm.org.br` (DNS + `server` novo + certificado wildcard já cobre `*.apm.org.br`, mas **não** `*.minha.apm.org.br` — usar `minha-admin.apm.org.br` ou emitir Origin CA com o SAN); allowlist IP; `__Host-` cookie próprio.
  - (c) **(a) ou (b) + Cloudflare Access (Zero Trust)** na frente: 2FA sem código (Entra ID/Google com MFA), log de acesso na Cloudflare, política por e-mail/grupo; plano free até 50 usuários (a confirmar com a conta); exige validar o JWT `Cf-Access-Jwt-Assertion` no porteiro/app para não confiar só no DNS; não dispensa perfis na aplicação.
  - Em todas: trilha append-only de ações (`backoffice_evento`, só INSERT, regra 8), usuário de banco **próprio** (`apm_area_admin`) com UPDATE nas tabelas de catálogo/configuração, sem reutilizar `apm_area`.
- **Estado:** ⬜.
- **Fase:** F1 (B01-B06, B12, B13) · roteiro: sem fase — maior lacuna de infra da spec.

### OpenAPI interna ("API documentada")
- **Spec pede:** "API documentada (OpenAPI)" (spec:1209); contrato de dados do cadastro com "documentação da API" (spec:1154).
- **Existe hoje:** FastAPI gera o schema, mas `/docs`, `/redoc`, `/openapi.json` só com `APP_ENV=development` (app/main.py:140-142, `expose_openapi` em app/config.py:157) e `return 403` na borda (area_associado.conf:61-63). Nenhum `openapi.json` versionado. Contrato do hub documentado à mão em `docs/CONTRATO-HUB.md`.
- **Falta:** forma de publicar sem expor: (1) `scripts/export_openapi.py` rodado no build/CI, saída versionada em `docs/openapi.json` (diff revisável em PR); (2) flag `EXPOSE_OPENAPI` independente do `APP_ENV`, servindo `/docs` só pela rede Docker (borda continua 403); (3) portal interno (Redoc estático no backoffice sob allowlist). Recomendo (1)+(2).
- **Estado:** 🟡 (schema existe, não publicado).
- **Fase:** F1 · roteiro: novo (TI-E09), P.

### PWA (instalável)
- **Spec pede:** "Aplicativo web instalável (PWA), com ícone na tela inicial" (spec:1192-1193).
- **Existe hoje:** nada de PWA (inventário-código: "sem manifest, SW, public/"); `app/static/` tem `apple-touch-icon.png`, `favicon-192.png`, `favicon-32.png` (ls); CSP já tem `manifest-src 'self'` (app/main.py:103); cache: `/static/spa/assets` `immutable`, demais `/static` 86400, **resto `no-store`** (app/main.py:175-185; `/area` `no-store` em app/spa.py:5); SPA com `basename=/area`.
- **Falta (infra de servir):** `GET /manifest.webmanifest` e `GET /sw.js` pelo FastAPI (não pela SPA: o SW precisa de escopo `/area/` ou header `Service-Worker-Allowed: /area/`), ícones 192/512 maskable, `Cache-Control` adequado (manifest `public, max-age=3600`; `sw.js` `no-cache`), `location` no vhost (hoje cairiam em `/` zona `area_publico`, aceitável), teste e2e de `securitypolicyviolation`. Decisão de escopo do SW (DEC-E08): sem cache de `/api/` nem de telas com dado pessoal (RNF-21 proíbe `localStorage`; Cache API é análogo).
- **Estado:** ⬜.
- **Fase:** F1 ("instalável" é RNF, mas a spec não a amarra a fase) · roteiro: Vitrine + Maestro; infra P.

### Vhost para rotas novas e WAF/Cloudflare
- **Spec pede:** limite de tentativas, OWASP (spec:1194-1196); P14 FAQ/cancelamento; P04 página do benefício.
- **Existe hoje:** zonas `area_publico 10r/s`, `area_auth 5r/s`, `area_api 20r/s`, `area_static 30r/s`, `area_verificar 2r/s` (area_associado.conf:14-22) — todas por `$binary_remote_addr` com `real_ip` do Cloudflare (23 CIDRs em `_real_ip_cidrs.inc`); `/api/` 64k, foto 6m, `/verificar/` 1k; `$req_varredura` → 403 (`_00_seguranca.conf:21-53`); Cloudflare: regra `login-abuso 15 req/10 s` só no IdP (inventário-vizinhos) — nada para `minha.apm.org.br` (não confirmável daqui; registrar como a confirmar).
- **Falta:** P04/P14 são rotas **logadas** (`/area/*` + `/api/v1/*`): já cobertas por `area_api`; rotas **públicas** novas candidatas: `/manifest.webmanifest`, `/sw.js` (static-like), página de manutenção, backoffice (host próprio) e upload do CSV (`client_max_body_size` ~10m, zona própria). Regra 11: rota interna nova → `return 403`; pública → `limit_req`. Cloudflare: rate rule em `/auth/` e `/verificar/` como defesa em profundidade.
- **Estado:** ✅ (atual) · ⬜ (novas) · comentário desatualizado em area_associado.conf:50-52 ("quem entra é só quem tem o DEV_STUB_TOKEN").
- **Fase:** conforme cada rota.

### P-01 — certificado de origem (vencido)
- **Spec pede:** HTTPS (spec:1194).
- **Existe hoje:** `sites-enabled/certs/origin.pem`: `notAfter=Oct 10 13:58:41 2026 GMT`, `subject=CN=*.apm.org.br, O=TEMPORARIO-NAO-USAR-EM-PRODUCAO`, autoassinado (issuer = subject); `temp.pem` idêntico (`openssl x509`). Carregado por `_ssl.inc:24-25` em todos os vhosts 443. Os sites só respondem porque a zona Cloudflare **não** está em Full (strict) (P-01, PENDENCIAS.md:54) — ou seja, Cloudflare→origem aceita certificado inválido: MITM entre Cloudflare e a EC2 não é detectado. PENDENCIAS_AWS.md:103-105 cita o caminho `nginx-proxy/certs/` (real: `sites-enabled/certs/`, explicado em `_ssl.inc:16-21`).
- **Falta:** emitir Cloudflare Origin CA `*.apm.org.br` (15 anos), trocar `origin.pem/.key`, `nginx -t && reload`, zona → Full (strict), apagar `temp.pem`; checagem de validade no `verificar-pos-reboot.sh`.
- **Estado:** ⚠️ P0, 19 dias vencido.
- **Fase:** F0 (bloqueia cutover) · P-01.

### P-34 — catch-all na 443
- **Existe hoje:** sem `default_server` explícito; host sem vhost cai em `apm_parceiros.conf` (PENDENCIAS.md:58; `_00_seguranca.conf:4-7` explica a ordem alfabética). Risco a cada DNS novo (`hml.`, `admin.`).
- **Falta:** `_00_padrao.conf` com `listen 443 ssl default_server; server_name _; return 444;` mantendo o default da 80.
- **Estado:** ⬜ · pré-requisito de homolog/backoffice.
- **Fase:** F1 · P-34.

### P-36 — `.env` no Secrets Manager / backup do `.env`
- **Existe hoje:** `.env` 0600 de 21/10 13:13; três `.env.bak-*` 0600; segredo `prod/area-associado/env` não confirmável (`ListSecrets` → `AccessDenied`). Chaves cuja perda é irreversível: `SESSION_ENC_KEYS` (derruba sessões), `CARTEIRINHA_HMAC_KEY` (invalida todos os QRs já impressos/compartilhados), `LOG_HASH_KEY` (descorrelaciona `evento_log`).
- **Falta:** replicar; apagar `.bak`; rotina de conferência (hash do `.env` × segredo) — exige `secretsmanager:GetSecretValue` na role ou execução pelo operador.
- **Estado:** ⚠️ atrasada desde 19/10.
- **Fase:** — · P-36.

### P-26 — buildx
- **Existe hoje:** build clássico (`DOCKER_BUILDKIT=0`) funciona com o multi-stage (Dockerfile:7,31); build cache 336 MB, 2,8 GB de imagens recuperáveis (`docker system df`). CI em GitHub Actions teria buildx nativo, o que torna P-26 menos urgente.
- **Estado:** 🔒 (decisão do operador) · ⬜.

### P-19 — pós-reboot
- **Existe hoje:** `verificar-pos-reboot.sh:16` espera ≥12 containers (há 15); lista em :19 não tem `area_associado`, `mcp_hub`, `appapm-cron` nem o futuro `area-associado-jobs`; sites em :24 não têm `minha` nem `mcp`.
- **Falta:** incluir os 3 (4) containers, os 2 hosts, validade do `origin.pem`, `docker compose ps` healthy e `/health` por dentro da rede.
- **Estado:** ⬜ (P, pode hoje).

### Recursos do host (cabe web 512M + jobs 256M?)
- **Medido:** `free -m`: 7801 MiB total, 4567 usados, 3233 disponíveis, swap 2047 (0 usado); `nproc`=2; disco `/` 77G, 23G usados (30%); soma dos limites de memória dos 15 containers = **4924 MiB** (docker inspect); área usa 139,5 MiB/512 (`docker stats`), hub 274/768, IdP 164/512. Load 0,11.
- **Conclusão:** jobs 256M cabe (limites 5180/7801); homolog completa (+512+256) ainda cabe (~5950) mas deixa ~1,8 GiB de folga real contando page cache; backoffice separado (+256) idem. CPU: 2 vCPU para 15 containers — jobs de varredura (WP, score) devem rodar de madrugada e com `nice`/intervalo.
- **Banco:** pool `DB_POOL_SIZE=5 + DB_MAX_OVERFLOW=10` por worker × 2 = até 30 conexões da área; RDS db.t4g.micro (1 GiB) tem `max_connections` padrão ≈ 85 (fórmula AWS; **a confirmar** com `SHOW VARIABLES`), compartilhado com IdP, hub, totalpass, parceiros, appapm. Jobs e homolog devem nascer com pool pequeno (2+2).
- **Estado:** ✅ memória/disco · ⚠️ conexões do RDS a confirmar.

### Escalabilidade dos limites em memória por processo
- **Existe hoje:** `app/limites.py` por processo; 2 workers → limite efetivo dobra (inventário-código); token do hub em memória por worker (1 emissão por worker por deploy, P-41). Jobs em container separado não compartilham nada disso — bom para isolamento, mas limites "por associado" (10/h contato, 5/h foto) continuam por worker.
- **Falta:** se virar problema de precisão (fila de ligações, A05 não dependem disso), mover para MySQL (`GET_LOCK`/tabela) — não para Redis (serviço novo, 🔒 sem porta, memória). Hoje é aceitável e documentado.
- **Estado:** 🟡 documentado.

### Cutover (`docs/CUTOVER.md`) × gate F0 da spec
- **Spec (15.1):** F1 começa com base conciliada, autenticação/situação comprovada, catálogo com carências, contratos de dados, destino dos eventos/LGPD.
- **Nosso cutover:** `APP_ENV=production` + hub/SMTP reais + `noindex` fora (CUTOVER.md:27-41); pré-requisitos P-01 (vencido), P-27 (SMTP), P-29 (escrita). Rollback = `deny all` no vhost (CUTOVER.md:62-66).
- **Divergência:** o cutover técnico é **menor** que o gate F0: ele vira a produção da Fase 2 (perfil/carteirinha) sem catálogo, carências, contratos de parceiro nem destino de eventos. Isso é compatível desde que o que vai ao ar seja só P01/P07/P13 — exatamente o que a spec protege ("P07 só se passar no gate técnico", 15.2). Falta no CUTOVER.md: snapshot manual do RDS antes, replicar `.env`, monitor externo ligado, `verificar-pos-reboot` atualizado, aviso de manutenção, critério de "go" por indicador 14.
- **Estado:** 🟡.

### Testes com dados anonimizados (homologação) — origem
- **Fato:** o schema `area_associado` guarda pouco PII (`associado_perfil`: nome, e-mail, telefones, endereço JSON, miniatura; `email_verificacao`: só HMACs; `evento_log`/`evento_uso`: HMAC/`contact_id`). O PII de verdade está no CRM/IdP e chega pelo hub. "Anonimizar" aqui = (1) não copiar `associado_perfil`/`email_verificacao`; (2) hub em `stub` (dados determinísticos, `hub_stub.py`) ou conta do hub apontando para sandbox do Dataverse (EXT, CRM admin); (3) IdP: `AUTH_MODE=stub` é permitido fora de `production` e já usado no e2e — ou contatos de teste (P-37). Totalpass tem o precedente de base de ensaio (`apm_totalpass_ensaio.sql`, `apm_totalpass_corte_SIMULADO.sql` em `/home/ubuntu`).
- **Estado:** ⬜ · depende de DEC-E06.

### Logs de auditoria imutáveis (§14) × retenção
- **Spec:** "Log imutável de solicitações e de ações no backoffice" (spec:1198); "Prazo de guarda de logs de solicitação e auditoria definido pelo jurídico" (spec:1058); log de status com conteúdo enviado (spec:767, 938).
- **Existe hoje:** imutabilidade por privilégio: `apm_area` sem UPDATE/DELETE no schema, `evento_log`/`evento_uso` só INSERT, CHECK contra segredo/CPF (sql/002, sql/004); `db_check` falha com DELETE em qualquer tabela; prova de append-only no PROVISIONAMENTO.md:88-103. Logs de container 30 MB rotativos, perdidos na recriação. Retenção/purga: P-15 (operador, sem DELETE pela app), sem prazo.
- **Falta:** prazo do jurídico (EXT); purga pelo operador com snapshot prévio; backoffice com trilha própria só INSERT; opcional: exportar `evento_log` mensal para S3 Object Lock (imutabilidade fora do RDS — exige IAM).
- **Estado:** ✅ imutabilidade · ⬜ retenção.

### P-41 — volume ao hub (jobs mudam a conta)
- **Fato:** provisório 120/min e 5.000 PII/dia (PENDENCIAS.md:99). Jobs novos (`atualizar_perfis` diário, outbox 1 min, sync 5 min, CSV em lote resolvendo CPF) mudam o perfil de consumo: um `atualizar_perfis` sobre N associados ativos estoura 5.000/dia se N > 5.000. A resposta à P-41 tem de incluir os jobs e pedir conta/cota separada para eles (ou `client_id` próprio `area-associado-jobs`, o que também separa o token em memória e a allowlist de IP).
- **Estado:** 🟡 · ⛔ negócio.

---

## Serviço de jobs — desenho de prontidão

**Como os irmãos resolvem (fatos):**
| Projeto | Mecanismo | Lock | Efeito controlado | Saúde | Onde ficam segredos de job |
|---|---|---|---|---|---|
| totalpass | `crond -f` na imagem (`FROM app AS cron`, `apk add flock`), crontab copiado, `cap_add SETUID,SETGID` (totalpass/Dockerfile; docker-compose.yml serviço `cron`, profile `jobs`, 256M, `TZ=America/Sao_Paulo`) | `flock -n -E 75 /tmp/cron-<job>.lock` (executar.sh:93-102) | `CRON_APLICAR=1` injeta `--aplicar/--confirmar` por job (executar.sh:54-83); job sem dry-run bloqueado (:44-52) | `pgrep crond` | `.env.erp` só no cron (`env_file: path/required: false`) |
| appapm | loop `sh` com `sleep` + `trap TERM` (docker/cron-entrypoint.sh:29-40), profile `cron`, 128M | claim por `rowCount()` no banco | — | heartbeat em `/tmp`, unhealthy após 10 min (compose :161-166); watchdog no crontab do host a cada 5 min | — |
| login_associado / form_filiacao | crontab do **host** com `docker compose exec`/`docker exec` (crontab -l) | — | — | logs em `/home/ubuntu/<proj>/logs/*.log` | `.env` do serviço web |
| mcp_hub | sem jobs | — | — | — | — |

**Proposta para a área (sem código):**
- **Compose:** serviço `area-associado-jobs` (`container_name: area_associado_jobs`), `build: .` (mesma imagem), `command: ["python", "-m", "app.jobs"]`, **sem `expose`**, `env_file: .env` + `{path: .env.jobs, required: false}` (`WP_DB_*`, `RD_*`, credencial de job do hub), `read_only`, `tmpfs /tmp:size=64m`, `cap_drop ALL`, `no-new-privileges`, 256M, `pids_limit`, `logging json-file 10m×3`, `TZ=America/Sao_Paulo` (fila das 8h e horário 8h-20h são locais; o compose atual não define TZ), `restart: always`, `profiles: ["jobs"]` enquanto não houver job com efeito externo liberado (padrão totalpass/appapm), `JOBS_APLICAR=0|1` (análogo a `CRON_APLICAR`) para dry-run de tudo que escreve em CRM/RD. Rede: `rede_publica` (alcança `mcp_hub`); saída NAT para Locaweb 3306 e API do RD (confirmar SG de egress).
- **Agendador:** loop Python in-process (uma thread por job com intervalo, ou um loop único com "próxima execução"), sem crond (evita `cap_add SETUID/SETGID` e pacote `cron` no slim) e sem host-cron (perde reprodutibilidade e logs no `docker logs`). Tratamento de SIGTERM, falha de um job não derruba o loop, intervalo fixo com jitter.
- **Locks:** `SELECT GET_LOCK('area_job_<nome>', 0)` no MySQL por execução (funciona com `SELECT`, sobrevive a dois containers por engano, libera na queda de conexão) **e** linha em `job_execucao` (`status running/ok/erro`, `inicio`, `fim`, `itens`, `erro`) — UPDATE já previsto na allowlist. Jobs de outbox usam claim condicional (`UPDATE … WHERE crm_sync='pendente' AND crm_proxima_tentativa <= NOW()`), um vencedor.
- **Observabilidade:** heartbeat em `/tmp/jobs.heartbeat` tocado a cada ciclo + `HEALTHCHECK` por idade (padrão appapm) — importante porque `python -m app.jobs` sem porta não tem `/health`; `/db-health` do web passa a expor a última execução ok de cada job (lendo `job_execucao`); falha 3× seguidas → `evento_log` severidade `erro` (ADR-0006:71-72) → alerta (TI-E07); `verificar-pos-reboot.sh` com o container.
- **Recursos:** 256M é suficiente (sem Pillow no caminho de job, CSV de milhares de linhas em streaming, WP em lotes); pool de banco pequeno (`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=2`); limitar concorrência a 1 job por vez na primeira versão (2 vCPU compartilhadas).
- **Segurança:** o serviço jobs recebe `ferramentas:escrever` **antes** do web? Não: a escrita do outbox também passa pela P-29; até lá, jobs sobem só com WP (stub) e marcação de `sem_retorno`. Conta do hub separada para jobs (P-41).

**Tabela de jobs exigidos pela spec:**
| Job | Periodicidade | Recursos / efeito | Dependência | Fase spec |
|---|---|---|---|---|
| `espelhar_solicitacoes` (outbox → CRM) | 1 min | escreve no CRM via hub; backoff 1…60 min, 10 tentativas | sql/008, P-06, P-29, `ferramentas:escrever` | F1 |
| `sincronizar_solicitacoes` (status de volta) | 5 min | lê hub (`solicitacao.alteracoes_consultar`, a criar) | P-06, hub | F1 |
| `marcar_sem_retorno` (A05) | 15 min | UPDATE marcador + `solicitacao_evento` + alerta interno | prazo por parceiro (B04), SMTP/RD para o aviso | F1 |
| `importar_csv` (§10.3) | sob demanda (acionado pelo B06) ou varredura de fila | lê arquivo de quarentena; resolve CPF→contact_id no hub; grava uso/valor | DEC-E03, B06, hub (lote), Atlas (tabelas) | F1 |
| `enviar_rd_station` (outbox RD, A01-A06, A09, A16-A18) | 1-5 min | HTTPS saída; credencial OAuth2 RD (refresh token) | credencial RD (EXT-E13), consentimento (§11.6) | F1 |
| `carencia_vencida` (A03) | diário 06:00 | lê catálogo + `data_filiacao`; gera aviso/evento | catálogo com carências (F0), RD | F1 |
| `gerar_fila_ligacoes` (§10.5) | diário 08:00 BRT | INSERT fila; lê régua, score (F2) | backoffice B05, TZ | F1 |
| `atualizar_perfis` | diário madrugada | hub `perfil_consultar` em lote → **cota PII** | P-41 (cota de jobs) | já previsto (REQUISITOS:915) |
| `sincronizar_portal` (WP) | 15 min | MySQL Locaweb RO, `max_execution_time` 5 s, cache local | P-07, P-21, `WP_MODE` | F2 (nossa 5) |
| `calcular_score` (§11.4) | diário | varre `evento_uso` + financeiro; UPDATE em tabela de score | cobrança (§13.1), F2 | F2 |
| `resumo_mensal` (A08) | mensal dia 1 | agrega meu valor; envia ao RD | A08, meu valor | F2 (F1 só proteção incluída) |
| `mensalidade_vencida` (A09) | diário | depende de evento/consulta da cobrança | novo sistema de cobrança (§13.1) | F1 condicional |
| expurgo/retenção (P-15) | operador | DELETE **nunca** pela app (🔒 regra 14) | prazo do jurídico | — |

---

## Ambientes

| | Desenvolvimento | Homologação | Produção |
|---|---|---|---|
| **Existe** | Container local (`APP_ENV=development`, `AUTH_MODE=stub`, 127.0.0.1:18000) para e2e (README.md:80-81); MySQL 8.4 descartável para `pytest -m mysql`; `HUB_MODE=stub`, `SMTP_MODE=stub`. Sem ambiente compartilhado. | **Não existe.** O que se chama "staging" é o container público `area_associado` (`APP_ENV=staging`) no mesmo host, mesmo RDS, IdP e CRM reais (leitura). | O mesmo container, após `APP_ENV=production` (CUTOVER.md). |
| **Falta** | `docker-compose.override.yml.example` documentado; `make`/script único para subir dev; e2e no CI. | Compose project separado (`-p area_hml`), `.env.hml`, schema `area_associado_hml` + usuário `apm_area_hml` (migrações iguais), vhost `hml-minha.apm.org.br` (wildcard cobre) com allowlist IP (padrão mcp_hub.conf:45-49) e/ou Cloudflare Access, `noindex`, hub `stub` ou conta de sandbox, IdP `stub` (permitido fora de production) ou contatos de teste (P-37), catch-all P-34 antes do DNS. | P-01, P-27, P-29, P-36, monitor, snapshot pré-cutover, `verificar-pos-reboot`. |
| **Dados anonimizados (origem)** | `hub_stub.py` determinístico; sem PII. | Schema vazio + migrações (sem copiar `associado_perfil`/`email_verificacao`); perfis via `hub_stub` **ou** Dataverse sandbox pelo hub (EXT-E12); `evento_log`/`evento_uso` já são pseudônimos (HMAC/`contact_id`). Nunca restaurar snapshot de produção no mesmo RDS para "anonimizar depois". | Reais. |
| **Custo / risco** | zero; risco: Node do host antigo (README.md:71) → tudo em container. | +~770 MiB de limites (cabe: 4924 → ~5700 de 7801); +conexões no RDS t4g.micro compartilhado (⚠️ a confirmar `max_connections`); RDS separado por snapshot = db.t4g.micro ~US$ 15-20/mês (evita contaminar `mysql-producao` e permite ensaiar restore ao mesmo tempo). Risco: homolog pública sem allowlist vira segundo alvo. | Single-AZ, 1 host; cert vencido. |

---

## Propostas

### TI (`TI-E*`)
| ID | Tarefa | Camada | Repo | Tam. | Pré-requisito | Hoje? |
|---|---|---|---|---|---|---|
| TI-E01 | Serviço `area-associado-jobs` no compose (mesma imagem, `python -m app.jobs`, sem expose, 256M, `read_only`, tmpfs `size=`, `cap_drop ALL`, `pids_limit`, `TZ`, `env_file .env.jobs required:false`, profile `jobs`, healthcheck por heartbeat, `JOBS_APLICAR`) | container | area_associado | M | ADR dos jobs (DEC-E01); `app/jobs` do Integrador; `sql/012` do Atlas | esqueleto sim (profile desligado) |
| TI-E02 | `docs/JOBS.md` (runbook: ligar/desligar, dry-run, reprocessar outbox, ler `job_execucao`) — citado em REQUISITOS:1088 e inexistente | docs | area_associado | P | TI-E01 | sim |
| TI-E03 | `verificar-pos-reboot.sh`: + `area_associado`, `mcp_hub`, `appapm-cron`, `area_associado_jobs`; sites `minha`, `mcp`; validade do `origin.pem`; `docker compose ps` healthy | host | infra | P | — (P-19) | sim |
| TI-E04 | Catch-all `_00_padrao.conf` (`listen 443 ssl default_server; server_name _; return 444;`), mantendo default da 80 | vhost | nginx-proxy | P | aprovação do operador (mexe em todos) | sim |
| TI-E05 | `scripts/deploy.sh`: `git pull --ff-only` + `DOCKER_BUILDKIT=0 build` com tag `area:<sha>` + `up -d` + esperar healthy + `db_check`/`check_oidc`/`csp_check` + `curl /health` + rollback para tag anterior | deploy | area_associado | P/M | — | sim |
| TI-E06 | Monitor externo de uptime nos 7 hosts (`/health`), alerta por e-mail/WhatsApp da conta do operador | monitoramento | infra | P | conta (EXT-E06) | sim |
| TI-E07 | Alerta diário/horário à la `login_associado/deploy/alertas.sh`: 5xx do porteiro para `minha.`, Tracebacks, `uso_falhas` de `/db-health`, `job_execucao` com erro, 429 anormais, cert a <30 dias, `.env` ≠ Secrets | monitoramento | area_associado + infra | M | SMTP (P-27) ou webhook | parcial (script sem envio) |
| TI-E08 | RUM próprio: `web-vitals` (LCP/INP/CLS) + `window.onerror`/`unhandledrejection` → `POST /api/v1/uso` com ações `vitais_web`/`erro_js` (catálogo fechado, sem stack com PII); painel em `/db-health` ou SQL | front + API | area_associado | M | Vitrine/Maestro/Atlas (catálogo) | sim |
| TI-E09 | `scripts/export_openapi.py` → `docs/openapi.json` versionado (gerado no CI/release) + `EXPOSE_OPENAPI` separado do `APP_ENV` (borda continua 403) | API/docs | area_associado | P | — | sim |
| TI-E10 | GitHub Actions: `check` (npm check, pytest, build com buildx), e2e Playwright com container stub + MySQL service, Lighthouse CI (orçamentos LCP/INP), `npm audit`; sem deploy automático (ver DEC-E07) | CI | area_associado | M | Actions na org (EXT-E07) | sim (arquivo); roda após EXT |
| TI-E11 | Hardening pendente no compose: `pids_limit`, `tmpfs /tmp:size=64m` (hoje sem `size`), `TZ` | container | area_associado | P | — | sim |
| TI-E12 | Runbook de backup/restore: política atual (7 d, 06:11 UTC, PITR), snapshot manual antes de cada `sql/NNN` e do cutover, restauração trimestral em instância temporária (`db_check`, contagens, `schema_migrations`), descarte; evidência em CONCLUIDO | docs/infra | area_associado + infra | M | IAM para executar (EXT-E02) | doc sim; ensaio após EXT |
| TI-E13 | P-36: replicar `.env`; apagar os 3 `.env.bak-*`; `scripts/env_check.sh` (hash do `.env` × segredo) | segredos | infra | P | `GetSecretValue` ou operador | operador hoje |
| TI-E14 | P-01: instalar Origin CA em `sites-enabled/certs/`, `nginx -t && reload`, remover `temp.pem`, zona Full (strict); corrigir caminho em PENDENCIAS_AWS.md | TLS | nginx-proxy | P | certificado (EXT-E01) | após EXT (mesmo dia) |
| TI-E15 | Vhost: `location`s para `/manifest.webmanifest`, `/sw.js` (zona static, `no-cache`), página de manutenção (`maintenance.html` + `return 503` chaveado por arquivo), zona/`client_max_body_size` para upload de CSV, `server` do backoffice | vhost | nginx-proxy | P/M | rotas existirem; DEC-E02/E03 | parcial |
| TI-E16 | PWA (infra de servir): rotas FastAPI `manifest`/`sw.js`/ícones 192-512 maskable, `Service-Worker-Allowed`, cache headers, teste e2e de CSP | backend/front | area_associado | M | DEC-E08 | após DEC |
| TI-E17 | Backoffice (infra): conforme DEC-E02 — container `area-associado-admin` (mesma imagem, 256M) ou rotas `/admin`; vhost com allowlist IP; Cloudflare Access; usuário de banco `apm_area_admin`; trilha só INSERT | container/vhost/db | area_associado + nginx-proxy | G | DEC-E02, EXT-E08, Atlas | após DEC |
| TI-E18 | Canal do CSV: conforme DEC-E03 — tmpfs de quarentena com `size=`, `location` de upload, (se S3) bucket privado SSE + lifecycle + role com `PutObject` só no prefixo | infra | area_associado + infra | M | DEC-E03, EXT-E18 | após DEC |
| TI-E19 | Homologação: `docker-compose.hml.yml` (`-p area_hml`), `.env.hml`, schema `area_associado_hml`, vhost `hml-minha.apm.org.br` restrito, hub stub/sandbox | ambientes | area_associado + nginx-proxy | G | TI-E04, DEC-E06, EXT-E12 | após DEC |
| TI-E20 | Logs: avaliar `awslogs` (CloudWatch Logs, retenção 90 d) ou `journald` para não perder `docker logs` na recriação; manter `json-file` como padrão 🔒 | logs | infra | P | IAM `logs:PutLogEvents` (EXT-E02) | após EXT |
| TI-E21 | CUTOVER.md: adicionar snapshot manual, `.env` replicado, monitor ligado, pós-reboot atualizado, critério de go por indicador 14, aviso de manutenção; atualizar comentário desatualizado em area_associado.conf:50-52 | docs | area_associado + nginx-proxy | P | — | sim |
| TI-E22 | Resposta à P-41 incluindo os jobs: pedir `client_id` separado `area-associado-jobs` com cota própria | hub | mcp_hub (provisão) | P | estimativa de N associados ativos | sim |

### EXT (`EXT-E*`)
| ID | O que exatamente | De quem | Destrava | Enquanto isso | Ref. |
|---|---|---|---|---|---|
| EXT-E01 | Emitir Cloudflare Origin CA `*.apm.org.br` (RSA 2048, 15 anos) e enviar `.pem/.key` ao operador; passar a zona para Full (strict) após instalar | operador/Cloudflare | TI-E14, cutover, segurança de todos os 7 sites | nada (risco aceito desde 10/10) | P-01 |
| EXT-E02 | IAM: ampliar a role `EC2-ReadOnly-Billing` (ou criar perfil humano) com `rds:CreateDBSnapshot`, `rds:RestoreDBInstanceFromDBSnapshot` (restore em instância temporária), `secretsmanager:GetSecretValue` em `prod/area-associado/env`, `cloudwatch:DescribeAlarms`, opcional `logs:*` para awslogs | AWS admin | TI-E12, TI-E13, TI-E20 | operador faz pelo console | novo |
| EXT-E03 | Replicar o `.env` de 21/10 no Secrets Manager; apagar `.env.bak-*` | operador | recuperação do servidor | — | P-36 |
| EXT-E04 | Executar um teste de restauração do RDS (snapshot → instância temporária → validação → delete) e registrar data/evidência | operador/AWS | §14 "teste de restauração" | TI-E12 (doc) | novo |
| EXT-E05 | Decidir retenção de backup do RDS (7 → 14 ou 35 dias) e habilitar export de logs (`error`, `slowquery`) + Performance Insights (free tier) | AWS admin | diagnóstico de incidentes; indicador 14 | — | novo |
| EXT-E06 | Conta num monitor externo (UptimeRobot/Better Stack, free) com contatos de alerta | operador | TI-E06 | pós-reboot manual | PENDENCIAS_AWS.md:93-94 |
| EXT-E07 | GitHub Actions habilitado na org `SistemasTiAPM` (minutos), branch protection em `main` | GitHub admin | TI-E10 | checks no build local | P-25 |
| EXT-E08 | Cloudflare Access (Zero Trust) com IdP corporativo (Entra ID/Google) e MFA para `admin`/`hml` | Cloudflare admin | backoffice 2FA (DEC-E02), homolog | allowlist IP no porteiro | novo |
| EXT-E09 | Regra de rate limit da Cloudflare para `minha.apm.org.br` (`/auth/*`, `/verificar/*`) como o `login-abuso` do IdP; confirmar WAF managed rules ligadas | Cloudflare admin | defesa em profundidade | `limit_req` do porteiro | novo |
| EXT-E10 | Decidir o destino do Datadog (usar para RDS/EC2 + containers, ou cancelar) | operador | TI-E07 (canal de alerta) | — | PENDENCIAS_AWS P2 |
| EXT-E11 | `apt install docker-buildx` (ou manter `DOCKER_BUILDKIT=0`) | operador | build moderno; irrelevante se CI usa buildx | `DOCKER_BUILDKIT=0` | P-26 |
| EXT-E12 | Sandbox do Dataverse (ou conjunto de contatos de teste marcados) acessível por uma conta do hub para homologação | CRM admin | TI-E19 com dados anonimizados | `HUB_MODE=stub` | novo (relacionado a P-37) |
| EXT-E13 | Credencial OAuth2 do RD Station para a área (ou reuso do app do totalpass, decisão de Marketing) | Marketing/RD | job `enviar_rd_station` | outbox local sem envio | novo |
| EXT-E14 | Credencial SMTP própria com SPF/DKIM | TI/infra | SMTP real, alertas por e-mail (TI-E07), A04/A06 | stub | P-27 |
| EXT-E15 | Usuário RO na Locaweb + TLS + restrição de IP | infra/Planeta W | `sincronizar_portal` | `WP_MODE=stub` | P-07 |
| EXT-E16 | Confirmar egress do SG `ec2-producao-sg` para Locaweb 3306 e API do RD (443) a partir do container de jobs | AWS admin | jobs WP/RD | — | novo |
| EXT-E17 | Prazo de guarda de `evento_log`, `evento_uso`, `solicitacao_evento` e trilha do backoffice | jurídico/encarregado | P-15 (purga pelo operador) | sem purga | P-15 |
| EXT-E18 | Bucket S3 privado + role com `PutObject` restrito (só se DEC-E03 escolher S3) | AWS admin | TI-E18 | upload pelo backoffice | novo |
| EXT-E19 | Lista de IPs/VPN da APM para allowlist de `admin`/`hml` (hoje 2 IPs em mcp_hub.conf:46-47) | operador | TI-E17, TI-E19 | — | novo |

### DIV (`DIV-E*`) — divergências spec × realidade/documentos
| ID | Divergência | Evidência |
|---|---|---|
| DIV-E01 | Spec exige dev/homolog/prod; existe um host, um RDS e o "staging" é a produção pública em construção | `docker inspect` (APP_ENV=staging), ACESSO-CONSTRUCAO.md:6-9 |
| DIV-E02 | "Publicação automatizada" × deploy manual por SSH sem CI, tag ou rollback | ACESSO-CONSTRUCAO.md:36-43; sem `.github/` |
| DIV-E03 | "Backup diário com teste de restauração" × RDS automático 7 d sem teste documentado; `.env` desatualizado no cofre (P-36) e 3 `.bak` no disco | `aws rds describe-db-instances`; `ls -la .env*` |
| DIV-E04 | "Alertas de erro" × só healthcheck/restart; nenhum monitor externo desde 14/09 | PENDENCIAS_AWS.md:93-94 |
| DIV-E05 | Indicador 14 (LCP/erros JS) e "Clarity já instalado no portal" × CSP `script-src 'self'` sem terceiros (regra 15, ADR-0013) → só RUM próprio | app/main.py:95-106 |
| DIV-E06 | PWA × `no-store` em tudo fora de `/static` + RNF-21 (nada do associado no dispositivo): SW não pode cachear `/api/` nem carteirinha | app/main.py:185; REQUISITOS:885 |
| DIV-E07 | "API documentada (OpenAPI)" × `/docs` só em development e 403 na borda | app/main.py:140-142; area_associado.conf:61-63 |
| DIV-E08 | CSV "por canal autenticado, nunca e-mail" × nenhum canal; e o CSV traz CPF, proibido na área (regra 17/ADR-0014) | spec:1159-1167 |
| DIV-E09 | "2FA no backoffice" × IdP sem TOTP e feito para associados | inventário-vizinhos (login_associado) |
| DIV-E10 | RNF-19 diz web 400M × compose 512M desde `6a20cbf` | REQUISITOS:883; docker-compose.yml:26 |
| DIV-E11 | CLAUDE.md/REQUISITOS citam `area-associado-jobs`, `WP_MODE`, `docs/JOBS.md` como existentes/alvo × nada existe no código | inventário-código; `.env.example` |
| DIV-E12 | Regra 6 do CLAUDE.md: "`WP_MODE=stub` proibido em produção" sem validador em `Settings` | app/config.py (sem `WP_MODE`) |
| DIV-E13 | CUTOVER.md:8-9 fala em "expira 10/10" como futuro; vhost diz "quem entra é só quem tem o DEV_STUB_TOKEN" | CUTOVER.md; area_associado.conf:50-52 |
| DIV-E14 | PENDENCIAS_AWS.md:104 manda guardar certificado em `nginx-proxy/certs/`; o real é `sites-enabled/certs/` (`_ssl.inc:16-21`) | `openssl x509` |
| DIV-E15 | Spec: fila 8h e horário 8h-20h locais × containers sem `TZ` (UTC) | docker-compose.yml:1-37; totalpass define `TZ` |
| DIV-E16 | Spec "log imutável" com "prazo definido pelo jurídico" × P-15 sem prazo e `evento_uso` sem TTL | PENDENCIAS.md:85 |
| DIV-E17 | P-41 estimou consumo do hub só pelo web; jobs (perfis diários, CSV em lote) mudam a cota PII | PENDENCIAS.md:99 |
| DIV-E18 | `verificar-pos-reboot.sh` não conhece `area_associado`, `mcp_hub`, `appapm-cron` (há 15 containers, script espera 12) | verificar-pos-reboot.sh:16,19,24 |

### DEC (`DEC-E*`) — decisões a tomar (opções, prós/contras, recomendação)
| ID | Decisão | Opções | Recomendação |
|---|---|---|---|
| DEC-E01 | Agendador dos jobs | (a) loop Python in-process (`python -m app.jobs`): + `docker logs`, SIGTERM, sem caps extras, healthcheck por heartbeat; − precisa de disciplina de lock/intervalo. (b) `crond` na imagem (totalpass): + crontab legível; − pacote `cron` no slim, `cap_add SETUID/SETGID`, log via `-L`. (c) crontab do host com `docker compose exec` (login_associado): + zero código; − fora do compose, logs em arquivo do host, não reproduzível em homolog/CI. | **(a)** + `GET_LOCK` + `job_execucao` + `JOBS_APLICAR` (dry-run) — ADR nova |
| DEC-E02 | Hospedagem e autenticação do backoffice | (a) mesmo container `/admin`; (b) container separado mesma imagem + host próprio; (c) qualquer um atrás de Cloudflare Access (MFA do IdP corporativo) + allowlist IP; autenticação da app: OIDC com Entra ID da APM (funcionários) ≠ `login_associado` (associados). | **(b)+(c)**: isola pool/memória/superfície, 2FA sem código novo, perfis na app; usuário de banco próprio; ADR nova |
| DEC-E03 | Canal do CSV plano B | (a) upload pelo funcionário no B06 (parceiro entrega por canal corporativo da APM — fora do sistema): + simples, F1; − "canal autenticado" fica fora do nosso controle. (b) S3 presigned URL gerada pelo backoffice por parceiro/mês: + sem porta nova, auditável, barato; − IAM/role, ciclo de vida, antivírus opcional. (c) SFTP (Transfer Family ~US$ 200+/mês ou sshd na EC2 = porta nova 🔒 evitar). (d) portal do parceiro PAR-01 (F2). | **(a) em F1, (b) em F2** (ou junto com PAR-01); nunca (c) |
| DEC-E04 | OpenAPI | (1) `openapi.json` versionado gerado no CI; (2) `/docs` por flag só na rede Docker; (3) portal interno. | **(1)+(2)** |
| DEC-E05 | Observabilidade/alertas | Datadog (já pago, integração CloudWatch) × CloudWatch alarms + SNS (IAM) × monitor externo free + resumo por e-mail (padrão IdP) × RUM próprio em `evento_uso`. | Monitor externo + resumo/alerta próprio (TI-E07) + RUM próprio (TI-E08); Datadog só se alguém o consumir (EXT-E10) |
| DEC-E06 | Topologia da homologação | (a) mesmo host, mesmo RDS, schema `_hml`: + barato; − contamina `mysql-producao`, conexões. (b) mesmo host, RDS separado por snapshot (db.t4g.micro): + isola, serve de ensaio de restore; − ~US$ 15-20/mês. (c) não criar; "staging" continua sendo a produção em construção até a virada: + zero custo; − viola §14 e deixa a escrita no CRM sem ensaio. | **(b)** quando a Fase 3 (escrita) chegar; até lá (c) com `HUB_ESCRITA_HABILITADA=false` |
| DEC-E07 | Deploy automatizado | (a) CI só valida, deploy por `scripts/deploy.sh` no host (pull-based): + SG fechado (SSH só 2 IPs), simples; − humano no loop. (b) Actions faz SSH na EC2: − abre 22 para IPs do GitHub. (c) runner self-hosted na EC2: − RAM/CPU, superfície. | **(a)** |
| DEC-E08 | Escopo do PWA | (a) só manifest (instalável, sem offline); (b) manifest + SW mínimo (shell/assets + página offline, nunca `/api/`); (c) SW com cache de carteirinha offline (dado pessoal no dispositivo). | **(b)**; (c) só com ADR e decisão do encarregado de dados |
| DEC-E09 | Disponibilidade-alvo | (a) declarar SLO 99,5 % mensal com 1 host/Single-AZ + runbook de restore; (b) Multi-AZ no RDS (~2× custo da instância). | (a) agora; (b) revisitar com RI (PENDENCIAS_AWS P4) |
| DEC-E10 | Retenção de backup do RDS | 7 d (atual) × 14 d × 35 d; custo só acima de 30 GB de backup gratuito. | 14 d + snapshot manual antes de cada migração/cutover |

---

## Riscos e ADRs candidatas

**Riscos ativos (ordem de gravidade):**
1. **Certificado de origem vencido há 19 dias** (P-01): Cloudflare↔origem sem validação; qualquer mudança para Full (strict) por engano derruba os 7 sites.
2. **`.env` sem cópia atual** (P-36): perda do host = perda de `SESSION_ENC_KEYS`/`CARTEIRINHA_HMAC_KEY`/`LOG_HASH_KEY` → QRs e trilha irrecuperáveis.
3. **Zero monitoramento externo e zero alerta**: um 502 em `minha.` só é visto por quem abrir o site.
4. **Backup nunca restaurado**: 7 dias de retenção, sem evidência de que o snapshot serve.
5. **Catch-all ausente**: DNS de `hml`/`admin` antes do vhost abre o Sistema de Parceiros naquele host (repete 19/10).
6. **RDS t4g.micro compartilhado**: jobs + homolog + backoffice somam pools; `max_connections` a confirmar.
7. **Jobs com efeito externo (CRM/RD) sem dry-run obrigatório** repetiriam o problema que o totalpass já resolveu com `CRON_APLICAR`.
8. **CSV com CPF** entrando pela área contraria ADR-0014; resolver no hub.
9. **Docs desatualizados** (DIV-E10..E14) induzem erro no cutover.

**ADRs candidatas:**
- ADR-0018 — Serviço de jobs: agendador in-process, `GET_LOCK` + `job_execucao`, `JOBS_APLICAR`, segredos de job só no serviço jobs, conta própria no hub.
- ADR-0019 — Backoffice: container separado na mesma imagem, host próprio, Cloudflare Access + allowlist, OIDC corporativo, usuário de banco próprio, trilha só INSERT.
- ADR-0020 — Ambientes e promoção: dev (stub) → homolog (RDS separado, hub stub/sandbox, dados anonimizados por construção) → prod; CI valida, deploy pull-based com tag e rollback.
- ADR-0021 — Canal do CSV plano B: upload no backoffice (F1) → S3 presigned (F2); CPF resolvido no hub, quarentena fora do schema.
- ADR-0022 — Observabilidade: uptime externo, alerta próprio, RUM próprio via `evento_uso` (sem terceiros por CSP), retenção de logs.
- ADR-0023 — PWA: manifest + SW mínimo sem dado pessoal em cache.
- ADR-0024 — Backup e restauração: política, snapshot pré-migração, teste trimestral, `.env` no cofre com conferência.
- ADR-0025 — OpenAPI versionado no repositório, `/docs` só na rede interna.

## Ordem sugerida
1. **Hoje, sem código:** EXT-E01/TI-E14 (certificado), EXT-E03/TI-E13 (`.env`), TI-E04 (catch-all), TI-E03 (pós-reboot), EXT-E06/TI-E06 (uptime).
2. **Antes da Fase 3 entrar no ar:** ADR-0018 + TI-E01/E02/E11/E22 (jobs com profile desligado e dry-run), TI-E05 (deploy script), TI-E12 + EXT-E02/E04 (restore ensaiado), TI-E09 (OpenAPI), TI-E21 (docs).
3. **Com a Fase 3/4:** TI-E07/E08 (alertas + RUM, indicador 14), TI-E10 + EXT-E07 (CI), decisão DEC-E06 e TI-E19 (homolog) antes de `HUB_ESCRITA_HABILITADA=true`.
4. **Backoffice (F1 da spec, sem fase nossa):** DEC-E02/E03 → ADR-0019/0021 → EXT-E08/E19 → TI-E17/E18.
5. **F2:** DEC-E08 → TI-E16/E15 (PWA), jobs WP/score/resumo, S3 para CSV, Multi-AZ/retenção (DEC-E09/E10) junto da RI do RDS.
