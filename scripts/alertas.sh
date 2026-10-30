#!/usr/bin/env bash
# =====================================================================
# Sinais de saúde da Minha APM nas últimas 24 h (TI-75; molde:
# login_associado/deploy/alertas.sh). Roda NO HOST, só leitura, e IMPRIME —
# ainda não envia nada: o envio por e-mail depende da credencial SMTP (P-27)
# e o webhook/monitor externo da conta do operador (P-61). Quando um dos
# dois existir, o `--email` passa a entregar o mesmo texto (hoje só avisa).
#
#   scripts/alertas.sh [--desde 24h] [--json] [--email destino@apm.org.br]
#
# Código de saída: 0 sem alerta, 2 com ao menos um alerta (cron pode agir),
# 1 erro do próprio script. Nunca imprime valor de segredo (compara hashes).
#
# Cron sugerido (ubuntu), depois de P-27/P-61:
#   5 7 * * * /home/ubuntu/area_associado/scripts/alertas.sh >> /home/ubuntu/area_alertas.log 2>&1
#
# Limitação herdada do IdP: `docker logs` recomeça quando o container é
# recriado (deploy) — no dia de um deploy a janela cobre só o período depois.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

DESDE=24h; JSON=0; EMAIL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --desde) DESDE=${2:?}; shift ;;
    --json)  JSON=1 ;;
    --email) EMAIL=${2:?}; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 1 ;;
  esac
  shift
done

# ------------------------------------------------------------- limiares
LIM_5XX_AREA=5        # respostas 5xx do gunicorn da área
LIM_5XX_PORTEIRO=20   # 5xx de TODOS os hosts (o log do porteiro não traz o host)
LIM_429=200           # 429 do porteiro (todos os hosts) — pico anormal de limite
LIM_TRACEBACK=0
LIM_CERT_DIAS=30
CONTAINERS="area_associado mcp_hub nginx_porteiro"
CERT=/home/ubuntu/nginx-proxy/sites-enabled/certs/origin.pem
SEGREDO=prod/area-associado/env
REGIAO=sa-east-1

ALERTAS=()
alerta() { ALERTAS+=("$*"); }
cnt() { printf '%s\n' "$1" | grep -cE -- "$2" || true; }   # grep -c, não -q (pipefail)

# ------------------------------------------------------------- coleta
LOG_AREA=$(docker logs --since "$DESDE" area_associado 2>&1 || true)
LOG_PORT=$(docker logs --since "$DESDE" nginx_porteiro 2>&1 || true)

n_5xx_area=$(cnt "$LOG_AREA" '" 5[0-9]{2}$')
n_traceback=$(cnt "$LOG_AREA" 'Traceback')
n_error=$(cnt "$LOG_AREA" ' ERROR ')
n_csrf=$(cnt "$LOG_AREA" 'csrf_recusado')
n_5xx_port=$(cnt "$LOG_PORT" '" 5[0-9]{2} ')
n_429_port=$(cnt "$LOG_PORT" '" 429 ')
n_444_port=$(cnt "$LOG_PORT" '" 444 ')

[ "$n_5xx_area" -gt "$LIM_5XX_AREA" ] && alerta "área: $n_5xx_area respostas 5xx (limite $LIM_5XX_AREA)"
[ "$n_traceback" -gt "$LIM_TRACEBACK" ] && alerta "área: $n_traceback Traceback(s) no log"
[ "$n_5xx_port" -gt "$LIM_5XX_PORTEIRO" ] && alerta "porteiro: $n_5xx_port respostas 5xx em todos os hosts (limite $LIM_5XX_PORTEIRO)"
[ "$n_429_port" -gt "$LIM_429" ] && alerta "porteiro: $n_429_port respostas 429 (limite $LIM_429) — ataque ou limite baixo demais"

# Saúde declarada dos containers.
SAUDE=""
for c in $CONTAINERS; do
  h=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$c" 2>/dev/null || echo ausente)
  SAUDE="$SAUDE $c=$h"
  [ "$h" = "healthy" ] || alerta "container $c: $h"
done

