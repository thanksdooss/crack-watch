"""고전 영상처리 균열 검출 — 모델 없이 여기까지가 기준선이다.

순서:
1. 밝기 평탄화 — 사진 전체의 그림자·조명 기울기를 지운다(큰 블러로 나눔).
2. 능선(ridge) 강조 — 헤세 행렬 고유값으로 "주변보다 어두운 가는 선"을 찾는다(Frangi).
   점 모양(기공)은 두 방향 곡률이 비슷해서 걸러지고, 선 모양만 남는다.
3. 이력 임계(hysteresis) — 확실한 부분(high)에 이어진 애매한 부분(low)까지만 살린다.
   균열은 끊겼다 이어지므로 단일 임계보다 연속성을 잘 지킨다.
4. 모양 필터 — 짧거나 뭉툭한 덩어리를 버린다.

파라미터는 shared/pipeline.json의 "classic". 웹 구현도 같은 값을 읽는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ml.color.card import pipeline_config


@dataclass(frozen=True)
class ClassicParams:
    flatten_sigma: float
    scales: tuple[float, ...]
    beta: float
    c: float
    hyst_high: float
    hyst_low: float
    min_length_px: int
    min_elongation: float

    @classmethod
    def from_config(cls, **override) -> "ClassicParams":
        c = pipeline_config()["classic"]
        base = dict(
            flatten_sigma=c["flattenSigma"], scales=tuple(c["scales"]), beta=c["beta"], c=c["c"],
            hyst_high=c["hystHigh"], hyst_low=c["hystLow"], min_length_px=c["minLengthPx"],
            min_elongation=c["minElongation"],
        )
        base.update(override)
        return cls(**base)


def to_gray(img: np.ndarray) -> np.ndarray:
    """0~1 float RGB → 휘도. uint8도 받는다."""
    img = np.asarray(img)
    if img.dtype == np.uint8:
        img = img.astype(np.float32) / 255
    if img.ndim == 3:
        img = img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722
    return img.astype(np.float32)


def flatten(gray: np.ndarray, sigma: float) -> np.ndarray:
    """배경 밝기로 나눠 그림자를 지운다. 결과는 배경 ≈ 1."""
    bg = cv2.GaussianBlur(gray, (0, 0), sigma)
    return gray / np.maximum(bg, 1e-3)


def ridge_response(flat: np.ndarray, p: ClassicParams) -> np.ndarray:
    """어두운 능선(균열)에 강하게, 점·평면에 약하게 반응하는 지도. 0~1."""
    out = np.zeros_like(flat)
    for s in p.scales:
        g = cv2.GaussianBlur(flat, (0, 0), s)
        dxx = cv2.Sobel(g, cv2.CV_32F, 2, 0, ksize=3) * s * s
        dyy = cv2.Sobel(g, cv2.CV_32F, 0, 2, ksize=3) * s * s
        dxy = cv2.Sobel(g, cv2.CV_32F, 1, 1, ksize=3) * s * s
        tmp = np.sqrt((dxx - dyy) ** 2 + 4 * dxy**2)
        l1 = 0.5 * (dxx + dyy + tmp)
        l2 = 0.5 * (dxx + dyy - tmp)
        swap = np.abs(l1) < np.abs(l2)
        la = np.where(swap, l1, l2)  # 작은 쪽: 선을 따라가는 방향
        lb = np.where(swap, l2, l1)  # 큰 쪽: 선을 가로지르는 방향
        rb = la / (lb + 1e-9)
        ss = np.sqrt(la**2 + lb**2)
        v = np.exp(-(rb**2) / (2 * p.beta**2)) * (1 - np.exp(-(ss**2) / (2 * p.c**2)))
        v[lb <= 0] = 0  # 밝은 선(긁힘 반사 등)은 균열이 아니다
        out = np.maximum(out, v)
    return out


def hysteresis(resp: np.ndarray, low: float, high: float) -> np.ndarray:
    weak = (resp >= low).astype(np.uint8)
    n, labels = cv2.connectedComponents(weak, connectivity=8)
    if n <= 1:
        return np.zeros_like(weak)
    strong_ids = np.unique(labels[resp >= high])
    keep = np.zeros(n, bool)
    keep[strong_ids] = True
    keep[0] = False
    return keep[labels].astype(np.uint8)


def shape_filter(mask: np.ndarray, min_length: int, min_elongation: float) -> np.ndarray:
    """짧은 조각과 뭉툭한 덩어리를 버린다.

    길이는 회전 외접 사각형의 긴 변, 가늘기는 (길이² / 면적)으로 잰다.
    선이면 면적이 길이×폭이라 이 값이 길이/폭 ≈ 크고, 덩어리면 작다.

    조각이 수천 개(기공 파편)일 수 있어서, 조각마다 전체 이미지를 훑지 않는다.
    외접 상자 대각선이 최소 길이보다 짧으면 회전 사각형을 볼 필요도 없이 버린다.
    """
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return np.zeros_like(mask)
    diag = np.hypot(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT])
    candidates = np.nonzero((diag >= min_length) & (stats[:, cv2.CC_STAT_AREA] >= 4))[0]
    candidates = candidates[candidates > 0]
    keep = np.zeros(n, bool)
    for i in candidates:
        x, y, w, h, area = stats[i]
        ys, xs = np.nonzero(labels[y:y + h, x:x + w] == i)
        (_, _), (rw, rh), _ = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
        length = max(rw, rh)
        if length >= min_length and length * length / area >= min_elongation:
            keep[i] = True
    return keep[labels].astype(np.uint8)


def detect(img: np.ndarray, p: ClassicParams | None = None) -> tuple[np.ndarray, np.ndarray]:
    """균열 마스크(uint8 0/1)와 능선 응답 지도를 돌려준다."""
    p = p or ClassicParams.from_config()
    flat = flatten(to_gray(img), p.flatten_sigma)
    resp = ridge_response(flat, p)
    mask = hysteresis(resp, p.hyst_low, p.hyst_high)
    mask = shape_filter(mask, p.min_length_px, p.min_elongation)
    return mask, resp
