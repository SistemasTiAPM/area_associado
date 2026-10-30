# Operação — Minha APM (`minha.apm.org.br`)

Runbooks do operador. Tudo aqui roda **fora da aplicação**: no host da EC2, no console da AWS ou no
Cloudflare. Nada é executado pela área nem pelo processo web. Criado em 2026-10-30 (Onda 0/1 do
`docs/PLANO-EXECUCAO.md`); itens marcados **[pendente]** ainda não foram executados.

| § | Runbook | Pendência | Estado |
|---|---|---|---|
| 1 | Deploy com tag, smoke e rollback (`scripts/deploy.sh`) | TI-74 | pronto |
| 2 | Certificado de origem (Cloudflare Origin CA) | P-01 / TI-70 | **[pendente]** — cert vencido em 10/10 |
| 3 | `.env` no Secrets Manager e limpeza dos `.env.bak-*` | P-36 / TI-73 | **[pendente]** |
| 4 | Catch-all da porta 443 | P-34 / TI-71 | **[pendente]** — arquivo pronto |
| 5 | Pós-reboot e monitor externo | P-19 / TI-72, TI-75 | **[pendente]** — trecho e script prontos |
| 6 | Backup e restauração do RDS | TI-76 | política confirmada; ensaio **[pendente]** (IAM, P-59) |
| 7 | Partições de `evento_log`/`evento_uso` (criar futuras, expurgar) | TI-02 / P-15 | migração pronta; aplicação **[pendente]** |
| 8 | Segredos e rotação de chaves | TI-12 | runbook; rotação só quando houver motivo |
| 9 | Alertas (`scripts/alertas.sh`) | TI-75 | pronto sem envio (P-27/P-61) |

Convenções: `~/.rds-admin.cnf` (0600) é a credencial administrativa do RDS; o `.env` do projeto tem só
a credencial limitada `apm_area`. Toda ação aqui que muda estado ganha linha em `docs/CONCLUIDO.md`
(data, quem, evidência).

---

## 1. Deploy (`scripts/deploy.sh`)

```bash
cd /home/ubuntu/area_associado
scripts/deploy.sh                 # pull --ff-only → build → tag <sha> → up -d → healthy → smoke
scripts/deploy.sh --sem-pull      # código já está no disco (ex.: branch local)
scripts/deploy.sh --dry-run       # só mostra o que faria
scripts/deploy.sh --rollback      # volta à imagem que estava no ar antes do último deploy
scripts/deploy.sh --rollback 6a20cbf2   # ou a uma tag específica (docker images area_associado-area-associado)
```

O que ele garante: um deploy por vez (`flock`); árvore limpa antes do `pull`; build com o builder
clássico (`DOCKER_BUILDKIT=0`, o host não tem `buildx` — P-26); a imagem recebe a tag
`area_associado-area-associado:<sha8>`; espera `healthy` (padrão 150 s, `--timeout`); smoke
`db_check` + `check_oidc` + `csp_check` dentro do container e `curl https://minha.apm.org.br/health`.
**Qualquer falha após o `up` volta a imagem anterior** e sobe de novo; o código no disco fica no commit
novo para investigação. Mantém as 5 tags mais recentes (`--manter N`). Estado do rollback em
`.deploy-anterior` (gitignored).

O que ele **não** faz: migração SQL (operador, antes do deploy que depende dela — `docs/PROVISIONAMENTO.md`),
mudança no `.env` (editar antes; o `up -d` recria o container e relê) e vhost do porteiro.

Ordem de uma entrega com migração: snapshot manual (§6.2) → `sql/NNN` → `db_check` → `deploy.sh`.

## 2. Certificado de origem — P-01 (TI-70)

Situação: `/home/ubuntu/nginx-proxy/sites-enabled/certs/origin.pem` é autoassinado
(`O=TEMPORARIO-NAO-USAR-EM-PRODUCAO`) e **venceu em 10/10/2026**. Os 7 sites só respondem porque a zona
Cloudflare não está em *Full (strict)*: Cloudflare → origem aceita certificado inválido (MITM entre o
Cloudflare e a EC2 não é detectado). O caminho correto é `sites-enabled/certs/` (bind mount `conf.d` do
`nginx_porteiro`, `:ro`), não `nginx-proxy/certs/` — `PENDENCIAS_AWS.md` corrigido em 30/10.

