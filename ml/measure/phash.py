"""지각 해시 — web/src/lib/phash.ts와 같은 알고리즘(골든 테스트로 일치 확인).

서버는 해시를 계산하지 않는다(사진을 받지 않으므로). 이 파이썬 구현은 임계값을 정하기 위한
측정(ml/eval/phash_study.py)에만 쓴다.
"""

from __future__ import annotations

import numpy as np

N, K = 32, 8


def _dct_matrix() -> np.ndarray:
    k = np.arange(N)[:, None]
    n = np.arange(N)[None, :]
    m = np.cos(np.pi / N * (n + 0.5) * k)
    m[0] *= np.sqrt(1 / N)
    m[1:] *= np.sqrt(2 / N)
    return m


D = _dct_matrix()


def phash(lum: np.ndarray) -> str:
    """휘도(0~1, h×w) → 16자리 hex. 32×32 면적 평균 축소 → DCT 저주파 8×8 → DC 뺀 중앙값 기준."""
    h, w = lum.shape
    small = np.empty((N, N))
    for y in range(N):
        y0 = (y * h) // N
        y1 = max(y0 + 1, ((y + 1) * h) // N)
        for x in range(N):
            x0 = (x * w) // N
            x1 = max(x0 + 1, ((x + 1) * w) // N)
            small[y, x] = lum[y0:y1, x0:x1].mean()
    coef = (D[:K] @ small @ D[:K].T).ravel()
    med = np.sort(coef[1:])[(len(coef) - 1) // 2]
    bits = coef > med
    return "".join(f"{int(''.join('1' if b else '0' for b in bits[i:i + 4]), 2):x}" for i in range(0, 64, 4))


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")
