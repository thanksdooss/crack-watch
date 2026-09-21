"""사진 속 기준 카드 찾기 — 네 모서리 검은 사각형 → 원근 보정 → px/mm, 색 칸 읽기.

순서
1. 어두운 영역 중 '사각형이고, 속이 꽉 차 있고, 크기가 비슷한 것' 후보를 모은다.
2. 후보 4개 조합마다 카드 치수(중심 간격 77×43mm)로 호모그래피를 세우고,
   네 가지 방향(카드가 뒤집히거나 돌아간 경우)을 모두 시험한다.
3. 색 칸 밝기 순서(흰 > 회50 > 회18 > 검)가 맞는 방향·조합만 남긴다. 이 순서 검사가
   '벽의 다른 검은 네모를 카드로 착각'하는 것과 '카드를 거꾸로 읽는 것'을 동시에 막는다.
4. 균열 위치에서의 px/mm는 호모그래피의 국소 확대율로 구한다(카드와 균열이 같은 벽면에
   있다는 가정 — 이게 성립하지 않으면 환산이 틀린다. 사용자 안내에 넣는다).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import cv2
import numpy as np

from .card import FIDUCIAL_CENTERS_MM, FIDUCIAL_SIZE, SWATCH_MM, swatches

MAX_CANDIDATES = 14
BLOCK_DIVISORS = (12, 6, 3)  # 적응 임계 창 = 짧은 변 / 이 값
LUM_ORDER = ["white", "gray50", "gray18", "black"]


@dataclass
class CardDetection:
    H: np.ndarray  # 카드 mm → 이미지 px
    swatch_srgb: dict[str, np.ndarray]
    reproj_err_px: float  # 모서리 꼭짓점 오차 (한 변 길이 대비 비율)
    fiducial_px: np.ndarray  # (4,2)

    def px_per_mm_at(self, x: float, y: float) -> float:
        """이미지 점 (x,y)에서의 px/mm. 호모그래피 역변환의 국소 야코비안으로 구한다."""
        Hinv = np.linalg.inv(self.H)
        p = Hinv @ np.array([x, y, 1.0])
        mm = p[:2] / p[2]
        eps = 1.0
        pts = np.array([[mm[0], mm[1]], [mm[0] + eps, mm[1]], [mm[0], mm[1] + eps]], np.float64)
        img = cv2.perspectiveTransform(pts[None], self.H)[0]
        dx = np.linalg.norm(img[1] - img[0])
        dy = np.linalg.norm(img[2] - img[0])
        return float(np.sqrt(dx * dy))  # 두 방향 기하평균 (비스듬하면 방향마다 다르다)

    def px_per_mm_anisotropy(self, x: float, y: float) -> float:
        """방향별 배율 차이(%). 크면 비스듬히 찍었다는 뜻 — 폭 방향에 따라 오차가 커진다."""
        Hinv = np.linalg.inv(self.H)
        p = Hinv @ np.array([x, y, 1.0])
        mm = p[:2] / p[2]
        pts = np.array([[mm[0], mm[1]], [mm[0] + 1, mm[1]], [mm[0], mm[1] + 1]], np.float64)
        img = cv2.perspectiveTransform(pts[None], self.H)[0]
        dx, dy = np.linalg.norm(img[1] - img[0]), np.linalg.norm(img[2] - img[0])
        return float(abs(dx - dy) / max(dx, dy))


def _candidates(gray: np.ndarray) -> list[np.ndarray]:
    """검은 사각형 후보의 네 꼭짓점들.

    적응 임계(주변 평균보다 어두우면 1)의 창이 모서리 사각형보다 작으면, 사각형 속은
    '주변도 어두우니 어둡지 않다'로 판정돼 속 빈 테두리가 된다. 카드를 가까이 찍으면
    사각형이 커지므로 창 크기 하나로는 못 버틴다. 창을 여러 크기로 돌려 후보를 합친다.
    """
    g = (gray * 255).astype(np.uint8) if gray.dtype != np.uint8 else gray
    h, w = g.shape
    min_area = (min(h, w) * 0.008) ** 2
    out: list[np.ndarray] = []
    for div in BLOCK_DIVISORS:
        block = max(31, (min(h, w) // div) | 1)
        bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,
                                   block, 15)
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area or area > h * w * 0.05:
                continue
            approx = cv2.approxPolyDP(c, 0.06 * cv2.arcLength(c, True), True)
            if len(approx) != 4 or not cv2.isContourConvex(approx):
                continue
            (_, _), (rw, rh), _ = cv2.minAreaRect(approx)
            if min(rw, rh) / max(rw, rh) < 0.5:
                continue
            if area / cv2.contourArea(cv2.convexHull(c)) < 0.85:
                continue
            mask = np.zeros_like(g)
            cv2.drawContours(mask, [approx], -1, 255, -1)
            if cv2.mean(g, mask=mask)[0] > 90:  # 속이 어두워야 한다
                continue
            quad = approx.reshape(4, 2).astype(np.float32)
            c0, size = quad.mean(axis=0), np.sqrt(area)
            if any(np.linalg.norm(q.mean(axis=0) - c0) < 0.3 * size for q in out):
                continue  # 다른 창 크기에서 이미 찾은 것
            out.append(quad)
    return out


def _sample_swatches(img: np.ndarray, H: np.ndarray) -> dict[str, np.ndarray]:
    """각 색 칸의 가운데 60%를 읽어 평균낸다. 가장자리는 인쇄 번짐·흐림이 섞인다.

    전체 이미지 크기의 마스크를 만들면 조합마다 수백만 픽셀을 훑게 되므로, 칸을 감싸는
    작은 사각형만 잘라서 본다.
    """
    out = {}
    inset = SWATCH_MM * 0.2
    h, w = img.shape[:2]
    for s in swatches():
        quad_mm = np.array([[s.x_mm + inset, s.y_mm + inset],
                            [s.x_mm + SWATCH_MM - inset, s.y_mm + inset],
                            [s.x_mm + SWATCH_MM - inset, s.y_mm + SWATCH_MM - inset],
                            [s.x_mm + inset, s.y_mm + SWATCH_MM - inset]], np.float64)
        quad = cv2.perspectiveTransform(quad_mm[None], H)[0]
        x0, y0 = np.floor(quad.min(axis=0)).astype(int)
        x1, y1 = np.ceil(quad.max(axis=0)).astype(int) + 1
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h or (x1 - x0) * (y1 - y0) < 9:
            return {}
        mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillConvexPoly(mask, (quad - [x0, y0]).astype(np.int32), 1)
        if mask.sum() < 9:
            return {}
        roi = img[y0:y1, x0:x1][mask > 0]
        out[s.name] = roi.mean(axis=0)
    return out


def _centre_lum(gray: np.ndarray, H: np.ndarray, name: str) -> float:
    """색 칸 중심 3×3 픽셀 밝기 — 방향 판정용 싼 검사."""
    s = next(x for x in swatches() if x.name == name)
    c = cv2.perspectiveTransform(
        np.array([[[s.x_mm + SWATCH_MM / 2, s.y_mm + SWATCH_MM / 2]]], np.float64), H)[0][0]
    x, y = int(round(c[0])), int(round(c[1]))
    h, w = gray.shape
    if not (1 <= x < w - 1 and 1 <= y < h - 1):
        return -1.0
    return float(gray[y - 1:y + 2, x - 1:x + 2].mean())


def _corner_error(H: np.ndarray, quads: list[np.ndarray]) -> float:
    """예측한 모서리 사각형 4개의 꼭짓점 16개가 검출된 꼭짓점과 얼마나 맞는가(한 변 길이 대비).

    중심점 4개로 만든 원근 변환은 그 4점을 항상 정확히 지나므로 중심점 오차는 0이 되어
    아무것도 검증하지 못한다. 꼭짓점은 변환을 만들 때 쓰지 않았으므로 진짜 검증이 된다.
    크기가 다른 검정 색 칸(12mm)을 모서리 사각형(7mm)으로 착각하면 여기서 걸린다.
    """
    errs = []
    for (cx, cy), quad in zip(FIDUCIAL_CENTERS_MM, quads):
        hs = FIDUCIAL_SIZE / 2
        pred_mm = np.array([[cx - hs, cy - hs], [cx + hs, cy - hs], [cx + hs, cy + hs],
                            [cx - hs, cy + hs]], np.float64)
        pred = cv2.perspectiveTransform(pred_mm[None], H)[0]
        side = np.mean(np.linalg.norm(pred - np.roll(pred, 1, axis=0), axis=1))
        d = np.linalg.norm(pred[:, None, :] - quad[None, :, :], axis=2).min(axis=1)
        errs.append(d.mean() / max(side, 1e-6))
    return float(np.mean(errs))


def _lum(rgb: np.ndarray) -> float:
    return float(rgb @ np.array([0.2126, 0.7152, 0.0722]))


def detect(img: np.ndarray) -> CardDetection | None:
    """img: float RGB 0~1. 못 찾으면 None — 그 사진은 색·크기를 믿지 않는다."""
    gray = cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    gray_f = gray.astype(np.float32) / 255
    cands = _candidates(gray)
    if len(cands) < 4:
        return None
    areas = np.array([cv2.contourArea(c) for c in cands])
    order = np.argsort(-areas)[:MAX_CANDIDATES]
    cands = [cands[i] for i in order]
    centres = np.array([c.mean(axis=0) for c in cands])
    sizes = np.sqrt(areas[order])

    src_all = np.array(FIDUCIAL_CENTERS_MM, np.float64)  # BL, BR, TL, TR (mm, y 위)
    best: CardDetection | None = None
    for combo in itertools.combinations(range(len(cands)), 4):
        s = sizes[list(combo)]
        if s.max() / s.min() > 2.0:  # 네 사각형 크기는 비슷해야 한다
            continue
        idx = list(combo)
        pts = centres[idx]
        # 이미지에서 볼록 사각형 순서로 정렬 (중심 기준 각도)
        c0 = pts.mean(axis=0)
        order_ring = np.argsort(np.arctan2(pts[:, 1] - c0[1], pts[:, 0] - c0[0]))
        # 카드 쪽 볼록 순서: BL→BR→TR→TL (FIDUCIAL_CENTERS_MM 인덱스 0,1,3,2)
        card_idx = [0, 1, 3, 2]
        card_ring = src_all[card_idx]
        for k in range(4):
            for flip in (False, True):
                ring_idx = np.roll(order_ring, k)
                if flip:
                    ring_idx = ring_idx[::-1]
                dst = pts[ring_idx]
                H = cv2.getPerspectiveTransform(card_ring.astype(np.float32),
                                                dst.astype(np.float32))
                # 1차: 모서리 사각형 꼭짓점이 예측과 맞는가 (싸고 강력하다)
                quads_by_fid = [None] * 4
                for pos, fid in enumerate(card_idx):
                    quads_by_fid[fid] = cands[idx[ring_idx[pos]]]
                cerr = _corner_error(H, quads_by_fid)
                if cerr > 0.25:
                    continue
                # 2차: 색 칸 중심 밝기 순서 — 뒤집혀 읽는 것을 막는다
                lums = [_centre_lum(gray_f, H, n) for n in LUM_ORDER]
                if min(lums) < 0 or not all(a > b + 0.02 for a, b in zip(lums, lums[1:])):
                    continue
                if best is None or cerr < best.reproj_err_px:
                    best = CardDetection(H=H, swatch_srgb={}, reproj_err_px=cerr, fiducial_px=dst)
    if best is None:
        return None
    # 마지막: 이긴 후보 하나만 색 칸을 제대로 읽는다 (비싸다)
    best.swatch_srgb = _sample_swatches(img, best.H)
    if len(best.swatch_srgb) != len(swatches()):
        return None
    return best
