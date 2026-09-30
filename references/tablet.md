# The tablet

## Fully Kiosk Browser

Fully is still the standard kiosk browser for HA wall panels. It offers keep-awake, motion
wake, a screensaver, remote admin and a first-party HA integration.

- **Fire tablets**: install the Fire-specific APK from fully-kiosk.com (download box) with
  "Apps from unknown sources" enabled. It isn't on the Amazon Appstore.
- **PLUS licence** (paid, per device) unlocks Remote Admin, which the HA **Fully Kiosk Browser**
  integration needs for screen on/off, brightness, battery and motion entities. It's optional
  for the panel itself. Ask before buying.
- Settings that matter:
  - **Start URL**: `http://<ha>:8123/<dashboard>/home`
  - **Keep Screen On**, **Launch on Boot**
  - **Toolbars and Appearance**: hide the status bar and navigation bar (fullscreen)
  - **Auto Reload on Network Reconnect**
  - **Screensaver**: dim at night rather than off, if motion wake isn't set up
  - **Remote Administration** (PLUS): password set, local network only; port 2323 for the integration
- Log in as the **non-admin kiosk user** and tick "Keep me logged in".

## Measure the viewport

Load `http://<ha>:8123/local/<dashboard>/viewport.html` in Fully. It shows `innerWidth ×
innerHeight`, the device pixel ratio and the user agent. The Fire HD 10 (2021/2023, 1920×1200 at
224 ppi) is expected to report **1280×800 at DPR 1.5**. Always measure: Fully's zoom and
"initial scale" settings change it. If it differs, set `viewport:` in panel.yaml and regenerate.

## Browser Mod registration (doorbell pop-up)

The pop-up targets a Browser Mod **browser ID**, not a device. On the tablet:

1. Open the dashboard as an admin, or with `?disable_km` appended, since the kiosk user has no
   sidebar.
2. Open the **Browser Mod** panel, turn on **Register**, and set the Browser ID to
   `tablet.browser_id` from panel.yaml. Refresh.
3. Log back in as the kiosk user if you switched.
4. Test it: Cameras → **Test doorbell ring** (SIM), or press the real doorbell.

A reported gotcha is that pop-ups can stop appearing on long-running wall panels until the page
reloads. A nightly Fully reload (or `fully_kiosk.load_url`) keeps it fresh.

## After installing a new custom card

**Restart Fully** (or force a reload). A long-running WebView keeps the resource list it
started with. Cards whose JavaScript it never loaded render as red "!" icons until then.

## Soak test

Leave it running for 24 hours before calling it done. Watch for:

- **Black or blank screens.** Fully and Android System WebView regressions come and go with HA
  frontend releases. See `sources.md` for known ones on the target version and their workarounds
  (Fully's "Graphics Acceleration Mode", or pinning a core version).
- **Stale pop-ups** (see above).
- **Heat and battery.** A tablet on 24/7 charge can swell its battery. Cycling the charger on a
  smart plug from the Fully battery sensor is common practice. Fire OS has no native charge limit.

## Cameras on a low-power tablet

- Use the camera's **sub stream** (Reolink calls it "Fluent") for the tablet. The main stream is
  heavy for a cheap SoC.
- HA's built-in go2rtc serves WebRTC to `picture-entity` automatically. Use H.264; H.265 support
  in Android WebView is unreliable.
- One live stream on screen at a time. The Cameras page is for occasional use.
- **Two-way talk** needs microphone access, which browsers only allow over HTTPS, plus
  two-way audio support in HA for the camera. Neither is a given, so check `sources.md` before
  promising it.
