// ONNX Runtime Web으로 균열 모델 실행. WASM(SIMD) 경로가 기본, WebGPU는 쓸 수 있으면 가속.
// 모델 파일과 WASM은 같은 출처(/models, /ort)에서 받는다 — 오프라인(서비스 워커 캐시)에서도 돌게.
import pipeline from '@shared/pipeline.json'
import type { ModelRunner } from '../analyze'
import { normalize } from './preprocess'

const MODEL_URL = `${import.meta.env.BASE_URL}models/${(pipeline as { model?: { file: string } }).model?.file ?? 'crack_unet_int8.onnx'}`
const MAX_SIDE = 1024 // 모델 입력 긴 변. 폭 측정은 원래 해상도(분석 해상도)의 원본 밝기에서 한다

export async function createRunner(): Promise<ModelRunner> {
  const ort = await import('onnxruntime-web/wasm')
  ort.env.wasm.wasmPaths = `${import.meta.env.BASE_URL}ort/`
  ort.env.wasm.numThreads = 1 // 교차 출처 격리(COOP/COEP) 없는 정적 호스팅에서도 동작하게
  const session = await ort.InferenceSession.create(MODEL_URL, { executionProviders: ['wasm'] })
  const inputName = session.inputNames[0]

  return {
    name: `model@${MODEL_URL.split('/').pop()}`,
    async run(rgb, w, h) {
      // 긴 변을 MAX_SIDE 이하로, 32의 배수로 맞춘다(인코더가 해상도를 32배 줄였다 키운다)
      const f = Math.min(1, MAX_SIDE / Math.max(w, h))
      const W = Math.max(32, Math.round((w * f) / 32) * 32)
      const H = Math.max(32, Math.round((h * f) / 32) * 32)
      const small = resizeRGB(rgb, w, h, W, H)
      const tensor = new ort.Tensor('float32', normalize(small, W, H), [1, 3, H, W])
      const out = await session.run({ [inputName]: tensor })
      const logits = out[session.outputNames[0]].data as Float32Array
      // 확률을 원래 분석 해상도로 되돌린다(쌍선형)
      const prob = new Float32Array(w * h)
      for (let y = 0; y < h; y++) {
        const sy = Math.min(H - 1, ((y + 0.5) * H) / h - 0.5)
        const y0 = Math.max(0, Math.floor(sy)), y1 = Math.min(H - 1, y0 + 1), fy = Math.max(0, sy - y0)
        for (let x = 0; x < w; x++) {
          const sx = Math.min(W - 1, ((x + 0.5) * W) / w - 0.5)
          const x0 = Math.max(0, Math.floor(sx)), x1 = Math.min(W - 1, x0 + 1), fx = Math.max(0, sx - x0)
          const l = (logits[y0 * W + x0] * (1 - fx) + logits[y0 * W + x1] * fx) * (1 - fy) +
            (logits[y1 * W + x0] * (1 - fx) + logits[y1 * W + x1] * fx) * fy
          prob[y * w + x] = 1 / (1 + Math.exp(-l))
        }
      }
      return prob
    },
  }
}

function resizeRGB(src: Uint8Array | Uint8ClampedArray, w: number, h: number, W: number, H: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(W * H * 3)
  for (let y = 0; y < H; y++) {
    const sy = Math.min(h - 1, Math.max(0, ((y + 0.5) * h) / H - 0.5))
    const y0 = Math.floor(sy), y1 = Math.min(h - 1, y0 + 1), fy = sy - y0
    for (let x = 0; x < W; x++) {
      const sx = Math.min(w - 1, Math.max(0, ((x + 0.5) * w) / W - 0.5))
      const x0 = Math.floor(sx), x1 = Math.min(w - 1, x0 + 1), fx = sx - x0
      for (let c = 0; c < 3; c++) {
        const v = (src[(y0 * w + x0) * 3 + c] * (1 - fx) + src[(y0 * w + x1) * 3 + c] * fx) * (1 - fy) +
          (src[(y1 * w + x0) * 3 + c] * (1 - fx) + src[(y1 * w + x1) * 3 + c] * fx) * fy
        out[(y * W + x) * 3 + c] = v
      }
    }
  }
  return out
}
