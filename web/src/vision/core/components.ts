// 연결 요소(8방향) — 두 번 훑기 + 합집합 찾기. cv2.connectedComponentsWithStats 대응.
import type { Mask } from './image'

export interface ComponentStats {
  n: number // 배경(0) 포함 개수
  labels: Int32Array
  area: Int32Array
  x0: Int32Array
  y0: Int32Array
  x1: Int32Array // 포함 경계
  y1: Int32Array
}

export function connectedComponents(m: Mask): ComponentStats {
  const { w, h, data } = m
  const labels = new Int32Array(w * h)
  const parent: number[] = [0]
  const find = (a: number): number => {
    while (parent[a] !== a) {
      parent[a] = parent[parent[a]]
      a = parent[a]
    }
    return a
  }
  const union = (a: number, b: number) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent[Math.max(ra, rb)] = Math.min(ra, rb)
  }
  let next = 1
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x
      if (!data[i]) continue
      let lab = 0
      // 이미 본 이웃: 왼쪽, 왼쪽위, 위, 오른쪽위
      const nb = [
        x > 0 ? labels[i - 1] : 0,
        x > 0 && y > 0 ? labels[i - w - 1] : 0,
        y > 0 ? labels[i - w] : 0,
        x < w - 1 && y > 0 ? labels[i - w + 1] : 0,
      ]
      for (const l of nb) {
        if (!l) continue
        if (!lab) lab = l
        else if (l !== lab) union(lab, l)
      }
      if (!lab) {
        lab = next++
        parent.push(lab)
      }
      labels[i] = lab
    }
  }
  // 대표 번호를 1..n-1로 다시 매긴다
  const remap = new Int32Array(next)
  let n = 1
  for (let l = 1; l < next; l++) {
    const r = find(l)
    if (!remap[r]) remap[r] = n++
    remap[l] = remap[r]
  }
  const area = new Int32Array(n)
  const x0 = new Int32Array(n).fill(w)
  const y0 = new Int32Array(n).fill(h)
  const x1 = new Int32Array(n).fill(-1)
  const y1 = new Int32Array(n).fill(-1)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x
      const l = labels[i] ? remap[labels[i]] : 0
      labels[i] = l
      if (!l) continue
      area[l]++
      if (x < x0[l]) x0[l] = x
      if (y < y0[l]) y0[l] = y
      if (x > x1[l]) x1[l] = x
      if (y > y1[l]) y1[l] = y
    }
  }
  return { n, labels, area, x0, y0, x1, y1 }
}
