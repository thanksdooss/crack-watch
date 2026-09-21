// 고전 CV 균열 검출 — ml/baseline/classic.py의 TS 이식. 파라미터는 shared/pipeline.json "classic".
// 단계와 이유는 파이썬 쪽 주석과 docs/00-approach.md 참고.
import pipeline from '@shared/pipeline.json'
import { connectedComponents } from '../core/components'
import { gaussianBlur, sobel } from '../core/filter'
import type { Pt } from '../core/geometry'
import { minAreaRectSides } from '../core/geometry'
import { type Gray, type Mask, gray, mask } from '../core/image'

export interface ClassicParams {
  flattenSigma: number
  scales: number[]
  beta: number
  c: number
  hystHigh: number
  hystLow: number
  minLengthPx: number
  minElongation: number
}

export const defaultParams = (): ClassicParams => {
  const c = pipeline.classic
  return {
    flattenSigma: c.flattenSigma, scales: [...c.scales], beta: c.beta, c: c.c,
    hystHigh: c.hystHigh, hystLow: c.hystLow, minLengthPx: c.minLengthPx, minElongation: c.minElongation,
  }
}

/** 배경 밝기로 나눠 그림자를 지운다. 결과는 배경 ≈ 1. */
export function flatten(g: Gray, sigma: number): Gray {
  const bg = gaussianBlur(g, sigma)
  const out = gray(g.w, g.h)
  for (let i = 0; i < out.data.length; i++) out.data[i] = g.data[i] / Math.max(bg.data[i], 1e-3)
  return out
}

/** 어두운 능선(Frangi). 0~1. */
export function ridgeResponse(flat: Gray, p: ClassicParams): Gray {
  const out = gray(flat.w, flat.h)
  for (const s of p.scales) {
    const g = gaussianBlur(flat, s)
    const dxx = sobel(g, 2, 0).data
    const dyy = sobel(g, 0, 2).data
    const dxy = sobel(g, 1, 1).data
    const s2 = s * s
    for (let i = 0; i < out.data.length; i++) {
      const xx = dxx[i] * s2
      const yy = dyy[i] * s2
      const xy = dxy[i] * s2
      const tmp = Math.sqrt((xx - yy) ** 2 + 4 * xy * xy)
      const l1 = 0.5 * (xx + yy + tmp)
      const l2 = 0.5 * (xx + yy - tmp)
      const swap = Math.abs(l1) < Math.abs(l2)
      const la = swap ? l1 : l2
      const lb = swap ? l2 : l1
      if (lb <= 0) continue // 밝은 선은 균열이 아니다
      const rb = la / (lb + 1e-9)
      const ss = la * la + lb * lb
      const v = Math.exp(-(rb * rb) / (2 * p.beta * p.beta)) * (1 - Math.exp(-ss / (2 * p.c * p.c)))
      if (v > out.data[i]) out.data[i] = v
    }
  }
  return out
}

export function hysteresis(resp: Gray, low: number, high: number): Mask {
  const weak = mask(resp.w, resp.h)
  for (let i = 0; i < weak.data.length; i++) weak.data[i] = resp.data[i] >= low ? 1 : 0
  const cc = connectedComponents(weak)
  const keep = new Uint8Array(cc.n)
  for (let i = 0; i < resp.data.length; i++) if (resp.data[i] >= high && cc.labels[i]) keep[cc.labels[i]] = 1
  const out = mask(resp.w, resp.h)
  for (let i = 0; i < out.data.length; i++) out.data[i] = keep[cc.labels[i]]
  return out
}

/** 짧은 조각과 뭉툭한 덩어리를 버린다. 길이 = 회전 사각형 긴 변, 가늘기 = 길이²/면적. */
export function shapeFilter(m: Mask, minLength: number, minElongation: number): Mask {
  const cc = connectedComponents(m)
  const keep = new Uint8Array(cc.n)
  const pts: Pt[][] = Array.from({ length: cc.n }, () => [])
  const cand = new Uint8Array(cc.n)
  for (let l = 1; l < cc.n; l++) {
    const diag = Math.hypot(cc.x1[l] - cc.x0[l] + 1, cc.y1[l] - cc.y0[l] + 1)
    if (diag >= minLength && cc.area[l] >= 4) cand[l] = 1
  }
  for (let i = 0; i < cc.labels.length; i++) {
    const l = cc.labels[i]
    if (l && cand[l]) pts[l].push([i % m.w, Math.floor(i / m.w)])
  }
  for (let l = 1; l < cc.n; l++) {
    if (!cand[l]) continue
    const [len] = minAreaRectSides(pts[l])
    if (len >= minLength && (len * len) / cc.area[l] >= minElongation) keep[l] = 1
  }
  const out = mask(m.w, m.h)
  for (let i = 0; i < out.data.length; i++) out.data[i] = keep[cc.labels[i]]
  return out
}

export function detectClassic(g: Gray, p: ClassicParams = defaultParams()): { mask: Mask; response: Gray } {
  const flat = flatten(g, p.flattenSigma)
  const response = ridgeResponse(flat, p)
  const m = shapeFilter(hysteresis(response, p.hystLow, p.hystHigh), p.minLengthPx, p.minElongation)
  return { mask: m, response }
}
