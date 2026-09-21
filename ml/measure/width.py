"""균열 폭 측정 — 픽셀 단위. mm 환산은 기준 카드가 준 px/mm로 나중에 곱한다.

세 가지 방법을 구현하고 합성 정답과 비교해 고른다(docs/decisions.md):

1. mask_dt  — 마스크 중심선에서 경계까지 거리 × 2. 가장 흔한 방법.
              마스크 두께가 곧 폭이라, 검출기의 이진화 임계에 폭이 끌려간다.
2. fwhm     — 중심선에 수직으로 원본 밝기 단면을 떠서, 어두운 골의 '절반 깊이 폭'.
              마스크와 무관하게 원본 신호에서 잰다. 단, 흐림(blur)보다 가는 균열은
              골이 바닥까지 안 내려가서 흐림 폭만큼 과대추정한다.
3. area     — 단면에서 '어두워진 넓이 ÷ 균열 속 깊이'. 흐려져도 어두워진 총량은
              보존된다는 점을 쓴다. 깊이는 같은 균열의 넓은 구간에서 빌려온다.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .skeleton import thin

from ml.color.card import pipeline_config

METHODS = ("mask_dt", "fwhm", "area", "hybrid")
_M = pipeline_config()["measure"]
SWITCH_PX = float(_M["hybridSwitchPx"])
SMOOTH_FRAC = float(_M["profileSmoothFrac"])


@dataclass
class WidthSample:
    x: float
    y: float
    mask_dt: float
    fwhm: float
    area: float
    depth: float  # 단면 골의 상대 깊이 (0~1)
    hybrid: float = 0.0  # 채택한 방법: 가늘면 area, 넓으면 fwhm


def _direction(skel: np.ndarray, p: np.ndarray, radius: int = 5) -> np.ndarray | None:
    """주변 중심선 점들의 주성분 방향 = 균열이 뻗는 방향. 작은 창만 본다."""
    x, y = int(p[0]), int(p[1])
    h, w = skel.shape
    y0, y1, x0, x1 = max(0, y - radius), min(h, y + radius + 1), max(0, x - radius), min(w, x + radius + 1)
    ys, xs = np.nonzero(skel[y0:y1, x0:x1])
    if len(xs) < 4:
        return None
    nb = np.column_stack([xs, ys]).astype(np.float32)
    c = nb - nb.mean(axis=0)
    _, vecs = np.linalg.eigh(c.T @ c)
    return vecs[:, -1]


def _profile(img: np.ndarray, p: np.ndarray, normal: np.ndarray, half: int, step: float = 0.25
             ) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(-half, half + step, step, dtype=np.float32)
    xs = (p[0] + t * normal[0]).astype(np.float32)
    ys = (p[1] + t * normal[1]).astype(np.float32)
    vals = cv2.remap(img, xs.reshape(1, -1), ys.reshape(1, -1), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT).ravel()
    return t, vals


def _fwhm_and_area(t: np.ndarray, v: np.ndarray, core: float) -> tuple[float, float, float, float]:
    """(fwhm, 어두워진 넓이, 상대 깊이, 배경) — 배경은 단면 양 끝, 골은 가운데 근처 최소."""
    n = len(v)
    tail = max(4, n // 6)
    bg = float(np.median(np.concatenate([v[:tail], v[-tail:]])))
    centre = np.abs(t) <= max(core, 1.0)
    i_min = int(np.argmin(np.where(centre, v, np.inf)))
    vmin = float(v[i_min])
    depth = (bg - vmin) / max(bg, 1e-6)
    if depth <= 0.02:
        return 0.0, 0.0, 0.0, bg
    half = (bg + vmin) / 2
    left = i_min
    while left > 0 and v[left] < half:
        left -= 1
    right = i_min
    while right < n - 1 and v[right] < half:
        right += 1

    def cross(i0: int, i1: int) -> float:
        a, b = v[i0], v[i1]
        f = 0.0 if a == b else (half - a) / (b - a)
        return float(t[i0] + f * (t[i1] - t[i0]))

    fwhm = cross(right - 1, right) - cross(left + 1, left) if 0 < left and right < n - 1 else 0.0
    dt = float(t[1] - t[0])
    # 골 주변(반치폭의 3배 범위)만 적분해 배경 잡음을 덜 줍는다
    win = np.abs(t - t[i_min]) <= max(1.5 * fwhm, 2.0)
    darkness = float(np.sum(np.clip(bg - v[win], 0, None)) * dt)
    return fwhm, darkness, depth, bg


def chord(mask: np.ndarray, p: np.ndarray, normal: np.ndarray, max_len: int = 96) -> int:
    """중심점에서 단면 방향으로 마스크를 가로지른 길이(px). 균열 폭의 대략값 — 평활·탐색 범위에 쓴다."""
    h, w = mask.shape
    total = 1
    for sgn in (1, -1):
        k = 0
        while k < max_len:
            x = int(round(float(p[0] + sgn * (k + 1) * normal[0])))
            y = int(round(float(p[1] + sgn * (k + 1) * normal[1])))
            if not (0 <= x < w and 0 <= y < h) or not mask[y, x]:
                break
            k += 1
        total += k
    return total


def _smooth(v: np.ndarray, sigma_samples: float) -> np.ndarray:
    if sigma_samples <= 0.5:
        return v
    return cv2.GaussianBlur(v.reshape(1, -1).astype(np.float32), (0, 0), sigmaX=sigma_samples,
                            sigmaY=0.01).ravel()


def measure(gray: np.ndarray, mask: np.ndarray, half_width_px: int = 12, stride: int = 3
            ) -> list[WidthSample]:
    """중심선을 따라 stride 간격으로 폭을 잰다. gray는 평탄화된 밝기(배경≈1) 권장."""
    gray = np.asarray(gray, np.float32)
    skel = thin(mask)
    ys, xs = np.nonzero(skel)
    if len(xs) == 0:
        return []
    pts = np.column_stack([xs, ys]).astype(np.float32)
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)

    raw = []
    for i in range(0, len(pts), stride):
        d = _direction(skel, pts[i])
        if d is None:
            continue
        normal = np.array([-d[1], d[0]], np.float32)
        p = pts[i]
        mdt = float(2 * dist[int(p[1]), int(p[0])])
        L = chord(mask, p, normal)
        core = max(1.5, 0.5 * L)
        # 넓은 균열은 ±12px 단면 밖으로 삐져나가 폭이 잘린다. 골 가장자리가 창 끝에 닿으면
        # 창을 두 배로 넓혀 다시 잰다.
        # 반치폭은 균열 폭(L)의 10%만큼 평활한 단면에서 잰다 — 넓은 균열 바닥의 기공 하나가
        # '가장 어두운 점'이 되면 그 기공 폭만 재는 문제가 있었다(docs/decisions.md).
        # 넓이(어두워진 총량)는 평활해도 보존되므로 원본 단면에서 잰다.
        fwhm = 0.0
        for half in (half_width_px, half_width_px * 2, half_width_px * 4):
            t, v = _profile(gray, p, normal, half)
            fwhm, _, depth, bg = _fwhm_and_area(t, _smooth(v, SMOOTH_FRAC * L / (t[1] - t[0])), core)
            _, dark, _, _ = _fwhm_and_area(t, v, core)
            if fwhm > 0 and fwhm < 0.8 * half:
                break
        if fwhm <= 0:
            continue
        raw.append((p, mdt, fwhm, dark, depth, bg))
    if not raw:
        return []

    # 균열 속 진짜 깊이: 흐림이 바닥을 가리지 않는 넓은 구간(반치폭 상위 30%)의 깊이 중앙값.
    fw = np.array([r[2] for r in raw])
    wide = fw >= np.percentile(fw, 70)
    true_depth = float(np.median([r[4] for r, w in zip(raw, wide) if w]))

    out = []
    for p, mdt, fwhm, dark, depth, bg in raw:
        area_w = dark / max(true_depth * bg, 1e-6)
        hyb = area_w if fwhm < SWITCH_PX else fwhm
        out.append(WidthSample(float(p[0]), float(p[1]), max(mdt, 0.0), fwhm, area_w, depth, hyb))
    return out
