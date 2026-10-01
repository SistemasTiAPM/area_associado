-- =====================================================================
-- area_associado — schema e usuário no RDS MySQL (mysql-producao).
--
-- Rodar UMA VEZ, com a credencial administrativa do RDS (~/.rds-admin.cnf):
--   mysql --defaults-extra-file=~/.rds-admin.cnf --ssl-mode=REQUIRED < /tmp/prov.sql
--
-- NÃO edite o placeholder da senha neste arquivo versionado. Injete na
-- execução (ver docs/PROVISIONAMENTO.md):
--   SENHA=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 40)
--   sed "s/TROCAR_POR_SENHA_FORTE/${SENHA}/" sql/000_schema_e_usuario.sql > /tmp/prov.sql
-- e use a MESMA no DB_PASS do .env.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `area_associado`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Um schema por app, um usuário por app: um vazamento aqui não alcança o
-- schema do login_associado nem os demais. REQUIRE SSL + verificação do
-- certificado no cliente (database.py) fecham o canal dos dois lados.
CREATE USER IF NOT EXISTS 'apm_area'@'%'
    IDENTIFIED BY 'TROCAR_POR_SENHA_FORTE'
    REQUIRE SSL;

-- Sem DDL, sem UPDATE e sem DELETE no nível do schema — de propósito.
-- A aplicação nasce append-only: toda tabela nova é inalterável pela app até
-- que uma migração conceda UPDATE/DELETE POR TABELA, com justificativa.
-- Lição do apm-parceiros (sql/008), onde foi preciso revogar depois.
GRANT SELECT, INSERT, EXECUTE
    ON `area_associado`.* TO 'apm_area'@'%';

FLUSH PRIVILEGES;

-- Conferência:
--   SHOW GRANTS FOR 'apm_area'@'%';
--   SELECT user, host, ssl_type FROM mysql.user WHERE user = 'apm_area';
-- ssl_type deve vir 'ANY'. Se vier vazio, o REQUIRE SSL não foi aplicado e a
-- conexão poderia cair para texto claro.
