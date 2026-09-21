import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { analyze, downscale } from './analyze'

const DIR = resolve(__dirname, '../../../shared/fixtures/golden')
const meta = JSON.parse(readFileSync(resolve(DIR, 'meta.json'), 'utf8'))

describe('분석 파이프라인 (카드가 붙은 합성 장면)', { timeout: 60_000 }, () => {
  const s = meta.cardScenes[0]
  const rgb = new Uint8Array(readFileSync(resolve(DIR, s.file)))

  it('카드를 찾고, 색 보정·지각 해시·흐림 점수를 낸다', async () => {
    const a = await analyze({ rgb, w: s.w, h: s.h })
    expect(a.card).not.toBeNull()
    expect(Math.abs(a.card!.pxPerMm - s.pxPerMm) / s.pxPerMm).toBeLessThan(0.05)
    expect(a.correction?.quality).toBe('good')
    expect(a.phash).toMatch(/^[0-9a-f]{16}$/)
    expect(a.engine).toMatch(/^classic@/)
    expect(a.blurScore).toBeGreaterThanOrEqual(0)
  })

  it('카드 영역은 균열로 세지 않는다', async () => {
    const a = await analyze({ rgb, w: s.w, h: s.h })
    const [x, y] = s.probe
    expect(a.mask.data[y * a.w + x]).toBe(0)
  })

  it('모델이 실패하면 고전 CV로 대신하고 사유를 남긴다', async () => {
    const broken = { name: 'model@x', run: async () => { throw new Error('메모리 부족') } }
    const a = await analyze({ rgb, w: s.w, h: s.h }, { model: broken })
    expect(a.engine).toMatch(/^classic@/)
    expect(a.warnings.join(' ')).toContain('메모리 부족')
  })

  it('큰 사진은 줄여서 분석한다', () => {
    const big = new Uint8Array(3200 * 2400 * 3)
    const d = downscale(big, 3200, 2400)
    expect(Math.max(d.w, d.h)).toBe(1600)
    expect(d.f).toBeCloseTo(0.5)
  })
})
