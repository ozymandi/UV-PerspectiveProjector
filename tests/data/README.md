# Real test photos

Ten stock photos (Pixabay Content License, free use, no attribution required) fetched with the
`adobe-operator` media tools (`md_do stock.fetch`) into `media/`. `sources.json` records each file's
Pixabay id, page, author, licence and the licence verdict. Pixabay's API serves 1280 px versions without EXIF.
The photos and the overlays drawn on them are not committed: Pixabay's licence does not allow redistributing the files. Fetch them again by their ids in `sources.json`.

| Photo | Scene | Result | Confidence | Focal (35 mm eq.) |
|---|---|---|---|---|
| warehouse.jpg | aisle between racks | automatic | 0.75 | 23.5 mm |
| towers_three_point.jpg | glass towers from below, three-point | automatic | 0.75 | 28.9 mm |
| church_nave.jpg | nave, one-point | editor: focal not observable | 0.45 | none |
| corridor_one_point.jpg | dark corridor, one-point | editor: focal not observable | 0.37 | none |
| kitchen.jpg | long kitchen, cropped | borderline (0.34–0.75 across runs) | 0.36 | 20.8 mm |
| street_one_point.jpg | cobbled street, one-point | editor | 0.12 | none |
| cafe.jpg | brick wall, frontal | editor | 0.11 | none |
| office.jpg | conference room, frontal | editor | 0.10 | none |
| forest_organic.jpg | foggy forest, only vertical trunks | editor | 0.09 | none |
| street_corner.jpg | corner building, wide lens | editor | 0.08 | none |

Confidence threshold: **0.5** (`CONFIDENCE_THRESHOLD` in `perspective_projector/blender/calibration.py`).

- **Automatic:** photos with two or three clear directions and an observable focal length.
- **Editor, with the auto lines already placed:**
  - one-point views, whose focal length cannot be recovered without EXIF;
  - frontal shots;
  - the organic scene.
- **Not asserted:** the kitchen. It is a cropped photo whose pairwise focal estimates disagree, so it lands on either side of the threshold between runs.
- `tests/core/test_real_photos.py` locks this split. The test uses the same grey conversion as the add-on in Blender.

Detection takes 1.3–3.2 s per photo: three search runs, keeping the one that explains the most edges.

## Focal accuracy against EXIF

There is no EXIF in the Pixabay files, so focal accuracy was checked separately. Five CC0 originals from
Wikimedia Commons with an EXIF focal were downscaled to 1600 px and kept outside the repository:

| Photo | EXIF (35 mm eq.) | Detected | Error | Confidence |
|---|---|---|---|---|
| IBM building corner | 26 mm | 26.6 mm | +2% | 0.76 automatic |
| Corner building, Dresden | 33 mm | 34.5 mm | +4% | 0.61 automatic |
| Kitchen, Fujifilm X100T (23 mm on APS-C) | 35 mm | 39.8 mm | +14% | 0.84 automatic |
| Kitchen café, phone ultra-wide | 12 mm | 25.2 mm | +110% | 0.38 editor |
| Street facade, frontal | 75 mm | none | none | 0.24 editor |

Where the detector is confident, the focal is within 2–14%. The ultra-wide phone photo is far off, but it falls below the threshold and goes to the editor. The X100T photo also showed that EXIF FocalLength + FocalPlaneXResolution can be wrong: it gave 13.9 mm. The add-on therefore reads only FocalLengthIn35mmFilm.

## Re-run

```
python tests/data/evaluate.py      # prints the table, writes overlays/<photo>.jpg and overlays/sheet.jpg
```

The overlays show inlier segments per axis (X red, Y green, Z blue) and guide lines towards each
vanishing point.
