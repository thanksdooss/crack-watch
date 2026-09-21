// 균열 폭(픽셀) 측정 — ml/measure/width.py의 TS 이식.
// 중심선을 따라 일정 간격으로, 균열 방향에 수직인 밝기 단면을 떠서 폭을 잰다.
//  - fwhm: 어두운 골의 '절반 깊이 폭'
//  - area: '어두워진 넓이 ÷ 균열 속 깊이' (흐려져도 어두워진 총량은 보존된다)
// 마스크 두께로 재지 않는 이유는 docs/00-approach.md 2절(마스크는 검출기 임계에 끌려간다).
import pipeline from '@shared/pipeline.json'
import { gaussianKernel } from '../vision/core/filter'
import type { Gray, Mask } from '../vision/core/image'
import { reflect101 } from '../vision/core/image'
import { thin } from '../vision/core/thin'

const SWITCH_PX = pipeline.measure.hybridSwitchPx
const SMOOTH_FRAC = pipeline.measure.profileSmoothFrac

export interface WidthSample {
  x: number
  y: number
  fwhm: number
  area: number
  depth: number
  /** 채택한 값: 가늘면(반치폭 < 4px) area, 넓으면 fwhm */
  hybrid: number
}

/** cv2.remap BORDER_REFLECT(가장자리 복제 반사: ...1 0 | 0 1 2...) + 쌍선형 보간 */
function reflect(i: number, n: number): number {
  if (n === 1) return 0
  const period = 2 * n
  let k = ((i % period) + period) % period
  if (k >= n) k = period - 1 - k
  return k
}

export function bilinear(g: Gray, x: number, y: number): number {
  const x0 = Math.floor(x), y0 = Math.floor(y)
  const fx = x - x0, fy = y - y0
  const a = g.data[reflect(y0, g.h) * g.w + reflect(x0, g.w)]
  const b = g.data[reflect(y0, g.h) * g.w + reflect(x0 + 1, g.w)]
  const c = g.data[reflect(y0 + 1, g.h) * g.w + reflect(x0, g.w)]
  const d = g.data[reflect(y0 + 1, g.h) * g.w + reflect(x0 + 1, g.w)]
  return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
}

/** 주변 중심선 점들의 주성분 방향 (단위 벡터). 점이 모자라면 null. */
function direction(skel: Mask, x: number, y: number, radius = 5): [number, number] | null {
  const xs: number[] = [], ys: number[] = []
  for (let yy = Math.max(0, y - radius); yy <= Math.min(skel.h - 1, y + radius); yy++)
    for (let xx = Math.max(0, x - radius); xx <= Math.min(skel.w - 1, x + radius); xx++)
      if (skel.data[yy * skel.w + xx]) { xs.push(xx); ys.push(yy) }
  if (xs.length < 4) return null
  const mx = xs.reduce((a, b) => a + b, 0) / xs.length
  const my = ys.reduce((a, b) => a + b, 0) / ys.length
  let sxx = 0, syy = 0, sxy = 0
  for (let i = 0; i < xs.length; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my
    sxx += dx * dx; syy += dy * dy; sxy += dx * dy
  }
  // 2×2 대칭 행렬의 큰 고유값 방향
  const theta = 0.5 * Math.atan2(2 * sxy, sxx - syy)
  return [Math.cos(theta), Math.sin(theta)]
}

/** 중심점에서 단면 방향으로 마스크를 가로지른 길이(px) — ml/measure/width.py chord와 같다. */
export function chord(m: Mask, x: number, y: number, nx: number, ny: number, maxLen = 96): number {
  let total = 1
  for (const sgn of [1, -1]) {
    let k = 0
    while (k < maxLen) {
      const xx = Math.round(x + sgn * (k + 1) * nx)
      const yy = Math.round(y + sgn * (k + 1) * ny)
      if (xx < 0 || yy < 0 || xx >= m.w || yy >= m.h || !m.data[yy * m.w + xx]) break
      k++
    }
    total += k
  }
  return total
}

/** 1차원 가우시안 평활 — cv2.GaussianBlur(1행, sigmaX)와 같은 커널·경계 규칙. */
function smooth(v: Float32Array, sigma: number): Float32Array {
  if (sigma <= 0.5) return v
  const k = gaussianKernel(sigma)
  const r = (k.length - 1) / 2
  const out = new Float32Array(v.length)
  for (let i = 0; i < v.length; i++) {
    let s = 0
    for (let j = 0; j < k.length; j++) s += k[j] * v[reflect101(i + j - r, v.length)]
    out[i] = s
  }
  return out
}

