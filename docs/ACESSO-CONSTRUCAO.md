# Regras de acesso — fase de construção (até a virada de chave)

Válido enquanto `AUTH_MODE=stub` e `APP_ENV=staging`. Revogado pelo procedimento de
[CUTOVER.md](CUTOVER.md); depois disso este documento vira histórico.

## Quem acessa e como

| Situação | Regra |
| --- | --- |
| DNS `associado.apm.org.br` | **Não existe ainda.** Não criar até a virada. |
| Acesso pela internet | **Bloqueado.** O Security Group só aceita 80/443 das faixas do Cloudflare, e sem DNS o Cloudflare não roteia para cá. |
| Acesso da equipe | **Somente por túnel SSH** até o `nginx_porteiro` (abaixo). |
| Login na área | **Somente o login de construção** (`AUTH_MODE=stub`): token `DEV_STUB_TOKEN` do `.env` + nome, e-mail e um CPF de 11 dígitos (vira só a máscara). Não há consulta ao CRM nem ao Login APM. |
| Login pelo Login APM | **Desligado nesta app** (`/auth/callback` responde 404 em stub). O client `area-associado` já está registrado no IdP e o segredo já está no `.env`; nada precisa ser feito lá na virada. |
| Dados reais de associado | **Nenhum.** O que entra no stub é o que o desenvolvedor digitar; não usar CPF/e-mail reais de terceiros. |
| Produção | **Impossível por desenho**: `AUTH_MODE=stub` com `APP_ENV=production` impede o container de subir (`app/config.py`). |

## Acesso pela sua máquina

```bash
# túnel: porta local 8443 → porta 443 do porteiro na EC2
ssh -N -L 8443:127.0.0.1:443 ubuntu@15.228.223.178
```

No arquivo `hosts` da sua máquina (`/etc/hosts` no Linux/macOS,
`C:\Windows\System32\drivers\etc\hosts` no Windows):

```
127.0.0.1  associado.apm.org.br
```

Abrir **`https://associado.apm.org.br:8443/`** e aceitar o aviso de certificado (é o Origin CA
do Cloudflare, confiável só para o Cloudflare). Tem de ser HTTPS: o cookie de sessão é `Secure`.

Ao terminar, remover a linha do `hosts` — senão, depois da virada, o navegador continuará
indo para o túnel em vez do site real.

## Token de construção

- Está em `DEV_STUB_TOKEN` no `.env` (`chmod 600`, só o usuário `ubuntu` lê).
- Compartilhar apenas com quem desenvolve a área, por canal privado. Nunca em chat, ticket ou commit.
- Para trocar: gerar outro (`python3 -c "import secrets; print(secrets.token_urlsafe(36))"`),
  atualizar o `.env` e `docker compose up -d`. Sessões abertas continuam até expirar.
- Token errado é auditado em `evento_log` (`login_stub_falha`); login certo, em `login_stub`.

## Como o código chega ao container

O código é copiado para a imagem (sem bind-mount). Depois de editar `app/`:

```bash
cd /home/ubuntu/area_associado
docker compose up -d --build
docker compose ps        # (healthy)
```

Testes (sem rede, dentro da imagem):

```bash
docker run --rm -v "$PWD:/app:ro" -w /app -e HOME=/tmp --entrypoint sh \
  area_associado-area-associado:latest \
  -c "pip install -q --user pytest==8.3.4 && python -m pytest -p no:cacheprovider"
```

## O que NÃO fazer nesta fase

- Não publicar porta no `docker-compose.yml` nem abrir o SG: o túnel já resolve.
- Não ligar `AUTH_MODE=oidc` "para testar" sem o DNS: o IdP redireciona para
  `https://associado.apm.org.br/auth/callback`, que ainda não resolve.
- Não descomentar o bloco `allow/deny` do vhost sem preencher os IPs: `deny all` sozinho fecha
  tudo, inclusive o túnel (o IP visto pelo nginx no túnel é `127.0.0.1`).
- Não guardar CPF completo, tokens ou segredos em sessão, log ou `evento_log` (regras 4 e 8 do
  `CLAUDE.md`).
