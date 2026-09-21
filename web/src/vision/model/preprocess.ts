// 모델 입력 전처리 — ml/train/data.py normalize와 같은 상수(shared/pipeline.json)를 쓴다.
import pipeline from '@shared/pipeline.json'

const MEAN = pipeline.normalize.mean
const STD = pipeline.normalize.std

/** RGB uint8 (h*w*3, HWC) → 정규화된 float32 (3*h*w, CHW) */
export function normalize(rgb: Uint8Array | Uint8ClampedArray, w: number, h: number): Float32Array {
  const out = new Float32Array(3 * w * h)
  const plane = w * h
  for (let i = 0; i < plane; i++) {
    for (let c = 0; c < 3; c++) {
      out[c * plane + i] = (rgb[i * 3 + c] / 255 - MEAN[c]) / STD[c]
    }
  }
  return out
}
