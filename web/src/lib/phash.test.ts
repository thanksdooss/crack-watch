import { describe, expect, it } from 'vitest'
import { hamming, phash } from './phash'

function scene(w: number, h: number, seed: number, gain = 1, shift = 0): Float32Array {
  const out = new Float32Array(w * h)
  let s = seed
  const rnd = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff)
  const blobs = Array.from({ length: 12 }, () => [rnd() * w, rnd() * h, 10 + rnd() * 60, rnd() - 0.5])
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let v = 0.5
    for (const [bx, by, r, a] of blobs) v += a * Math.exp(-(((x + shift - bx) ** 2 + (y - by) ** 2) / (2 * r * r)))
    out[y * w + x] = Math.min(1, Math.max(0, v * gain))
  }
  return out
}

describe('지각 해시', () => {
  it('16자리 hex', () => {
    expect(phash(scene(200, 150, 1), 200, 150)).toMatch(/^[0-9a-f]{16}$/)
  })
  it('밝기가 달라도 같은 장면이면 가깝다', () => {
    const a = phash(scene(200, 150, 1), 200, 150)
    const b = phash(scene(200, 150, 1, 0.8), 200, 150)
    expect(hamming(a, b)).toBeLessThanOrEqual(6)
  })
  it('조금 옆에서 찍어도 가깝다', () => {
    const a = phash(scene(200, 150, 1), 200, 150)
    const b = phash(scene(200, 150, 1, 1, 4), 200, 150)
    expect(hamming(a, b)).toBeLessThanOrEqual(10)
  })
  it('다른 장면이면 멀다', () => {
    const a = phash(scene(200, 150, 1), 200, 150)
    const b = phash(scene(200, 150, 99), 200, 150)
    expect(hamming(a, b)).toBeGreaterThan(16)
  })
})
