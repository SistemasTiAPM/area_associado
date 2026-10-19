# Regras de acesso — fase de construção (até a virada de chave)

Válido enquanto `AUTH_MODE=stub` e `APP_ENV=staging`. Revogado pelo procedimento de
[CUTOVER.md](CUTOVER.md); depois disso este documento vira histórico.

**Desde 2026-10-19 o ambiente é público em `https://minha.apm.org.br`**, para a agência de
marketing e a equipe acompanharem o progresso sem túnel nem VPN. Antes disso, o acesso era só
por túnel SSH, sem DNS.

## Quem acessa e como

| Situação | Regra |
| --- | --- |
| Endereço | **`https://minha.apm.org.br`**: DNS na Cloudflare (proxied), vhost `area_associado.conf` no porteiro, sem allowlist de IP. |
| Indexação | Bloqueada: o vhost envia `X-Robots-Tag: noindex, nofollow` em toda resposta. Sai na virada. |
| Quem vê o quê | Qualquer pessoa vê a página inicial e a tela de login de construção. **Só entra na área quem tem o token de construção.** |
| Login na área | **Somente o login de construção** (`AUTH_MODE=stub`): token `DEV_STUB_TOKEN` + nome, e-mail, um CPF de 11 dígitos (vira só a máscara) e uma persona (tipo de associado). Não há consulta ao CRM nem ao Login APM. |
| Login pelo Login APM | **Desligado nesta app** (`/auth/callback` responde 404 em stub). O client `area-associado` existe no IdP, mas com os endereços antigos (`associado.apm.org.br`): atualizar antes da virada (P-35). |
| Dados reais de associado | **Nenhum.** Hub do CRM e e-mail são simulados (`HUB_MODE=stub`, `SMTP_MODE=stub`): o perfil mostra celular e endereço fictícios, e o código de troca de e-mail aparece na própria resposta, sem envio. Não digitar CPF nem e-mail reais de terceiros. |
| Produção | **Impossível por desenho**: stub com `APP_ENV=production` impede o container de subir (`app/config.py`). |
| Rotas internas | `/db-health`, `/auth-health`, `/docs`, `/redoc` e `/openapi.json` respondem 403 na borda. |

## Token de construção

- Está em `DEV_STUB_TOKEN` no `.env` (`chmod 600`, só o usuário `ubuntu` lê).
- **Compartilhar só por canal privado** (nunca em chat aberto, ticket, e-mail em grupo ou commit),
  com quem desenvolve a área e com as pessoas nominadas da agência.
- Quem tem o token só enxerga dados de teste. Mesmo assim, troque o token quando alguém sair do
  projeto: gere outro (`python3 -c "import secrets; print(secrets.token_urlsafe(36))"`), atualize
  o `.env` e rode `docker compose up -d`. Sessões abertas continuam até expirar.
- Token errado é auditado em `evento_log` (`login_stub_falha`); login certo, em `login_stub`.
  `/auth/*` tem limite de 5 r/s por IP no vhost.
- Na virada o token deixa de existir.

## Observações para quem testa

- Use um navegador comum. A Cloudflare barra clientes de script com user-agent genérico
  (`Python-urllib`, por exemplo) com um 403 próprio, que não vem da aplicação.
- Telas que ainda não existem aparecem como "em construção".

## Como o código chega ao container

O código é copiado para a imagem (sem bind-mount). Depois de editar:

```bash
cd /home/ubuntu/area_associado
DOCKER_BUILDKIT=0 docker compose build    # o host não tem buildx (P-26); o build roda o check do front
docker compose up -d
docker compose ps                          # (healthy)
docker compose exec area-associado python -m scripts.db_check
```

Testes: ver [README.md](../README.md#testes).

## O que NÃO fazer nesta fase

- Não ligar `AUTH_MODE=oidc` "para testar": o client do IdP ainda aponta para o endereço antigo
  (P-35), e com o hub simulado associados reais veriam dados fictícios como se fossem deles.
- Não publicar porta no `docker-compose.yml`: o acesso é pelo porteiro.
- Não guardar CPF completo, tokens ou segredos em sessão, log ou `evento_log` (regras 4 e 8 do
  `CLAUDE.md`).
