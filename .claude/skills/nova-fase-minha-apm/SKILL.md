---
name: nova-fase-minha-apm
description: Checklist de prontidão para abrir, executar e fechar uma fase ou entrega da Minha APM (área do associado da APM) — plano com personas e aprovação, migração sql/NNN com GRANT UPDATE justificado e allowlist do db_check, flag nova, ação nova no catálogo de evento_uso, testes (pytest com marcador mysql, Vitest, Playwright e2e com stub), build sem buildx, scripts de verificação, atualização de PENDENCIAS/CONCLUIDO e ADR quando a decisão muda. Use SEMPRE que o usuário pedir para "começar a fase N", "implementar P0x/B0x", "criar tabela/endpoint/tela nova", "subir isso em minha.apm.org.br", "fechar a entrega", ou quando uma tarefa TI-nn do levantamento for executada — mesmo que pareça pequena.
---

# Nova fase ou entrega na Minha APM

A área está **no ar e pública** (`minha.apm.org.br`, `APP_ENV=staging`, OIDC real, hub real só
leitura, SMTP simulado). Tudo o que sobe é visto pela agência e por qualquer associado. Por isso a
rotina abaixo existe: ela garante que nada ilustrativo vaze, que o banco continue append-only e
que o próximo a retomar o trabalho saiba o que aconteceu.

## 0. Antes de qualquer código: plano e aprovação

`CLAUDE.md` Sessão 4: alteração em autenticação/sessão, banco, API, integrações/jobs, segredos,
dependências, container/rede ou vhost **sempre** exige plano + aprovação explícita. O plano nomeia:

- os itens do levantamento que a fase absorve (`TI-nn` de `docs/LEVANTAMENTO-TECNICO-spec-v2.md`)
  e os `EXT-nn` que ela **não** espera (o que fica atrás de flag/stub);
- a persona de cada trecho (Sentinela, Atlas, Maestro, Integrador, Vitrine, Estivador);
- arquivos tocados, migrações, flags, ações de uso, impactos de segurança;
- as ADRs que a fase cria (decisão nova) — nunca editar ADR aceita.

Fast-path (sem plano): texto/CSS/doc; componente React que não toca `frontend/src/api/`, sessão,
CSRF nem `package.json`.

## 1. Banco (Atlas) — migração `sql/NNN_*.sql`

```bash
ls sql/ | tail -3                                   # próximo NNN (008+ está reservado no REQUISITOS §6)
sed -n 1,60p sql/005_associado.sql                  # molde: cabeçalho, CHECKs, GRANT na própria migração
grep -n "TABELAS_COM_UPDATE" -A 16 scripts/db_check.py
```

- Cabeçalho comentado com o quê/por quê e a ADR; `USE area_associado;`; `CREATE TABLE IF NOT EXISTS`;
  `DATETIME(6)` em UTC; chave do associado `contact_id CHAR(36)` + `sub_hash`; **nunca CPF**.
- JSON com `CHECK` contra chaves proibidas (molde `ck_detalhes_sem_segredo` em `sql/002`).
- Tabela mutável: `GRANT UPDATE ON area_associado.<tabela> TO 'apm_area'@'%'` **na própria
  migração**, com comentário de justificativa (ADR-0004); acrescente a tabela em
  `TABELAS_COM_UPDATE` no `scripts/db_check.py`. **DELETE nunca**: desfazer = coluna de estado.
- Trilhas (`evento_log`, `evento_uso`, `solicitacao_evento`, `onboarding_progresso`, importações,
  logs de status/comunicação) ficam só com INSERT.
- Sem TRIGGER/PROCEDURE (RDS sem SUPER).
- Ensaio num MySQL 8.4 descartável antes do commit, aplicando `sql/000` … `sql/NNN` em ordem, e
  a suíte `mysql` (`TESTE_DB_HOST=... python -m pytest -m mysql`).
- Entregar ao operador: arquivo + comando + sha256 (`docs/PROVISIONAMENTO.md` §2, mesmo laço
  `for v in NNN`). **Eu não aplico DDL em produção.**

## 2. Flags, eventos e limites (Maestro)

- Funcionalidade sem fonte real ou com dependência externa aberta nasce **atrás de flag**
  (ADR-0007): chave nova em `app/flags.py` (`FLAGS_CONHECIDAS`) + seed `ligada=0` na migração +
  espelho em `frontend/src/api/tipos.ts`; desligada = 404 `recurso_desligado` e UI oculta. Nada de
  "em breve" nem valor de exemplo.