# /db-health pela rede interna (bloqueado na borda): status, uso_falhas, SPA.
DBH=$(docker exec area_associado curl -fsS --max-time 10 http://localhost:8000/db-health 2>/dev/null || echo '{}')
db_status=$(printf '%s' "$DBH" | jq -r '.status // "indisponivel"' 2>/dev/null || echo "indisponivel")
uso_falhas=$(printf '%s' "$DBH" | jq -r '.uso_falhas // -1' 2>/dev/null || echo -1)
spa_ok=$(printf '%s' "$DBH" | jq -r '.spa // false' 2>/dev/null || echo false)
db_tls=$(printf '%s' "$DBH" | jq -r '.ssl_cipher // "-"' 2>/dev/null || echo "-")
[ "$db_status" = "ok" ] || alerta "/db-health: $db_status"
[ "$uso_falhas" = "0" ] || alerta "/db-health: uso_falhas=$uso_falhas (evento_uso não gravou desde o último boot)"
[ "$spa_ok" = "true" ] || alerta "/db-health: SPA ausente na imagem"
[ "$db_tls" != "-" ] && [ "$db_tls" != "null" ] || { [ "$db_status" = "ok" ] && alerta "/db-health: conexão ao RDS sem cifra TLS"; }

# Certificado de origem (P-01).
cert_venc="-"; cert_org="-"
if [ -r "$CERT" ]; then
  cert_venc=$(openssl x509 -in "$CERT" -noout -enddate | cut -d= -f2)
  cert_org=$(openssl x509 -in "$CERT" -noout -subject | grep -o 'O *= *[^,]*' | head -1 || true)
  if ! openssl x509 -in "$CERT" -noout -checkend 0 >/dev/null; then alerta "certificado de origem VENCIDO em $cert_venc (P-01)"
  elif ! openssl x509 -in "$CERT" -noout -checkend $((LIM_CERT_DIAS*86400)) >/dev/null; then alerta "certificado de origem vence em < $LIM_CERT_DIAS dias ($cert_venc)"; fi
  case "$cert_org" in *TEMPORARIO*) alerta "certificado de origem ainda é o temporário (P-01)";; esac
else
  alerta "certificado de origem não legível em $CERT"
fi

# .env × cofre (P-36): compara só hashes dos pares KEY=VALUE ordenados; nunca imprime valores.
env_cofre="nao_verificavel"
if [ -r .env ]; then
  h_local=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | sort | sha256sum | cut -c1-16)
  if cofre=$(aws secretsmanager get-secret-value --region "$REGIAO" --secret-id "$SEGREDO" \
             --query SecretString --output text 2>/dev/null); then
    h_cofre=$(printf '%s' "$cofre" | jq -r 'to_entries[] | "\(.key)=\(.value)"' 2>/dev/null | sort | sha256sum | cut -c1-16)
    unset cofre
    if [ "$h_local" = "$h_cofre" ]; then env_cofre="igual"; else env_cofre="DIFERENTE"; alerta ".env difere do cofre $SEGREDO — replicar (P-36)"; fi
  else
    env_cofre="nao_verificavel (sem secretsmanager:GetSecretValue — P-59)"
  fi
  # Cópias antigas no disco são risco, não backup (P-36).
  n_bak=$(find . -maxdepth 1 -name '.env.bak-*' | wc -l)
  [ "$n_bak" -gt 0 ] && alerta "$n_bak arquivo(s) .env.bak-* no disco — apagar após replicar no cofre (P-36)"
fi

# job_execucao (ADR-0019 item 5; docs/JOBS.md §6). Lido pelo container WEB (tem a
# credencial do banco e o mesmo código): `python -m app.jobs --estado --json`.
# Alerta: execução com erro em 24 h; evento_log de erro gravado por job (3 falhas
# seguidas, espelho/comunicação `falhou`); job parado além do atraso máximo
# (só quando o serviço rodou nas últimas 24 h — desligado de propósito não alerta);
# container de jobs existente e não saudável. n/a sem a sql/011.
jobs_erro="n/a (tabela job_execucao ainda não existe)"
JE=$(docker exec area_associado python -m app.jobs --estado --json 2>/dev/null || true)
if [ -z "$JE" ] || ! printf '%s' "$JE" | jq -e . >/dev/null 2>&1; then
  jobs_erro="n/a (imagem sem app.jobs ou banco indisponível)"
elif printf '%s' "$JE" | jq -e '.erro' >/dev/null 2>&1; then
  jobs_erro="erro:$(printf '%s' "$JE" | jq -r '.erro')"; alerta "jobs: leitura de job_execucao falhou ($jobs_erro)"
