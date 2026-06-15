#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Herds relay — reproducible box setup / disaster recovery.
#
# Stands up the whole relay VM from scratch: a Python venv running `herds relay`,
# Caddy terminating TLS (on-demand certs) + reverse-proxying it, both under
# systemd with Restart=always and boot-enabled. Idempotent — safe to re-run.
#
# The Postgres URL is a SECRET — pass it via the environment, never commit it:
#
#   HERDS_DATABASE_URL='postgresql://…' sudo -E bash scripts/deploy-relay.sh
#
# ── Create the VM first (GCE example) ────────────────────────────────────────
#   gcloud compute addresses create herds-relay-ip --region us-central1
#   gcloud compute instances create herds-relay \
#       --zone us-central1-a --machine-type e2-small \
#       --image-family ubuntu-2204-lts --image-project ubuntu-os-cloud \
#       --address herds-relay-ip --tags http-server,https-server
#   gcloud compute firewall-rules create allow-web \
#       --allow tcp:80,tcp:443 --target-tags http-server,https-server
#   # copy this script over and run it:
#   gcloud compute scp scripts/deploy-relay.sh herds-relay:/tmp/ --zone us-central1-a
#   gcloud compute ssh herds-relay --zone us-central1-a --command \
#       "HERDS_DATABASE_URL='postgresql://…' sudo -E bash /tmp/deploy-relay.sh"
#
# ── Then point DNS at the box's public IP ────────────────────────────────────
#   relay.herds.run     A  <IP>
#   *.relay.herds.run   A  <IP>
#   (first HTTPS hit issues the cert via Caddy's on-demand TLS)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${HERDS_RELAY_DOMAIN:-relay.herds.run}"
EMAIL="${HERDS_RELAY_EMAIL:-teddy@spawnlabs.ai}"
PORT="${HERDS_RELAY_PORT:-8888}"
SPEC="${HERDS_INSTALL_SPEC:-herds[relay] @ git+https://github.com/teddyoweh/herds@main}"
: "${HERDS_DATABASE_URL:?set HERDS_DATABASE_URL (Neon Postgres) — provided at deploy time, never committed}"

[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo -E bash $0" >&2; exit 1; }

echo "→ system packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl gnupg \
    debian-keyring debian-archive-keyring apt-transport-https

echo "→ Caddy…"
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi

echo "→ herds[relay] into /opt/herds…"
python3 -m venv /opt/herds
/opt/herds/bin/pip install -q --upgrade pip
/opt/herds/bin/pip install -q --upgrade --force-reinstall "${SPEC}"

mkdir -p /var/lib/herds   # durable account store (HERDS_RELAY_STATE)

echo "→ Caddyfile…"
cat > /etc/caddy/Caddyfile <<CADDY
{
	email ${EMAIL}
	on_demand_tls {
		ask http://127.0.0.1:${PORT}/internal/tls-allow
	}
}

${DOMAIN}, *.${DOMAIN} {
	tls {
		on_demand
	}
	reverse_proxy 127.0.0.1:${PORT}
}
CADDY

echo "→ caddy auto-restart…"
mkdir -p /etc/systemd/system/caddy.service.d
cat > /etc/systemd/system/caddy.service.d/restart.conf <<'CONF'
[Service]
Restart=always
RestartSec=5
CONF

echo "→ herds-relay unit…"
cat > /etc/systemd/system/herds-relay.service <<UNIT
[Unit]
Description=Herds Relay
After=network-online.target
Wants=network-online.target

[Service]
Environment=HERDS_RELAY_STATE=/var/lib/herds/relay.json
ExecStart=/opt/herds/bin/herds relay --port ${PORT} --domain ${DOMAIN}
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
UNIT

echo "→ database secret (env drop-in, 0600)…"
mkdir -p /etc/systemd/system/herds-relay.service.d
( umask 077; cat > /etc/systemd/system/herds-relay.service.d/database.conf <<DBCONF
[Service]
Environment="HERDS_DATABASE_URL=${HERDS_DATABASE_URL}"
DBCONF
)
chmod 600 /etc/systemd/system/herds-relay.service.d/database.conf

echo "→ enable + (re)start…"
systemctl daemon-reload
systemctl enable --now herds-relay caddy
systemctl restart herds-relay caddy
sleep 3

echo
echo "✓ herds-relay=$(systemctl is-active herds-relay)  caddy=$(systemctl is-active caddy)"
echo "  local health: $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/healthz")"
echo
echo "Point DNS at this box, then verify:"
echo "    ${DOMAIN}    A  <this IP>"
echo "  *.${DOMAIN}    A  <this IP>"
echo "    curl https://${DOMAIN}/healthz"
