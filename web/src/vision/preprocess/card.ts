// 사진 속 기준 카드 찾기 — ml/color/detect_card.py와 같은 전략, 다른 구현.
// 파이썬은 OpenCV 윤곽선 추적(findContours)을 쓰지만, 웹은 OpenCV.js(약 10MB)를 싣지 않으려고
// 연결 요소 + 볼록 껍질로 사각형 후보를 만든다. 그래서 픽셀 단위 일치 대신 결과(px/mm)로 검증한다.
//
// 1. 어둡고, 사각형이고, 속이 찬 덩어리를 후보로 모은다.
// 2. 후보 4개 조합 × 방향 8가지마다 카드 치수로 원근 변환을 세운다.
// 3. 변환을 만들 때 쓰지 않은 정보(모서리 사각형 꼭짓점 16개)로 검증한다.
// 4. 색 칸 밝기 순서(흰 > 회50 > 회18 > 검)로 뒤집혀 읽는 것을 막는다.
import pipeline from '@shared/pipeline.json'
import { connectedComponents } from '../core/components'
import { type Pt, applyH, convexHull, homography, minAreaRectSides } from '../core/geometry'
import { type Mask, mask } from '../core/image'

const CARD = pipeline.calibration.card
const PATCH = pipeline.calibration.patch
const MAX_CANDIDATES = 14
/** 적응 임계 창 = 짧은 변 / 이 값. 창이 모서리 사각형보다 작으면 속 빈 테두리가 되므로 여러 크기로 돈다. */
const BLOCK_DIVISORS = [12, 6, 3]
const LUM_ORDER = ['white', 'gray50', 'gray18', 'black']

export interface RGBImage {
  w: number
  h: number
  /** RGB 0~255, 길이 w*h*3 */
  data: Uint8Array | Uint8ClampedArray
}

export interface Swatch {
  name: string
  xMm: number
  yMm: number
  targetSrgb: [number, number, number]
  neutral: boolean
}

export const NEUTRALS = new Set(['white', 'gray50', 'black', 'gray18'])

export function swatches(): Swatch[] {
  const cols = PATCH.cols
  const rows = PATCH.rows
  return PATCH.swatches.map((name, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    const t = (PATCH.targetSrgb as Record<string, number[]>)[name]
    return {
      name,
      xMm: CARD.gridX0 + col * (CARD.swatchMm + CARD.swatchGap),
      yMm: CARD.gridY0 + (rows - 1 - row) * (CARD.swatchMm + CARD.swatchGap),
      targetSrgb: [t[0] / 255, t[1] / 255, t[2] / 255],
      neutral: NEUTRALS.has(name),
    }
  })
}

/** 네 모서리 사각형 중심(mm): BL, BR, TL, TR */
export function fiducialCentersMm(): Pt[] {
  const m = CARD.fiducialMargin + CARD.fiducialSize / 2
  return [[m, m], [CARD.w - m, m], [m, CARD.h - m], [CARD.w - m, CARD.h - m]]
}

export interface CardDetection {
  /** 카드 mm → 이미지 px, 3×3 행 우선 */
  H: number[]
  swatchSrgb: Record<string, [number, number, number]>
  /** 모서리 꼭짓점 오차 (한 변 길이 대비 비율) */
  cornerErr: number
}

/** 이미지 점에서의 px/mm (두 방향 기하평균)와 방향별 배율 차이 비율. */
export function localScale(H: number[], x: number, y: number): { pxPerMm: number; anisotropy: number } {
  const Hinv = invert3(H)
  const mm = applyH(Hinv, [x, y])
  const o = applyH(H, mm)
  const ex = applyH(H, [mm[0] + 1, mm[1]])
  const ey = applyH(H, [mm[0], mm[1] + 1])
  const dx = Math.hypot(ex[0] - o[0], ex[1] - o[1])
  const dy = Math.hypot(ey[0] - o[0], ey[1] - o[1])
  return { pxPerMm: Math.sqrt(dx * dy), anisotropy: Math.abs(dx - dy) / Math.max(dx, dy) }
}

