---
name: ha-wall-panel
description: Design and build a floorplan wall-tablet dashboard for a Home Assistant instance — interview the owner, get or sketch a floorplan, simulate devices that aren't installed yet, connect to their HA over SSH + API, generate a dark, touch-first panel (ha-floorplan + button-card + layout-card + kiosk-mode + Browser Mod), deploy it with backups, and verify it at the tablet's exact viewport. Use when someone wants a Home Assistant wall panel, kiosk dashboard, floorplan dashboard, or tablet control screen, or asks to add rooms, devices, cameras, or a doorbell pop-up to one built with this kit.
---

# HA Wall Panel

You are building a wall-mounted control panel that a non-technical household member will use
every day. The bar is "looks installed, not hacked together": one main page covers ~90% of use,
every tap target is finger-sized, colour only ever means state, and nothing breaks when a device
is missing. This skill is the procedure; `scripts/` does the mechanical work; `references/` holds
the detail you load when you reach each phase.

**Work in phases, in order.** Each phase ends with something the owner can see or confirm.
Don't skip ahead to building before the interview and the mockup are agreed — rework on a live
Home Assistant is expensive, and the owner's answers change the design.

## Ground rules

- **Their Home Assistant is live.** Back it up before the first change (`hactl.py backup`), keep
  every change additive and reversible, and run `ha core check` before any restart. Say what you
  are about to change before you change it.
- **Never handle their secrets in chat.** The owner creates the long-lived access token and the
  SSH add-on key line, and writes the token to `token_file` themselves. You never ask them to
  paste a password, token, or OAuth client secret into the conversation — those go straight into
  the HA UI or a local file. Tablet passwords are theirs alone.
- **Pin every claim to a source.** Versions and syntax for HA and every custom card change fast.
  `references/sources.md` lists what was verified and when; if you're past its date or on a newer
  HA major, re-check the linked pages before relying on a key or command.
- **Nothing costs money without a yes.** Fully Kiosk PLUS is a per-device licence; cloud services
  (Nabu Casa, paid camera APIs) are the owner's call. Surface the cost, don't assume.
- **Placeholders are first-class.** A device the owner doesn't have yet becomes a `sim` entity so
  the panel is complete on day one; swapping in the real device later is a one-line change.

## Phase 1 — Interview

Load `references/interview.md` and run it conversationally — a few questions at a time, grouped,
with sensible defaults offered, not a 40-item form. You need, at minimum:

1. **The tablet**: make/model, orientation (landscape strongly preferred), where it's mounted,
   who uses it. Look up its CSS viewport (Fire HD 10 = 1280×800 at DPR 1.5) — you will measure it
   for real in Phase 7.
2. **The house**: floors, rooms per floor, and whether a floorplan image exists.
3. **Devices, room by room**: lights, motion, temperature, locks, garage, alarm, thermostats,
   doorbell, cameras — for each, "have it (entity id)", "planned (simulate)", or "not wanted".
4. **People and daily life**: who lives there (person entities), calendar, shopping list, the
   3–4 scenes they'd actually tap (e.g. All off / Goodnight / Morning / Movie).
5. **Access**: HA URL reachable from where you run, whether HACS is installed, HA version.

Capture answers straight into a `panel.yaml` draft (schema: `references/panel-schema.md`,
example: `examples/panel.example.yaml`). Read back what you understood in plain language and fix
it before moving on.

## Phase 2 — Floorplan

Load `references/floorplan.md`. Three paths, in order of preference:

- **They have an image** (Floorplanner, Magicplan, listing brochure, builder PDF page): run
  `scripts/prepare_floorplan.py` — auto-crop, mute for a dark UI, knock out the paper white. Then
  measure each room's rectangle **in the output image's pixels**, view the image to check, and
  write `rect: [x, y, w, h]` per room.
- **They can make one in ~15 minutes**: suggest Floorplanner's free tier (draw walls, export a
  2D image), then take the first path.
