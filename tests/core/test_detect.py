import os
import time

import numpy as np
import pytest

from perspective_projector.core import lines, solve, vp_detect
from render import render_scene
from synth import SynthCamera

SCENES = [
    dict(),
    dict(yaw_deg=-25, pitch_deg=-18, roll_deg=2, focal_px=2400),
    dict(yaw_deg=-50, pitch_deg=-8, focal_px=3600, width=3000, height=4000),
    dict(yaw_deg=-40, pitch_deg=-30, focal_px=1500, width=1920, height=1080, location=(-4.0, -1.0, 3.0)),
]


# Detection must finish within 10 s on a developer machine. Shared CI runners (and busy
# machines) are slower, so the limit is scaled by PP_TIME_FACTOR (CI sets 3).
TIME_LIMIT_S = 10.0 * float(os.environ.get("PP_TIME_FACTOR", "1"))


def _true_vps(cam):
    return [cam.vp(i) for i in range(3)]


def test_segments_lie_on_scene_edges():
    cam = SynthCamera()
    img = render_scene(cam)
    seg = lines.detect_segments(img)
    assert len(seg) > 50
    diag = np.hypot(cam.width, cam.height)
    vps = [solve.normalize_vp(v, diag) for v in _true_vps(cam)]
    res = np.min(np.stack([vp_detect._image_residual_deg(seg, v) for v in vps], axis=1), axis=1)
    lengths = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1])
    # at least 90% of the detected length points at one of the true VPs within 1 degree
    assert lengths[res < 1.0].sum() / lengths.sum() > 0.9
    # coordinates are full resolution even though detection ran downscaled
    assert seg[:, [0, 2]].max() > 0.6 * cam.width


@pytest.mark.parametrize("params", SCENES)
def test_detect_recovers_camera(params):
    cam = SynthCamera(**params)
    img = render_scene(cam, seed=1)
    seg = lines.detect_segments(img)
    t = time.perf_counter()
    det = vp_detect.detect(seg, cam.width, cam.height)
    elapsed = time.perf_counter() - t
    assert det is not None
    assert det.focal_px == pytest.approx(cam.f, rel=0.03)
    sol = det.solution()
    # each solved axis is parallel to the true axis of the same name
    for i in range(3):
        assert abs(np.dot(sol.rotation[:, i], cam.M[:, i])) > np.cos(np.radians(1.0)), solve.AXES[i]
    assert det.confidence > 0.5
    assert elapsed < TIME_LIMIT_S, f"detection took {elapsed:.1f} s (limit {TIME_LIMIT_S:.0f} s)"


def test_noise_image_is_not_confident():
    rng = np.random.default_rng(3)
    img = (rng.random((1200, 1600)) * 255).astype(np.uint8)
    import cv2
    img = cv2.GaussianBlur(img, (0, 0), 6)
    seg = lines.detect_segments(img)
    det = vp_detect.detect(seg, 1600, 1200)
    assert det is None or det.confidence < 0.3
