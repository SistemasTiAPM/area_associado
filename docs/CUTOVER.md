# Virada de chave — da construção para o login pelo Login APM

A área nasce como Relying Party OIDC completa. "Virar a chave" é um passo de configuração,
não um deploy de código.

## Pré-requisitos (podem ser feitos a qualquer momento, sem impacto)

1. **Certificado de origem** do `nginx_porteiro` renovado (o atual é temporário e expira em
   10/10/2026 — derruba todos os sites em Full (strict)).
2. **DNS** `associado.apm.org.br` → EC2, proxied no Cloudflare.
3. **Client registrado no IdP** (no container do login):
   ```bash
   cd /home/ubuntu/login_associado
   docker compose exec login-associado python -m scripts.generate_client \
     --name "Área do Associado" --type confidential --client-id area-associado \
     --auth-method client_secret_basic \
     --redirect-uri https://associado.apm.org.br/auth/callback \
     --post-logout-redirect-uri https://associado.apm.org.br/ \
     --grant authorization_code \
     --scope "openid profile email cpf" --audience https://associado.apm.org.br --apply
   ```
   O segredo aparece **uma única vez**: vai direto para `OIDC_CLIENT_SECRET` no `.env` da área
   e para o Secrets Manager. Sem `refresh_token` de propósito: a área não chama API após o login.
4. `docker compose exec area-associado python -m scripts.check_oidc` → `OK` (com `AUTH_MODE=oidc`).
5. Round-trip validado em `APP_ENV=staging` + `AUTH_MODE=oidc` por alguém da allowlist do vhost:
   `/auth/login` → tela do Login APM mostrando "Área do Associado" → `/area` com nome/e-mail/CPF
   mascarado → Sair → volta a `https://associado.apm.org.br/`; `evento_log` com `login_ok` e `logout`.

## O passo único

```bash
cd /home/ubuntu/area_associado
sed -i 's|^APP_ENV=.*|APP_ENV=production|; s|^AUTH_MODE=.*|AUTH_MODE=oidc|; /^DEV_STUB_TOKEN=/d' .env
docker compose up -d                      # recria o container para reler o .env
docker compose ps                         # (healthy) — com stub em production ele NÃO sobe, por desenho
docker compose exec area-associado python -m scripts.check_oidc
# abrir ao público: remover/comentar o bloco allow/deny do vhost
sudo sed -i 's|^\(\s*\)\(allow\|deny\) |\1# \2 |' /home/ubuntu/nginx-proxy/sites-enabled/area_associado.conf
docker exec nginx_porteiro nginx -t && docker exec nginx_porteiro nginx -s reload
curl -sI https://associado.apm.org.br/ | head -1          # 200
curl -sI https://associado.apm.org.br/db-health | head -1 # 403
```

Depois: replicar o `.env` no Secrets Manager `prod/area-associado/env`, avisar a equipe para
**remover a linha do `hosts`** e encerrar os túneis SSH ([ACESSO-CONSTRUCAO.md](ACESSO-CONSTRUCAO.md)
passa a ser histórico), e trocar o `DEV_STUB_TOKEN` compartilhado por nada — ele deixa de existir.

## Rollback

Não existe "voltar ao stub" em produção (o `Settings` recusa). Rollback = fechar o site ao
público reativando a allowlist no vhost (`nginx -t && reload`) e corrigir a causa. Se o
problema for do IdP, o `evento_log` (`login_falha` com `detalhes.motivo`) diz onde.