export function invert3(m: number[]): number[] {
  const [a, b, c, d, e, f, g, h, i] = m
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g
  const det = a * A + b * B + c * C
  return [A, -(b * i - c * h), b * f - c * e, B, a * i - c * g, -(a * f - c * d), C, -(a * h - b * g), a * e - b * d]
    .map((v) => v / det)
}

function toGray255(img: RGBImage): Float32Array {
  const g = new Float32Array(img.w * img.h)
  for (let i = 0, j = 0; i < g.length; i++, j += 3) {
    // cv2.COLOR_RGB2GRAY 계수
    g[i] = 0.299 * img.data[j] + 0.587 * img.data[j + 1] + 0.114 * img.data[j + 2]
  }
  return g
}

/** cv2.adaptiveThreshold(MEAN_C, BINARY_INV) 대응: 주변 평균보다 C 이상 어두우면 1. 적분 영상으로 O(1). */
function adaptiveDark(g: Float32Array, w: number, h: number, block: number, C: number): Mask {
  const W = w + 1
  const S = new Float64Array(W * (h + 1))
  for (let y = 0; y < h; y++) {
    let row = 0
    for (let x = 0; x < w; x++) {
      row += g[y * w + x]
      S[(y + 1) * W + x + 1] = S[y * W + x + 1] + row
    }
  }
  const r = (block - 1) / 2
  const out = mask(w, h)
  for (let y = 0; y < h; y++) {
    const y0 = Math.max(0, y - r), y1 = Math.min(h - 1, y + r)
    for (let x = 0; x < w; x++) {
      const x0 = Math.max(0, x - r), x1 = Math.min(w - 1, x + r)
      const sum = S[(y1 + 1) * W + x1 + 1] - S[y0 * W + x1 + 1] - S[(y1 + 1) * W + x0] + S[y0 * W + x0]
      const mean = sum / ((y1 - y0 + 1) * (x1 - x0 + 1))
      out.data[y * w + x] = g[y * w + x] < mean - C ? 1 : 0
    }
  }
  return out
}

function open3(m: Mask): Mask {
  const erode = mask(m.w, m.h)
  const { w, h } = m
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      let all = 1
      for (let dy = -1; dy <= 1 && all; dy++) for (let dx = -1; dx <= 1; dx++) if (!m.data[(y + dy) * w + x + dx]) { all = 0; break }
      erode.data[y * w + x] = all
    }
  }
  const out = mask(w, h)
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      if (!erode.data[y * w + x]) continue
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) out.data[(y + dy) * w + x + dx] = 1
    }
  }
  return out
}

function polygonArea(p: Pt[]): number {
  let s = 0
  for (let i = 0; i < p.length; i++) {
    const a = p[i], b = p[(i + 1) % p.length]
    s += a[0] * b[1] - b[0] * a[1]
  }
  return Math.abs(s) / 2
}

/** 볼록 다각형에서 넓이가 가장 큰 사각형의 네 꼭짓점. 껍질 점이 적어(수십 개) 전수 탐색으로 충분하다. */
function bestQuad(hull: Pt[]): Pt[] | null {
  const n = hull.length
  if (n < 4) return null
  const step = Math.max(1, Math.floor(n / 24)) // 점이 많으면 솎아서 본다
  const idx = Array.from({ length: Math.ceil(n / step) }, (_, k) => k * step)
  let best = -1
  let quad: Pt[] | null = null
  for (let a = 0; a < idx.length; a++)
    for (let b = a + 1; b < idx.length; b++)
      for (let c = b + 1; c < idx.length; c++)
        for (let d = c + 1; d < idx.length; d++) {
          const q = [hull[idx[a]], hull[idx[b]], hull[idx[c]], hull[idx[d]]]
          const ar = polygonArea(q)
          if (ar > best) { best = ar; quad = q }
        }
  return quad
}

