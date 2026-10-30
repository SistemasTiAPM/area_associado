#!/usr/bin/env bash
# =====================================================================
# Deploy da Minha APM no host (TI-74; docs/OPERACAO.md §1).
#
#   scripts/deploy.sh [--sem-pull] [--dry-run] [--manter N] [--timeout S]
#   scripts/deploy.sh --rollback [<tag>]
#
# Passos: git pull --ff-only → build (DOCKER_BUILDKIT=0, o host não tem buildx)
# → tag da imagem com o sha curto do commit → `docker compose up -d` → espera
# `healthy` → smoke (db_check, check_oidc, csp_check, curl /health público).
# Qualquer falha depois do `up` volta a imagem anterior e sobe de novo.
#
# Estado: a tag `area_associado-area-associado:<sha>` de cada deploy fica no
# daemon (as últimas N, padrão 5); o sha que estava no ar antes do deploy vai
# para `.deploy-anterior` (arquivo local, gitignored; só um sha, sem segredo).
#
# Nunca roda `up` se o `.env` não existir. Não aplica migração SQL: a `sql/NNN`
# é do operador (docs/PROVISIONAMENTO.md), ANTES do deploy que depende dela.
# =====================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
RAIZ=$(pwd)
IMAGEM=area_associado-area-associado
SERVICO=area-associado
CONTAINER=area_associado
URL_HEALTH=${URL_HEALTH:-https://minha.apm.org.br/health}
ESTADO="$RAIZ/.deploy-anterior"
LOCK=/tmp/area_associado-deploy.lock

PULL=1; DRY=0; MANTER=5; TIMEOUT=150; ROLLBACK=0; TAG_ALVO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --sem-pull) PULL=0 ;;
    --dry-run)  DRY=1 ;;
    --manter)   MANTER=${2:?}; shift ;;
    --timeout)  TIMEOUT=${2:?}; shift ;;
    --rollback) ROLLBACK=1; if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then TAG_ALVO=$2; shift; fi ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
  shift
done

log()  { printf '%s [deploy] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
erro() { printf '%s [deploy] ERRO: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; }
run()  { if [ "$DRY" = 1 ]; then log "(dry-run) $*"; else log "\$ $*"; "$@"; fi; }

# Um deploy por vez.
exec 9>"$LOCK"
if ! flock -n 9; then erro "outro deploy em andamento ($LOCK)"; exit 1; fi

[ -f "$RAIZ/.env" ] || { erro ".env ausente em $RAIZ — nada é iniciado sem ele"; exit 1; }
command -v docker >/dev/null || { erro "docker não encontrado"; exit 1; }

imagem_existe() { docker image inspect "$IMAGEM:$1" >/dev/null 2>&1; }
sha_em_execucao() {
  # sha da tag que o container atual usa (pela imagem, não pelo git: é o que está no ar).
  local id; id=$(docker inspect -f '{{.Image}}' "$CONTAINER" 2>/dev/null || true)
  [ -n "$id" ] || return 0
  docker image inspect -f '{{range .RepoTags}}{{println .}}{{end}}' "$id" 2>/dev/null \
    | sed -n "s|^$IMAGEM:\([0-9a-f]\{7,12\}\)$|\1|p" | head -1
}

esperar_healthy() {
  local fim=$(( $(date +%s) + TIMEOUT )) st
  while :; do
    st=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo ausente)
    case "$st" in
      healthy) log "container healthy"; return 0 ;;
      unhealthy|exited|dead) erro "container $st"; docker logs --tail 40 "$CONTAINER" 2>&1 | sed 's/^/    /' >&2; return 1 ;;
    esac
    if [ "$(date +%s)" -ge "$fim" ]; then erro "timeout (${TIMEOUT}s) esperando healthy (estado: $st)"; return 1; fi
    sleep 3
  done
}