function median(v: number[]): number {
  const s = [...v].sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function profileWidth(t: Float32Array, v: Float32Array, core: number) {
  const n = v.length
  const tail = Math.max(4, Math.floor(n / 6))
  const bg = median([...v.slice(0, tail), ...v.slice(n - tail)])
  let iMin = -1
  for (let i = 0; i < n; i++) if (Math.abs(t[i]) <= Math.max(core, 1) && (iMin < 0 || v[i] < v[iMin])) iMin = i
  const vmin = v[iMin]
  const depth = (bg - vmin) / Math.max(bg, 1e-6)
  if (depth <= 0.02) return null
  const half = (bg + vmin) / 2
  let left = iMin
  while (left > 0 && v[left] < half) left--
  let right = iMin
  while (right < n - 1 && v[right] < half) right++
  if (!(left > 0 && right < n - 1)) return null
  const cross = (i0: number, i1: number) => {
    const a = v[i0], b = v[i1]
    const f = a === b ? 0 : (half - a) / (b - a)
    return t[i0] + f * (t[i1] - t[i0])
  }
  const fwhm = cross(right - 1, right) - cross(left + 1, left)
  if (fwhm <= 0) return null
  const dt = t[1] - t[0]
  let dark = 0
  const win = Math.max(1.5 * fwhm, 2)
  for (let i = 0; i < n; i++) if (Math.abs(t[i] - t[iMin]) <= win) dark += Math.max(0, bg - v[i]) * dt
  return { fwhm, dark, depth, bg }
}

/** 중심선 위 stride 간격 표본. g는 평탄화된 밝기(배경≈1) 권장. */
export function measureWidths(g: Gray, m: Mask, halfWidthPx = pipeline.measure.profileHalfWidthPx, stride = 3): WidthSample[] {
  const skel = thin(m)
  const pts: [number, number][] = []
  for (let y = 0; y < skel.h; y++) for (let x = 0; x < skel.w; x++) if (skel.data[y * skel.w + x]) pts.push([x, y])
  const step = 0.25
  const grids = [halfWidthPx, halfWidthPx * 2, halfWidthPx * 4].map((half) => {
    const n = Math.round((2 * half) / step) + 1
    const t = new Float32Array(n)
    for (let i = 0; i < n; i++) t[i] = -half + i * step
    return { half, t, v: new Float32Array(n) }
  })
  const raw: { x: number; y: number; fwhm: number; dark: number; depth: number; bg: number }[] = []
  for (let i = 0; i < pts.length; i += stride) {
    const [x, y] = pts[i]
    const d = direction(skel, x, y)
    if (!d) continue
    const nx = -d[1], ny = d[0]
    // 넓은 균열은 ±12px 단면 밖으로 삐져나가 폭이 잘린다. 골 가장자리가 창 끝에 닿으면
    // 창을 두 배로 넓혀 다시 잰다(ml/measure/width.py와 같은 규칙).
    // 파이썬은 마스크 거리변환으로 '골을 찾을 범위'를 정한다. 여기선 그 값 대신 단면 중앙 4px
    // 안에서 찾는다(정답 마스크 기준 두 방식의 차이는 골든 테스트로 확인).
    const L = chord(m, x, y, nx, ny)
    const core = Math.max(1.5, 0.5 * L)
    let r: { fwhm: number; dark: number; depth: number; bg: number } | null = null
    for (const gr of grids) {
      for (let k = 0; k < gr.t.length; k++) gr.v[k] = bilinear(g, x + gr.t[k] * nx, y + gr.t[k] * ny)
      // 반치폭은 균열 폭의 10%만큼 평활한 단면에서(바닥의 기공에 끌려가지 않게), 넓이는 원본 단면에서
      const sm = profileWidth(gr.t, smooth(gr.v, (SMOOTH_FRAC * L) / step), core)
      const rawP = profileWidth(gr.t, gr.v, core)
      r = sm ? { fwhm: sm.fwhm, depth: sm.depth, bg: sm.bg, dark: rawP ? rawP.dark : 0 } : null
      if (r && r.fwhm < 0.8 * gr.half) break
    }
    if (r) raw.push({ x, y, ...r })
  }
  if (!raw.length) return []
  const fws = raw.map((r) => r.fwhm).sort((a, b) => a - b)
  const p70 = fws[Math.floor(0.7 * (fws.length - 1))]
  const trueDepth = median(raw.filter((r) => r.fwhm >= p70).map((r) => r.depth))
  return raw.map((r) => {
    const area = r.dark / Math.max(trueDepth * r.bg, 1e-6)
    return { x: r.x, y: r.y, fwhm: r.fwhm, area, depth: r.depth, hybrid: r.fwhm < SWITCH_PX ? area : r.fwhm }
  })
}
