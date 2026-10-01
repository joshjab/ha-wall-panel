#!/usr/bin/env python3
"""Draw a clean schematic floorplan PNG from room rectangles — for when there's no floorplan image.

Usage:
    python3 scripts/sketch_floorplan.py panel.yaml --floor main --out sketch-main.png [--scale 2]

Reads the floor's `width`, `height` and each room's `rect: [x, y, w, h]` from panel.yaml and draws
walls, floors and doorway gaps in the same muted palette as a processed Floorplanner export, so the
generated overlay (shades, motion outlines, badges) looks identical either way. Point the floor's
`image:` at the output and re-run generate.py.

The rectangles come from talking the layout through with the owner (see
references/floorplan.md, "No floorplan? Sketch it together"). Iterate: draw, show, adjust.

Requires: PyYAML, Pillow.
"""
import argparse
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

FLOOR_FILL = {  # muted fills by room kind; anything else gets "room"
    "room": (74, 66, 58), "kitchen": (84, 86, 88), "bath": (88, 90, 96), "laundry": (84, 86, 88),
    "garage": (96, 98, 100), "hall": (70, 62, 54), "outside": (40, 44, 40),
}
WALL = (22, 24, 27)
WALL_W = 4


def kind_of(room):
    if room.get("kind"):
        return room["kind"]
    rid = room["id"]
    for k in FLOOR_FILL:
        if k in rid:
            return k
    return "room"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("panel", type=Path)
    ap.add_argument("--floor", default=None, help="floor id (default: the first floor)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--scale", type=int, default=2, help="render at N× (the SVG scales it back down, so it stays crisp)")
    ap.add_argument("--labels", action="store_true", help="burn room names in (useful while iterating)")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.panel.read_text())
    floors = cfg["floors"]
    floor = next(f for f in floors if f["id"] == args.floor) if args.floor else floors[0]
    s = args.scale
    w, h = floor["width"], floor["height"]
    img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def outline(room):  # rect or poly, as scaled points
        if room.get("poly"):
            return [(px * s, py * s) for px, py in room["poly"]]
        x, y, rw, rh = room["rect"]
        return [(x * s, y * s), ((x + rw) * s, y * s), ((x + rw) * s, (y + rh) * s), (x * s, (y + rh) * s)]

    for room in floor["rooms"]:
        d.polygon(outline(room), fill=FLOOR_FILL[kind_of(room)] + (255,))
    for room in floor["rooms"]:
        d.polygon(outline(room), outline=WALL + (255,), width=WALL_W * s)
    # Doorway gaps: `doors: [[x, y, length, "h"|"v"], ...]` on the floor, drawn in floor colour.
    for dx, dy, length, orient in floor.get("doors", []) or []:
        box = [dx * s, (dy - 3) * s, (dx + length) * s, (dy + 3) * s] if orient == "h" else \
              [(dx - 3) * s, dy * s, (dx + 3) * s, (dy + length) * s]
        d.rectangle(box, fill=FLOOR_FILL["hall"] + (255,))
    if args.labels:
        font = ImageFont.load_default()
        for room in floor["rooms"]:
            pts = outline(room)
            cx, cy = sum(px for px, _ in pts) / len(pts), sum(py for _, py in pts) / len(pts)
            d.text((cx, cy), room.get("label", room["name"]), fill=(200, 200, 200, 255), font=font, anchor="mm")

    # Saved at --scale x; the SVG draws it into the floor's width x height box, so it stays crisp.
    img.save(args.out)
    print(f"wrote {args.out} ({img.width}x{img.height}) for floor '{floor['id']}'")


if __name__ == "__main__":
    main()
