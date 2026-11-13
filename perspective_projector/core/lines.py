"""Line segment detection (OpenCV LSD) with downscaling and length filtering."""

from __future__ import annotations

import numpy as np

DEFAULT_MAX_SIDE = 4096
DEFAULT_MIN_LENGTH_FRACTION = 0.02


def to_gray_u8(pixels, width: int, height: int, bottom_up: bool = True) -> np.ndarray:
    """Convert Blender-style float RGBA pixels (flat or HxWx4, rows bottom-up) to top-down uint8 gray."""
    arr = np.asarray(pixels, dtype=np.float32).reshape(height, width, -1)
    rgb = arr[..., :3] if arr.shape[2] >= 3 else np.repeat(arr[..., :1], 3, axis=2)
    gray = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    if bottom_up:
        gray = gray[::-1]
    return np.clip(gray * 255.0 + 0.5, 0, 255).astype(np.uint8)


def detect_segments(gray: np.ndarray, max_side: int = DEFAULT_MAX_SIDE,
                    min_length_fraction: float = DEFAULT_MIN_LENGTH_FRACTION) -> np.ndarray:
    """Detect straight segments in a top-down uint8 gray image.

    Returns an (N, 4) float array ``x0, y0, x1, y1`` in full-resolution pixel
    coordinates (origin top-left), sorted longest first.
    """
    import cv2

    if gray.ndim != 2:
        raise ValueError("expected a 2D gray image")
    h, w = gray.shape
    scale = min(1.0, max_side / float(max(w, h)))
    small = gray
    if scale < 1.0:
        small = cv2.resize(gray, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                           interpolation=cv2.INTER_AREA)
    lsd = cv2.createLineSegmentDetector()
    found = lsd.detect(small)[0]
    if found is None or len(found) == 0:
        return np.zeros((0, 4))
    seg = found.reshape(-1, 4).astype(float) / scale
    lengths = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1])
    keep = lengths >= min_length_fraction * np.hypot(w, h)
    seg, lengths = seg[keep], lengths[keep]
    return seg[np.argsort(-lengths)]
