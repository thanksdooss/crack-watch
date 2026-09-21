// 골든 테스트: 파이썬(ml/)이 만든 기준값과 TS 구현이 같은 답을 내는가.
// 기준선 숫자(docs/evaluation.md)는 파이썬으로 쟀다. 웹이 다르게 동작하면 그 숫자는
// 웹의 성능을 대표하지 못한다. 여기가 그 연결 고리다.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { detectClassic, flatten, hysteresis, ridgeResponse, shapeFilter } from './classic/detect'
import { gray, mask } from './core/image'
import { thin } from './core/thin'
import { normalize } from './model/preprocess'

const DIR = resolve(__dirname, '../../../shared/fixtures/golden')
const meta = JSON.parse(readFileSync(resolve(DIR, 'meta.json'), 'utf8'))
const f32 = (name: string) => {
  const b = readFileSync(resolve(DIR, name))
  return new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength))
}
const u8 = (name: string) => new Uint8Array(readFileSync(resolve(DIR, name)))
const { w, h, params } = meta

function maxAbsDiff(a: Float32Array, b: Float32Array) {
  let m = 0
  for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i]))
  return m
}

/** 99.9백분위 절대 오차. 최대값은 Frangi 필터의 부호 경계(λ≈0)에서 32/64비트 누적 차이로
 *  튀는 몇 픽셀에 끌려간다(3만6천 중 13개 수준). 그 몇 픽셀은 마스크 비교에서 따로 잡는다. */
function p999AbsDiff(a: Float32Array, b: Float32Array) {
  const d = Array.from(a, (v, i) => Math.abs(v - b[i])).sort((x, y) => x - y)
  return d[Math.floor(0.999 * (d.length - 1))]
}

function iou(a: Uint8Array, b: Uint8Array) {
  let inter = 0, uni = 0
  for (let i = 0; i < a.length; i++) {
    if (a[i] && b[i]) inter++
    if (a[i] || b[i]) uni++
  }
  return uni ? inter / uni : 1
}

describe('파이썬과 같은 답', { timeout: 60_000 }, () => {
  const g = gray(w, h, f32(meta.files.gray))

  it('평탄화', () => {
    expect(maxAbsDiff(flatten(g, params.flattenSigma).data, f32(meta.files.flat))).toBeLessThan(1e-4)
  })

  it('능선 응답', () => {
    const r = ridgeResponse(flatten(g, params.flattenSigma), params)
    expect(p999AbsDiff(r.data, f32(meta.files.response))).toBeLessThan(1e-3)
  })

  it('검출 마스크 (임계 경계의 미세한 실수 오차만 허용)', () => {
    const { mask: m } = detectClassic(g, params)
    expect(iou(m.data, u8(meta.files.mask))).toBeGreaterThan(0.99)
    // 단계별로도: 파이썬 응답을 그대로 넣으면 완전히 같아야 한다
    const r = gray(w, h, f32(meta.files.response))
    const m2 = shapeFilter(hysteresis(r, params.hystLow, params.hystHigh), params.minLengthPx, params.minElongation)
    expect(iou(m2.data, u8(meta.files.mask))).toBe(1)
  })

  it('세선화', () => {
    const sk = thin(mask(w, h, u8(meta.files.gtMask)))
    expect(Array.from(sk.data)).toEqual(Array.from(u8(meta.files.skeleton)))
  })

  it('모델 입력 정규화 (shared/pipeline.json 상수)', () => {
    const rgb = u8(meta.files.rgb32)
    const out = normalize(rgb, 32, 32)
    expect(maxAbsDiff(out, f32(meta.files.norm32))).toBeLessThan(1e-5)
  })
})
