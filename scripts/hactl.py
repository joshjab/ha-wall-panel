#!/usr/bin/env python3
"""Talk to Home Assistant for the wall-panel kit: SSH, websocket, REST, deploy, SIM cameras.

Connection details live in connection.yaml in the current folder (git-ignored; copy connection.example.yaml).
The long-lived access token is read from `token_file`, never from the command line or chat.

    hactl.py check                      verify SSH, `ha` CLI, REST and websocket all work
    hactl.py ssh '<command>'            run a command in the Terminal & SSH app
    hactl.py ws '<json>'                send one websocket command, print the result
    hactl.py backup "<name>"            full backup via `ha backups new`, then list it
    hactl.py hacs <repo_id> [...]       install HACS repositories by numeric GitHub id
    hactl.py deploy build/              copy a generated build into /config, then `ha core check`
    hactl.py sim-cameras panel.yaml [--dry-run]
                                        create Generic Camera entries for `sim` cameras
    hactl.py reload                     reload input helpers, templates, scripts, automations, themes

Requires: PyYAML, websocket-client.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parent.parent

# HACS repository ids (GitHub numeric ids) for the frontend pieces the panel uses.
HACS = {
    "ha-floorplan": "188323494",
    "kiosk-mode": "497319128",
    "layout-card": "156434866",
    "button-card": "146194325",
    "browser_mod": "194140521",
}


def conn() -> dict:
    # $WALLPANEL_CONNECTION, else ./connection.yaml (the owner's project folder), else the kit's own.
    candidates = [Path(os.environ["WALLPANEL_CONNECTION"])] if os.environ.get("WALLPANEL_CONNECTION") else \
        [Path.cwd() / "connection.yaml", KIT / "connection.yaml"]
    path = next((c for c in candidates if c.exists()), None)
    if path is None:
        sys.exit(f"missing connection.yaml: copy {KIT / 'connection.example.yaml'} into this folder and fill it in")
    c = yaml.safe_load(path.read_text())
    c["ssh_key"] = os.path.expanduser(c.get("ssh_key", "~/.ssh/ha_wall_panel_ed25519"))
    c["token_file"] = os.path.expanduser(c.get("token_file", "~/.config/ha-wall-panel/token"))
    c["ha_url"] = c["ha_url"].rstrip("/")
    return c


def token(c) -> str:
    """The long-lived access token: from $HA_TOKEN if set, else from token_file."""
    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"].strip()
    path = Path(c["token_file"])
    if not path.exists():
        sys.exit(f"no token: set HA_TOKEN or create {path} (chmod 600) holding only the token")
    return path.read_text().strip()


# --------------------------------------------------------------------------- transports

def ssh(cmd: str, stdin: bytes | None = None, check=True) -> str:
    c = conn()
    args = ["ssh", "-i", c["ssh_key"], "-p", str(c.get("ssh_port", 22)), "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
            f"{c.get('ssh_user', 'root')}@{c['ssh_host']}", cmd]
    r = subprocess.run(args, input=stdin, capture_output=True)
    if check and r.returncode != 0:
        sys.exit(f"ssh failed ({r.returncode}): {r.stderr.decode().strip()}")
    return r.stdout.decode()


def rest(method: str, path: str, body=None):
    c = conn()
    req = urllib.request.Request(c["ha_url"] + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token(c)}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def ws(msg: dict):
    import websocket  # websocket-client
    c = conn()
    url = re.sub(r"^http", "ws", c["ha_url"]) + "/api/websocket"
    sock = websocket.create_connection(url, timeout=180)
    sock.recv()
    sock.send(json.dumps({"type": "auth", "access_token": token(c)}))
    if json.loads(sock.recv()).get("type") != "auth_ok":
        sys.exit("websocket auth failed: check token_file")
    sock.send(json.dumps({**msg, "id": 1}))
    while True:
        reply = json.loads(sock.recv())
        if reply.get("id") == 1 and reply.get("type") == "result":
            break
    sock.close()
    if not reply.get("success"):
        sys.exit(f"websocket error: {reply.get('error')}")
    return reply.get("result")


# --------------------------------------------------------------------------- commands

def cmd_check():
    c = conn()
    print("ssh:      ", ssh("echo ok").strip())
    info = json.loads(ssh("ha core info --raw-json"))["data"]
    print("ha cli:   ", info["version"], "(update available)" if info.get("update_available") else "")
    cfg = rest("GET", "/api/config")
    print("rest:     ", cfg["version"], "|", cfg.get("time_zone"))
    comps = set(cfg["components"])
    print("hacs:     ", "installed" if "hacs" in comps else "MISSING — install HACS first")
    print("go2rtc:   ", "yes" if "go2rtc" in comps else "no")
    print("websocket:", len(ws({"type": "lovelace/resources"})), "dashboard resources")
    print("url:      ", c["ha_url"])


def cmd_backup(name: str):
    print(ssh(f'ha backups new --name "{name}"'))
    print(ssh("ha backups list"))


def cmd_hacs(ids: list[str]):
    for rid in ids:
        rid = HACS.get(rid, rid)
        ws({"type": "hacs/repository/download", "repository": str(rid)})
        print("installed", rid)
    for r in ws({"type": "lovelace/resources"}):
        print("resource:", r["url"])


def cmd_deploy(build: Path):
    for f in build.rglob("*.yaml"):  # HA's config check does not look at dashboard YAML
        yaml.safe_load(f.read_text())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for sub in ("dashboards", "packages", "themes", "www"):
            if (build / sub).exists():
                tar.add(build / sub, arcname=sub)
    ssh("cd /config && tar xf - --no-same-owner && chown -R root:root dashboards packages themes www",
        stdin=buf.getvalue())
    print(ssh("ha core check 2>&1 | tail -3"))
    print("deployed. Dashboard/asset changes: refresh the browser. Package changes: `hactl.py reload`.")


def cmd_reload():
    for svc in ("input_boolean", "input_number", "input_select", "template", "script", "automation"):
        rest("POST", f"/api/services/{svc}/reload", {})
        print("reloaded", svc)
    rest("POST", "/api/services/frontend/reload_themes", {})
    print("reloaded themes")


def cmd_sim_cameras(panel: Path, dry_run: bool = False):
    """Generic Camera entries from still-image URLs, renamed to camera.sim_<name>."""
    cfg = yaml.safe_load(panel.read_text())
    cams = cfg.get("cameras") or {}
    wanted = []
    if cams.get("doorbell"):
        wanted.append(cams["doorbell"] | {"name": cams["doorbell"].get("name", "Doorbell")})
    wanted += cams.get("others", []) or []
    wanted = [c for c in wanted if c.get("entity") == "sim" and c.get("sim_still_url")]
    existing = {e["title"] for e in rest("GET", "/api/config/config_entries/entry?domain=generic")}
    for cam in wanted:
        title = f"SIM {cam['name']}"
        target = "camera.sim_" + re.sub(r"[^a-z0-9]+", "_", cam["name"].lower()).strip("_")
        if title in existing:
            print("skip", title, "(already exists)")
            continue
        if dry_run:
            print("would create", title, "->", target, "from", cam["sim_still_url"])
            continue
        flow = rest("POST", "/api/config/config_entries/flow", {"handler": "generic"})
        data = {"still_image_url": cam["sim_still_url"], "advanced": {"framerate": 0.5, "verify_ssl": True}}
        if cam.get("sim_stream_url"):
            data["stream_source"] = cam["sim_stream_url"]
        step = rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", data)
        if step.get("type") == "form" and step.get("errors"):
            rest("DELETE", f"/api/config/config_entries/flow/{flow['flow_id']}")
            print(f"FAILED {title}: {step['errors']} (stream DRM-protected or unreachable? try still only)")
            continue
        if step.get("type") == "form":
            step = rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", {"confirmed_ok": True})
        entry_id = step["result"]["entry_id"]
        ws({"type": "config_entries/update", "entry_id": entry_id, "title": title})
        for e in ws({"type": "config/entity_registry/list"}):
            if e.get("config_entry_id") == entry_id:
                ws({"type": "config/entity_registry/update", "entity_id": e["entity_id"],
                    "new_entity_id": target, "name": title})
        print("created", title, "->", target)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest_args = sys.argv[1], sys.argv[2:]
    if cmd == "check":
        cmd_check()
    elif cmd == "ssh":
        print(ssh(" ".join(rest_args), check=False), end="")
    elif cmd == "ws":
        print(json.dumps(ws(json.loads(rest_args[0])), indent=2))
    elif cmd == "backup":
        cmd_backup(rest_args[0])
    elif cmd == "hacs":
        cmd_hacs(rest_args or list(HACS))
    elif cmd == "deploy":
        cmd_deploy(Path(rest_args[0]))
    elif cmd == "reload":
        cmd_reload()
    elif cmd == "sim-cameras":
        cmd_sim_cameras(Path(rest_args[0]), dry_run="--dry-run" in rest_args)
    else:
        sys.exit(f"unknown command {cmd}; see --help")


if __name__ == "__main__":
    main()
