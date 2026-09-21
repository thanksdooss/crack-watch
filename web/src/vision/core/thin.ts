// Zhang-Suen 세선화 — ml/measure/skeleton.py와 같은 알고리즘(전경 픽셀만 순회).
import { type Mask, mask as newMask } from './image'

export function thin(src: Mask, maxIter = 200): Mask {
  const { w, h } = src
  const W = w + 2
  const flat = new Uint8Array((h + 2) * W)
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) flat[(y + 1) * W + x + 1] = src.data[y * w + x] ? 1 : 0
  let fg: number[] = []
  for (let i = 0; i < flat.length; i++) if (flat[i]) fg.push(i)
  // P2..P9: 위에서 시계방향
  const offs = [-W, -W + 1, 1, W + 1, W, W - 1, -1, -W - 1]
  const n = new Uint8Array(8)
  for (let it = 0; it < maxIter; it++) {
    let changed = false
    for (let step = 0; step < 2; step++) {
      const rm: number[] = []
      const keep: number[] = []
      for (const i of fg) {
        let b = 0
        for (let k = 0; k < 8; k++) { n[k] = flat[i + offs[k]]; b += n[k] }
        let a = 0
        for (let k = 0; k < 8; k++) if (n[k] === 0 && n[(k + 1) % 8] === 1) a++
        const [p2, , p4, , p6, , p8] = n
        const c = step === 0
          ? p2 * p4 * p6 === 0 && p4 * p6 * p8 === 0
          : p2 * p4 * p8 === 0 && p2 * p6 * p8 === 0
        if (b >= 2 && b <= 6 && a === 1 && c) rm.push(i)
        else keep.push(i)
      }
      // 파이썬(넘파이) 구현과 같게: 한 단계의 판정을 모두 끝낸 뒤 한꺼번에 지운다
      for (const i of rm) flat[i] = 0
      if (rm.length) changed = true
      fg = keep
    }
    if (!changed) break
  }
  const out = newMask(w, h)
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) out.data[y * w + x] = flat[(y + 1) * W + x + 1]
  return out
}
