// 폭(픽셀) → 폭(mm) + 오차 범위 + 안내 문구.
//
// 단일 숫자만 보여 주면 사용자는 그 숫자를 믿는다. 그래서 폭은 항상 범위와 함께 낸다.
// 오차의 출처는 세 가지다.
//   1) 측정 한계 — 픽셀보다 가는 건 잴 수 없다. ±resolutionFloorPx는 항상 남는다.
//   2) 균열을 따라 잰 값들의 흩어짐 — 같은 균열도 위치마다 폭이 다르고, 측정도 흔들린다.
//   3) 축척 — 기준 카드를 찾은 정확도와, 비스듬히 찍어 방향마다 배율이 다른 정도.
// 카드와 균열이 같은 벽면에 있다는 가정은 여기서 확인할 수 없다(화면 안내로 대신한다).
import pipeline from '@shared/pipeline.json'

const cfg = pipeline.measure

export interface ScaleEstimate {
  pxPerMm: number
  /** 상대 불확실성 (0.02 = ±2%) */
  relUncertainty: number
}

export type Guidance = '관찰 필요' | '전문가 점검 권장' | '판정 보류'

export interface WidthResult {
  /** 대표 폭: 균열을 따라 잰 값의 상위 백분위(기본 90%). 최대값은 잡음 한 점에 끌려간다 */
  representativeMm: number
  medianMm: number
  ciMm: [number, number]
  /** 가장 넓은 곳도 측정 한계에 못 미침 → 값보다 '이보다 가늘다'로 읽어야 한다 */
  belowResolution: boolean
  guidance: Guidance
  reasons: string[]
  n: number
}

export function percentile(values: readonly number[], p: number): number {
  if (values.length === 0) throw new Error('빈 배열')
  const s = [...values].sort((a, b) => a - b)
  const rank = (p / 100) * (s.length - 1)
  const lo = Math.floor(rank)
  const hi = Math.ceil(rank)
  return s[lo] + (s[hi] - s[lo]) * (rank - lo)
}

/**
 * 기준 카드 검출 결과 → 축척과 그 불확실성.
 * cornerErrFrac: 모서리 꼭짓점 오차(한 변 대비 비율). anisotropy: 방향별 배율 차이 비율.
 */
export function scaleFromCard(pxPerMm: number, cornerErrFrac: number, anisotropy: number): ScaleEstimate {
  if (!(pxPerMm > 0)) throw new Error('px/mm는 양수여야 한다')
  // 꼭짓점 오차는 7mm 사각형 기준이라 카드 전체(77mm) 기준 축척 오차는 그보다 훨씬 작다.
  // 여기선 보수적으로 1/4만 줄여 반영하고, 비스듬함은 절반(방향 평균)을 더한다.
  const rel = Math.abs(cornerErrFrac) / 4 + Math.abs(anisotropy) / 2
  return { pxPerMm, relUncertainty: rel }
}

export function summarizeWidth(samplesPx: readonly number[], scale: ScaleEstimate | null): WidthResult {
  const reasons: string[] = []
  const valid = samplesPx.filter((w) => Number.isFinite(w) && w > 0)
  if (valid.length === 0) {
    return {
      representativeMm: NaN, medianMm: NaN, ciMm: [NaN, NaN], belowResolution: false,
      guidance: '판정 보류', reasons: ['폭을 잴 수 있는 균열 구간이 없습니다'], n: 0,
    }
  }
  if (!scale) {
    return {
      representativeMm: NaN, medianMm: NaN, ciMm: [NaN, NaN], belowResolution: false,
      guidance: '판정 보류', reasons: ['기준 카드를 찾지 못해 mm로 환산할 수 없습니다'], n: valid.length,
    }
  }

  const repPx = percentile(valid, cfg.representativePercentile)
  const medPx = percentile(valid, 50)
  // 흩어짐: 대표값 주변 사분위 폭의 절반을 측정 흔들림으로 본다
  const spreadPx = (percentile(valid, 75) - percentile(valid, 25)) / 2
  const deltaPx = Math.max(cfg.resolutionFloorPx, spreadPx)
  const s = scale.relUncertainty

  const lo = Math.max(0, (repPx - deltaPx) / (scale.pxPerMm * (1 + s)))
  const hi = (repPx + deltaPx) / (scale.pxPerMm * Math.max(1e-6, 1 - s))
  const belowResolution = repPx < cfg.minMeasurablePx

  let guidance: Guidance
  if (s > cfg.maxScaleUncertainty) {
    guidance = '판정 보류'
    reasons.push(`축척 불확실성이 ±${(s * 100).toFixed(0)}%로 큽니다. 카드를 정면에서 다시 찍어 주세요`)
  } else if (hi >= cfg.guidance.expertReviewMm) {
    guidance = '전문가 점검 권장'
    reasons.push(`추정 폭 범위의 상단이 ${cfg.guidance.expertReviewMm}mm 이상입니다`)
  } else {
    guidance = '관찰 필요'
    reasons.push(`추정 폭 범위가 ${cfg.guidance.expertReviewMm}mm 아래입니다. 시간이 지나며 넓어지는지 다시 찍어 비교하세요`)
  }
  if (belowResolution) reasons.push('이 사진의 해상도로는 이보다 가는 균열을 구분하기 어렵습니다. 더 가까이서 찍으면 정확해집니다')

  return {
    representativeMm: repPx / scale.pxPerMm,
    medianMm: medPx / scale.pxPerMm,
    ciMm: [lo, hi],
    belowResolution,
    guidance,
    reasons,
    n: valid.length,
  }
}
