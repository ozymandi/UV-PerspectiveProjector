# End-to-end runs on real photos

`run_e2e.py` runs the whole chain in a windowed Blender:

1. Load Photo, then Calibrate (if the editor opens, set a Manual focal);
2. Project, and put a 3D object in front of the card;
3. Remap the card;
4. Render through camera A and through camera B after moving B sideways and turning it 4°.

Output for each Blender version lands in `blender_<version>/`:

- `<photo>_calibrated.png`: the viewport after Calibrate;
- `<photo>_through_a.png` / `<photo>_through_b.png`: renders through camera A and camera B;
- `<photo>_viewport_b.png`: the viewport through camera B;
- `summary.json`: the numbers.

| Photo | Calibration | Lens | Through A vs photo (median diff) | 5.2.1 | 4.2.23 |
|---|---|---|---|---|---|
| warehouse.jpg | automatic, 0.75 | 23.5 mm | 1.3% | pass | pass |
| towers_three_point.jpg | automatic, 0.73–0.75 | 28.2–28.7 mm | 1.1–1.2% | pass | pass |
| church_nave.jpg | editor (0.34), Manual focal 20 mm | 20 mm | 1.6% | pass | pass |

The difference "through B vs through A" is 0.20–0.27 in every run: camera B sees the object shift against the card (parallax), and the photo stays on the card.

```
python tests/run_blender.py -k smoke     # build + install the current code
BLENDER_USER_RESOURCES=build/blender_user blender --python tests/e2e/run_e2e.py
```
