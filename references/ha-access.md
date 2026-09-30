# Connecting to the owner's Home Assistant

The build needs three channels:

- **SSH** into the official Terminal & SSH add-on, for files and the `ha` CLI.
- **REST**, for states, services and config flows.
- **Websocket**, for dashboards, HACS and the entity registry.

The owner performs every privileged step. You verify each one with `hactl.py check`.

## 1. SSH: the official Terminal & SSH add-on

Why this add-on:

- It's first-party.
- It exposes `/config` read-write.
- It ships the `ha` CLI (`ha core check`, `ha core restart`, `ha backups new`), so you can
  validate, restart and back up without the UI.

Samba only moves files. The File editor is a web UI you can't script.

1. Generate a dedicated key on the machine you run from:
   `ssh-keygen -t ed25519 -f ~/.ssh/ha_wall_panel_ed25519 -N "" -C "ha-wall-panel"`
2. Owner: **Settings → Add-ons → Add-on store → Terminal & SSH** (the official one, not
   "Advanced SSH & Web Terminal"), then install it.
3. Owner: **Configuration** tab:
   - Under `authorized_keys`, paste the single `.pub` line and leave the password empty.
   - Under **Network**, set the port to `22`. It ships blank, which means disabled, and the add-on
     log then says *"SSH port is disabled. Prevent start of SSH server."* Turn on "Show disabled
     ports" if the field is hidden.
   - Save, then **Start** (or **Restart**). Enable **Start on boot**.
4. You: `ssh -i ~/.ssh/ha_wall_panel_ed25519 root@<host> 'ha core info'`.

Notes:

- `/config` is a symlink to `/homeassistant` inside the add-on.
- The add-on has **no python3**. Do data wrangling on your side: `cat` the file over SSH and
  parse it locally.
- To revoke access, the owner deletes the key line or stops the add-on. Tell them this.

## 2. API token

Owner: **Profile (bottom-left) → Security → Long-lived access tokens → Create**. Name it after
this tool, then write it to the `token_file` path from `connection.yaml` and `chmod 600` it. It
never goes through chat. The token acts as that user, so it must belong to an **admin** for
HACS and dashboard writes.

## 3. connection.yaml and the check

```bash
cp connection.example.yaml connection.yaml   # fill in ha_url, ssh_host, key, token_file
python3 scripts/hactl.py check
```

Every line should print a value. Common failures:

| Symptom | Cause |
|---|---|
| `Connection refused` on 22 | Port not set in the add-on's Network section, or the add-on isn't restarted |
| `Permission denied (publickey)` | Key line not saved, or the wrong key file in connection.yaml |
| REST `401` | Token file missing, has a trailing newline issue, or the token was revoked |
| `hacs: MISSING` | Install HACS first (needs the owner's GitHub login) |
| `/api/hassio/...` returns `401` | Expected: Supervisor endpoints aren't open to user tokens. Use the `ha` CLI over SSH instead |

## 4. Read before you write

Pull the current state and keep a copy (`baseline/`) before changing anything:

- `configuration.yaml`: existing `homeassistant:`, `frontend:`, `lovelace:` keys to merge with
- `.storage/lovelace_dashboards`, `.storage/lovelace_resources`: existing dashboards and resources
- HACS installed repositories: `ha-floorplan` may already be there
- `ha addons`, `ha backups list`, `ha core info` (is an update pending?)
- The entity list over REST: map the interview's "have it" devices to real entity ids and
  confirm them with the owner

## Operating safely

- Take a full backup and copy it off the box before the first change.
- Keep a local git repo of every file you author for HA. It becomes the owner's source of truth.
- Validate YAML locally before deploying. `ha core check` validates configuration and packages
  but **not** dashboard YAML files. A broken dashboard deploys "successfully" and then fails to
  render.
- Prefer reloads over restarts (`hactl.py reload`). Restart only for new top-level keys, new
  packages dirs, new YAML dashboards or new integrations, and run `ha core check` first.
- Use a scratch dashboard (storage mode via `lovelace/dashboards/create` +
  `lovelace/config/save`) to trial big changes alongside the live one, then delete it.
