#!/bin/bash
# VM 上で実行する。Postgres は localhost だけにする。5432 は外へ開かない。
set -euo pipefail

ROOT=/home/ubuntu/signal-nexus
ENV_FILE=/home/ubuntu/analytics.env
cd "$ROOT"
echo "analytics-vm start"

SITE_FILE=/home/ubuntu/site.env
if [[ ! -f "$ENV_FILE" ]]; then
  echo "analytics.env is missing" >&2
  exit 1
fi
if [[ ! -f "$SITE_FILE" ]]; then
  echo "site.env is missing" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$SITE_FILE"
set +a
if [[ -z "${RENDER_HEALTH_URL:-}" || -z "${CADDY_SITE_ADDRESS:-}" ]]; then
  echo "site.env is missing RENDER_HEALTH_URL or CADDY_SITE_ADDRESS" >&2
  exit 1
fi

apt_get() {
  local attempt output status
  for attempt in $(seq 1 6); do
    echo "apt-get $* (attempt ${attempt})"
    set +e
    output=$(sudo -n DEBIAN_FRONTEND=noninteractive timeout 120 apt-get -o Dpkg::Lock::Timeout=30 "$@" 2>&1)
    status=$?
    set -e
    printf '%s\n' "$output"
    if [[ "$status" -eq 0 ]]; then
      return 0
    fi
    if [[ "$status" -eq 124 ]]; then
      echo "apt-get timed out on attempt ${attempt}" >&2
      return 124
    fi
    if ! printf '%s\n' "$output" | grep -q 'Could not get lock'; then
      return "$status"
    fi
    echo "apt-get failed on attempt ${attempt}; waiting for the dpkg lock" >&2
    sleep 10
  done
  return 1
}

stop_stale_apt() {
  if ! pgrep -x apt-get >/dev/null 2>&1; then
    return 0
  fi
  echo "stopping a stalled apt-get"
  ps -ef | grep '[a]pt-get' || true
  sudo -n pkill -9 -x apt-get || true
  sudo -n pkill -9 -f 'DEBIAN_FRONTEND=noninteractive apt-get' || true
  sleep 2
}

packages_ready() {
  command -v python3 >/dev/null || return 1
  python3 -c 'import venv' || return 1
  command -v psql >/dev/null || return 1
  command -v curl >/dev/null || return 1
}

continue_without_apt() {
  if packages_ready; then
    echo "apt-get did not finish; installed packages are already present"
    return 0
  fi
  return 1
}

caddy_list=/etc/apt/sources.list.d/caddy-stable.list
if [[ -f "$caddy_list" ]] && command -v caddy >/dev/null 2>&1; then
  sudo -n mv "$caddy_list" "${caddy_list}.disabled"
fi

stop_stale_apt
if packages_ready; then
  echo "packages already installed"
else
  if ! apt_get update; then
    continue_without_apt
  fi
  if ! apt_get install -y python3-venv python3-pip postgresql curl; then
    continue_without_apt
  fi
fi

listen=$(sudo -n -u postgres psql -tAc "SHOW listen_addresses" | tr -d '[:space:]')
case "$listen" in
  localhost | 127.0.0.1) ;;
  *)
    echo "postgres listen_addresses must stay on localhost" >&2
    exit 1
    ;;
esac

hba=$(sudo -n -u postgres psql -tAc "SHOW hba_file")
if ! sudo -n grep -Eq '^host[[:space:]]+all[[:space:]]+all[[:space:]]+127\.0\.0\.1/32[[:space:]]+(scram-sha-256|md5)([[:space:]]|$)' "$hba"; then
  echo "postgres password auth for 127.0.0.1 is missing" >&2
  exit 1
fi

if sudo -n -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'signalnexus'" | grep -q 1; then
  role_state=exists
else
  role_state=missing
fi
python3 -m deploy.configure_database role-sql "$ENV_FILE" "$ROOT/role.sql" "$role_state"
sudo -n -u postgres psql -v ON_ERROR_STOP=1 -f - < "$ROOT/role.sql"
rm -f "$ROOT/role.sql"

if ! sudo -n -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'signalnexus'" | grep -q 1; then
  sudo -n -u postgres createdb --owner=signalnexus signalnexus
fi

python3 -m deploy.configure_database database-url "$ENV_FILE"
chmod 600 "$ENV_FILE"

if ss -lnt | awk '$4 ~ /:5432$/ && $4 !~ /^(127\.0\.0\.1|\[::1\]):5432$/ { found = 1 } END { exit(found ? 0 : 1) }'; then
  echo "postgres is listening outside localhost" >&2
  exit 1
fi
if ! ss -lnt | awk '$4 ~ /^(127\.0\.0\.1|\[::1\]):5432$/ { found = 1 } END { exit(found ? 0 : 1) }'; then
  echo "postgres is not listening on localhost" >&2
  exit 1
fi

python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" -m deploy.futures_read "$ENV_FILE"

sudo -n cp deploy/systemd/signal-nexus-analytics-api.service /etc/systemd/system/
sudo -n cp deploy/systemd/signal-nexus-analytics-importer.service /etc/systemd/system/
sudo -n cp deploy/systemd/signal-nexus-render-keepalive.service /etc/systemd/system/
sudo -n cp deploy/systemd/signal-nexus-render-keepalive.timer /etc/systemd/system/
sudo -n systemctl daemon-reload
sudo -n systemctl enable signal-nexus-analytics-api signal-nexus-analytics-importer
sudo -n systemctl enable --now signal-nexus-render-keepalive.timer
sudo -n systemctl restart signal-nexus-analytics-api signal-nexus-analytics-importer

ready=0
for _ in $(seq 1 45); do
  if curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "analytics api health check failed" >&2
  sudo -n journalctl -u signal-nexus-analytics-api -n 120 --no-pager --output=short-iso >&2 || true
  exit 1
fi

sudo -n systemctl is-active --quiet signal-nexus-analytics-api
sudo -n systemctl is-active --quiet signal-nexus-analytics-importer
sudo -n systemctl is-active --quiet signal-nexus-render-keepalive.timer

if ! sudo -n iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport 443 -j ACCEPT; then
  sudo -n iptables -I INPUT -p tcp -m state --state NEW -m tcp --dport 443 -j ACCEPT
fi
sudo -n netfilter-persistent save

if ! command -v caddy >/dev/null 2>&1; then
  if [[ ! -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg ]]; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo -n gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  fi
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo -n tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt_get update
  apt_get install -y caddy
fi
sudo -n mkdir -p /etc/systemd/system/caddy.service.d
printf '%s\n' '[Service]' 'EnvironmentFile=/home/ubuntu/site.env' | sudo -n tee /etc/systemd/system/caddy.service.d/site.conf >/dev/null
sudo -n systemctl daemon-reload
sudo -n cp deploy/caddy/Caddyfile /etc/caddy/Caddyfile
sudo -n env CADDY_SITE_ADDRESS="$CADDY_SITE_ADDRESS" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo -n systemctl enable caddy
sudo -n systemctl restart caddy
sudo -n systemctl is-active --quiet caddy
