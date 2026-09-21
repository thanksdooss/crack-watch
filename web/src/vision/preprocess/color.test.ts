import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { applyToColor, deltaE2000, fitCorrection, type RGB, srgbToLab } from './color'
import { NEUTRALS, swatches } from './card'

const FIX = resolve(__dirname, '../../../../shared/fixtures')

describe('CIEDE2000', () => {
  it('Sharma(2005) 34쌍과 일치', () => {
    const rows = readFileSync(resolve(FIX, 'ciede2000_testdata.txt'), 'utf8').trim().split('\n')
      .map((l) => l.trim().split(/\s+/).map(Number))
    expect(rows).toHaveLength(34)
    for (const r of rows) {
      expect(deltaE2000([r[0], r[1], r[2]], [r[3], r[4], r[5]])).toBeCloseTo(r[6], 4)
    }
  })
})

describe('색 보정 — 파이썬과 같은 계수', () => {
  const meta = JSON.parse(readFileSync(resolve(FIX, 'golden/meta.json'), 'utf8')).calibration
  const observed = Object.fromEntries(meta.names.map((n: string, i: number) => [n, meta.observed[i] as RGB]))
  const targets = Object.fromEntries(swatches().map((s) => [s.name, s.targetSrgb]))
  const corr = fitCorrection(observed, targets, NEUTRALS)

  it('이득·오프셋', () => {
    corr.gain.forEach((g, i) => expect(g).toBeCloseTo(meta.gain[i], 6))
    corr.offset.forEach((o, i) => expect(o).toBeCloseTo(meta.offset[i], 6))
    expect(corr.quality).toBe(meta.quality)
  })

  it('계산에 넣지 않은 빨강·파랑도 제자리로 (평균 오차 절반 이하 — ml/tests/test_calibration.py와 같은 기준)', () => {
    const de = (name: string, fix: boolean) =>
      deltaE2000(srgbToLab(fix ? applyToColor(corr, observed[name]) : observed[name]), srgbToLab(targets[name]))
    const before = (de('red', false) + de('blue', false)) / 2
    const after = (de('red', true) + de('blue', true)) / 2
    expect(after).toBeLessThan(before / 2)
  })
})
