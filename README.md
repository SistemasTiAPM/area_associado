# area_associado — Minha APM (Área do Associado)

Aplicação FastAPI atrás do `nginx_porteiro` (`associado.apm.org.br`), autenticada pelo
`login_associado` via OIDC. Arquitetura e regras: [CLAUDE.md](CLAUDE.md).

## Documentação

| Documento | Para quê |
|---|---|
| [docs/SPEC-minha-apm.md](docs/SPEC-minha-apm.md) | Interface "Minha APM": telas, tokens visuais, componentes, textos. Em UI, a spec vence. |
| [docs/REQUISITOS-minha-apm.md](docs/REQUISITOS-minha-apm.md) | Requisitos RF/RNF, integrações (IdP, mcp_hub, CRM, ERP, WordPress, TotalPass), modelo de dados, solicitações, perfil, flags, lacunas. |
| [docs/adr/](docs/adr/) | Decisões de arquitetura (SPA React + Vite, D365 via mcp_hub, UPDATE por tabela, foto no CRM, cache do site, flags, CSP...). |
| [docs/PENDENCIAS.md](docs/PENDENCIAS.md) | Backlog vivo com dono, prioridade e fase bloqueada, mais o roteiro das fases 1 a 8. |
| [docs/CONCLUIDO.md](docs/CONCLUIDO.md) | O que já foi entregue, com data e evidência. |
| [docs/PROVISIONAMENTO.md](docs/PROVISIONAMENTO.md) · [docs/CUTOVER.md](docs/CUTOVER.md) · [docs/ACESSO-CONSTRUCAO.md](docs/ACESSO-CONSTRUCAO.md) | Banco, virada de chave e acesso na fase de construção. |

**Estado:** Fase 0 (documentação) concluída. A SPA React (`frontend/`), a API `/api/v1`, a
integração com o `mcp_hub` e o serviço de jobs são o alvo das fases 1 a 8 e ainda não existem
no código. O que roda hoje é o esqueleto Jinja2 + OIDC descrito abaixo.

## Subir

```bash
cp .env.example .env && chmod 600 .env     # preencher; ver docs/PROVISIONAMENTO.md para o banco
docker compose up -d --build
docker compose ps                           # (healthy)
docker compose exec area-associado python -m scripts.db_check
docker compose exec area-associado python -m scripts.check_oidc   # com AUTH_MODE=oidc
```

Vhost: `deploy/nginx_porteiro/area_associado.conf.example` →
`/home/ubuntu/nginx-proxy/sites-enabled/area_associado.conf`, depois
`docker exec nginx_porteiro nginx -t && docker exec nginx_porteiro nginx -s reload`.

## Fase de construção (até a virada)

Sem DNS e sem acesso público: entrada **só por túnel SSH** e login de construção.
Regras e passo a passo: [docs/ACESSO-CONSTRUCAO.md](docs/ACESSO-CONSTRUCAO.md).

## Modos de autenticação

- `AUTH_MODE=oidc` — produção. Login no `login.apm.org.br`, callback em `/auth/callback`.
- `AUTH_MODE=stub` — construção de telas, só com `APP_ENV` ≠ `production` e `DEV_STUB_TOKEN`.
  Em produção o container se recusa a subir. Virada: [docs/CUTOVER.md](docs/CUTOVER.md).

## Testes (na imagem, sem rede)

```bash
docker run --rm -v "$PWD:/app:ro" -w /app -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint sh area_associado-area-associado:latest \
  -c "pip install -q --user -r requirements-dev.txt && python -m pytest -p no:cacheprovider"
```

## Operação

- Banco: `docs/PROVISIONAMENTO.md` (schema, usuário `REQUIRE SSL`, migrações, prova append-only).
- `.env` replicado no AWS Secrets Manager `prod/area-associado/env` a cada mudança.
- Probes internos (403 no edge): `/db-health` (usuário, cifra TLS), `/auth-health` (modo, kids do JWKS).
