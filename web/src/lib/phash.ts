// 지각 해시(pHash) — 사진의 '대략적인 모습'을 64비트로 줄인 지문.
// 같은 벽을 조금 다른 밝기·각도로 찍어도 비슷한 값이 나오고, 원본 사진은 복원할 수 없다.
// 서버는 이 값의 해밍 거리로 '같은 장면의 중복 신고인가'를 판단한다(docs/01-architecture.md 3절).
// 주의: 복원은 불가능해도 '같은 장면인지 식별'은 가능하다 — 원본보다 덜 민감할 뿐 무해하지 않다.

const N = 32
const K = 8

function dctMatrix(): Float64Array {
  const m = new Float64Array(N * N)
  for (let k = 0; k < N; k++)
    for (let n = 0; n < N; n++) m[k * N + n] = Math.cos((Math.PI / N) * (n + 0.5) * k) * (k === 0 ? Math.sqrt(1 / N) : Math.sqrt(2 / N))
  return m
}
const D = dctMatrix()

/** 휘도(0~1, w*h)를 32×32로 줄여(면적 평균) DCT → 저주파 8×8 → 중앙값 기준 비트. 16자리 hex. */
export function phash(lum: Float32Array, w: number, h: number): string {
  const small = new Float64Array(N * N)
  for (let y = 0; y < N; y++) {
    const y0 = Math.floor((y * h) / N), y1 = Math.max(y0 + 1, Math.floor(((y + 1) * h) / N))
    for (let x = 0; x < N; x++) {
      const x0 = Math.floor((x * w) / N), x1 = Math.max(x0 + 1, Math.floor(((x + 1) * w) / N))
      let s = 0
      for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) s += lum[yy * w + xx]
      small[y * N + x] = s / ((y1 - y0) * (x1 - x0))
    }
  }
  // 2차원 DCT의 왼쪽 위 8×8만 필요하다
  const tmp = new Float64Array(K * N)
  for (let k = 0; k < K; k++) for (let x = 0; x < N; x++) {
    let s = 0
    for (let y = 0; y < N; y++) s += D[k * N + y] * small[y * N + x]
    tmp[k * N + x] = s
  }
  const coef: number[] = []
  for (let k = 0; k < K; k++) for (let l = 0; l < K; l++) {
    let s = 0
    for (let x = 0; x < N; x++) s += tmp[k * N + x] * D[l * N + x]
    coef.push(s)
  }
  const ac = coef.slice(1) // 평균 밝기(DC)는 빼고 중앙값을 잡는다 — 노출이 달라도 흔들리지 않게
  const med = [...ac].sort((a, b) => a - b)[ac.length >> 1]
  let hex = ''
  for (let i = 0; i < 64; i += 4) {
    let nib = 0
    for (let b = 0; b < 4; b++) nib = (nib << 1) | (coef[i + b] > med ? 1 : 0)
    hex += nib.toString(16)
  }
  return hex
}

export function hamming(a: string, b: string): number {
  if (a.length !== b.length) throw new Error('해시 길이가 다르다')
  let d = 0
  for (let i = 0; i < a.length; i++) {
    let x = parseInt(a[i], 16) ^ parseInt(b[i], 16)
    while (x) { d += x & 1; x >>= 1 }
  }
  return d
}
