#!/usr/bin/env python3
"""Generate a Home Assistant wall-panel build from one panel.yaml.

Usage:
    python3 scripts/generate.py panel.yaml [--out build]

Writes, under --out (default ./build), a tree that mirrors /config on Home Assistant:

    dashboards/<dashboard>.yaml     YAML-mode dashboard (floorplan + button-card layout)
    packages/<package>.yaml         SIM placeholder entities, scene scripts, doorbell pop-up
    themes/<dashboard>.yaml         the dark theme
    www/<dashboard>/                floorplan SVG(s), stylesheet, background image(s), viewport probe

Any entity given as `sim` in panel.yaml gets a simulated stand-in (input_boolean / template
entity) so the panel is fully usable before the hardware exists. Swap in the real entity id
later and re-run. See references/panel-schema.md for every key.

Requires: PyYAML (python3-yaml).
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parent.parent
TEMPLATES = KIT / "templates"

# Layout constants, tuned on a Fire HD 10 (1280x800 CSS px) and kept in proportion elsewhere.
PAD = 16          # layout-card padding
GAP = 12          # grid gap
HEADER_H = 64
DOOR_H = 236      # doorbell / locks row
ALARM_H = 110
CLIMATE_H = 80
LOCKS_W = 164     # right-most column (lock / garage tiles)
CHROME = 64       # width HA's panel view + layout-card eat beyond the declared padding (measured)


# --------------------------------------------------------------------------- YAML output

class _Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_presenter)


def dump(data) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, width=1000, allow_unicode=True)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# --------------------------------------------------------------------------- config model

class Panel:
    """panel.yaml plus resolved entity ids (real, or generated SIM stand-ins)."""

    def __init__(self, cfg: dict, base: Path):
        self.cfg = cfg
        self.base = base
        self.dash = cfg.get("dashboard", "wall-panel")
        if "-" not in self.dash:
            sys.exit("dashboard must contain a hyphen (HA requirement), e.g. wall-panel")
        self.title = cfg.get("title", "Wall Panel")
        self.theme = cfg.get("theme_name", "Wall Panel Dark")
        self.package = cfg.get("package", slug(self.dash))
        vp = cfg.get("viewport", {})
        self.vw, self.vh = int(vp.get("width", 1280)), int(vp.get("height", 800))
        self.browser_id = cfg.get("tablet", {}).get("browser_id", f"{self.dash}-tablet")
        self.screen_switch = cfg.get("tablet", {}).get("screen_switch")
        self.alarm_hold_mode = cfg.get("alarm_hold_mode", "armed_home")
        phone = cfg.get("phone")
        self.phone = None
        if phone:
            self.phone = {"dashboard": phone.get("dashboard", "phone-panel"), "title": phone.get("title", "Home")}
            if "-" not in self.phone["dashboard"]:
                sys.exit("phone.dashboard must contain a hyphen, e.g. phone-panel")
        self.floors = cfg.get("floors") or []
        if not self.floors:
            sys.exit("panel.yaml needs at least one floor")
        self.sim = {  # collected SIM entities, rendered into the package
            "input_boolean": {}, "input_number": {}, "input_select": {},
            "lock": [], "cover": [], "alarm": None,
        }
        self._resolve()

    # -- entity resolution ---------------------------------------------------------------
    def _sim_bool(self, key, name, icon):
        self.sim["input_boolean"][key] = {"name": f"SIM · {name}", "icon": icon}
        return f"input_boolean.{key}"

    def _resolve(self):
        for floor in self.floors:
            for room in floor.get("rooms", []):
                rid, rname = room["id"], room["name"]
                if room.get("light") == "sim":
                    room["light"] = self._sim_bool(f"sim_light_{rid}", f"{rname} lights", "mdi:lightbulb")
                if room.get("motion") == "sim":
                    room["motion"] = self._sim_bool(f"sim_motion_{rid}", f"{rname} motion", "mdi:motion-sensor")
                if room.get("temperature") == "sim":
                    key = f"sim_temp_{rid}"
                    self.sim["input_number"][key] = {
                        "name": f"SIM · {rname} temperature", "min": 55, "max": 90, "step": 1,
                        "initial": 71, "unit_of_measurement": "°F"}
                    room["temperature"] = f"input_number.{key}"
            for lock in floor.get("locks", []):
                if lock.get("entity") == "sim":
                    backing = self._sim_bool(f"sim_{lock['id']}_locked", f"{lock['name']} locked", "mdi:lock")
                    self.sim["lock"].append((lock["name"], lock["id"], backing))
                    lock["entity"] = f"lock.sim_{slug(lock['name'])}"
            garage = floor.get("garage")
            if garage and garage.get("entity") == "sim":
                backing = self._sim_bool("sim_garage_open", f"{garage.get('name', 'Garage')} door open", "mdi:garage-open")
                self.sim["cover"].append((garage.get("name", "Garage"), backing))
                garage["entity"] = f"cover.sim_{slug(garage.get('name', 'Garage'))}_door"

        alarm = self.cfg.get("alarm")
        if alarm == "sim":
            self.sim["input_select"]["sim_alarm_state"] = {
                "name": "SIM · Alarm state",
                "options": ["disarmed", "armed_home", "armed_away", "triggered"],
                "initial": "disarmed"}
            self.sim["alarm"] = "input_select.sim_alarm_state"
            self.cfg["alarm"] = "alarm_control_panel.sim_alarm"

        cams = self.cfg.get("cameras") or {}
        door = cams.get("doorbell")
        if door:
            if door.get("entity") == "sim":
                door["entity"] = f"camera.sim_{slug(door.get('name', 'doorbell'))}"
            if door.get("ring") == "sim":
                door["ring"] = self._sim_bool("sim_doorbell_ring", "Doorbell ring", "mdi:doorbell")
                door["ring_is_sim"] = True
        for cam in cams.get("others", []) or []:
            if cam.get("entity") == "sim":
                cam["entity"] = f"camera.sim_{slug(cam['name'])}"

    # -- convenience -------------------------------------------------------------------
    @property
    def main(self):
        return self.floors[0]

    def floor_path(self, floor):
        return "home" if floor is self.main else floor["id"]

    def all_lights(self):
        return [r["light"] for f in self.floors for r in f.get("rooms", []) if r.get("light")]

    def all_locks(self):
        return [l["entity"] for f in self.floors for l in f.get("locks", [])]

    def garages(self):
        return [f["garage"] for f in self.floors if f.get("garage")]

    def camera_badges(self, floor):
        """Cameras with a `badge: [x, y]` on this floor (default: the main floor)."""
        cams = self.cfg.get("cameras") or {}
        items = ([cams["doorbell"]] if cams.get("doorbell") else []) + list(cams.get("others") or [])
        return [c for c in items if c.get("badge") and c.get("entity")
                and c.get("floor", self.main["id"]) == floor["id"]]

    @property
    def mode_sensor(self):
        """Trigger-based sensor holding the last scene run (the phone's Mode button shows it)."""
        return f"sensor.{slug(self.title + ' mode')}" if self.cfg.get("scenes") else None

    def scene_script(self, scene: dict) -> str:
        return scene.get("script") or f"script.{self.package}_{slug(scene['name'])}"

    def www(self, name):
        return f"/local/{self.dash}/{name}"


# --------------------------------------------------------------------------- floorplan SVG

def floor_svg(p: Panel, floor: dict) -> str:
    w, h = floor.get("width"), floor.get("height")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f"<!-- {floor['name']}: generated by ha-wall-panel. Coordinates are in image pixels. -->",
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">']
    if floor.get("image"):
        href = p.www(Path(floor["image"]).name)
        out.append(f'  <image id="background" href="{href}" xlink:href="{href}" x="0" y="0" width="{w}" height="{h}"/>')
    out.append('  <g id="rooms">')
    for room in floor.get("rooms", []):
        x, y, rw, rh = room_bbox(room)
        compact = rw < 70 or rh < 50
        label = room.get("label", room["name"]).upper()
        tag_w, tag_h = (38, 11) if compact else (46, 13)
        label_cls = "label small" if compact else "label"
        anchor = ""
        if room.get("label_at") == "center":  # e.g. a closet marked "C"
            lx, ly = x + rw / 2, y + rh / 2 + (3 if compact else 4)
            anchor = ' text-anchor="middle"'
        elif room.get("label_at"):
            lx, ly = room["label_at"]
        else:
            lx, ly = x + (4 if compact else 8), y + (13 if compact else 15)
        ty = ly + 7
        rid = room["id"]
        if room.get("poly"):
            pts = " ".join(f"{px},{py}" for px, py in room["poly"])
            # The outline is drawn twice as thick and clipped to the room, so it hugs the inside
            # of the walls the way the inset rect does for a rectangular room.
            shapes = [f'      <clipPath id="clip.{rid}"><polygon points="{pts}"/></clipPath>',
                      f'      <polygon class="shade" points="{pts}"/>',
                      f'      <polygon class="outline" points="{pts}" clip-path="url(#clip.{rid})" '
                      'style="stroke-width:5;stroke-linejoin:round"/>']
        else:
            shapes = [f'      <rect class="shade" x="{x}" y="{y}" width="{rw}" height="{rh}" rx="3"/>',
                      f'      <rect class="outline" x="{x + 1.5}" y="{y + 1.5}" width="{rw - 3}" height="{rh - 3}" rx="4"/>']
        tag = ([] if room.get("label_at") == "center" or not room.get("motion") else
               [f'      <g class="tag"><rect x="{lx}" y="{ty}" width="{tag_w}" height="{tag_h}" rx="3"/>'
                f'<text x="{lx + tag_w / 2}" y="{ty + tag_h - 3}" text-anchor="middle">MOTION</text></g>'])
        out += ([f'    <g id="room.{rid}" class="{room_base_class(room)}">'] + shapes +
                [f'      <text class="{label_cls}" x="{lx}" y="{ly}"{anchor}>{label}</text>'] + tag + ["    </g>"])
    out.append("  </g>")
    for room in floor.get("rooms", []):
        if room.get("temperature"):
            x, y, rw, rh = room_bbox(room)
            tx, ty = room.get("temp_at", [x + rw - 7, y + rh - 7])
            out.append(f'  <text id="temp.{room["id"]}" class="temp" x="{tx}" y="{ty}" text-anchor="end">--°</text>')
    garage = floor.get("garage")
    if garage and garage.get("bar"):
        bx, by, bw, bh = garage["bar"]
        out.append(f'  <rect id="door.garage" class="door" x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="3"/>')
    for lock in floor.get("locks", []):
        if not lock.get("badge"):
            continue
        cx, cy = lock["badge"]
        r = lock.get("badge_r", 26)  # big enough to press and hold on a phone
        k = r / 18
        out += [
            f'  <g id="lock.{lock["id"]}" class="lock">',
            f'    <circle cx="{cx}" cy="{cy}" r="{r}"/>',
            f'    <path d="M{cx - 7.5 * k} {cy - 1 * k}v{-4 * k}a{7.5 * k} {7.5 * k} 0 0 1 {15 * k} 0v{4 * k}" fill="none" '
            f'stroke-width="{2.6 * k:.2f}" stroke-linecap="round"/>',
            f'    <rect x="{cx - 11 * k}" y="{cy - 1 * k}" width="{22 * k}" height="{13 * k}" rx="{2.5 * k}"/>',
            "  </g>"]
    for cam in p.camera_badges(floor):
        cx, cy = cam["badge"]
        r = cam.get("badge_r", 22)
        k = r / 18
        # Camera body + lens, drawn on the same 18-unit grid as the lock glyph.
        out += [
            f'  <g id="cam.{slug(cam["name"])}" class="cam">',
            f'    <circle cx="{cx}" cy="{cy}" r="{r}"/>',
            f'    <rect x="{cx - 10 * k:.1f}" y="{cy - 6 * k:.1f}" width="{14 * k:.1f}" height="{12 * k:.1f}" rx="{2.5 * k:.1f}"/>',
            f'    <path d="M{cx + 5 * k:.1f} {cy - 2 * k:.1f}l{6 * k:.1f} {-3.5 * k:.1f}v{11 * k:.1f}l{-6 * k:.1f} {-3.5 * k:.1f}z"/>',
            "  </g>"]
    if garage and garage.get("button"):
        out += control_svg("ctl.garage", "", garage["button"], "garage", garage.get("name", "Garage").upper() + " · HOLD", "ctlstate.garage")
    if floor.get("alarm_button") and p.cfg.get("alarm"):
        out += control_svg("ctl.alarm", "", floor["alarm_button"], "shield", "ALARM · HOLD", "ctlstate.alarm")
    for sc, box in scene_boxes(p, floor):
        glyph = SCENE_ICON.get(sc.get("preset", slug(sc["name"])), "play")
        out += control_svg(f"scene.{slug(sc['name'])}", "scene", box, glyph, sc["name"])
    for nav in floor.get("stairs", []) or []:
        sx, sy = nav["at"]
        target = next(f for f in p.floors if f["id"] == nav["to"])
        label = target["name"] if len(target["name"]) <= 9 else "Stairs"
        out += [
            f'  <g id="nav.{nav["to"]}" class="nav">',
            f'    <rect x="{sx}" y="{sy}" width="92" height="40" rx="20"/>',
            f'    <path d="M{sx + 14} {sy + 29}h7v-7h7v-7h8" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
            f'    <text x="{sx + 44}" y="{sy + 25}">{label}</text>',
            "  </g>"]
    out.append("</svg>")
    return "\n".join(out) + "\n"


def placeholder_svg(p: Panel, floor: dict) -> str:
    """For a floor with no plan yet: a dashed frame and a way back."""
    back = next((n for n in floor.get("stairs", []) or []), {"to": p.main["id"]})
    target = next(f for f in p.floors if f["id"] == back["to"])
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- {floor['name']}: placeholder until a plan exists. Generated by ha-wall-panel. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 516 540" width="516" height="540">
  <rect x="8" y="8" width="500" height="524" rx="14" fill="none" stroke="#2a2f34" stroke-width="2" stroke-dasharray="8 8"/>
  <text x="258" y="250" text-anchor="middle" class="placeholder-title">{floor['name']} plan coming</text>
  <text x="258" y="278" text-anchor="middle" class="placeholder-sub">Add a floorplan image for this floor to fill this in</text>
  <g id="nav.{target['id']}" class="nav">
    <rect x="203" y="310" width="110" height="40" rx="20"/>
    <text x="258" y="335" text-anchor="middle">{target['name']}</text>
  </g>
</svg>
'''


# 24-unit stroke icons used by the on-plan controls (same glyph family as the mockup).
ICONS = {
    "shield": "M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z",
    "garage": "M3 21V9l9-5 9 5v12M7 21v-8h10v8",
    "power": "M12 3v8M6.3 6.3a8 8 0 1 0 11.4 0",
    "night": "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
    "sun": "M16 12a4 4 0 1 1-8 0a4 4 0 1 1 8 0zM12 2v2M12 20v2M2 12h2M20 12h2",
    "tv": "M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM8 21h8",
    "play": "M8 5v14l11-7z",
}
SCENE_ICON = {"all_off": "power", "goodnight": "night", "morning": "sun", "movie": "tv"}


def icon(name: str, x: float, y: float, size: float = 22) -> str:
    k = size / 24
    return (f'<path class="ic" transform="translate({x} {y}) scale({k:.3f})" d="{ICONS[name]}" '
            f'fill="none" stroke-width="{2 / k:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')


def control_svg(el_id: str, cls: str, box, glyph: str, label: str, state_id: str | None = None) -> list:
    """A labelled on-plan button: rounded rect, icon, label and (optionally) a live state line."""
    x, y, w, h = box
    ic = min(26, h - 20)
    lines = [f'  <g id="{el_id}" class="ctl {cls}">',
             f'    <rect class="bg" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/>',
             "    " + icon(glyph, x + 12, y + (h - ic) / 2, ic)]
    tx = x + 12 + ic + 10
    if state_id:
        lines += [f'    <text class="ctl-label" x="{tx}" y="{y + h / 2 - 4}">{label}</text>',
                  f'    <text id="{state_id}" class="ctl-state" x="{tx}" y="{y + h / 2 + 13}">…</text>']
    else:
        lines.append(f'    <text class="ctl-name" x="{tx}" y="{y + h / 2 + 5}">{label}</text>')
    return lines + ["  </g>"]


def scene_boxes(p: "Panel", floor: dict):
    """Split the floor's scene_buttons area into a 2x2 grid, one box per scene (max 4)."""
    if not floor.get("scene_buttons"):
        return []
    x, y, w, h = floor["scene_buttons"]
    g = 8
    bw, bh = (w - g) / 2, (h - g) / 2
    scenes = (p.cfg.get("scenes") or [])[:4]
    return [(sc, (x + (i % 2) * (bw + g), y + (i // 2) * (bh + g), bw, bh)) for i, sc in enumerate(scenes)]


def room_bbox(room: dict):
    """[x, y, w, h] of a room given as `rect` or as a `poly` outline."""
    if room.get("poly"):
        xs, ys = [pt[0] for pt in room["poly"]], [pt[1] for pt in room["poly"]]
        return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
    return room["rect"]


def room_base_class(room: dict) -> str:
    x, y, rw, rh = room_bbox(room)
    return "room compact" if (rw < 70 or rh < 50) else "room"


# --------------------------------------------------------------------------- floorplan rules

def floor_rules(p: Panel, floor: dict, dash: str | None = None) -> list:
    dash = dash or p.dash
    rules = []
    for room in floor.get("rooms", []):
        light, motion = room.get("light"), room.get("motion")
        ents = [e for e in (light, motion) if e]
        if not ents:
            continue
        base = room_base_class(room)
        js = (f"> var light = hass.states['{light}'];\n" if light else "> var light = null;\n")
        js += (f"var motion = hass.states['{motion}'];\n" if motion else "var motion = null;\n")
        js += (f"var cls = '{base}';\n"
               "if (light && light.state === 'on') cls += ' light-on';\n"
               "if (motion && motion.state === 'on') cls += ' motion-on';\n"
               "return cls;")
        rule = {"entities": ents, "element": f"room.{room['id']}",
                "state_action": {"action": "call-service", "service": "floorplan.class_set",
                                 "service_data": {"class": js}}}
        if light:
            rule["tap_action"] = {"action": "call-service", "service": "homeassistant.toggle",
                                  "service_data": {"entity_id": light}}
            rule["hold_action"] = {"action": "more-info", "entity": light}
        else:
            rule["tap_action"] = {"action": "more-info", "entity": motion}
        rules.append(rule)

    for room in floor.get("rooms", []):
        if room.get("temperature"):
            rules.append({"entity": room["temperature"], "element": f"temp.{room['id']}",
                          "state_action": {"action": "call-service", "service": "floorplan.text_set",
                                           "service_data": {"text": "${Math.round(Number(entity.state))}°"}}})

    garage = floor.get("garage")
    if garage and garage.get("bar"):
        alarm = p.cfg.get("alarm")
        js = f"> var door = hass.states['{garage['entity']}'];\n"
        js += f"var alarm = hass.states['{alarm}'];\n" if alarm else "var alarm = null;\n"
        js += ("if (!door || door.state === 'closed') return 'door';\n"
               "return (alarm && alarm.state.startsWith('armed')) ? 'door open-armed' : 'door open';")
        rules.append({"entities": [e for e in (garage["entity"], alarm) if e], "element": "door.garage",
                      "state_action": {"action": "call-service", "service": "floorplan.class_set",
                                       "service_data": {"class": js}},
                      "tap_action": {"action": "more-info", "entity": garage["entity"]}})

    for lock in floor.get("locks", []):
        if lock.get("badge"):
            rules.append({"entity": lock["entity"], "element": f"lock.{lock['id']}",
                          "state_action": {"action": "call-service", "service": "floorplan.class_set",
                                           "service_data": {"class": '${entity.state === "locked" ? "lock" : "lock unlocked"}'}},
                          "tap_action": {"action": "more-info", "entity": lock["entity"]},
                          # Press and hold locks/unlocks (no confirmation: the hold is deliberate).
                          "hold_action": {"action": "call-service", "service": "script.turn_on",
                                          "service_data": {"entity_id": f"script.{p.package}_toggle_lock_{lock['id']}"}}})

    for cam in p.camera_badges(floor):
        # ha-floorplan only opens more-info from a rule that names an entity, so give it one.
        rules.append({"entity": cam["entity"], "element": f"cam.{slug(cam['name'])}",
                      "tap_action": {"action": "more-info", "entity": cam["entity"]}})

    if garage and garage.get("button"):
        alarm = p.cfg.get("alarm")
        js = f"> var door = hass.states['{garage['entity']}'];\n"
        js += f"var alarm = hass.states['{alarm}'];\n" if alarm else "var alarm = null;\n"
        js += ("if (!door || door.state === 'closed') return 'ctl';\n"
               "return (alarm && alarm.state.startsWith('armed')) ? 'ctl problem' : 'ctl attention';")
        hold = {"action": "call-service", "service": "cover.toggle", "service_data": {"entity_id": garage["entity"]}}
        rules.append({"entities": [e for e in (garage["entity"], alarm) if e], "element": "ctl.garage",
                      "state_action": {"action": "call-service", "service": "floorplan.class_set",
                                       "service_data": {"class": js}},
                      "tap_action": {"action": "more-info", "entity": garage["entity"]}, "hold_action": hold})
        rules.append({"entity": garage["entity"], "element": "ctlstate.garage",
                      "state_action": {"action": "call-service", "service": "floorplan.text_set",
                                       "service_data": {"text": "${entity.state === 'open' ? 'Open' : "
                                                                "(entity.state === 'closed' ? 'Closed' : entity.state)}"}}})

    alarm = p.cfg.get("alarm")
    if floor.get("alarm_button") and alarm:
        rules.append({"entity": alarm, "element": "ctl.alarm",
                      "state_action": {"action": "call-service", "service": "floorplan.class_set",
                                       "service_data": {"class": "${entity.state === 'triggered' ? 'ctl problem' : "
                                                                 "(entity.state.startsWith('armed') ? 'ctl secure' : "
                                                                 "(entity.state === 'disarmed' ? 'ctl' : 'ctl attention'))}"}},
                      "tap_action": {"action": "more-info", "entity": alarm},
                      "hold_action": {"action": "call-service", "service": "script.turn_on",
                                      "service_data": {"entity_id": f"script.{p.package}_toggle_alarm"}}})
        rules.append({"entity": alarm, "element": "ctlstate.alarm",
                      "state_action": {"action": "call-service", "service": "floorplan.text_set",
                                       "service_data": {"text": ALARM_TEXT_JS}}})

    for sc, _box in scene_boxes(p, floor):
        rules.append({"element": f"scene.{slug(sc['name'])}",
                      "tap_action": {"action": "call-service", "service": "script.turn_on",
                                     "service_data": {"entity_id": p.scene_script(sc)}}})

    for nav in floor.get("stairs", []) or []:
        target = next(f for f in p.floors if f["id"] == nav["to"])
        rules.append({"element": f"nav.{nav['to']}",
                      "tap_action": {"action": "navigate", "navigation_path": f"/{dash}/{p.floor_path(target)}"}})
    return rules


ALARM_TEXT_JS = ("> var names = {disarmed: 'Disarmed', armed_home: 'Armed home', armed_away: 'Armed away', "
                 "armed_night: 'Armed night', armed_vacation: 'Armed vacation', armed_custom_bypass: 'Armed', "
                 "arming: 'Arming…', pending: 'Pending…', triggered: 'TRIGGERED'};\n"
                 "return names[entity.state] || entity.state;")


def floorplan_card(p: Panel, floor: dict, version: str, dash: str | None = None, **extra) -> dict:
    dash = dash or p.dash
    image = "floor-" + floor["id"] + ".svg"
    rules = floor_rules(p, floor, dash)
    if not floor.get("image"):  # placeholder floor: only its nav element
        back = next((n for n in floor.get("stairs", []) or []), {"to": p.main["id"]})
        target = next(f for f in p.floors if f["id"] == back["to"])
        rules = [{"element": f"nav.{target['id']}",
                  "tap_action": {"action": "navigate", "navigation_path": f"/{dash}/{p.floor_path(target)}"}}]
    full_height = extra.pop("full_height", False)
    card = {"type": "custom:floorplan-card", **extra, "full_height": full_height,
            "config": {"image": f"{p.www(image)}?v={version}",
                       "stylesheet": f"{p.www('floorplan.css')}?v={version}",
                       "console_log_level": "warn",
                       "rules": rules}}
    return card


# --------------------------------------------------------------------------- dashboard cards

def btn(**kw) -> dict:
    return {"type": "custom:button-card", **kw}


def grid(areas=None, cols=None, rows=None, gap=GAP, pad=None, cards=None, area=None) -> dict:
    layout = {}
    if pad is not None:
        layout["padding"] = f"{pad}px"
    layout["grid-gap"] = f"{gap}px"
    if cols:
        layout["grid-template-columns"] = cols
    if rows:
        layout["grid-template-rows"] = rows
    if areas:
        layout["grid-template-areas"] = "\n".join(f'"{a}"' for a in areas) + "\n"
    card = {"type": "custom:layout-card", "layout_type": "custom:grid-layout", "layout": layout,
            "cards": cards or []}
    if area:
        card = {"type": card["type"], "view_layout": {"grid-area": area}, **{k: v for k, v in card.items() if k != "type"}}
    return card


def at(card: dict, area: str) -> dict:
    return {**{"type": card["type"]}, "view_layout": {"grid-area": area},
            **{k: v for k, v in card.items() if k != "type"}}


DIVIDER = {"card": ["width: 1px", "height: 44px", "margin-top: 10px", "background: \"#2a2f34\"",
                    "border-radius: 0", "box-shadow: none"]}


def _styles(d: dict) -> dict:
    """Turn {'card': ['width: 1px', ...]} into button-card's list-of-maps style form."""
    out = {}
    for part, rules in d.items():
        items = []
        for r in rules:
            k, v = r.split(":", 1)
            items.append({k.strip(): v.strip().strip('"')})
        out[part] = items
    return out


WEATHER_NAMES = ("{'clear-night': 'Clear', 'cloudy': 'Cloudy', 'exceptional': 'Exceptional', 'fog': 'Fog', "
                 "'hail': 'Hail', 'lightning': 'Lightning', 'lightning-rainy': 'Thunderstorms', "
                 "'partlycloudy': 'Partly cloudy', 'pouring': 'Pouring', 'rainy': 'Rain', 'snowy': 'Snow', "
                 "'snowy-rainy': 'Sleet', 'sunny': 'Sunny', 'windy': 'Windy', 'windy-variant': 'Windy'}")


def header(p: Panel) -> dict:
    people = p.cfg.get("people", []) or []
    cols = ["150px", "150px", "1px", "190px"] + ["150px"] * len(people) + ["minmax(0, 1fr)", "1px", "48px", "48px", "48px"]
    names = ["clock", "date", "div1", "weather"] + [f"p{i}" for i in range(len(people))] + ["alerts", "div2", "nav1", "nav2", "nav3"]
    cards = [
        at({"type": "clock", "clock_size": "medium", "no_background": True}, "clock"),
        at({"type": "markdown", "text_only": True,
            "content": "{{ now().strftime('%A') }}<br>{{ now().strftime('%B %-d') }}\n"}, "date"),
        at(btn(styles=_styles(DIVIDER)), "div1"),
    ]
    weather = p.cfg.get("weather")
    if weather:
        cards.append(at(btn(
            entity=weather, show_label=True, show_state=False,
            name="[[[ return Math.round(entity.attributes.temperature) + '°' ]]]",
            label=f"[[[ var names = {WEATHER_NAMES};\nreturn names[entity.state] || entity.state; ]]]",
            tap_action={"action": "more-info"},
            # Rows sized to their text and centred as a block, so temperature + condition sit on the
            # header's centre line with the clock and chips (two 1fr rows pushed it low).
            styles={"card": [{"height": "64px"}, {"padding": "0 4px"}, {"background": "transparent"}, {"box-shadow": "none"}],
                    "grid": [{"grid-template-areas": '"i n" "i l"'}, {"grid-template-columns": "34px 1fr"},
                             {"grid-template-rows": "min-content min-content"}, {"align-content": "center"},
                             {"column-gap": "10px"}, {"row-gap": "3px"}],
                    "icon": [{"width": "30px"}, {"color": "#ffcf7a"}],
                    "name": [{"justify-self": "start"}, {"align-self": "end"}, {"font-size": "26px"}, {"font-weight": "600"},
                             {"line-height": "1"}, {"color": "#ecebe7"}],
                    "label": [{"justify-self": "start"}, {"align-self": "start"}, {"font-size": "13px"}, {"color": "#a3a9ae"}]}),
            "weather"))
    palette = ["#2c4a63", "#5a4a2c", "#3d5a3a", "#5a3a4f"]
    for i, person in enumerate(people):
        nm = person["name"]
        cards.append(at(btn(
            template="wp_chip", entity=person["entity"],
            name=("[[[ var where = entity.state === 'home' ? 'Home' : entity.state === 'not_home' ? 'Away' : entity.state;\n"
                  f"return '{nm} <span style=\"color:#a3a9ae\">· ' + where + '</span>'; ]]]"),
            custom_fields={"av": person.get("initial", nm[:1].upper())},
            styles={"custom_fields": {"av": [{"background": person.get("color", palette[i % len(palette)])}]}}),
            f"p{i}"))
    garages = p.garages()
    if garages:
        g = garages[0]
        cards.append(at({"type": "conditional",
                         "conditions": [{"condition": "state", "entity": f"binary_sensor.{p.package}_garage_open_long", "state": "on"}],
                         "card": btn(entity=g["entity"], icon="mdi:alert-circle-outline",
                                     name=f"{g.get('name', 'Garage')} open {p.cfg.get('alerts', {}).get('garage_open_minutes', 20)}+ min",
                                     show_state=False, tap_action={"action": "more-info"},
                                     styles={"card": [{"height": "40px"}, {"margin-top": "12px"}, {"padding": "0 14px"},
                                                      {"border-radius": "20px"}, {"background": "#2a2114"},
                                                      {"border": "1px solid #6b4a1c"}, {"box-shadow": "none"}],
                                             "grid": [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "20px 1fr"},
                                                      {"column-gap": "8px"}],
                                             "icon": [{"width": "16px"}, {"color": "#f5b75c"}],
                                             "name": [{"justify-self": "start"}, {"font-size": "14px"}, {"font-weight": "600"},
                                                      {"color": "#f5b75c"}]})}, "alerts"))
    cards.append(at(btn(styles=_styles(DIVIDER)), "div2"))
    nav = [("nav1", "mdi:home", f"/{p.dash}/home", True),
           ("nav2", "mdi:cctv", f"/{p.dash}/cameras", False),
           ("nav3", "mdi:format-list-checks", f"/{p.dash}/lists", False)]
    for area, icon, path, active in nav:
        c = btn(template="wp_nav", icon=icon, tap_action={"action": "navigate", "navigation_path": path})
        if active:
            c["styles"] = {"card": [{"background": "#262b30"}], "icon": [{"color": "#ecebe7"}]}
        cards.append(at(c, area))
    return grid(areas=[" ".join(names)], cols=" ".join(cols), rows=f"{HEADER_H}px", gap=10, cards=cards, area="header")


def placeholder(name, label="Not installed yet", icon="mdi:help-circle-outline") -> dict:
    return btn(template="wp_placeholder", icon=icon, name=name, label=label, tap_action={"action": "none"})


def cam_view(cam: dict, default: str = "auto") -> str:
    """picture-entity `camera_view` for a camera. `live` streams (WebRTC via go2rtc); `auto` is a
    still that refreshes every ~10 s. The doorbell defaults to live, everything else to a still,
    so only one stream runs on the tablet at a time. `view:` on the camera overrides either."""
    return cam.get("view") or default


def doorbell_card(p: Panel) -> dict:
    door = (p.cfg.get("cameras") or {}).get("doorbell")
    if not door or not door.get("entity"):
        return {"type": "markdown",
                "content": "### Front door\nDoorbell not installed yet.\n\nThe live view appears here once it's set up, "
                           "and pops up full screen when someone rings.\n"}
    return {"type": "picture-entity", "entity": door["entity"], "name": door.get("name", "Front door"),
            "camera_view": cam_view(door, "live"), "aspect_ratio": "16:9", "show_state": False}


def locks_column(p: Panel) -> dict:
    # The wall panel's tiles act on a tap (hold shows details). Unlocking and moving the garage
    # door ask first; locking doesn't. The on-plan buttons keep press-and-hold, because the same
    # plan is on a phone that lives in a pocket.
    tiles = []
    for f in p.floors:
        for lock in f.get("locks", []):
            tiles.append(btn(template="wp_lock", entity=lock["entity"], name=lock["name"],
                             tap_action={"action": "perform-action", "perform_action": "script.turn_on",
                                         "target": {"entity_id": f"script.{p.package}_toggle_lock_{lock['id']}"},
                                         "confirmation": (f"[[[ return entity.state === 'locked' ? "
                                                          f"{{text: 'Unlock the {lock['name'].lower()}?'}} : false ]]]")},
                             hold_action={"action": "more-info"}))
    for g in p.garages():
        amber = [{"background": "#2a2114"}, {"border": "1px solid #6b4a1c"}]
        gname = g.get("name", "Garage").lower()
        tiles.append(btn(
            template="wp_tile", entity=g["entity"], name=g.get("name", "Garage"),
            icon="[[[ return entity.state === 'open' ? 'mdi:garage-open' : 'mdi:garage' ]]]",
            state_display="[[[ return entity.state === 'open' ? 'Tap to close' : 'Closed' ]]]",
            tap_action={"action": "perform-action", "perform_action": "cover.toggle",
                        "target": {"entity_id": g["entity"]},
                        "confirmation": {"text": f"[[[ return entity.state === 'open' ? 'Close the {gname} door?' "
                                                 f": 'Open the {gname} door?' ]]]"}},
            hold_action={"action": "more-info"},
            state=[{"value": "open", "styles": {"card": amber, "img_cell": [{"background": "#f0a33a"}],
                                                "icon": [{"color": "#0e1012"}], "name": [{"color": "#f5b75c"}],
                                                "state": [{"color": "#f5b75c"}]}}]))
    tiles = tiles[:3]
    while len(tiles) < 3:
        tiles.append(placeholder("Lock", icon="mdi:lock-outline"))
    rows = " ".join(["70px", "70px", "72px"])
    return grid(cols="minmax(0, 1fr)", rows=rows, cards=tiles, area="locks")


def alarm_card(p: Panel) -> dict:
    alarm = p.cfg.get("alarm")
    if not alarm:
        return at(placeholder("Alarm", icon="mdi:shield-outline"), "alarm")

    def mode(name, service, active_state, dim_when=None, confirm=None):
        # A tap acts (Disarm asks first); hold shows details.
        tap = {"action": "perform-action", "perform_action": f"alarm_control_panel.{service}",
               "target": {"entity_id": alarm}}
        if confirm:
            tap["confirmation"] = {"text": confirm}
        c = btn(template="wp_action", entity=alarm, name=name, tap_action=tap, hold_action={"action": "more-info"})
        states = []
        if active_state:
            states.append({"value": active_state, "styles": {"card": [{"background": "#1c2d3b"}, {"border": "1px solid #3d5a73"}],
                                                            "name": [{"color": "#bcdcf6"}]}})
        if dim_when:
            states.append({"value": dim_when, "styles": {"name": [{"color": "#6b7278"}]}})
        if states:
            c["state"] = states
        return {"card": c}

    return at(btn(
        entity=alarm, name="Alarm", show_state=True,
        icon="[[[ return entity.state === 'disarmed' ? 'mdi:shield-outline' : 'mdi:shield-lock' ]]]",
        tap_action={"action": "more-info"},
        styles={"card": [{"height": "100%"}, {"padding": "0 12px 0 18px"}, {"border-radius": "18px"},
                         {"background": "#16191c"}, {"box-shadow": "none"}],
                "grid": [{"grid-template-areas": '"i n home away off" "i s home away off"'},
                         {"grid-template-columns": "30px minmax(0, 1fr) 104px 104px 104px"},
                         {"grid-template-rows": "1fr 1fr"}, {"column-gap": "12px"}],
                "icon": [{"width": "30px"},
                         {"color": "[[[ return entity.state === 'disarmed' ? '#a3a9ae' : (entity.state === 'triggered' ? '#ef5b5b' : '#7cb7e8') ]]]"}],
                "name": [{"justify-self": "start"}, {"align-self": "end"}, {"font-size": "13px"}, {"color": "#a3a9ae"}],
                "state": [{"justify-self": "start"}, {"align-self": "start"}, {"font-size": "24px"}, {"font-weight": "600"},
                          {"line-height": "1.15"}, {"white-space": "nowrap"},
                          {"color": "[[[ return entity.state === 'triggered' ? '#ef5b5b' : '#ecebe7' ]]]"}],
                "custom_fields": {"home": [{"align-self": "center"}], "away": [{"align-self": "center"}],
                                  "off": [{"align-self": "center"}]}},
        custom_fields={"home": mode("Arm home", "alarm_arm_home", "armed_home"),
                       "away": mode("Arm away", "alarm_arm_away", "armed_away"),
                       "off": mode("Disarm", "alarm_disarm", None, dim_when="disarmed", confirm="Disarm the alarm?")}),
        "alarm")


def climate_row(p: Panel) -> dict:
    cards = []
    for c in (p.cfg.get("climate") or [])[:2]:
        if c.get("entity"):
            cards.append(btn(
                template="wp_tile", entity=c["entity"], name=c["name"], icon="mdi:thermostat",
                state_display=("[[[ var a = entity.attributes; var cur = Math.round(a.current_temperature);\n"
                               "var set = a.temperature != null ? Math.round(a.temperature) : null;\n"
                               "return set != null ? cur + '° → ' + set + '°' : cur + '°'; ]]]"),
                tap_action={"action": "more-info"}))
        else:
            cards.append(placeholder(f"{c['name']} thermostat", icon="mdi:thermostat"))
    while len(cards) < 2:
        cards.append(placeholder("Thermostat", icon="mdi:thermostat"))
    return grid(cols="1fr 1fr", rows=f"{CLIMATE_H}px", cards=cards, area="climate")


def bottom_row(p: Panel, bottom_h: int) -> dict:
    cal = p.cfg.get("calendar")
    if cal:
        today = at({"type": "calendar", "entities": [cal], "initial_view": "listWeek"}, "today")
    else:
        today = at({"type": "markdown", "content": "##### TODAY\nAdd a calendar entity to show today's events here.\n"}, "today")
    scenes = []
    for s in (p.cfg.get("scenes") or [])[:4]:
        script = p.scene_script(s)
        scenes.append(btn(template="wp_scene", name=s["name"], icon=s.get("icon", "mdi:play"),
                          entity=p.mode_sensor, state=[{"value": s["name"], "styles": CHOICE_ACTIVE}],
                          tap_action={"action": "perform-action", "perform_action": "script.turn_on",
                                      "target": {"entity_id": script}}))
    row_h = (bottom_h - GAP) // 2
    scene_grid = grid(cols="1fr 1fr", rows=f"{row_h}px {row_h}px", cards=scenes, area="scenes")
    return grid(areas=["today scenes"], cols="1fr 1fr", rows=f"{bottom_h}px", cards=[today, scene_grid], area="bottom")


def home_view(p: Panel) -> dict:
    main = p.main
    avail_h = p.vh - 2 * PAD - HEADER_H - GAP
    plan_w = min(round(p.vw * 0.5), 640)
    if main.get("width") and main.get("height"):
        plan_w = min(plan_w, int(avail_h * main["width"] / main["height"]))
    door_w = p.vw - CHROME - plan_w - 2 * GAP - LOCKS_W
    bottom_h = p.vh - 2 * PAD - HEADER_H - DOOR_H - ALARM_H - CLIMATE_H - 4 * GAP
    version = str(p.cfg.get("asset_version", 1))
    cards = [
        header(p),
        floorplan_card(p, main, version, view_layout={"grid-area": "plan"}),
        at(doorbell_card(p), "door"),
        locks_column(p),
        alarm_card(p),
        climate_row(p),
        bottom_row(p, bottom_h),
    ]
    return {"title": "Home", "path": "home", "type": "panel", "theme": p.theme, "cards": [grid(
        pad=PAD,
        cols=f"{plan_w}px {door_w}px minmax(0, 1fr)",
        rows=f"{HEADER_H}px {DOOR_H}px {ALARM_H}px {CLIMATE_H}px {bottom_h}px",
        areas=["header header  header", "plan   door    locks", "plan   alarm   alarm",
               "plan   climate climate", "plan   bottom  bottom"],
        cards=cards)]}


def back_button(p: Panel) -> dict:
    return btn(template="wp_scene", name="Back home", icon="mdi:arrow-left",
               styles={"grid": [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "30px 1fr"},
                                {"grid-template-rows": "1fr"}],
                       "card": [{"height": "56px"}, {"padding": "0 14px"}]},
               tap_action={"action": "navigate", "navigation_path": f"/{p.dash}/home"})


def cameras_view(p: Panel) -> dict:
    cams = p.cfg.get("cameras") or {}
    items = []
    if cams.get("doorbell") and cams["doorbell"].get("entity"):
        items.append(cams["doorbell"])
    items += [c for c in cams.get("others", []) or [] if c.get("entity")]
    bar = [back_button(p), {"type": "markdown", "text_only": True,
                            "content": cams.get("note", "Cameras") + "\n"}]
    door = cams.get("doorbell") or {}
    if door.get("ring_is_sim"):
        bar.append(btn(template="wp_scene", name="Test doorbell ring", icon="mdi:doorbell",
                       styles={"grid": [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "30px 1fr"},
                                        {"grid-template-rows": "1fr"}],
                               "card": [{"height": "56px"}, {"padding": "0 14px"}]},
                       tap_action={"action": "perform-action", "perform_action": "input_boolean.turn_on",
                                   "target": {"entity_id": door["ring"]}}))
    else:
        bar.append({"type": "markdown", "text_only": True, "content": " \n"})
    rows = max(1, (len(items) + 1) // 2)
    areas = ["bar bar"] + [f"c{2 * r} c{2 * r + 1}" for r in range(rows)]
    # Fixed pixel rows: `1fr` rows in an unsized grid overflow and the page scrolls.
    bar_h = 56
    row_h = (p.vh - 2 * PAD - bar_h - GAP * rows - 8) // rows
    cards = [grid(cols="160px 1fr 200px", cards=bar, area="bar")]
    for i, c in enumerate(items):
        cards.append(at({"type": "picture-entity", "entity": c["entity"], "name": c.get("name", ""),
                         "camera_view": cam_view(c, "live" if c is door else "auto"),
                         "aspect_ratio": "16:9", "show_state": False}, f"c{i}"))
    return {"title": "Cameras", "path": "cameras", "type": "panel", "theme": p.theme, "cards": [grid(
        pad=PAD, cols="minmax(0, 1fr) minmax(0, 1fr)", rows=f"{bar_h}px " + " ".join([f"{row_h}px"] * rows), areas=areas, cards=cards)]}


def lists_view(p: Panel) -> dict:
    cards = [{"type": "todo-list", "entity": t, "title": (p.cfg.get("list_titles") or {}).get(t)} for t in p.cfg.get("lists", [])]
    cards = [{k: v for k, v in c.items() if v is not None} for c in cards] or [
        {"type": "markdown", "content": "No lists configured yet."}]
    return {"title": "Lists", "path": "lists", "theme": p.theme, "cards": cards + [back_button(p)]}


def dashboard(p: Panel) -> str:
    templates = yaml.safe_load((TEMPLATES / "button_card_templates.yaml").read_text())
    views = [home_view(p)]
    version = str(p.cfg.get("asset_version", 1))
    for floor in p.floors[1:]:
        views.append({"title": floor["name"], "path": p.floor_path(floor), "type": "panel", "theme": p.theme,
                      "cards": [floorplan_card(p, floor, version, full_height=True)]})
    views += [cameras_view(p), lists_view(p)]
    doc = {"kiosk_mode": {"non_admin_settings": {"kiosk": True}},
           "button_card_templates": templates,
           "title": p.title,
           "views": views}
    head = (f"# {p.title}: generated by ha-wall-panel from panel.yaml. Do not hand-edit; change panel.yaml\n"
            f"# and re-run scripts/generate.py. Designed for {p.vw}x{p.vh} CSS px (landscape tablet).\n\n")
    return head + dump(doc)


# --------------------------------------------------------------------------- phone dashboard

def phone_tabs(p: Panel, active: str) -> dict:
    d = p.phone["dashboard"]
    tabs = [("home", "Home", "mdi:floor-plan"), ("cameras", "Cameras", "mdi:cctv"),
            ("today", "Today", "mdi:calendar-today"), ("lists", "Lists", "mdi:format-list-checks")]
    cards = []
    for path, name, ic in tabs:
        c = btn(template="wp_tab", name=name, icon=ic, tap_action={"action": "navigate", "navigation_path": f"/{d}/{path}"})
        if path == active:
            c["styles"] = {"icon": [{"color": "#ecebe7"}], "name": [{"color": "#ecebe7"}],
                           "card": [{"background": "#1d2125"}]}
        cards.append(c)
    return grid(cols="repeat(4, minmax(0, 1fr))", rows="56px", gap=6, cards=cards, area="tabs")


def phone_page(p: Panel, title: str, path: str, body: list, active: str) -> dict:
    """A phone view: content stacked in one column, tab bar pinned to the bottom."""
    areas = [f"b{i}" for i in range(len(body))] + ["tabs"]
    cards = [at(c, f"b{i}") for i, c in enumerate(body)] + [phone_tabs(p, active)]
    view_grid = grid(pad=10, gap=10, cols="minmax(0, 1fr)",
                     rows=" ".join(["auto"] * (len(body) - 1) + ["1fr", "56px"]),
                     areas=areas, cards=cards)
    view_grid["layout"]["height"] = "calc(100dvh - 20px)"  # pins the tab bar to the bottom edge
    return {"title": title, "path": path, "type": "panel", "theme": p.theme, "cards": [view_grid]}


def phone_topbar(p: Panel) -> dict:
    cards = [at({"type": "clock", "clock_size": "small", "no_background": True}, "clock")]
    cols, names = ["auto"], ["clock"]
    if p.cfg.get("weather"):
        cards.append(at(btn(entity=p.cfg["weather"], show_state=False,
                            name="[[[ return Math.round(entity.attributes.temperature) + '°' ]]]",
                            tap_action={"action": "more-info"},
                            styles={"card": [{"height": "44px"}, {"background": "transparent"}, {"box-shadow": "none"}, {"padding": "0 4px"}],
                                    "grid": [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "26px auto"}, {"column-gap": "6px"}],
                                    "icon": [{"width": "22px"}, {"color": "#ffcf7a"}],
                                    "name": [{"font-size": "18px"}, {"font-weight": "600"}, {"color": "#ecebe7"}]}), "weather"))
        cols.append("auto"); names.append("weather")
    cols.append("minmax(0, 1fr)"); names.append("gap")
    cards.append(at({"type": "markdown", "text_only": True, "content": " \n"}, "gap"))
    cards.append(at(btn(template="wp_nav", icon="mdi:cog", tap_action={"action": "navigate", "navigation_path": "/config"},
                        styles={"card": [{"width": "44px"}, {"height": "44px"}, {"margin-top": "0"}]}), "cog"))
    cols.append("44px"); names.append("cog")
    return grid(areas=[" ".join(names)], cols=" ".join(cols), rows="44px", gap=8, cards=cards)


def _bm_popup(title: str, content: dict) -> dict:
    """A Browser Mod pop-up on *this* device (no browser registration needed)."""
    return {"action": "fire-dom-event",
            "browser_mod": {"service": "browser_mod.popup", "data": {"title": title, "content": content}}}


def _bm_then_close(service: str, data: dict) -> dict:
    """Pop-up choice: run one action, then close the pop-up."""
    return {"action": "fire-dom-event",
            "browser_mod": {"service": "browser_mod.sequence",
                            "data": {"sequence": [{"service": service, "data": data},
                                                  {"service": "browser_mod.close_popup", "data": {}}]}}}


CHOICE_STYLES = {"card": [{"height": "92px"}, {"padding": "12px 14px"}, {"border-radius": "16px"},
                          {"background": "#1d2125"}, {"border": "1px solid #3a4148"}, {"box-shadow": "none"}],
                 "grid": [{"grid-template-areas": '"i" "." "n"'}, {"grid-template-columns": "1fr"},
                          {"grid-template-rows": "min-content 1fr min-content"}],
                 "img_cell": [{"justify-self": "start"}, {"width": "26px"}, {"height": "26px"}],
                 "icon": [{"width": "26px"}, {"color": "#ecebe7"}],
                 "name": [{"justify-self": "start"}, {"font-size": "15px"}, {"font-weight": "600"}, {"color": "#ecebe7"}]}
CHOICE_ACTIVE = {"card": [{"background": "#1c2d3b"}, {"border": "1px solid #3d5a73"}],
                 "icon": [{"color": "#7cb7e8"}], "name": [{"color": "#bcdcf6"}]}


def mode_picker(p: Panel) -> dict:
    cards = []
    for s in (p.cfg.get("scenes") or [])[:6]:
        cards.append(btn(entity=p.mode_sensor, name=s["name"], icon=s.get("icon", "mdi:play"), show_state=False,
                         tap_action=_bm_then_close("script.turn_on", {"entity_id": p.scene_script(s)}),
                         styles=CHOICE_STYLES, state=[{"value": s["name"], "styles": CHOICE_ACTIVE}]))
    return {"type": "grid", "columns": 2, "square": False, "cards": cards}


ALARM_CHOICES = [("Disarm", "mdi:shield-outline", "alarm_disarm", "disarmed"),
                 ("Arm home", "mdi:home", "alarm_arm_home", "armed_home"),
                 ("Arm away", "mdi:walk", "alarm_arm_away", "armed_away")]


def alarm_picker(p: Panel) -> dict:
    alarm = p.cfg["alarm"]
    cards = [btn(entity=alarm, name=name, icon=ic, show_state=False,
                 tap_action=_bm_then_close(f"alarm_control_panel.{svc}", {"entity_id": alarm}),
                 styles=CHOICE_STYLES, state=[{"value": st, "styles": CHOICE_ACTIVE}])
             for name, ic, svc, st in ALARM_CHOICES]
    return {"type": "grid", "columns": 3, "square": False, "cards": cards}


def mode_button(p: Panel) -> dict:
    """Shows the current scene; tap (or hold) to pick another."""
    icons = {s["name"]: s.get("icon", "mdi:play") for s in p.cfg.get("scenes") or []}
    return btn(template="wp_tile", entity=p.mode_sensor, show_label=True, show_state=False,
               icon=f"[[[ var m = {icons!r}; return m[entity.state] || 'mdi:home-variant-outline' ]]]",
               name="[[[ return (entity.state in " + repr(icons) + ") ? entity.state : 'Mode' ]]]",
               label="Mode",
               tap_action=_bm_popup("Mode", mode_picker(p)),
               hold_action=_bm_popup("Mode", mode_picker(p)),
               styles={"grid": [{"grid-template-areas": '"i n" "i l"'}],
                       "label": [{"justify-self": "start"}, {"align-self": "start"}, {"font-size": "13px"},
                                 {"color": "#a3a9ae"}, {"white-space": "nowrap"}]})


# Shield glyph per alarm state: [shield icon, colour, inner glyph or None, tile background, border].
ALARM_GLYPH_JS = ("var s = entity.state;\n"
                  "var g = {disarmed: ['mdi:shield-outline', '#f0a33a', null, '#2a2114', '#6b4a1c'],\n"
                  "  armed_away: ['mdi:shield', '#7cb7e8', 'mdi:walk', '#1c2d3b', '#3d5a73'],\n"
                  "  armed_home: ['mdi:shield', '#7cb7e8', 'mdi:home', '#1c2d3b', '#3d5a73'],\n"
                  "  armed_night: ['mdi:shield', '#7cb7e8', 'mdi:weather-night', '#1c2d3b', '#3d5a73'],\n"
                  "  armed_vacation: ['mdi:shield', '#7cb7e8', 'mdi:airplane', '#1c2d3b', '#3d5a73'],\n"
                  "  armed_custom_bypass: ['mdi:shield', '#7cb7e8', null, '#1c2d3b', '#3d5a73'],\n"
                  "  arming: ['mdi:shield', '#f0a33a', 'mdi:timer-sand', '#2a2114', '#6b4a1c'],\n"
                  "  pending: ['mdi:shield', '#f0a33a', 'mdi:timer-sand', '#2a2114', '#6b4a1c'],\n"
                  "  triggered: ['mdi:shield', '#ef5b5b', 'mdi:exclamation-thick', '#3a1818', '#ef5b5b']}[s]\n"
                  "  || ['mdi:shield-off-outline', '#6b7278', null, '#16191c', 'transparent'];\n")


def alarm_button(p: Panel) -> dict:
    """Icon-only alarm: amber outline disarmed, blue + person away, blue + house home. Hold to change."""
    shield = ("[[[ " + ALARM_GLYPH_JS +
              "var inner = g[2] ? '<ha-icon icon=\"' + g[2] + '\" style=\"--mdc-icon-size:17px;color:#0e1012;"
              "position:absolute;left:12.5px;top:10px\"></ha-icon>' : '';\n"
              "return '<div style=\"position:relative;width:42px;height:42px\"><ha-icon icon=\"' + g[0] + "
              "'\" style=\"--mdc-icon-size:42px;color:' + g[1] + ';position:absolute;inset:0\"></ha-icon>' + inner + '</div>'; ]]]")
    bg = "[[[ " + ALARM_GLYPH_JS + "return g[3]; ]]]"
    border = "[[[ " + ALARM_GLYPH_JS + "return '1px solid ' + g[4]; ]]]"
    return btn(entity=p.cfg["alarm"], show_name=False, show_state=False, show_icon=False,
               custom_fields={"shield": shield},
               tap_action={"action": "more-info"},
               hold_action=_bm_popup("Alarm", alarm_picker(p)),
               styles={"card": [{"height": "100%"}, {"border-radius": "16px"}, {"background": bg},
                                {"border": border}, {"box-shadow": "none"}],
                       "grid": [{"grid-template-areas": '"shield"'}],
                       "custom_fields": {"shield": [{"justify-self": "center"}, {"align-self": "center"}]}})


def phone_controls(p: Panel) -> dict | None:
    """Row under the plan: Mode (wide) and the alarm shield (square)."""
    cards, cols, names = [], [], []
    if p.mode_sensor:
        cards.append(at(mode_button(p), "mode")); cols.append("minmax(0, 1fr)"); names.append("mode")
    if p.cfg.get("alarm"):
        cards.append(at(alarm_button(p), "alarm")); cols.append("72px"); names.append("alarm")
    if not cards:
        return None
    return grid(areas=[" ".join(names)], cols=" ".join(cols), rows="72px", gap=10, cards=cards)


def phone_status(p: Panel) -> dict:
    """Mode and alarm, who's home, any alert, and the thermostats: the only extras under the plan."""
    cards, names = [], []
    for i, person in enumerate(p.cfg.get("people", []) or []):
        nm = person["name"]
        cards.append(at(btn(template="wp_chip", entity=person["entity"],
                            name=("[[[ var where = entity.state === 'home' ? 'Home' : entity.state === 'not_home' ? 'Away' : entity.state;\n"
                                  f"return '{nm} <span style=\"color:#a3a9ae\">· ' + where + '</span>'; ]]]"),
                            custom_fields={"av": person.get("initial", nm[:1].upper())},
                            styles={"card": [{"margin-top": "0"}],
                                    "custom_fields": {"av": [{"background": person.get("color", "#2c4a63")}]}}), f"p{i}"))
        names.append(f"p{i}")
    people_row = grid(areas=[" ".join(names) or "."], cols=" ".join(["auto"] * max(1, len(names))) + " minmax(0, 1fr)",
                      rows="44px", gap=8, cards=cards) if names else None
    body = [c for c in [phone_controls(p), people_row] if c]
    garages = p.garages()
    if garages:
        body.append({"type": "conditional",
                     "conditions": [{"condition": "state", "entity": f"binary_sensor.{p.package}_garage_open_long", "state": "on"}],
                     "card": btn(entity=garages[0]["entity"], icon="mdi:alert-circle-outline",
                                 name=f"{garages[0].get('name', 'Garage')} open {p.cfg.get('alerts', {}).get('garage_open_minutes', 20)}+ min",
                                 show_state=False, tap_action={"action": "more-info"},
                                 styles={"card": [{"height": "40px"}, {"border-radius": "20px"}, {"background": "#2a2114"},
                                                  {"border": "1px solid #6b4a1c"}, {"box-shadow": "none"}],
                                         "grid": [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "20px 1fr"}],
                                         "icon": [{"width": "16px"}, {"color": "#f5b75c"}],
                                         "name": [{"justify-self": "start"}, {"font-size": "14px"}, {"font-weight": "600"}, {"color": "#f5b75c"}]})})
    climate = climate_row(p)
    climate.pop("view_layout", None)
    body.append(climate)
    return body


def phone_dashboard(p: Panel) -> str:
    d = p.phone["dashboard"]
    templates = yaml.safe_load((TEMPLATES / "button_card_templates.yaml").read_text())
    version = str(p.cfg.get("asset_version", 1))
    home_body = [phone_topbar(p), floorplan_card(p, p.main, version, dash=d)] + phone_status(p)
    views = [phone_page(p, "Home", "home", home_body, "home")]
    for floor in p.floors[1:]:
        views.append(phone_page(p, floor["name"], p.floor_path(floor),
                                [phone_topbar(p), floorplan_card(p, floor, version, dash=d)], "home"))
    cams = p.cfg.get("cameras") or {}
    cam_cards = []
    door = cams.get("doorbell") or {}
    if door.get("ring_is_sim"):
        cam_cards.append(btn(template="wp_scene", name="Test doorbell ring", icon="mdi:doorbell",
                             styles={"grid": [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "30px 1fr"},
                                              {"grid-template-rows": "1fr"}], "card": [{"height": "52px"}, {"padding": "0 14px"}]},
                             tap_action={"action": "perform-action", "perform_action": "input_boolean.turn_on",
                                         "target": {"entity_id": door["ring"]}}))
    for c in ([door] if door.get("entity") else []) + [c for c in cams.get("others", []) or [] if c.get("entity")]:
        cam_cards.append({"type": "picture-entity", "entity": c["entity"], "name": c.get("name", ""),
                          "camera_view": cam_view(c, "live" if c is door else "auto"),
                          "aspect_ratio": "16:9", "show_state": False})
    views.append(phone_page(p, "Cameras", "cameras", cam_cards or [{"type": "markdown", "content": "No cameras yet."}], "cameras"))
    cal = p.cfg.get("calendar")
    today = [{"type": "calendar", "entities": [cal], "initial_view": "listWeek"}] if cal else \
            [{"type": "markdown", "content": "##### TODAY\nAdd a calendar entity to show today's events here.\n"}]
    views.append(phone_page(p, "Today", "today", today, "today"))
    lists = [{"type": "todo-list", "entity": t, **({"title": (p.cfg.get("list_titles") or {})[t]}
                                                    if t in (p.cfg.get("list_titles") or {}) else {})}
             for t in p.cfg.get("lists", [])] or [{"type": "markdown", "content": "No lists configured yet."}]
    views.append(phone_page(p, "Lists", "lists", lists, "lists"))
    doc = {"kiosk_mode": {"kiosk": True},  # full screen in the Companion app; the ⚙ button opens Settings
           "button_card_templates": templates, "title": p.phone["title"], "views": views}
    head = (f"# {p.phone['title']} (phone): generated by ha-wall-panel from panel.yaml. Do not hand-edit.\n"
            f"# Same floorplan, on-plan buttons and SIM entities as /{p.dash}; portrait phones.\n\n")
    return head + dump(doc)


# --------------------------------------------------------------------------- package

def package(p: Panel) -> str:
    pkg: dict = {}
    sim = p.sim
    if sim["input_boolean"]:
        pkg["input_boolean"] = sim["input_boolean"]
    if sim["input_number"]:
        pkg["input_number"] = sim["input_number"]
    if sim["input_select"]:
        pkg["input_select"] = sim["input_select"]

    template: dict = {}
    locks = []
    for name, lid, backing in sim["lock"]:
        locks.append({"name": f"SIM {name}", "unique_id": f"{p.package}_sim_{slug(name)}_lock",
                      "state": f"{{{{ 'locked' if is_state('{backing}', 'on') else 'unlocked' }}}}",
                      "lock": [{"action": "input_boolean.turn_on", "target": {"entity_id": backing}}],
                      "unlock": [{"action": "input_boolean.turn_off", "target": {"entity_id": backing}}]})
    if locks:
        template["lock"] = locks
    covers = []
    for name, backing in sim["cover"]:
        covers.append({"name": f"SIM {name} door", "unique_id": f"{p.package}_sim_{slug(name)}_door",
                       "device_class": "garage",
                       "state": f"{{{{ 'open' if is_state('{backing}', 'on') else 'closed' }}}}",
                       "open_cover": [{"action": "input_boolean.turn_on", "target": {"entity_id": backing}}],
                       "close_cover": [{"action": "input_boolean.turn_off", "target": {"entity_id": backing}}]})
    if covers:
        template["cover"] = covers
    if sim["alarm"]:
        sel = sim["alarm"]

        def pick(opt):
            return [{"action": "input_select.select_option", "target": {"entity_id": sel}, "data": {"option": opt}}]
        template["alarm_control_panel"] = [{
            "name": "SIM Alarm", "unique_id": f"{p.package}_sim_alarm", "code_arm_required": False,
            "state": f"{{{{ states('{sel}') }}}}",
            "arm_home": pick("armed_home"), "arm_away": pick("armed_away"), "disarm": pick("disarmed")}]
    garages = p.garages()
    if garages:
        g = garages[0]["entity"]
        domain, obj = g.split(".", 1)
        minutes = int(p.cfg.get("alerts", {}).get("garage_open_minutes", 20))
        template["binary_sensor"] = [{
            "name": f"{p.title} garage open long", "unique_id": f"{p.package}_alert_garage_open_long",
            "state": (f"{{{{ is_state('{g}', 'open')\n   and (now() - states.{domain}.{obj}.last_changed)"
                      f".total_seconds() > {minutes * 60} }}}}\n")}]
    pkg["template"] = [template] if template else []
    if p.mode_sensor:
        # Last scene run, set by the scene scripts' event. Trigger-based, so it survives restarts.
        pkg["template"].append({
            "triggers": [{"trigger": "event", "event_type": f"{p.package}_mode"}],
            "sensor": [{"name": f"{p.title} mode", "unique_id": f"{p.package}_mode",
                        "icon": "mdi:home-variant-outline", "state": "{{ trigger.event.data.mode }}"}]})
    if not pkg["template"]:
        del pkg["template"]

    scripts = {}
    lights, locks_all, garages_e = p.all_lights(), p.all_locks(), [g["entity"] for g in garages]
    alarm = p.cfg.get("alarm")
    for s in p.cfg.get("scenes") or []:
        if s.get("script"):
            continue
        preset = s.get("preset", slug(s["name"]))
        seq = []
        if preset in ("all_off", "goodnight", "movie") and lights:
            seq.append({"action": "homeassistant.turn_off", "target": {"entity_id": lights}})
        if preset == "goodnight":
            if locks_all:
                seq.append({"action": "lock.lock", "target": {"entity_id": locks_all}})
            if garages_e:
                seq.append({"action": "cover.close_cover", "target": {"entity_id": garages_e}})
            if alarm:
                seq.append({"action": "alarm_control_panel.alarm_arm_home", "target": {"entity_id": alarm}})
        if preset == "morning" and alarm:
            seq.append({"action": "alarm_control_panel.alarm_disarm", "target": {"entity_id": alarm}})
        on = s.get("lights_on") or []
        if on:
            seq.append({"action": "homeassistant.turn_on", "target": {"entity_id": [resolve_room_light(p, r) for r in on]}})
        if not seq:
            seq = [{"action": "logbook.log", "data": {"name": s["name"], "message": "scene has no actions yet"}}]
        seq.insert(0, {"event": f"{p.package}_mode", "event_data": {"mode": s["name"]}})
        scripts[f"{p.package}_{slug(s['name'])}"] = {"alias": s["name"], "icon": s.get("icon", "mdi:play"), "sequence": seq}
    # Hold-to-act helpers used by the floorplan buttons and tiles (work for real or SIM entities).
    for f in p.floors:
        for lock in f.get("locks", []):
            e = lock["entity"]
            scripts[f"{p.package}_toggle_lock_{lock['id']}"] = {
                "alias": f"Toggle {lock['name']} lock", "icon": "mdi:lock",
                "sequence": [{"if": [{"condition": "state", "entity_id": e, "state": "locked"}],
                              "then": [{"action": "lock.unlock", "target": {"entity_id": e}}],
                              "else": [{"action": "lock.lock", "target": {"entity_id": e}}]}]}
    if alarm:
        scripts[f"{p.package}_toggle_alarm"] = {
            "alias": "Toggle alarm", "icon": "mdi:shield-home",
            "sequence": [{"if": [{"condition": "state", "entity_id": alarm, "state": "disarmed"}],
                          "then": [{"action": f"alarm_control_panel.alarm_arm_{p.alarm_hold_mode.replace('armed_', '')}",
                                    "target": {"entity_id": alarm}}],
                          "else": [{"action": "alarm_control_panel.alarm_disarm", "target": {"entity_id": alarm}}]}]}
    if scripts:
        pkg["script"] = scripts

    door = (p.cfg.get("cameras") or {}).get("doorbell") or {}
    if door.get("ring") and door.get("entity"):
        actions = []
        if p.screen_switch:
            actions.append({"action": "switch.turn_on", "target": {"entity_id": p.screen_switch}})
        actions.append({"action": "browser_mod.popup", "data": {
            "browser_id": [p.browser_id],
            "title": door.get("popup_title", "Someone's at the front door"),
            "initial_style": "fullscreen", "timeout": int(door.get("popup_seconds", 120)) * 1000,
            "dismissable": True,
            "content": {"type": "picture-entity", "entity": door["entity"], "camera_view": cam_view(door, "live"),
                        "show_name": False, "show_state": False},
            "right_button": "Dismiss",
            "right_button_action": {"action": "browser_mod.close_popup", "data": {"browser_id": [p.browser_id]}}}})
        if door.get("ring_is_sim"):
            actions += [{"delay": "00:00:02"},
                        {"action": "input_boolean.turn_off", "target": {"entity_id": door["ring"]}}]
        pkg["automation"] = [{
            "id": f"{p.package}_doorbell_popup", "alias": f"{p.title} · Doorbell pop-up", "mode": "restart",
            "triggers": [{"trigger": "state", "entity_id": door["ring"], "to": "on"}],
            "actions": actions}]

    head = (f"# {p.title} package: generated by ha-wall-panel from panel.yaml. Do not hand-edit.\n"
            "# SIM entities stand in for devices that aren't installed yet. Replace `sim` in panel.yaml\n"
            "# with the real entity id and re-run the generator; the SIM entity then disappears.\n\n")
    return head + dump(pkg)


def resolve_room_light(p: Panel, room_id: str) -> str:
    for f in p.floors:
        for r in f.get("rooms", []):
            if r["id"] == room_id and r.get("light"):
                return r["light"]
    sys.exit(f"scene lights_on names room '{room_id}', which has no light")


# --------------------------------------------------------------------------- main

def theme(p: Panel) -> str:
    text = (TEMPLATES / "theme.yaml").read_text()
    return text.replace("\nWall Panel Dark:\n", f"\n{p.theme}:\n", 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("panel", type=Path)
    ap.add_argument("--out", type=Path, default=Path("build"))
    args = ap.parse_args()

    cfg = yaml.safe_load(args.panel.read_text())
    p = Panel(cfg, args.panel.parent)
    out = args.out
    www = out / "www" / p.dash
    for d in (out / "dashboards", out / "packages", out / "themes", www):
        d.mkdir(parents=True, exist_ok=True)

    (out / "dashboards" / f"{p.dash}.yaml").write_text(dashboard(p))
    if p.phone:
        (out / "dashboards" / f"{p.phone['dashboard']}.yaml").write_text(phone_dashboard(p))
    (out / "packages" / f"{p.package}.yaml").write_text(package(p))
    (out / "themes" / f"{p.dash}.yaml").write_text(theme(p))
    shutil.copy(TEMPLATES / "floorplan.css", www / "floorplan.css")
    shutil.copy(TEMPLATES / "viewport.html", www / "viewport.html")
    for floor in p.floors:
        if floor.get("image"):
            src = (p.base / floor["image"]).resolve()
            shutil.copy(src, www / src.name)
            (www / f"floor-{floor['id']}.svg").write_text(floor_svg(p, floor))
        else:
            (www / f"floor-{floor['id']}.svg").write_text(placeholder_svg(p, floor))

    # Parse everything back so a bad build never reaches Home Assistant.
    for f in out.rglob("*.yaml"):
        yaml.safe_load(f.read_text())
    print(f"Generated {p.title} -> {out}/")
    print(f"  dashboard  dashboards/{p.dash}.yaml   (/{p.dash})")
    if p.phone:
        print(f"  phone      dashboards/{p.phone['dashboard']}.yaml   (/{p.phone['dashboard']})")
    print(f"  package    packages/{p.package}.yaml   ({sum(len(v) for v in p.sim.values() if isinstance(v, (dict, list)))} SIM groups)")
    print(f"  theme      themes/{p.dash}.yaml   ({p.theme})")
    print(f"  assets     www/{p.dash}/")


if __name__ == "__main__":
    main()
