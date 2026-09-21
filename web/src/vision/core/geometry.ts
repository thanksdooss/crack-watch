// 볼록 껍질, 최소 면적 회전 사각형, 원근 변환(호모그래피).
export type Pt = [number, number]

/** Andrew monotone chain. 반시계 순서, 중복 끝점 없음. */
export function convexHull(points: Pt[]): Pt[] {
  const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  if (p.length <= 2) return p
  const cross = (o: Pt, a: Pt, b: Pt) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const lower: Pt[] = []
  for (const q of p) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], q) <= 0) lower.pop()
    lower.push(q)
  }
  const upper: Pt[] = []
  for (let i = p.length - 1; i >= 0; i--) {
    const q = p[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], q) <= 0) upper.pop()
    upper.push(q)
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1))
}

/**
 * 최소 면적 회전 사각형의 (긴 변, 짧은 변). 픽셀 중심 좌표 기준.
 * cv2.minAreaRect는 점 집합의 사각형이라, 픽셀 1개짜리 선은 폭 0이 된다 — 같은 규칙을 따른다.
 */
export function minAreaRectSides(points: Pt[]): [number, number] {
  const hull = convexHull(points)
  if (hull.length === 1) return [0, 0]
  if (hull.length === 2) return [Math.hypot(hull[1][0] - hull[0][0], hull[1][1] - hull[0][1]), 0]
  let best = Infinity
  let sides: [number, number] = [0, 0]
  for (let i = 0; i < hull.length; i++) {
    const a = hull[i]
    const b = hull[(i + 1) % hull.length]
    const len = Math.hypot(b[0] - a[0], b[1] - a[1])
    if (len === 0) continue
    const ux = (b[0] - a[0]) / len
    const uy = (b[1] - a[1]) / len
    let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity
    for (const q of hull) {
      const u = q[0] * ux + q[1] * uy
      const v = -q[0] * uy + q[1] * ux
      if (u < minU) minU = u
      if (u > maxU) maxU = u
      if (v < minV) minV = v
      if (v > maxV) maxV = v
    }
    const area = (maxU - minU) * (maxV - minV)
    if (area < best) {
      best = area
      const s1 = maxU - minU
      const s2 = maxV - minV
      sides = s1 >= s2 ? [s1, s2] : [s2, s1]
    }
  }
  return sides
}

/** 4점 대응으로 호모그래피 (src → dst). 3×3 행 우선, h33 = 1. */
export function homography(src: Pt[], dst: Pt[]): number[] {
  if (src.length !== 4 || dst.length !== 4) throw new Error('점 4개가 필요하다')
  const A: number[][] = []
  const bvec: number[] = []
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i]
    const [u, v] = dst[i]
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); bvec.push(u)
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); bvec.push(v)
  }
  const h = solve(A, bvec)
  return [...h, 1]
}

export function applyH(H: number[], p: Pt): Pt {
  const [x, y] = p
  const z = H[6] * x + H[7] * y + H[8]
  return [(H[0] * x + H[1] * y + H[2]) / z, (H[3] * x + H[4] * y + H[5]) / z]
}

/** 가우스 소거(부분 피벗). 작은 시스템 전용. */
export function solve(A: number[][], b: number[]): number[] {
  const n = b.length
  const M = A.map((row, i) => [...row, b[i]])
  for (let c = 0; c < n; c++) {
    let piv = c
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[piv][c])) piv = r
    if (Math.abs(M[piv][c]) < 1e-12) throw new Error('특이 행렬 — 점들이 한 직선 위에 있다')
    ;[M[c], M[piv]] = [M[piv], M[c]]
    for (let r = 0; r < n; r++) {
      if (r === c) continue
      const f = M[r][c] / M[c][c]
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k]
    }
  }
  return M.map((row, i) => row[n] / row[i])
}
