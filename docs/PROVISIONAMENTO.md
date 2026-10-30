# Provisionamento do banco — area_associado

Roda **uma vez**, com uma credencial que tenha DDL no RDS `mysql-producao`.

## Regra de credenciais

| Credencial | Onde vive | Quem usa |
| --- | --- | --- |
| `apm_area` (limitada) | `.env` do projeto, `chmod 600` | a aplicação, em todo request |
| Admin / operador do RDS | `~/.rds-admin.cnf` (0600), **fora do projeto** | uma pessoa, só nas migrações |

A credencial administrativa **não entra no `.env`**: o compose injeta o arquivo inteiro no
container. O `apm_area` recebe `SELECT, INSERT, EXECUTE` — sem DDL, sem UPDATE e sem DELETE
no schema. Mutação é concedida **por tabela**, em migração própria, quando houver motivo.

## 1. Schema e usuário (senha injetada na execução)

```bash
cd /home/ubuntu/area_associado
umask 077
SENHA=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 40)
sed "s/TROCAR_POR_SENHA_FORTE/${SENHA}/" sql/000_schema_e_usuario.sql > /tmp/prov.sql
mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED < /tmp/prov.sql
shred -u /tmp/prov.sql
sed -i "s|^DB_PASS=.*|DB_PASS=${SENHA}|" .env
unset SENHA
```

`CREATE DATABASE IF NOT EXISTS` e `CREATE USER IF NOT EXISTS` tornam o `000` seguro de
reexecutar — mas numa reexecução a senha **não** é alterada (use `ALTER USER` para isso).

## 2. Migrations e registro do sha256

```bash
for f in sql/001_schema_migrations.sql sql/002_evento_log.sql; do
  echo "aplicando $f"
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado < "$f" || break
done
for v in 002; do
  f=$(ls sql/${v}_*.sql); h=$(sha256sum "$f" | cut -d' ' -f1)
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado -e \
    "INSERT INTO schema_migrations (versao, arquivo, sha256) VALUES ('$v', '$(basename $f)', '$h')
     ON DUPLICATE KEY UPDATE sha256 = VALUES(sha256);"
done
```

### 2.1 Fase 1 da Minha APM — `sql/003` a `sql/005` (2026-10-17)

`003_feature_flag` (8 flags, todas desligadas), `004_evento_uso` (analytics, append-only) e
`005_associado` (identidade da área; **concede `UPDATE` só na tabela `associado`**, ADR-0004).
Validadas num MySQL 8.4.11 descartável antes do commit (grants, CHECKs, recusa de DELETE).

```bash
for f in sql/003_feature_flag.sql sql/004_evento_uso.sql sql/005_associado.sql; do
  echo "aplicando $f"
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado < "$f" || break
done
for v in 003 004 005; do
  f=$(ls sql/${v}_*.sql); h=$(sha256sum "$f" | cut -d' ' -f1)
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado -e \
    "INSERT INTO schema_migrations (versao, arquivo, sha256) VALUES ('$v', '$(basename $f)', '$h') AS novo
     ON DUPLICATE KEY UPDATE sha256 = novo.sha256;"
done
```

### 2.2 Fase 2a — `sql/006` e `sql/007` (2026-10-17)

`006_associado_perfil` (cache do cadastro e miniatura da foto; UPDATE só nela) e
`007_email_verificacao` (só HMACs; UPDATE só nela). Mesmo procedimento do §2.1, com
`for v in 006 007`. Validadas num MySQL 8.4 descartável com a suíte de integração
(`TESTE_DB_HOST=... python -m pytest`).

Sem as tabelas a aplicação **continua no ar** (fail-safe): flags ficam todas desligadas,
`evento_uso` e o registro de acesso só geram log de erro e o contador `uso_falhas` em `/db-health`.

### 2.3 Onda 1 — `sql/008_particao_eventos` (2026-10-30)

