// 블러와 미분 — OpenCV(cv2.GaussianBlur, cv2.Sobel)와 같은 커널·경계 처리로 맞춘다.
// 파이썬 기준선과 결과가 달라지면 문서의 기준선 숫자가 웹 동작을 대표하지 못한다.
import { type Gray, gray, reflect101 } from './image'

/** cv2.getGaussianKernel과 같은 규칙: float 이미지에서 ksize = round(sigma*8+1) | 1 */
export function gaussianKernel(sigma: number): Float32Array {
  const ksize = Math.round(sigma * 8 + 1) | 1
  const r = (ksize - 1) / 2
  const k = new Float32Array(ksize)
  let sum = 0
  for (let i = 0; i < ksize; i++) {
    const x = i - r
    k[i] = Math.exp(-(x * x) / (2 * sigma * sigma))
    sum += k[i]
  }
  for (let i = 0; i < ksize; i++) k[i] /= sum
  return k
}

/** 경계 반사 인덱스 표: i ∈ [-r, n+r) → 원본 인덱스. 탭마다 함수를 부르면 수십 배 느려진다. */
function reflectTable(n: number, r: number): Int32Array {
  const t = new Int32Array(n + 2 * r)
  for (let i = 0; i < t.length; i++) t[i] = reflect101(i - r, n)
  return t
}

/** 분리 가능한 커널을 가로(kx)·세로(ky)로 적용. */
export function sepFilter(src: Gray, kx: Float32Array, ky: Float32Array): Gray {
  const { w, h } = src
  const tmp = new Float32Array(w * h)
  const out = gray(w, h)
  const rx = (kx.length - 1) / 2
  const ry = (ky.length - 1) / 2
  const tx = reflectTable(w, rx)
  const ty = reflectTable(h, ry)
  const d = src.data
  for (let y = 0; y < h; y++) {
    const row = y * w
    for (let x = 0; x < w; x++) {
      let s = 0
      for (let k = 0; k < kx.length; k++) s += kx[k] * d[row + tx[x + k]]
      tmp[row + x] = s
    }
  }
  const o = out.data
  for (let y = 0; y < h; y++) {
    for (let k = 0; k < ky.length; k++) {
      const kk = ky[k]
      if (kk === 0) continue
      const srcRow = ty[y + k] * w
      const dstRow = y * w
      for (let x = 0; x < w; x++) o[dstRow + x] += kk * tmp[srcRow + x]
    }
  }
  return out
}

export function gaussianBlur(src: Gray, sigma: number): Gray {
  const k = gaussianKernel(sigma)
  return sepFilter(src, k, k)
}

// cv2.Sobel ksize=3의 분리 커널
const D0 = new Float32Array([1, 2, 1])
const D1 = new Float32Array([-1, 0, 1])
const D2 = new Float32Array([1, -2, 1])
const KERNELS = [D0, D1, D2]

/** cv2.Sobel(src, CV_32F, dx, dy, ksize=3) */
export function sobel(src: Gray, dx: 0 | 1 | 2, dy: 0 | 1 | 2): Gray {
  return sepFilter(src, KERNELS[dx], KERNELS[dy])
}
