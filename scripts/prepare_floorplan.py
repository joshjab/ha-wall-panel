#!/usr/bin/env python3
"""Turn a floorplan export (Floorplanner, Magicplan, a listing JPG...) into a dark-theme background.

Usage:
    python3 scripts/prepare_floorplan.py input.jpg --out floor-main.png [--crop x0 y0 x1 y1]

What it does, in order:
  1. Crops to the drawing: auto-detects the non-white bounds (pass --crop to override,
     e.g. to exclude a watermark in a corner).
  2. Mutes it for a dark UI: saturation 70%, brightness 78% (tweak with --saturation/--brightness).
  3. Knocks out the paper: flood-fills near-white from the edges to transparent, so the plan
     floats on the dashboard background. Interior light floors are untouched because the fill
     only spreads from the outside.

Prints the output size. Use it as the floor's `width`/`height` in panel.yaml; room rectangles
are measured in these pixel coordinates.

Requires: Pillow.
"""
import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageEnhance


def bounds(im, threshold=700, step=3):
    px = im.load()
    w, h = im.size
    xs = [x for x in range(w) for y in range(0, h, step) if sum(px[x, y]) < threshold]
    ys = [y for y in range(h) for x in range(0, w, step) if sum(px[x, y]) < threshold]
    if not xs:
        return 0, 0, w, h
    pad = 4
    return max(min(xs) - pad, 0), max(min(ys) - pad, 0), min(max(xs) + pad, w), min(max(ys) + pad, h)


def knock_out_paper(im, brightness):
    rgba = im.convert("RGBA")
    d = rgba.load()
    w, h = rgba.size
    limit = brightness * 235
    seen, q = set(), deque()
    q.extend((x, 0) for x in range(w))
    q.extend((x, h - 1) for x in range(w))
    q.extend((0, y) for y in range(h))
    q.extend((w - 1, y) for y in range(h))
    while q:
        x, y = q.popleft()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        r, g, b, _ = d[x, y]
        if min(r, g, b) >= limit:
            d[x, y] = (0, 0, 0, 0)
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return rgba


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--crop", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--saturation", type=float, default=0.7)
    ap.add_argument("--brightness", type=float, default=0.78)
    args = ap.parse_args()

    im = Image.open(args.input).convert("RGB")
    box = tuple(args.crop) if args.crop else bounds(im)
    im = im.crop(box)
    im = ImageEnhance.Color(im).enhance(args.saturation)
    im = ImageEnhance.Brightness(im).enhance(args.brightness)
    out = knock_out_paper(im, args.brightness)
    out.save(args.out)
    print(f"crop {box} -> {args.out} {out.width}x{out.height}  (use width: {out.width}, height: {out.height})")


if __name__ == "__main__":
    main()
