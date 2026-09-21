// 사진 한 장 분석 — 기기 안에서 끝난다. 서버로는 여기서 나온 숫자와 해시만 간다.
//
//  축소 → 기준 카드 찾기 → 색 보정 → 균열 검출(모델 | 고전 CV) → 중심선·폭(px) → mm 환산 → 지각 해시
//
// 각 단계가 실패해도 멈추지 않고 '무엇을 믿을 수 없는지'를 사유로 남긴다.
// 예: 카드가 없으면 검출은 하되 mm 환산과 색 판정은 하지 않는다(지어내지 않는다).
import pipeline from '@shared/pipeline.json'
import { phash } from '../lib/phash'
import { measureWidths } from '../measure/profile'
import { type ScaleEstimate, scaleFromCard, summarizeWidth, type WidthResult } from '../measure/width'
import { detectClassic, flatten } from './classic/detect'
import { connectedComponents } from './core/components'
import { type Gray, type Mask, gray, luminance } from './core/image'
import { thin } from './core/thin'
import { type CardDetection, detectCard, localScale, NEUTRALS, swatches } from './preprocess/card'
import { applyToImage, type Correction, fitCorrection, type RGB } from './preprocess/color'

export const MAX_SIDE = 1600

export interface ModelRunner {
  name: string // 예: model@unet-mnv3s-int8
  /** RGB uint8 (w*h*3) → 균열 확률 (w*h) */
  run(rgb: Uint8Array | Uint8ClampedArray, w: number, h: number): Promise<Float32Array>
}

export interface CrackTrace {
  /** 정규화 좌표(0~1) 폴리라인, 최대 32점 */
  polyline: [number, number][]
  lengthPx: number
  width: WidthResult
}

export interface Analysis {
  w: number
  h: number
  /** 분석 해상도의 사진(보정 전 RGB). 기기 밖으로 나가지 않는다 — 화면 표시와 표지 색 확인용 */
  rgb: Uint8ClampedArray
  scaleFactor: number // 원본 → 분석 해상도 배율
  engine: string
  card: (CardDetection & { pxPerMm: number; anisotropy: number }) | null
  correction: Correction | null
  mask: Mask
  cracks: CrackTrace[]
  overall: WidthResult
  phash: string
  blurScore: number
  timings: Record<string, number>
  warnings: string[]
}

/** 면적 평균 축소 (정수 배율이 아니어도 된다). */
export function downscale(rgb: Uint8Array | Uint8ClampedArray, w: number, h: number, maxSide = MAX_SIDE) {
  const f = Math.min(1, maxSide / Math.max(w, h))
  if (f === 1) return { rgb: Uint8ClampedArray.from(rgb) as Uint8ClampedArray, w, h, f }
  const W = Math.round(w * f), H = Math.round(h * f)
  const out = new Uint8ClampedArray(W * H * 3)
  for (let y = 0; y < H; y++) {
    const y0 = Math.floor(y / f), y1 = Math.max(y0 + 1, Math.floor((y + 1) / f))
    for (let x = 0; x < W; x++) {
      const x0 = Math.floor(x / f), x1 = Math.max(x0 + 1, Math.floor((x + 1) / f))
      const acc = [0, 0, 0]
      for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) {
        const j = (yy * w + xx) * 3
        acc[0] += rgb[j]; acc[1] += rgb[j + 1]; acc[2] += rgb[j + 2]
      }
      const n = (y1 - y0) * (x1 - x0)
      const o = (y * W + x) * 3
      out[o] = acc[0] / n; out[o + 1] = acc[1] / n; out[o + 2] = acc[2] / n
    }
  }
  return { rgb: out, w: W, h: H, f }
}

