// 색 보정 — ml/color/difference.py, ml/color/calibrate.py의 TS 이식.
// 계수는 무채색(흰·회색·검정) 칸에서만 구하고, 빨강·파랑은 검증에만 쓴다(docs/color-calibration.md).
import pipeline from '@shared/pipeline.json'

export type RGB = [number, number, number]

const M = [
  [0.4124564, 0.3575761, 0.1804375],
  [0.2126729, 0.7151522, 0.072175],
  [0.0193339, 0.119192, 0.9503041],
]
const D65: RGB = [0.95047, 1.0, 1.08883]

export const srgbToLinear = (v: number) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
export const linearToSrgb = (v: number) => {
  const c = Math.min(1, Math.max(0, v))
  return c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055
}

export function srgbToLab(rgb: RGB): RGB {
  const lin = rgb.map(srgbToLinear)
  const xyz = M.map((row) => row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2])
  const eps = 216 / 24389, kappa = 24389 / 27
  const f = xyz.map((v, i) => {
    const r = v / D65[i]
    return r > eps ? Math.cbrt(r) : (kappa * r + 16) / 116
  })
  return [116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])]
}

const rad = (d: number) => (d * Math.PI) / 180
const deg = (r: number) => (r * 180) / Math.PI

/** CIEDE2000. Sharma(2005) 34쌍으로 검증(shared/fixtures/ciede2000_testdata.txt). */
export function deltaE2000(lab1: RGB, lab2: RGB): number {
  const [L1, a1, b1] = lab1
  const [L2, a2, b2] = lab2
  const C1 = Math.hypot(a1, b1), C2 = Math.hypot(a2, b2)
  const Cb = (C1 + C2) / 2
  const G = 0.5 * (1 - Math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
  const a1p = (1 + G) * a1, a2p = (1 + G) * a2
  const C1p = Math.hypot(a1p, b1), C2p = Math.hypot(a2p, b2)
  const h1p = a1p === 0 && b1 === 0 ? 0 : (deg(Math.atan2(b1, a1p)) + 360) % 360
  const h2p = a2p === 0 && b2 === 0 ? 0 : (deg(Math.atan2(b2, a2p)) + 360) % 360
  const dLp = L2 - L1
  const dCp = C2p - C1p
  let dhp = 0
  if (C1p * C2p !== 0) {
    const dh = h2p - h1p
    dhp = Math.abs(dh) <= 180 ? dh : dh > 180 ? dh - 360 : dh + 360
  }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(rad(dhp) / 2)
  const Lbp = (L1 + L2) / 2
  const Cbp = (C1p + C2p) / 2
  let hbp = h1p + h2p
  if (C1p * C2p !== 0) {
    if (Math.abs(h1p - h2p) <= 180) hbp = (h1p + h2p) / 2
    else hbp = h1p + h2p < 360 ? (h1p + h2p + 360) / 2 : (h1p + h2p - 360) / 2
  }
  const T = 1 - 0.17 * Math.cos(rad(hbp - 30)) + 0.24 * Math.cos(rad(2 * hbp)) +
    0.32 * Math.cos(rad(3 * hbp + 6)) - 0.2 * Math.cos(rad(4 * hbp - 63))
  const dTheta = 30 * Math.exp(-(((hbp - 275) / 25) ** 2))
  const Rc = 2 * Math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
  const Sl = 1 + (0.015 * (Lbp - 50) ** 2) / Math.sqrt(20 + (Lbp - 50) ** 2)
  const Sc = 1 + 0.045 * Cbp
  const Sh = 1 + 0.015 * Cbp * T
  const Rt = -Math.sin(rad(2 * dTheta)) * Rc
  const tl = dLp / Sl, tc = dCp / Sc, th = dHp / Sh
  return Math.sqrt(tl * tl + tc * tc + th * th + Rt * tc * th)
}

export interface Correction {
  gain: RGB
  offset: RGB
  residualDeltaE: number
  quality: 'good' | 'fair' | 'poor'
}

/**
 * 관측된 칸 색(0~1 sRGB)과 목표 색으로 채널별 `관측 = 이득 × 실제 + 오프셋`을 무채색 칸에서만 푼다.
 */
export function fitCorrection(observed: Record<string, RGB>, targets: Record<string, RGB>, neutrals: Set<string>): Correction {
  const names = Object.keys(observed).filter((n) => neutrals.has(n) && targets[n])
  if (names.length < 2) throw new Error('무채색 칸이 2개 이상 있어야 이득과 오프셋을 나눌 수 있다')
  const gain: RGB = [1, 1, 1]
  const offset: RGB = [0, 0, 0]
  for (let c = 0; c < 3; c++) {
    const xs = names.map((n) => srgbToLinear(targets[n][c]))
    const ys = names.map((n) => srgbToLinear(observed[n][c]))
    const n = xs.length
    const mx = xs.reduce((a, b) => a + b, 0) / n
    const my = ys.reduce((a, b) => a + b, 0) / n
    let sxy = 0, sxx = 0
    for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2 }
    gain[c] = Math.max(sxy / sxx, 1e-4)
    offset[c] = my - gain[c] * mx
  }
  const corr = { gain, offset } as Correction
  const residual = names.reduce((s, n) => s + deltaE2000(srgbToLab(applyToColor(corr, observed[n])), srgbToLab(targets[n])), 0) / names.length
  const th = pipeline.calibration.deltaEThreshold
  return { gain, offset, residualDeltaE: residual, quality: residual <= th.good ? 'good' : residual <= th.fair ? 'fair' : 'poor' }
}

export function applyToColor(c: Pick<Correction, 'gain' | 'offset'>, rgb: RGB): RGB {
  return rgb.map((v, i) => linearToSrgb((srgbToLinear(v) - c.offset[i]) / c.gain[i])) as RGB
}

/** 이미지 전체(RGB 0~255)에 보정 적용. 256단계 조회표로 픽셀마다 거듭제곱 계산을 피한다. */
export function applyToImage(c: Pick<Correction, 'gain' | 'offset'>, rgb: Uint8Array | Uint8ClampedArray): Uint8ClampedArray {
  const lut = [0, 1, 2].map((ch) => {
    const t = new Uint8ClampedArray(256)
    for (let v = 0; v < 256; v++) t[v] = Math.round(linearToSrgb((srgbToLinear(v / 255) - c.offset[ch]) / c.gain[ch]) * 255)
    return t
  })
  const out = new Uint8ClampedArray(rgb.length)
  for (let i = 0; i < rgb.length; i += 3) {
    out[i] = lut[0][rgb[i]]
    out[i + 1] = lut[1][rgb[i + 1]]
    out[i + 2] = lut[2][rgb[i + 2]]
  }
  return out
}
