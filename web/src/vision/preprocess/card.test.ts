import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { detectCard, localScale } from './card'

const DIR = resolve(__dirname, '../../../../shared/fixtures/golden')
const meta = JSON.parse(readFileSync(resolve(DIR, 'meta.json'), 'utf8'))

describe('기준 카드 검출 (파이썬이 합성한 장면)', { timeout: 60_000 }, () => {
  for (const scene of meta.cardScenes) {
    it(`${scene.file}: px/mm를 1% 안으로 복원`, () => {
      const data = new Uint8Array(readFileSync(resolve(DIR, scene.file)))
      const d = detectCard({ w: scene.w, h: scene.h, data })
      expect(d).not.toBeNull()
      const { pxPerMm } = localScale(d!.H, scene.probe[0], scene.probe[1])
      expect(Math.abs(pxPerMm - scene.pxPerMm) / scene.pxPerMm).toBeLessThan(0.01)
      expect(d!.swatchSrgb.white[0]).toBeGreaterThan(d!.swatchSrgb.black[0] + 0.5)
    })
  }

  it('카드가 없으면 null — 크기를 지어내지 않는다', () => {
    const data = new Uint8Array(400 * 300 * 3).fill(150)
    expect(detectCard({ w: 400, h: 300, data })).toBeNull()
  })
})