`008_particao_eventos` **reconstrói** `evento_log` e `evento_uso`: PK composta `(id, ocorrido_em)` e
`PARTITION BY RANGE (TO_DAYS(ocorrido_em))` mensal, 25 partições pré-criadas (2026-10 … 2028-10) +
`pMAX`. Nenhum GRANT novo: as trilhas continuam só INSERT para `apm_area`; o expurgo da P-15 passa a ser
`DROP PARTITION`/`EXCHANGE PARTITION` administrativo (procedimentos no cabeçalho do arquivo e em
`docs/OPERACAO.md` §7). Ensaiada em MySQL 8.4.11 descartável em 2026-10-30 (000→008 em ordem, `SHOW
CREATE TABLE`, INSERT como `apm_area` ok, UPDATE/DELETE/ALTER recusados, suíte `-m mysql` verde).

Particularidades: (1) **não é reaplicável** — rodar duas vezes só reconstrói de novo; confira antes
`SELECT versao FROM schema_migrations` (sem `008`); (2) a cópia segura um *metadata lock*: os INSERTs da
aplicação esperam alguns segundos e `audit`/`uso` nunca derrubam a resposta — ainda assim, janela de pouco
tráfego; (3) **snapshot manual do RDS antes** (`docs/OPERACAO.md` §6). sha256 esperado do arquivo:
`8c3e26ad6c816391f861ead35acd0a0b2f9c4d0e7cc51e06f6edd2932e6ec493` (confira com `sha256sum`; se
divergir, o arquivo foi editado depois do ensaio — não aplique).

```bash
cd /home/ubuntu/area_associado
sha256sum sql/008_particao_eventos.sql          # deve bater com o hash acima
for f in sql/008_particao_eventos.sql; do
  echo "aplicando $f"
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado < "$f" || break
done
for v in 008; do
  f=$(ls sql/${v}_*.sql); h=$(sha256sum "$f" | cut -d' ' -f1)
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado -e \
    "INSERT INTO schema_migrations (versao, arquivo, sha256) VALUES ('$v', '$(basename $f)', '$h') AS novo
     ON DUPLICATE KEY UPDATE sha256 = novo.sha256;"
done
mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado -e \
  "SELECT TABLE_NAME, COUNT(*) particoes FROM information_schema.PARTITIONS
   WHERE TABLE_SCHEMA='area_associado' AND TABLE_NAME IN ('evento_log','evento_uso') GROUP BY TABLE_NAME;"
docker compose exec area-associado python -m scripts.db_check   # particoes : evento_log=26 evento_uso=26
```

### 2.4 Onda 1 — `sql/009_flags_v2` (2026-10-30)

`009_flags_v2` insere as 7 flags da spec v2 (ADR-0021): `notificacoes`, `encaminhamento_parceiro`,
`reservas`, `inscricoes`, `comunicacao_outbox`, `cancelamento_online`, `lgpd_consentimentos` — todas
**desligadas**, sem GRANT novo (só INSERT na `feature_flag` da `003`; reexecução atualiza apenas a
`descricao`, nunca `ligada`). Mesmo laço do §2.1:

```bash
for f in sql/009_flags_v2.sql; do
  echo "aplicando $f"
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado < "$f" || break
done
for v in 009; do
  f=$(ls sql/${v}_*.sql); h=$(sha256sum "$f" | cut -d' ' -f1)
  mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado -e \
    "INSERT INTO schema_migrations (versao, arquivo, sha256) VALUES ('$v', '$(basename $f)', '$h') AS novo
     ON DUPLICATE KEY UPDATE sha256 = novo.sha256;"
done
mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado -e \
  "SELECT chave, ligada FROM feature_flag ORDER BY chave;"   # 15 linhas, todas as novas com ligada=0
```

Antes de aplicar, a aplicação já conhece as chaves (`app/flags.py`) e as trata como desligadas; depois,
ligar uma é `UPDATE feature_flag SET ligada = 1 WHERE chave = '...'` (vale em até `FLAGS_CACHE_TTL`).

### 2.5 Onda 2 — `sql/010` a `sql/014` (2026-10-30)