1. **Emitir** (admin do Cloudflare): SSL/TLS → Origin Server → *Create Certificate* → RSA (2048),
   hostnames `*.apm.org.br` e `apm.org.br`, validade 15 anos. Copiar o certificado (PEM) e a chave
   privada **na hora** (a chave não é mostrada de novo).
2. **Instalar** (host, como root — o diretório é do root):
   ```bash
   cd /home/ubuntu/nginx-proxy/sites-enabled/certs
   sudo cp origin.pem origin.pem.bak-$(date +%Y%m%d) && sudo cp origin.key origin.key.bak-$(date +%Y%m%d)
   sudo install -m 0644 -o root -g root /caminho/novo/origin.pem origin.pem
   sudo install -m 0640 -o root -g root /caminho/novo/origin.key origin.key
   openssl x509 -in origin.pem -noout -subject -issuer -enddate     # issuer = CloudFlare Origin SSL CA; 2041
   openssl x509 -noout -modulus -in origin.pem | sha256sum; sudo openssl rsa -noout -modulus -in origin.key | sha256sum   # iguais
   docker exec nginx_porteiro nginx -t && docker exec nginx_porteiro nginx -s reload
   ```
   Os vhosts não mudam: todos incluem `_ssl.inc`, que aponta para `origin.pem`/`origin.key`.
3. **Conferir** antes do strict: `curl -sI https://minha.apm.org.br/health | head -1` (200) e, do host,
   `openssl s_client -connect 127.0.0.1:443 -servername minha.apm.org.br </dev/null 2>/dev/null | openssl x509 -noout -issuer`.
4. **Zona Full (strict)** no Cloudflare (SSL/TLS → Overview). Repetir o `curl` nos 7 hosts
   (`app totalpass parceiros login formulario minha mcp`): qualquer 526 = voltar para *Full* e revisar o
   passo 2.
5. **Limpar**: `sudo rm temp.pem temp.key` e, depois de uma semana, os `.bak-*`. Rodar
   `bash ~/verificar-pos-reboot.sh` (bloco de certificado, §5) e `scripts/alertas.sh` (sem alerta de cert).
6. Registrar em `docs/CONCLUIDO.md` e fechar P-01 em `docs/PENDENCIAS.md` e `PENDENCIAS_AWS.md`.

## 3. `.env` no cofre e limpeza — P-36 (TI-73)

A role da EC2 (`EC2-ReadOnly-Billing`) **não** tem `secretsmanager:GetSecretValue` nem `DescribeSecret`
(confirmado em 30/10: `AccessDeniedException`). Até a P-59 (IAM), a replicação é manual pelo console.

1. Console AWS, região `sa-east-1`, Secrets Manager → `prod/area-associado/env` → *Retrieve secret value*
   → *Edit* → aba *Plaintext*. Colar o conteúdo de `/home/ubuntu/area_associado/.env` convertido para
   JSON de pares (sem comentários nem linhas vazias):
   ```bash
   cd /home/ubuntu/area_associado
   grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | jq -Rn '[inputs | capture("^(?<k>[^=]+)=(?<v>.*)$")] | from_entries' > /dev/shm/env.json
   cat /dev/shm/env.json   # colar no console; depois: shred -u /dev/shm/env.json
   ```
2. Conferência (mesmo hash dos dois lados, sem expor valores): no host
   `grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | sort | sha256sum | cut -c1-16`; no console, baixar o JSON e
   `jq -r 'to_entries[] | "\(.key)=\(.value)"' | sort | sha256sum | cut -c1-16`. Com a P-59,
   `scripts/alertas.sh` faz isso sozinho (`.env×cofre : igual`).
