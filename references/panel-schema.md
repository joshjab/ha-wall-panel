# panel.yaml reference

Everything the generator reads. `examples/panel.example.yaml` is a complete working example.
Any device value may be a real entity id, `sim` (generate a stand-in), or `null`/omitted (leave
it out, or show a quiet placeholder where the layout has a slot).

## Top level

| Key | Default | Meaning |
|---|---|---|
| `title` | `Wall Panel` | Dashboard title |
| `dashboard` | `wall-panel` | URL path, which **must contain a hyphen** (HA rule). Also names the `/local/<dashboard>/` asset folder |
| `theme_name` | `Wall Panel Dark` | Theme name, applied to every view |
| `package` | slug of `dashboard` | Prefix for generated scripts and sensors (`script.<package>_goodnight`) |
| `viewport` | `{width: 1280, height: 800}` | Tablet CSS viewport. Measure it with `viewport.html` |
| `asset_version` | `1` | Appended to image/CSS URLs. Bump it after changing them so the tablet refetches |
| `tablet.browser_id` | `<dashboard>-tablet` | Browser Mod ID the doorbell pop-up targets |
| `tablet.screen_switch` | none | e.g. `switch.<tablet>_screen` from the Fully Kiosk integration. Turned on when the doorbell rings |
| `phone.dashboard` / `phone.title` | none | Also generate a portrait **phone dashboard** (e.g. `phone-panel`, which needs a hyphen) from the same floors and controls |
| `alarm_hold_mode` | `armed_home` | What press-and-hold on the on-plan alarm button arms to when it's disarmed (`armed_away`, `armed_night`...) |

## `floors[]`

The first floor is the main page (`/<dashboard>/home`). The others get their own views at
`/<dashboard>/<id>`.

| Key | Meaning |
|---|---|
| `id`, `name` | Floor id (used in URLs and nav) and display name |
| `image` | PNG relative to panel.yaml. Omit it for a placeholder floor |
| `width`, `height` | The image's coordinate space (its pixel size from `prepare_floorplan.py`, or your sketch canvas) |
| `rooms[]` | See below |
| `locks[]` | `{id, name, entity, badge: [x, y], badge_r?}`. `badge` puts a hold-to-lock button on the plan (radius 26 by default, big enough for a phone). Without it the lock only appears as a tile |
| `garage` | `{name, entity, bar: [x, y, w, h], button?: [x, y, w, h]}`. `bar` is the door edge drawn on the plan; `button` adds a hold-to-open/close control |
| `alarm_button` | `[x, y, w, h]`: an on-plan alarm button (tap = details, hold = arm/disarm). Optional: with a phone dashboard the alarm shield sits under the plan instead |
| `scene_buttons` | `[x, y, w, h]`: an empty area of the plan for the first four scenes as a 2×2 grid (tap to run). Optional: with a phone dashboard the Mode button under the plan covers this |
| `stairs[]` | `{to: <floor id>, at: [x, y]}`. A pill that switches floor (omit `at` on placeholder floors) |
| `doors[]` | Sketch only: doorway gaps `[x, y, length, "h"|"v"]` for `sketch_floorplan.py` |

### `rooms[]`

