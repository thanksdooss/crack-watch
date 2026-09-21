"""색 공간 변환과 색차(ΔE00).

왜 ΔE00인가: RGB 값의 차이는 사람이 느끼는 색 차이와 맞지 않는다. 같은 숫자 차이라도
어두운 색에서는 크게, 밝은 색에서는 작게 보인다. CIEDE2000은 그 불일치를 보정한
표준 색차 공식이고, 대략 ΔE00 ≈ 1이 "훈련된 눈이 겨우 구분하는 차이"다.

구현은 shared/fixtures/ciede2000_testdata.txt(Sharma 2005)로 검증한다.
"""

from __future__ import annotations

import numpy as np

# sRGB(IEC 61966-2-1) 원색 → XYZ, 백색점 D65
RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
XYZ_TO_RGB = np.linalg.inv(RGB_TO_XYZ)

D65 = np.array([0.95047, 1.00000, 1.08883])


def srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """0~1 sRGB → 선형 RGB. 보정 계산은 반드시 선형 공간에서 한다."""
    srgb = np.asarray(srgb, dtype=float)
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.clip(np.asarray(linear, dtype=float), 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


def linear_to_xyz(linear: np.ndarray) -> np.ndarray:
    return np.asarray(linear, dtype=float) @ RGB_TO_XYZ.T


def xyz_to_linear(xyz: np.ndarray) -> np.ndarray:
    return np.asarray(xyz, dtype=float) @ XYZ_TO_RGB.T


def xyz_to_lab(xyz: np.ndarray, white: np.ndarray = D65) -> np.ndarray:
    ratio = np.asarray(xyz, dtype=float) / white
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(ratio > eps, np.cbrt(ratio), (kappa * ratio + 16) / 116)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


def srgb_to_lab(srgb: np.ndarray) -> np.ndarray:
    return xyz_to_lab(linear_to_xyz(srgb_to_linear(srgb)))


def delta_e_2000(lab1: np.ndarray, lab2: np.ndarray, kl: float = 1.0, kc: float = 1.0,
                 kh: float = 1.0) -> np.ndarray:
    """CIEDE2000 색차. 입력은 (..., 3) 형태의 L*a*b*."""
    lab1 = np.atleast_2d(np.asarray(lab1, dtype=float))
    lab2 = np.atleast_2d(np.asarray(lab2, dtype=float))
    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]

    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - np.sqrt(c_bar**7 / (c_bar**7 + 25.0**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)

    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    h1p = np.where((a1p == 0) & (b1 == 0), 0.0, h1p)
    h2p = np.where((a2p == 0) & (b2 == 0), 0.0, h2p)

    dlp = l2 - l1
    dcp = c2p - c1p
    dh = h2p - h1p
    dhp = np.where(c1p * c2p == 0, 0.0,
                   np.where(np.abs(dh) <= 180, dh, np.where(dh > 180, dh - 360, dh + 360)))
    dhp_cap = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp) / 2)

    lbp = (l1 + l2) / 2
    cbp = (c1p + c2p) / 2
    h_sum, h_abs = h1p + h2p, np.abs(h1p - h2p)
    hbp = np.where(
        c1p * c2p == 0, h_sum,
        np.where(h_abs <= 180, h_sum / 2,
                 np.where(h_sum < 360, (h_sum + 360) / 2, (h_sum - 360) / 2)),
    )

    t = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    rc = 2 * np.sqrt(cbp**7 / (cbp**7 + 25.0**7))
    sl = 1 + (0.015 * (lbp - 50) ** 2) / np.sqrt(20 + (lbp - 50) ** 2)
    sc = 1 + 0.045 * cbp
    sh = 1 + 0.015 * cbp * t
    rt = -np.sin(np.radians(2 * dtheta)) * rc

    term_l = dlp / (kl * sl)
    term_c = dcp / (kc * sc)
    term_h = dhp_cap / (kh * sh)
    de = np.sqrt(term_l**2 + term_c**2 + term_h**2 + rt * term_c * term_h)
    return de if de.shape != (1,) else de[0]
