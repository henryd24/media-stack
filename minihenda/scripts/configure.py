#!/usr/bin/env python3
"""Conecta Prowlarr <-> Sonarr/Radarr <-> qBittorrent por API. Idempotente.
Uso: python3 -I scripts/configure.py   (con el stack ya levantado y ~1 min de arranque)"""
import json, re, subprocess, sys, time, urllib.request, urllib.parse, http.cookiejar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
CONF = (ROOT / ENV["CONFIG_DIR"]).resolve()
import secrets
QB_USER = "henda"
QB_PASS_FILE = CONF / "qbittorrent" / ".qb_pass"

def api_key(app):
    t = (CONF / app / "config.xml").read_text()
    return re.search(r"<ApiKey>(\w+)</ApiKey>", t).group(1)

def call(base, key, method, path, body=None):
    req = urllib.request.Request(base + path, method=method, headers={"X-Api-Key": key, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = r.read(); return json.loads(d) if d else None

def wait(base, key, ver):
    for _ in range(60):
        try: call(base, key, "GET", f"/api/{ver}/system/status"); return
        except Exception: time.sleep(3)
    sys.exit(f"{base} no responde")

def fill(schema, values):
    for f in schema["fields"]:
        if f["name"] in values: f["value"] = values[f["name"]]
    return schema

def schema_for(base, key, ver, path, impl):
    return next(s for s in call(base, key, "GET", f"/api/{ver}/{path}/schema") if s["implementation"] == impl)

# ---- qBittorrent: credenciales + rutas
def setup_qbit():
    if QB_PASS_FILE.exists(): pw = QB_PASS_FILE.read_text().strip()
    else: pw = secrets.token_urlsafe(14)
    base = "http://127.0.0.1:8085"
    cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    def login(u, p):
        try:
            r = op.open(base + "/api/v2/auth/login", urllib.parse.urlencode({"username": u, "password": p}).encode()).read()
        except urllib.error.HTTPError:
            return False
        return r.strip() != b"Fails."
    for _ in range(40):
        try: urllib.request.urlopen(base, timeout=3); break
        except Exception: time.sleep(3)
    if not login(QB_USER, pw):
        logs = subprocess.run(["docker", "logs", "qbittorrent"], capture_output=True, text=True).stdout + ""
        m = re.findall(r"temporary password[^:]*: (\S+)", logs)
        if not m or not login("admin", m[-1]): sys.exit("qBittorrent: no pude entrar (¿ya configurado con otra clave? borra config/qbittorrent/.qb_pass y usa tu clave)")
    prefs = {"web_ui_username": QB_USER, "web_ui_password": pw, "save_path": "/data/torrents",
             "auto_tmm_enabled": True, "torrent_changed_tmm_enabled": True, "save_path_changed_tmm_enabled": True,
             "web_ui_host_header_validation_enabled": False, "web_ui_csrf_protection_enabled": False}
    op.open(base + "/api/v2/app/setPreferences", urllib.parse.urlencode({"json": json.dumps(prefs)}).encode())
    QB_PASS_FILE.write_text(pw); QB_PASS_FILE.chmod(0o600)
    print(f"qBittorrent OK  usuario={QB_USER}  clave en {QB_PASS_FILE}")
    return pw

def setup_arr(name, port, cat, root, catfield, qpw):
    base, key = f"http://127.0.0.1:{port}", api_key(name)
    wait(base, key, "v3")
    if not any(r["path"] == root for r in call(base, key, "GET", "/api/v3/rootfolder")):
        call(base, key, "POST", "/api/v3/rootfolder", {"path": root})
    if not any(c["name"] == "qBittorrent" for c in call(base, key, "GET", "/api/v3/downloadclient")):
        s = fill(schema_for(base, key, "v3", "downloadclient", "QBittorrent"),
                 {"host": "gluetun", "port": 8085, "username": QB_USER, "password": qpw, catfield: cat})
        s.update(name="qBittorrent", enable=True); call(base, key, "POST", "/api/v3/downloadclient", s)
    # hardlinks en vez de copiar
    mm = call(base, key, "GET", "/api/v3/config/mediamanagement"); mm["copyUsingHardlinks"] = True
    call(base, key, "PUT", f"/api/v3/config/mediamanagement/{mm['id']}", mm)
    print(f"{name} OK  root={root}  cliente=qBittorrent")
    return key

def setup_prowlarr(apps):
    base, key = "http://127.0.0.1:9696", api_key("prowlarr")
    wait(base, key, "v1")
    have = {a["name"] for a in call(base, key, "GET", "/api/v1/applications")}
    for name, port, k in apps:
        if name in have: continue
        s = fill(schema_for(base, key, "v1", "applications", name),
                 {"prowlarrUrl": "http://prowlarr:9696", "baseUrl": f"http://{name.lower()}:{port}", "apiKey": k, "syncLevel": "fullSync"})
        s.update(name=name, syncLevel="fullSync"); call(base, key, "POST", "/api/v1/applications", s)
    print("Prowlarr OK  apps=Sonarr,Radarr (los indexers los agregas tú en la UI; se sincronizan solos)")

if __name__ == "__main__":
    pw = setup_qbit()
    sk = setup_arr("sonarr", 8989, "tv", "/data/media/tv", "tvCategory", pw)
    rk = setup_arr("radarr", 7878, "movies", "/data/media/movies", "movieCategory", pw)
    setup_prowlarr([("Sonarr", 8989, sk), ("Radarr", 7878, rk)])
    print("\nFalta (UI): indexers en Prowlarr, Bazarr (proveedores+Sonarr/Radarr), Jellyseerr (login Jellyfin) y libraries en Jellyfin.")
