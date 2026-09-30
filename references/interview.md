# The interview

Run this as a conversation. Ask a few related questions at a time, offer a default for each, and
write answers into `panel.yaml` as you go. Most owners know their house and their daily routine
well and their entity ids not at all. Look entity ids up yourself once you're connected
(Phase 4) and confirm them with the owner then.

Read back a plain-language summary at the end of each block ("So: a Fire HD 10 in landscape by
the kitchen doorway, mainly for Sam and the kids...") and correct it before moving on.

## 1. The tablet and who it's for

| Ask | Why it matters | Default |
|---|---|---|
| Which tablet (make, model, year)? | Sets the CSS viewport and how much animation it can handle | Fire HD 10 (2023): 1280×800 |
| Landscape or portrait? | The layout is designed landscape-first; portrait squeezes the floorplan | Landscape |
| Where is it mounted, and at what height? | Glare, reach and whether it can see the front door | Kitchen, eye level |
| Who uses it most? Anyone who isn't technical? Kids? | Sets the bar for labels, confirmations and what's on the main page | Everyone in the house |
| Is it powered all the time? | Screen and battery management (smart plug cycling later) | Yes, USB |
| Anything they already hate about smart-home screens? | Cheap wins: things to leave off | — |

## 2. The house

- How many floors? Name them the way the household does ("Main floor", "Upstairs", "Basement").
- Rooms per floor, in their words. Don't correct "the office" to "study".
- Is there a floorplan image? Floorplanner, Magicplan, a listing brochure, builder drawings, a
  photo of a hand sketch all count. If not, plan to sketch it together (`floorplan.md`).
- Which doors are exterior (front, back, garage entry)? These get lock badges.
- Is there an attached garage with a door opener?

## 3. Devices, room by room

Walk the rooms in order. For each device class, record one of: **have it** (entity id, or "yes,
look it up"), **planned** (simulate it with `sim`), or **not wanted** (leave it out).

| Class | panel.yaml key | Notes |
|---|---|---|
| Lights (one control per room is enough) | `rooms[].light` | A light group or switch per room; tap toggles it |
| Motion / presence | `rooms[].motion` | binary_sensor; draws the outline and MOTION tag |
| Temperature | `rooms[].temperature` | sensor; shown as a label on the plan |
| Door locks | `floors[].locks[]` | Tap opens details; never a one-tap unlock |
| Garage door | `floors[].garage` | Tile asks for confirmation before toggling |
| Alarm panel | `alarm` | Alarmo or the vendor integration; `sim` otherwise |
| Thermostats (up to 2 on the main page) | `climate[]` | `entity: null` shows a tidy "Not installed yet" tile |
| Doorbell camera and its ring sensor | `cameras.doorbell` | Ring drives the full-screen pop-up |
| Other cameras | `cameras.others[]` | Shown on the Cameras page |

Ask about **planned** hardware explicitly ("anything you've bought but not installed, or plan to
buy?"). Planned devices are exactly what SIM entities are for. The owner sees the finished
panel on day one, and each device goes live by editing one line.

## 4. Daily life

- **People**: who lives there, and do they run the HA Companion app (for presence)? Include
  anyone the household would want to see on the panel. Ask before adding guests or kids.
- **Weather**: default `weather.forecast_home` (Met.no ships with HA).
- **Calendar**: a shared family calendar? This needs the Google Calendar (or CalDAV/local)
  integration. Anything on it will be readable by anyone standing in the kitchen, so ask
  which calendar, and whether event titles are fine to show.
- **Lists**: shopping list (`todo.shopping_list` ships with HA), chores.
- **Scenes**: "Which 3–4 buttons would you tap every day?" Offer the defaults *All off*,
  *Goodnight* (all off, lock up, close garage, arm home), *Morning* (disarm, kitchen + living
  on) and *Movie* (everything off but the living room). Use their names for them.
- **Alerts** worth interrupting for: garage open too long (default 20 min), door open while
  armed, leak, low battery. Only exceptions get a chip; normal states stay quiet.

## 5. Access and environment

- The Home Assistant URL from wherever you're running (LAN IP, `homeassistant.local`, Tailscale).
- HA version and install type (the build assumes HAOS or Supervised, because it uses add-ons and the `ha` CLI).
- Is HACS installed? If not, that's the owner's first step; it needs a GitHub login.
- Is anything already on `configuration.yaml` that we need to merge with (packages, themes,
  lovelace dashboards)?
- A backup policy? You'll take a full backup regardless and copy it off the box.

## Close the interview

Summarise: tablet and viewport, floors and rooms, the device matrix (have / simulate / skip),
people, calendar, scenes, and alerts. Get a yes. Then move to the floorplan.
