"""Manhattan-world vanishing point detection from line segments.

Search (after Lu et al. 2017, "2-line exhaustive searching", extended to an unknown
focal length by scanning focal candidates):

1. For a focal candidate f, lift each segment to the unit normal of its
   interpretation plane in camera space.
2. VP1 hypotheses = intersections of random pairs of long segments.
3. For each VP1, sweep VP2 around the great circle orthogonal to VP1; VP3 = VP1 x VP2.
4. Score = length of segments whose plane passes within ``angle_tol`` of one of the
   three directions. Best (f, VP1, VP2) wins.
5. Refine each VP in image space by weighted least squares over its inliers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import solve

ANGLE_TOL_DEG = 1.5
MIN_SEGMENTS_PER_VP = 4
FOCAL_35MM_RANGE = (8.0, 400.0)  # plausible 35 mm-equivalent focal lengths
SECOND_AXIS_FULL_SUPPORT = 0.15
MIN_AXIS_SUPPORT = 0.03  # an axis needs this share of edge length to count
MAX_FOCAL_SPREAD = 1.25
EXHAUSTIVE_TOP = 60  # all pairs of the 60 longest segments are VP1 candidates  # pairwise focal estimates may differ by this factor before confidence drops  # second direction needs this share of edge length for full confidence


@dataclass
class Detection:
    vps: list  # homogeneous (u, v, w) in pixels, indexed by axis X, Y, Z
    support: list  # inlier length fraction per axis
    inliers: list  # list of index arrays per axis into the segment array
    confidence: float
    focal_px: float | None  # None when the photo does not constrain the focal length
    width: int
    height: int
    segments: np.ndarray = field(repr=False, default=None)
    focal_search_px: float | None = None  # best focal of the orthogonal-triplet search (diagnostics)

    def axis_pair(self):
        """Two (axis, vp) entries to solve from (and to seed the editor with).

        With a known focal: the two best-supported finite VPs. Without one (one-point views): the VP
        nearest the image centre plus the best-supported other one, because two VPs far towards
        infinity give no camera even once the user enters a focal length.
        """
        order = sorted(range(3), key=lambda i: -self.support[i])
        good = [i for i in order if self.support[i] >= MIN_AXIS_SUPPORT] or order
        if self.focal_px is None:
            centre = np.array([self.width / 2.0, self.height / 2.0])

            def dist(i):
                v = self.vps[i]
                return np.inf if v[2] == 0 else float(np.linalg.norm(v[:2] / v[2] - centre))

            # the nearest finite VP may have few inliers (e.g. the depth direction of a one-point
            # view, which the two other axes already fix); it still anchors the camera
            a = min(range(3), key=dist)
            if not np.isfinite(dist(a)):
                a = good[0]
            b = next(i for i in order if i != a)
        else:
            finite = [i for i in good if self.vps[i][2] != 0]
            a, b = (finite[0], finite[1]) if len(finite) >= 2 else (order[0], order[1])
        a, b = sorted((a, b))
        return (solve.AXES[a], solve.AXES[b]), (self.vps[a], self.vps[b])

    def solution(self, focal_px=None):
        axes, vps = self.axis_pair()
        f = focal_px if focal_px is not None else self.focal_px
        return solve.solve_from_vps(vps[0], vps[1], axes, self.width, self.height, focal_px=f)


def _centred(seg, width, height):
    cx, cy = width / 2.0, height / 2.0
    p = np.stack([seg[:, 0] - cx, -(seg[:, 1] - cy)], axis=1)
    q = np.stack([seg[:, 2] - cx, -(seg[:, 3] - cy)], axis=1)
    return p, q


def _plane_normals(p, q, f):
    a = np.column_stack([p, np.full(len(p), -f)])
    b = np.column_stack([q, np.full(len(q), -f)])
    n = np.cross(a, b)
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def _orthonormal_basis(d):
    helper = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(d, helper)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return u, v


def _search_for_focal(normals, weights, f, rng, n_pairs, top_k, tol, phi_steps):
    """Best (score, d1, d2, d3) for one focal candidate."""
    n = len(normals)
    # every pair of the longest segments (deterministic: the dominant directions are always tried)
    # plus random pairs over all segments; segments arrive sorted longest first
    top = min(n, EXHAUSTIVE_TOP)
    ii, jj = np.triu_indices(top, k=1)
    idx = np.concatenate([np.column_stack([ii, jj]), rng.integers(0, n, size=(n_pairs, 2))])
    idx = idx[idx[:, 0] != idx[:, 1]]
    cand = np.cross(normals[idx[:, 0]], normals[idx[:, 1]])
    norms = np.linalg.norm(cand, axis=1)
    cand = cand[norms > 1e-9] / norms[norms > 1e-9, None]
    if len(cand) == 0:
        return -1.0, None
    # single-VP score to keep the most promising VP1 candidates
    single = (np.abs(cand @ normals.T) < tol) @ weights
    order = np.argsort(-single)
    chosen = []
    for i in order:
        d = cand[i]
        if all(abs(np.dot(d, c)) < np.cos(np.radians(2.0)) for c in chosen):
            chosen.append(d)
        if len(chosen) >= top_k:
            break
    phis = np.linspace(0.0, np.pi, phi_steps, endpoint=False)
    best = (-1.0, None)
    for d1 in chosen:
        u, v = _orthonormal_basis(d1)
        d2 = np.outer(np.cos(phis), u) + np.outer(np.sin(phis), v)  # (P, 3)
        d3 = np.cross(d1, d2)
        r1 = np.abs(normals @ d1)  # (N,)
        r2 = np.abs(d2 @ normals.T)  # (P, N)
        r3 = np.abs(d3 @ normals.T)
        rmin = np.minimum(np.minimum(r1[None, :], r2), r3)
        scores = (rmin < tol) @ weights
        k = int(np.argmax(scores))
        if scores[k] > best[0]:
            best = (float(scores[k]), (d1, d2[k], d3[k]))
    return best


def _vp_to_image(d, f, width, height):
    """Camera-space direction -> homogeneous pixel VP."""
    cx, cy = width / 2.0, height / 2.0
    x, y, z = d
    w = -z / f if f > 0 else 0.0
    return np.array([x + cx * w, -y + cy * w, w])


def _refine_vp(seg, idx, weights, diag):
    """Weighted least-squares intersection of inlier segment lines (pixels)."""
    s = 1.0 / diag  # scale pixels to ~unit range for conditioning
    p = np.column_stack([seg[idx, 0] * s, seg[idx, 1] * s, np.ones(len(idx))])
    q = np.column_stack([seg[idx, 2] * s, seg[idx, 3] * s, np.ones(len(idx))])
    lines = np.cross(p, q)
    lines /= np.linalg.norm(lines[:, :2], axis=1, keepdims=True)
    _, _, vt = np.linalg.svd(lines * weights[idx, None])
    vs = vt[-1]
    return solve.normalize_vp(np.array([vs[0] / s, vs[1] / s, vs[2]]), diag)


def _image_residual_deg(seg, vp):
    """Angle between each segment and the line from its midpoint to the VP (degrees)."""
    mid = (seg[:, :2] + seg[:, 2:]) / 2.0
    d_seg = seg[:, 2:] - seg[:, :2]
    if vp[2] != 0:
        d_vp = vp[:2] / vp[2] - mid
    else:
        d_vp = np.tile(vp[:2], (len(seg), 1))
    cos = np.abs(np.sum(d_seg * d_vp, axis=1)) / (np.linalg.norm(d_seg, axis=1) * np.linalg.norm(d_vp, axis=1) + 1e-12)
    return np.degrees(np.arccos(np.clip(cos, 0.0, 1.0)))


def _assign_axes(seg, dirs, vps, inl, f):
    """Map the three found directions to X, Y, Z. Returns an index permutation."""
    verticality = []
    for k in range(3):
        if len(inl[k]) == 0:
            verticality.append(0.0)
            continue
        d = seg[inl[k], 2:] - seg[inl[k], :2]
        ang = np.abs(d[:, 1]) / (np.linalg.norm(d, axis=1) + 1e-12)
        verticality.append(float(np.average(ang, weights=np.linalg.norm(d, axis=1))))
    z = int(np.argmax(verticality))
    rest = [k for k in range(3) if k != z]
    # point each horizontal direction into the scene, then the one further right is X
    xs = []
    for k in rest:
        d = dirs[k] if dirs[k][2] < 0 else -dirs[k]
        xs.append(d[0])
    x = rest[int(np.argmax(xs))]
    y = rest[0] if x == rest[1] else rest[1]
    return x, y, z


def _rodrigues(w):
    theta = float(np.linalg.norm(w))
    if theta < 1e-12:
        return np.eye(3)
    k = w / theta
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(theta) * kx + (1 - np.cos(theta)) * kx @ kx


def _refine_camera(p, q, weights, inl, axes_used, m0, f0, free_focal, f_range, iterations=15):
    """Levenberg-Marquardt on (rotation, log focal) minimising inlier plane residuals |n_i . d_k|.

    The focal is kept inside ``f_range``: unbounded, it runs off to a near-orthographic camera
    (every pair of image directions looks orthogonal) or collapses towards zero.
    """
    lo, hi = np.log(f_range[0] / f0), np.log(f_range[1] / f0)
    idx = np.concatenate([inl[k] for k in axes_used])
    owner = np.concatenate([np.full(len(inl[k]), k) for k in axes_used])
    sw = np.sqrt(weights[idx])

    def residuals(x):
        m = _rodrigues(x[:3]) @ m0
        f = f0 * np.exp(x[3])
        n = _plane_normals(p[idx], q[idx], f)
        d = m[:, owner].T
        return sw * np.sum(n * d, axis=1)

    nparam = 4 if free_focal else 3
    x = np.zeros(4)
    lam = 1e-3
    r = residuals(x)
    cost = float(r @ r)
    for _ in range(iterations):
        jac = np.empty((len(r), nparam))
        for j in range(nparam):
            dx = np.zeros(4)
            dx[j] = 1e-6
            jac[:, j] = (residuals(x + dx) - r) / 1e-6
        a = jac.T @ jac
        g = jac.T @ r
        improved = False
        for _ in range(8):
            step = np.linalg.solve(a + lam * np.diag(np.diag(a) + 1e-12), -g)
            xn = x.copy()
            xn[:nparam] += step
            xn[3] = float(np.clip(xn[3], lo, hi))
            rn = residuals(xn)
            cn = float(rn @ rn)
            if cn < cost:
                x, r, cost, lam, improved = xn, rn, cn, lam * 0.3, True
                break
            lam *= 10
        if not improved or np.linalg.norm(step) < 1e-10:
            break
    return _rodrigues(x[:3]) @ m0, f0 * np.exp(x[3])


def detect(segments: np.ndarray, width: int, height: int, focal_hint_px: float | None = None,
           seed: int = 0, starts: int = 3, **kwargs) -> Detection | None:
    """Find three orthogonal vanishing points. Returns None when there are too few segments.

    The search has several nearly equal optima on real photos; ``starts`` independent runs are made
    and the one that explains the most edge length wins, so the result does not hinge on one seed.
    """
    best = None
    for k in range(starts):
        det = _detect_once(segments, width, height, focal_hint_px, seed=seed + 1000 * k, **kwargs)
        if det is None:
            continue
        if best is None or sum(det.support) > sum(best.support) + 1e-9:
            best = det
    return best


def _detect_once(segments: np.ndarray, width: int, height: int, focal_hint_px: float | None = None,
                 seed: int = 0, max_segments: int = 600, n_pairs: int = 1500, top_k: int = 40,
                 phi_steps: int = 180, angle_tol_deg: float = ANGLE_TOL_DEG) -> Detection | None:
    """One search run (see ``detect``)."""
    seg = np.asarray(segments, dtype=float)[:max_segments]
    if len(seg) < 6:
        return None
    diag = float(np.hypot(width, height))
    lengths = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1])
    weights = lengths / lengths.sum()
    p, q = _centred(seg, width, height)
    tol = np.sin(np.radians(angle_tol_deg)) * 0.5
    rng = np.random.default_rng(seed)

    side = float(max(width, height))
    focals = list(np.geomspace(0.35 * side, 5.0 * side, 18))
    if focal_hint_px:
        focals.append(float(focal_hint_px))

    def run(fs):
        best = (-1.0, None, None)
        for f in fs:
            normals = _plane_normals(p, q, f)
            score, dirs = _search_for_focal(normals, weights, f, rng, n_pairs, top_k, tol, phi_steps)
            if dirs is not None and score > best[0] + 1e-9:
                best = (score, f, dirs)
        return best

    score, f_best, dirs = run(focals)
    if dirs is None:
        return None
    fine = np.geomspace(f_best / 1.25, f_best * 1.25, 9)
    score2, f2, dirs2 = run(fine)
    if dirs2 is not None and score2 >= score:
        score, f_best, dirs = score2, f2, dirs2

    # image-space assignment and refinement
    vps0 = [_vp_to_image(d, f_best, width, height) for d in dirs]
    vps0 = [solve.normalize_vp(v, diag) for v in vps0]
    res = np.stack([_image_residual_deg(seg, v) for v in vps0], axis=1)
    owner = np.argmin(res, axis=1)
    ok = res[np.arange(len(seg)), owner] < angle_tol_deg
    inl = [np.where(ok & (owner == k))[0] for k in range(3)]
    vps = []
    for k in range(3):
        if len(inl[k]) >= 2:
            vps.append(_refine_vp(seg, inl[k], weights, diag))
        else:
            vps.append(vps0[k])
    # re-assign once against the refined VPs
    res = np.stack([_image_residual_deg(seg, v) for v in vps], axis=1)
    owner = np.argmin(res, axis=1)
    ok = res[np.arange(len(seg)), owner] < angle_tol_deg
    inl = [np.where(ok & (owner == k))[0] for k in range(3)]
    support = [float(weights[i].sum()) for i in inl]

    xi, yi, zi = _assign_axes(seg, dirs, vps, inl, f_best)
    perm = [xi, yi, zi]
    vps = [vps[k] for k in perm]
    inl = [inl[k] for k in perm]
    support = [support[k] for k in perm]

    def plausible(f):
        return f is not None and FOCAL_35MM_RANGE[0] <= f * 43.2666 / diag <= FOCAL_35MM_RANGE[1]

    def assign(vps_):
        r = np.stack([_image_residual_deg(seg, v) for v in vps_], axis=1)
        own = np.argmin(r, axis=1)
        ok_ = r[np.arange(len(seg)), own] < angle_tol_deg
        inl_ = [np.where(ok_ & (own == k))[0] for k in range(3)]
        return inl_, [float(weights[i].sum()) for i in inl_]

    # focal from every pair of well-supported finite VPs; disagreement between pairs means the
    # photo breaks the model (cropped / off-centre principal point, distortion): lower confidence
    good = [k for k in range(3) if len(inl[k]) >= MIN_SEGMENTS_PER_VP and support[k] >= MIN_AXIS_SUPPORT]
    finite = [k for k in good if vps[k][2] != 0]
    pair_focals = []
    for i in range(len(finite)):
        for j in range(i + 1, len(finite)):
            try:
                f_ij = solve.focal_from_vps(vps[finite[i]], vps[finite[j]], np.array([width / 2.0, height / 2.0]))
            except solve.CalibrationError:
                continue
            if plausible(f_ij):
                pair_focals.append(f_ij)
    focal = float(np.exp(np.median(np.log(pair_focals)))) if pair_focals else None
    focal_spread = max(pair_focals) / min(pair_focals) if len(pair_focals) >= 2 else 1.0

    # joint refinement of rotation (+ focal when constrained) over all inlier segments;
    # kept only when it does not lose inliers
    if len(good) >= 2:
        f0 = focal or focal_hint_px or f_best
        order = sorted(good, key=lambda k: -support[k])
        a, b = sorted(order[:2])
        try:
            sol = solve.solve_from_vps(vps[a], vps[b], (solve.AXES[a], solve.AXES[b]), width, height, focal_px=f0)
            f_range = (0.35 * side, 5.0 * side)
            # rotation only: the plane-residual cost is biased towards short focal lengths,
            # so the focal stays the one from the vanishing points
            m, f_ref = _refine_camera(p, q, weights, inl, good, sol.rotation, f0, False, f_range)
            vps_ref = [solve.normalize_vp(_vp_to_image(m[:, k], float(f_ref), width, height), diag) for k in range(3)]
            inl_ref, support_ref = assign(vps_ref)
            if sum(support_ref) >= 0.98 * sum(support):
                vps, inl, support = vps_ref, inl_ref, support_ref
                if focal is not None:
                    focal = float(f_ref) if plausible(float(f_ref)) else None
        except solve.CalibrationError:
            pass

    # confidence: share of explained edges, scaled by the second-strongest direction
    # (a camera needs two directions: a forest of vertical trunks alone is not enough)
    good = [k for k in range(3) if len(inl[k]) >= MIN_SEGMENTS_PER_VP and support[k] >= MIN_AXIS_SUPPORT]
    explained = float(sum(support))
    ranked = sorted((support[k] for k in good), reverse=True)
    second = ranked[1] if len(ranked) >= 2 else 0.0
    confidence = explained * min(1.0, second / SECOND_AXIS_FULL_SUPPORT)
    if len(good) < 3:
        confidence *= 0.85
    if focal is None and focal_hint_px is None:
        confidence *= 0.5
    confidence *= min(1.0, MAX_FOCAL_SPREAD / focal_spread)

    return Detection(vps=vps, support=support, inliers=inl, confidence=confidence,
                     focal_px=focal, width=int(width), height=int(height), segments=seg,
                     focal_search_px=float(f_best))