- **Neither — sketch it together.** This is a conversation, not a form: walk the house from the
  front door, one room at a time ("what's straight ahead? what's to the left? roughly how big
  compared to the kitchen?"), block it out as rectangles on a grid, render with
  `scripts/sketch_floorplan.py --labels`, show the owner, and iterate until they say "yes, that's
  my house". Proportions matter more than accuracy; nobody measures a wall panel.

Either way you finish with, per floor: an image, its `width`/`height`, room rectangles, lock
badge points on exterior doors, the garage door edge, and a stairs point for each other floor.

## Phase 3 — Design and mockup

Load `references/design-system.md` — the palette, type, layout grid, and component rules this
panel is built from. Before touching HA, show the owner a **mockup at the tablet's exact
viewport** (an HTML page or artboard at 1280×800) with their floorplan, their room names, and
their devices in the standard layout:

- **Header**: clock + date │ weather │ people chips │ alert chips (only when something's wrong) │ nav.
- **Left ~half**: the floorplan. Rooms dim when dark, tint warm when lit, blue outline + MOTION tag
  on motion, amber/red door edges, lock badges, temperature labels, a pill to change floor.
- **Right column**: doorbell camera (16:9) beside lock/garage tiles; alarm (big state text +
  text buttons); two climate tiles; today's agenda beside a 2×2 scene grid.
- **Doorbell pop-up**: full-screen live view with Dismiss, auto-closing after 2 minutes.

Walk them through it, show one "something's wrong" state (garage open, motion, alarm armed), and
take their edits. Room names, what's on the main page vs a secondary page, scene names. Update
`panel.yaml`. This is the cheapest moment to change anything.

## Phase 4 — Connect to their Home Assistant

Load `references/ha-access.md`. The owner does the privileged steps; you verify:

1. **SSH**: they install the official **Terminal & SSH** add-on, paste your public key into
   `authorized_keys`, set the network port to **22** (it ships disabled — the log says "SSH port
   is disabled"), save, and restart it. Generate a dedicated key for this
   (`ssh-keygen -t ed25519 -f ~/.ssh/ha_wall_panel_ed25519 -N ""`) so it can be revoked alone.
2. **API token**: they create a long-lived access token (Profile → Security) and write it to the
   `token_file` path themselves.
3. Copy `connection.example.yaml` → `connection.yaml`, fill it in, and run
   `scripts/hactl.py check`. Every line must pass before you continue.
4. Read the current state without changing anything: `configuration.yaml`, installed HACS
   repositories, dashboards, add-ons, users, entity list. Note any existing `homeassistant:`,
   `lovelace:`, or `frontend:` keys — you will merge into them, not duplicate them.

## Phase 5 — Build

1. **Back up**: `hactl.py backup "pre-wall-panel <date>"`, then copy the tarball off the box
   (`hactl.py ssh 'cat /backup/<slug>.tar' > ...`). Offer a core update first if one is pending,
   checking `references/sources.md` for known frontend/kiosk regressions on the target version.
2. **Frontend pieces**: `hactl.py hacs` installs ha-floorplan, kiosk-mode, layout-card,
   button-card and Browser Mod (HACS auto-registers the dashboard resources). Browser Mod is an
   integration: restart, then add it (the config flow is one step:
   `POST /api/config/config_entries/flow {"handler": "browser_mod"}`).
3. **configuration.yaml** — add, merging with any existing keys (show the owner the diff):
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   frontend:
     themes: !include_dir_merge_named themes
   lovelace:
     dashboards:
       wall-panel:            # = dashboard in panel.yaml
         mode: yaml
         filename: dashboards/wall-panel.yaml
         title: Wall Panel
         icon: mdi:tablet-dashboard
         show_in_sidebar: true
   ```
4. **Generate + deploy**: `scripts/generate.py panel.yaml --out build`, then
   `hactl.py deploy build`. The generator refuses to emit YAML that doesn't parse; `deploy` parses
   again locally because **HA's config check does not validate dashboard YAML**.
5. **Restart once** (new packages/dashboard keys need it), then create SIM cameras if any:
   `hactl.py sim-cameras panel.yaml`. After later changes, `hactl.py reload` is enough for
   packages; dashboard/asset changes only need a browser refresh (bump `asset_version`).
6. **Kiosk user**: the owner creates a non-admin person with login (Settings → People). Any name;
   kiosk-mode hides header and sidebar for every non-admin, so admins keep the normal UI.

## Phase 6 — Verify on a desktop at the tablet's viewport

Open the dashboard in a browser sized to the exact viewport (set the window so
`innerWidth × innerHeight` = e.g. 1280×800, and add `?kiosk` to hide chrome as the admin). Check
and screenshot:

- `scrollWidth == innerWidth` and `scrollHeight == innerHeight` — **no scrolling, either way**.
- Flip SIM states over the API and watch the plan react: light on → room lifts; motion → outline +
  tag; garage open → amber bar and tile (red if alarm armed) and, after N minutes, the alert chip;
  lock → badge colour; alarm → big state text + active button.
- Tap a room (light toggles), the stairs pill (floor switch), a scene, the garage (confirm dialog).
- Reset every SIM to a calm state afterwards.

A reload can drop the browser's login if "Keep me logged in" wasn't ticked — prefer in-page
navigation (`history.pushState` + a `location-changed` event) over full reloads while testing.

## Phase 7 — The tablet

Load `references/tablet.md`. With the owner holding the device:

1. Fully Kiosk Browser (Fire tablets: the APK from fully-kiosk.com, sideloaded). Start URL
   `http://<ha>:8123/<dashboard>/home`, keep screen on, launch on boot, hide system bars, auto
   reload on network reconnect. Log in as the kiosk user.
2. Open `/local/<dashboard>/viewport.html` — confirm the viewport; if it isn't what you designed
   for, update `viewport:` and regenerate.
3. Register the tablet in **Browser Mod** with the `browser_id` from panel.yaml (do it as an admin
   or with `?disable_km`; the kiosk user has no sidebar). Press the SIM doorbell ring
   (Cameras → Test doorbell ring) and watch the pop-up.
4. **Restart Fully after any new custom card is installed** — a running WebView keeps the old
   resource list and shows red "!" icons until it reloads.
5. Leave it running 24h before calling it done (known WebView/frontend regressions: see sources).

## Phase 8 — Hand-over

- Commit `panel.yaml`, the processed floorplan, and `build/` to the owner's own repo; that repo is
  now the source of truth for the panel. Re-running the generator replaces hand edits.
- Tell the owner, plainly: how to swap a SIM for a real device (edit `panel.yaml`, regenerate,
  deploy, reload), how to roll back (remove the two config keys, or restore the backup), and
  what's still pending (real devices, calendar, HTTPS for two-way talk).
- Record anything that surprised you in `references/troubleshooting.md` for the next build.

## Swapping a SIM for a real device later

Change `light: sim` → `light: light.kitchen_ceiling` (or `lock`, `cover`, `alarm`, `camera`,
`ring: binary_sensor.<doorbell>_visitor`), run `generate.py`, `hactl.py deploy build`,
`hactl.py reload`. The SIM helper disappears from the package; delete its leftover entity in HA if
it lingers. For a real doorbell with the Reolink integration, `ring` is its Visitor binary sensor
and `entity` its Fluent (sub) stream camera.

## Verification

`python3 scripts/generate.py examples/panel.example.yaml --out /tmp/wp-build` exits 0 and prints
a dashboard, package, theme and asset directory; every YAML file under `/tmp/wp-build` parses.
