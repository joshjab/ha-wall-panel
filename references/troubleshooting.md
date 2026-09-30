# Troubleshooting and lessons

Things that actually went wrong while building the first panel with this kit, and the fix.
Add to this list whenever something surprises you.

## Building

| Symptom | Cause | Fix |
|---|---|---|
| Tapping a room does nothing | An SVG element with its own rule is layered over the room and catches the tap (ha-floorplan attaches handlers to every ruled element, whatever the CSS `pointer-events` says) | Keep everything a room draws inside the room's group, driven by one rule. The generator does this |
| Dashboard renders blank or with an error after a "successful" deploy | YAML syntax error in the dashboard file. `ha core check` doesn't validate dashboards | Parse locally before deploying (`hactl.py deploy` does) |
| YAML error at a `#` colour inside `[...]` | In a YAML flow sequence an unquoted `#` starts a comment | Quote it: `border: "1px solid #3d5a73"` |
| Page scrolls a little at the target viewport | The floorplan card's on-card log panel (`config.log_level`) adds height | Only set `console_log_level` |
| Header items shift left when an alert is hidden | Auto-placed grid items fill the gap left by a hidden conditional card | Give every header card an explicit `grid-area` |
| Tiles in a nested layout-card are squashed | `1fr` rows inside an unsized nested grid collapse | Use fixed pixel rows in nested grids |
| Right column wider or narrower than designed | HA's panel view and layout-card use ~32px beyond the declared padding, and long text widens `1fr` columns | Compute widths with that allowance and use `minmax(0, 1fr)` plus nowrap/ellipsis on tile text |
| Weather reads "Partlycloudy" | HA condition ids aren't words | Map condition ids to labels (the generator does) |
| Shell helper runs a command as one word | zsh doesn't word-split `$VAR` holding `ssh -i … host` | Use a wrapper script or an array, not a string variable |

## Cameras

| Symptom | Cause | Fix |
|---|---|---|
| Generic Camera flow fails with `stream_source: timeout` on a public HLS feed | The stream is DRM-encrypted (look for `#EXT-X-KEY:METHOD=SAMPLE-AES` in the chunk playlist), e.g. many DOT traffic cams | Use the still-image URL only. Never try to get around DRM |
| Pop-up doesn't appear on the tablet | The tablet isn't registered in Browser Mod under `tablet.browser_id`, or the page has been open for days | Register it; reload Fully nightly |

## Tablet and browser

| Symptom | Cause | Fix |
|---|---|---|
| Red "!" icons on the tablet only | Fully was started before a custom card was installed | Restart Fully |
| Desktop test browser logs out on every reload | "Keep me logged in" wasn't ticked | Tick it, or navigate in-page (`history.pushState` + `location-changed`) |
| Window sized to 1280 but the page isn't 1280 wide | OS display scaling or browser zoom | Size by measuring `innerWidth`/`innerHeight` and adjust until they match |
| Floorplan looks soft on the tablet | Low-resolution source image (the tablet renders ~1.5–2× CSS px) | Export larger. `sketch_floorplan.py` renders at 2× by default |

## Access

| Symptom | Cause | Fix |
|---|---|---|
| SSH refused after installing the add-on | The network port ships blank (disabled) | Set port 22 in Configuration → Network, then restart the add-on |
| `/api/hassio/*` returns 401 with an admin token | Supervisor API isn't open to user tokens through the proxy | Use the `ha` CLI over SSH |
