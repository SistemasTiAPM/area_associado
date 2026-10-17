# ADR-0006: Site WordPress por leitura direta do MySQL, com cache local

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0013

## Contexto

Notícias e eventos exibidos na "Minha APM" vêm do site institucional `www.apm.org.br`, um
WordPress mantido pela agência Planeta W e hospedado na Locaweb. O banco é o `portal_apm` em
`portal_apm.vpshost5693.mysql.dbaas.com.br`, prefixo de tabelas `pw_portal_`, **fora do RDS** e
fora da VPC da APM. Os *post types* relevantes são `post` (notícias), `evento`, `banner-header` e
`regional`.

O `appapm` já lê esse banco diretamente, **sem TLS**, em `appapm/src/config.php:134-146`, com o
usuário `portal_apm@%` — marcado como **vazado** em `/home/ubuntu/PENDENCIAS_AWS.md` (senha
rotacionada em 2026-09-10, mas o grant continua aberto a todas as tabelas e a qualquer host). As
consultas já estão prontas e validadas em
`appapm/src/includes/{eventos,banners,regionais}_portal_service.php`, o que reduz o risco de
interpretar errado o esquema do WordPress (`postmeta` serializado, `yoast_indexable` para imagens
e descrições).

O usuário decidiu pela **leitura direta do MySQL `portal_apm`**, descartando a WP REST API (que
depende da Planeta W expor os tipos com `show_in_rest`) e os endpoints do `appapm`. Cabe a esta
ADR registrar as condições para que essa leitura não repita o perfil de risco do `appapm`.

## Decisão

1. **Somente o serviço de jobs** (`docker-compose` serviço `jobs`, mesma imagem, comando
   `python -m app.jobs`) abre conexão com a Locaweb. O processo web **nunca** importa o módulo
   `app/integracoes/portal_wp.py` nem possui as variáveis `WP_DB_*` (não são passadas ao
   serviço `web` no compose).
2. **Usuário novo e somente leitura** no `portal_apm` (pendência P-07): `apm_area_ro`, com
   `SELECT` **apenas** em `pw_portal_posts`, `pw_portal_postmeta`, `pw_portal_terms`,
   `pw_portal_term_taxonomy`, `pw_portal_term_relationships` e `pw_portal_yoast_indexable`;
   restrito por host ao IP de saída da APM, `REQUIRE SSL` quando a Locaweb suportar. O usuário
   `portal_apm` vazado não é reaproveitado.
3. **TLS**: `WP_DB_SSL = verify | required | off`. `verify` valida o certificado com
   `WP_DB_SSL_CA`; `required` exige cifra sem validar a cadeia; `off` é **proibido com
   `APP_ENV=production`**, salvo `WP_DB_ACEITO_SEM_TLS=1` — e nesse caso o boot grava em
   `evento_log` o evento `portal.sem_tls_aceito` e o `/db-health` expõe `portal_tls: off`.
   Validador em `config.py`.
4. Cada sessão do job executa `SET SESSION max_execution_time = 5000` (5 s) e usa
   `read_timeout=10`, `connect_timeout=5`; queries parametrizadas, `LIMIT` fixo (200 por tipo).
5. **Cache local** em `area_associado.noticia_cache` e `area_associado.evento_cache`:
   `wp_id`, `slug`, `titulo`, `resumo`, `url`, `imagem_url`, `categoria`, `publicado_em`,
   `inicio_em`/`fim_em` (eventos), `regional`, `ativo TINYINT`, `hash CHAR(64)`,
   `sincronizado_em`. Job a cada **15 min**: upsert por `wp_id` (só grava quando `hash` muda),
   marca `ativo = 0` o que sumiu da fonte, **nunca apaga** (ADR-0004) e **mantém a última
   cópia** se a Locaweb estiver fora — a área continua servindo o cache.
6. `imagem_url` só é aceita se o host estiver em `CSP_IMG_HOSTS` (ADR-0013); caso contrário a
   coluna fica `NULL` e a UI usa placeholder próprio. Conteúdo HTML de `post_content` **não** é
   importado; só `post_excerpt`/descrição Yoast, sanitizados para texto puro.
7. `WP_MODE = real | stub`; em `stub` o job lê `app/integracoes/fixtures/portal_*.json`.
   `stub` é proibido com `APP_ENV=production`.
8. A API da área (`GET /api/v1/noticias`, `GET /api/v1/eventos`) lê **só** do cache local;
   nunca consulta a Locaweb na requisição.

## Consequências

### Positivas
- Latência e disponibilidade da área independem da Locaweb; falha lá degrada para "dados de
  há X minutos", não para erro.
- O processo exposto ao público nunca tem credencial da Locaweb.
- Usuário de banco com escopo mínimo, substituindo o usuário vazado do `appapm` nesse uso.
- Reaproveita consultas já validadas pelo `appapm`.

### Negativas / riscos
- Acoplamento ao esquema interno do WordPress e ao prefixo `pw_portal_`; mudança de plugin
  (Yoast) ou de tema quebra o job. Mitigado por testes contra *dump* de fixture e por alerta
  em `evento_log` quando a sincronização falha 3 vezes seguidas.
- Depende de a Locaweb aceitar TLS e restrição por host (P-07); até lá a área roda em `stub`
  ou com `WP_DB_ACEITO_SEM_TLS=1` registrado.
- Conteúdo até 15 min desatualizado (aceito pelo usuário).
- Serviço `jobs` é um processo novo com conexão de saída para a internet; o firewall de
  egresso deve permitir só `vpshost5693.mysql.dbaas.com.br:3306`.

### Obrigações decorrentes
- P-07: criar `apm_area_ro`, restrição por host e TLS na Locaweb; registrar no
  `docs/PROVISIONAMENTO.md`.
- `scripts/portal_check.py`: valida usuário, grants (falha se houver tabela fora da lista ou
  qualquer privilégio além de `SELECT`), TLS efetivo e tempo de uma consulta de amostra.
- Compose: `WP_DB_*` só no serviço `jobs`; `web` não recebe essas variáveis (teste de
  configuração que falha se `Settings` do `web` tiver `WP_DB_HOST`).
- Migrações `sql/00N_noticia_cache.sql` e `sql/00N_evento_cache.sql` com `GRANT UPDATE`
  justificado.
- Testes: sanitização de resumo (sem HTML), rejeição de `imagem_url` fora de
  `CSP_IMG_HOSTS`, upsert idempotente por `hash`, `ativo=0` para itens sumidos, cache mantido
  quando a conexão falha.

## Alternativas descartadas

- **WP REST API (`/wp-json/wp/v2/`).** Depende de a Planeta W expor os *post types*
  customizados com `show_in_rest` e de controle de cache do lado deles; a APM não tem gestão
  sobre esse prazo.
- **Endpoints do `appapm`.** O BFF do aplicativo não serve notícias (só eventos, banners e
  regionais) e acoplaria a área ao ciclo de deploy e ao usuário vazado do `appapm`.
