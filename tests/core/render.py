"""Render simple synthetic scenes (axis-aligned boxes and tiles) for detection tests."""

import cv2
import numpy as np


def _quad(cam, pts):
    pc = [cam.M @ (np.asarray(p, float) - cam.location) for p in pts]
    if any(p[2] > -0.05 for p in pc):
        return None
    return np.array([cam.project(p) for p in pts], dtype=np.float64)


def render_scene(cam, seed=0):
    """Gray uint8 image of a floor checkerboard, a back wall with windows and a few boxes."""
    rng = np.random.default_rng(seed)
    img = np.full((cam.height, cam.width), 128, np.uint8)
    polys = []
    # floor tiles on z = 0
    for i in range(-6, 8):
        for j in range(0, 14):
            if (i + j) % 2:
                polys.append(([(i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0)], 90))
    # back wall y = 14 with windows
    polys.append(([(-6, 14, 0), (8, 14, 0), (8, 14, 4), (-6, 14, 4)], 170))
    for k in range(-5, 7, 2):
        polys.append(([(k, 14, 1), (k + 1, 14, 1), (k + 1, 14, 3), (k, 14, 3)], 40))
    # side wall x = 8 with panels
    polys.append(([(8, 0, 0), (8, 14, 0), (8, 14, 4), (8, 0, 4)], 200))
    for k in range(1, 13, 3):
        polys.append(([(8, k, 0.5), (8, k + 1.5, 0.5), (8, k + 1.5, 3), (8, k, 3)], 60))
    # boxes
    for _ in range(3):
        x0, y0 = rng.uniform(-3, 4), rng.uniform(4, 10)
        sx, sy, sz = rng.uniform(0.6, 1.5, 3)
        x1, y1 = x0 + sx, y0 + sy
        polys += [
            ([(x0, y0, sz), (x1, y0, sz), (x1, y1, sz), (x0, y1, sz)], 230),
            ([(x0, y0, 0), (x1, y0, 0), (x1, y0, sz), (x0, y0, sz)], 150),
            ([(x0, y0, 0), (x0, y1, 0), (x0, y1, sz), (x0, y0, sz)], 110),
        ]
    for pts, shade in polys:
        q = _quad(cam, pts)
        if q is None:
            continue
        cv2.fillPoly(img, [np.round(q * 16).astype(np.int32)], int(shade), lineType=cv2.LINE_AA, shift=4)
    noise = rng.normal(0, 3, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)
