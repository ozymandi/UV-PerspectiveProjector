"""Synthetic cameras for tests: build a known camera, project world geometry to pixels."""

import numpy as np


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class SynthCamera:
    """Camera at ``location`` (world), yaw about Z then pitch, roll about view axis."""

    def __init__(self, width=4000, height=3000, focal_px=3000.0, yaw_deg=-35.0, pitch_deg=-12.0,
                 roll_deg=0.0, location=(0.0, -8.0, 1.6)):
        self.width, self.height, self.f = width, height, focal_px
        self.pp = np.array([width / 2.0, height / 2.0])
        # camera-to-world: start looking along +Y world (camera -Z = world +Y), Z up
        base = np.column_stack([[1, 0, 0], [0, 0, 1], [0, -1, 0]]).astype(float)
        c2w = rot_z(np.radians(yaw_deg)) @ base @ rot_x(np.radians(pitch_deg)) @ _rot_view(np.radians(roll_deg))
        self.c2w = c2w
        self.M = c2w.T  # world -> camera
        self.location = np.array(location, dtype=float)

    def project(self, p):
        pc = self.M @ (np.asarray(p, dtype=float) - self.location)
        assert pc[2] < 0, "point behind camera"
        return np.array([self.pp[0] + self.f * pc[0] / -pc[2], self.pp[1] - self.f * pc[1] / -pc[2]])

    def vp(self, axis_index):
        d = self.M[:, axis_index]
        return np.array([self.pp[0] * -d[2] + self.f * d[0], self.pp[1] * -d[2] - self.f * d[1], -d[2]])

    def segment(self, p, direction, length=1.0):
        p = np.asarray(p, dtype=float)
        q = p + length * np.asarray(direction, dtype=float)
        return (tuple(self.project(p)), tuple(self.project(q)))


def _rot_view(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def angle_deg(a, b):
    """Max angle between matching columns of two rotation matrices."""
    return max(np.degrees(np.arccos(np.clip(np.dot(a[:, i], b[:, i]), -1, 1))) for i in range(3))