Cinco migrações, de três frentes, aplicadas **em ordem crescente** e cada uma uma única vez:

| Migração | Frente que cria | Conteúdo | Grant novo para `apm_area` | Reaplicável |
|---|---|---|---|---|
| `010_solicitacao` | A (Atlas) | `solicitacao` (8 status da spec, marcador `sem_retorno_desde`, vínculos, prazo, avaliação, idempotência, `crm_*`) e `solicitacao_evento` (log append-only com ator/origem/justificativa/`conteudo_enviado`) — ADR-0018 | `UPDATE` **por coluna** em `solicitacao` (status, datas, avaliação, `crm_*`, marcador); nada em `solicitacao_evento` | sim |
| `011_job_execucao` | C (Integrador/Estivador) | `job_execucao`: rastro de cada execução do serviço de jobs (nome com CHECK, início/fim, `status` executando/ok/erro/abortado, `modo` aplicar/simular, contagens, `erro_resumo` com CHECK anti-CPF/credencial, `posicao` do sync do CRM, `host`, `versao_app`) — ADR-0019 | `UPDATE` **por coluna** só no que fecha a linha (`terminado_em`, `status`, `itens_*`, `erro_resumo`, `posicao`) | sim |
| `012_comunicacao_notificacao` | A (Atlas) | outbox `comunicacao_evento` (dedupe por gatilho+associado+referência+canal+destinatário), `comunicacao_envio` e `comunicacao_supressao` (append-only), `notificacao`, `fila_ligacao` (só INSERT; resultado é do backoffice) | `UPDATE` por coluna em `comunicacao_evento` (estado da entrega) e só `lida_em` em `notificacao` | sim |
| `013_ajuda_parametro` | A (Atlas) | `faq`, `texto_sistema`, `parametro` com seed (`avaliacao_prazo_dias`=30, `prazo_retorno_padrao_dias`=10, `cancelamento_janela_horas`=24, `central_horario`/`central_telefone` vazios até a P-44) | **nenhum** — só leitura (ADR-0022); mudar valor é ato do operador | sim (o seed nunca sobrescreve `valor`) |
| `014_carteirinha_revogacao` | B (Sentinela) | §2.5b abaixo | nenhum | **não** |

sha256 esperados das migrações da frente A (ensaiadas em MySQL 8.4.11 descartável `mysql-ensaio-a` em
2026-10-30: 000→013 em ordem, reaplicação de 010/012/013 sem erro, grants conferidos como `apm_area` —
UPDATE só nas colunas concedidas, DELETE e UPDATE em trilha/configuração recusados —, `db_check`
conforme e suíte `-m mysql` verde; a `011` da frente C no `mysql-ensaio-c`, 000→014 em ordem, reaplicação sem
erro, UPDATE fora das colunas concedidas/DELETE recusados, CHECKs recusando, `db_check` conforme e suíte inteira
verde com MySQL). Se o `sha256sum` divergir, o arquivo mudou depois do ensaio: **não aplique**.

```
16c9518e2b7a024651c84a4cd02ea0e8c87bdab81c1579f2b93bf2b5773ed659  sql/010_solicitacao.sql
4e80bba866488d7cf4ded499ca4a5170e4c9aedf0aa3a87dcd0588209aedc6ff  sql/011_job_execucao.sql
1477bd9676e7546418fcad4eb013bd56e8c0ae99fbaf3210b8029479294f7fc9  sql/012_comunicacao_notificacao.sql
92fa92cd7c521e6b432327d8fa369b197d966778b62a255889a0701901273129  sql/013_ajuda_parametro.sql
```

Laço único (snapshot manual do RDS antes — `docs/OPERACAO.md` §6). Pula o que já está em
`schema_migrations` (a `014` não é reaplicável), para no primeiro erro e recusa arquivo com hash
diferente do esperado. A `014` tem o seu no §2.5b.