3. Apagar as cópias antigas — são risco (chaves de 19–21/10 já substituídas), não backup:
   `shred -u .env.bak-20261019-dominio .env.bak-20261020-oidc .env.bak-202610211310`.
4. Regra daqui em diante: **toda** mudança no `.env` = replicar no cofre no mesmo dia; nunca `.env.bak`
   no disco (se precisar de histórico, é o cofre que versiona).
5. Registrar em `docs/CONCLUIDO.md`; fechar P-36.

## 4. Catch-all da 443 — P-34 (TI-71)

Arquivo pronto: `deploy/nginx_porteiro/_00_padrao.conf.example` (`listen 443 ssl default_server;
server_name _; return 444;`, reaproveitando `_ssl.inc`; **não** toca a porta 80, cujo default continua
`apm_parceiros.conf`). Mexe no porteiro de todos os sites → aprovação do operador.

```bash
cp /home/ubuntu/area_associado/deploy/nginx_porteiro/_00_padrao.conf.example /home/ubuntu/nginx-proxy/sites-enabled/_00_padrao.conf
docker exec nginx_porteiro nginx -t && docker exec nginx_porteiro nginx -s reload
curl -sk -o /dev/null -w '%{http_code}\n' https://52.67.3.198/                      # 000 (fechada)
curl -s  -o /dev/null -w '%{http_code}\n' https://minha.apm.org.br/health           # 200
for h in app totalpass parceiros login formulario mcp; do curl -s -o /dev/null -w "$h %{http_code}\n" --max-time 20 https://$h.apm.org.br/; done
```

Reverter: `rm .../_00_padrao.conf && nginx -t && nginx -s reload`. Fechar P-34.

## 5. Pós-reboot e monitor externo — P-19 (TI-72, TI-75)

- **Pós-reboot**: aplicar `deploy/verificar-pos-reboot.patch.md` em `~/verificar-pos-reboot.sh`
  (containers `area_associado`, `mcp_hub`, `appapm-cron`; hosts `minha`/`mcp` em `/health`; `/db-health`
  403 na borda; validade e emissor do `origin.pem`; Tracebacks da área). `area_associado_jobs` entra
  quando o serviço de jobs subir (Onda 2).
- **Monitor externo** (EXT-29 / P-61): conta gratuita em UptimeRobot ou Better Stack, com contato de
  alerta do operador. Cadastrar **7 monitores HTTP(S)**, intervalo 5 min, esperando `200`:
  `https://minha.apm.org.br/health`, `https://mcp.apm.org.br/health`, `https://login.apm.org.br/health`
  (ou a rota de saúde do IdP), `https://app.apm.org.br/`, `https://totalpass.apm.org.br/`,
  `https://parceiros.apm.org.br/`, `https://formulario.apm.org.br/`. Sem palavra-chave no corpo (a
  `/health` devolve `{"status":"ok"}`; pode-se exigir `"ok"`). Alerta após 2 falhas seguidas.
  Decidir junto o destino do Datadog pago (`PENDENCIAS_AWS.md`): usar ou cancelar.
- **Alertas internos**: `scripts/alertas.sh` (§9) no cron diário quando houver canal de envio.

## 6. Backup e restauração do RDS — TI-76

### 6.1 Política atual (confirmada em 29/10 com `aws rds describe-db-instances`)

`mysql-producao` (db.t4g.micro, MySQL 8.4.8, Single-AZ, 30 GB cifrado, `DeletionProtection=true`):
retenção **7 dias**, janela de backup **06:11–06:41 UTC** (03:11 BRT), **PITR** ativo, snapshots
automáticos diários (`rds:mysql-producao-AAAA-MM-DD-06-16`), **zero snapshots manuais**, nenhum teste de
restauração registrado. Logs `error`/`slowquery` não exportados; Performance Insights desligado.
Recomendação registrada (DEC-33): retenção 14 dias + snapshot manual antes de migração e cutover.
A área não tem volume: backup = RDS + `.env` (cofre, §3) + git.

### 6.2 Snapshot manual — antes de cada `sql/NNN` e do cutover