| Key | Meaning |
|---|---|
| `id`, `name` | Room id (SVG element `room.<id>`) and name. `name` names the SIM entities in HA; it's also the plan label unless `label` is set |
| `label` | Short text for the plan, e.g. `Bath` for "Guest Bath Downstairs", or `C` for a closet (shown upper-case) |
| `label_at` | `[x, y]` baseline for the label (the MOTION tag sits under it), or `center` to centre it (no tag). Default: the bounding box's top-left corner, which can land outside an L-shaped room |
| `rect` | `[x, y, w, h]` in the floor's coordinates. Rooms under ~70×50 get the compact style |
| `poly` | Instead of `rect`: `[[x, y], ...]` traced along the room, for L-shapes, bays and halls. The motion outline is clipped to the inside. Include the wall tops if you want the tint to reach them |
| `light` | Entity that tap toggles and that drives the lit/dark tint (`light.*`, `switch.*`, a group, or `sim`) |
| `motion` | Binary sensor that drives the outline and MOTION tag, or `sim`. Omit it for closets |
| `temperature` | Sensor shown as a label, or `sim` |
| `temp_at` | `[x, y]` for the temperature label (default: the room's bottom-right corner) |
| `kind` | Sketch colour: `room`, `kitchen`, `bath`, `laundry`, `garage`, `hall`, `outside` |

## Right column and header

| Key | Meaning |
|---|---|
| `people[]` | `{entity: person.x, name, initial?, color?}`. A header chip each, showing Home or Away |
| `weather` | Weather entity for the header (`weather.forecast_home`) |
| `alarm` | `alarm_control_panel.*` or `sim`. Omitted: a placeholder tile |
| `climate[]` | Up to two `{name, entity}`. `entity: null` shows "Not installed yet" |
| `calendar` | Calendar entity for the Today panel. Omitted: a hint to add one |
| `lists[]` | Todo entities for the Lists page. `list_titles` maps entity → title |
| `alerts.garage_open_minutes` | Minutes before the "garage open" chip appears (default 20) |

## `cameras`

| Key | Meaning |
|---|---|
| `note` | Text in the Cameras page header |
| `doorbell.name` / `entity` | Camera shown on the main page and in the pop-up. `sim` → `camera.sim_<name>` |
| `doorbell.ring` | Entity whose `on` triggers the pop-up (Reolink: `binary_sensor.<name>_visitor`). `sim` adds a Test button |
| `doorbell.popup_title`, `popup_seconds` | Pop-up text and auto-close time (default 120s) |
| `doorbell.sim_still_url` | For `sim` cameras: a public, unencrypted still-image URL (`hactl.py sim-cameras`) |
| `others[]` | `{name, entity, sim_still_url?}` for the Cameras page |
| `badge`, `floor` | On the doorbell or any `others[]` entry: `badge: [x, y]` puts a camera button on the plan (radius 22, `badge_r` to change) that opens the live view. `floor` defaults to the main floor |

## `scenes[]` (up to four on the main page)

`{name, icon, script}` calls an existing script. Or give a `preset` and the generator writes the
script for you, acting on whatever entities (real or sim) the panel knows about:

| Preset | Does |
|---|---|
| `all_off` | Every room light off |
| `goodnight` | Lights off, lock every lock, close the garage, arm home |
| `morning` | Disarm, then turn on `lights_on: [room ids]` |
| `movie` | Lights off, then `lights_on` |
| any other | Only `lights_on`, or a logbook placeholder if there's nothing to do |

## Mode

Every generated scene script first fires a `<package>_mode` event, and a trigger-based template
sensor (`sensor.<title>_mode`, e.g. `sensor.wall_panel_mode`) keeps the last one run. The wall
panel highlights that scene's tile; the phone's Mode button shows its icon and name.

## Tap, hold, and where each applies

- **Wall panel tiles** (right column) act on a **tap**: lock/unlock, open/close the garage, arm
  home/away, disarm. Unlocking, moving the garage door, and disarming ask first; locking and
  arming don't. Holding a tile opens its details.
- **On-plan controls** (in the floor SVG, shared by both dashboards) act on **press and hold**:
  lock badges and the garage button. A tap opens details. Camera badges open the live view on a
  tap. Room lights toggle on a tap.
- **Phone Mode and Alarm buttons** (under the plan): Mode opens its scene picker on a tap or a
  hold. The alarm opens its picker (Disarm / Arm home / Arm away) on a press and hold as a Browser Mod pop-up on that device; a choice runs and closes
  it. A tap on the alarm shows its details. The shield reads at a glance: amber outline disarmed,
  blue with a walking person armed away, blue with a house armed home, red when triggered.

The phone's on-plan controls keep the hold because the phone lives in a pocket. The wall panel
is mounted, so its tiles act on a tap like any wall switch. Put on-plan controls in empty parts
of the plan (outside walls, unused corners) where they don't cover room labels; about 55+ units
tall keeps them finger-sized on a phone.
