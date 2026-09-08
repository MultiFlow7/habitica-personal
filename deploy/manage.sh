#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
ROOT="$PWD"
mkdir -p backups releases
exec 9>"$ROOT/.operation.lock"
flock -n 9 || { echo 'Another deployment or backup is running.' >&2; exit 1; }

backup() {
  local target="backups/$(date -u +%Y%m%dT%H%M%S)-$(date +%s).archive.gz"
  if docker compose -f compose.yml exec -T mongo mongodump --db habitica --archive --gzip > "$target.tmp"; then
    mv "$target.tmp" "$target"
    echo "$target"
  else
    rm -f "$target.tmp"
    return 1
  fi
}

case "${1:-status}" in
  status)
    cat .env
    docker compose -f compose.yml ps
    docker stats --no-stream "$(docker compose -f compose.yml ps -q app)" "$(docker compose -f compose.yml ps -q mongo)"
    ;;
  backup) backup ;;
  logs) docker compose -f compose.yml logs --tail 80 -f ;;
  deploy|rollback)
    revision="${2:?Usage: ./manage.sh deploy COMMIT_SHA}"
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'A full commit SHA is required.' >&2; exit 1; }
    release="$ROOT/releases/$revision"
    test "$(cat "$release/REVISION")" = "$revision"
    (cd "$release" && sha256sum -c SHA256SUMS)
    test -f config.json
    docker load -i "$release/habitica-image.tar.gz"
    test "$(docker image inspect "habitica-personal:$revision" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$revision"
    previous=false
    if test -f .env; then
      backup
      cp .env .env.previous
      cp compose.yml compose.previous.yml
      previous=true
    fi
    cp "$release/compose.yml" compose.yml
    printf 'HABITICA_IMAGE=habitica-personal:%s\n' "$revision" > .env.next
    mv .env.next .env
    if docker compose -f compose.yml up -d --wait --wait-timeout 240 \
       && docker compose -f compose.yml exec -T app node deploy/check.mjs; then
      printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$1" "$revision" >> deployments.log
      cp "$release/manage.sh" "$ROOT/manage.sh.next"
      chmod 700 "$ROOT/manage.sh.next"
      mv "$ROOT/manage.sh.next" "$ROOT/manage.sh"
      echo "Release active: $revision"
    else
      docker compose -f compose.yml logs --tail 50 >&2
      if "$previous"; then
        cp .env.previous .env
        cp compose.previous.yml compose.yml
        docker compose -f compose.yml up -d --wait --wait-timeout 240
        echo 'Previous application version restored. Database was not restored.' >&2
      fi
      exit 1
    fi
    ;;
  *) echo 'Usage: ./manage.sh status|backup|logs|deploy SHA|rollback SHA' >&2; exit 1 ;;
esac