smoke() {
  local ok=0
  for s in db_check check_oidc csp_check; do
    if docker compose exec -T "$SERVICO" python -m "scripts.$s" >/tmp/area_smoke_$s.log 2>&1; then
      log "smoke $s: ok"
    else
      erro "smoke $s falhou:"; tail -20 "/tmp/area_smoke_$s.log" | sed 's/^/    /' >&2; ok=1
    fi
  done
  if curl -fsS -o /dev/null --max-time 15 "$URL_HEALTH"; then log "smoke $URL_HEALTH: ok"
  else erro "smoke $URL_HEALTH falhou"; ok=1; fi
  return $ok
}

subir_tag() {
  # Aponta `latest` (a imagem que o compose usa) para a tag pedida e recria o container.
  run docker tag "$IMAGEM:$1" "$IMAGEM:latest"
  # --force-recreate: o compose só recria quando o ID da imagem muda; no rollback queremos sempre recriar
  run docker compose up -d --no-build --force-recreate "$SERVICO"
}

rollback_para() {
  local tag=$1
  if [ -z "$tag" ] || ! imagem_existe "$tag"; then
    erro "sem imagem para rollback (tag '${tag:-?}'). Tags disponíveis:"
    docker images "$IMAGEM" --format '    {{.Tag}}  {{.CreatedSince}}' >&2
    return 1
  fi
  log "ROLLBACK para $IMAGEM:$tag"
  subir_tag "$tag"
  [ "$DRY" = 1 ] || esperar_healthy
  log "rollback concluído — o código no disco continua no commit novo; investigue antes de repetir o deploy"
}

podar_tags() {
  # Mantém as N tags de sha mais recentes (nunca remove `latest` nem a em uso).
  local atual; atual=$(sha_em_execucao)
  docker images "$IMAGEM" --format '{{.Tag}} {{.CreatedAt}}' \
    | awk '$1 ~ /^[0-9a-f]{7,12}$/ {print $1}' \
    | tail -n +$((MANTER + 1)) \
    | while read -r t; do
        [ "$t" = "$atual" ] && continue
        run docker rmi "$IMAGEM:$t" >/dev/null || true
      done
}

# ------------------------------------------------------------- rollback manual
if [ "$ROLLBACK" = 1 ]; then
  [ -n "$TAG_ALVO" ] || TAG_ALVO=$(cat "$ESTADO" 2>/dev/null || true)
  rollback_para "$TAG_ALVO"
  exit $?
fi

# -------------------------------------------------------------------- deploy
SHA_ANTES=$(sha_em_execucao)
log "no ar agora: ${SHA_ANTES:-sem tag de sha (primeiro deploy pelo script)}"

if [ "$PULL" = 1 ]; then
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    erro "árvore com alterações locais — commit/stash antes, ou use --sem-pull"; git status --short >&2; exit 1
  fi
  run git pull --ff-only
fi
SHA=$(git rev-parse --short=8 HEAD)
log "commit alvo: $SHA ($(git log -1 --format='%s' | cut -c1-70))"

if [ -z "$SHA_ANTES" ] && [ "$DRY" = 0 ] && imagem_existe latest; then
  # Preserva a imagem atual sob uma tag para o rollback existir já no primeiro uso.
  docker tag "$IMAGEM:latest" "$IMAGEM:pre-$SHA"; SHA_ANTES="pre-$SHA"
  log "imagem atual guardada como $IMAGEM:$SHA_ANTES"
fi

log "build (DOCKER_BUILDKIT=0 — host sem buildx, P-26)"
if [ "$DRY" = 1 ]; then log "(dry-run) DOCKER_BUILDKIT=0 docker compose build $SERVICO"
else DOCKER_BUILDKIT=0 docker compose build "$SERVICO"; fi
run docker tag "$IMAGEM:latest" "$IMAGEM:$SHA"

[ "$DRY" = 1 ] || printf '%s\n' "$SHA_ANTES" > "$ESTADO"
run docker compose up -d --no-build "$SERVICO"

if [ "$DRY" = 1 ]; then log "(dry-run) esperar healthy → smoke → podar tags"; exit 0; fi

if ! esperar_healthy || ! smoke; then
  erro "deploy de $SHA reprovado"
  rollback_para "$SHA_ANTES" || exit 1
  exit 1
fi

podar_tags
log "deploy de $SHA concluído (anterior: ${SHA_ANTES:-—}; rollback: scripts/deploy.sh --rollback)"
