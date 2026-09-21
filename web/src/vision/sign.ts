// 원래 기획의 질문: "표지가 붉게 변했는가?" — 사용자가 짚은 곳의 색을 보정한 뒤 판정한다.
// 표지(구조색 필름)는 타 기관 기술이라 우리가 만들거나 성능을 주장하지 않는다. 여기서 하는 일은
// '사진 속 색을 믿을 수 있게 만드는 것'뿐이고, 기준 색(파랑·빨강)은 가정한 값이다.
import { type Correction, deltaE2000, type RGB, srgbToLab, applyToColor } from './preprocess/color'

const REF_BLUE: RGB = [60 / 255, 70 / 255, 160 / 255]
const REF_RED: RGB = [180 / 255, 60 / 255, 55 / 255]

export interface SignJudgement {
  corrected: RGB
  towards: '붉은 쪽' | '파란 쪽' | '판정 보류'
  deltaERed: number
  deltaEBlue: number
  note: string
}

export function judgeSignColor(
  rgb: Uint8Array | Uint8ClampedArray, w: number, h: number, x: number, y: number, correction: Correction | null, r = 4,
): SignJudgement {
  const acc = [0, 0, 0]
  let n = 0
  for (let yy = Math.max(0, y - r); yy <= Math.min(h - 1, y + r); yy++)
    for (let xx = Math.max(0, x - r); xx <= Math.min(w - 1, x + r); xx++) {
      const j = (yy * w + xx) * 3
      acc[0] += rgb[j]; acc[1] += rgb[j + 1]; acc[2] += rgb[j + 2]; n++
    }
  const raw: RGB = [acc[0] / n / 255, acc[1] / n / 255, acc[2] / n / 255]
  if (!correction) {
    return { corrected: raw, towards: '판정 보류', deltaERed: NaN, deltaEBlue: NaN, note: '기준 카드가 없어 조명 영향을 걷어낼 수 없습니다' }
  }
  const c = applyToColor(correction, raw)
  const lab = srgbToLab(c)
  const dr = deltaE2000(lab, srgbToLab(REF_RED))
  const db = deltaE2000(lab, srgbToLab(REF_BLUE))
  const margin = Math.abs(dr - db)
  return {
    corrected: c,
    towards: margin < 3 ? '판정 보류' : dr < db ? '붉은 쪽' : '파란 쪽',
    deltaERed: dr, deltaEBlue: db,
    note: margin < 3 ? '두 기준 색의 중간이라 어느 쪽인지 말하기 어렵습니다' : '조명 영향을 걷어낸 색 기준입니다',
  }
}
