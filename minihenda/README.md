# Variante minihenda

Adaptación del stack original: Seerr (en vez de Jellyseerr), gluetun + ProtonVPN (WireGuard con NAT-PMP) para qBittorrent,
FlareSolverr, Recyclarr (perfiles TRaSH, incl. anime) y Caddy con subdominios por servicio.

Sin credenciales: copia `*.example` a `.env`, `vpn.env` y `recyclarr.env` y rellénalos.
Las carpetas `config/` y `data/` no se versionan.

Arranque: `scripts/init-dirs.sh`, `docker compose up -d`, luego `scripts/configure.py`.
Recyclarr usa alias de red (`sonarr-4k`, `sonarr-anime`, `radarr-4k`) porque ignora varias instancias con la misma URL.
