// 브라우저에서 쓸 실행 파일을 public/으로 복사한다(저장소에는 넣지 않는다 — .gitignore).
//  - ONNX Runtime Web의 WASM 경로 파일 2개 (WebGPU용 22MB 파일은 싣지 않는다)
//  - 학습·양자화한 모델 (data/models → public/models), 있으면
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const here = resolve(import.meta.dirname, '..')
const ortDist = resolve(here, 'node_modules/onnxruntime-web/dist')
const ortOut = resolve(here, 'public/ort')
mkdirSync(ortOut, { recursive: true })
for (const f of ['ort-wasm-simd-threaded.mjs', 'ort-wasm-simd-threaded.wasm']) copyFileSync(resolve(ortDist, f), resolve(ortOut, f))

const model = resolve(here, '../data/models/crack_unet_fp32.onnx')
const modelOut = resolve(here, 'public/models')
if (existsSync(model)) {
  mkdirSync(modelOut, { recursive: true })
  copyFileSync(model, resolve(modelOut, 'crack_unet_fp32.onnx'))
  console.log('model copied')
} else if (!existsSync(resolve(modelOut, 'crack_unet_fp32.onnx'))) {
  console.warn('! 모델 파일 없음 — 앱은 고전 영상처리로만 동작한다')
}
