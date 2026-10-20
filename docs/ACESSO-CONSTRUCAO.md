# Regras de acesso — fase de construção (até a virada)

Válido enquanto `APP_ENV=staging` com hub do CRM e e-mail simulados. A virada
([CUTOVER.md](CUTOVER.md)) revoga estas regras; depois disso este documento vira histórico.

**Desde 2026-10-20 a entrada é pelo Login APM** (`AUTH_MODE=oidc`). O login de construção
(token compartilhado) acabou: `DEV_STUB_TOKEN` não existe mais no `.env`. O ambiente continua
**público em `https://minha.apm.org.br`**, para a agência de marketing e a equipe acompanharem o
progresso.

## Quem acessa e como

| Situação | Regra |
| --- | --- |
| Endereço | **`https://minha.apm.org.br`**: DNS na Cloudflare (proxied), vhost `area_associado.conf` no porteiro, sem allowlist de IP. |
| Indexação | Bloqueada: o vhost envia `X-Robots-Tag: noindex, nofollow` em toda resposta. Sai na virada. |
| Entrada | `/` leva direto ao **Login APM** (`login.apm.org.br`) e volta para `/area`. Não há página própria de login. Quem já está logado no Login APM entra direto (SSO). Sair encerra a sessão no IdP também e volta ao formulário do Login APM. |
| Quem entra | **Qualquer conta do Login APM** com situação associativa válida (o escopo `carteirinha` exige tipo e situação; sem eles o login é recusado, ADR-0016). |
| Agência | Entra com **contatos de teste no CRM** (P-37): o CRM admin cria contatos com situação ativa e a agência faz o cadastro normal no Login APM com eles. Nenhuma conta ou código de exceção na área. |
| Dados de associado | **Nome, tipo, situação, CRM e filiação são reais** (vêm do Login APM/CRM). **Celular, telefones, endereço e foto são de demonstração**: o hub do CRM é simulado (`HUB_MODE=stub`) e nada do que o associado edita vai para o cadastro real. A troca de e-mail também não envia nada (`SMTP_MODE=stub`; o código aparece na própria resposta). A faixa amarela no topo avisa isso a todo logado. |
| Produção | **Impossível por desenho**: `APP_ENV=production` com hub ou SMTP simulados impede o container de subir (`app/config.py`). |
| Rotas internas | `/db-health`, `/auth-health`, `/docs`, `/redoc` e `/openapi.json` respondem 403 na borda. |

## Observações para quem testa

- Use um navegador comum. A Cloudflare barra clientes de script com user-agent genérico
  (`Python-urllib`, por exemplo) com um 403 próprio, que não vem da aplicação.
- Telas que ainda não existem aparecem como "em construção".
- Login e logout ficam em `evento_log` (`login_ok`, `login_falha` com o motivo, `logout`), só com
  HMAC da identidade.

## Como o código chega ao container

O código é copiado para a imagem (sem bind-mount). Depois de editar:

```bash
cd /home/ubuntu/area_associado
DOCKER_BUILDKIT=0 docker compose build    # o host não tem buildx (P-26); o build roda o check do front
docker compose up -d
docker compose ps                          # (healthy)
docker compose exec area-associado python -m scripts.db_check
docker compose exec area-associado python -m scripts.check_oidc
```

Testes: ver [README.md](../README.md#testes). O e2e Playwright em `frontend/e2e/` continua
usando um container local com `AUTH_MODE=stub`: o modo stub existe só para testes automatizados.

## O que NÃO fazer nesta fase

- Não ligar `HUB_MODE=real` sem a provisão do hub (P-02, P-05) e sem a P-29: com a escrita
  liberada, o que o associado digitar vai para o CRM de verdade.
- Não voltar para `AUTH_MODE=stub` no ambiente público: o token seria compartilhado de novo.
- Não publicar porta no `docker-compose.yml`: o acesso é pelo porteiro.
- Não guardar CPF completo, tokens ou segredos em sessão, log ou `evento_log` (regras 4 e 8 do
  `CLAUDE.md`).
