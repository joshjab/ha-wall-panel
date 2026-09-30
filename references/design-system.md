# Design system

This panel should read as an appliance: something that came with the house, not a hobby
dashboard. The rules below are what make it look that way. The generator implements all of
them. Keep them when you customise.

## Principles

1. **One main page does ~90% of the job.** Secondary pages (another floor, cameras, lists) are
   for occasional use. If the household keeps navigating away, the main page is wrong.
2. **Colour means state, nothing else.** The floorplan and chrome are muted. Colour only
   appears when something is on, open or wrong:
   - **warm** `#ffcf7a`: lights on
   - **blue** `#7cb7e8`: secure (locked, armed) and motion
   - **amber** `#f0a33a`: open or needs attention (garage open, door unlocked)
   - **red** `#ef5b5b`: problem (open while armed, alarm triggered)
3. **Hide what's normal.** Alert chips appear only when something's wrong. Placeholders say
   "Not installed yet" quietly rather than showing errors.
4. **Fingers, not cursors.** Every target is at least 48px. Actions have a label, not just an
   icon. Irreversible or outward-facing actions (close garage, disarm, unlock) ask first. The
   floorplan never unlocks a door in one tap.
5. **Calm motion.** State changes fade (0.2–0.6s). Motion outlines appear at once and fade over
   30s. Nothing loops forever, because constant animation costs battery and CPU on a cheap
   tablet and trains people to ignore it.
6. **Dark by default, on every view.** The theme is applied per view, so the panel is dark
   whatever the device or user profile says.

## Palette (`templates/theme.yaml`)

| Token | Hex | Used for |
|---|---|---|
| ground | `#0e1012` | page background |
| surface | `#16191c` | cards |
| surface-2 | `#1d2125` | chips, buttons, inset controls |
| line | `#2a2f34` | dividers |
| border | `#3a4148` | button outlines |
| text | `#ecebe7` | primary text |
| text-2 | `#a3a9ae` | labels, secondary text (≥4.5:1 on surface) |
| text-3 | `#6b7278` | disabled / inactive |
| secure | `#7cb7e8` on `#1c2d3b` | locked, armed, motion |
| attention | `#f0a33a` / `#f5b75c` on `#2a2114`, border `#6b4a1c` | open, unlocked |
| problem | `#ef5b5b` | triggered, open while armed |
| warm | `#ffcf7a` / `#ffe2ad` | lights on, weather sun |

## Type

- Large numerals: the clock (HA clock card, medium), temperatures (26px), alarm state (24px/600).
- Names 14–15px/600, secondary lines 13px in text-2.
- Floorplan labels: small caps-style uppercase at 10.5px, 8px in compact rooms.
- Keep text on one line in tiles (nowrap + ellipsis). Rephrase long states ("Tap to close")
  rather than letting them wrap.

## Layout (landscape, 1280×800)

```
┌───────────────────────── header 64 ──────────────────────────────┐
│ clock │ date ┊ weather │ people… │ alerts (only if any)  ┊ ⌂ ▣ ☰    │
├──────────────────────────┬──────────────────────┬─────────────────┤
│                          │ doorbell 16:9        │ lock            │
│                          │ (live / snapshot)    │ lock            │  236
│      floorplan           │                      │ garage          │
│      (~half width,       ├──────────────────────┴─────────────────┤
│       full height)       │ 🛡 Alarm  Disarmed   [Arm home][Arm away][Disarm] │  110
│                          ├───────────────────┬─────────────────────┤
│                          │ climate           │ climate             │  80
│                          ├───────────────────┼──────────┬──────────┤
│                          │ TODAY             │ All off  │ Goodnight│
│                          │ agenda            ├──────────┼──────────┤  rest
│                          │                   │ Morning  │ Movie    │
└──────────────────────────┴───────────────────┴──────────┴──────────┘
```

- Outer padding 16, gaps 12, card radius 16–18, no shadows.
- The floorplan column is about half the width, capped so the plan fits the full height.
- The right-most column (locks) is ~164px. The doorbell takes the remainder at 16:9.
- `minmax(0, 1fr)` on flexible columns stops long text from widening the grid.
- Fixed row heights (no `1fr` inside nested layout-cards), because an unsized nested grid
  collapses its tiles.
- **No scrolling in either direction** at the target viewport. Verify with `scrollWidth`/`scrollHeight`.

## Floorplan overlay (`templates/floorplan.css`)

Each room is one SVG group: `shade` rect, `outline` rect, `label`, and a `tag` (MOTION pill).
One rule per room sets its class from its light and motion together:

| Class | Effect |
|---|---|
| `room` | shade `rgba(6,8,10,.62)` over the room, label in text-2 |
| `room light-on` | shade becomes a warm 10% tint, label warm |
| `room motion-on` | blue outline + MOTION tag, fading out over 30s after motion clears |
| `room compact` | smaller label and tag for rooms under ~70×50 units |

Keep everything a room draws **inside its group**. A separate element layered over a room
steals its taps: ha-floorplan attaches handlers to every element with a rule. Doors are thin
bars (`door`, `door open`, `door open-armed`), locks are 36-unit circular badges (`lock`,
`lock unlocked`), and floor switches are 92×40 pills (`nav`).

## Components (`templates/button_card_templates.yaml`)

| Template | Shape | Used by |
|---|---|---|
| `wp_tile` | icon chip left, name over state | locks, garage, real thermostats |
| `wp_lock` | `wp_tile` that turns amber when unlocked | locks |
| `wp_placeholder` | muted `wp_tile` with a label | devices not installed yet |
| `wp_action` | 64px text button with outline | alarm modes |
| `wp_scene` | icon top-left, name bottom-left | scenes, back buttons |
| `wp_chip` | 44px pill with avatar initial | people |
| `wp_nav` | 48px icon button | header navigation |

The alarm panel is one button-card whose `custom_fields` hold the three `wp_action` buttons,
so it reads as one control. The active mode is highlighted in the secure colours, and Disarm is
dimmed when already disarmed.

## Mockup before building

Always show a static mockup at the exact viewport before changing Home Assistant. Use the
owner's floorplan, room names and devices, and show one "something's wrong" state. Any tool
that renders HTML at a fixed size works. Edits here are free; edits on the live panel are not.
