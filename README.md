# HA Wall Panel

A floorplan wall-tablet dashboard for [Home Assistant](https://www.home-assistant.io/), plus
the process to build one for any house: interview the household, get or sketch a floorplan,
fake the devices you haven't bought yet, and deploy a dark, touch-first panel that looks like
it came with the house.

It's packaged as an **agent skill** (`SKILL.md`), so an AI coding agent can run the whole build
with you. Every step also works by hand with the scripts below.

## What you get

One main page, sized to your tablet, that covers almost everything you do day to day:

- **A live floorplan** of your house:
  - Rooms sit dim when their lights are off and warm when on. Tap a room to toggle its lights.
  - Motion draws a blue outline and a MOTION tag that fades out.
  - Lock badges on exterior doors, and a garage door that turns amber when open (red if the
    alarm is armed).
  - Room temperatures, and a button on the stairs to switch floors.
- **A doorbell camera** on the main page that pops up full screen on the tablet when someone
  rings, then closes itself after two minutes.
- **Locks and garage** tiles. The garage asks before it moves.
- **Alarm** with large state text and plain labelled buttons: Arm home, Arm away, Disarm.
- **Thermostats**, **today's calendar**, and **four scene buttons** you choose (e.g. All off,
  Goodnight, Morning, Movie).
- **A header** with the clock, weather, who's home, and alert chips that only appear when
  something needs attention.
- Secondary pages for **other floors**, **all cameras** and **lists**.

**Devices you don't have yet still work.** Mark them `sim` and the kit creates stand-ins, so the
panel is complete on day one and each real device is a one-line swap later.

## Requirements

