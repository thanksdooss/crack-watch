"""조명 조건을 합성한다 — 실촬영 전에 보정 알고리즘을 검증하기 위한 것.

합성이라는 점을 분명히 한다. 이 숫자는 "알고리즘이 원리대로 동작하는가"의 증거이지
"실제 스마트폰에서 이만큼 나온다"의 증거가 아니다. 실촬영 측정은 별도로 채운다.

모델: 반사색 → 조명에 따른 색 이동(von Kries, Bradford) → 카메라 자동 화이트밸런스가
일부만 되돌림(strength) → 노출 배율 → 플레어(더하기) → 클리핑 → 센서 잡음.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .difference import (
    D65,
    linear_to_srgb,
    linear_to_xyz,
    srgb_to_linear,
    xyz_to_linear,
)

BRADFORD = np.array(
    [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]]
)
BRADFORD_INV = np.linalg.inv(BRADFORD)

# CIE 표준 광원의 색도 좌표. 석양은 2500K 흑체 근사(Kim 등의 플랑크 궤적 근사식).
ILLUMINANTS_XY: dict[str, tuple[float, float]] = {
    "주광 D65": (0.31272, 0.32903),
    "흐린 하늘 D75": (0.29902, 0.31485),
    "형광등 F2": (0.37208, 0.37529),
    "백열등 A": (0.44757, 0.40745),
    "석양 2500K": (0.47701, 0.41366),
}


def xy_to_xyz(x: float, y: float) -> np.ndarray:
    return np.array([x / y, 1.0, (1 - x - y) / y])


def adapt(xyz: np.ndarray, src_white: np.ndarray, dst_white: np.ndarray,
          strength: float = 1.0) -> np.ndarray:
    """von Kries 색순응. strength=1이면 완전 순응, 0이면 아무 것도 안 함."""
    cone = np.asarray(xyz, float) @ BRADFORD.T
    ratio = (dst_white @ BRADFORD.T) / (src_white @ BRADFORD.T)
    return (cone * (ratio**strength)) @ BRADFORD_INV.T


@dataclass(frozen=True)
class CaptureConditions:
    illuminant: str
    awb_strength: float = 0.75  # 스마트폰 자동 화이트밸런스가 되돌리는 비율
    exposure: float = 1.0
    flare: float = 0.0  # 선형값에 더해지는 잡광
    noise_sigma: float = 0.0  # 픽셀 하나의 잡음
    # 스와치는 점이 아니라 면이다. 실제로는 스와치 안의 수백 픽셀을 평균 내 읽으므로
    # 잡음은 √n만큼 줄어든다. 이걸 빼면 어두운 스와치의 잡음이 과장돼,
    # 보정이 필요 없는 조명에서도 보정이 손해처럼 보인다.
    patch_pixels: int = 256


def capture(srgb: np.ndarray, cond: CaptureConditions, rng: np.random.Generator | None = None
            ) -> np.ndarray:
    """D65에서의 색 srgb가 주어진 조건에서 어떻게 찍히는지."""
    src = D65
    dst = xy_to_xyz(*ILLUMINANTS_XY[cond.illuminant])
    dst = dst / dst[1] * src[1]

    xyz = linear_to_xyz(srgb_to_linear(srgb))
    lit = adapt(xyz, src, dst)                       # 조명 아래에서의 색
    seen = adapt(lit, dst, src, cond.awb_strength)   # 카메라가 일부만 되돌림
    lin = xyz_to_linear(seen) * cond.exposure + cond.flare
    if cond.noise_sigma and rng is not None:
        effective = cond.noise_sigma / np.sqrt(max(cond.patch_pixels, 1))
        lin = lin + rng.normal(0.0, effective, size=lin.shape)
    return linear_to_srgb(np.clip(lin, 0.0, 1.0))
