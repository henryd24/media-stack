#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."; set -a; . ./.env; set +a
mkdir -p "$DATA_DIR"/torrents/{movies,tv} "$DATA_DIR"/media/{movies,tv}
for a in prowlarr sonarr radarr bazarr qbittorrent jellyseerr; do mkdir -p "$CONFIG_DIR/$a"; done
echo "OK: $DATA_DIR"
