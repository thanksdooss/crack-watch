"""기준 패치 카드의 정의.

색(무엇을 기준으로 보정하나)과 기하(몇 mm인가)를 한 장에 담는다. 한 장으로
화이트밸런스 보정과 픽셀→mm 환산을 둘 다 해결하려는 의도다. 사용자가 챙길 물건이
하나여야 실제로 챙긴다.

치수의 단일 출처는 여기와 shared/pipeline.json이다. PDF 생성기와 검출기가 같은 값을 읽는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "shared"
FIXTURES = SHARED / "fixtures"


@lru_cache(maxsize=1)
def pipeline_config() -> dict:
    with (SHARED / "pipeline.json").open(encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class Swatch:
    name: str
    srgb: tuple[float, float, float]  # 0~1
    x_mm: float  # 카드 좌하단 기준
    y_mm: float
    is_neutral: bool  # 보정 계수를 여기서만 구한다


_CARD = pipeline_config()["calibration"]["card"]
# 카드 전체 치수 (mm). 값의 단일 출처는 shared/pipeline.json — 웹 검출기도 같은 값을 읽는다.
CARD_W, CARD_H = float(_CARD["w"]), float(_CARD["h"])
FIDUCIAL_SIZE = float(_CARD["fiducialSize"])
FIDUCIAL_MARGIN = float(_CARD["fiducialMargin"])
SWATCH_MM = float(_CARD["swatchMm"])
SWATCH_GAP = float(_CARD["swatchGap"])
GRID_X0, GRID_Y0 = float(_CARD["gridX0"]), float(_CARD["gridY0"])
RULER_X0, RULER_Y0, RULER_LEN = float(_CARD["rulerX0"]), float(_CARD["rulerY0"]), float(_CARD["rulerLen"])

NEUTRALS = {"white", "gray50", "black", "gray18"}

# 네 모서리 검은 사각형의 중심 좌표. 4점이면 원근 보정(호모그래피)과
# 픽셀→mm 환산이 동시에 풀린다.
FIDUCIAL_CENTERS_MM = (
    (FIDUCIAL_MARGIN + FIDUCIAL_SIZE / 2, FIDUCIAL_MARGIN + FIDUCIAL_SIZE / 2),
    (CARD_W - FIDUCIAL_MARGIN - FIDUCIAL_SIZE / 2, FIDUCIAL_MARGIN + FIDUCIAL_SIZE / 2),
    (FIDUCIAL_MARGIN + FIDUCIAL_SIZE / 2, CARD_H - FIDUCIAL_MARGIN - FIDUCIAL_SIZE / 2),
    (CARD_W - FIDUCIAL_MARGIN - FIDUCIAL_SIZE / 2, CARD_H - FIDUCIAL_MARGIN - FIDUCIAL_SIZE / 2),
)


@lru_cache(maxsize=1)
def swatches() -> tuple[Swatch, ...]:
    cfg = pipeline_config()["calibration"]["patch"]
    names = cfg["swatches"]
    targets = cfg["targetSrgb"]
    cols, rows = cfg["cols"], cfg["rows"]
    out: list[Swatch] = []
    for i, name in enumerate(names):
        col, row = i % cols, i // cols
        # 화면 기준 위쪽 행이 먼저 오도록 y를 뒤집는다(PDF는 y가 위로 증가).
        x = GRID_X0 + col * (SWATCH_MM + SWATCH_GAP)
        y = GRID_Y0 + (rows - 1 - row) * (SWATCH_MM + SWATCH_GAP)
        out.append(
            Swatch(
                name=name,
                srgb=tuple(c / 255 for c in targets[name]),  # type: ignore[arg-type]
                x_mm=x,
                y_mm=y,
                is_neutral=name in NEUTRALS,
            )
        )
    return tuple(out)


def target_srgb(names: list[str] | None = None) -> np.ndarray:
    sw = {s.name: s.srgb for s in swatches()}
    keys = names or [s.name for s in swatches()]
    return np.array([sw[k] for k in keys], dtype=float)


def neutral_names() -> list[str]:
    return [s.name for s in swatches() if s.is_neutral]


def chromatic_names() -> list[str]:
    return [s.name for s in swatches() if not s.is_neutral]