Pelo console (RDS → Databases → `mysql-producao` → Actions → *Take snapshot*) ou, com a P-59 (IAM
`rds:CreateDBSnapshot`):

```bash
aws rds create-db-snapshot --region sa-east-1 --db-instance-identifier mysql-producao \
  --db-snapshot-identifier "manual-area-$(date +%Y%m%d-%H%M)-pre-sql008"
aws rds wait db-snapshot-available --region sa-east-1 --db-snapshot-identifier manual-area-...   # ~2–5 min
```

Nome: `manual-<projeto>-<data>-<motivo>`. Snapshot manual não expira: apagar os com mais de 90 dias
que não documentem um incidente (`aws rds delete-db-snapshot`). Anotar o identificador na linha da
migração em `docs/CONCLUIDO.md`.

### 6.3 Restauração ensaiada — trimestral (próxima: **[pendente]**, exige P-59)

Nunca restaurar **sobre** a produção. Sempre em instância temporária, validar, descartar.

```bash
SNAP=$(aws rds describe-db-snapshots --region sa-east-1 --db-instance-identifier mysql-producao \
       --query 'reverse(sort_by(DBSnapshots,&SnapshotCreateTime))[0].DBSnapshotIdentifier' --output text)
aws rds restore-db-instance-from-db-snapshot --region sa-east-1 --db-snapshot-identifier "$SNAP" \
  --db-instance-identifier mysql-restore-teste --db-instance-class db.t4g.micro --no-publicly-accessible \
  --vpc-security-group-ids <sg da EC2> --db-subnet-group-name <mesmo da produção> --no-multi-az
aws rds wait db-instance-available --region sa-east-1 --db-instance-identifier mysql-restore-teste   # 10–20 min
HOST=$(aws rds describe-db-instances --region sa-east-1 --db-instance-identifier mysql-restore-teste --query 'DBInstances[0].Endpoint.Address' --output text)
```

Validação (a credencial admin é a mesma do snapshot):

```bash
mysql --defaults-extra-file=$HOME/.rds-admin.cnf -h "$HOST" --ssl-mode=REQUIRED area_associado -e "
  SELECT versao, arquivo, aplicado_em FROM schema_migrations ORDER BY versao;
  SELECT 'associado', COUNT(*) FROM associado UNION ALL SELECT 'associado_perfil', COUNT(*) FROM associado_perfil
  UNION ALL SELECT 'evento_log', COUNT(*) FROM evento_log UNION ALL SELECT 'evento_uso', COUNT(*) FROM evento_uso
  UNION ALL SELECT 'feature_flag', COUNT(*) FROM feature_flag;
  SELECT MAX(ocorrido_em) ultimo_evento FROM evento_log;"
# db_check contra a instância restaurada, como a aplicação (grants e partições vêm no snapshot):
cd /home/ubuntu/area_associado && docker compose run --rm -e DB_HOST="$HOST" area-associado python -m scripts.db_check
```

Critério de sucesso: `schema_migrations` igual à produção, contagens compatíveis com a hora do snapshot,
`ultimo_evento` ≤ hora do snapshot, `db_check` conforme. Descartar **no mesmo dia**:

```bash
aws rds delete-db-instance --region sa-east-1 --db-instance-identifier mysql-restore-teste --skip-final-snapshot
```

Registrar em `docs/CONCLUIDO.md`: data, snapshot usado, tempo até `available`, contagens, quem. Com PITR a
mesma receita vale com `restore-db-instance-to-point-in-time --restore-time <UTC>` (erro humano com hora
conhecida). Opcional (F2): exportar `evento_log` mensal para S3 com Object Lock (imutabilidade fora do RDS).

### 6.4 Restauração real (incidente)

1. Parar a escrita: `docker compose stop area-associado` (o porteiro devolve 502 só em `minha.`).
2. Restaurar em instância **nova** (6.3) a partir do snapshot/PITR escolhido; validar.
3. Apontar a área: `DB_HOST` no `.env` → `docker compose up -d` → `db_check` → replicar `.env` no cofre.
   Os outros projetos continuam na instância original até cada um decidir.
