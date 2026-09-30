# Starting from nothing

For owners with no Home Assistant yet, or no smart devices. Run this as **Phase 0**, before the
interview's device questions. Keep it proportionate: the panel works on day one with nothing but
a host and a tablet, because every missing device can be `sim`. Help the owner choose what to
buy first; don't hand them a shopping list for the whole house.

Checked 2026-09-30. Prices are manufacturer MSRP at that date. Re-check before quoting them, and
never buy anything on the owner's behalf.

## 1. The Home Assistant host

This kit needs **Home Assistant OS**. It uses Apps (called add-ons before HA 2026.2) and the `ha`
CLI. HA Container has no Apps, and Core and Supervised installs lost support after 2025.12.
([installation](https://www.home-assistant.io/installation/),
[deprecation notice](https://www.home-assistant.io/blog/2025/05/22/deprecating-core-and-supervised-installation-methods-and-32-bit-systems/))

| Option | When to pick it | Notes |
|---|---|---|
| **[Home Assistant Green](https://www.home-assistant.io/green/)** | Default for most homes | Plug and play, HA OS preinstalled. Quad-core A55, 4 GB RAM, 32 GB eMMC. $199 / €179 |
| **[Raspberry Pi 5 or 4](https://www.home-assistant.io/installation/raspberrypi)** | Already own one | At least 2 GB RAM, a 32 GB+ A2 microSD (an SSD is better), Ethernet |
| **[x86-64 mini PC](https://www.home-assistant.io/installation/generic-x86-64)** | Want headroom (NVR, voice, many cameras) | Install HA OS directly on a repurposed PC |
| **[Virtual machine](https://www.home-assistant.io/installation/alternative)** | Already run Proxmox, KVM, ESXi or VirtualBox | `.qcow2` / `.ova` / `.vdi` images. At least 2 GB RAM and 2 vCPUs. Pass a USB radio through to the VM |

Home Assistant Yellow is discontinued. Don't recommend it.

After first boot:

1. **Onboarding.** Create the owner account, set the home location, and let HA discover devices.
2. **Updates.** Apply any pending core or OS updates, then take a backup.
3. **[HACS](https://hacs.xyz/docs/use/download/download/).** Add the App repository
   `https://github.com/hacs/addons`, then install and start **Get HACS**, and follow its log.
   The owner needs a GitHub account to finish the setup.
4. **[Companion app](https://companion.home-assistant.io/)** on each phone. It creates the
   `device_tracker` a `person` uses, which drives the "Home / Away" chips.
5. **Terminal & SSH** (App store), for the kit. See `ha-access.md`.

## 2. Radios: only for the devices you'll actually buy

| Radio | Buy it for | Product |
|---|---|---|
| **Zigbee** | Cheap, battery-friendly contact and motion sensors, bulbs, plugs | [Connect ZBT-2](https://www.home-assistant.io/connect/zbt-2/) ($49 / €45). Runs Zigbee *or* Thread. ZBT-1 is discontinued |
| **Z-Wave** | Door locks, in-wall switches, long range | [Connect ZWA-2](https://www.home-assistant.io/connect/zwa-2/) ($69 / €59). Z-Wave 800 plus Long Range |
| **Thread / Matter** | Newer Matter-over-Thread devices | A ZBT-2 in Thread mode with the OpenThread Border Router App, plus the Matter Server App and IPv6 enabled ([Matter](https://www.home-assistant.io/integrations/matter/)) |
| **Wi-Fi / Ethernet** | Cameras, doorbells, garage controllers, the tablet | No radio needed |

A household that wants "lights, sensors, locks" usually needs Zigbee first and Z-Wave for the
locks. If they already own a hub (Hue, Lutron, SmartThings), use its integration before buying
radios.

## 3. What the panel needs, and recommended starting points

Pick by what the owner wants on the main page. Everything here has a **local**
(no-cloud-needed) Home Assistant integration.

| Panel slot | Recommended | Integration | Notes |
|---|---|---|---|
| **Wall tablet** | Amazon Fire HD 10 (13th gen, 2023). A 4 GB RAM variant appeared in 2026 | [Fully Kiosk](https://www.home-assistant.io/integrations/fully_kiosk/) | The layout's reference device (1280×800 CSS). Plan permanent USB power at the mount |
| Kiosk browser | [Fully Kiosk Browser](https://www.fully-kiosk.com/) (PLUS €8.90 per device, optional) | Fully Kiosk | PLUS adds screen and motion control from HA |
| **Doorbell** | [Reolink Video Doorbell](https://www.home-assistant.io/integrations/reolink/), PoE (preferred) or Wi-Fi | Reolink (core) | Local push. The "Visitor" sensor drives the pop-up. Use the Fluent (sub) stream on the tablet. No two-way audio in HA yet |
| Doorbell (UniFi homes) | [UniFi Protect G4 Doorbell / Pro](https://www.home-assistant.io/integrations/unifiprotect/) | UniFi Protect | Needs a UniFi OS console |
| **Cameras** | Reolink PoE cameras + a PoE switch | Reolink | Frigate (a separate NVR) later for AI detection |
| **Locks** | Z-Wave or Matter deadbolts | [Z-Wave JS](https://www.home-assistant.io/integrations/zwave_js/) / [Matter](https://www.home-assistant.io/integrations/matter/) | Local, with user codes |
| **Garage** | [ratgdo](https://github.com/ratgdo/esphome-ratgdo) (Chamberlain/LiftMaster) or [Tailwind iQ3](https://www.home-assistant.io/integrations/tailwind/) | ESPHome / Tailwind | ratgdo shows up through ESPHome, not its own integration |
| **Door, window and motion sensors** | Zigbee contact and motion sensors | [ZHA](https://www.home-assistant.io/integrations/zha/) | Feed both the floorplan and the alarm |
| **Alarm** | [Alarmo](https://github.com/nielsfaber/alarmo) (HACS) | Alarmo | Builds an `alarm_control_panel` from your sensors: modes, delays, PIN users, all in the UI |
| Alarm (no HACS) | [Manual alarm panel](https://www.home-assistant.io/integrations/manual/) | Manual (core) | YAML-only DIY alarm |
| **Lights** | Whatever they already have, or Zigbee bulbs and switches | Hue / ZHA / Z-Wave JS / Matter | One control per room is enough for the floorplan (a light group) |
| **Thermostats** | Their existing smart thermostat's integration | e.g. ecobee, Nest, Z-Wave | Shown as "current → setpoint" tiles |
| **Calendar** | [Google Calendar](https://www.home-assistant.io/integrations/google/), [CalDAV](https://www.home-assistant.io/integrations/caldav/) or [Local Calendar](https://www.home-assistant.io/integrations/local_calendar/) | — | Anyone in the room can read event titles |

## 4. A sensible first order

For a household that wants the full panel but is starting from zero, in priority order:

1. Host (Green) plus tablet (Fire HD 10) plus Fully Kiosk. **The panel is live now, with every device simulated.**
2. Doorbell (Reolink PoE). The first real device, and the one people use most.
3. Zigbee radio plus contact sensors on exterior doors, plus a few motion sensors. This makes the
   floorplan come alive and gives the alarm something to watch.
4. Alarmo.
5. Locks (Z-Wave radio plus deadbolts) and the garage controller.
6. Lights and thermostats as budget allows.

After each purchase, swap its `sim` in `panel.yaml` for the real entity and redeploy. The panel
never looks unfinished along the way.

## 5. Full integration list used by the panel

**Required**

| Piece | Kind | Why |
|---|---|---|
| Home Assistant OS | Install type | Apps + `ha` CLI |
| Terminal & SSH | App | Files, backups, config check, restarts for the kit |
| HACS | App / integration | Installs the frontend pieces below |
| ha-floorplan | HACS dashboard card | The interactive floorplan |
| button-card | HACS dashboard card | The panel's tiles, buttons and chips |
| layout-card | HACS dashboard card | The fixed grid layout |
| kiosk-mode | HACS dashboard plugin | Hides header and sidebar for the kiosk user |
| Browser Mod | HACS integration | Full-screen doorbell pop-up on the tablet |
| Template, input helpers, script, automation | Core | SIM devices, scenes, the pop-up automation |
| Met.no | Core (default) | Weather in the header |
| Person + Mobile App | Core | Who's home |
| Camera, Stream, go2rtc | Core (default) | Camera tiles and live view |

**Optional, by what the house has**

| Piece | Kind | For |
|---|---|---|
| Generic Camera | Core | SIM cameras from public still images |
| Fully Kiosk Browser | Core | Tablet screen on at doorbell ring, battery, brightness |
| Reolink / UniFi Protect / ONVIF | Core | Doorbell and cameras |
| ZHA / Z-Wave JS / Matter (+ Matter Server, OpenThread Border Router Apps) | Core + Apps | Sensors, locks, lights |
| ESPHome / Tailwind | Core | Garage door |
| Alarmo, or Manual | HACS / Core | Alarm panel |
| Google Calendar / CalDAV / Local Calendar | Core | Today panel |
| Shopping List (to-do) | Core (default) | Lists page |