elif [ "$(printf '%s' "$JE" | jq -r '.tabela')" = "true" ]; then
  n_err=$(printf '%s' "$JE" | jq '[.jobs[].erros_24h] | add // 0')
  n_ab=$(printf '%s' "$JE" | jq '[.jobs[].abortados_24h] | add // 0')
  ativo=$(printf '%s' "$JE" | jq -r '.ativo')
  jobs_erro="$n_err (abortados=$n_ab, serviço ativo=$ativo)"
  [ "$n_err" -gt 0 ] && alerta "jobs: $n_err execução(ões) com erro em 24 h: $(printf '%s' "$JE" | jq -r '[.jobs[] | select(.erros_24h > 0) | "\(.job)=\(.erros_24h)"] | join(", ")')"
  ev=$(printf '%s' "$JE" | jq -r '(.eventos_erro_24h // {}) | to_entries | map("\(.key)=\(.value)") | join(", ")')
  [ -n "$ev" ] && alerta "jobs: evento_log de erro em 24 h: $ev"
  if [ "$ativo" = "true" ]; then
    parados=$(printf '%s' "$JE" | jq -r '[.jobs[] | select(.parado) | "\(.job) (última ok \(.ultima_ok // "nunca"))"] | join(", ")')
    [ -n "$parados" ] && alerta "jobs: parado(s) além do atraso máximo: $parados"
  fi
fi
if docker inspect area_associado_jobs >/dev/null 2>&1; then
  hj=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' area_associado_jobs)
  SAUDE="$SAUDE area_associado_jobs=$hj"
  [ "$hj" = "healthy" ] || alerta "container area_associado_jobs: $hj (heartbeat parado?)"
fi

# ------------------------------------------------------------- saída
if [ "$JSON" = 1 ]; then
  jq -n --arg desde "$DESDE" --arg saude "$SAUDE" --arg env_cofre "$env_cofre" --arg cert_venc "$cert_venc" \
        --arg jobs "$jobs_erro" --argjson a5a "$n_5xx_area" --argjson tb "$n_traceback" --argjson er "$n_error" \
        --argjson csrf "$n_csrf" --argjson a5p "$n_5xx_port" --argjson a429 "$n_429_port" --argjson a444 "$n_444_port" \
        --arg dbs "$db_status" --arg uf "$uso_falhas" \
        --argjson alertas "$(printf '%s\n' "${ALERTAS[@]:-}" | jq -R . | jq -s 'map(select(length>0))')" \
        '{janela:$desde, contagens:{area_5xx:$a5a, area_traceback:$tb, area_error:$er, area_csrf_recusado:$csrf,
          porteiro_5xx:$a5p, porteiro_429:$a429, porteiro_444:$a444}, db_health:{status:$dbs, uso_falhas:$uf},
          containers:$saude, cert_origem_vence:$cert_venc, env_x_cofre:$env_cofre, jobs_erro_24h:$jobs, alertas:$alertas}'
else
  echo "Minha APM — sinais das últimas $DESDE ($(date '+%Y-%m-%d %H:%M %Z'))"
  echo "  área       : 5xx=$n_5xx_area traceback=$n_traceback error=$n_error csrf_recusado=$n_csrf"
  echo "  porteiro   : 5xx=$n_5xx_port 429=$n_429_port 444=$n_444_port (todos os hosts)"
  echo "  containers :$SAUDE"
  echo "  db-health  : status=$db_status uso_falhas=$uso_falhas spa=$spa_ok tls=$db_tls"
  echo "  cert origem: vence $cert_venc ($cert_org)"
  echo "  .env×cofre : $env_cofre"
  echo "  jobs c/erro: $jobs_erro"
  if [ ${#ALERTAS[@]} -eq 0 ]; then echo "  ALERTAS    : nenhum"
  else echo "  ALERTAS    : ${#ALERTAS[@]}"; for a in "${ALERTAS[@]}"; do echo "    - $a"; done; fi
fi

if [ -n "$EMAIL" ]; then
  echo "(--email $EMAIL: envio ainda não implementado — depende da credencial SMTP própria, P-27; o texto acima é o corpo previsto)" >&2
fi

[ ${#ALERTAS[@]} -eq 0 ] && exit 0 || exit 2
