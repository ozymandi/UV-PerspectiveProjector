"""Focal length and scale from two ground segments of known length (one-point photos)."""

import numpy as np
import pytest

from perspective_projector.core import solve
from synth import SynthCamera

W, H = 2880, 3840  # portrait, like the field-test photo


def setup(focal_px=2000.0, yaw=-1.5, pitch=0.0, pp=None, cam_h=1.2):
    cam = SynthCamera(width=W, height=H, focal_px=focal_px, yaw_deg=yaw, pitch_deg=pitch,
                      location=(0.0, -3.0, cam_h), pp=pp)
    # axes: Y is depth here (camera looks along +Y), X is across, Z up
    pairs = [[cam.segment((-0.6, 0.0, 0.0), (0, 1, 0), 3.0), cam.segment((0.6, 0.0, 0.0), (0, 1, 0), 3.0)],
             [cam.segment((-0.6, 4.0, 0.0), (0, 0, 1), 2.0), cam.segment((0.6, 4.0, 0.0), (0, 0, 1), 2.0)]]
    axes = ("Y", "Z")
    pp_s, _ = solve.principal_point_for(pairs, axes, W, H)
    depth = (tuple(cam.project((0.2, 0.5, 0.0))), tuple(cam.project((0.2, 1.7, 0.0))))   # 1.2 m along Y
    across = (tuple(cam.project((-0.4, 0.5, 0.0))), tuple(cam.project((0.2, 0.5, 0.0))))  # 0.6 m along X
    return cam, pairs, axes, pp_s, depth, across


@pytest.mark.parametrize("focal_px,pitch,pp", [
    (2000.0, 0.0, None),
    (1500.0, 0.0, (W / 2.0, H * 0.42)),   # shifted render
    (3200.0, 0.0, None),
])
def test_one_point_focal_and_scale(focal_px, pitch, pp):
    cam, pairs, axes, pp_s, depth, across = setup(focal_px=focal_px, pitch=pitch, pp=pp)
    sol, height = solve.focal_from_known_size(pairs, axes, W, H, pp_s, depth, across, 1.2, 0.6)
    assert sol.focal_px == pytest.approx(focal_px, rel=0.03)
    assert height == pytest.approx(1.2, rel=0.03)
    assert sol.focal_source == "known size"
    # both segments measure their real lengths at the solved height
    assert np.linalg.norm(solve.ground_length(sol, *depth, height)) == pytest.approx(1.2, rel=0.01)
    assert np.linalg.norm(solve.ground_length(sol, *across, height)) == pytest.approx(0.6, rel=0.01)


def test_order_of_segments_does_not_matter():
    cam, pairs, axes, pp_s, depth, across = setup()
    sol, height = solve.focal_from_known_size(pairs, axes, W, H, pp_s, across, depth, 0.6, 1.2)
    assert sol.focal_px == pytest.approx(2000.0, rel=0.03)
    assert height == pytest.approx(1.2, rel=0.03)


def test_segment_above_horizon_is_rejected():
    cam, pairs, axes, pp_s, depth, across = setup()
    sky = ((W * 0.4, H * 0.1), (W * 0.6, H * 0.1))
    with pytest.raises(solve.CalibrationError, match="above the horizon"):
        solve.focal_from_known_size(pairs, axes, W, H, pp_s, sky, across, 1.0, 0.6)


def test_segments_along_the_same_axis_are_rejected():
    cam, pairs, axes, pp_s, depth, across = setup()
    other_depth = (tuple(cam.project((-0.3, 0.5, 0.0))), tuple(cam.project((-0.3, 1.5, 0.0))))
    with pytest.raises(solve.CalibrationError, match="same direction"):
        solve.focal_from_known_size(pairs, axes, W, H, pp_s, depth, other_depth, 1.2, 1.0)


def test_impossible_ratio_is_rejected():
    cam, pairs, axes, pp_s, depth, across = setup()
    with pytest.raises(solve.CalibrationError, match="do not match"):
        solve.focal_from_known_size(pairs, axes, W, H, pp_s, depth, across, 500.0, 0.01)
