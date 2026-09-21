// 단순한 이미지 컨테이너. 행 우선(row-major), 한 채널.
export interface Gray {
  w: number
  h: number
  data: Float32Array
}

export interface Mask {
  w: number
  h: number
  data: Uint8Array
}

export const gray = (w: number, h: number, data?: Float32Array): Gray => ({ w, h, data: data ?? new Float32Array(w * h) })
export const mask = (w: number, h: number, data?: Uint8Array): Mask => ({ w, h, data: data ?? new Uint8Array(w * h) })

/** OpenCV 기본 경계 처리(BORDER_REFLECT_101): ...3 2 1 | 0 1 2 3 ... | n-2 n-3 ... */
export function reflect101(i: number, n: number): number {
  if (n === 1) return 0
  while (i < 0 || i >= n) {
    if (i < 0) i = -i
    if (i >= n) i = 2 * n - 2 - i
  }
  return i
}

/** RGB(0~1, 길이 w*h*3) → 휘도. 파이썬 ml.baseline.classic.to_gray와 같은 계수(Rec.709). */
export function luminance(rgb: Float32Array, w: number, h: number): Gray {
  const out = gray(w, h)
  for (let i = 0, j = 0; i < w * h; i++, j += 3) {
    out.data[i] = rgb[j] * 0.2126 + rgb[j + 1] * 0.7152 + rgb[j + 2] * 0.0722
  }
  return out
}
