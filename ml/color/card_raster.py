"""기준 카드를 이미지로 그리고, 장면에 원근·조명을 입혀 합성한다(검출기 시험용)."""

from __future__ import annotations

import cv2
import numpy as np

from .card import CARD_H, CARD_W, FIDUCIAL_MARGIN, FIDUCIAL_SIZE, SWATCH_MM, swatches


def render(px_per_mm: float = 10.0) -> np.ndarray:
    """카드 좌하단 원점(mm) → 이미지 좌상단 원점. float RGB 0~1."""
    w, h = int(round(CARD_W * px_per_mm)), int(round(CARD_H * px_per_mm))
    img = np.full((h, w, 3), 0.95, np.float32)

    def box(x_mm, y_mm, s_mm, color):
        x0 = int(round(x_mm * px_per_mm))
        y1 = int(round((CARD_H - y_mm) * px_per_mm))
        y0 = int(round((CARD_H - y_mm - s_mm) * px_per_mm))
        x1 = int(round((x_mm + s_mm) * px_per_mm))
        img[y0:y1, x0:x1] = color

    for fx in (FIDUCIAL_MARGIN, CARD_W - FIDUCIAL_MARGIN - FIDUCIAL_SIZE):
        for fy in (FIDUCIAL_MARGIN, CARD_H - FIDUCIAL_MARGIN - FIDUCIAL_SIZE):
            box(fx, fy, FIDUCIAL_SIZE, (0.02, 0.02, 0.02))
    for s in swatches():
        box(s.x_mm, s.y_mm, SWATCH_MM, s.srgb)
    return img


def card_mm_to_raster(px_per_mm: float) -> np.ndarray:
    """카드 mm 좌표(y 위로) → 카드 래스터 픽셀 좌표(y 아래로) 변환 행렬."""
    return np.array([[px_per_mm, 0, 0], [0, -px_per_mm, CARD_H * px_per_mm], [0, 0, 1]],
                     np.float64)


def place(scene: np.ndarray, centre_xy: tuple[float, float], px_per_mm: float,
          rotation_deg: float = 0.0, tilt: tuple[float, float] = (0.0, 0.0),
          raster_ppm: float = 12.0) -> tuple[np.ndarray, np.ndarray]:
    """장면에 카드를 붙인다. 돌려주는 H는 카드 mm 좌표 → 장면 픽셀.

    tilt: 원근 왜곡 정도(비스듬히 찍은 효과). 모서리 네 점을 흔들어 만든다.
    """
    card = render(raster_ppm)
    corners_mm = np.array([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]], np.float64)
    c = np.array(centre_xy, np.float64)
    th = np.radians(rotation_deg)
    rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    # 장면에서 y는 아래로 → 카드 y를 뒤집어 놓는다
    local = (corners_mm - [CARD_W / 2, CARD_H / 2]) * [1, -1] * px_per_mm
    dst = local @ rot.T + c
    tx, ty = tilt
    dst = dst + np.array([[-tx, -ty], [tx, -ty], [tx, ty], [-tx, ty]]) * px_per_mm * 4
    H = cv2.getPerspectiveTransform(corners_mm.astype(np.float32), dst.astype(np.float32))
    Hr = H @ np.linalg.inv(card_mm_to_raster(raster_ppm))
    h, w = scene.shape[:2]
    warped = cv2.warpPerspective(card, Hr, (w, h), flags=cv2.INTER_AREA)
    alpha = cv2.warpPerspective(np.ones(card.shape[:2], np.float32), Hr, (w, h),
                                flags=cv2.INTER_LINEAR)[..., None]
    return scene * (1 - alpha) + warped * alpha, H