- Ação nova de analytics = entrada no catálogo fechado de `app/uso.py` (+ `AcaoUi` em
  `frontend/src/lib/analytics.ts` se vier da UI); use o nome do evento da spec v2 quando houver
  equivalente (`docs/spec-v2/INDICE-IDS.md`, seção "Eventos de uso"). `uso.registrar` roda depois
  do commit do negócio, nunca lança.
- Rota nova: dependências na ordem sessão → CSRF (`exigir_csrf`) → flag → limite de taxa
  (`app/limites.py`, lembrando que é por processo e há 2 workers) → `run_in_threadpool` para SQL
  e hub. Erro sempre no contrato `{erro, mensagem, request_id, detalhes?}` (`app/api/erros.py`).
- Rota pública nova → `limit_req` no vhost; rota interna nova → `return 403` no vhost
  (`deploy/nginx_porteiro/area_associado.conf.example` e o arquivo real em
  `/home/ubuntu/nginx-proxy/sites-enabled/`).

## 3. Integrações e jobs (Integrador)

Fonte ou parceiro novo → skill `integracao-terceiro-minha-apm`. Job novo → `app/jobs/` (serviço
`area-associado-jobs`, mesma imagem), rastro em `job_execucao`, lock, idempotência, nunca no
processo web.

## 4. Frontend (Vitrine)

- Tela nova segue o mockup correspondente (ADR-0017; sem mockup conhecido → EXT com a agência) e
  o "Precisa ter" da spec v2; textos na voz da spec §3.3 (Dr./Dra., sem exclamação, botão com
  verbo, erro diz o que fazer); estados vazio/erro/carregando obrigatórios (§15.4).
- Zero inline, zero CDN, ícones SVG próprios, tokens em `tokens.css`; links externos só pela
  allowlist de `frontend/src/lib/links.ts`.
- `npm run check` (typecheck, ESLint com regras de CSP, Vitest) roda no build; e2e Playwright +
  axe em `frontend/e2e/` com `AUTH_MODE=stub` num container local (`E2E_STUB_TOKEN`), e falha em
  qualquer `securitypolicyviolation`.

## 5. Build, verificação e publicação (Estivador)

```bash
cd /home/ubuntu/area_associado
python -m pytest -q                                   # unidades (sem rede/banco)
DOCKER_BUILDKIT=0 docker compose build && docker compose up -d     # host sem buildx (P-26)
docker compose ps                                     # (healthy)
docker compose exec area-associado python -m scripts.db_check      # TLS, grants, allowlist
docker compose exec area-associado python -m scripts.check_oidc
docker compose exec area-associado python -m scripts.check_hub <contact_id de teste>   # se tocou o hub
docker compose exec area-associado python -m scripts.csp_check
curl -sI https://minha.apm.org.br/ | head -1          # 200/303; /db-health deve dar 403
```

Mudou o `.env`? Replicar no Secrets Manager `prod/area-associado/env` (P-36) — ato do operador.

## 6. Fechar a entrega (obrigatório)

1. `docs/PENDENCIAS.md`: item resolvido sai; descoberta nova entra com dono, prioridade, "bloqueia"
   e estado; o bloco "Onde paramos" ganha a data.
2. `docs/CONCLUIDO.md`: entrada com data, commit, evidência (contagem de testes, saída dos
   scripts, URL).
3. `docs/LEVANTAMENTO-TECNICO-spec-v2.md`: marcar os `TI-nn` concluídos (estado ✅ e referência).
4. ADR nova se alguma decisão mudou; `CLAUDE.md` se mudou stack, fronteira de módulo ou regra.
5. Commit só quando o usuário pedir; mensagem no padrão `feat(escopo): …` / `docs: …`.

## Quando parar e perguntar

- A tarefa precisa de dado que só um `EXT-nn` entrega e não há flag/stub que a isole.
- Uma decisão `DEC-nn`/`DIV-nn` do levantamento ainda está aberta e muda o desenho.
- Precisa de UPDATE/DELETE fora da allowlist, de `UploadFile` como parâmetro, de `localStorage`
  para estado, de CDN, de inline, de CPF em qualquer tabela ou log: não faça; explique.
