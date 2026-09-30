# Getting a floorplan

The floorplan is the heart of the main page, so it's worth getting right. Either way you end
up with the same thing per floor: a PNG, its `width`/`height`, and room rectangles in that
PNG's pixel coordinates.

## Path A: they have an image

Anything with walls works: a Floorplanner or Magicplan export, a listing brochure page, a
builder drawing, a phone photo of a clean sketch.

```bash
python3 scripts/prepare_floorplan.py their-plan.jpg --out floor-main.png
# crop (227, 0, 740, 540) -> floor-main.png 513x540  (use width: 513, height: 540)
```

- **Watermarks and logos**: if the auto-crop includes a corner badge (free Floorplanner exports
  carry one), pass `--crop x0 y0 x1 y1` to exclude it. Look at the output before continuing.
- **Low resolution** (under ~800px on the long side) looks soft on a tablet. It still works.
  Mention that a higher-resolution export would help, and move on.
- **Measure the rooms.** View the processed image and read off each room's rectangle
  `[x, y, w, h]` in its pixels. Keep rooms to their floor area. The overlay is a tap target and
  a tint, not an architectural drawing, so rectangles are fine even for L-shaped rooms: use the
  largest rectangle, or split the room into two entries that share a light.
- **Exterior doors**: pick a point on or just inside each door for its lock `badge`.
- **Garage**: the door edge as a thin `bar: [x, y, w, 8]` along the garage's outside wall.
- **Stairs**: a point on the stairs for the floor-switch pill (`stairs: [{to: upstairs, at: [x, y]}]`).
  The pill is 92×40 units, so put it somewhere it won't cover a room label.

Then **check the overlay against the image** by generating and viewing the result at 1280×800.
Misplaced rectangles are obvious at a glance. The owner confirms room names and positions in
the mockup review.

## Path B: they can make one quickly

Floorplanner's free tier is enough: draw the outer walls, split rooms, add doors, then export a
2D image. Allow ~15 minutes. Then follow Path A.

## Path C: no floorplan? Sketch it together

This is a conversation. Nobody has room dimensions to hand, but everyone can walk their house in
their head. Your job is to turn that walk into a grid of rectangles, show it, and adjust it
until the owner recognises their home.

**How to run it:**

1. **Pick a canvas.** Use about 520×540 units per floor (the width/height in panel.yaml). Up is
   the back of the house, the front door is at the bottom.
2. **Start at the front door.** "You walk in the front door. What's straight ahead? Left? Right?"
   Place each room as you hear about it.
3. **Get relative sizes, not measurements.** "Is the living room bigger or smaller than the
   kitchen? About twice as big?" Anchor on one big room and size the others against it.
4. **Draw after every few rooms.**
   ```bash
   python3 scripts/sketch_floorplan.py panel.yaml --floor main --out sketch-main.png --labels
   ```
   Show the image. Ask what's wrong: "The garage is further left", "the laundry is tiny". Nudge
   the numbers and redraw. Three or four rounds is normal.
5. **Add doorways** where rooms connect, as `doors: [[x, y, length, h|v], ...]` on the floor.
   They're drawn as gaps in the walls, which makes it read as a floorplan rather than a grid.
6. **Set `kind:`** on hallways, garages, baths and laundry if their ids don't say so. It picks
   the floor colour.
7. **Finish without `--labels`.** The dashboard draws its own labels. Point the floor's `image:`
   at the final PNG.

**Tips that save rounds:**

- Rooms that share a wall should share an edge exactly, e.g. kitchen `x + w` = dining `x`.
- A hallway is just a long thin room. Give it a light and motion like any other.
- Leave a margin (~8–20 units) around the outside walls so outlines aren't clipped.
- A satellite or aerial view (e.g. USGS NAIP imagery in the US, public domain) can confirm the
  overall footprint shape: L-shaped, garage on the left, and so on. It won't show interior walls,
  so treat it as a hint, not the plan.

## More than one floor

Each floor is its own entry under `floors:` with its own image and rooms. The first floor is the
main page; the others become their own views, reached by the stairs pill. A floor with no image
yet renders as a tidy placeholder with a way back. Add its plan later and regenerate.