```bash
cd /home/ubuntu/area_associado
MYSQL="mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED area_associado"
declare -A ESPERADO=(
  [010]=16c9518e2b7a024651c84a4cd02ea0e8c87bdab81c1579f2b93bf2b5773ed659
  [011]=4e80bba866488d7cf4ded499ca4a5170e4c9aedf0aa3a87dcd0588209aedc6ff
  [012]=1477bd9676e7546418fcad4eb013bd56e8c0ae99fbaf3210b8029479294f7fc9
  [013]=92fa92cd7c521e6b432327d8fa369b197d966778b62a255889a0701901273129
  [014]=9595dc359ed438489788c9bdec49f76603db02cf8a01fe98a2cdc38f035a6bab
)
for v in 010 011 012 013 014; do
  f=$(ls sql/${v}_*.sql 2>/dev/null) || { echo "AUSENTE: sql/${v}_*.sql — parar"; break; }
  if [ -n "$($MYSQL -N -e "SELECT versao FROM schema_migrations WHERE versao = '$v'")" ]; then
    echo "já aplicada: $f"; continue
  fi
  h=$(sha256sum "$f" | cut -d' ' -f1)
  [ "$h" = "${ESPERADO[$v]}" ] || { echo "HASH DIVERGENTE em $f ($h) — parar"; break; }
  echo "aplicando $f"
  $MYSQL < "$f" || { echo "ERRO em $f — parar"; break; }
  $MYSQL -e "INSERT INTO schema_migrations (versao, arquivo, sha256) VALUES ('$v', '$(basename $f)', '$h') AS novo
             ON DUPLICATE KEY UPDATE sha256 = novo.sha256;"
done
```

Conferência:

```bash
$MYSQL -e "SELECT versao, arquivo, sha256 FROM schema_migrations WHERE versao >= '010' ORDER BY versao;
           SELECT chave, valor, tipo FROM parametro ORDER BY chave;          -- 5 linhas
           SHOW GRANTS FOR 'apm_area'@'%';"
docker compose exec area-associado python -m scripts.db_check
#  esperado: GRANT UPDATE (colunas) em solicitacao, job_execucao, comunicacao_evento e notificacao (lida_em);
#  nada em solicitacao_evento, comunicacao_envio, comunicacao_supressao, fila_ligacao, faq,
#  texto_sistema, parametro; "resultado : conforme".
```

Em até 60 s (cache da prontidão), `GET /api/v1/sessao` passa a devolver `recursos: {"solicitacoes": true,
"ajuda": true}` e a SPA deixa de mostrar "em construção" nessas rotas.

**Antes de aplicar**, a área segue no ar: `app/prontidao.py` verifica as tabelas (cache 60 s; falha de
leitura = indisponível por 15 s), `GET /sessao` devolve `recursos {solicitacoes: false, ajuda: false}` e
`solicitacoes_aguardando: 0`, e as rotas de solicitações/FAQ respondem `503 recurso_indisponivel` (o
contato da Central funciona sem migração). **Depois de aplicar**, a Central passa a ter horário e
telefone na Ajuda quando o operador preencher (P-44):

```sql
UPDATE parametro SET valor = '(11) 3188-6200' WHERE chave = 'central_telefone';
UPDATE parametro SET valor = 'Segunda a sexta, das 8h às 18h' WHERE chave = 'central_horario';
```

**Serviço de jobs:** só depois das cinco migrações e do `db_check` conforme — `docs/JOBS.md` §1 (sobe em
dry-run, `JOBS_APLICAR=0`). Sem a `011`, o serviço sobe e não executa nada (log `sql/011 ausente`).

Sem DELETE em nenhuma tabela nova; desfazer é coluna de estado. O pedido de cancelamento
(`POST /ajuda/cancelamento`) continua atrás da flag `cancelamento_online` (desligada no seed da `009`).

### 2.5b Onda 2 — `sql/014_carteirinha_revogacao` (2026-10-30)

