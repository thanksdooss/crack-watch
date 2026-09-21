import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { gray, mask } from '../vision/core/image'
import { measureWidths } from './profile'

const DIR = resolve(__dirname, '../../../shared/fixtures/golden')
const meta = JSON.parse(readFileSync(resolve(DIR, 'meta.json'), 'utf8'))
const f32 = (n: string) => { const b = readFileSync(resolve(DIR, n)); return new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)) }
const med = (v: number[]) => { const s = [...v].sort((a, b) => a - b); return s[s.length >> 1] }

describe('폭 측정 — 파이썬과 같은 답', () => {
  const ws = measureWidths(gray(meta.w, meta.h, f32(meta.files.flat)), mask(meta.w, meta.h, new Uint8Array(readFileSync(resolve(DIR, meta.files.gtMask)))))
  const py = meta.width.samples as number[][]

  it('표본 수가 비슷하다', () => {
    expect(Math.abs(ws.length - meta.width.n) / meta.width.n).toBeLessThan(0.1)
  })
  it('반치폭(fwhm) 중앙값 2% 이내', () => {
    const a = med(ws.map((w) => w.fwhm)), b = med(py.map((s) => s[2]))
    expect(Math.abs(a - b) / b).toBeLessThan(0.02)
  })
  it('채택 값(hybrid) 중앙값 2% 이내', () => {
    const a = med(ws.map((w) => w.hybrid)), b = med(py.map((s) => s[5]))
    expect(Math.abs(a - b) / b).toBeLessThan(0.02)
  })
  it('넓이 기반(area) 중앙값 2% 이내', () => {
    const a = med(ws.map((w) => w.area)), b = med(py.map((s) => s[3]))
    expect(Math.abs(a - b) / b).toBeLessThan(0.02)
  })
})
