# Sources of truth

Verified 2026-09-30 against Home Assistant **2026.9.4** (HAOS 18.3). Custom cards and HA's
frontend move fast: if you're on a newer HA major or more than a few months past this date,
re-check the linked page before relying on a key, command or version.

| Topic | What was verified | Source |
|---|---|---|
| HA CLI | `ha backups new --name`, `ha core check`, `ha core restart`, `ha core update --version x` | https://www.home-assistant.io/common-tasks/os/ |
| Terminal & SSH add-on | Ships the `ha` CLI; `/config` mapped read-write; network port must be set | https://github.com/home-assistant/addons/blob/master/ssh/DOCS.md |
| Serving files | `/config/www` is served at `/local/` (unauthenticated) | https://www.home-assistant.io/integrations/http/#hosting-files |
| YAML dashboards | `lovelace: dashboards: <path-with-hyphen>: mode: yaml, filename:`. A restart is needed to add one | https://www.home-assistant.io/dashboards/dashboards/ |
| Dashboard WS API | `lovelace/dashboards/create` (`url_path` needs a hyphen), `lovelace/config/save`, `lovelace/resources/create` | https://github.com/home-assistant/core/tree/dev/homeassistant/components/lovelace |
| Packages | `homeassistant: packages: !include_dir_named packages` | https://www.home-assistant.io/docs/configuration/packages/ |
| Themes | `frontend: themes: !include_dir_merge_named themes`, plus `theme:` per view | https://www.home-assistant.io/integrations/frontend/ · https://www.home-assistant.io/dashboards/views/ |
| Panel view | One full-width card per view | https://www.home-assistant.io/dashboards/panel/ |
| Clock card | `type: clock`, `clock_size`, `no_background` | https://www.home-assistant.io/dashboards/clock/ |
| Template entities | Modern `template:` lock / cover / alarm_control_panel / binary_sensor | https://www.home-assistant.io/integrations/template/ |
| **ha-floorplan** | Latest *stable* v1.1.5 (v1.1.6 and v1.2.0 were pre-releases). JS `${}` templates; `class_set`, `text_set`; `hass` and `entities` in templates. `image_resource_prefix` only exists from 1.1.6, so use absolute `/local/` hrefs in the SVG | https://github.com/ExperienceLovelace/ha-floorplan/releases · https://experiencelovelace.github.io/ha-floorplan/docs/usage/ |
| **button-card** | v7.0.1, needs HA 2025.10 or later. Templates, `custom_fields` holding cards, state styles, JS templates | https://github.com/custom-cards/button-card |
| **layout-card** | v2.4.7, needs HA 2025.10 or later. `custom:grid-layout`, `grid-template-areas`, `view_layout.grid-area`. Spacing issues reported since 2026.4, so test the layout | https://github.com/thomasloven/lovelace-layout-card |
| **kiosk-mode** | v14.2.1. HA 2026.6 or later needs v14+. `non_admin_settings`, `?disable_km` | https://github.com/NemesisRE/kiosk-mode |
| **Browser Mod** | v3.2.3, needs HA 2026.7 or later. `browser_mod.popup` targets `browser_id:` in `data`, not `target:`. `initial_style: fullscreen`, `timeout` in ms | https://github.com/thomasloven/hass-browser_mod/blob/master/documentation/services.md |
| card-mod | **Not used.** Open bugs on HA 2026.9: styling silently stops when a theme defines card-mod vars, and edit mode slows down | https://github.com/thomasloven/lovelace-card-mod/issues |
| HACS WS | `hacs/repository/download {repository: "<numeric GitHub id>"}`. Plugins auto-register storage-mode resources | https://github.com/hacs/integration/tree/main/custom_components/hacs/websocket |
| Generic Camera | Config flow: `still_image_url` / `stream_source` + `advanced.{framerate, verify_ssl}`, then `confirmed_ok` | https://www.home-assistant.io/integrations/generic/ |
| Fully Kiosk | Fire build is an APK from the site only. PLUS is per device. Webcam and mic need HTTPS | https://www.fully-kiosk.com/en/ |
| Fully integration | Needs PLUS Remote Admin (port 2323). Screen, brightness, battery and motion entities; `fully_kiosk.load_url` | https://www.home-assistant.io/integrations/fully_kiosk/ |
| Reolink | Local user/pass; Fluent (sub) stream on by default; Visitor binary sensor. "2-way audio is not available" | https://www.home-assistant.io/integrations/reolink/ |
| Two-way audio | Core PR #148282 is still a draft (needs HTTPS / mTLS). getUserMedia requires a secure context | https://github.com/home-assistant/core/pull/148282 · https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia |
| Google Calendar | Google Cloud project, **Publish app** (Testing expires tokens in 7 days), Web client, redirect `https://my.home-assistant.io/redirect/oauth` | https://www.home-assistant.io/integrations/google/ |
| Fire HD 10 (2023) | 1920×1200, 224 ppi, Fire OS 8. **1280×800 CSS at DPR 1.5 must be measured, it's not documented** | https://developer.amazon.com/docs/device-specs/ft-device-specifications-firehd-models.html |

## Known issues to check on the target version

- **HA frontend #54150**: intermittent black WebView in Fully Kiosk on 2026.9.1/9.2. Still open
  at 2026.9.4 with no fix; rolling back to 2026.8.3 resolves it.
  https://github.com/home-assistant/frontend/issues/54150
- **Android System WebView 140+**: flicker and banding in Fully. Workaround is Fully's
  "Graphics Acceleration Mode".
  https://community.home-assistant.io/t/fully-kiosk-browser-rendering-issue-with-android-system-webview/945745