4. Registrar incidente, causa e janela perdida em `docs/CONCLUIDO.md`.

## 7. Partições de `evento_log` / `evento_uso` — TI-02 (P-15)

A `sql/008_particao_eventos.sql` (aplicação em `docs/PROVISIONAMENTO.md` §2.3) deixa as duas trilhas
particionadas por mês (2026-10 … 2028-10 + `pMAX`). O `db_check` imprime `particoes : evento_log=26
evento_uso=26` e **avisa** quando a última partição mensal estiver a menos de 90 dias.

- **Criar partições futuras** (a cada semestre ou ao aviso), usuário admin — divide só `pMAX`:
  ```sql
  ALTER TABLE evento_log REORGANIZE PARTITION pMAX INTO (
      PARTITION p202811 VALUES LESS THAN (TO_DAYS('2028-12-01')),
      PARTITION p202812 VALUES LESS THAN (TO_DAYS('2029-01-01')),
      PARTITION pMAX    VALUES LESS THAN MAXVALUE);
  -- idem para evento_uso
  ```
- **Expurgo** (só após o prazo do jurídico, P-54; snapshot manual antes; nunca o mês corrente):
  mês inteiro → `ALTER TABLE evento_uso DROP PARTITION p202610;`. Em `evento_log`, `request` expira em
  12 meses mas `seguranca`/`negocio`/`erro` não: tirar a partição para uma tabela de arquivo com
  `EXCHANGE PARTITION` e apagar só `request` lá (receita completa no cabeçalho da `sql/008`, item 2b).
- Ocupação por mês: consulta em `information_schema.PARTITIONS` (cabeçalho da `sql/008`, item 3).
- Registrar cada expurgo em `docs/CONCLUIDO.md` (tabela, partição, data, quem).

## 8. Segredos e rotação — TI-12

Onde vivem: `.env` (0600) + cofre `prod/area-associado/env` (§3). O que cada chave protege e o custo
de trocá-la (todas exigem `docker compose up -d` para o container reler o `.env`):

| Chave | Protege | Efeito da troca | Como rotacionar |
|---|---|---|---|
| `SESSION_ENC_KEYS` | cookie de sessão (Fernet, ADR-0011) | sem janela de convivência, **todos** são deslogados | **MultiFernet**: gerar nova (`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`), colocá-la **à esquerda** da atual (`nova,antiga`), `up -d`; após `SESSION_MAX_AGE` remover a antiga, `up -d`. Ninguém cai. |
| `SECRET_KEY` | CSRF de formulário, derivações fora de produção | sessões e formulários em voo invalidam | trocar em janela de baixo uso; em produção não deriva mais nada (as chaves abaixo são explícitas). |
| `CARTEIRINHA_HMAC_KEY` | token público do QR (`associado.carteirinha_token`, ADR-0014) | **invalida todos os QRs já impressos/compartilhados**; `/verificar/{token}` antigo passa a responder "não encontrado" | só por comprometimento. Trocar, `up -d`; `garantir_token` regenera o token de cada associado **no próximo login** (UPDATE em `associado`). Comunicar aos associados que o QR mudou; não há migração em massa (seria um UPDATE administrativo com a chave nova — se preciso, script único do operador, fora da app). |
| `LOG_HASH_KEY` | HMAC de `sub`/IP/UA em `evento_log` e `evento_uso` | eventos antigos e novos deixam de correlacionar (pseudônimo muda) | só por comprometimento; registrar a data da troca em CONCLUIDO para quem for investigar a trilha. |
| `OIDC_CLIENT_SECRET` | autenticação do RP no Login APM | login para até o IdP ter o mesmo valor | gerar no IdP (`login_associado`), colocar no `.env`, `up -d`, `check_oidc`. |
| `HUB_CLIENT_SECRET` | conta `area-associado` no `mcp_hub` | perfil/carteirinha sem dado do CRM até casar | rotacionar no hub e aqui na mesma janela; `check_hub`. |
| `DB_PASS` | `apm_area` no RDS | app sem banco até casar | `ALTER USER 'apm_area'@'%' IDENTIFIED BY '...'` (admin) + `.env` + `up -d` + `db_check`. |
| `SMTP_PASSWORD` (P-27) | envio de e-mail | e-mails de verificação param | trocar no provedor e no `.env`. |

