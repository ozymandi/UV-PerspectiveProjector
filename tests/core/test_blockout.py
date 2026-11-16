import numpy as np
import pytest

from perspective_projector.core import blockout as B
from synth import SynthCamera

W, H = 4000, 3000


def ray(cam, px):
    """World ray through pixel ``px`` of a synthetic camera."""
    x = px[0] - cam.pp[0]
    y = -(px[1] - cam.pp[1])
    d = cam.c2w @ np.array([x, y, -cam.f])
    return cam.location, d / np.linalg.norm(d)


@pytest.fixture
def cam():
    return SynthCamera(width=W, height=H, yaw_deg=-30, pitch_deg=-12, focal_px=2800, location=(0, -8, 1.6))


def test_ground_hit_reprojects(cam):
    p = np.array([1.5, 3.0, 0.0])
    o, d = ray(cam, cam.project(p))
    hit = B.ray_plane(o, d, (0, 0, 0), (0, 0, 1))
    assert hit == pytest.approx(p, abs=1e-6)
    assert np.abs(cam.project(hit) - cam.project(p)).max() < 0.1


def test_ground_hit_limits(cam):
    o, d = ray(cam, (W / 2, 10))  # above the horizon: the ground is behind
    assert B.ray_plane(o, d, (0, 0, 0), (0, 0, 1)) is None
    o, d = ray(cam, cam.project((0, 400, 0)))
    assert B.ray_plane(o, d, (0, 0, 0), (0, 0, 1), max_distance=100) is None
    assert B.ray_plane(o, d, (0, 0, 0), (0, 0, 1), max_distance=1000) is not None


def test_height_from_click(cam):
    base = np.array([1.0, 2.0, 0.0])
    top = np.array([1.0, 2.0, 0.75])
    o, d = ray(cam, cam.project(top))
    got = B.closest_on_line(o, d, base, (0, 0, 1))
    assert got == pytest.approx(top, abs=1e-6)


def test_depth_from_click_on_a_vertical_base(cam):
    # a facade at y = 5 facing the camera (-Y); a balcony front 1.2 m out of it
    back = np.array([0.5, 5.0, 2.0])
    front = back + np.array([0.0, -1.2, 0.0])
    o, d = ray(cam, cam.project(front))
    got = B.closest_on_line(o, d, back, (0, -1, 0))
    assert got == pytest.approx(front, abs=1e-6)
    assert np.abs(cam.project(got) - cam.project(front)).max() < 0.1


@pytest.mark.parametrize("deg,snaps", [(4.0, True), (6.0, False)])
def test_axis_snapping(deg, snaps):
    a = np.radians(deg)
    d = B.snap_horizontal((np.cos(a), np.sin(a), 0.3))
    if snaps:
        assert d == pytest.approx([1, 0, 0])
    else:
        assert d == pytest.approx([np.cos(a), np.sin(a), 0], abs=1e-9)


def test_wall_keeps_first_point_and_snaps():
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([4.0, 0.2, 0.0])  # under 3 degrees off X
    corners = B.wall_corners(a, b, (4.0, 0.2, 2.5))
    assert corners[0] == pytest.approx(a)
    assert corners[1] == pytest.approx([4.0, 0.0, 0.0], abs=1e-3)
    assert corners[2][2] == pytest.approx(2.5)
    oblique = B.wall_corners(a, (3.0, 1.7320508, 0.0), (3.0, 1.73, 2.0))  # 30 degrees
    assert oblique[1] == pytest.approx([3.0, 1.7320508, 0.0], abs=1e-6)


def test_rect_on_floor_and_on_a_facade():
    r = B.rect_from_corners((0, 0, 0.5), (2, 1, 0.5), (0, 0, 1))
    assert [list(p) for p in r] == [[0, 0, 0.5], [2, 0, 0.5], [2, 1, 0.5], [0, 1, 0.5]]
    f = B.rect_from_corners((0, 5, 1), (2, 5, 3), (0, -1, 0))  # facade along X
    assert all(p[1] == pytest.approx(5.0) for p in f)
    assert sorted({round(p[2], 6) for p in f}) == [1.0, 3.0]
    with pytest.raises(B.BlockoutError):
        B.rect_from_corners((0, 0, 0), (2, 0, 0), (0, 0, 1))


def test_box_and_reference_corner(cam):
    rect = B.rect_from_corners((0, 0, 0), (1, 1, 0), (0, 0, 1))
    corners = B.box_corners(rect, (0, 0, 0.5))
    assert len(corners) == 8 and corners[4][2] == pytest.approx(0.5)
    o, d = ray(cam, (W * 0.6, H * 0.3))
    c10 = B.reference_corner(o, d, 10.0)
    c20 = B.reference_corner(o, d, 20.0)
    assert (c20 - o) == pytest.approx(2 * (c10 - o))
    p, n = B.reference_plane(c10, "X")
    assert n == pytest.approx([0, 1, 0]) and p == pytest.approx(c10)


def test_ceiling_extent():
    assert B.ceiling_extent([(0, 0, 0), (3, 1, 2), (1, 4, 0)]) == (0.0, 0.0, 3.0, 4.0)
    with pytest.raises(B.BlockoutError):
        B.ceiling_extent([])