- Home Assistant OS or Supervised (the build uses add-ons and the `ha` CLI), 2026.7 or newer.
- [HACS](https://hacs.xyz/) installed.
- A wall tablet. It's designed and tested on an Amazon Fire HD 10 in landscape (1280×800 CSS
  px) running [Fully Kiosk Browser](https://www.fully-kiosk.com/). Other sizes work through the
  `viewport` setting.
- A computer with Python 3.10+, `ssh`, and `pip install -r requirements.txt`.

The kit installs these frontend pieces from HACS:
[ha-floorplan](https://github.com/ExperienceLovelace/ha-floorplan),
[button-card](https://github.com/custom-cards/button-card),
[layout-card](https://github.com/thomasloven/lovelace-layout-card),
[kiosk-mode](https://github.com/NemesisRE/kiosk-mode) and
[Browser Mod](https://github.com/thomasloven/hass-browser_mod).

## How it works

```
interview ─▶ panel.yaml ─▶ scripts/generate.py ─▶ build/ ─▶ scripts/hactl.py deploy ─▶ Home Assistant
                 ▲                                   ├─ dashboards/<name>.yaml   (the panel)
  floorplan ─────┘                                   ├─ packages/<name>.yaml     (SIM devices, scenes, doorbell pop-up)
  (image or sketch)                                  ├─ themes/<name>.yaml       (dark theme)
                                                     └─ www/<name>/              (floorplan SVG, CSS, images)
```

Everything about your house lives in one file, **`panel.yaml`**: floors, rooms, which entity
controls what, your people, scenes and cameras. The generator turns it into Home Assistant
files. You never hand-edit the dashboard; change `panel.yaml` and regenerate.

## Quick start (by hand)

```bash
git clone <this repo> && cd ha-wall-panel
pip install -r requirements.txt

# 1. Describe your house (start from the example)
cp examples/panel.example.yaml panel.yaml

# 2. A floorplan: prepare an export you have...
python3 scripts/prepare_floorplan.py ~/Downloads/my-plan.jpg --out floor-main.png
#    ...or sketch one from room rectangles in panel.yaml
python3 scripts/sketch_floorplan.py panel.yaml --out floor-main.png --labels

# 3. Connect (see "Connecting to Home Assistant" below), then check
cp connection.example.yaml connection.yaml
python3 scripts/hactl.py check

# 4. Back up, install the frontend pieces, generate, deploy
python3 scripts/hactl.py backup "pre-wall-panel"
python3 scripts/hactl.py hacs
python3 scripts/generate.py panel.yaml --out build
python3 scripts/hactl.py deploy build
#    Add the configuration.yaml blocks below once, run `ha core check`, then restart HA.
python3 scripts/hactl.py sim-cameras panel.yaml   # only if you have sim cameras
```

Then open `http://<your-ha>:8123/wall-panel/home` on the tablet.

### configuration.yaml (once)

Merge these into your existing keys; don't duplicate `homeassistant:` or `frontend:`:

```yaml
homeassistant:
  packages: !include_dir_named packages

frontend:
  themes: !include_dir_merge_named themes

lovelace:
  dashboards:
    wall-panel:                       # the `dashboard` value from panel.yaml
      mode: yaml
      filename: dashboards/wall-panel.yaml
      title: Wall Panel
      icon: mdi:tablet-dashboard
      show_in_sidebar: true
```

## Quick start (with an AI agent)

Point your agent at this repo and ask for a wall panel. `SKILL.md` walks it through eight
phases:

1. **Interview**: your tablet, floors and rooms, devices room by room (have it / simulate it /
   skip it), people, calendar, and the scenes you'd actually tap.
2. **Floorplan**: prepares your image, or sketches your house with you in conversation (walk it
   from the front door, draw, adjust, repeat).
3. **Mockup**: shows you the panel at your tablet's exact size before touching Home Assistant.
4. **Connect**: you install the SSH add-on and create a token; the agent never asks for secrets
   in chat.
5. **Build**: backup, HACS pieces, generate, deploy, restart once.
6. **Verify**: checks the layout at the exact viewport, with no scrolling, and exercises every state.
7. **Tablet**: Fully Kiosk setup, viewport check, Browser Mod registration, doorbell test.
8. **Hand-over**: how to swap in real devices, how to roll back, and what's pending.

## Connecting to Home Assistant

The scripts use three channels: **SSH** (files and the `ha` CLI), **REST** and **websocket**.

1. Create a key for this tool:
   `ssh-keygen -t ed25519 -f ~/.ssh/ha_wall_panel_ed25519 -N ""`
2. In HA, install the official **Terminal & SSH** add-on:
   - Paste the `.pub` line into `authorized_keys`.
   - Set the **Network** port to `22`. It ships disabled.
   - Save, then start the add-on.
3. Create a **long-lived access token** (Profile → Security), save it to a file (e.g.
   `~/.config/ha-wall-panel/token`), and `chmod 600` it.
4. Fill in `connection.yaml` and run `python3 scripts/hactl.py check`.

`connection.yaml` and anything in `build/` are git-ignored. Revoke access any time by removing
the key from the add-on or deleting the token.

## Day-two changes

| You want to... | Do this |
|---|---|
| Swap a SIM for a real device | In `panel.yaml`, replace `sim` with the entity id (e.g. `light: light.kitchen`), then `generate.py` → `hactl.py deploy build` → `hactl.py reload` |
| Rename a room or move its rectangle | Edit `panel.yaml`, bump `asset_version`, regenerate and deploy, refresh the tablet |
| Add a floor | Add it under `floors:` with a `stairs` link from an existing floor. With no image it shows a placeholder |
| Change the look | Edit `templates/` (theme, floorplan CSS, button-card templates) and regenerate |
| Undo everything | Remove the two `configuration.yaml` blocks and restart, or restore the backup taken before the build |

## Design

The look is deliberate: colour only means state (warm lights, blue secure, amber open, red
problem), anything normal stays out of the way, targets are finger-sized, and motion is calm. See
[`references/design-system.md`](references/design-system.md) for the palette, layout grid and
component rules.

## Known limits

- **Two-way talk** through a doorbell isn't possible in HA yet (no two-way audio in the Reolink
  integration), and browsers only allow the tablet's microphone over HTTPS.
- **Many public camera streams are DRM-protected.** SIM cameras use still images, which is enough
  to design and test with.
- **Fire tablets and Fully Kiosk** are sensitive to HA frontend and WebView releases. Soak-test
  for 24 hours, and check [`references/sources.md`](references/sources.md) for known regressions.

## Repository layout

```
SKILL.md                     agent procedure (the eight phases)
scripts/
  generate.py                panel.yaml → dashboard, package, theme, floorplan assets
  prepare_floorplan.py       floorplan export → cropped, muted, transparent PNG
  sketch_floorplan.py        room rectangles → schematic floorplan PNG
  hactl.py                   check / backup / hacs / deploy / reload / sim-cameras / ssh / ws
templates/                   theme, floorplan CSS, button-card templates, viewport probe
references/                  interview, floorplan, design system, schema, HA access, tablet,
                             sources of truth, troubleshooting
examples/                    a complete panel.yaml for a fictional house, with its sketch
```
