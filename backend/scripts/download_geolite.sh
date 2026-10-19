#!/usr/bin/env sh
# Download MaxMind GeoLite2-City into backend/data/ (needs a free MaxMind account).
#   MAXMIND_ACCOUNT_ID=123456 MAXMIND_LICENSE_KEY=xxxx ./scripts/download_geolite.sh
# Safe to run in a build step: without credentials it just skips (geo shows "Unknown").
set -eu
cd "$(dirname "$0")/.."

if [ -z "${MAXMIND_ACCOUNT_ID:-}" ] || [ -z "${MAXMIND_LICENSE_KEY:-}" ]; then
  echo "MAXMIND_ACCOUNT_ID / MAXMIND_LICENSE_KEY not set; skipping GeoLite2 download."
  exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -u "${MAXMIND_ACCOUNT_ID}:${MAXMIND_LICENSE_KEY}" \
  "https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz" \
  -o "$tmp/geolite.tar.gz"
tar -xzf "$tmp/geolite.tar.gz" -C "$tmp"
mkdir -p data
find "$tmp" -name 'GeoLite2-City.mmdb' -exec mv {} data/GeoLite2-City.mmdb \;
echo "Saved data/GeoLite2-City.mmdb"