/** 라플라시안 분산 기반 흐림 점수 0~1 (클수록 흐리다). 서버 신뢰도 규칙이 쓴다. */
export function blurScore(g: Gray): number {
  let s = 0, s2 = 0, n = 0
  for (let y = 1; y < g.h - 1; y++) for (let x = 1; x < g.w - 1; x++) {
    const i = y * g.w + x
    const l = 4 * g.data[i] - g.data[i - 1] - g.data[i + 1] - g.data[i - g.w] - g.data[i + g.w]
    s += l; s2 += l * l; n++
  }
  const variance = s2 / n - (s / n) ** 2
  // 경험적 척도: 선명한 콘크리트 사진의 분산 ≈ 1e-3 이상. 로그 척도로 0~1에 눌러 담는다.
  return Math.min(1, Math.max(0, -Math.log10(Math.max(variance, 1e-7)) / 4 - 0.5))
}

/** 중심선을 단순화한 정규화 폴리라인 (서버 전송용, 최대 32점). */
function tracePolyline(skel: Mask, labels: Int32Array, label: number, w: number, h: number): { poly: [number, number][]; length: number } {
  const pts: [number, number][] = []
  for (let i = 0; i < labels.length; i++) if (labels[i] === label && skel.data[i]) pts.push([i % w, Math.floor(i / w)])
  if (pts.length < 2) return { poly: [], length: 0 }
  // 주성분 축으로 정렬한 뒤 균등 간격으로 뽑는다 (가지가 있어도 대략적인 모양은 남는다)
  const mx = pts.reduce((a, p) => a + p[0], 0) / pts.length
  const my = pts.reduce((a, p) => a + p[1], 0) / pts.length
  let sxx = 0, syy = 0, sxy = 0
  for (const [x, y] of pts) { sxx += (x - mx) ** 2; syy += (y - my) ** 2; sxy += (x - mx) * (y - my) }
  const th = 0.5 * Math.atan2(2 * sxy, sxx - syy)
  const ux = Math.cos(th), uy = Math.sin(th)
  pts.sort((a, b) => (a[0] - mx) * ux + (a[1] - my) * uy - ((b[0] - mx) * ux + (b[1] - my) * uy))
  const k = Math.min(32, pts.length)
  const poly: [number, number][] = []
  for (let i = 0; i < k; i++) {
    const p = pts[Math.round((i * (pts.length - 1)) / (k - 1))]
    poly.push([p[0] / w, p[1] / h])
  }
  return { poly, length: pts.length }
}