`ALTER TABLE associado`: `carteirinha_revogada_em`, `situacao_consultada_em`, `situacao_normalizada`
(`ativo|suspenso|cancelado|outro`), índice `ix_associado_situacao_consultada` e CHECK do par
situação/data (TI-45). **Nenhum GRANT novo** (UPDATE em `associado` já vem da `005`). O CHECK obriga
`ALGORITHM=COPY`: a tabela é reconstruída e o upsert do login espera alguns segundos — janela de pouco
tráfego, snapshot antes. **Não reaplicável** (a segunda execução falha inteira com ERROR 3822; confira
`schema_migrations` sem `014`). Ensaiada em MySQL 8.4.11 descartável em 2026-10-30 (000→009 e 014,
UPDATE das colunas novas como `apm_area` ok, DELETE/ALTER recusados, CHECK do par recusa situação sem
data, `db_check` conforme, suíte `-m mysql` verde). sha256 esperado:
`9595dc359ed438489788c9bdec49f76603db02cf8a01fe98a2cdc38f035a6bab`. Mesmo laço do §2.4 com
`sql/014_carteirinha_revogacao.sql` e `v=014`. Até ser aplicada, a verificação pública segue no
comportamento anterior (só cache de perfil) e `GET /carteirinha` informa `revogada: false`.

## 3. Conferir

```bash
mysql --defaults-extra-file=$HOME/.rds-admin.cnf --ssl-mode=REQUIRED -e "
  SELECT user, host, ssl_type FROM mysql.user WHERE user = 'apm_area';
  SHOW GRANTS FOR 'apm_area'@'%';
  SELECT versao, arquivo, aplicado_em FROM area_associado.schema_migrations ORDER BY versao;"
```

Esperado: `ssl_type = ANY` (senão o `REQUIRE SSL` não pegou); grant de schema **sem** UPDATE/DELETE;
as migrations listadas.

Prova do append-only, conectado **como a aplicação** (depois do passo 4):

```bash
docker compose exec area-associado python - <<'EOF2'
from sqlalchemy import text
from app.database import engine
with engine.begin() as c:
    c.execute(text("INSERT INTO evento_log (categoria, tipo) VALUES ('request','prova_provisionamento')"))
    for sql in ("UPDATE evento_log SET tipo='x' WHERE tipo='prova_provisionamento'",
                "DELETE FROM evento_log WHERE tipo='prova_provisionamento'"):
        try:
            c.execute(text(sql)); print("FALHA: mutação permitida:", sql)
        except Exception as e:
            print("ok (recusado):", sql.split()[0], type(e).__name__)
EOF2
```

## 4. Subir a aplicação

```bash
docker compose up -d --build
docker compose ps                                   # (healthy)
docker compose exec area-associado python -m scripts.db_check
```

`db_check` imprime usuário efetivo, cifra TLS, grants, migrações registradas e partições; sai com 1
se não houver TLS, se o usuário for a conta master (ou sem política em `POLITICAS`), se os grants
violarem a ADR-0004 (UPDATE fora da allowlist do usuário, qualquer DELETE, ALL ou privilégio em outro
schema), se uma **tabela da allowlist existir sem o GRANT UPDATE** (ADR-0004 §6 — migração aplicada pela
metade) ou se `evento_log`/`evento_uso` não estiverem particionadas com a `008` registrada. Avisa (sem
falhar) quando a `008` ainda não foi aplicada e quando a última partição mensal termina em < 90 dias.
A allowlist lista **só tabelas já migradas**; tabela nova entra no mesmo commit da migração.

Este host não tem o plugin `buildx`: com BuildKit ligado o build falha. Construir com o
builder clássico (suporta o Dockerfile multi-stage):

```bash
DOCKER_BUILDKIT=0 docker compose build && docker compose up -d
docker compose exec area-associado python -m scripts.csp_check   # cabeçalhos de segurança
```

## 5. Cópia de segurança do `.env`

AWS Secrets Manager, região `sa-east-1`, segredo **`prod/area-associado/env`** (pares
chave/valor, rotação desligada). Toda mudança no `.env` é replicada lá, manualmente, pelo
console — a role da EC2 é somente leitura. Sem `SECRET_KEY`/`LOG_HASH_KEY` os hashes do
`evento_log` ficam incorrelacionáveis e as sessões ativas caem.
