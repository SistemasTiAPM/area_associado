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

`db_check` imprime usuário efetivo, cifra TLS e grants; sai com 1 se não houver TLS, se o
usuário for a conta master ou se os grants violarem a ADR-0004 (UPDATE fora da allowlist
`TABELAS_COM_UPDATE`, qualquer DELETE, ALL ou privilégio em outro schema).

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
