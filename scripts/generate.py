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
        x, y, rw, rh = room["rect"]
        compact = rw < 70 or rh < 50
        lx = x + (4 if compact else 8)
        ly = y + (13 if compact else 15)
        tag_w, tag_h = (38, 11) if compact else (46, 13)
        ty = y + 22
        label_cls = "label small" if compact else "label"
        out += [
            f'    <g id="room.{room["id"]}" class="{room_base_class(room)}">',
            f'      <rect class="shade" x="{x}" y="{y}" width="{rw}" height="{rh}" rx="3"/>',
            f'      <rect class="outline" x="{x + 1.5}" y="{y + 1.5}" width="{rw - 3}" height="{rh - 3}" rx="4"/>',
            f'      <text class="{label_cls}" x="{lx}" y="{ly}">{room["name"].upper()}</text>',
            f'      <g class="tag"><rect x="{lx}" y="{ty}" width="{tag_w}" height="{tag_h}" rx="3"/>'
            f'<text x="{lx + tag_w / 2}" y="{ty + tag_h - 3}" text-anchor="middle">MOTION</text></g>',
            "    </g>"]
    out.append("  </g>")
    for room in floor.get("rooms", []):
        if room.get("temperature"):
            x, y, rw, rh = room["rect"]
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
        out += [
            f'  <g id="lock.{lock["id"]}" class="lock">',
            f'    <circle cx="{cx}" cy="{cy}" r="18"/>',
            f'    <path d="M{cx - 7.5} {cy - 1}v-4a7.5 7.5 0 0 1 15 0v4" fill="none" stroke-width="2.6" stroke-linecap="round"/>',
            f'    <rect x="{cx - 11}" y="{cy - 1}" width="22" height="13" rx="2.5"/>',
            "  </g>"]
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


def room_base_class(room: dict) -> str:
    x, y, rw, rh = room["rect"]
    return "room compact" if (rw < 70 or rh < 50) else "room"


# --------------------------------------------------------------------------- floorplan rules

def floor_rules(p: Panel, floor: dict) -> list:
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
                          "tap_action": "more-info"})

    for nav in floor.get("stairs", []) or []:
        target = next(f for f in p.floors if f["id"] == nav["to"])
        rules.append({"element": f"nav.{nav['to']}",
                      "tap_action": {"action": "navigate", "navigation_path": f"/{p.dash}/{p.floor_path(target)}"}})
    return rules


def floorplan_card(p: Panel, floor: dict, version: str, **extra) -> dict:
    image = "floor-" + floor["id"] + ".svg"
    rules = floor_rules(p, floor)
    if not floor.get("image"):  # placeholder floor: only its nav element
        back = next((n for n in floor.get("stairs", []) or []), {"to": p.main["id"]})
        target = next(f for f in p.floors if f["id"] == back["to"])
        rules = [{"element": f"nav.{target['id']}",
                  "tap_action": {"action": "navigate", "navigation_path": f"/{p.dash}/{p.floor_path(target)}"}}]
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
            styles={"card": [{"height": "64px"}, {"padding": "0 4px"}, {"background": "transparent"}, {"box-shadow": "none"}],
                    "grid": [{"grid-template-areas": '"i n" "i l"'}, {"grid-template-columns": "34px 1fr"}, {"column-gap": "10px"}],
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


def doorbell_card(p: Panel) -> dict:
    door = (p.cfg.get("cameras") or {}).get("doorbell")
    if not door or not door.get("entity"):
        return {"type": "markdown",
                "content": "### Front door\nDoorbell not installed yet.\n\nThe live view appears here once it's set up, "
                           "and pops up full screen when someone rings.\n"}
    return {"type": "picture-entity", "entity": door["entity"], "name": door.get("name", "Front door"),
            "camera_view": "auto", "aspect_ratio": "16:9", "show_state": False}


def locks_column(p: Panel) -> dict:
    tiles = []
    for f in p.floors:
        for lock in f.get("locks", []):
            tiles.append(btn(template="wp_lock", entity=lock["entity"], name=lock["name"]))
    for g in p.garages():
        amber = [{"background": "#2a2114"}, {"border": "1px solid #6b4a1c"}]
        tiles.append(btn(
            template="wp_tile", entity=g["entity"], name=g.get("name", "Garage"),
            icon="[[[ return entity.state === 'open' ? 'mdi:garage-open' : 'mdi:garage' ]]]",
            state_display="[[[ return entity.state === 'open' ? 'Tap to close' : 'Closed' ]]]",
            tap_action={"action": "perform-action", "perform_action": "cover.toggle",
                        "target": {"entity_id": g["entity"]},
                        "confirmation": {"text": "[[[ return entity.state === 'open' ? 'Close the garage door?' : 'Open the garage door?' ]]]"}},
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

    def mode(name, service, active_state, confirm=None, dim_when=None):
        c = btn(template="wp_action", entity=alarm, name=name,
                tap_action={"action": "perform-action", "perform_action": f"alarm_control_panel.{service}",
                            "target": {"entity_id": alarm}})
        if confirm:
            c["tap_action"]["confirmation"] = {"text": confirm}
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
                       "off": mode("Disarm", "alarm_disarm", None, confirm="Disarm the alarm?", dim_when="disarmed")}),
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
        script = s.get("script") or f"script.{p.package}_{slug(s['name'])}"
        scenes.append(btn(template="wp_scene", name=s["name"], icon=s.get("icon", "mdi:play"),
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
    cards = [grid(cols="160px 1fr 200px", cards=bar, area="bar")]
    for i, c in enumerate(items):
        cards.append(at({"type": "picture-entity", "entity": c["entity"], "name": c.get("name", ""),
                         "camera_view": "auto", "show_state": False}, f"c{i}"))
    return {"title": "Cameras", "path": "cameras", "type": "panel", "theme": p.theme, "cards": [grid(
        pad=PAD, cols="1fr 1fr", rows="56px " + " ".join(["1fr"] * rows), areas=areas, cards=cards)]}


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
        locks.append({"name": f"SIM {name}", "unique_id": f"{p.package}_sim_{lid}_lock",
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
            "name": f"{p.package} garage open long", "unique_id": f"{p.package}_alert_garage_open_long",
            "state": (f"{{{{ is_state('{g}', 'open')\n   and (now() - states.{domain}.{obj}.last_changed)"
                      f".total_seconds() > {minutes * 60} }}}}\n")}]
    if template:
        pkg["template"] = [template]

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
        scripts[f"{p.package}_{slug(s['name'])}"] = {"alias": s["name"], "icon": s.get("icon", "mdi:play"), "sequence": seq}
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
            "content": {"type": "picture-entity", "entity": door["entity"], "camera_view": "auto",
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
    print(f"  package    packages/{p.package}.yaml   ({sum(len(v) for v in p.sim.values() if isinstance(v, (dict, list)))} SIM groups)")
    print(f"  theme      themes/{p.dash}.yaml   ({p.theme})")
    print(f"  assets     www/{p.dash}/")


if __name__ == "__main__":
    main()
