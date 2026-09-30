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

## `floors[]`

The first floor is the main page (`/<dashboard>/home`). The others get their own views at
`/<dashboard>/<id>`.

| Key | Meaning |
|---|---|
| `id`, `name` | Floor id (used in URLs and nav) and display name |
| `image` | PNG relative to panel.yaml. Omit it for a placeholder floor |
| `width`, `height` | The image's coordinate space (its pixel size from `prepare_floorplan.py`, or your sketch canvas) |
| `rooms[]` | See below |
| `locks[]` | `{id, name, entity, badge: [x, y]}`. `badge` is optional; without it the lock only appears as a tile |
| `garage` | `{name, entity, bar: [x, y, w, h]}`. `bar` is the door edge drawn on the plan |
| `stairs[]` | `{to: <floor id>, at: [x, y]}`. A pill that switches floor (omit `at` on placeholder floors) |
| `doors[]` | Sketch only: doorway gaps `[x, y, length, "h"|"v"]` for `sketch_floorplan.py` |

### `rooms[]`

| Key | Meaning |
|---|---|
| `id`, `name` | Room id (SVG element `room.<id>`) and label (shown upper-case) |
| `rect` | `[x, y, w, h]` in the floor's coordinates. Rooms under ~70×50 get the compact style |
| `light` | Entity that tap toggles and that drives the lit/dark tint (`light.*`, `switch.*`, a group, or `sim`) |
| `motion` | Binary sensor that drives the outline and MOTION tag, or `sim` |
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
