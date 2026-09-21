import { describe, expect, it } from 'vitest'
import { percentile, scaleFromCard, summarizeWidth } from './width'

const scale10 = { pxPerMm: 10, relUncertainty: 0.02 }

describe('percentile', () => {
  it('선형 보간한다', () => {
    expect(percentile([0, 10], 50)).toBe(5)
    expect(percentile([3, 1, 2], 50)).toBe(2)
    expect(percentile([1, 2, 3, 4, 5], 90)).toBeCloseTo(4.6)
  })
})

describe('summarizeWidth', () => {
  it('px를 mm로 환산하고 대표값은 오차 범위 안에 있다', () => {
    const r = summarizeWidth(Array(50).fill(8), scale10)
    expect(r.representativeMm).toBeCloseTo(0.8)
    expect(r.ciMm[0]).toBeLessThan(0.8)
    expect(r.ciMm[1]).toBeGreaterThan(0.8)
  })

  it('오차 범위는 측정 한계(±0.5px) 아래로 좁아지지 않는다', () => {
    const r = summarizeWidth(Array(50).fill(8), { pxPerMm: 10, relUncertainty: 0 })
    expect(r.ciMm[1] - r.ciMm[0]).toBeCloseTo(0.1, 5) // (8±0.5)/10
  })

  it('범위 상단이 0.3mm에 닿으면 대표값이 그 아래여도 전문가 점검을 권한다(보수적)', () => {
    const r = summarizeWidth(Array(50).fill(2.8), scale10) // 0.28mm, 상단 ≈ 0.34mm
    expect(r.representativeMm).toBeLessThan(0.3)
    expect(r.guidance).toBe('전문가 점검 권장')
  })

  it('확실히 가는 균열은 관찰 필요 — 안전하다고 말하지 않는다', () => {
    const r = summarizeWidth(Array(50).fill(1.5), { pxPerMm: 20, relUncertainty: 0.02 })
    expect(r.guidance).toBe('관찰 필요')
    expect(JSON.stringify(r)).not.toContain('안전')
  })

  it('카드가 없으면 mm를 지어내지 않는다', () => {
    const r = summarizeWidth([5, 6, 7], null)
    expect(r.guidance).toBe('판정 보류')
    expect(Number.isNaN(r.representativeMm)).toBe(true)
  })

  it('축척이 크게 흔들리면 판정을 보류한다', () => {
    const r = summarizeWidth(Array(50).fill(8), { pxPerMm: 10, relUncertainty: 0.3 })
    expect(r.guidance).toBe('판정 보류')
  })

  it('해상도 한계보다 가늘면 알린다', () => {
    const r = summarizeWidth(Array(50).fill(1.0), scale10)
    expect(r.belowResolution).toBe(true)
  })

  it('잡음 한 점에 대표값이 끌려가지 않는다(최대값이 아니라 90백분위)', () => {
    const r = summarizeWidth([...Array(99).fill(5), 60], scale10)
    expect(r.representativeMm).toBeCloseTo(0.5)
  })
})

describe('scaleFromCard', () => {
  it('비스듬할수록 불확실성이 커진다', () => {
    const flat = scaleFromCard(8, 0.02, 0.0)
    const tilted = scaleFromCard(8, 0.02, 0.2)
    expect(tilted.relUncertainty).toBeGreaterThan(flat.relUncertainty)
  })
  it('잘못된 축척은 거부한다', () => {
    expect(() => scaleFromCard(0, 0, 0)).toThrow()
  })
})
