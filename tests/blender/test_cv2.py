"""OpenCV bundled with the extension imports inside Blender and LSD works."""

import numpy as np

import cv2

img = np.zeros((200, 200), np.uint8)
cv2.rectangle(img, (50, 50), (150, 150), 255, -1)
found = cv2.createLineSegmentDetector().detect(img)[0]
assert found is not None and len(found) >= 4, "LSD found no segments"
print("cv2", cv2.__version__, "numpy", np.__version__)