export async function analyze(
  input: { rgb: Uint8Array | Uint8ClampedArray; w: number; h: number },
  opts: { model?: ModelRunner | null } = {},
): Promise<Analysis> {
  const timings: Record<string, number> = {}
  const warnings: string[] = []
  const tick = (() => { let t = performance.now(); return (k: string) => { const n = performance.now(); timings[k] = Math.round(n - t); t = n } })()

  const small = downscale(input.rgb, input.w, input.h)
  const { w, h } = small
  tick('downscale')

  const card = detectCard({ w, h, data: small.rgb })
  let correction: Correction | null = null
  let rgb: Uint8ClampedArray = small.rgb
  if (card) {
    const targets = Object.fromEntries(swatches().map((s) => [s.name, s.targetSrgb as RGB]))
    correction = fitCorrection(card.swatchSrgb as Record<string, RGB>, targets, NEUTRALS)
    rgb = applyToImage(correction, small.rgb)
    if (correction.quality === 'poor') warnings.push('기준 카드 색이 크게 틀어져 색 판정을 믿기 어렵습니다(그늘·반사 확인)')
  } else {
    warnings.push('기준 카드를 찾지 못했습니다 — 균열 위치는 표시하지만 폭(mm)과 색은 판정하지 않습니다')
  }
  tick('card+color')

  const rgbF = new Float32Array(rgb.length)
  for (let i = 0; i < rgb.length; i++) rgbF[i] = rgb[i] / 255
  const lum = luminance(rgbF, w, h)

  let engine = `classic@${pipeline.version}`
  let mask: Mask
  if (opts.model) {
    try {
      const prob = await opts.model.run(rgb, w, h)
      const cfg = (pipeline as { model?: { threshold: number; minArea: number } }).model ?? { threshold: 0.5, minArea: 0 }
      mask = { w, h, data: new Uint8Array(w * h) }
      for (let i = 0; i < prob.length; i++) mask.data[i] = prob[i] >= cfg.threshold ? 1 : 0
      if (cfg.minArea > 0) {
        const cc = connectedComponents(mask)
        for (let i = 0; i < mask.data.length; i++) if (cc.labels[i] && cc.area[cc.labels[i]] < cfg.minArea) mask.data[i] = 0
      }
      engine = opts.model.name
    } catch (e) {
      warnings.push(`모델 실행 실패로 고전 영상처리로 대신했습니다 (${(e as Error).message})`)
      mask = detectClassic(lum).mask
    }
  } else {
    mask = detectClassic(lum).mask
  }
  // 카드 자체(모서리 사각형·색 칸 경계)는 균열이 아니다 — 카드 영역을 지운다
  if (card) eraseCard(mask, card.H)
  tick('detect')

  const flat = flatten(lum, pipeline.classic.flattenSigma)
  const skel = thin(mask)
  const cc = connectedComponents(mask)
  let scale: ScaleEstimate | null = null
  let cardOut: Analysis['card'] = null
  if (card) {
    const ls = localScale(card.H, w / 2, h / 2)
    scale = scaleFromCard(ls.pxPerMm, card.cornerErr, ls.anisotropy)
    cardOut = { ...card, ...ls }
  }
  const method = pipeline.measure.method as 'fwhm' | 'area' | 'hybrid'
  const allWidths: number[] = []
  const cracks: CrackTrace[] = []
  const samples = measureWidths(flat, mask)
  for (let l = 1; l < cc.n; l++) {
    const mine = samples.filter((s) => cc.labels[s.y * w + s.x] === l).map((s) => s[method])
    if (mine.length < 3) continue
    const { poly, length } = tracePolyline(skel, cc.labels, l, w, h)
    allWidths.push(...mine)
    cracks.push({ polyline: poly, lengthPx: length, width: summarizeWidth(mine, scale) })
  }
  cracks.sort((a, b) => b.lengthPx - a.lengthPx)
  tick('measure')

  const result: Analysis = {
    w, h, rgb: small.rgb, scaleFactor: small.f, engine, card: cardOut, correction, mask,
    cracks: cracks.slice(0, 16),
    overall: summarizeWidth(allWidths, scale),
    phash: phash(lum.data, w, h),
    blurScore: blurScore(lum),
    timings, warnings,
  }
  tick('hash')
  return result
}

function eraseCard(m: Mask, H: number[]) {
  const pad = 2 // mm
  const C = pipeline.calibration.card
  const corners = [[-pad, -pad], [C.w + pad, -pad], [C.w + pad, C.h + pad], [-pad, C.h + pad]].map(([x, y]) => {
    const z = H[6] * x + H[7] * y + H[8]
    return [(H[0] * x + H[1] * y + H[2]) / z, (H[3] * x + H[4] * y + H[5]) / z]
  })
  const xs = corners.map((c) => c[0]), ys = corners.map((c) => c[1])
  for (let y = Math.max(0, Math.floor(Math.min(...ys))); y <= Math.min(m.h - 1, Math.ceil(Math.max(...ys))); y++)
    for (let x = Math.max(0, Math.floor(Math.min(...xs))); x <= Math.min(m.w - 1, Math.ceil(Math.max(...xs))); x++) {
      let inside = true, sign = 0
      for (let i = 0; i < 4 && inside; i++) {
        const a = corners[i], b = corners[(i + 1) % 4]
        const c = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if (c !== 0) { if (!sign) sign = Math.sign(c); else if (Math.sign(c) !== sign) inside = false }
      }
      if (inside) m.data[y * m.w + x] = 0
    }
}

/** 사용자가 짚은 곳(표지 등)의 보정된 색과 '붉은 쪽인가' 판정. 카드가 없으면 판정하지 않는다. */
export { judgeSignColor } from './sign'
export type { Gray }
export { gray }
