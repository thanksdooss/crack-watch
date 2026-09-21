"""검증 규칙의 임계값. 코드에 흩어 두지 않고 한곳에 모은다 — 운영하며 조정할 값들이다.

값의 근거:
- 15m: 스마트폰 GPS의 도심 오차 수준. 같은 벽 앞에서 찍어도 이만큼은 흔들린다.
- 해밍 거리(64비트 지각 해시)는 실제 벽 사진으로 잰 분포에서 골랐다(ml/eval/phash_study.py,
  docs/results/phash.json). 처음엔 '같은 장면 ≤ 14'로 가정했는데, 재촬영(구도·조명 변화)의
  중앙값이 16비트라 정상 재촬영의 절반도 못 묶었다.
  · 같은 장면 ≤ 18: 재촬영 약 77% 묶임, 서로 다른 벽 충돌 0.3~0.8% — 15m 안 후보끼리만 비교하므로 감당 가능
  · 사실상 같은 사진 ≤ 8: 재압축·밝기만 다른 사진 100% 잡힘, 충돌 0.06% 이하
  · 다른 위치의 같은 장면 ≤ 12: 500m 안 많은 후보와 비교하므로 엄격하게(충돌 0.2% 이하)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rules:
    site_radius_m: float = 15.0
    max_radius_m: float = 50.0  # GPS 정확도가 나빠도 이 이상 넓혀 묶지 않는다
    same_scene_hamming: int = 18
    duplicate_hamming: int = 8
    reuse_far_m: float = 200.0  # 같은 사진이 이보다 먼 곳으로 올라오면 재사용
    duplicate_same_device_hours: float = 24.0  # 같은 기기가 같은 장면을 하루 안에 또 보냄
    duplicate_any_device_hours: float = 2.0  # 누구든 거의 같은 사진을 2시간 안에 또 보냄
    hold_below: float = 0.5
    gps_imprecise_m: float = 50.0
    blur_max: float = 0.6
    future_skew_min: float = 10.0
    stale_days: float = 30.0
    flood_per_hour: int = 6  # 한 건물 균열 여러 개를 연달아 올리는 정상 사용은 대개 3~5건
    device_min_reviewed: int = 3
    device_reject_rate: float = 0.5
    max_plausible_width_mm: float = 50.0
    # 같은 장면이 이 거리 안의 '다른 위치'에 이미 있으면 위치가 틀렸을 가능성 (엉뚱한 건물 신고)
    scene_elsewhere_m: float = 500.0
    scene_elsewhere_hamming: int = 12


RULES = Rules()