Chaves **previstas** (nascem com as fases; documentar aqui quando existirem): `.env.jobs` do serviço de
jobs (conta própria `area-associado-jobs` no hub, ADR-0019), `RD_*` (RD Station, Onda 3), segredo do
canal do CSV (DEC-05), `WP_DB_*` (leitura do portal, Fase 5). Regra: toda chave nova entra no
`config.Settings` com validador de produção, no `.env.example` com comentário e no cofre.

Perda do `.env` sem cofre atualizado = sessões caem (`SESSION_ENC_KEYS`), QRs invalidam
(`CARTEIRINHA_HMAC_KEY`) e trilhas descorrelacionam (`LOG_HASH_KEY`). É por isso que o §3 vem antes de
qualquer deploy grande.

## 9. Alertas internos — `scripts/alertas.sh` (TI-75)

```bash
scripts/alertas.sh              # texto; exit 0 sem alerta, 2 com alerta
scripts/alertas.sh --json       # mesmo conteúdo para um webhook futuro
scripts/alertas.sh --desde 1h   # janela menor (padrão 24h)
```

Sinais: 5xx e Tracebacks da área (`docker logs`), 5xx/429/444 do porteiro (todos os hosts — o
`log_format main` não traz o host), saúde dos containers `area_associado`/`mcp_hub`/`nginx_porteiro`,
`/db-health` pela rede interna (`status`, `uso_falhas`, SPA, TLS), validade e emissor do certificado
de origem (< 30 dias), `.env` × cofre (quando houver `GetSecretValue`; hoje imprime "não verificável") e
`.env.bak-*` no disco, `job_execucao` com erro (n/a até a tabela existir). **Não envia nada**: `--email`
só avisa que depende da P-27. Quando houver canal: cron `5 7 * * *` conforme o cabeçalho do script.


## 10. mcp_hub — deploy e grant das ferramentas de situação (TI-47, M-7)

A saída sem CPF de `associado.situacao` e `associado.historico_associacao` só vale em produção depois do
rebuild do hub; a área só consegue chamá-las depois do grant exato na conta `area-associado`.

```bash
cd /home/ubuntu/mcp_hub
docker tag mcp_hub-mcp-hub:latest mcp_hub-mcp-hub:anterior        # rollback possível
DOCKER_BUILDKIT=0 docker compose build && docker compose up -d
docker compose ps                                                 # (healthy)
docker compose exec mcp-hub python -m scripts.db_check            # RESULTADO: OK
# smoke do IdP (ele consome associado.situacao):
cd /home/ubuntu/login_associado && docker compose exec login-associado python -m scripts.check_crm
```

Rollback: `docker tag mcp_hub-mcp-hub:anterior mcp_hub-mcp-hub:latest && docker compose up -d`.

**Grant (M-7, painel do hub, não há migração):** Painel → Grupos → grupo da conta `area-associado` →
permissões → **permitir** `associado.situacao` e `associado.historico_associacao`, nome **exato**, modo
`completo`, sem exportar. Nunca `associado.*` (liberaria `consultar`/`visao_360`, que devolvem CPF). Vale
em ≤ 30 s. Prova na área: `docker compose exec area-associado python -m scripts.check_hub <contact_id de
teste>` → `situacao : ok`, `campos : 12/12`, `sem cpf : ok`.

**Conta de jobs (M-8, Onda 2):** `area-associado-jobs`, `client_credentials` próprio, só `ferramentas:ler`,
grants exatos em `associado.situacao` e `associado.perfil_consultar`, mesma allowlist de rede, 300/min e
15.000 PII/dia (P-41). Credencial no `.env.jobs` do serviço de jobs.
