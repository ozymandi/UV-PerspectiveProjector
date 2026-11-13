"""Regression on the real stock photos in tests/data/media (see tests/data/README.md).

Locks the behaviour the confidence threshold was tuned on: architectural photos with two or three
clear directions calibrate automatically; organic scenes and one-point photos without a focal length
fall back to the manual editor.
"""

import os

import cv2
import pytest

from perspective_projector.core import lines, vp_detect

MEDIA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "media")
THRESHOLD = 0.5  # perspective_projector.blender.calibration.CONFIDENCE_THRESHOLD

AUTOMATIC = ["towers_three_point.jpg", "warehouse.jpg"]
EDITOR = ["forest_organic.jpg", "corridor_one_point.jpg", "street_one_point.jpg", "office.jpg", "cafe.jpg",
          "street_corner.jpg", "church_nave.jpg"]
# church_nave.jpg is a one-point view: its focal length is not observable, so the editor asks for one.
# kitchen.jpg is borderline (cropped photo, pairwise focals disagree): its confidence swings around the
# threshold with tiny input changes, so it is reported by evaluate.py but not asserted here.


def _detect(name):
    path = os.path.join(MEDIA, name)
    if not os.path.isfile(path):
        pytest.skip(f"{name} not downloaded")
    return vp_detect.detect(*_gray_like_blender(path))


def _gray_like_blender(path):
    """Same grey conversion the add-on uses on Blender image pixels (sRGB floats, Rec. 709 weights)."""
    bgr = cv2.imread(path)
    h, w = bgr.shape[:2]
    rgb = bgr[..., ::-1].astype("float32") / 255.0
    gray = lines.to_gray_u8(rgb, w, h, bottom_up=False)
    return lines.detect_segments(gray), w, h


@pytest.mark.parametrize("name", AUTOMATIC)
def test_architecture_calibrates_automatically(name):
    det = _detect(name)
    assert det is not None and det.confidence >= THRESHOLD, det and det.confidence
    assert det.focal_px is not None


@pytest.mark.parametrize("name", EDITOR)
def test_hard_photos_open_the_editor(name):
    det = _detect(name)
    assert det is None or det.confidence < THRESHOLD, det.confidence


def test_forest_trunks_alone_are_not_a_camera():
    det = _detect("forest_organic.jpg")
    # one strong direction (vertical trunks) must not produce a confident camera
    assert det.confidence < THRESHOLD
