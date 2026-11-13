"""Run vanishing-point detection on the real test photos and draw overlays for a visual check.

    python tests/data/evaluate.py

Writes tests/data/overlays/<name>.jpg (inlier segments coloured by axis: X red, Y green, Z blue,
plus thin guide lines towards each vanishing point) and tests/data/overlays/sheet.jpg, and prints
a results table (confidence, focal, axes used).
"""

import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from perspective_projector.core import lines, solve, vp_detect  # noqa: E402

COLORS = {0: (60, 60, 240), 1: (80, 210, 80), 2: (240, 140, 60)}  # BGR for X, Y, Z


def guide_lines(img, vp, color, n=9):
    h, w = img.shape[:2]
    if vp[2] != 0:
        target = vp[:2] / vp[2]
        for k in range(n):
            # fan of rays from points along the image border towards the VP
            t = (k + 0.5) / n
            for start in ((t * w, 0), (t * w, h), (0, t * h), (w, t * h)):
                d = target - np.array(start)
                if np.linalg.norm(d) < 1:
                    continue
                end = np.array(start) + d / np.linalg.norm(d) * 3 * max(w, h)
                cv2.line(img, tuple(int(v) for v in start), tuple(int(v) for v in end), color, 1, cv2.LINE_AA)
    else:
        d = vp[:2] / (np.linalg.norm(vp[:2]) + 1e-12)
        nrm = np.array([-d[1], d[0]])
        for k in range(-n, n + 1):
            c = np.array([w / 2, h / 2]) + nrm * k * max(w, h) / (2 * n)
            p0, p1 = c - d * 2 * max(w, h), c + d * 2 * max(w, h)
            cv2.line(img, tuple(int(v) for v in p0), tuple(int(v) for v in p1), color, 1, cv2.LINE_AA)


def main():
    media = os.path.join(HERE, "media")
    out_dir = os.path.join(HERE, "overlays")
    os.makedirs(out_dir, exist_ok=True)
    rows, tiles = [], []
    for name in sorted(os.listdir(media)):
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        img = cv2.imread(os.path.join(media, name))
        h, w = img.shape[:2]
        # same grey conversion as the add-on applies to Blender image pixels
        gray = lines.to_gray_u8(img[..., ::-1].astype(np.float32) / 255.0, w, h, bottom_up=False)
        seg = lines.detect_segments(gray)
        det = vp_detect.detect(seg, w, h)
        over = (img * 0.55).astype(np.uint8)
        row = dict(photo=name, segments=int(len(seg)), confidence=0.0, focal_35mm=None, axes=None, support=None)
        if det is not None:
            row["confidence"] = round(det.confidence, 3)
            row["support"] = [round(s, 3) for s in det.support]
            row["axes"] = "".join(det.axis_pair()[0])
            if det.focal_px:
                row["focal_35mm"] = round(det.focal_px * 43.2666 / np.hypot(w, h), 1)
            guide = over.copy()
            for k in range(3):
                if len(det.inliers[k]) >= vp_detect.MIN_SEGMENTS_PER_VP:
                    guide_lines(guide, det.vps[k], COLORS[k])
            over = cv2.addWeighted(guide, 0.35, over, 0.65, 0)
            for k in range(3):
                for i in det.inliers[k]:
                    x0, y0, x1, y1 = seg[i]
                    cv2.line(over, (int(x0), int(y0)), (int(x1), int(y1)), COLORS[k], 2, cv2.LINE_AA)
        label = f"{name}  conf {row['confidence']:.2f}  f35 {row['focal_35mm']}"
        cv2.putText(over, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(os.path.join(out_dir, os.path.splitext(name)[0] + ".jpg"), over)
        tiles.append(cv2.resize(over, (640, int(640 * h / w)))[:427])
        rows.append(row)
    pad = [np.zeros_like(tiles[0])] * ((-len(tiles)) % 2)
    tiles += pad
    tiles = [cv2.copyMakeBorder(t, 0, 427 - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
    sheet = np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)])
    cv2.imwrite(os.path.join(out_dir, "sheet.jpg"), sheet)
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    for r in rows:
        print(f"{r['photo']:26s} seg {r['segments']:4d}  conf {r['confidence']:.3f}  f35 {r['focal_35mm']}  "
              f"axes {r['axes']}  support {r['support']}")


if __name__ == "__main__":
    main()
