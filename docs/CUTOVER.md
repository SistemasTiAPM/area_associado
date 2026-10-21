# Virada de chave — da construção para o login pelo Login APM

A área nasce como Relying Party OIDC completa. "Virar a chave" é um passo de configuração,
não um deploy de código.

## Pré-requisitos (podem ser feitos a qualquer momento, sem impacto)

1. **Certificado de origem** do `nginx_porteiro` renovado (o atual é temporário e expira em
   10/10/2026 — derruba todos os sites em Full (strict)).
2. **DNS** `minha.apm.org.br` → EC2, proxied no Cloudflare. **Feito em 2026-10-19**; o site já
   está público em modo de construção ([ACESSO-CONSTRUCAO.md](ACESSO-CONSTRUCAO.md)).
3. **Client do IdP com o domínio novo.** Feito em 2026-10-20: `redirect_uri`
   `https://minha.apm.org.br/auth/callback`, post-logout `https://minha.apm.org.br/` e
   `audience` `https://minha.apm.org.br` (`scripts/update_client_uris` do `login_associado` para
   os URIs; o `audience` foi corrigido por UPDATE direto, o script não o cobre).
4. `docker compose exec area-associado python -m scripts.check_oidc` → `OK`. Feito em 2026-10-20:
   a área já roda com `AUTH_MODE=oidc` em `APP_ENV=staging`.
5. **Hub e SMTP reais**: `APP_ENV=production` não sobe com `HUB_MODE=stub` nem `SMTP_MODE=stub`.
   Exige a provisão do mcp_hub (P-02, P-05) e a credencial SMTP (P-27). A escrita no CRM é um
   passo à parte, depois da P-29 (abaixo): até lá `HUB_ESCRITA_HABILITADA=false` e o perfil fica
   só de leitura.
6. Round-trip validado em `APP_ENV=staging` + `AUTH_MODE=oidc`. Feito em 2026-10-20 com um
   usuário de teste do CRM (evidência em CONCLUIDO.md):
   `/auth/login` → tela do Login APM mostrando "Área do Associado" → `/area` com nome/e-mail/CPF
   mascarado → Sair → volta a `https://minha.apm.org.br/`; `evento_log` com `login_ok` e `logout`.

## O passo único

```bash
cd /home/ubuntu/area_associado
sed -i 's|^APP_ENV=.*|APP_ENV=production|; s|^HUB_MODE=.*|HUB_MODE=real|; s|^SMTP_MODE=.*|SMTP_MODE=real|' .env
# (AUTH_MODE=oidc e a remoção do DEV_STUB_TOKEN já foram feitos em 2026-10-20)
docker compose up -d                      # recria o container para reler o .env
docker compose ps                         # (healthy) — com stub em production ele NÃO sobe, por desenho
docker compose exec area-associado python -m scripts.check_oidc
# liberar indexação: remover o X-Robots-Tag de construção do vhost (o site já é público)
sed -i '/X-Robots-Tag "noindex, nofollow"/d' /home/ubuntu/nginx-proxy/sites-enabled/area_associado.conf
docker exec nginx_porteiro nginx -t && docker exec nginx_porteiro nginx -s reload
curl -sI https://minha.apm.org.br/ | head -1          # 200
curl -sI https://minha.apm.org.br/db-health | head -1 # 403
```

Depois: replicar o `.env` no Secrets Manager `prod/area-associado/env` e avisar a equipe e a
agência de que a faixa de demonstração sumiu: a partir daí o que o associado edita vai para o
CRM. [ACESSO-CONSTRUCAO.md](ACESSO-CONSTRUCAO.md) passa a ser histórico.

## Ligar a edição do cadastro (depois da P-29)

A conta `area-associado` no hub nasce só com `ferramentas:ler`. Pedir `escrever` antes de o hub
concedê-lo derruba até as leituras (`invalid_scope`), então a ordem é:

1. P-29 concluída (flows de `contact` mapeados) e P-05 com o papel de escrita.
2. No hub: marcar `ferramentas:escrever` na conta `area-associado`.
3. Na área: `HUB_ESCRITA_HABILITADA=true` no `.env`, `docker compose up -d`, e
   `docker compose exec area-associado python -m scripts.check_hub <contact_id de teste>` deve
   imprimir `token : ok (ferramentas:ler ferramentas:escrever)` e `edição : habilitada`.
4. Replicar o `.env` no Secrets Manager.

Desligar = o inverso (flag `false` primeiro, depois tirar o escopo no hub); a revogação no
hub vale em até 30 s mesmo com token já emitido.

## Rollback

Não existe "voltar ao stub" em produção (o `Settings` recusa). Rollback = fechar o site ao
público com um bloco `allow`/`deny all` no vhost (`nginx -t && reload`) e corrigir a causa. Se o
problema for do IdP, o `evento_log` (`login_falha` com `detalhes.motivo`) diz onde.
