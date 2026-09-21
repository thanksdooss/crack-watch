// 메인 스레드 ↔ 분석 워커. 사진 파일은 여기서 픽셀로 풀린 뒤 워커로 가고, 어디로도 업로드되지 않는다.
import type { Analysis } from '../vision/analyze'
import type { AnalyzeRequest, AnalyzeResponse } from '../vision/worker/analyze.worker'

let worker: Worker | null = null
let seq = 0

function getWorker(): Worker {
  if (!worker) worker = new Worker(new URL('../vision/worker/analyze.worker.ts', import.meta.url), { type: 'module' })
  return worker
}

export interface Loaded {
  rgba: Uint8ClampedArray
  w: number
  h: number
}

/** File 또는 URL → 픽셀. 원본의 EXIF(위치·기기 정보)는 픽셀로 풀면서 자연히 버려진다. */
export async function loadImage(src: File | string, maxSide = 3000): Promise<Loaded> {
  const blob = typeof src === 'string' ? await (await fetch(src)).blob() : src
  const bmp = await createImageBitmap(blob, { imageOrientation: 'from-image' })
  const f = Math.min(1, maxSide / Math.max(bmp.width, bmp.height))
  const w = Math.round(bmp.width * f), h = Math.round(bmp.height * f)
  const canvas = new OffscreenCanvas(w, h)
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(bmp, 0, 0, w, h)
  bmp.close()
  return { rgba: ctx.getImageData(0, 0, w, h).data, w, h }
}

export function runAnalysis(img: Loaded, useModel: boolean, onProgress?: (s: string) => void): Promise<Analysis> {
  const id = ++seq
  const w = getWorker()
  return new Promise((resolve, reject) => {
    const handler = (ev: MessageEvent<AnalyzeResponse>) => {
      const d = ev.data
      if (d.id !== id) return
      if ('progress' in d) { onProgress?.(d.progress); return }
      w.removeEventListener('message', handler)
      if (d.ok) resolve(d.result)
      else reject(new Error(d.error))
    }
    w.addEventListener('message', handler)
    const req: AnalyzeRequest = { id, rgba: img.rgba, w: img.w, h: img.h, useModel }
    w.postMessage(req)
  })
}
