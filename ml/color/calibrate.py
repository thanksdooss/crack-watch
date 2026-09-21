"""사진 속 기준 패치로 색을 정규화한다.

모델: 채널마다 `관측 = 이득 × 실제 + 오프셋`.
- 오프셋은 검은 스와치가 잡는다(렌즈 플레어, 센서 블랙 레벨 — 어두운 데가 안 어두운 현상).
- 이득은 흰색·회색이 잡는다(조명 색 + 자동 화이트밸런스가 남긴 잔여 색 틀어짐).

중요한 설계 선택: **계수는 무채색 스와치에서만 구한다.** 빨강·파랑 스와치는 계산에
넣지 않고 검증용으로 남긴다. 전부 넣고 맞추면 "잘 맞는다"는 결과가 당연해져서
숫자가 아무것도 증명하지 못한다. 빼놓은 색이 보정 후에 제자리를 찾아야 진짜다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .card import neutral_names, pipeline_config, target_srgb
from .difference import delta_e_2000, srgb_to_lab, srgb_to_linear, linear_to_srgb

MIN_GAIN = 1e-4


@dataclass(frozen=True)
class Correction:
    gain: np.ndarray  # (3,)
    offset: np.ndarray  # (3,)
    residual_delta_e: float  # 무채색 스와치에서의 보정 후 잔차
    quality: str  # good | fair | poor

    def apply_linear(self, linear: np.ndarray) -> np.ndarray:
        return np.clip((np.asarray(linear, float) - self.offset) / self.gain, 0.0, 1.0)

    def apply_srgb(self, srgb: np.ndarray) -> np.ndarray:
        return linear_to_srgb(self.apply_linear(srgb_to_linear(srgb)))


def fit(observed_srgb: np.ndarray, names: list[str]) -> Correction:
    """관측된 스와치 색에서 보정 계수를 구한다.

    observed_srgb: (N, 3) 0~1, names: 각 행이 어떤 스와치인지
    """
    observed_srgb = np.asarray(observed_srgb, dtype=float)
    idx = [i for i, n in enumerate(names) if n in set(neutral_names())]
    if len(idx) < 2:
        raise ValueError("무채색 스와치가 2개 이상 있어야 이득과 오프셋을 나눌 수 있다")

    obs_lin = srgb_to_linear(observed_srgb[idx])
    tgt_lin = srgb_to_linear(target_srgb([names[i] for i in idx]))

    gain = np.empty(3)
    offset = np.empty(3)
    for c in range(3):
        # 채널별 1차 최소제곱: obs = gain*tgt + offset
        a = np.vstack([tgt_lin[:, c], np.ones(len(idx))]).T
        sol, *_ = np.linalg.lstsq(a, obs_lin[:, c], rcond=None)
        gain[c], offset[c] = max(float(sol[0]), MIN_GAIN), float(sol[1])

    corrected = np.clip((obs_lin - offset) / gain, 0.0, 1.0)
    residual = float(
        np.mean(delta_e_2000(srgb_to_lab(linear_to_srgb(corrected)),
                             srgb_to_lab(linear_to_srgb(tgt_lin))))
    )
    th = pipeline_config()["calibration"]["deltaEThreshold"]
    quality = "good" if residual <= th["good"] else "fair" if residual <= th["fair"] else "poor"
    return Correction(gain=gain, offset=offset, residual_delta_e=residual, quality=quality)