interface Candidate { quad: Pt[]; centre: Pt; size: number }

function candidates(g: Float32Array, w: number, h: number): Candidate[] {
  const out: Candidate[] = []
  const minArea = (Math.min(h, w) * 0.008) ** 2
  for (const div of BLOCK_DIVISORS) {
    const block = Math.max(31, Math.floor(Math.min(h, w) / div) | 1)
    const bw = open3(adaptiveDark(g, w, h, block, 15))
    const cc = connectedComponents(bw)
    const pts: Pt[][] = Array.from({ length: cc.n }, () => [])
    const sums = new Float64Array(cc.n)
    for (let i = 0; i < cc.labels.length; i++) {
      const l = cc.labels[i]
      if (!l || cc.area[l] < minArea || cc.area[l] > w * h * 0.05) continue
      pts[l].push([i % w, Math.floor(i / w)])
      sums[l] += g[i]
    }
    for (let l = 1; l < cc.n; l++) {
      if (pts[l].length === 0) continue
      if (sums[l] / pts[l].length > 90) continue // 속이 어두워야 한다
      const hull = convexHull(pts[l])
      const hullArea = polygonArea(hull)
      if (hullArea <= 0 || cc.area[l] / hullArea < 0.85) continue // 속이 꽉 차야 한다
      const [long, short] = minAreaRectSides(hull)
      if (long === 0 || short / long < 0.5) continue
      const quad = bestQuad(hull)
      if (!quad || polygonArea(quad) < 0.85 * hullArea) continue // 사각형이 아니면 버린다
      const centre: Pt = [quad.reduce((s, p) => s + p[0], 0) / 4, quad.reduce((s, p) => s + p[1], 0) / 4]
      const size = Math.sqrt(cc.area[l])
      if (out.some((o) => Math.hypot(o.centre[0] - centre[0], o.centre[1] - centre[1]) < 0.3 * size)) continue
      out.push({ quad, centre, size })
    }
  }
  return out.sort((a, b) => b.size - a.size).slice(0, MAX_CANDIDATES)
}

function cornerError(H: number[], quads: Pt[][]): number {
  const hs = CARD.fiducialSize / 2
  let total = 0
  fiducialCentersMm().forEach(([cx, cy], k) => {
    const pred = ([[cx - hs, cy - hs], [cx + hs, cy - hs], [cx + hs, cy + hs], [cx - hs, cy + hs]] as Pt[]).map((p) => applyH(H, p))
    let side = 0
    for (let i = 0; i < 4; i++) side += Math.hypot(pred[i][0] - pred[(i + 3) % 4][0], pred[i][1] - pred[(i + 3) % 4][1])
    side /= 4
    let e = 0
    for (const p of pred) e += Math.min(...quads[k].map((q) => Math.hypot(p[0] - q[0], p[1] - q[1])))
    total += e / 4 / Math.max(side, 1e-6)
  })
  return total / 4
}

function centreLum(g: Float32Array, w: number, h: number, H: number[], s: Swatch): number {
  const [x, y] = applyH(H, [s.xMm + CARD.swatchMm / 2, s.yMm + CARD.swatchMm / 2]).map(Math.round)
  if (x < 1 || y < 1 || x >= w - 1 || y >= h - 1) return -1
  let sum = 0
  for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) sum += g[(y + dy) * w + x + dx]
  return sum / 9 / 255
}

function pointInQuad(q: Pt[], x: number, y: number): boolean {
  let sign = 0
  for (let i = 0; i < 4; i++) {
    const a = q[i], b = q[(i + 1) % 4]
    const c = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
    if (c !== 0) {
      if (sign === 0) sign = Math.sign(c)
      else if (Math.sign(c) !== sign) return false
    }
  }
  return true
}

