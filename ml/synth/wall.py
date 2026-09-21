"""합성 벽면 + 균열 생성기.

왜 합성 데이터가 필요한가: 공개 데이터셋에는 균열 위치(마스크)는 있어도
**실제 폭(mm)이 없다.** 폭 추정 오차를 재려면 정답 폭을 알아야 하는데, 그걸 아는 방법은
(1) 실제 벽을 캘리퍼스로 재거나 (2) 폭을 정해 놓고 그리는 것뿐이다. 이 모듈은 (2)다.

또 하나: 고전 영상처리가 무엇에 속는지 조절하며 시험할 수 있다. 거푸집 자국, 줄눈,
얼룩, 그림자 같은 '균열처럼 생긴 가짜'를 넣고 뺄 수 있다.

합성은 실제의 대체물이 아니다. 여기서 나온 숫자는 항상 '합성'으로 표기한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class WallSpec:
    size_px: tuple[int, int] = (768, 768)  # (h, w)
    px_per_mm: float = 8.0  # 1mm = 8px → 0.3mm 균열이 2.4px
    base_gray: float = 0.62
    texture: float = 0.06  # 표면 거칠기 대비
    pores: int = 350  # 기공(작은 검은 점)
    stains: int = 3  # 빗물 자국 (세로로 긴 어두운 띠 — 균열과 헷갈린다)
    form_lines: int = 2  # 거푸집 이음 자국 (곧은 직선 — 균열과 헷갈린다)
    shadow: float = 0.25  # 비스듬한 조명 그라데이션 세기
    blur_sigma: float = 0.7  # 렌즈·초점 흐림


@dataclass
class CrackSpec:
    width_mm: float = 0.8  # 평균 폭
    width_jitter: float = 0.35  # 폭 변동 비율
    length_frac: float = 0.8  # 이미지 대각 대비 길이
    branches: int = 1
    tortuosity: float = 0.35  # 꼬불거림
    depth: float = 0.55  # 안쪽이 얼마나 어두운가


@dataclass
class Sample:
    image: np.ndarray  # float32 (h, w, 3) 0~1 sRGB
    mask: np.ndarray  # uint8 (h, w) 0/1 — 폭 정의상 균열 안쪽
    centerline: list[np.ndarray] = field(default_factory=list)  # 각 가지의 (n, 2) xy
    widths_mm: list[np.ndarray] = field(default_factory=list)  # 중심선 점마다 정답 폭
    px_per_mm: float = 8.0


def _fbm(rng: np.random.Generator, h: int, w: int, octaves: int = 5) -> np.ndarray:
    """여러 크기의 잡음을 겹쳐 콘크리트 표면 얼룩을 만든다."""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = 2 ** (o + 2)
        small = rng.standard_normal((max(2, h // s), max(2, w // s))).astype(np.float32)
        out += amp * cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
        total += amp
        amp *= 0.55
    out /= total
    return out / (np.abs(out).max() + 1e-6)


def _crack_path(rng: np.random.Generator, h: int, w: int, spec: CrackSpec,
                start: np.ndarray | None = None, heading: float | None = None,
                length_px: float | None = None) -> np.ndarray:
    """꼬불거리되 원래 진행 방향으로 되돌아오는 경로.

    처음에는 방향 변화를 누적시켰더니 균열이 C자로 말려 들어갔다. 실제 균열은 응력
    방향을 따라 대체로 한 방향으로 간다. 그래서 방향 편차가 평균으로 되돌아오게 했다.
    """
    diag = float(np.hypot(h, w))
    length_px = length_px or spec.length_frac * diag
    step = 2.0
    n = int(length_px / step)
    if start is None:
        start = np.array([rng.uniform(0.2, 0.8) * w, rng.uniform(0.02, 0.12) * h])
    theta0 = heading if heading is not None else rng.uniform(np.pi * 0.35, np.pi * 0.65)
    pts = [start.astype(float)]
    dev = 0.0
    for _ in range(n):
        dev = 0.93 * dev + rng.normal(0, spec.tortuosity * 0.12)
        theta = theta0 + float(np.clip(dev, -0.9, 0.9))
        nxt = pts[-1] + step * np.array([np.cos(theta), np.sin(theta)])
        if not (2 <= nxt[0] < w - 2 and 2 <= nxt[1] < h - 2):
            break
        pts.append(nxt)
    return np.array(pts)


def _smooth_widths(rng: np.random.Generator, n: int, spec: CrackSpec) -> np.ndarray:
    """폭은 점마다 튀지 않고 천천히 변한다. 끝으로 갈수록 가늘어진다."""
    raw = rng.standard_normal(max(n // 20, 2))
    wave = cv2.resize(raw.reshape(1, -1).astype(np.float32), (n, 1),
                      interpolation=cv2.INTER_CUBIC).ravel()
    widths = spec.width_mm * (1 + spec.width_jitter * np.tanh(wave))
    taper = np.minimum(1.0, np.minimum(np.arange(n), np.arange(n)[::-1]) / max(n * 0.08, 1))
    return np.clip(widths * (0.35 + 0.65 * taper), 0.08, None)


def _draw_crack(depth_map: np.ndarray, mask: np.ndarray, pts: np.ndarray,
                widths_mm: np.ndarray, px_per_mm: float, depth: float, ss: int) -> None:
    """ss배 확대 캔버스에 그린다 — 1~2px짜리 가는 균열의 경계를 서브픽셀로 표현하려고."""
    for i in range(len(pts) - 1):
        wpx = widths_mm[i] * px_per_mm * ss
        p1 = tuple(int(v) for v in pts[i] * ss)
        p2 = tuple(int(v) for v in pts[i + 1] * ss)
        th = max(1, int(round(wpx)))
        cv2.line(depth_map, p1, p2, float(depth), th, lineType=cv2.LINE_8)
        cv2.line(mask, p1, p2, 1, th, lineType=cv2.LINE_8)


def generate(rng: np.random.Generator, wall: WallSpec | None = None,
             cracks: list[CrackSpec] | None = None) -> Sample:
    wall = wall or WallSpec()
    cracks = cracks if cracks is not None else [CrackSpec()]
    h, w = wall.size_px
    ss = 4  # 슈퍼샘플링 배율

    tex = _fbm(rng, h, w)
    fine = rng.standard_normal((h, w)).astype(np.float32) * 0.35
    gray = wall.base_gray + wall.texture * (tex + fine)

    for _ in range(wall.pores):
        c = (int(rng.uniform(0, w)), int(rng.uniform(0, h)))
        cv2.circle(gray, c, int(rng.integers(1, 4)), float(wall.base_gray * 0.55), -1)

    distract = np.zeros((h, w), np.float32)
    for _ in range(wall.stains):
        x = int(rng.uniform(0.1, 0.9) * w)
        y0 = int(rng.uniform(0, 0.4) * h)
        cv2.line(distract, (x, y0), (x + int(rng.normal(0, 8)), y0 + int(rng.uniform(0.3, 0.6) * h)),
                 0.09, int(rng.integers(6, 18)))
    for _ in range(wall.form_lines):
        if rng.random() < 0.5:
            y = int(rng.uniform(0.1, 0.9) * h)
            cv2.line(distract, (0, y), (w, y + int(rng.normal(0, 3))), 0.12, 2)
        else:
            x = int(rng.uniform(0.1, 0.9) * w)
            cv2.line(distract, (x, 0), (x + int(rng.normal(0, 3)), h), 0.12, 2)
    distract = cv2.GaussianBlur(distract, (0, 0), 2.5)
    gray -= distract

    depth_hi = np.zeros((h * ss, w * ss), np.float32)
    mask_hi = np.zeros((h * ss, w * ss), np.uint8)
    centerlines, widths = [], []
    for spec in cracks:
        main = _crack_path(rng, h, w, spec)
        wmm = _smooth_widths(rng, len(main), spec)
        _draw_crack(depth_hi, mask_hi, main, wmm, wall.px_per_mm, spec.depth, ss)
        centerlines.append(main)
        widths.append(wmm)
        for _ in range(spec.branches):
            if len(main) < 20:
                break
            k = int(rng.integers(len(main) // 4, 3 * len(main) // 4))
            branch_spec = CrackSpec(width_mm=spec.width_mm * 0.5, width_jitter=spec.width_jitter,
                                    tortuosity=spec.tortuosity, depth=spec.depth * 0.9)
            d = main[min(k + 1, len(main) - 1)] - main[k]
            heading = float(np.arctan2(d[1], d[0]) + rng.choice([-1, 1]) * rng.uniform(0.5, 1.0))
            br = _crack_path(rng, h, w, branch_spec, start=main[k], heading=heading,
                             length_px=len(main) * 2.0 * rng.uniform(0.2, 0.4))
            if len(br) < 5:
                continue
            bw = _smooth_widths(rng, len(br), branch_spec)
            _draw_crack(depth_hi, mask_hi, br, bw, wall.px_per_mm, branch_spec.depth, ss)
            centerlines.append(br)
            widths.append(bw)

    depth = cv2.resize(depth_hi, (w, h), interpolation=cv2.INTER_AREA)
    mask = (cv2.resize(mask_hi.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) >= 0.5)
    # 균열 안은 어둡지만 바닥까지 새까맣지는 않다. 가장자리는 부서져 약간 흐리다.
    gray = gray * (1 - depth)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = rng.uniform(0, 2 * np.pi)
    ramp = (np.cos(ang) * xx / w + np.sin(ang) * yy / h)
    gray *= 1 - wall.shadow * (ramp - ramp.min()) / (np.ptp(ramp) + 1e-6)

    gray = cv2.GaussianBlur(gray, (0, 0), wall.blur_sigma)
    tint = np.array([1.0, 0.99, 0.95], np.float32) * rng.uniform(0.97, 1.03, 3).astype(np.float32)
    img = np.clip(gray[..., None] * tint, 0, 1).astype(np.float32)
    return Sample(image=img, mask=mask.astype(np.uint8), centerline=centerlines,
                  widths_mm=widths, px_per_mm=wall.px_per_mm)
