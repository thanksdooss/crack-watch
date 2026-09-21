// 분석은 전부 이 워커에서 돈다. 4000×3000 사진을 메인 스레드에서 처리하면 화면이 멈추고,
// 사용자는 앱이 죽은 줄 안다.
import { type Analysis, analyze, type ModelRunner } from '../analyze'

export interface AnalyzeRequest {
  id: number
  rgba: Uint8ClampedArray
  w: number
  h: number
  useModel: boolean
}
export type AnalyzeResponse =
  | { id: number; ok: true; result: Analysis }
  | { id: number; ok: false; error: string }
  | { id: number; progress: string }

let modelPromise: Promise<ModelRunner | null> | null = null

async function getModel(): Promise<ModelRunner | null> {
  if (!modelPromise) {
    modelPromise = import('../model/runner').then((m) => m.createRunner()).catch(() => null)
  }
  return modelPromise
}

self.onmessage = async (ev: MessageEvent<AnalyzeRequest>) => {
  const { id, rgba, w, h, useModel } = ev.data
  try {
    const rgb = new Uint8ClampedArray(w * h * 3)
    for (let i = 0, j = 0; i < w * h; i++, j += 4) {
      rgb[i * 3] = rgba[j]; rgb[i * 3 + 1] = rgba[j + 1]; rgb[i * 3 + 2] = rgba[j + 2]
    }
    ;(self as unknown as Worker).postMessage({ id, progress: useModel ? '모델 준비 중' : '분석 중' } satisfies AnalyzeResponse)
    const model = useModel ? await getModel() : null
    ;(self as unknown as Worker).postMessage({ id, progress: '분석 중' } satisfies AnalyzeResponse)
    const result = await analyze({ rgb, w, h }, { model })
    if (useModel && !model) result.warnings.push('모델을 불러오지 못해 고전 영상처리로 분석했습니다')
    ;(self as unknown as Worker).postMessage({ id, ok: true, result } satisfies AnalyzeResponse)
  } catch (e) {
    ;(self as unknown as Worker).postMessage({ id, ok: false, error: (e as Error).message } satisfies AnalyzeResponse)
  }
}