/** 색 칸 가운데 60%의 평균 RGB (0~1). 가장자리는 인쇄 번짐·흐림이 섞인다. */
export function sampleSwatches(img: RGBImage, H: number[]): Record<string, [number, number, number]> | null {
  const out: Record<string, [number, number, number]> = {}
  const inset = CARD.swatchMm * 0.2
  for (const s of swatches()) {
    const q = ([[s.xMm + inset, s.yMm + inset], [s.xMm + CARD.swatchMm - inset, s.yMm + inset],
      [s.xMm + CARD.swatchMm - inset, s.yMm + CARD.swatchMm - inset], [s.xMm + inset, s.yMm + CARD.swatchMm - inset]] as Pt[])
      .map((p) => applyH(H, p))
    const x0 = Math.floor(Math.min(...q.map((p) => p[0]))), x1 = Math.ceil(Math.max(...q.map((p) => p[0])))
    const y0 = Math.floor(Math.min(...q.map((p) => p[1]))), y1 = Math.ceil(Math.max(...q.map((p) => p[1])))
    if (x0 < 0 || y0 < 0 || x1 >= img.w || y1 >= img.h) return null
    const acc = [0, 0, 0]
    let n = 0
    for (let y = y0; y <= y1; y++)
      for (let x = x0; x <= x1; x++) {
        if (!pointInQuad(q, x, y)) continue
        const j = (y * img.w + x) * 3
        acc[0] += img.data[j]; acc[1] += img.data[j + 1]; acc[2] += img.data[j + 2]
        n++
      }
    if (n < 9) return null
    out[s.name] = [acc[0] / n / 255, acc[1] / n / 255, acc[2] / n / 255]
  }
  return out
}

export function detectCard(img: RGBImage): CardDetection | null {
  const { w, h } = img
  const g = toGray255(img)
  const cands = candidates(g, w, h)
  if (cands.length < 4) return null
  const sw = swatches()
  const byName = Object.fromEntries(sw.map((s) => [s.name, s]))
  const fid = fiducialCentersMm()
  const cardIdx = [0, 1, 3, 2] // 볼록 순서 BL→BR→TR→TL
  const cardRing = cardIdx.map((i) => fid[i])
  let best: { H: number[]; err: number } | null = null

  const n = cands.length
  for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) for (let c = b + 1; c < n; c++) for (let d = c + 1; d < n; d++) {
    const combo = [a, b, c, d].map((i) => cands[i])
    const sizes = combo.map((k) => k.size)
    if (Math.max(...sizes) / Math.min(...sizes) > 2) continue
    const cx = combo.reduce((s, k) => s + k.centre[0], 0) / 4
    const cy = combo.reduce((s, k) => s + k.centre[1], 0) / 4
    const ring = [...combo].sort((p, q) => Math.atan2(p.centre[1] - cy, p.centre[0] - cx) - Math.atan2(q.centre[1] - cy, q.centre[0] - cx))
    for (let k = 0; k < 4; k++) {
      for (const flip of [false, true]) {
        let order = [0, 1, 2, 3].map((i) => ring[(i + k) % 4])
        if (flip) order = order.reverse()
        let H: number[]
        try { H = homography(cardRing, order.map((o) => o.centre)) } catch { continue }
        const quads: Pt[][] = new Array(4)
        cardIdx.forEach((fidIdx, pos) => { quads[fidIdx] = order[pos].quad })
        const err = cornerError(H, quads)
        if (err > 0.25) continue
        const lums = LUM_ORDER.map((nm) => centreLum(g, w, h, H, byName[nm]))
        if (Math.min(...lums) < 0 || !lums.every((v, i) => i === 0 || lums[i - 1] > v + 0.02)) continue
        if (!best || err < best.err) best = { H, err }
      }
    }
  }
  if (!best) return null
  const swatchSrgb = sampleSwatches(img, best.H)
  if (!swatchSrgb) return null
  return { H: best.H, swatchSrgb, cornerErr: best.err }
}
