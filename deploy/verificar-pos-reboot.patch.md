# Trecho para `/home/ubuntu/verificar-pos-reboot.sh` (P-19 / TI-72)

O script do host (criado em 18/09/2026, só leitura) ainda não conhece `area_associado`, `mcp_hub` e
`appapm-cron`, não testa `minha.`/`mcp.` e não olha a validade do certificado de origem. Este arquivo
traz as alterações prontas; **quem edita o script é o operador** (ele fica fora do repositório).

Aplicar: `cp ~/verificar-pos-reboot.sh ~/verificar-pos-reboot.sh.bak-$(date +%Y%m%d)` e fazer as quatro
edições abaixo; depois `bash -n ~/verificar-pos-reboot.sh && bash ~/verificar-pos-reboot.sh`.

## 1. Bloco `=== CONTAINERS ===` — contagem e lista

Hoje: `[ "$n" -ge 12 ]` e a lista termina em `totalpass-next-php`. Trocar por:

```bash
n=$(docker ps -q | wc -l); [ "$n" -ge 15 ] && chk ok "$n containers rodando" || chk x "$n containers rodando (esperado 15)"
uh=$(docker ps --filter health=unhealthy --format '{{.Names}}'); [ -z "$uh" ] && chk ok "nenhum unhealthy" || chk x "unhealthy: $uh"
st=$(docker ps --filter health=starting --format '{{.Names}}'); [ -n "$st" ] && echo "  (ainda iniciando: $st — rode de novo em 1 min)"
# area_associado_jobs entra aqui quando o serviço de jobs subir (Onda 2); até lá fica fora da lista.
for c in nginx_porteiro appapm appapm-php appapm-cron totalpass totalpass-php totalpass-cron apm-parceiros apm-parceiros-php login_associado form_filiacao totalpass-next totalpass-next-php mcp_hub area_associado; do
  s=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null); [ "$s" = "running" ] || chk x "$c: ${s:-inexistente}"
done
# Saúde declarada pelos próprios containers (HEALTHCHECK) dos serviços novos.
for c in area_associado mcp_hub; do
  h=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}sem-healthcheck{{end}}' "$c" 2>/dev/null)
  [ "$h" = "healthy" ] && chk ok "$c healthy" || chk x "$c: ${h:-inexistente}"
done
```

## 2. Bloco `=== SITES (pelo Cloudflare) ===` — hosts novos

Os dois novos respondem `200` em `/health` (a raiz de `mcp.` é 403 por desenho e a de `minha.` é 303
para o Login APM). Acrescentar **depois** do laço `for h in app totalpass parceiros login formulario`:

```bash
for h in minha mcp; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "https://$h.apm.org.br/health?cb=$(date +%s)")
  [ "$c" = "200" ] && chk ok "$h.apm.org.br /health HTTP $c" || chk x "$h.apm.org.br /health HTTP $c"
done
# Probes internos continuam bloqueados na borda (403) — se vier 200, o vhost perdeu o bloqueio.
c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "https://minha.apm.org.br/db-health")
[ "$c" = "403" ] && chk ok "minha: /db-health bloqueado na borda (403)" || chk x "minha: /db-health HTTP $c (esperado 403)"
```

## 3. Bloco novo `=== CERTIFICADO DE ORIGEM ===` (antes de `=== ERROS DESDE O BOOT ===`)

`origin.pem` é legível (0644). `-checkend` devolve 1 quando o certificado vence dentro do prazo.

```bash
echo; echo "=== CERTIFICADO DE ORIGEM ==="
CERT=/home/ubuntu/nginx-proxy/sites-enabled/certs/origin.pem
if [ -r "$CERT" ]; then
  venc=$(openssl x509 -in "$CERT" -noout -enddate | cut -d= -f2)
  org=$(openssl x509 -in "$CERT" -noout -subject | grep -o 'O *= *[^,]*' | head -1)
  if ! openssl x509 -in "$CERT" -noout -checkend 0; then chk x "origin.pem VENCIDO em $venc ($org) — P-01"
  elif ! openssl x509 -in "$CERT" -noout -checkend $((30*86400)); then chk x "origin.pem vence em < 30 dias: $venc"
  else chk ok "origin.pem válido até $venc"; fi
  case "$org" in *TEMPORARIO*) chk x "origin.pem ainda é o temporário ($org) — instalar o Origin CA (P-01)";; esac
  [ -e /home/ubuntu/nginx-proxy/sites-enabled/certs/temp.pem ] && echo "  (temp.pem ainda presente — remover após o P-01)"
else
  chk x "origin.pem não legível em $CERT"
fi
```

## 4. Bloco `=== ERROS DESDE O BOOT ===` — Tracebacks da área

Acrescentar ao final do bloco:

```bash
t=$(docker logs --since 10m area_associado 2>&1 | grep -c "Traceback" || true)
[ "$t" = "0" ] && chk ok "area_associado sem Traceback" || chk x "area_associado: $t Traceback(s)"
```

## Saída esperada após as edições (resumo)

`15 containers rodando`, `area_associado healthy`, `mcp_hub healthy`, `minha.apm.org.br /health HTTP 200`,
`mcp.apm.org.br /health HTTP 200`, `minha: /db-health bloqueado na borda (403)`. O bloco de certificado
**vai falhar** até o P-01 ser feito (`origin.pem VENCIDO em Oct 10 13:58:41 2026 GMT`, `TEMPORARIO`) —
é o comportamento desejado: o pós-reboot passa a cobrar a pendência.
