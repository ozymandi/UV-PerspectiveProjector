import pytest

from perspective_projector.core import clip

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_area_square():
    assert clip.area(SQUARE) == pytest.approx(100.0)
    assert clip.area(list(reversed(SQUARE))) == pytest.approx(100.0)


def test_clip_rect_inside_unchanged():
    assert clip.area(clip.clip_rect(SQUARE, -5, -5, 20, 20)) == pytest.approx(100.0)


def test_clip_rect_partial():
    assert clip.area(clip.clip_rect(SQUARE, 5, 2, 20, 6)) == pytest.approx(5 * 4)


def test_clip_rect_huge_polygon_covers_rect():
    huge = [(-1e6, -1e6), (1e6, -1e6), (1e6, 1e6), (-1e6, 1e6)]
    assert clip.area(clip.clip_rect(huge, 0, 0, 4000, 3000)) == pytest.approx(4000 * 3000)


def test_clip_rect_outside_empty():
    assert clip.clip_rect(SQUARE, 20, 20, 30, 30) == []


def test_clip_near_keeps_front_part():
    # quad on the floor (y = -1) from 2 m behind the camera to 8 m in front (camera looks down -Z)
    quad = [(-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, -1.0, -8.0), (-1.0, -1.0, -8.0)]
    front = clip.clip_near(quad, 0.1)
    assert len(front) == 4
    assert all(p[2] <= -0.1 + 1e-9 for p in front)
    zs = sorted({round(p[2], 6) for p in front})
    assert zs == [-8.0, -0.1]


def test_clip_near_all_behind():
    quad = [(-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, -1.0, 1.0), (-1.0, -1.0, 1.0)]
    assert clip.clip_near(quad, 0.1) == []
