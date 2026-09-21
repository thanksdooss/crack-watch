"""마스크 → 한 픽셀 두께 중심선 (Zhang-Suen 세선화).

OpenCV 기본 배포(contrib 없음)에는 세선화가 없고, 웹에서도 같은 알고리즘을 TS로 옮겨야
하므로 단순한 고전 알고리즘을 직접 구현한다.

처음엔 매 반복마다 이미지 전체 배열을 계산해 768px 한 장에 2.5초가 걸렸다. 균열은
이미지의 1~3%뿐이라, 전경 픽셀의 인덱스만 들고 다니며 그 이웃만 보도록 바꿨다.
"""

from __future__ import annotations

import numpy as np


def thin(mask: np.ndarray, max_iter: int = 200) -> np.ndarray:
    h, w = mask.shape
    W = w + 2
    flat = np.zeros((h + 2) * W, np.uint8)
    flat.reshape(h + 2, W)[1:-1, 1:-1] = np.asarray(mask) > 0
    fg = np.flatnonzero(flat)
    # P2..P9: 위에서 시계방향
    offs = np.array([-W, -W + 1, 1, W + 1, W, W - 1, -1, -W - 1])

    for _ in range(max_iter):
        changed = False
        for step in (0, 1):
            if fg.size == 0:
                break
            n = flat[fg[:, None] + offs[None, :]].astype(np.int8)  # (k, 8)
            p2, p4, p6, p8 = n[:, 0], n[:, 2], n[:, 4], n[:, 6]
            b = n.sum(axis=1)
            a = ((n == 0) & (np.roll(n, -1, axis=1) == 1)).sum(axis=1)
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (b >= 2) & (b <= 6) & (a == 1) & c
            if rm.any():
                flat[fg[rm]] = 0
                fg = fg[~rm]
                changed = True
        if not changed:
            break
    return flat.reshape(h + 2, W)[1:-1, 1:-1].copy()
